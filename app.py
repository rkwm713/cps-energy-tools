from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for, session, Response
import os
import json
import tempfile
import pandas as pd
from werkzeug.utils import secure_filename
from datetime import datetime
import io
import zipfile
from spidaqc import QCChecker

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

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Create a web-compatible MRR processor class
class WebMRRProcessor:
    def __init__(self):
        # Create an instance of the original FileProcessorGUI to access its methods
        # but we won't use the GUI parts
        self.processor = MattsMRR.FileProcessorGUI()
        
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
            
            # Generate summary info
            summary = {
                'total_connections': len(df),
                'job_label': job_data.get('label', 'Unknown'),
                'nodes_count': len(job_data.get('nodes', {})),
                'connections_count': len(job_data.get('connections', {})),
                'photos_count': len(job_data.get('photos', {})),
                'output_filename': output_filename,
                'output_path': output_path
            }
            
            return output_path, summary
            
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
            # Store the output file path in session or return download info
            return jsonify({
                'success': True,
                'message': 'MRR processing completed successfully',
                'summary': result,
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 