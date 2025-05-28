import math
import json
import os
import re
import types # For the safe tkinter import patch, though it won't be used directly here

# === Constants for Attachment and Span Labels ===
EXISTING_ATTACHMENT_HEIGHT = "Attachment Height - Existing"
MR_MOVE = "MR Move"
EFFECTIVE_MOVE = "Effective Move"
PROPOSED_ATTACHMENT_HEIGHT = "Attachment Height - Proposed"

EXISTING_SPAN_HEIGHT = "Mid-Span Existing"
SPAN_MR_MOVE = "Span MR Move"
SPAN_EFFECTIVE_MOVE = "Span Effective Move"
SPAN_PROPOSED_HEIGHT = "Mid-Span Proposed"

ALLOWED_NODE_TYPES = {"pole", "Power", "Power Transformer", "Joint", "Joint Transformer"}

def format_height_feet_inches(height_float):
    if not isinstance(height_float, (int, float)) or height_float in (float('inf'), float('-inf')) or height_float is None:
        return ""
    total_inches = round(height_float)
    feet = total_inches // 12
    inches = total_inches % 12
    return f"{feet}'-{inches}\""

def get_attachers_from_node_trace(job_data, node_id):
    attachers = {}
    node_info = job_data.get("nodes", {}).get(node_id, {})
    photo_ids = node_info.get("photos", {})
    main_photo_id = next((pid for pid, pdata in photo_ids.items() if pdata.get("association") == "main"), None)
    if not main_photo_id:
        return {}
    photo_data = job_data.get("photos", {}).get(main_photo_id, {})
    photofirst_data = photo_data.get("photofirst_data", {})
    trace_data = job_data.get("traces", {}).get("trace_data", {})
    
    # First pass: collect all power wires to find the lowest one
    power_wires = {}
    for category in ["wire", "equipment", "guying"]:
        for item in photofirst_data.get(category, {}).values():
            trace_id = item.get("_trace")
            if not trace_id or trace_id not in trace_data:
                continue
            trace_entry = trace_data[trace_id]
            company = trace_entry.get("company", "").strip()
            type_label = trace_entry.get("cable_type", "") if category in ["wire", "guying"] else trace_entry.get("equipment_type", "")
            if not type_label:
                continue
            
            # Check if it's a power wire (CPS owned)
            if company.lower() == "cps energy" and type_label.lower() in ["primary", "neutral", "street light"]:
                measured = item.get("_measured_height")
                if measured is not None:
                    try:
                        measured = float(measured)
                        power_wires[type_label] = (measured, trace_id)
                    except:
                        continue
    
    # Find the lowest power wire
    lowest_power_wire = None
    lowest_height = float('inf')
    for wire_type, (height, trace_id) in power_wires.items():
        if height < lowest_height:
            lowest_height = height
            lowest_power_wire = (wire_type, trace_id)
    
    # Second pass: collect all non-power wires and only the lowest power wire
    for category in ["wire", "equipment", "guying"]:
        for item in photofirst_data.get(category, {}).values():
            trace_id = item.get("_trace")
            if not trace_id or trace_id not in trace_data:
                continue
            trace_entry = trace_data[trace_id]
            company = trace_entry.get("company", "").strip()
            type_label = trace_entry.get("cable_type", "") if category in ["wire", "guying"] else trace_entry.get("equipment_type", "")
            if not type_label:
                continue
            
            # Skip if it's a power wire that's not the lowest one
            if company.lower() == "cps energy" and type_label.lower() in ["primary", "neutral", "street light"]:
                if not lowest_power_wire or trace_id != lowest_power_wire[1]:
                    continue
            
            attacher_name = type_label if company.lower() == "cps energy" else f"{company} {type_label}"
            attachers[attacher_name] = trace_id
    return attachers

def get_heights_for_node_trace_attachers(job_data, node_id, attacher_trace_map):
    heights = {}
    photo_ids = job_data.get("nodes", {}).get(node_id, {}).get("photos", {})
    main_photo_id = next((pid for pid, pdata in photo_ids.items() if pdata.get("association") == "main"), None)
    if not main_photo_id:
        return heights
    photofirst_data = job_data.get("photos", {}).get(main_photo_id, {}).get("photofirst_data", {})
    all_sections = {**photofirst_data.get("wire", {}), **photofirst_data.get("equipment", {}), **photofirst_data.get("guying", {})}
    for attacher_name, trace_id in attacher_trace_map.items():
        for item in all_sections.values():
            if item.get("_trace") != trace_id:
                continue
            measured = item.get("_measured_height")
            mr_move = item.get("mr_move", 0)
            if measured is not None:
                try:
                    measured = float(measured)
                    mr_move = float(mr_move) if mr_move else 0.0
                    proposed = measured + mr_move
                    existing_fmt = format_height_feet_inches(measured)
                    proposed_fmt = "" if abs(proposed - measured) < 0.01 else format_height_feet_inches(proposed)
                    heights[attacher_name] = (existing_fmt, proposed_fmt)
                    break
                except Exception as e:
                    # self.info_text.insert(tk.END, f"Height parse error: {str(e)}\n") # Removed GUI dependency
                    pass # Log or handle error appropriately in a headless context
    return heights

