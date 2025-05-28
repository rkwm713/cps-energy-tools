"""Temporary wrapper referencing legacy spida_utils. To be refactored."""

# NOTE: This is a *first slice* of migrating logic out of the monolithic
# `spida_utils` module.  Once the transition is complete we will delete the
# duplicated code from the legacy module and import helpers directly here.

from __future__ import annotations

from datetime import datetime
import math
from typing import Any

# Re-use small helpers from our own utils module.  `insulator_specs` remains
# imported from the legacy module for now until its data-loading is migrated.
from .utils import _ensure_dict, _FT_TO_M, extract_pole_details, insulator_specs  # noqa: PLC0414

__all__ = [
    "convert_katapult_to_spidacalc",
    "extract_attachments",
    "insulator_specs",
]


# ---------------------------------------------------------------------------
# Katapult → SPIDAcalc conversion (lifted from spida_utils with minimal edits)
# ---------------------------------------------------------------------------


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

    # --- Haversine helper --------------------------------------------------
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:  # noqa: WPS430 – inner fn is fine here
        R = 6_371_000.0  # Earth radius in metres
        phi1, phi2 = map(math.radians, (lat1, lat2))
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

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


# ---------------------------------------------------------------------------
# Attachment extraction (verbatim from spida_utils for now)
# ---------------------------------------------------------------------------


def extract_attachments(nodes: dict[str, Any], connections: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return **SCID → list[attachment]** mapping extracted from raw Katapult dictionaries.

    A very direct copy of the original helper – it *will* be refactored once
    a comprehensive test-suite is in place.
    """

    from spida_utils import extract_attachments as _legacy_extract

    # Delegate to legacy implementation for now – baby steps.
    return _legacy_extract(nodes, connections) 