"""Katapult to SPIDAcalc conversion utilities."""

from __future__ import annotations

from datetime import datetime
import copy
import math
from typing import Any

# Re-use small helpers from our own utils module
from .utils import (_ensure_dict, _FT_TO_M, extract_pole_details, insulator_specs, 
                   normalize_scid, select_insulator, get_wire_properties)

__all__ = [
    "convert_katapult_to_spidacalc",
    "extract_attachments",
    "insulator_specs",
]


def convert_katapult_to_spidacalc(kat_json: dict[str, Any], job_id: str, job_name: str):
    """Convert Katapult-Pro JSON into a SPIDAcalc v11 *native project* JSON.

    Parameters
    ----------
    kat_json:
        Raw Katapult export (already parsed into a Python dictionary).
    job_id:
        Identifier injected into the exported project – appears as the main
        *label* inside SPIDAcalc.
    job_name:
        Human-readable job label.  Currently unused but kept to preserve the
        original function signature (future versions will embed it in the
        JSON as well).
    """
    
    # Wire and insulator data comes from engineering_templates.json
    
    # --- Extract nodes / pole details -------------------------------------
    raw_nodes = kat_json.get("nodes") or kat_json.get("data", {}).get("nodes", {})
    nodes = _ensure_dict(raw_nodes, key_field="id", name="nodes")

    # Extract attachments first so we can use that information for node filtering
    attachments_map = extract_attachments(kat_json)
    
    # Keep only nodes that either have attachments or have a SCID attribute
    filtered_nodes = {
        nid: node
        for nid, node in nodes.items()
        if nid in attachments_map or (node.get("attributes") or {}).get("scid")
    }
    
    # Log the filtering results
    print(f"  Found {len(nodes)} total nodes, retaining {len(filtered_nodes)} for export")
    for nid in set(nodes.keys()) - set(filtered_nodes.keys()):
        print(f"  Dropping node {nid} - no attachments and no SCID")
        
    nodes = filtered_nodes

    # Extract pole measurements & relationships ---------------------------------
    scid_map, pole_details = extract_pole_details(kat_json)
    # attachments_map already extracted above
    
    # Process connections to find spans between poles
    connections = _ensure_dict(
        kat_json.get("connections") or kat_json.get("data", {}).get("connections", {}),
        name="connections"
    )
    
    # Build a map of node_id to connected node_ids and connection types
    connection_map = {}
    for conn_id, conn in connections.items():
        # Get connection type - look in different possible locations
        attrs = conn.get("attributes", {}) or {}
        conn_type = None
        if isinstance(attrs.get("connection_type"), dict):
            conn_type = attrs.get("connection_type", {}).get("value") or ""
        else:
            conn_type = attrs.get("connection_type") or ""
            
        # We're interested in spans (wires between poles)
        conn_type_lower = conn_type.lower()
        if any(span_type in conn_type_lower for span_type in ["span", "wire"]):
            node1 = conn.get("node_id_1")
            node2 = conn.get("node_id_2")
            if node1 and node2:
                connection_map.setdefault(node1, []).append((node2, conn_id))
                connection_map.setdefault(node2, []).append((node1, conn_id))
    
    print(f"\n=== Found {len(connection_map)} nodes with connections ===")

    # --- Build locations list ---------------------------------------------
    locations: list[dict[str, Any]] = []

    print("\n=== Converting nodes to SPIDA locations ===")
    for node_id, node in nodes.items():
        attrs = node.get("attributes", {}) or {}
        
        # Normalize SCID identically everywhere
        scid = normalize_scid((node.get("attributes", {}) or {}).get("scid")) or node_id
        print(f"  Node {node_id} -> using node ID as SCID '{scid}'")

        pole_no = (
            (attrs.get("PoleNumber", {}) or {}).get("value")
            or attrs.get("PoleNumber")
            or scid
        )

        # Latitude / longitude ------------------------------------------------
        lat = node.get("latitude") or node.get("lat")
        lon = node.get("longitude") or node.get("lon")
        if (lat is None or lon is None) and "geometry" in node:
            coords = node["geometry"].get("coordinates", [])
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]

        if not scid:
            continue  # Skip nodes without any identifier

        det = pole_details.get(node_id, {})
        pole_height = det.get("poleHeight", 40.0 * _FT_TO_M)
        glc = det.get("groundLineClearance", 15.0 * _FT_TO_M)

        location: dict[str, Any] = {
            "label": str(scid),
            "poleId": str(scid),
            "designs": [
                {
                    "label": "Default Design",
                    "layerType": "Measured",
                    "structure": {
                        "pole": {
                            "id": str(scid),
                            "agl": {"unit": "METRE", "value": pole_height},
                            "glc": {"unit": "METRE", "value": glc},
                            "anchors": [
                                {
                                    "id": a["anchorId"],
                                    "height": {"unit": "METRE", "value": a["height"]},
                                }
                                for a in det.get("anchors", [])
                            ],
                            "guys": [
                                {
                                    "id": g["guyId"],
                                    "height": {"unit": "METRE", "value": g["height"]},
                                    "type": g["type"],
                                }
                                for g in det.get("guys", [])
                            ],
                            "referencePoles": [{"id": ref_sid} for ref_sid in det.get("referencePoles", [])],
                        },
                        "wireEndPoints": [],
                        "wires": [],
                    },
                }
            ],
        }

        if lat is not None and lon is not None:
            location["mapLocation"] = {"coordinates": [float(lon), float(lat)]}

        struct = location["designs"][0]["structure"]

        # Process attachments for this pole
        for att in attachments_map.get(scid, []):
            # Convert feet → metres
            m = att["height"] * _FT_TO_M

            # Build a "wire" entry
            # Ensure phase is always a string, never None
            phase = att.get("phase") or "Unknown"
            phase_upper = phase.upper()
            wire_id = f"{scid}-{phase}-{round(m,3)}"
            
            # Get wire properties from engineering templates
            wire_props = get_wire_properties(phase)
            
            wire = {
                "id": wire_id,
                "usageGroups": [phase_upper],
                "size": wire_props.get("size"),
                "calculation": "STATIC",
                "strength": {"unit": "NEWTON", "value": wire_props.get("strength", 10000)},
                "weight": {"unit": "NEWTON_PER_METRE", "value": wire_props.get("weight", 2.0)},
                "diameter": {"unit": "METRE", "value": wire_props.get("diameter", 0.01)},
                "description": phase,
                "endpoints": []
            }
            struct["wires"].append(wire)

            # Create endpoint on this pole
            struct["wireEndPoints"].append({
                "wireId": wire_id,
                "poleId": scid,
                "height": {"unit": "METRE", "value": m}
            })
            
            # Check if this pole has connections to other poles
            # For PRIMARY, NEUTRAL, and similar, create two-ended spans
            # Skip for service drops, equipment, etc.
            if phase_upper in ["PRIMARY", "NEUTRAL", "SECONDARY"] and node_id in connection_map:
                for connected_node, conn_id in connection_map.get(node_id, []):
                    connected_scid = scid_map.get(connected_node)
                    if connected_scid:
                        # Create a second endpoint on the connected pole at same height
                        # Add a small suffix to wire_id to make it unique for this span
                        span_wire_id = f"{wire_id}-span-{conn_id[-6:]}"
                        
                        # Create a new wire entry for this span
                        # Create a new wire entry for this span with same properties
                        span_wire = {
                            "id": span_wire_id,
                            "usageGroups": [phase_upper],
                            "size": wire_props.get("size"),
                            "calculation": "STATIC",
                            "strength": {"unit": "NEWTON", "value": wire_props.get("strength", 10000)},
                            "weight": {"unit": "NEWTON_PER_METRE", "value": wire_props.get("weight", 2.0)},
                            "diameter": {"unit": "METRE", "value": wire_props.get("diameter", 0.01)},
                            "description": f"{phase} Span",
                            "endpoints": []
                        }
                        struct["wires"].append(span_wire)
                        
                        # Add the two endpoints for this span
                        struct["wireEndPoints"].append({
                            "wireId": span_wire_id,
                            "poleId": scid,
                            "height": {"unit": "METRE", "value": m}
                        })
                        
                        struct["wireEndPoints"].append({
                            "wireId": span_wire_id,
                            "poleId": connected_scid,
                            "height": {"unit": "METRE", "value": m}  # Same height on connected pole
                        })
            
        # Add insulators based on attachments
        attachments = attachments_map.get(scid, [])
        insulators_added = set()  # Keep track of which insulator types we've already added
        
        for att in attachments:
            # Determine insulator type based on attachment
            insulator_type = None
            phase = att.get("phase") or ""
            phase_lower = phase.lower()
            
            if att.get("onCrossarm", False):
                insulator_type = "CROSSARM"
            elif "neutral" in phase_lower:
                insulator_type = "DEADEND" if "NEUTRAL" not in insulators_added else None
            elif "primary" in phase_lower:
                insulator_type = "POLE_TOP" if "PRIMARY" not in insulators_added else None
            elif "comm" in phase_lower:
                insulator_type = "DEADEND" if "COMM" not in insulators_added else None
            
            # Add the insulator if we found a type and haven't added it yet
            if insulator_type and insulator_type not in insulators_added:
                insulator = select_insulator(insulator_type, phase)
                if insulator:
                    location["designs"][0]["structure"]["pole"].setdefault("insulators", []).append(insulator)
                    insulators_added.add(insulator_type)
        
        # Create a "Recommended" design as a copy of the "Measured" design
        measured_design = location["designs"][0]
        recommended_design = copy.deepcopy(measured_design)
        recommended_design["label"] = "Recommended Design"
        recommended_design["layerType"] = "Recommended"
        
        # Since we don't have actual MR-move data, we'll just add a small increase to wire heights
        # to demonstrate the feature - in a real implementation, this would use actual MR data
        MR_HEIGHT_DELTA = 0.3  # 30 cm increase for demonstration
        for endpoint in recommended_design["structure"]["wireEndPoints"]:
            # Only adjust heights for attachments that would typically be moved
            wire_id = endpoint["wireId"]
            if any(phase in wire_id.upper() for phase in ["PRIMARY", "NEUTRAL", "SECONDARY"]):
                endpoint["height"]["value"] += MR_HEIGHT_DELTA
        
        # Add the recommended design
        location["designs"].append(recommended_design)

        locations.append(location)

    print(f"  Created {len(locations)} locations")

    spida_project = {
        "label": job_id,
        "dateModified": int(datetime.now().timestamp() * 1000),
        "clientFile": "TechServ_Light C_Static_Tension.client",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "schema": "/schema/spidacalc/calc/project.schema",
        "version": 11,
        "engineer": "Taylor Larsen",
        "leads": [
            {
                "label": "Lead",
                "locations": locations,
            }
        ],
    }

    return spida_project