def get_attachers_for_node(job_data, node_id):
    """Get all attachers for a node including guying and equipment, from neutral down"""
    main_attacher_data = []
    neutral_height = get_neutral_wire_height(job_data, node_id)
    node_photos = job_data.get("nodes", {}).get(node_id, {}).get("photos", {})
    main_photo_id = next((pid for pid, pdata in node_photos.items() if pdata.get("association") == "main"), None)
    debug_items = []  # For debugging output
    if main_photo_id:
        photo_data = job_data.get("photos", {}).get(main_photo_id, {})
        photofirst_data = photo_data.get("photofirst_data", {})
        trace_data = job_data.get("traces", {}).get("trace_data", {})
        for category in ["wire", "equipment", "guying"]:
            for item in photofirst_data.get(category, {}).values():
                trace_id = item.get("_trace")
                trace_info = trace_data.get(trace_id, {}) if trace_id else {}
                if category == "wire":
                    company = trace_info.get("company", "").strip()
                    type_label = trace_info.get("cable_type", "").strip()
                elif category == "equipment":
                    company = trace_info.get("company", "").strip() or ("CPS ENERGY" if item.get("equipment_type") in ["street_light", "riser"] else "")
                    type_label = trace_info.get("equipment_type", "").strip() or item.get("equipment_type", "").strip()
                elif category == "guying":
                    company = trace_info.get("company", "").strip() or ""
                    type_label = trace_info.get("cable_type", "").strip() or item.get("guying_type", "").strip()
                if not type_label:
                    continue
                if type_label.lower() == "primary":
                    continue
                measured_height = item.get("_measured_height")
                mr_move = item.get("mr_move")
                # Only include equipment/guying at or below neutral
                if category in ["equipment", "guying"] and measured_height is not None and neutral_height is not None:
                    try:
                        if float(measured_height) > neutral_height:
                            continue
                    except (ValueError, TypeError):
                        pass
                # --- Naming logic ---
                attacher_name = f"{company} {type_label}".strip()
                if category == "equipment" and type_label.lower() == "street_light":
                    measurement_of = item.get("measurement_of", "").replace("_", " ").strip()
                    if measurement_of:
                        attacher_name = f"{company} Street Light ({measurement_of})"
                    else:
                        attacher_name = f"{company} Street Light"
                elif category == "equipment" and type_label.lower() == "riser":
                    attacher_name = f"{company} Riser"
                elif category == "guying" and type_label.lower() == "down guy":
                    attacher_name = f"{company} Down Guy"
                elif category == "guying":
                    guying_type = item.get("guying_type", "").strip()
                    if guying_type:
                        attacher_name += f" ({guying_type})"
                    else:
                        attacher_name += " (Guy)"
                elif category == "equipment":
                    equipment_type = item.get("equipment_type", "").strip()
                    if equipment_type and equipment_type.lower() != "riser":
                        attacher_name += f" ({equipment_type})"
                    elif not equipment_type:
                        attacher_name += " (Equipment)"
                existing_height = format_height_feet_inches(measured_height)
                proposed_height = ""
                raw_height = None
                
                # Check if this is a proposed wire/guying by checking the trace_info
                is_proposed = trace_info.get("proposed", False)
                
                if measured_height is not None:
                    try:
                        measured_height = float(measured_height)
                        raw_height = measured_height
                        
                        # For proposed wires/guying, put measured_height in proposed column
                        if is_proposed:
                            existing_height = ""  # No existing height for proposed items
                            proposed_height = format_height_feet_inches(measured_height)
                        else:
                            # For existing wires/guying, put measured_height in existing column
                            existing_height = format_height_feet_inches(measured_height)
                            # Calculate proposed height if there's an mr_move
                            if mr_move is not None:
                                try:
                                    mr_move_val = float(mr_move)
                                    if abs(mr_move_val) > 0.01:
                                        proposed_height_value = measured_height + mr_move_val
                                        proposed_height = format_height_feet_inches(proposed_height_value)
                                except (ValueError, TypeError):
                                    proposed_height = ""
                    except (ValueError, TypeError):
                        existing_height = ""
                        proposed_height = ""
                        raw_height = 0
                
                main_attacher_data.append({
                    'name': attacher_name,
                    'existing_height': existing_height,
                    'proposed_height': proposed_height,
                    'raw_height': raw_height or 0,
                    'is_proposed': is_proposed  # Store the proposed flag for later use
                })
                debug_items.append({
                    'category': category,
                    'name': attacher_name,
                    'measured_height': raw_height,
                    'existing_height': existing_height
                })
    main_attacher_data.sort(key=lambda x: x['raw_height'], reverse=True)
    reference_spans = get_reference_attachers(job_data, node_id)
    backspan_data, backspan_bearing = get_backspan_attachers(job_data, node_id)
    return {
        'main_attachers': main_attacher_data,
        'reference_spans': reference_spans,
        'backspan': {
            'data': backspan_data,
            'bearing': backspan_bearing
        }
    }

