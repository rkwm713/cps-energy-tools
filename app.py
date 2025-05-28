from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for, session, Response, send_from_directory
import os
import json
import tempfile
import pandas as pd
from werkzeug.utils import secure_filename
from datetime import datetime
import io
import zipfile
from spidaqc import QCChecker
import math
from pathlib import Path
from spida_utils import convert_katapult_to_spidacalc
from flask_cors import CORS

# Import the existing tool modules
from pole_comparison_tool import PoleComparisonTool
from cover_sheet_tool import extract_cover_sheet_data
# Import specific methods from MattsMRR without the GUI class
import MattsMRR

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed file extensions
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'json', 'geojson'}

CORS(app, resources={r"/api/*": {"origins": "*"}})

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Create a web-compatible MRR processor class
class WebMRRProcessor:
    """MRR processor that runs the heavy-lifting logic from MattsMRR without
    instantiating a Tkinter GUI (which is not allowed in a Flask worker thread)."""

    class _HeadlessProcessor(MattsMRR.FileProcessorGUI):
        """Subclass that skips tk.Tk initialisation and stubs GUI widgets."""

        def __init__(self):  # pylint: disable=super-init-not-called
            # DO NOT call super().__init__ (that would create a Tk() root window)
            import os

            # Minimal attribute set required by processing helpers -------------
            self.downloads_path = os.path.join(os.path.expanduser("~"), "Downloads")

            # Stub that swallows .insert / .delete calls so logging works safely
            class _DummyText:  # noqa: D401, pylint: disable=too-few-public-methods
                def insert(self, *_, **__):
                    pass

                def delete(self, *_, **__):
                    pass

            self.info_text = _DummyText()

    def __init__(self):
        # Use the headless subclass instead of the GUI class
        self.processor = WebMRRProcessor._HeadlessProcessor()
        
    def process_files(self, job_json_path, geojson_path=None):
        """Process MRR files and return Excel file path and summary info"""
        try:
            # Load job data
            job_data = self.processor.load_json(job_json_path)
            
            # Load GeoJSON data if provided
            geojson_data = None
            if geojson_path and os.path.exists(geojson_path):
                geojson_data = self.processor.load_json(geojson_path)
            
            # Process the data using the original logic
            df = self.processor.process_data(job_data, geojson_data)
            
            if df.empty:
                return None, {"error": "No data to process"}
            
            # Generate output filename
            json_base = os.path.splitext(os.path.basename(job_json_path))[0]
            output_filename = f"{json_base}_MRR_Output.xlsx"
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            
            # Create Excel file using original logic
            self.processor.create_output_excel(output_path, df, job_data)
            
            # ------------------------------------------------------------
            # Build light-weight preview structure for the front-end
            # ------------------------------------------------------------
            poles: dict[str, dict] = {}

            for _, rec in df.iterrows():
                node_id = rec.get('node_id_1')
                if not node_id:
                    continue

                pole_key = str(rec.get('SCID') or rec.get('Pole #') or node_id)

                # Fetch attacher info using existing helper – only main attachers
                attachers = self.processor.get_attachers_for_node(job_data, node_id)['main_attachers']

                # Try to capture coordinates from node entry
                node_entry = job_data.get('nodes', {}).get(node_id, {})
                lat = node_entry.get('latitude') or node_entry.get('lat')
                lon = node_entry.get('longitude') or node_entry.get('lon')

                if pole_key not in poles:
                    poles[pole_key] = {
                        'pole_number': rec.get('Pole #'),
                        'scid': rec.get('SCID'),
                        'lat': lat,
                        'lon': lon,
                        'attachers': []
                    }

                # If we didn't have coords yet but now found some, update
                if lat and lon and (poles[pole_key].get('lat') is None):
                    poles[pole_key]['lat'] = lat
                    poles[pole_key]['lon'] = lon

                poles[pole_key]['attachers'].extend(attachers)

                # Also process the TO pole of this connection so every pole appears at least once
                node_id_2 = rec.get('node_id_2')
                if node_id_2:
                    node2_rec = rec.copy()
                    node2_rec['node_id_1'] = node_id_2  # reuse helper
                    # minimal fields for pole number / scid
                    node2_rec['Pole #'] = rec.get('To Pole Properties', {}).get('DLOC_number') or rec.get('To Pole Properties', {}).get('pole_tag')
                    node2_rec['SCID'] = rec.get('To Pole Properties', {}).get('scid')
                    # ------------- replicate pole add logic for node2 -------------
                    pole_key2 = str(node2_rec.get('SCID') or node2_rec.get('Pole #') or node_id_2)
                    node_entry2 = job_data.get('nodes', {}).get(node_id_2, {})
                    lat2 = node_entry2.get('latitude') or node_entry2.get('lat')
                    lon2 = node_entry2.get('longitude') or node_entry2.get('lon')
                    if pole_key2 not in poles:
                        poles[pole_key2] = {
                            'pole_number': node2_rec.get('Pole #'),
                            'scid': node2_rec.get('SCID'),
                            'lat': lat2,
                            'lon': lon2,
                            'attachers': []
                        }
                    if lat2 and lon2 and (poles[pole_key2].get('lat') is None):
                        poles[pole_key2]['lat'] = lat2
                        poles[pole_key2]['lon'] = lon2
                    poles[pole_key2]['attachers'].extend(attachers)

            # De-duplicate attachers by name within each pole
            preview = []
            for p in poles.values():
                seen = set()
                uniq = []
                for a in p['attachers']:
                    if a['name'] in seen:
                        continue
                    seen.add(a['name'])
                    uniq.append(a)
                p['attachers'] = uniq
                preview.append(p)

            # Generate summary info (kept separate for display)
            summary = {
                'total_connections': len(df),
                'job_label': job_data.get('label', 'Unknown'),
                'nodes_count': len(job_data.get('nodes', {})),
                'connections_count': len(job_data.get('connections', {})),
                'photos_count': len(job_data.get('photos', {})),
                'output_filename': output_filename,
                'output_path': output_path
            }

            payload = {
                'summary': summary,
                'preview': preview
            }

            return output_path, payload
            
        except Exception as e:
            return None, {"error": str(e)}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/pole-comparison', methods=['GET', 'POST'])
