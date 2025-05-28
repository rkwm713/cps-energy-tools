"""Katapult to SPIDAcalc conversion utilities."""

from __future__ import annotations

from datetime import datetime
import math
from typing import Any

# Re-use small helpers from our own utils module
from .utils import _ensure_dict, _FT_TO_M, extract_pole_details, insulator_specs

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

    for node_id, node in nodes.items():
        attrs = node.get("attributes", {}) or {}
        scid = (
            (attrs.get("scid", {}) or {}).get("value") if isinstance(attrs.get("scid"), dict) else attrs.get("scid")
        )
        scid = scid or attrs.get("SCID") or node.get("id") or node_id

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


def extract_attachments(nodes: dict[str, Any], connections: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return **SCID → list[attachment]** mapping extracted from raw Katapult dictionaries.

    Each attachment is a dict with keys:
    - height: float | None (measured height in feet)
    - phase: str | None (e.g. "Primary", "Neutral", "Comms")
    - onCrossarm: bool (True if attachment sits on a crossarm)
    """
    
    # Accept lists as well – normalise to dictionaries keyed by ID
    nodes = _ensure_dict(nodes, name="nodes")
    connections = _ensure_dict(connections, name="connections")
    
    # Build node-id → SCID look-up
    scid_for_node: dict[str, str] = {}
    for nid, node in nodes.items():
        scid = (
            node.get("attributes", {}).get("scid", {}).get("value")
            or node.get("attributes", {}).get("SCID")
            or node.get("id")
            or str(nid)
        )
        scid_for_node[str(nid)] = str(scid)
    
    # Initialize result
    result: dict[str, list[dict[str, Any]]] = {scid: [] for scid in scid_for_node.values()}
    
    def _safe_float(val: Any) -> float | None:
        try:
            return float(val) if val is not None and val != '' else None
        except (ValueError, TypeError):
            return None
    
    def _infer_phase(item: dict | None) -> str | None:
        """Best-effort guess of phase label from cable/description fields."""
        if not item:
            return None
        desc = (item.get('description') or item.get('cable_type') or '').lower()
        if 'primary' in desc:
            return 'Primary'
        if 'neutral' in desc:
            return 'Neutral'
        if 'secondary' in desc:
            return 'Secondary'
        if 'service' in desc:
            return 'Service'
        return None
    
    def _parse_attachment_blob(blob: dict) -> list[dict]:
        out: list[dict] = []
        
        # Common place 1: direct keys
        if {'height', 'phase', 'onCrossarm'} <= blob.keys():
            out.append({
                'height': _safe_float(blob.get('height')),
                'phase': blob.get('phase'),
                'onCrossarm': bool(blob.get('onCrossarm')),
            })
            return out
        
        # Common place 2: PhotoFirst wire list
        pf = blob.get('photofirst_data') or {}
        for cat in ('wire', 'equipment', 'guying'):
            for item in pf.get(cat, {}).values():
                h = _safe_float(item.get('_measured_height'))
                phase = item.get('phase') or item.get('_phase') or _infer_phase(item)
                on_arm = bool(item.get('on_crossarm') or item.get('onCrossarm'))
                out.append({'height': h, 'phase': phase, 'onCrossarm': on_arm})
        return out
    
    # Walk each connection and harvest attachments at both ends
    for conn in connections.values():
        for endpoint, tag in (("node_id_1", "end1"), ("node_id_2", "end2")):
            nid = conn.get(endpoint)
            if nid is None:
                continue
            scid = scid_for_node.get(str(nid))
            if scid is None:
                continue
            
            # Pattern A: attachment data stored directly on the connection
            direct_height = conn.get(f"{tag}_height") or conn.get(f"{endpoint}_height")
            if direct_height is not None:
                result[scid].append({
                    'height': _safe_float(direct_height),
                    'phase': conn.get(f"{tag}_phase") or conn.get(f"{endpoint}_phase"),
                    'onCrossarm': bool(conn.get(f"{tag}_onCrossarm") or conn.get(f"{endpoint}_onCrossarm")),
                })
            
            # Pattern B: iterate through sections looking for photo/wire data
            for sect in (conn.get('sections') or {}).values():
                result[scid].extend(_parse_attachment_blob(sect))
    
    # Also look inside each node for attachments
    for nid, node in nodes.items():
        scid = scid_for_node[str(nid)]
        result[scid].extend(_parse_attachment_blob(node))
    
    # Clean up: remove empty placeholders and deduplicate
    clean: dict[str, list[dict]] = {}
    for scid, lst in result.items():
        # Drop completely empty records
        filtered: list[dict] = []
        for att in lst:
            if att.get('height') is None and att.get('phase') is None and not att.get('onCrossarm'):
                continue
            filtered.append(att)
        
        # Simple de-dup by (height, phase, onCrossarm)
        seen: set[tuple] = set()
        dedup: list[dict] = []
        for att in filtered:
            key = (att.get('height'), att.get('phase'), att.get('onCrossarm'))
            if key in seen:
                continue
            seen.add(key)
            dedup.append(att)
        clean[scid] = dedup
    
    return clean