def extract_attachments(kata_json: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return **SCID → list[attachment]** mapping extracted from raw Katapult JSON.

    Each attachment is a dict with keys:
    - height: float | None (measured height in feet)
    - phase: str | None (e.g. "Primary", "Neutral", "Comms")
    - onCrossarm: bool (True if attachment sits on a crossarm)
    """
    
    print("\n=== Extracting attachments ===")
    
    # Accept both direct args and full kata_json for backward compatibility
    if isinstance(kata_json, dict) and "nodes" not in kata_json and len(kata_json) == 2:
        # Old signature: extract_attachments(nodes, connections)
        nodes = kata_json
        connections = {}  # Ignored for new extraction method
        kata_json = {"nodes": nodes}  # Create minimal structure
    
    # Extract nodes and photos from the full structure
    nodes = _ensure_dict(
        kata_json.get("nodes") or kata_json.get("data", {}).get("nodes", {}),
        name="nodes"
    )
    photos = kata_json.get("photos", {})
    traces = kata_json.get("traces", {})
    trace_data = traces.get("trace_data", {}) if traces else {}
    
    # Initialize result - using normalized SCID as key for consistency
    result: dict[str, list[dict[str, Any]]] = {}
    
    def _safe_float(val: Any) -> float | None:
        try:
            return float(val) if val is not None and val != '' else None
        except (ValueError, TypeError):
            return None
    
    def _infer_phase_from_trace(trace_id: str | None) -> str | None:
        """Infer phase from trace data."""
        if not trace_id or not trace_data:
            return None
        
        trace_info = trace_data.get(trace_id, {})
        cable_type = (trace_info.get("cable_type") or "").lower()
        equipment_type = (trace_info.get("equipment_type") or "").lower()
        company = (trace_info.get("company") or "").lower()
        
        # Check cable type
        if 'primary' in cable_type:
            return 'Primary'
        if 'neutral' in cable_type:
            return 'Neutral'
        if 'secondary' in cable_type:
            return 'Secondary'
        if 'service' in cable_type:
            return 'Service'
        if 'street' in cable_type and 'light' in cable_type:
            return 'Street Light'
        
        # Check equipment type
        if equipment_type:
            if 'street' in equipment_type and 'light' in equipment_type:
                return 'Street Light'
            if 'transformer' in equipment_type:
                return 'Equipment'
        
        # Check company
        if 'comm' in company or 'fiber' in company or 'catv' in company or 'att' in company:
            return 'Comms'
            
        # Return original cable_type if can't infer
        return trace_info.get("cable_type") or trace_info.get("equipment_type")
    
    def _is_on_crossarm(phase: str | None) -> bool:
        """Determine if attachment should be on crossarm based on phase."""
        if not phase:
            return False
        phase_lower = phase.lower()
        return any(x in phase_lower for x in ['primary', 'neutral', 'street light'])
    
    # For each node, find attachments in photofirst_data
    for node_id, node in nodes.items():
        # Normalize SCID early for consistency with converter
        raw_scid = (node.get("attributes") or {}).get("scid")
        scid = normalize_scid(raw_scid) or node_id
        result[scid] = []
        
        # Check if we have photos in the node
        node_photos = node.get("photos", {})
        if not node_photos:
            print(f"  Node {node_id}: No photos found")
            continue
            
        # Find "main" photo (Katapult marks it with association=True or association_type="auto")
        main_photo_id = None
        for photo_id, photo_ref in node_photos.items():
            if not isinstance(photo_ref, dict):
                continue
            assoc = photo_ref.get("association")
            assoc_type = photo_ref.get("association_type")
            # Accept multiple variants – boolean True, the string "main", or "auto" (Katapult auto-selection)
            if (
                assoc is True
                or (isinstance(assoc, str) and assoc.lower() == "main")
                or (isinstance(assoc_type, str) and assoc_type.lower() in ("main", "auto"))
            ):
                main_photo_id = photo_id
                break
        
        # Fallback: if no explicit main, just pick the first available photo
        if not main_photo_id:
            main_photo_id = next(iter(node_photos.keys()), None)
            if main_photo_id:
                print(f"  Node {node_id}: Using first photo {main_photo_id} as fallback main")
            else:
                print(f"  Node {node_id}: No photos available after fallback")
                continue
            
        # Get the actual photo data
        if main_photo_id not in photos:
            print(f"  Node {node_id}: Main photo {main_photo_id} not found in photos")
            continue
            
        photo_data = photos[main_photo_id]
        photofirst_data = photo_data.get("photofirst_data", {})
        
        if not photofirst_data:
            print(f"  Node {node_id}: No photofirst_data found")
            continue
            
        # Extract attachments from photofirst_data
        attachment_count = 0
        for category in ["wire", "equipment", "guying"]:
            category_data = photofirst_data.get(category, {})
            for item_id, item in category_data.items():
                height_ft = _safe_float(item.get("_measured_height"))
                if height_ft is None:
                    continue
                
                # Get trace ID to look up phase info
                trace_id = item.get("_trace")
                phase = _infer_phase_from_trace(trace_id)
                
                # If no phase from trace, try direct fields
                # Ensure we have a string value for phase, not None
                if not phase:
                    cable_type = item.get("cable_type")
                    equipment_type = item.get("equipment_type")
                    if cable_type or equipment_type:
                        phase = cable_type or equipment_type
                    else:
                        phase = ""  # Ensure phase is never None
                
                # Determine if on crossarm
                on_crossarm = _is_on_crossarm(phase)
                
                result[scid].append({
                    'height': height_ft,
                    'phase': phase,
                    'onCrossarm': on_crossarm,
                })
                attachment_count += 1
                
        if attachment_count > 0:
            print(f"  Node {node_id} (SCID {scid}): Found {attachment_count} attachments from photofirst_data")
    
    # Summary of results
    total_atts = sum(len(atts) for atts in result.values())
    print(f"\n  Total attachments found: {total_atts}")
    for scid, atts in result.items():
        if atts:
            print(f"    SCID '{scid}': {len(atts)} attachments")
    
    return result