def get_lowest_heights_for_connection(job_data, connection_id):
    lowest_com = float('inf')
    lowest_cps = float('inf')
    
    # Get the connection data
    connection_data = job_data.get("connections", {}).get(connection_id, {})
    if not connection_data:
        return "", ""
        
    # Get sections from the connection
    sections = connection_data.get("sections", {})
    if not sections:
        return "", ""
        
    # Get trace_data
    trace_data = job_data.get("traces", {}).get("trace_data", {})
    
    # Look through each section's photos
    for section_id, section_data in sections.items():
        photos = section_data.get("photos", {})
        main_photo_id = next((pid for pid, pdata in photos.items() if pdata.get("association") == "main"), None)
        if not main_photo_id:
            continue
            
        # Get photofirst_data
        photo_data = job_data.get("photos", {}).get(main_photo_id, {})
        photofirst_data = photo_data.get("photofirst_data", {})
        
        # Process wire data
        for wire in photofirst_data.get("wire", {}).values():
            trace_id = wire.get("_trace")
            if not trace_id or trace_id not in trace_data:
                continue
                
            trace_info = trace_data[trace_id]
            company = trace_info.get("company", "").strip()
            cable_type = trace_info.get("cable_type", "").strip()
            measured_height = wire.get("_measured_height")
            
            if measured_height is not None:
                try:
                    height = float(measured_height)
                    
                    # For CPS ENERGY electrical (Neutral or Street Light)
                    if company.lower() == "cps energy" and cable_type.lower() in ["neutral", "street light"]:
                        lowest_cps = min(lowest_cps, height)
                    # For communication attachments (non-CPS)
                    elif company.lower() != "cps energy":
                        lowest_com = min(lowest_com, height)
                except (ValueError, TypeError):
                    continue
    
    # Format the heights
    lowest_com_formatted = format_height_feet_inches(lowest_com)
    lowest_cps_formatted = format_height_feet_inches(lowest_cps)
    
    return lowest_com_formatted, lowest_cps_formatted