def pole_comparison():
    """Pole Comparison page – handles both the initial form and the processing logic."""
    if request.method == 'POST':
        try:
            # Validate uploaded files
            if 'katapult_file' not in request.files or 'spida_file' not in request.files:
                flash('Both Katapult and SPIDAcalc files are required.', 'error')
                return redirect(url_for('pole_comparison'))

            katapult_file = request.files['katapult_file']
            spida_file = request.files['spida_file']

            if katapult_file.filename == '' or spida_file.filename == '':
                flash('No files selected.', 'error')
                return redirect(url_for('pole_comparison'))

            # Validate file extensions – Katapult must be Excel
            katapult_ext = os.path.splitext(katapult_file.filename)[1].lower()
            if katapult_ext not in ['.xlsx', '.xls']:
                flash('Katapult file must be an Excel spreadsheet (.xlsx or .xls).', 'error')
                return redirect(url_for('pole_comparison'))

            # Threshold value (defaults to 5.0)
            try:
                threshold = float(request.form.get('threshold', 5.0))
            except ValueError:
                threshold = 5.0

            # Persist uploads to temp directory
            k_filename = secure_filename(katapult_file.filename)
            s_filename = secure_filename(spida_file.filename)
            k_path = os.path.join(app.config['UPLOAD_FOLDER'], k_filename)
            s_path = os.path.join(app.config['UPLOAD_FOLDER'], s_filename)
            katapult_file.save(k_path)
            spida_file.save(s_path)

            # Run comparison
            tool = PoleComparisonTool(threshold=threshold)
            comparison_data, verification = tool.process_files(k_path, s_path)
            issue_rows = tool.apply_threshold_and_find_issues(comparison_data)

            # Build summary dict
            verification_errors = (len(verification.missing_in_spida) +
                                   len(verification.missing_in_katapult) +
                                   len(verification.duplicates_in_spida) +
                                   len(verification.duplicates_in_katapult) +
                                   len(verification.formatting_issues))

            summary = {
                'total_poles': len(comparison_data),
                'poles_with_issues': len(issue_rows),
                'verification_errors': verification_errors,
                'threshold': threshold
            }

            # Helper to convert dataclass → dict for JSON/session storage
            def row_to_dict(row):
                return {
                    'pole_number': row.pole_number,
                    'scid_number': row.scid_number,
                    'spida_pole_number': row.spida_pole_number,
                    'katapult_pole_number': row.katapult_pole_number,
                    'spida_pole_spec': row.spida_pole_spec,
                    'katapult_pole_spec': row.katapult_pole_spec,
                    'spida_existing_loading': row.spida_existing_loading,
                    'katapult_existing_loading': row.katapult_existing_loading,
                    'spida_final_loading': row.spida_final_loading,
                    'katapult_final_loading': row.katapult_final_loading,
                    'existing_delta': row.existing_delta,
                    'final_delta': row.final_delta,
                    'has_issue': row.has_issue
                }

            session['pole_comparison_results'] = [row_to_dict(r) for r in comparison_data]
            session['pole_comparison_threshold'] = threshold

            # Clean up temporary files
            os.remove(k_path)
            os.remove(s_path)

            return render_template(
                'pole_comparison.html',
                all_rows=comparison_data,
                issue_rows=issue_rows,
                verification=verification,
                summary=summary,
                threshold=threshold
            )

        except Exception as e:
            flash(str(e), 'error')
            return redirect(url_for('pole_comparison'))

    # GET request – just render the empty form
    return render_template('pole_comparison.html')

