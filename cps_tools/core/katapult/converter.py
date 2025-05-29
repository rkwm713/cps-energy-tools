"""Katapult to SPIDAcalc conversion utilities."""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any

# Re-use small helpers from our own utils module
from .utils import _ensure_dict, _FT_TO_M, extract_pole_details, insulator_specs, normalize_scid

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

    # --- Extract nodes / pole details -------------------------------------
    raw_nodes = kat_json.get("nodes") or kat_json.get("data", {}).get("nodes", {})
    nodes = _ensure_dict(raw_nodes, key_field="id", name="nodes")

    # Extract pole measurements & relationships ---------------------------------
    scid_map, pole_details = extract_pole_details(kat_json)

    # --- Build locations list ---------------------------------------------
    locations: list[dict[str, Any]] = []

    print("\n=== Converting nodes to SPIDA locations ===")
    for node_id, node in nodes.items():
        attrs = node.get("attributes", {}) or {}
        
        # Use the node_id as the primary identifier for consistency
        # This matches what extract_attachments will use
        scid = node_id
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
    
    # Initialize result - using node_id as SCID for consistency
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
        cable_type = trace_info.get("cable_type", "").lower()
        equipment_type = trace_info.get("equipment_type", "").lower()
        company = trace_info.get("company", "").lower()
        
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
        # Use node_id as SCID for consistency with convert_katapult_to_spidacalc
        scid = node_id
        result[scid] = []
        
        # Check if we have photos in the node
        node_photos = node.get("photos", {})
        if not node_photos:
            print(f"  Node {node_id}: No photos found")
            continue
            
        # Find main photo
        main_photo_id = None
        for photo_id, photo_ref in node_photos.items():
            if isinstance(photo_ref, dict) and photo_ref.get("association") == "main":
                main_photo_id = photo_id
                break
                
        if not main_photo_id:
            print(f"  Node {node_id}: No main photo found")
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
                if not phase:
                    cable_type = item.get("cable_type")
                    equipment_type = item.get("equipment_type")
                    if cable_type or equipment_type:
                        phase = cable_type or equipment_type
                
                # Determine if on crossarm
                on_crossarm = _is_on_crossarm(phase)
                
                result[scid].append({
                    'height': height_ft,
                    'phase': phase,
                    'onCrossarm': on_crossarm,
                })
                attachment_count += 1
                
        if attachment_count > 0:
            print(f"  Node {node_id}: Found {attachment_count} attachments from photofirst_data")
    
    # Summary of results
    total_atts = sum(len(atts) for atts in result.values())
    print(f"\n  Total attachments found: {total_atts}")
    for scid, atts in result.items():
        if atts:
            print(f"    SCID '{scid}': {len(atts)} attachments")
    
    return result