def get_backspan_attachers(job_data, current_node_id):
    """Find backspan attachers by finding a connection where current_node_id matches node_id_2"""
    backspan_data = []
    bearing = ""
    
    # Get neutral wire height
    neutral_height = get_neutral_wire_height(job_data, current_node_id)
    
    # Get trace_data
    trace_data = job_data.get("traces", {}).get("trace_data", {})
    
    # Find the connection where our current_node_id matches node_id_2
    backspan_connection = None
    for conn_id, conn_data in job_data.get("connections", {}).items():
        if conn_data.get("node_id_2") == current_node_id:
            backspan_connection = conn_data
            # Calculate bearing from coordinates
            sections = conn_data.get("sections", {})
            if sections:
                first_section = next(iter(sections.values()))
                if first_section:
                    lat = first_section.get("latitude")
                    lon = first_section.get("longitude")
                    if lat and lon:
                        # Get the from pole coordinates
                        from_node = job_data.get("nodes", {}).get(current_node_id, {})
                        from_photos = from_node.get("photos", {})
                        if from_photos:
                            main_photo_id = next((pid for pid, pdata in from_photos.items() if pdata.get("association") == "main"), None)
                            if main_photo_id:
                                photo_data = job_data.get("photos", {}).get(main_photo_id, {})
                                if photo_data and "latitude" in photo_data and "longitude" in photo_data:
                                    from_lat = photo_data["latitude"]
                                    from_lon = photo_data["longitude"]
                                    # Calculate bearing
                                    degrees, cardinal = calculate_bearing(from_lat, from_lon, lat, lon)
                                    bearing = f"{cardinal} ({int(degrees)}°)"
            break
    
    if not backspan_connection:
        return [], ""
        
    # Get the sections data from the backspan connection
    sections = backspan_connection.get("sections", {})
    
    # For each attacher, find the lowest measured height across all sections
    attacher_sections = {}
    for section_id, section_data in sections.items():
        photos = section_data.get("photos", {})
        main_photo_id = next((pid for pid, pdata in photos.items() if pdata.get("association") == "main"), None)
        if not main_photo_id:
            continue
        photo_data = job_data.get("photos", {}).get(main_photo_id, {})
        if not photo_data:
            continue
        photofirst_data = photo_data.get("photofirst_data", {})
        if not photofirst_data:
            continue
        # Wires
        for wire in photofirst_data.get("wire", {}).values():
            trace_id = wire.get("_trace")
            if not trace_id or trace_id not in trace_data:
                continue
            trace_info = trace_data[trace_id]
            company = trace_info.get("company", "").strip()
            cable_type = trace_info.get("cable_type", "").strip()
            if cable_type.lower() == "primary":
                continue
            measured_height = wire.get("_measured_height")
            mr_move = wire.get("mr_move", 0)
            effective_moves = wire.get("_effective_moves", {})
            if company and cable_type and measured_height is not None:
                try:
                    measured_height = float(measured_height)
                    attacher_name = f"{company} {cable_type}"
                    # If this attacher is not yet in the dict or this section has a lower height, update
                    if attacher_name not in attacher_sections or measured_height < attacher_sections[attacher_name]["measured_height"]:
                        attacher_sections[attacher_name] = {
                            "measured_height": measured_height,
                            "mr_move": mr_move,
                            "effective_moves": effective_moves
                        }
                except (ValueError, TypeError):
                    continue
        # Guying
        for guy in photofirst_data.get("guying", {}).values():
            trace_id = guy.get("_trace")
            if not trace_id or trace_id not in trace_data:
                continue
            trace_info = trace_data[trace_id]
            company = trace_info.get("company", "").strip()
            cable_type = trace_info.get("cable_type", "").strip()
            measured_height = guy.get("_measured_height")
            mr_move = guy.get("mr_move", 0)
            effective_moves = guy.get("_effective_moves", {})
            if company and cable_type and measured_height is not None and neutral_height is not None:
                try:
                    guy_height = float(measured_height)
                    if guy_height < neutral_height:
                        attacher_name = f"{company} {cable_type} (Down Guy)"
                        if attacher_name not in attacher_sections or guy_height < attacher_sections[attacher_name]["measured_height"]:
                            attacher_sections[attacher_name] = {
                                "measured_height": guy_height,
                                "mr_move": mr_move,
                                "effective_moves": effective_moves
                            }
                except (ValueError, TypeError):
                    continue
    # Now build the backspan_data list from the lowest section for each attacher
    for attacher_name, info in attacher_sections.items():
        measured_height = info["measured_height"]
        mr_move = info["mr_move"]
        effective_moves = info["effective_moves"]
        feet = int(measured_height) // 12
        inches = round(measured_height - (feet * 12))
        existing_height = format_height_feet_inches(measured_height)
        proposed_height = ""
        total_move = 0.0  # Initialize to 0.0 instead of using mr_move directly
        
        # Safely convert mr_move to float
        try:
            if mr_move and str(mr_move).strip():  # Check if mr_move is not empty
                total_move = float(mr_move)
        except (ValueError, TypeError):
            total_move = 0.0
            
        if effective_moves:
            for move in effective_moves.values():
                try:
                    if move and str(move).strip():  # Check if move is not empty
                        total_move += float(move)
                except (ValueError, TypeError):
                    continue
        if abs(total_move) > 0:
            proposed_height_value = measured_height + total_move
            feet_proposed = int(proposed_height_value) // 12
            inches_proposed = round(proposed_height_value - (feet_proposed * 12))
            proposed_height = format_height_feet_inches(proposed_height_value)
        backspan_data.append({
            'name': attacher_name,
            'existing_height': existing_height,
            'proposed_height': proposed_height,
            'raw_height': measured_height
        })
    backspan_data.sort(key=lambda x: x['raw_height'], reverse=True)
    return backspan_data, bearing

