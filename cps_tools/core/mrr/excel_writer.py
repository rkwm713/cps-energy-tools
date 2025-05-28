"""Excel export helper for the MRR tool.

This module takes a :class:`pandas.DataFrame` produced by the processor logic
and writes it to an ``.xlsx`` file **using *openpyxl* in *write-only* mode** so
large (>10 000 rows) reports do not exhaust memory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import xlsxwriter # Import xlsxwriter for rich formatting

from .excel_formatter_utils import (
    format_height_feet_inches,
    get_attachers_for_node,
    get_lowest_heights_for_connection,
    get_movement_summary,
    get_short_cps_movement_summary,
    get_pole_structure,
    has_proposed_wires,
    get_attachment_action,
    compare_scids,
    find_backspan_connection_id,
    find_backspan_connection_id_by_scid,
    get_backspan_attachers,
    get_reference_attachers,
    calculate_bearing,
    get_work_type,
    get_responsible_party,
    get_midspan_proposed_heights,
    get_neutral_wire_height,
    _is_number # Private helper, but needed for now
)

__all__ = [
    "write_basic_excel",
    "write_formatted_excel",
]


def write_basic_excel(df: pd.DataFrame, output: Path, *, sheet_name: str = "MRR") -> Path:
    """Write *df* to *output* using the fastest streaming mode available (openpyxl).

    Parameters
    ----------
    df:
        The data frame containing the rows to export.
    output:
        Destination ``.xlsx`` path (parent directories are created if needed).
    sheet_name:
        Name of the worksheet to create.  Defaults to ``MRR``.

    Returns
    -------
    Path
        The resolved path of the written workbook.  Useful for logging / tests.
    """

    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook(write_only=True)
    ws = wb.create_sheet(sheet_name)

    for row in dataframe_to_rows(df, index=False, header=True):
        ws.append(row)

    wb.save(output)
    wb.close()
    return output

def write_formatted_excel(path: Path, df: pd.DataFrame, job_data: Dict[str, Any]) -> Path:
    """Write a richly formatted Excel report using xlsxwriter, replicating MattsMRR GUI output."""
    
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    wb = writer.book
    ws = wb.add_worksheet('Sheet1')

    # === Formats ===
    section_header_format = wb.add_format({
        'bold': True, 
        'align': 'center', 
        'valign': 'vcenter',
        'bg_color': '#B7DEE8', 
        'border': 1, 
        'text_wrap': True
    })
    
    sub_header_format = wb.add_format({
        'bold': True, 
        'align': 'center', 
        'valign': 'vcenter',
        'border': 1, 
        'bg_color': '#DAEEF3', 
        'text_wrap': True
    })
    
    cell_format = wb.add_format({
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True, 
        'border': 1
    })
    
    underground_format = wb.add_format({
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
        'border': 1,
        'bg_color': '#F2DCDB',  # Light red background
        'font_color': '#000000'
    })
    
    backspan_format = wb.add_format({
        'bold': True, 
        'align': 'center', 
        'valign': 'vcenter',
        'border': 1, 
        'bg_color': '#D9E1F2'
    })
    
    reference_format = wb.add_format({
        'bold': True, 
        'align': 'center', 
        'valign': 'vcenter',
        'border': 1, 
        'bg_color': '#E2EFD9'  # Light green background
    })
    
    # Yellow highlight format for backspan column Q cells (needs verification)
    yellow_highlight_format = wb.add_format({
        'align': 'center',
        'valign': 'vcenter',
        'text_wrap': True,
        'border': 1,
        'bg_color': '#FFFF00'  # Yellow background for verification
    })

    # Set default row height
    ws.set_default_row(20)

    # === Columns ===
    columns = [
        "Connection ID", "Operation Number", "Attachment Action", "Pole Owner", "Pole #", "SCID", "Pole Structure",
        "Proposed Riser", "Proposed Guy", "PLA (%) with proposed attachment", "Construction Grade of Analysis",
        "Height Lowest Com", "Height Lowest CPS Electrical", "Attacher Description",
        "Attachment Height - Existing", "Attachment Height - Proposed",
        "Mid-Span (same span as existing)",
        "One Touch Transfer", "Remedy Description", "Responsible Party",
        "Existing CPSE Red Tag on Pole", "Pole Data Missing in GIS", "CPSE Application Comments",
        "Movement Summary"
    ]

    # Write headers
    _write_excel_headers(ws, columns, section_header_format, sub_header_format)
    
    row_pos = 3  # Start after headers

    # Create a list to store all rows with their attachers in the correct order
    all_rows = []
    
    # Process each connection in order of operation number
    for _, record in df.sort_values('Operation Number').iterrows():
        connection_id = record['Connection ID']
        node_id_1 = record['node_id_1']
        
        # Check if this is an underground connection
        connection_data = job_data.get("connections", {}).get(connection_id, {})
        is_underground = connection_data.get("attributes", {}).get("connection_type", {}).get("button_added") == "underground cable"
        
        # Get attacher data
        attacher_data = get_attachers_for_node(job_data, node_id_1)
        
        # Get lowest heights for this connection
        lowest_com, lowest_cps = get_lowest_heights_for_connection(job_data, connection_id)
        
        # Get From Pole/To Pole values
        from_pole_props = record.get("From Pole Properties", {})
        to_pole_props = record.get("To Pole Properties", {})
        
        # Get From Pole value (DLOC_number or SCID)
        from_pole_value = from_pole_props.get('DLOC_number')
        if not from_pole_value or from_pole_value == 'N/A':
            from_pole_value = from_pole_props.get('pole_tag', 'N/A')
        if from_pole_value == 'N/A':
            from_pole_value = from_pole_props.get('scid', 'N/A')
        
        # Get To Pole value (DLOC_number or SCID)
        to_pole_value = to_pole_props.get('DLOC_number')
        if not to_pole_value or to_pole_value == 'N/A':
            to_pole_value = to_pole_props.get('pole_tag', 'N/A')
        if to_pole_value == 'N/A':
            to_pole_value = to_pole_props.get('scid', 'N/A')
        
        # For underground connections, set To Pole value to "UG"
        if is_underground:
            to_pole_value = "UG"
        else:
            # Add PL prefix if needed for To Pole value
            if to_pole_value != 'N/A' and not to_pole_value.upper().startswith('NT') and 'PL' not in to_pole_value.upper():
                to_pole_value = f"PL{to_pole_value}"
        
        # Store the connection info and its related data
        connection_data = {
            'record': record,
            'lowest_com': lowest_com,
            'lowest_cps': lowest_cps,
            'from_pole_value': from_pole_value,
            'to_pole_value': to_pole_value,
            'main_attachers': attacher_data['main_attachers'],
            'reference_spans': attacher_data['reference_spans'],
            'backspan': attacher_data['backspan'],
            'is_underground': is_underground
        }
        
        all_rows.append(connection_data)
    
    # Now write to Excel maintaining the order
    for connection_data in all_rows:
        group_start_row = row_pos  # Set this at the start of each group
        record = connection_data['record']
        is_underground = connection_data['is_underground']
        
        # Set group_end_row before any merges
        group_end_row = row_pos - 1

        # Process main attachers
        main_attachers = connection_data['main_attachers']
        
        if is_underground:
            # Ensure we have at least 3 rows total for data (before From/To Pole overlap)
            while len(main_attachers) < 3:
                main_attachers.append({'name': '', 'existing_height': '', 'proposed_height': '', 'raw_height': 0})

            attacher_start = row_pos
            # Write main attachers for the from pole
            for i, attacher in enumerate(main_attachers):
                current_row = row_pos + i
                _write_attacher_row(ws, current_row, attacher, record['Connection ID'], job_data, cell_format)
            row_pos += len(main_attachers)
            attacher_end = row_pos - 1

            # Process reference spans for underground connections
            for ref_span in connection_data['reference_spans']:
                bearing = ref_span.get('bearing', '')
                ref_data = ref_span.get('data', [])
                # Find the best available pole identifier for the reference span
                ref_to_pole = None
                # Try to get the to_node_id (the other node in the reference connection)
                for conn in job_data.get('connections', {}).values():
                    if 'reference' in str(conn.get('attributes', {}).get('connection_type', {})).lower():
                        if conn.get('node_id_1') == record['node_id_1']:
                            ref_to_pole = conn.get('node_id_2')
                        elif conn.get('node_id_2') == record['node_id_1']:
                            ref_to_pole = conn.get('node_id_1')
                        if ref_to_pole:
                            break
                ref_pole_label = None
                if ref_to_pole:
                    node_props = job_data.get('nodes', {}).get(ref_to_pole, {}).get('attributes', {})
                    # Try PL_Number
                    pl_number = node_props.get('PL_Number', {})
                    if pl_number:
                        pl_number_val = next(iter(pl_number.values()), None)
                        if pl_number_val:
                            ref_pole_label = str(pl_number_val)
                    # Try DLOC_number
                    if not ref_pole_label:
                        dloc_number = node_props.get('DLOC_number', {})
                        if dloc_number:
                            dloc_number_val = next(iter(dloc_number.values()), None)
                            if dloc_number_val:
                                ref_pole_label = str(dloc_number_val)
                    # Try pole_tag:tagtext
                    if not ref_pole_label:
                        pole_tag = node_props.get('pole_tag', {})
                        if pole_tag:
                            tagtext = next(iter(pole_tag.values()), {}).get('tagtext', None)
                            if tagtext:
                                ref_pole_label = str(tagtext)
                    # Add PL prefix if needed
                    if ref_pole_label and not ref_pole_label.upper().startswith('NT') and not ref_pole_label.upper().startswith('PL'):
                        ref_pole_label = f"PL{ref_pole_label}"
                if ref_data:
                    if bearing and ref_pole_label:
                        header_text = f"REF ({bearing}) to {ref_pole_label}"
                    elif bearing:
                        header_text = f"REF ({bearing})"
                    elif ref_pole_label:
                        header_text = f"REF to {ref_pole_label}"
                    else:
                        header_text = "REF"
                    ws.merge_range(row_pos, 13, row_pos, 16, header_text, reference_format)
                    row_pos += 1
                    for ref_row in ref_data:
                        _write_attacher_row(ws, row_pos, ref_row, record['Connection ID'], job_data, cell_format, main_attachers=main_attachers, yellow_highlight_format=yellow_highlight_format)
                        row_pos += 1

            # Process backspan data for underground connections
            backspan_data = connection_data['backspan']
            if backspan_data['data']:
                bearing = backspan_data['bearing']
                header_text = f"Backspan ({bearing})" if bearing else "Backspan"
                ws.merge_range(row_pos, 13, row_pos, 16, header_text, backspan_format)
                row_pos += 1
                # Only include wires (and OHG if present) from the main list
                main_wires = [
                    a for a in main_attachers
                    if all(x not in a['name'].lower() for x in ['guy', 'equipment', 'riser', 'street light'])
                ]

                # Build node_properties for SCID lookup
                node_properties = {nid: props for nid, props in job_data.get('nodes', {}).items()}
                for k, v in node_properties.items():
                    if 'attributes' in v:
                        node_properties[k] = v['attributes']

                # Find the backspan connection_id using SCID logic
                backspan_conn_id = find_backspan_connection_id_by_scid(job_data, record['node_id_1'], node_properties)


                # Write the backspan rows
                for bs_row in main_wires:
                    _write_attacher_row(
                        ws, row_pos, bs_row,
                        record['Connection ID'],  # For O/P (main list)
                        job_data, cell_format,
                        backspan_conn_id=backspan_conn_id,  # For Q (mid-span)
                        column_q_format=yellow_highlight_format,  # Yellow highlight for verification
                        yellow_highlight_format=yellow_highlight_format
                    )
                    row_pos += 1

            # Calculate From Pole/To Pole positions - they will overlap with the last two rows
            header_row = row_pos - 2
            value_row = row_pos - 1

            # Merge and fill Height Lowest Com/Electrical with 'NA' for all attacher rows (not for ref/backspan or header rows)
            if header_row - 1 > attacher_start:
                ws.merge_range(attacher_start, 11, header_row - 1, 11, "NA", cell_format)
                ws.merge_range(attacher_start, 12, header_row - 1, 12, "NA", cell_format)
            else:
                ws.write(attacher_start, 11, "NA", cell_format)
                ws.write(attacher_start, 12, "NA", cell_format)

            # Write From Pole/To Pole headers and values (overlapping last two rows, like aerial)
            ws.write(header_row, 11, "From Pole", sub_header_format)
            ws.write(header_row, 12, "To Pole", sub_header_format)
            ws.write(value_row, 11, connection_data['from_pole_value'], cell_format)
            ws.write(value_row, 12, connection_data['to_pole_value'], cell_format)
            
            # Set group_end_row before merges
            group_end_row = row_pos - 1

            # Store the final remedy text and merge/write it after all rows for the group are written
            install_lines = []
            riser_lines = set()
            for attacher in main_attachers:
                if attacher.get('is_proposed'):
                    company = attacher['name'].split()[0]
                    height = attacher.get('proposed_height') or attacher.get('existing_height') or ""
                    install_line = f"Install proposed {attacher['name']} at {height}" if height else f"Install proposed {attacher['name']}"
                    install_lines.append(install_line)
                    riser_lines.add(f"Install proposed {company} Riser @ {height} to UG connection" if height else f"Install proposed {company} Riser to UG connection")
            if not install_lines and main_attachers:
                attacher = main_attachers[0]
                company = attacher['name'].split()[0]
                height = attacher.get('proposed_height') or attacher.get('existing_height') or ""
                install_lines.append(f"Install proposed {attacher['name']} at {height}" if height else f"Install proposed {attacher['name']}")
                riser_lines.add(f"Install proposed {company} Riser @ {height} to UG connection" if height else f"Install proposed {company} Riser to UG connection")
            movement_summary = get_movement_summary(main_attachers)
            remedy_text = "\n".join(install_lines + list(riser_lines))
            if movement_summary:
                remedy_text += f"\n{movement_summary}"
            group_end_row = row_pos - 1
        else:
            # Ensure we have at least 3 rows total for data (before From/To Pole overlap)
            while len(main_attachers) < 3:
                main_attachers.append({'name': '', 'existing_height': '', 'proposed_height': '', 'raw_height': 0})

            # Write main attachers
            for i, attacher in enumerate(main_attachers):
                current_row = row_pos + i
                _write_attacher_row(ws, current_row, attacher, record['Connection ID'], job_data, cell_format)
            row_pos += len(main_attachers)

            group_end_row = row_pos - 1

            # Process reference spans
            for ref_span in connection_data['reference_spans']:
                bearing = ref_span.get('bearing', '')
                ref_data = ref_span.get('data', [])
                
                if ref_data:
                    # Find the best available pole identifier for the reference span
                    ref_to_pole = None
                    for conn in job_data.get('connections', {}).values():
                        if 'reference' in str(conn.get('attributes', {}).get('connection_type', {})).lower():
                            if conn.get('node_id_1') == record['node_id_1']:
                                ref_to_pole = conn.get('node_id_2')
                            elif conn.get('node_id_2') == record['node_id_1']:
                                ref_to_pole = conn.get('node_id_1')
                            if ref_to_pole:
                                break
                    ref_pole_label = None
                    if ref_to_pole:
                        node_props = job_data.get('nodes', {}).get(ref_to_pole, {}).get('attributes', {})
                        # Try PL_Number
                        pl_number = node_props.get('PL_Number', {})
                        if pl_number:
                            pl_number_val = next(iter(pl_number.values()), None)
                            if pl_number_val:
                                ref_pole_label = str(pl_number_val)
                        # Try DLOC_number
                        if not ref_pole_label:
                            dloc_number = node_props.get('DLOC_number', {})
                            if dloc_number:
                                dloc_number_val = next(iter(dloc_number.values()), None)
                                if dloc_number_val:
                                    ref_pole_label = str(dloc_number_val)
                        # Try pole_tag:tagtext
                        if not ref_pole_label:
                            pole_tag = node_props.get('pole_tag', {})
                            if pole_tag:
                                tagtext = next(iter(pole_tag.values()), {}).get('tagtext', None)
                                if tagtext:
                                    ref_pole_label = str(tagtext)
                        # Add PL prefix if needed
                        if ref_pole_label and not ref_pole_label.upper().startswith('NT') and not ref_pole_label.upper().startswith('PL'):
                            ref_pole_label = f"PL{ref_pole_label}"
                    if ref_data:
                        if bearing and ref_pole_label:
                            header_text = f"REF ({bearing}) to {ref_pole_label}"
                        elif bearing:
                            header_text = f"REF ({bearing})"
                        elif ref_pole_label:
                            header_text = f"REF to {ref_pole_label}"
                        else:
                            header_text = "REF"
                        ws.merge_range(row_pos, 13, row_pos, 16, header_text, reference_format)
                        row_pos += 1
                        for ref_row in ref_data:
                            _write_attacher_row(ws, row_pos, ref_row, record['Connection ID'], job_data, cell_format, main_attachers=main_attachers, yellow_highlight_format=yellow_highlight_format)
                            row_pos += 1

            # Process backspan data
            backspan_data = connection_data['backspan']
            if backspan_data['data']:
                # Write backspan header with bearing
                bearing = backspan_data['bearing']
                header_text = f"Backspan ({bearing})" if bearing else "Backspan"
                ws.merge_range(row_pos, 13, row_pos, 16, header_text, backspan_format)
                row_pos += 1

                # Find the backspan connection
                backspan_conn_id = find_backspan_connection_id(job_data, record['node_id_1'])
                
                
                # Only include wires (and OHG if present) from the main list
                main_wires = [
                    a for a in main_attachers
                    if all(x not in a['name'].lower() for x in ['guy', 'equipment', 'riser', 'street light'])
                ]
                
                # Write the backspan rows
                for bs_row in main_wires:
                    _write_attacher_row(
                        ws, row_pos, bs_row,
                        record['Connection ID'],  # For O/P (main list)
                        job_data, cell_format,
                        backspan_conn_id=backspan_conn_id,  # For Q (mid-span)
                        column_q_format=yellow_highlight_format,  # Yellow highlight for verification
                        yellow_highlight_format=yellow_highlight_format
                    )
                    row_pos += 1

            # Calculate From Pole/To Pole positions - they will overlap with the last two rows
            header_row = row_pos - 2
            value_row = row_pos - 1

            # Write lowest heights in the merged cells (all rows except last two)
            if header_row - 1 > group_start_row:
                # If we have multiple rows to merge
                ws.merge_range(group_start_row, 11, header_row - 1, 11, connection_data['lowest_com'], cell_format)  # Column L
                ws.merge_range(group_start_row, 12, header_row - 1, 12, connection_data['lowest_cps'], cell_format)  # Column M
            else:
                # If we only have one row, just write the values
                ws.write(group_start_row, 11, connection_data['lowest_com'], cell_format)
                ws.write(group_start_row, 12, connection_data['lowest_cps'], cell_format)

            # Write From Pole/To Pole headers and values (overlapping last two rows)
            ws.write(header_row, 11, "From Pole", sub_header_format)
            ws.write(header_row, 12, "To Pole", sub_header_format)
            ws.write(value_row, 11, connection_data['from_pole_value'], cell_format)
            ws.write(value_row, 12, connection_data['to_pole_value'], cell_format)

        # Set group_end_row before merges
        group_end_row = row_pos - 1

        # Merge columns A-K (0-10) for the group - MOVED TO END
        for col in range(11):
            col_name = columns[col] if col < len(columns) else str(col)
            value = record.get(columns[col], "")
            if group_start_row < group_end_row:
                ws.merge_range(group_start_row, col, group_end_row, col, value, cell_format)
            else:
                ws.write(group_start_row, col, value, cell_format)

        # Merge columns R, T, U, V (17, 19, 20, 21) for the group - MOVED TO END
        for col in [17, 19, 20, 21]:  # R, T, U, V columns only
            col_name = columns[col] if col < len(columns) else str(col)
            value = record.get(columns[col], "")
            if group_start_row < group_end_row:
                ws.merge_range(group_start_row, col, group_end_row, col, value, cell_format)
            else:
                ws.write(group_start_row, col, value, cell_format)

        # Get movement summaries
        all_movements = get_movement_summary(connection_data['main_attachers'])
        short_cps_movements = get_short_cps_movement_summary(connection_data['main_attachers'])
        cps_movements = get_movement_summary(connection_data['main_attachers'], cps_only=True)

        # Column S (18): Shortened CPS summary
        ws.merge_range(group_start_row, 18, group_end_row, 18, short_cps_movements, cell_format)

        # Column W (22): Full CPS + all movements, CPS first
        full_movement_text = cps_movements
        if all_movements:
            if cps_movements:
                full_movement_text += "\n"
            full_movement_text += all_movements
        
        ws.merge_range(group_start_row, 22, group_end_row, 22, full_movement_text, cell_format)

    writer.close()
    return output

def _write_excel_headers(ws: xlsxwriter.worksheet.Worksheet, columns: List[str], section_header_format: xlsxwriter.format.Format, sub_header_format: xlsxwriter.format.Format):
    """Write the Excel headers with proper formatting"""
    # === Top header: merge sections ===
    ws.merge_range(0, 11, 0, 12, "Existing Mid-Span Data", section_header_format)
    ws.merge_range(0, 13, 0, 16, "Make Ready Data", section_header_format)

    # === Row 2 headers ===
    ws.merge_range(1, 11, 2, 11, "Height Lowest Com", sub_header_format)
    ws.merge_range(1, 12, 2, 12, "Height Lowest CPS Electrical", sub_header_format)
    ws.merge_range(1, 13, 2, 13, "Attacher Description", sub_header_format)
    ws.merge_range(1, 14, 1, 15, "Attachment Height", sub_header_format)
    ws.write(2, 14, "Existing", sub_header_format)
    ws.write(2, 15, "Proposed", sub_header_format)
    ws.write(1, 16, "Mid-Span (same span as existing)", sub_header_format)
    ws.write(2, 16, "Proposed", sub_header_format)

    # === Extra header columns ===
    ws.merge_range(0, 17, 2, 17, "One Touch Transfer:\nMake Ready or Upgrade &\nSimple or Complex", section_header_format)
    ws.merge_range(0, 18, 2, 18, "Remedy Description and Explanation/\nAdditional Comments/Variance Requests", section_header_format)
    ws.merge_range(0, 19, 2, 19, "Responsible Party:\nAttacher or CPS", section_header_format)
    ws.merge_range(0, 20, 2, 20, "Existing CPSE Red Tag on Pole", section_header_format)
    ws.merge_range(0, 21, 2, 21, "Pole Data Missing in GIS\n(if yes fill out Missing Pole Data worksheet)", section_header_format)
    ws.merge_range(0, 22, 2, 22, "CPSE Application Comments", section_header_format)
        
    # === Fix: Add top-level headers for initial columns including Construction Grade ===
    for col_num, col_name in enumerate(columns[:11]):
        ws.merge_range(0, col_num, 2, col_num, col_name, section_header_format)
        
    # === Auto column width and center alignment ===
    for col_num, col_name in enumerate(columns):
        ws.set_column(col_num, col_num, max(len(col_name) + 2, 18), None)

def _write_attacher_row(ws: xlsxwriter.worksheet.Worksheet, row_pos: int, attacher: Dict[str, Any], connection_id: str, job_data: Dict[str, Any], cell_format: xlsxwriter.format.Format, backspan_conn_id: Optional[str]=None, column_q_format: Optional[xlsxwriter.format.Format]=None, main_attachers: Optional[List[Dict[str, Any]]]=None, yellow_highlight_format: Optional[xlsxwriter.format.Format]=None):
    """Write a row for an attacher including the proposed mid-span height
    
    Args:
        ws: Worksheet to write to
        row_pos: Row position to write at
        attacher: Attacher data dictionary
        connection_id: Current connection ID (for O/P columns and main section Q)
        job_data: Job data dictionary
        cell_format: Format to use for cells
        backspan_conn_id: Optional backspan connection ID (for backspan section Q)
        column_q_format: Optional format to use specifically for column Q (defaults to cell_format)
        main_attachers: List of main attachers for reference span lookups
        yellow_highlight_format: Format for highlighting cells that need user verification
    """
    # Use column_q_format if provided, otherwise use cell_format
    q_format = column_q_format if column_q_format is not None else cell_format
    
    # Check if this is a reference span row
    is_reference = attacher.get('is_reference', False)
    
    if is_reference:
        # For reference spans, implement new logic
        attacher_name = attacher['name']
        midspan_existing = attacher['existing_height']  # This goes to Column Q now
        midspan_proposed = attacher['proposed_height']  # This might be used for Column Q proposed
        
        # Look up corresponding main attacher(s) by name
        matching_attachers = []
        if main_attachers:
            matching_attachers = [a for a in main_attachers if a['name'] == attacher_name]
        
        # Determine Column O and P values based on matches
        if len(matching_attachers) == 1:
            # Single match - use the values
            main_existing = matching_attachers[0]['existing_height']
            main_proposed = matching_attachers[0]['proposed_height']
            col_o_format = cell_format
            col_p_format = cell_format
        elif len(matching_attachers) > 1:
            # Multiple matches - leave blank and highlight yellow
            main_existing = ""
            main_proposed = ""
            col_o_format = yellow_highlight_format if yellow_highlight_format else cell_format
            col_p_format = yellow_highlight_format if yellow_highlight_format else cell_format
        else:
            # No matches - leave blank and highlight yellow
            main_existing = ""
            main_proposed = ""
            col_o_format = yellow_highlight_format if yellow_highlight_format else cell_format
            col_p_format = yellow_highlight_format if yellow_highlight_format else cell_format
        
        # Write the reference span row with new logic
        ws.write(row_pos, 13, attacher_name, cell_format)  # Attacher name
        ws.write(row_pos, 14, main_existing, col_o_format)  # Column O - Main pole existing height
        ws.write(row_pos, 15, main_proposed, col_p_format)  # Column P - Main pole proposed height
        ws.write(row_pos, 16, midspan_existing, cell_format)  # Column Q - Midspan existing height
        return
    
    # Write the attacher name and heights from main list
    ws.write(row_pos, 13, attacher['name'], cell_format)
    ws.write(row_pos, 14, attacher['existing_height'], cell_format)  # Column O - Existing height
    ws.write(row_pos, 15, attacher['proposed_height'], cell_format)  # Column P - Proposed height
    
    # Determine if this is equipment or guying by name
    name_lower = attacher['name'].lower()
    is_equipment = '(equipment)' in name_lower or '(riser)' in name_lower
    is_guying = '(down guy)' in name_lower or '(guy)' in name_lower
    
    # For equipment and guying, column Q is always blank
    if is_equipment or is_guying:
        ws.write(row_pos, 16, "", q_format)
    # For backspan rows, column Q should always be blank
    elif backspan_conn_id is not None:
        ws.write(row_pos, 16, "", q_format)  # Use special format for backspan
    else:
        # For wires in main section only, calculate mid-span height
        midspan_height = get_midspan_proposed_heights(
            job_data, 
            connection_id,  # Use main connection_id for main section
            attacher['name']
        )
        ws.write(row_pos, 16, midspan_height, cell_format)