# ---------------------------------------------------------------------------
# CSV download for Pole Comparison results
# ---------------------------------------------------------------------------

@app.route('/pole-comparison/download')
def pole_comparison_download():
    """Stream a CSV of the last pole-comparison run (stored in session)."""
    issues_only = request.args.get('issues_only', 'false').lower() == 'true'

    results = session.get('pole_comparison_results')
    if not results:
        flash('No comparison data available to export.', 'error')
        return redirect(url_for('pole_comparison'))

    export_rows = [r for r in results if r.get('has_issue')] if issues_only else results

    # Convert to CSV
    df = pd.DataFrame(export_rows)
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    filename = f"pole_comparison_{'issues' if issues_only else 'all'}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

@app.route('/cover-sheet')
def cover_sheet():
    return render_template('cover_sheet.html')

@app.route('/mrr-tool')
def mrr_tool():
    return render_template('mrr_tool.html')

@app.route('/how-to-guide')
def how_to_guide():
    return render_template('how_to_guide.html')

@app.route('/spidacalc-qc')
def spidacalc_qc():
    return render_template('spidacalc_qc.html')

@app.route('/api/pole-comparison', methods=['POST'])
def api_pole_comparison():
    try:
        if 'katapult_file' not in request.files or 'spida_file' not in request.files:
            return jsonify({'error': 'Both Katapult Excel file and SPIDAcalc JSON file are required'}), 400
        
        katapult_file = request.files['katapult_file']
        spida_file = request.files['spida_file']
        threshold = float(request.form.get('threshold', 5.0))
        
        if katapult_file.filename == '' or spida_file.filename == '':
            return jsonify({'error': 'No files selected'}), 400
        
        if not (allowed_file(katapult_file.filename) and allowed_file(spida_file.filename)):
            return jsonify({'error': 'Invalid file types'}), 400
        
        # Save uploaded files
        katapult_filename = secure_filename(katapult_file.filename)
        spida_filename = secure_filename(spida_file.filename)
        
        katapult_path = os.path.join(app.config['UPLOAD_FOLDER'], katapult_filename)
        spida_path = os.path.join(app.config['UPLOAD_FOLDER'], spida_filename)
        
        katapult_file.save(katapult_path)
        spida_file.save(spida_path)
        
        # Process files using the existing tool
        tool = PoleComparisonTool(threshold=threshold)
        comparison_data, verification_result = tool.process_files(katapult_path, spida_path)
        
        # Apply threshold and find issues
        issues_data = tool.apply_threshold_and_find_issues(comparison_data)
        
        # Convert data to JSON-serializable format
        results = []
        for row in comparison_data:
            results.append({
                'pole_number': row.pole_number,
                'scid_number': row.scid_number,
                'spida_pole_number': row.spida_pole_number,
                'katapult_pole_number': row.katapult_pole_number,
                'spida_pole_spec': row.spida_pole_spec,
                'katapult_pole_spec': row.katapult_pole_spec,
                'spida_existing_loading': row.spida_existing_loading,
                'katapult_existing_loading': row.katapult_existing_loading,
                'spida_final_loading': row.spida_final_loading,
                'katapult_final_loading': row.katapult_final_loading,
                'existing_delta': row.existing_delta,
                'final_delta': row.final_delta,
                'has_issue': row.has_issue
            })
        
        issues = []
        for row in issues_data:
            issues.append({
                'pole_number': row.pole_number,
                'scid_number': row.scid_number,
                'spida_pole_number': row.spida_pole_number,
                'katapult_pole_number': row.katapult_pole_number,
                'spida_pole_spec': row.spida_pole_spec,
                'katapult_pole_spec': row.katapult_pole_spec,
                'spida_existing_loading': row.spida_existing_loading,
                'katapult_existing_loading': row.katapult_existing_loading,
                'spida_final_loading': row.spida_final_loading,
                'katapult_final_loading': row.katapult_final_loading,
                'existing_delta': row.existing_delta,
                'final_delta': row.final_delta,
                'has_issue': row.has_issue
            })
        
        verification = {
            'missing_in_spida': verification_result.missing_in_spida,
            'missing_in_katapult': verification_result.missing_in_katapult,
            'duplicates_in_spida': verification_result.duplicates_in_spida,
            'duplicates_in_katapult': verification_result.duplicates_in_katapult,
            'formatting_issues': verification_result.formatting_issues
        }
        
        # Clean up uploaded files
        os.remove(katapult_path)
        os.remove(spida_path)
        
        return jsonify({
            'results': results,
            'issues': issues,
            'verification': verification,
            'summary': {
                'total_poles': len(results),
                'poles_with_issues': len(issues),
                'threshold': threshold
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/cover-sheet', methods=['POST'])
def api_cover_sheet():
    try:
        if 'spida_file' not in request.files:
            return jsonify({'error': 'SPIDAcalc JSON file is required'}), 400
        
        spida_file = request.files['spida_file']
        
        if spida_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(spida_file.filename):
            return jsonify({'error': 'Invalid file type'}), 400
        
        # Save uploaded file
        spida_filename = secure_filename(spida_file.filename)
        spida_path = os.path.join(app.config['UPLOAD_FOLDER'], spida_filename)
        spida_file.save(spida_path)
        
        # Process file using the existing tool
        with open(spida_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        cover_sheet_data = extract_cover_sheet_data(json_data)
        
        # Clean up uploaded file
        os.remove(spida_path)
        
        return jsonify(cover_sheet_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/mrr-process', methods=['POST'])
def api_mrr_process():
    try:
        if 'job_file' not in request.files:
            return jsonify({'error': 'Job JSON file is required'}), 400
        
        job_file = request.files['job_file']
        geojson_file = request.files.get('geojson_file')  # Optional
        
        if job_file.filename == '':
            return jsonify({'error': 'No Job JSON file selected'}), 400
        
        if not allowed_file(job_file.filename):
            return jsonify({'error': 'Invalid Job JSON file type'}), 400
        
        # Check GeoJSON file if provided
        if geojson_file and geojson_file.filename != '' and not allowed_file(geojson_file.filename):
            return jsonify({'error': 'Invalid GeoJSON file type'}), 400
        
        # Save uploaded files
        job_filename = secure_filename(job_file.filename)
        job_path = os.path.join(app.config['UPLOAD_FOLDER'], job_filename)
        job_file.save(job_path)
        
        # Save GeoJSON file if provided
        geojson_path = None
        if geojson_file and geojson_file.filename != '':
            geojson_filename = secure_filename(geojson_file.filename)
            geojson_path = os.path.join(app.config['UPLOAD_FOLDER'], geojson_filename)
            geojson_file.save(geojson_path)
        
        # Process files using the full MRR logic
        processor = WebMRRProcessor()
        output_path, result = processor.process_files(job_path, geojson_path)
        
        # Clean up uploaded files
        os.remove(job_path)
        if geojson_path and os.path.exists(geojson_path):
            os.remove(geojson_path)
        
        if output_path:
            return jsonify({
                'success': True,
                'message': 'MRR processing completed successfully',
                'summary': result.get('summary'),
                'preview': result.get('preview'),
                'download_available': True
            })
        else:
            return jsonify({'error': result.get('error', 'Processing failed')}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-mrr/<filename>')
def download_mrr_file(filename):
    """Download the generated MRR Excel file"""
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(filename))
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/export-csv', methods=['POST'])
def api_export_csv():
    try:
        data = request.json
        results = data.get('results', [])
        export_type = data.get('export_type', 'all')  # 'all' or 'issues'
        
        if export_type == 'issues':
            results = [r for r in results if r.get('has_issue', False)]
        
        # Convert to DataFrame
        df = pd.DataFrame(results)
        
        # Create CSV in memory
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        # Create response
        response = app.response_class(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename=pole_comparison_{export_type}.csv'}
        )
        
        return response
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/launch-mrr-gui')
def launch_mrr_gui():
    """Launch the MRR GUI tool"""
    try:
        # Create and run the GUI
        import tkinter as tk
        root = tk.Tk()
        app_gui = MattsMRR.FileProcessorGUI()
        app_gui.mainloop()
        return jsonify({'message': 'MRR GUI launched successfully'})
    except Exception as e:
        return jsonify({'error': f'Failed to launch GUI: {str(e)}'}), 500

@app.route('/api/spidacalc-qc', methods=['POST'])
def api_spidacalc_qc():
    try:
        # ------------------------------------------------------------------
        # Validate and persist SPIDAcalc JSON (required)
        # ------------------------------------------------------------------
        if 'spida_file' not in request.files:
            return jsonify({'error': 'SPIDAcalc JSON file is required'}), 400

        spida_file = request.files['spida_file']
        if spida_file.filename == '':
            return jsonify({'error': 'SPIDAcalc JSON file not selected'}), 400

        if not allowed_file(spida_file.filename):
            return jsonify({'error': 'Invalid SPIDAcalc file type'}), 400

        spida_filename = secure_filename(spida_file.filename)
        spida_path = os.path.join(app.config['UPLOAD_FOLDER'], spida_filename)
        spida_file.save(spida_path)

        # ------------------------------------------------------------------
        # Katapult JSON is OPTIONAL – only process if included in upload
        # ------------------------------------------------------------------
        kata_json = {}
        kata_path = None
        if 'katapult_file' in request.files and request.files['katapult_file'].filename != '':
            kata_file = request.files['katapult_file']

            # Validate extension
            if not allowed_file(kata_file.filename):
                return jsonify({'error': 'Invalid Katapult file type'}), 400

            kata_filename = secure_filename(kata_file.filename)
            kata_path = os.path.join(app.config['UPLOAD_FOLDER'], kata_filename)
            kata_file.save(kata_path)

            # Load Katapult JSON
            with open(kata_path, 'r', encoding='utf-8') as f:
                kata_json = json.load(f)

        # ------------------------------------------------------------------
        # Load SPIDA JSON (always required)
        # ------------------------------------------------------------------
        with open(spida_path, 'r', encoding='utf-8') as f:
            spida_json = json.load(f)

        # Run QC checks
        checker = QCChecker(spida_json, kata_json)
        issues_by_pole = checker.run_checks()

        # ------------------------------------------------------------------
        # Build poles list for front-end (extract id, latitude, longitude)
        # ------------------------------------------------------------------
        def extract_poles(spida: dict) -> list:
            """Return a list of {id, lat, lon?} dicts pulled from the SPIDAcalc JSON.

            The structure of SPIDAcalc job files can differ depending on the export
            options that were used.  In most cases pole coordinates can be found in
            either 1) leads → locations → mapLocation.coordinates (GeoJSON-style
            lon/lat) or 2) the legacy nodes list with various possible latitude /‐
            longitude keys.  This helper looks in both places and deduplicates on
            the pole id so the front-end receives one entry per pole.
            """

            poles: list[dict] = []

            # ----------------------------------------------------------
            # 1) Modern "leads / locations" structure
            # ----------------------------------------------------------
            for lead in spida.get('leads', []):
                for loc in lead.get('locations', []):
                    label = loc.get('label') or loc.get('id') or loc.get('poleId')
                    if not label:
                        continue

                    coords = loc.get('mapLocation', {}).get('coordinates', [])
                    if isinstance(coords, (list, tuple)) and len(coords) == 2:
                        lon, lat = coords
                        try:
                            lat = float(lat)
                            lon = float(lon)
                            poles.append({'id': str(label), 'lat': lat, 'lon': lon})
                        except (TypeError, ValueError):
                            # Coordinates present but not numeric – fall back to id only
                            poles.append({'id': str(label)})
                    else:
                        # No coordinates – still record the pole id so it appears in UI
                        poles.append({'id': str(label)})

            # ----------------------------------------------------------
            # 2) Legacy/alternate "nodes" structure
            # ----------------------------------------------------------
            lat_keys = ['latitude', 'lat', 'Latitude', 'y', 'northing']
            lon_keys = ['longitude', 'lon', 'Longitude', 'x', 'easting']

            for node in spida.get('nodes', []):
                if not isinstance(node, dict):
                    continue

                pid = node.get('id') or node.get('poleId') or node.get('nodeId')
                if not pid:
                    continue

                lat = next((node.get(k) for k in lat_keys if node.get(k) is not None), None)
                lon = next((node.get(k) for k in lon_keys if node.get(k) is not None), None)

                if lat is not None and lon is not None:
                    try:
                        lat_f = float(lat)
                        lon_f = float(lon)
                        poles.append({'id': str(pid), 'lat': lat_f, 'lon': lon_f})
                    except (TypeError, ValueError):
                        poles.append({'id': str(pid)})
                else:
                    poles.append({'id': str(pid)})

            # ----------------------------------------------------------
            # 3) Deduplicate – prefer entry that has coordinates
            # ----------------------------------------------------------
            unique: dict[str, dict] = {}
            for p in poles:
                pid = p['id']
                if pid not in unique:
                    unique[pid] = p
                else:
                    # If existing record lacks coords but new one has, replace
                    if ('lat' in p and 'lat' not in unique[pid]):
                        unique[pid] = p
            return list(unique.values())

        poles = extract_poles(spida_json)

        # Ensure poles referenced in issues are always present
        for pid in issues_by_pole.keys():
            if not any(p['id'] == pid for p in poles):
                poles.append({'id': pid})

        # Flatten for count
        total_issues = sum(len(lst) for lst in issues_by_pole.values())

        # ------------------------------------------------------------------
        # Clean up saved files
        # ------------------------------------------------------------------
        os.remove(spida_path)
        if kata_path and os.path.exists(kata_path):
            os.remove(kata_path)

        return jsonify({'issues_by_pole': issues_by_pole, 'issues_count': total_issues, 'poles': poles})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/spida-import', methods=['GET', 'POST'])
def spida_import():
    if request.method == 'POST':
        try:
            if 'katapult_file' not in request.files:
                return render_template('spida_import.html', error='No file uploaded')
            
            file = request.files['katapult_file']
            if file.filename == '':
                return render_template('spida_import.html', error='No file selected')
            
            if not file.filename.endswith('.json'):
                return render_template('spida_import.html', error='File must be a JSON file')
            
            # Save uploaded file
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Load and process the Katapult JSON
            job_id = os.path.splitext(filename)[0]
            job_name = "CPS Energy Make-Ready"  # or pull from form
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    kat_json = json.load(f)

                spida_json = convert_katapult_to_spidacalc(kat_json, job_id, job_name)

                output_filename = f"{job_id}_for_spidacalc.json"
                output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
                with open(output_path, 'w') as out:
                    json.dump(spida_json, out, indent=2)

                return render_template('spida_import.html',
                                    success='Converted successfully!',
                                    download_url=url_for('download_spida_file', filename=output_filename))

            except Exception as e:
                return render_template('spida_import.html',
                                    error=f'Conversion failed: {e}')
            
        except Exception as e:
            print(f"Error processing file: {str(e)}")
            return render_template('spida_import.html', 
                                 error=f'Error processing file: {str(e)}')
    
    return render_template('spida_import.html')

@app.route('/download-spida-file/<filename>')
def download_spida_file(filename):
    try:
        return send_file(
            os.path.join(app.config['UPLOAD_FOLDER'], filename),
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(str(e), 'error')
        return redirect(url_for('spida_import'))

# ---------------------------------------------------------------------------
# React front-end in production
# ---------------------------------------------------------------------------

# Path to the React build directory (created by `npm run build` inside /frontend)
REACT_BUILD_DIR = Path(__file__).resolve().parent / 'frontend' / 'dist'

@app.route('/app', defaults={'path': ''})
@app.route('/app/<path:path>')
def serve_react(path):
    """Serve the compiled React SPA (created with Vite). During development
    this route is optional; React devserver runs separately. In production we
    build React into frontend/dist and Flask serves those static files.
    """
    # If the requested resource exists, return it directly
    if path and (REACT_BUILD_DIR / path).exists():
        return send_from_directory(REACT_BUILD_DIR, path)
    # Otherwise, return index.html so React Router can handle client side route
    return send_from_directory(REACT_BUILD_DIR, 'index.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 