def get_reference_attachers(job_data, current_node_id):
    """Find reference span attachers by finding connections where current_node_id matches either node_id_1 or node_id_2"""
    reference_info = []  # List to store reference data with bearings
    
    # Get neutral wire height
    neutral_height = get_neutral_wire_height(job_data, current_node_id)
    
    # Find reference connections where our current_node_id matches either node
    for conn_id, conn_data in job_data.get("connections", {}).items():
        # Check if it's a reference connection
        connection_type = conn_data.get("attributes", {}).get("connection_type", {})
        if isinstance(connection_type, dict):
            connection_type_value = next(iter(connection_type.values()), "")
        else:
            connection_type_value = connection_type.get("button_added", "")
        
        if "reference" in str(connection_type_value).lower():
            # Check if current_node_id matches either node
            if (conn_data.get("node_id_1") == current_node_id or 
                conn_data.get("node_id_2") == current_node_id):
                # Calculate bearing
                bearing = ""
                sections = conn_data.get("sections", {})
                if sections:
                    # Find the midpoint section (if multiple sections exist)
                    section_ids = list(sections.keys())
                    mid_section_index = len(section_ids) // 2
                    mid_section_id = section_ids[mid_section_index]
                    mid_section = sections[mid_section_id]
                    
                    # Calculate bearing using midpoint section
                    lat = mid_section.get("latitude")
                    lon = mid_section.get("longitude")
                    if lat and lon:
                        # Get the current pole coordinates
                        from_node = job_data.get("nodes", {}).get(current_node_id, {})
                        from_photos = from_node.get("photos", {})
                        if from_photos:
                            main_photo_id = next((pid for pid, pdata in from_photos.items() if pdata.get("association") == "main"), None)
                            if main_photo_id:
                                photo_data = job_data.get("photos", {}).get(main_photo_id, {})
                                if photo_data and "latitude" in photo_data and "longitude" in photo_data:
                                    from_lat = photo_data["latitude"]
                                    from_lon = photo_data["longitude"]
                                    # Calculate bearing
                                    degrees, cardinal = calculate_bearing(from_lat, from_lon, lat, lon)
                                    bearing = f"{cardinal} ({int(degrees)}°)"
                    
                    # Get the main photo from the midpoint section
                    photos = mid_section.get("photos", {})
                    main_photo_id = next((pid for pid, pdata in photos.items() if pdata.get("association") == "main"), None)
                    if main_photo_id:
                        # Get photofirst_data from the main photo
                        photo_data = job_data.get("photos", {}).get(main_photo_id, {})
                        if not photo_data:
                            continue
                        
                        photofirst_data = photo_data.get("photofirst_data", {})
                        if not photofirst_data:
                            continue
                        
                        # Process the reference span data
                        span_data = []
                        
                        # Get trace_data
                        trace_data = job_data.get("traces", {}).get("trace_data", {})
                        
                        # Process wire data
                        wire_data = photofirst_data.get("wire", {})
                        if wire_data:
                            for wire in wire_data.values():
                                trace_id = wire.get("_trace")
                                if not trace_id or trace_id not in trace_data:
                                    continue
                                
                                trace_info = trace_data[trace_id]
                                company = trace_info.get("company", "").strip()
                                cable_type = trace_info.get("cable_type", "").strip()
                                
                                # Skip if cable_type is "Primary"
                                if cable_type.lower() == "primary":
                                    continue
                                
                                measured_height = wire.get("_measured_height")
                                mr_move = wire.get("mr_move", 0)
                                effective_moves = wire.get("_effective_moves", {})
                                
                                if company and cable_type and measured_height is not None:
                                    try:
                                        measured_height = float(measured_height)
                                        attacher_name = f"{company} {cable_type}"
                                        
                                        # Format existing height (measured_height)
                                        existing_height = format_height_feet_inches(measured_height)
                                        
                                        # Calculate proposed height using effective_moves and mr_move
                                        proposed_height = ""
                                        total_move = float(mr_move)  # Start with mr_move
                                        
                                        # Add effective moves
                                        if effective_moves:
                                            for move in effective_moves.values():
                                                try:
                                                    total_move += float(move)
                                                except (ValueError, TypeError):
                                                    continue
                                        
                                        # Calculate proposed height if there's a move
                                        if abs(total_move) > 0:
                                            proposed_height_value = measured_height + total_move
                                            proposed_height = format_height_feet_inches(proposed_height_value)
                                        
                                        span_data.append({
                                            'name': attacher_name,
                                            'existing_height': existing_height,
                                            'proposed_height': proposed_height,
                                            'raw_height': measured_height,
                                            'is_reference': True  # Mark this as a reference span
                                        })
                                    except (ValueError, TypeError):
                                        continue
                        
                        # Process guying data
                        guying_data = photofirst_data.get("guying", {})
                        if guying_data:
                            for guy in guying_data.values():
                                trace_id = guy.get("_trace")
                                if not trace_id or trace_id not in trace_data:
                                    continue
                                
                                trace_info = trace_data[trace_id]
                                company = trace_info.get("company", "").strip()
                                cable_type = trace_info.get("cable_type", "").strip()
                                
                                measured_height = guy.get("_measured_height")
                                mr_move = guy.get("mr_move", 0)
                                effective_moves = guy.get("_effective_moves", {})
                                
                                if company and cable_type and measured_height is not None and neutral_height is not None:
                                    try:
                                        guy_height = float(measured_height)
                                        if guy_height < neutral_height:
                                            attacher_name = f"{company} {cable_type} (Down Guy)"
                                            
                                            # Format existing height
                                            existing_height = format_height_feet_inches(guy_height)
                                            
                                            # Calculate proposed height using effective_moves and mr_move
                                            proposed_height = ""
                                            total_move = float(mr_move)  # Start with mr_move
                                            
                                            # Add effective moves
                                            if effective_moves:
                                                for move in effective_moves.values():
                                                    try:
                                                        total_move += float(move)
                                                    except (ValueError, TypeError):
                                                        continue
                                            
                                            # Calculate proposed height if there's a move
                                            if abs(total_move) > 0:
                                                proposed_height_value = guy_height + total_move
                                                proposed_height = format_height_feet_inches(proposed_height_value)
                                            
                                            span_data.append({
                                                'name': attacher_name,
                                                'existing_height': existing_height,
                                                'proposed_height': proposed_height,
                                                'raw_height': guy_height,
                                                'is_reference': True
                                            })
                                    except (ValueError, TypeError):
                                        continue
                        
                        if span_data:  # Only add reference info if we found attachers
                            # Sort by height from highest to lowest
                            span_data.sort(key=lambda x: x['raw_height'], reverse=True)
                            reference_info.append({
                                'bearing': bearing,
                                'data': span_data
                            })
    
    return reference_info

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate the bearing between two points
    Returns tuple of (degrees, cardinal_direction)"""
    
    # Convert to radians
    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))
    
    # Calculate bearing
    dLon = lon2 - lon1
    y = math.sin(dLon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dLon)
    bearing = math.degrees(math.atan2(y, x))
    
    # Convert to compass bearing (0-360)
    bearing = (bearing + 360) % 360
    
    # Convert to cardinal direction
    directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    index = round(bearing / 45) % 8
    cardinal = directions[index]
    
    return (bearing, cardinal)

def get_work_type(job_data, node_id):
    """Determine work type based on mr_move changes in non-CPS/Charter/Spectrum attachers"""
    
    # Get all attachers for this node
    node_photos = job_data.get("nodes", {}).get(node_id, {}).get("photos", {})
    main_photo_id = next((pid for pid, pdata in node_photos.items() if pdata.get("association") == "main"), None)
    
    if not main_photo_id:
        return "None"
        
    photo_data = job_data.get("photos", {}).get(main_photo_id, {})
    photofirst_data = photo_data.get("photofirst_data", {})
    trace_data = job_data.get("traces", {}).get("trace_data", {})
    
    # Check all wires, equipment, and guying
    for category in ["wire", "equipment", "guying"]:
        for item in photofirst_data.get(category, {}).values():
            trace_id = item.get("_trace")
            if not trace_id or trace_id not in trace_data:
                continue
                
            trace_info = trace_data[trace_id]
            company = trace_info.get("company", "").strip().lower()
            
            # Skip CPS Energy, Charter, and Spectrum companies
            if any(comp in company for comp in ["cps energy", "charter", "spectrum"]):
                continue
            
            # Check for mr_move changes
            mr_move = item.get("mr_move", 0)
            if mr_move:
                try:
                    move_value = float(mr_move)
                    if abs(move_value) > 0.01:  # Non-zero movement
                        return "Make Ready Simple"
                except (ValueError, TypeError):
                    continue
    
    return "None"

def get_responsible_party(job_data, node_id):
    """Always return Charter (2) - bypassing all data logic"""
    return "Charter (2)"

def compare_scids(scid1, scid2):
    """Compare two SCID numbers, prioritizing base numbers over suffixed ones"""
    # Convert to strings if they're numbers
    scid1 = str(scid1)
    scid2 = str(scid2)
    
    # Handle N/A values
    if scid1 == 'N/A':
        return 1  # N/A values go last
    if scid2 == 'N/A':
        return -1
    
    # Split on dots to separate base number from suffixes
    scid1_parts = scid1.split('.')
    scid2_parts = scid2.split('.')
    
    # Compare base numbers first
    try:
        # Remove leading zeros and convert to integers
        base1 = int(scid1_parts[0].lstrip('0') or '0')
        base2 = int(scid2_parts[0].lstrip('0') or '0')
        if base1 != base2:
            return base1 - base2
    except (ValueError, IndexError):
        # If base numbers can't be compared as integers, compare as strings
        if scid1_parts[0] != scid2_parts[0]:
            return -1 if scid1_parts[0] < scid2_parts[0] else 1
    
    # If base numbers are equal, the one without suffixes comes first
    if len(scid1_parts) == 1 and len(scid2_parts) > 1:
        return -1
    if len(scid1_parts) > 1 and len(scid2_parts) == 1:
        return 1
    
    # If both have suffixes, compare them
    return -1 if scid1 < scid2 else 1

def get_midspan_proposed_heights(job_data, connection_id, attacher_name):
    """Get the proposed height for a specific attacher in the connection's span
    Only returns a height if there is an effective_move or mr_move for that wire.
    
    Args:
        job_data: The job data dictionary
        connection_id: The connection ID to look at
        attacher_name: The name of the attacher to find heights for
        
    Returns:
        Formatted height string if there are moves, empty string otherwise
    """
    if not connection_id:
        return ""
        
    # Get the connection data
    connection_data = job_data.get("connections", {}).get(connection_id, {})
    if not connection_data:
        return ""
        
    # Get sections from the connection
    sections = connection_data.get("sections", {})
    if not sections:
        return ""
        
    # Get trace_data
    trace_data = job_data.get("traces", {}).get("trace_data", {})
    
    # Store the lowest height section for this attacher
    lowest_height = float('inf')
    lowest_section = None
    
    # First pass: find the section with the lowest measured height for this attacher
    for section_id, section_data in sections.items():
        photos = section_data.get("photos", {})
        main_photo_id = next((pid for pid, pdata in photos.items() if pdata.get("association") == "main"), None)
        if not main_photo_id:
            continue
            
        # Get photofirst_data
        photo_data = job_data.get("photos", {}).get(main_photo_id, {})
        photofirst_data = photo_data.get("photofirst_data", {})
        
        # Process wire data
        for wire in photofirst_data.get("wire", {}).values():
            trace_id = wire.get("_trace")
            if not trace_id or trace_id not in trace_data:
                continue
                
            trace_info = trace_data[trace_id]
            company = trace_info.get("company", "").strip()
            cable_type = trace_info.get("cable_type", "").strip()
            
            # Skip if cable_type is "Primary"
            if cable_type.lower() == "primary":
                continue
            
            # Construct the attacher name the same way as in the main list
            current_attacher = f"{company} {cable_type}"
            
            if current_attacher.strip() == attacher_name.strip():
                measured_height = wire.get("_measured_height")
                if measured_height is not None:
                    try:
                        measured_height = float(measured_height)
                        if measured_height < lowest_height:
                            lowest_height = measured_height
                            lowest_section = (section_data, wire, trace_info)
                    except (ValueError, TypeError):
                        continue
    
    if not lowest_section:
        return ""
        
    section_data, wire, trace_info = lowest_section
    
    # Check if this is a proposed wire
    is_proposed = trace_info.get("proposed", False)
    if is_proposed:
        return format_height_feet_inches(lowest_height)
    
    # Check for moves
    mr_move = wire.get("mr_move", 0)
    effective_moves = wire.get("_effective_moves", {})
    
    # Only consider nonzero moves
    has_mr_move = False
    try:
        has_mr_move = abs(float(mr_move)) > 0.01
    except (ValueError, TypeError):
        has_mr_move = False
        
    has_effective_move = any(abs(float(mv)) > 0.01 for mv in effective_moves.values() if _is_number(mv))
    
    if not has_mr_move and not has_effective_move:
        return ""
    
    # Calculate total move
    total_move = float(mr_move) if has_mr_move else 0.0
    if has_effective_move:
        for move in effective_moves.values():
            try:
                move_value = float(move)
                # Only add if nonzero
                if abs(move_value) > 0.01:
                    # Round up half of the move
                    half_move = -(-move_value // 2) if move_value > 0 else (move_value // 2)
                    total_move += half_move
            except (ValueError, TypeError):
                continue
    
    # Calculate proposed height
    proposed_height = lowest_height + total_move
    return format_height_feet_inches(proposed_height)

def get_movement_summary(attacher_data, cps_only=False):
    """Generate a movement summary for all attachers that have moves, proposed wires, and guying
    Args:
        attacher_data: List of attacher data
        cps_only: If True, only include CPS Energy movements
    """
    summaries = []
    
    # First handle movements of existing attachments
    for attacher in attacher_data:
        name = attacher['name']
        existing = attacher['existing_height']
        proposed = attacher['proposed_height']
        is_proposed = attacher.get('is_proposed', False)
        is_guy = '(Guy)' in name
        
        # Skip if cps_only is True and this is not a CPS attachment
        if cps_only and not name.lower().startswith("cps energy"):
            continue
        
        # Handle proposed new attachments (including guys)
        if is_proposed:
            if is_guy:
                summaries.append(f"Add {name} at {existing}")
            else:
                summaries.append(f"Install proposed {name} at {existing}")
            continue
            
        # Handle movements of existing attachments
        if proposed and existing:
            try:
                existing_parts = existing.replace('"', '').split("'")
                proposed_parts = proposed.replace('"', '').split("'")
                
                existing_inches = int(existing_parts[0]) * 12 + int(existing_parts[1])
                proposed_inches = int(proposed_parts[0]) * 12 + int(proposed_parts[1])
                
                # Calculate movement
                movement = proposed_inches - existing_inches
                
                if movement != 0:
                    # Determine if raising or lowering
                    action = "Raise" if movement > 0 else "Lower"
                    # Get absolute movement in inches
                    inches_moved = abs(movement)
                    
                    summary = f"{action} {name} {inches_moved}\" from {existing} to {proposed}"
                    summaries.append(summary)
            except (ValueError, IndexError):
                continue
    
    return "\n".join(summaries) if summaries else ""

def get_neutral_wire_height(job_data, node_id):
    """Find the height of the neutral wire for a given node"""
    lowest_height = float('inf')
    # Get the node's photos
    node_photos = job_data.get("nodes", {}).get(node_id, {}).get("photos", {})
    # Find the main photo
    main_photo_id = next((pid for pid, pdata in node_photos.items() if pdata.get("association") == "main"), None)
    
    if main_photo_id:
        # Get photofirst_data from the main photo
        photo_data = job_data.get("photos", {}).get(main_photo_id, {})
        photofirst_data = photo_data.get("photofirst_data", {})
        
        # Get trace_data
        trace_data = job_data.get("traces", {}).get("trace_data", {})
        
        # Look through wire section for neutral wire
        for wire in photofirst_data.get("wire", {}).values():
            trace_id = wire.get("_trace")
            if trace_id and trace_id in trace_data:
                trace_info = trace_data[trace_id]
                company = trace_info.get("company", "").strip()
                cable_type = trace_info.get("cable_type", "").strip()
                
                if company.lower() == "cps energy" and cable_type.lower() == "neutral":
                    measured_height = wire.get("_measured_height")
                    if measured_height is not None:
                        try:
                            measured_height = float(measured_height)
                            if measured_height < lowest_height:
                                lowest_height = measured_height
                        except (ValueError, TypeError):
                            pass
    if lowest_height != float('inf'):
        return lowest_height
    else:
        return None

def _is_number(value):
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

def find_backspan_connection_id(job_data, current_from_pole_id):
    """Find the backspan connection where the current FROM pole is the TO pole.
    
    Args:
        job_data: The job data dictionary
        current_from_pole_id: The node_id of the current FROM pole
        
    Returns:
        The connection_id of the backspan connection, or None if not found
    """
    for conn_id, conn_data in job_data.get('connections', {}).items():
        # Skip underground cables
        connection_type = conn_data.get('attributes', {}).get('connection_type', {}).get('button_added', "")
        if connection_type == "underground cable":
            continue
            
        # Check if current_from_pole_id matches the TO pole (node_id_2)
        if conn_data.get('node_id_2') == current_from_pole_id:
            return conn_id
            
    return None

def find_backspan_connection_id_by_scid(job_data, from_pole_id, node_properties):
    from_scid = node_properties.get(from_pole_id, {}).get('scid', 'N/A')
    for conn_id, conn_data in job_data.get('connections', {}).items():
        n1 = conn_data.get('node_id_1')
        n2 = conn_data.get('node_id_2')
        if not (n1 and n2):
            continue
        scid_1 = node_properties.get(n1, {}).get('scid', 'N/A')
        scid_2 = node_properties.get(n2, {}).get('scid', 'N/A')
        # Use the same logic as main list to determine from/to
        if compare_scids(scid_1, scid_2) <= 0:
            from_id = n1
            to_id = n2
        else:
            from_id = n2
            to_id = n1
        if to_id == from_pole_id:
            return conn_id
    return None

def get_short_cps_movement_summary(attacher_data):
    """Generate a short summary for CPS movements"""
    lines = []
    for attacher in attacher_data:
        name = attacher['name']
        existing = attacher['existing_height']
        proposed = attacher['proposed_height']
        if name.lower().startswith("cps energy"):
            if proposed and existing:
                try:
                    existing_parts = existing.replace('"', '').split("'")
                    proposed_parts = proposed.replace('"', '').split("'")
                    existing_inches = int(existing_parts[0]) * 12 + int(existing_parts[1])
                    proposed_inches = int(proposed_parts[0]) * 12 + int(proposed_parts[1])
                    movement = proposed_inches - existing_inches
                    if movement != 0:
                        action = "Raise" if movement > 0 else "Lower"
                        # Remove "CPS ENERGY" from the name for output
                        clean_name = name.replace("CPS ENERGY", "").strip()
                        lines.append(f"{action} {clean_name}")
                except (ValueError, IndexError):
                    continue
    return "\n".join(lines) if lines else ""

def has_proposed_wires(job_data, node_id):
    """Check if a node has any proposed wires/attachments"""
    # Get all attachers for this node
    attacher_data = get_attachers_for_node(job_data, node_id)
    main_attachers = attacher_data['main_attachers']
    
    # Check if any attacher is proposed
    for attacher in main_attachers:
        if attacher.get('is_proposed', False):
            return True
    
    return False

def get_attachment_action(job_data, node_id):
    """Determine attachment action based on whether there are proposed wires"""
    if has_proposed_wires(job_data, node_id):
        return "( I )nstalling"
    else:
        return "( E )xisting"

def get_pole_structure(job_data, node_id):
    # Get the node's attributes
    node_attributes = job_data.get("nodes", {}).get(node_id, {}).get("attributes", {})
    
    # First try to get proposed_pole_spec
    proposed_spec = None
    proposed_spec_data = node_attributes.get("proposed_pole_spec", {})
    if proposed_spec_data:
        # Get the first non-empty value from the dynamic keys
        for key, value in proposed_spec_data.items():
            if isinstance(value, dict):
                proposed_spec = value.get("value")  # If it's in a value field
            else:
                proposed_spec = value  # If it's direct
            if proposed_spec and proposed_spec != "N/A":
                break
    
    if proposed_spec:
        return proposed_spec
    
    # Fall back to pole_height and pole_class
    # Get pole_height from dynamic key
    pole_height = None
    pole_height_data = node_attributes.get("pole_height", {})
    if pole_height_data:
        if "one" in pole_height_data:
            pole_height = pole_height_data.get("one")
        else:
            # Try first non-empty value from dynamic keys
            for key, value in pole_height_data.items():
                if value and value != "N/A":
                    pole_height = value
                    break
    
    # Get pole_class from dynamic key
    pole_class = None
    pole_class_data = node_attributes.get("pole_class", {})
    if pole_class_data:
        if "one" in pole_class_data:
            pole_class = pole_class_data.get("one")
        else:
            # Try first non-empty value from dynamic keys
            for key, value in pole_class_data.items():
                if value and value != "N/A":
                    pole_class = value
                    break
    
    if pole_height and pole_class:
        return f"{pole_height}-{pole_class}"
    
    return "N/A"
