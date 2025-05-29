"""Shared low-level helpers for Katapult-related converters.

Only generic, *side-effect-free* utilities live here so they can be unit-tested
in isolation and reused by multiple sub-modules.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
import json
from pathlib import Path

# Conversion constants ------------------------------------------------------

_FT_TO_M: float = 0.3048  # feet → metres

# ---------------------------------------------------------------------------
# Engineering templates JSON ------------------------------------------------
# ---------------------------------------------------------------------------

# Load both insulator_specs (legacy) and engineering_templates (new format)
_INSULATOR_SPECS_PATH = Path(__file__).resolve().parents[3] / "api" / "data" / "insulator_specs.json"
_ENGINEERING_TEMPLATES_PATH = Path(__file__).resolve().parents[3] / "api" / "data" / "engineering_templates.json"

# Legacy insulator specs
insulator_specs: dict | list = {}

# New engineering templates
engineering_templates: Dict[str, Dict] = {
    "insulators": {},
    "wires": {}
}

# Load legacy insulator specs
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

# Load new engineering templates
try:
    with _ENGINEERING_TEMPLATES_PATH.open(encoding="utf-8") as _f:
        engineering_templates = json.load(_f)
except FileNotFoundError:
    print(
        f"[katapult.utils] Warning – engineering_templates.json not found at {_ENGINEERING_TEMPLATES_PATH}."
    )
except json.JSONDecodeError as _err:
    print(
        f"[katapult.utils] Warning – failed to parse engineering_templates.json: {_err}."
    )

def select_insulator(insulator_type: str, phase: Optional[str] = None, voltage: str = "13.2") -> Dict:
    """Select an appropriate insulator based on type, phase, and voltage level.
    
    Parameters
    ----------
    insulator_type : str
        Type of insulator (e.g., "crossarm", "pole_top", "deadend")
    phase : str, optional
        Phase designation (e.g., "Primary", "Neutral")
    voltage : str, default "13.2"
        Voltage level (e.g., "13.2", "24.9")
        
    Returns
    -------
    Dict
        Insulator specification dictionary or empty dict if not found
    """
    # Normalize insulator type to uppercase
    insulator_type = insulator_type.upper()
    
    # Get insulators from engineering templates
    insulators = engineering_templates.get("insulators", {})
    if not insulators:
        return {}
    
    # Map common names to insulator types
    type_map = {
        "CROSSARM": "PIN",
        "POLE_TOP": "POLE_TOP",
        "DEADEND": "DEADEND",
        "RUNNING_ANGLE": "RUNNING_ANGLE",
        "BRACKET": "BRACKET",
    }
    
    # Get SPIDAcalc insulator type
    spida_type = type_map.get(insulator_type, insulator_type)
    
    # Try to find a matching insulator
    for name, spec in insulators.items():
        # Match type and voltage
        if (spec.get("type") == spida_type and 
            voltage in name):
            # Phase-specific match if provided
            if phase and phase.upper() in name.upper():
                return spec
            # Otherwise just return first matching insulator
            return spec
    
    # Fallback to any matching type if voltage-specific not found
    for name, spec in insulators.items():
        if spec.get("type") == spida_type:
            return spec
    
    # Return empty dict if nothing found
    return {}

def get_wire_properties(phase: str) -> Dict:
    """Get wire properties for a specific phase from engineering templates.
    
    Parameters
    ----------
    phase : str
        Phase designation (e.g., "Primary", "Neutral")
        
    Returns
    -------
    Dict
        Wire properties dictionary with all SPIDAcalc fields
    """
    # Normalize phase name to uppercase
    phase_upper = phase.upper() if phase else "UNKNOWN"
    
    # Get wire properties from engineering templates
    wires = engineering_templates.get("wires", {})
    
    # Try exact match
    if phase_upper in wires:
        return wires[phase_upper]
    
    # Try partial match
    for wire_type, props in wires.items():
        if wire_type in phase_upper or phase_upper in wire_type:
            return props
    
    # Default to PRIMARY properties if nothing found
    return wires.get("PRIMARY", {})


# SCID normalization --------------------------------------------------------

def normalize_scid(raw_scid: Any) -> str | None:
    """Normalize SCID to ensure consistent format across the pipeline.
    
    Parameters
    ----------
    raw_scid : Any
        The raw SCID value from Katapult JSON (could be string, int, dict, etc.)
    
    Returns
    -------
    str | None
        Normalized SCID string, or None if invalid
    """
    if raw_scid is None:
        return None
    
    # If it's a dict with 'value' key (common in Katapult attributes)
    if isinstance(raw_scid, dict) and 'value' in raw_scid:
        raw_scid = raw_scid['value']
    # Handle Katapult's autogenerated button naming such as
    #     {"auto_button": "011.A"}
    # These show up when users rely on the quick-create toolbar instead of
    # manually typing the SCID.  The *auto_button* string is the one that
    # should ultimately become the structure ID inside SPIDAcalc, so we
    # extract it here.
    elif isinstance(raw_scid, dict) and 'auto_button' in raw_scid:
        raw_scid = raw_scid['auto_button']
    
    # Convert to string and strip whitespace
    scid = str(raw_scid).strip()
    
    # Return None for empty strings
    if not scid:
        return None
        
    # Additional normalization can be added here as needed
    # (e.g., remove prefixes, handle special characters)
    
    return scid


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

    # Map node_id → SCID (structureId) using normalized SCIDs
    scid_map: dict[str, str] = {}
    for node_id, node in nodes.items():
        attrs = node.get("attributes", {}) or {}
        
        # Try multiple paths to find SCID
        scid = None
        if isinstance(attrs.get("scid"), dict):
            scid = attrs.get("scid", {}).get("value")
        else:
            scid = attrs.get("scid")
        scid = scid or attrs.get("SCID") or node.get("id") or node_id
        
        # Normalize the SCID
        normalized = normalize_scid(scid)
        if normalized:
            scid_map[node_id] = normalized
            print(f"  Node {node_id} -> SCID '{normalized}'")

    # 1) Gather raw measurements per node -----------------------------------
    details: dict[str, dict] = {}
    for nid, node in nodes.items():
        d: dict[str, Any] = {}

        # Pole height --------------------------------------------------------
        pt = node.get("pole_top", {}).get(nid)
        if pt and "_measured_height" in pt:
            d["poleHeight"] = float(pt["_measured_height"]) * _FT_TO_M
            print(f"  Node {nid}: pole height = {pt['_measured_height']} ft -> {d['poleHeight']:.2f} m")
        else:
            # Default pole height
            d["poleHeight"] = 40.0 * _FT_TO_M
            print(f"  Node {nid}: using default pole height 40 ft -> {d['poleHeight']:.2f} m")

        # GLC ----------------------------------------------------------------
        gm = node.get("ground_marker", {}).get("auto_added")
        if gm and "_measured_height" in gm:
            d["groundLineClearance"] = float(gm["_measured_height"]) * _FT_TO_M
        else:
            # Default GLC
            d["groundLineClearance"] = 15.0 * _FT_TO_M
            print(f"  Node {nid}: using default GLC 15 ft")

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
    "normalize_scid",
    "select_insulator",
    "get_wire_properties",
    "engineering_templates",
]
