"""
Katapult → SPIDAcalc v11 conversion helpers.

This module replaces the previous monolithic implementation with a
stream-lined version that focuses on the core translation rules required
by CPS-Energy.  The public interface remains **unchanged** so existing
call-sites keep working:

    >>> from cps_tools.core.katapult.converter import (
    ...     convert_katapult_to_spidacalc,
    ...     extract_attachments,
    ...     insulator_specs,
    ... )

The heavy-lifting utilities live in ``cps_tools.core.katapult.utils`` –
this wrapper merely orchestrates them.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List

from .utils import (
    _ensure_dict,
    _FT_TO_M,
    extract_pole_details,
    normalize_scid,
    select_insulator,
    get_wire_properties,
    insulator_specs,  # re-exported for convenience
)

__all__ = [
    "convert_katapult_to_spidacalc",
    "extract_attachments",
    "insulator_specs",
]

# ---------------------------------------------------------------------------
# Behavioural constants
# ---------------------------------------------------------------------------

# Katapult node *type* values that represent real poles / structures we want
# to preserve in the exported project.  The comparison is case-insensitive.
ALLOWED_NODE_TYPES: set[str] = {
    "pole",
    "power",
    "power transformer",
    "joint",
    "joint transformer",
}

# Vertical offset applied to every attachment in the *Recommended* design so
# SPIDAcalc can differentiate it from the *Measured* layer.
MR_HEIGHT_DELTA_M: float = 0.10  # 10 cm

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def is_main_scid(scid: str | None) -> bool:
    """Return ``True`` when *scid* is purely numeric – e.g. ``"002"``.

    Katapult encodes reference poles by appending a letter (``"002.A"``).
    We only treat the numeric root as the *main* pole.
    """

    return bool(re.fullmatch(r"\d+", scid or ""))


def extract_attachments(kat_json: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Harvest wire attachment meta-data from a full Katapult export.

    The routine returns a mapping **SCID → List[attachment]** where each
    *attachment* is a::

        {
            "height_ft": float,   # original height in feet – may be *None*
            "height_m":  float,   # height converted to metres – may be *None*
            "phase": str,         # Primary / Neutral / Comms / …
            "on_crossarm": bool,  # True when attachment sits on a cross-arm
        }
    """

    attachments: Dict[str, List[Dict[str, Any]]] = {}

    # Katapult can serialise ``nodes`` either as a *list* or a *mapping*.
    # Use the existing ``_ensure_dict`` helper so we always iterate over a
    # dictionary of nodes keyed by their ``id``.
    raw_nodes = kat_json.get("nodes") or kat_json.get("data", {}).get("nodes", {})
    nodes_dict = _ensure_dict(raw_nodes, key_field="id", name="nodes")

    for node in nodes_dict.values():
        attrs = node.get("attributes", {}) or {}
        raw_scid = attrs.get("scid")
        scid = normalize_scid(raw_scid)
        if not scid:
            continue  # skip nodes without an SCID entirely

        raw_traces = node.get("traces", []) or []
        if isinstance(raw_traces, list):
            traces_iter = raw_traces
        else:
            traces_iter = _ensure_dict(raw_traces, key_field="id", name="traces").values()

        for trace in traces_iter:
            h_ft = trace.get("height")
            if h_ft is None:
                continue

            h_m = h_ft * _FT_TO_M
            phase = trace.get("phase") or "UNKNOWN"
            on_crossarm = bool(trace.get("onCrossarm", False))

            attachments.setdefault(scid, []).append(
                {
                    "height_ft": h_ft,
                    "height_m": h_m,
                    "phase": phase,
                    "on_crossarm": on_crossarm,
                }
            )

    return attachments

# ---------------------------------------------------------------------------
# Main public routine
# ---------------------------------------------------------------------------

