"""Shared low-level helpers for Katapult-related converters.

Only generic, *side-effect-free* utilities live here so they can be unit-tested
in isolation and reused by multiple sub-modules.
"""

from __future__ import annotations

from typing import Any
import json
from pathlib import Path

# Conversion constants ------------------------------------------------------

_FT_TO_M: float = 0.3048  # feet → metres

# ---------------------------------------------------------------------------
# Insulator specifications JSON ---------------------------------------------
# ---------------------------------------------------------------------------

# Location is *project-root*/api/data/insulator_specs.json (same as legacy)
_INSULATOR_SPECS_PATH = Path(__file__).resolve().parents[3] / "api" / "data" / "insulator_specs.json"

insulator_specs: dict | list = {}

try:
    with _INSULATOR_SPECS_PATH.open(encoding="utf-8") as _f:
        insulator_specs = json.load(_f)
except FileNotFoundError:
    print(
        f"[katapult.utils] Warning – insulator_specs.json not found at {_INSULATOR_SPECS_PATH}. 'insulator_specs' will be empty."
    )
except json.JSONDecodeError as _err:
    print(
        f"[katapult.utils] Warning – failed to parse insulator_specs.json: {_err}. 'insulator_specs' will be empty."
    )


# Collection normaliser ------------------------------------------------------

def _ensure_dict(collection: Any, key_field: str = "id", name: str = "collection") -> dict:
    """Return *collection* as a dictionary.

    Katapult sometimes serialises the ``nodes`` and ``connections`` arrays as
    *lists* in exported JSON.  The importer expects dictionaries keyed by their
    unique identifier, so we convert when necessary.

    Parameters
    ----------
    collection : dict | list
        The raw JSON value (may be ``dict`` or ``list``).
    key_field : str, default ``"id"``
        Field name to use as the dictionary key when *collection* is a list.
    name : str, default ``"collection"``
        Human-readable name used in error messages.
    """

    # Fast-path – already a mapping → return unchanged
    if isinstance(collection, dict):
        return collection

    # If we receive a list, turn it into a mapping keyed by *key_field*
    if isinstance(collection, list):
        out = {}
        for idx, item in enumerate(collection):
            if not isinstance(item, dict):
                raise ValueError(f"{name} list item at index {idx} is not an object.")
            item_id = item.get(key_field) or str(idx)
            out[str(item_id)] = item
        return out

    # Anything else is unsupported
    raise ValueError(
        f"Katapult JSON: expected {name} to be dict or list, got {type(collection).__name__}."
    )


# ---------------------------------------------------------------------------
# Pole-detail extraction -----------------------------------------------------
# ---------------------------------------------------------------------------

def extract_pole_details(kat_json: dict):
    """Return *(scid_map, details)* extracted from raw Katapult JSON.

    * **scid_map** – mapping *node_id → SCID* (string)
    * **details**  – mapping *node_id → dict* containing:
        - poleHeight (float, metres)
        - groundLineClearance (float, metres)
        - anchors (list[dict])
        - guys (list[dict])
        - referencePoles (list[str])

    Logic ported verbatim from the legacy ``spida_utils`` module so downstream
    code no longer needs to depend on the monolithic utility file.
    """

    nodes = _ensure_dict(
        kat_json.get("nodes") or kat_json.get("data", {}).get("nodes", {}),
        name="nodes",
    )
    conns = _ensure_dict(
        kat_json.get("connections")
        or kat_json.get("data", {}).get("connections", {}),
        name="connections",
    )

    # Map node_id → SCID (structureId)
    scid_map: dict[str, str] = {}
    for node_id, node in nodes.items():
        attrs = node.get("attributes", {}) or {}
        scid = (
            attrs.get("scid", {}).get("value") if isinstance(attrs.get("scid"), dict) else attrs.get("scid")
        )
        scid = scid or attrs.get("SCID") or node.get("id") or node_id
        scid_map[node_id] = str(scid)

    # 1) Gather raw measurements per node -----------------------------------
    details: dict[str, dict] = {}
    for nid, node in nodes.items():
        d: dict[str, Any] = {}

        # Pole height --------------------------------------------------------
        pt = node.get("pole_top", {}).get(nid)
        if pt and "_measured_height" in pt:
            d["poleHeight"] = float(pt["_measured_height"]) * _FT_TO_M

        # GLC ----------------------------------------------------------------
        gm = node.get("ground_marker", {}).get("auto_added")
        if gm and "_measured_height" in gm:
            d["groundLineClearance"] = float(gm["_measured_height"]) * _FT_TO_M

        # Anchors ------------------------------------------------------------
        anchors: list[dict] = []
        for aid, anc in node.get("anchor_calibration", {}).items():
            h = anc.get("height")
            if h:
                anchors.append({"anchorId": aid, "height": float(h) * _FT_TO_M})
        d["anchors"] = anchors

        # Guys ---------------------------------------------------------------
        guys: list[dict] = []
        for gid, guy in node.get("guying", {}).items():
            ht = guy.get("_measured_height")
            gt = guy.get("guying_type")
            if ht is not None:
                guys.append({"guyId": gid, "height": float(ht) * _FT_TO_M, "type": gt})
        d["guys"] = guys

        details[nid] = d

    # 2) Build reference-poles list ----------------------------------------
    refs: dict[str, list[str]] = {nid: [] for nid in nodes}
    for conn in conns.values():
        typ = conn.get("attributes", {}).get("connection_type", {}).get("button_added")
        if typ == "reference":
            n1, n2 = conn.get("node_id_1"), conn.get("node_id_2")
            s1, s2 = scid_map.get(n1), scid_map.get(n2)
            if s1 and s2:
                refs[n1].append(s2)
                refs[n2].append(s1)

    for nid, lst in refs.items():
        details[nid]["referencePoles"] = lst

    return scid_map, details


# ---------------------------------------------------------------------------
# Public re-exports ----------------------------------------------------------
# ---------------------------------------------------------------------------

__all__ = [
    "_FT_TO_M",
    "_ensure_dict",
    "extract_pole_details",
    "insulator_specs",
] 