def convert_katapult_to_spidacalc(
    kat_json: Dict[str, Any],
    job_id: str,
    job_name: str,
) -> Dict[str, Any]:
    """Convert Katapult-Pro JSON to a SPIDAcalc *native* project (v11).

    The function purposefully keeps the *output structure* identical to the
    previous implementation so downstream code – notably the FastAPI router –
    remains unaffected.
    """

    # 1) Pre-compute helpers -------------------------------------------------

    attachments_map = extract_attachments(kat_json)
    scid_map, pole_details = extract_pole_details(kat_json)

    nodes_raw = _ensure_dict(
        kat_json.get("nodes") or kat_json.get("data", {}).get("nodes", {}),
        key_field="id",
        name="nodes",
    )

    # 2) Filter nodes – keep main poles or any that carry attachments --------
    filtered_nodes: List[Dict[str, Any]] = []
    for node in nodes_raw.values():
        node_type = (node.get("type") or "").lower()
        if node_type and node_type not in ALLOWED_NODE_TYPES:
            continue

        scid = scid_map.get(node.get("id"))
        if not scid:
            continue

        if is_main_scid(scid) or attachments_map.get(scid):
            filtered_nodes.append(node)

    # 3) Build *locations* list ---------------------------------------------
    locations: List[Dict[str, Any]] = []

    for node in filtered_nodes:
        node_id = node["id"]
        scid = scid_map[node_id]
        atts = attachments_map.get(scid, [])
        det = pole_details.get(node_id, {})

        # ------------------------------------------------------------------
        # Core pole fields
        # ------------------------------------------------------------------
        pole_height_m = det.get("poleHeight")
        glc_m = det.get("groundLineClearance")

        pole_dict: Dict[str, Any] = {
            "id": scid,
            "agl": {"unit": "METRE", "value": pole_height_m},
            "glc": {"unit": "METRE", "value": glc_m},
            "anchors": det.get("anchors", []),
            "guys": det.get("guys", []),
            "referencePoles": [
                {"id": ref} for ref in det.get("referencePoles", [])
            ],
        }

        # ------------------------------------------------------------------
        # Measured design ---------------------------------------------------
        # ------------------------------------------------------------------
        measured_structure: Dict[str, Any] = {
            "pole": pole_dict,
            "wireEndPoints": [],
            "wires": [],
            "insulators": [],
        }

        for idx, att in enumerate(atts):
            h_m = att["height_m"]
            phase = att["phase"].upper() if att["phase"] else "UNKNOWN"
            wire_props = get_wire_properties(phase)
            wire_id = f"{scid}-{phase}-{idx}"

            measured_structure["wires"].append(
                {
                    "id": wire_id,
                    "usageGroups": [phase],
                    "size": wire_props.get("size"),
                    "calculation": "STATIC",
                    "strength": {
                        "unit": "NEWTON",
                        "value": wire_props.get("strength", 10000),
                    },
                    "weight": {
                        "unit": "NEWTON_PER_METRE",
                        "value": wire_props.get("weight", 2.0),
                    },
                    "diameter": {
                        "unit": "METRE",
                        "value": wire_props.get("diameter", 0.01),
                    },
                    "description": phase,
                    "endpoints": [
                        {"scid": scid, "height_m": h_m},
                    ],
                }
            )

            measured_structure["wireEndPoints"].append(
                {
                    "wireId": wire_id,
                    "poleId": scid,
                    "height": {"unit": "METRE", "value": h_m},
                }
            )

            # Minimal insulator placement
            ins_type = "crossarm" if att["on_crossarm"] else "pole_top"
            spec = select_insulator(ins_type, phase)
            if spec:
                measured_structure["insulators"].append(spec)

        # ------------------------------------------------------------------
        # Recommended design – clone & bump heights -------------------------
        # ------------------------------------------------------------------
        recommended_structure: Dict[str, Any] = deepcopy(measured_structure)

        for ep in recommended_structure.get("wireEndPoints", []):
            ep["height"]["value"] += MR_HEIGHT_DELTA_M
        for wire in recommended_structure.get("wires", []):
            for ep in wire.get("endpoints", []):
                ep["height_m"] += MR_HEIGHT_DELTA_M

        # ------------------------------------------------------------------
        # Assemble *location* container ------------------------------------
        # ------------------------------------------------------------------
        location: Dict[str, Any] = {
            "label": scid,
            "poleId": scid,
            "designs": [
                {
                    "label": "Measured",
                    "layerType": "Measured",
                    "structure": measured_structure,
                },
                {
                    "label": "Recommended",
                    "layerType": "Recommended",
                    "structure": recommended_structure,
                },
            ],
        }

        # Geo-coordinates if available ------------------------------------
        lat = node.get("latitude") or node.get("lat")
        lon = node.get("longitude") or node.get("lon")
        if lat is not None and lon is not None:
            location["mapLocation"] = {
                "coordinates": [float(lon), float(lat)],
            }

        locations.append(location)

    # ----------------------------------------------------------------------
    # Final SPIDAcalc project dictionary -----------------------------------
    # ----------------------------------------------------------------------
    project: Dict[str, Any] = {
        "label": job_id,
        "dateModified": int(datetime.utcnow().timestamp() * 1000),
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "schema": "/schema/spidacalc/calc/project.schema",
        "version": 11,
        "engineer": "AutoConvert",
        "clientFile": "TechServ_Light C_Static_Tension.client",
        "leads": [
            {
                "label": job_name,
                "locations": locations,
            }
        ],
    }

    return project 