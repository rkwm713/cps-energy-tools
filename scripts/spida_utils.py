import json
import math
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Load insulator specifications JSON once at module import so other helpers
# can access it via `spida_utils.insulator_specs`.
# ---------------------------------------------------------------------------
_INSULATOR_SPECS_PATH = (
    Path(__file__).resolve().parent / "api" / "data" / "insulator_specs.json"
)

# Fall-back: if the file is missing we still want the module to import without
# crashing hard.  Instead, keep `insulator_specs` empty and issue a gentle
# warning so calling code can decide what to do.

insulator_specs: dict | list = {}

try:
    with _INSULATOR_SPECS_PATH.open(encoding="utf-8") as _f:
        insulator_specs = json.load(_f)
except FileNotFoundError:
    # Optional: could use logging instead of print depending on project prefs
    print(
        f"[spida_utils] Warning – insulator_specs.json not found at "
        f"{_INSULATOR_SPECS_PATH}.  `insulator_specs` will be empty."
    )
except json.JSONDecodeError as _err:
    print(
        f"[spida_utils] Warning – failed to parse insulator_specs.json: {_err}. "
        "`insulator_specs` will be empty."
    )

_FT_TO_M = 0.3048  # feet → metres conversion factor

def extract_pole_details(kat_json):
    """
    Extract pole heights, GLC, anchors, guys, and reference-pole links from Katapult JSON.
    Returns a tuple of (scid_map, details) where:
    - scid_map maps node_id to SCID
    - details contains pole measurements and relationships per node
    """
    nodes = _ensure_dict(
        kat_json.get("nodes") or kat_json.get("data", {}).get("nodes", {}),
        name="nodes",
    )
    conns = _ensure_dict(
        kat_json.get("connections") or kat_json.get("data", {}).get("connections", {}),
        name="connections",
    )

    # Map node_id → SCID (structureId)
    scid_map = {}
    for node_id, node in nodes.items():
        attrs = node.get("attributes", {}) or {}
        scid = attrs.get("scid", {}).get("value") if isinstance(attrs.get("scid"), dict) else attrs.get("scid")
        scid = scid or attrs.get("SCID") or node.get("id") or node_id
        scid_map[node_id] = str(scid)

    # 1) Gather raw measurements per node
    details = {}
    for nid, node in nodes.items():
        d = {}
        # Pole height from the "pole_top" measured_height
        pt = node.get("pole_top", {}).get(nid)
        if pt and "_measured_height" in pt:
            d["poleHeight"] = float(pt["_measured_height"]) * _FT_TO_M

        # GLC from any ground_marker entry
        gm = node.get("ground_marker", {}).get("auto_added")
        if gm and "_measured_height" in gm:
            d["groundLineClearance"] = float(gm["_measured_height"]) * _FT_TO_M

        # Anchors from anchor_calibration
        anchors = []
        for aid, anc in node.get("anchor_calibration", {}).items():
            h = anc.get("height")
            if h:
                anchors.append({"anchorId": aid, "height": float(h) * _FT_TO_M})
        d["anchors"] = anchors

        # Guys from guying
        guys = []
        for gid, guy in node.get("guying", {}).items():
            ht = guy.get("_measured_height")
            gt = guy.get("guying_type")
            if ht is not None:
                guys.append({"guyId": gid, "height": float(ht) * _FT_TO_M, "type": gt})
        d["guys"] = guys

        details[nid] = d

    # 2) Build reference-poles list per node by scanning connections of type "reference"
    refs = {nid: [] for nid in nodes}
    for cid, conn in conns.items():
        typ = conn.get("attributes", {}).get("connection_type", {}).get("button_added")
        if typ == "reference":
            n1, n2 = conn.get("node_id_1"), conn.get("node_id_2")
            # map to SCIDs
            s1, s2 = scid_map.get(n1), scid_map.get(n2)
            if s1 and s2:
                refs[n1].append(s2)
                refs[n2].append(s1)
    # attach refs
    for nid, lst in refs.items():
        details[nid]["referencePoles"] = lst

    return scid_map, details

def convert_katapult_to_spidacalc(kat_json: dict, job_id: str, job_name: str):
    """
    Convert a Katapult Pro JSON (nodes + connections) into a SPIDAcalc v11 native project JSON.
    Returns the SPIDA JSON dictionary.
    """
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000.0
        phi1, phi2 = map(math.radians, (lat1, lat2))
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

    # Extract nodes and build structures
    raw_nodes = kat_json.get("nodes") or kat_json.get("data", {}).get("nodes", {})
    nodes = _ensure_dict(raw_nodes, key_field="id", name="nodes")

    # Extract pole details
    scid_map, pole_details = extract_pole_details(kat_json)

    # Build locations with designs for each structure
    locations = []
    for node_id, node in nodes.items():
        attrs = node.get("attributes", {}) or {}
        scid = attrs.get("scid", {}).get("value") if isinstance(attrs.get("scid"), dict) else attrs.get("scid")
        scid = scid or attrs.get("SCID") or node.get("id") or node_id
        pole_no = (
            attrs.get("PoleNumber", {}).get("value")
            or attrs.get("PoleNumber")
            or scid  # fall back to SCID if explicit pole number missing
        )

        # latitude / longitude
        lat = node.get("latitude") or node.get("lat")
        lon = node.get("longitude") or node.get("lon")
        # fallback to geometry.coordinates
        if (lat is None or lon is None) and "geometry" in node:
            coords = node["geometry"].get("coordinates", [])
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]

        # We require a valid SCID / pole number.  Latitude & longitude are
        # *nice-to-have* but not mandatory – many Katapult exports omit them.
        # If either coordinate is missing we still create the location, leaving
        # mapLocation out so downstream code can fall back to "—".
        if not scid:
            continue

        # Get pole details
        det = pole_details.get(node_id, {})
        pole_height = det.get("poleHeight", 40.0 * _FT_TO_M)
        glc = det.get("groundLineClearance", 15.0 * _FT_TO_M)

        # Create location with design
        location: dict = {
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
                                    "height": {"unit": "METRE", "value": a["height"]}
                                }
                                for a in det.get("anchors", [])
                            ],
                            "guys": [
                                {
                                    "id": g["guyId"],
                                    "height": {"unit": "METRE", "value": g["height"]},
                                    "type": g["type"]
                                }
                                for g in det.get("guys", [])
                            ],
                            "referencePoles": [
                                {"id": ref_sid}
                                for ref_sid in det.get("referencePoles", [])
                            ]
                        },
                        "wireEndPoints": [],
                        "wires": []
                    }
                }
            ]
        }

        # Only include coordinates when both are present.
        if lat is not None and lon is not None:
            location["mapLocation"] = {"coordinates": [float(lon), float(lat)]}

        locations.append(location)

    # Build the native SPIDAcalc project JSON
    spida_project = {
        "label": job_id,
        "dateModified": int(datetime.now().timestamp() * 1000),  # Current time in milliseconds
        "clientFile": "TechServ_Light C_Static_Tension.client",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "schema": "/schema/spidacalc/calc/project.schema",
        "version": 11,
        "engineer": "Taylor Larsen",
        "leads": [
            {
                "label": "Lead",
                "locations": locations
            }
        ]
    }

    return spida_project

# ---------------------------------------------------------------------------
# Attachment extraction helper
# ---------------------------------------------------------------------------

def extract_attachments(nodes: dict, connections: dict) -> dict[str, list[dict]]:
    """Return a mapping **SCID → list[attachment]** extracted from raw Katapult
    *nodes* and *connections* dictionaries.

    Each *attachment* is a dict with the following keys::

        {
            "height": float | None,   # measured height in feet (or inches – see below)
            "phase": str | None,     # e.g. "Primary", "Neutral", "Comms" …
            "onCrossarm": bool       # True if the attachment sits on a crossarm
        }

    Because Katapult JSON can vary between jobs / export versions, the helper is
    defensive – it checks a handful of common patterns but falls back to *None*
    / *False* when a field cannot be found.
    """

    # Accept lists as well – normalise to dictionaries keyed by ID so the rest
    # of the helper can use the common `.items()` pattern safely.
    nodes = _ensure_dict(nodes, name="nodes")
    connections = _ensure_dict(connections, name="connections")

    # --------------------------------------------------
    # 1) Build node-id → SCID look-up so we always key the
    #    returned dictionary by SCID (string).
    # --------------------------------------------------
    scid_for_node: dict[str, str] = {}
    for nid, node in nodes.items():
        scid = (
            node.get("attributes", {}).get("scid", {}).get("value")
            or node.get("attributes", {}).get("SCID")
            or node.get("id")
            or str(nid)
        )
        scid_for_node[str(nid)] = str(scid)

    # Initialise result – make sure each SCID appears even if we find 0 attachments
    result: dict[str, list[dict]] = {scid: [] for scid in scid_for_node.values()}

    # --------------------------------------------------
    # 2) Utility to probe a *section* (or other data blob) for
    #    attachment info relative to a single pole.
    # --------------------------------------------------
    def _parse_attachment_blob(blob: dict) -> list[dict]:
        out: list[dict] = []

        # --- Common place 1: straight keys (height / phase / onCrossarm) ---
        if {'height', 'phase', 'onCrossarm'} <= blob.keys():
            out.append({
                'height': _safe_float(blob.get('height')),
                'phase': blob.get('phase'),
                'onCrossarm': bool(blob.get('onCrossarm')),
            })
            return out  # assume one attachment described directly

        # --- Common place 2: PhotoFirst wire list (what MattsMRR uses) ---
        #     path: photofirst_data → wire / equipment / guying → item dict
        pf = blob.get('photofirst_data') or {}
        for cat in ('wire', 'equipment', 'guying'):
            for item in pf.get(cat, {}).values():
                h = _safe_float(item.get('_measured_height'))
                phase = item.get('phase') or item.get('_phase') or _infer_phase(item)
                on_arm = bool(item.get('on_crossarm') or item.get('onCrossarm'))
                out.append({'height': h, 'phase': phase, 'onCrossarm': on_arm})
        return out

    def _safe_float(val):
        try:
            return float(val) if val is not None and val != '' else None
        except (ValueError, TypeError):
            return None

    def _infer_phase(item: dict | None) -> str | None:
        """Best-effort guess of phase label from cable / description fields."""
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

    # --------------------------------------------------
    # 3) Walk each connection and harvest attachments at both ends.
    # --------------------------------------------------
    for conn in connections.values():
        for endpoint, tag in (("node_id_1", "end1"), ("node_id_2", "end2")):
            nid = conn.get(endpoint)
            if nid is None:
                continue
            scid = scid_for_node.get(str(nid))
            if scid is None:
                continue

            # ---- Pattern A: attachment data stored directly on the connection ----
            # e.g. conn['end1_height'], conn['end1_phase'], conn['end1_onCrossarm']
            direct_height = conn.get(f"{tag}_height") or conn.get(f"{endpoint}_height")
            if direct_height is not None:
                result[scid].append({
                    'height': _safe_float(direct_height),
                    'phase': conn.get(f"{tag}_phase") or conn.get(f"{endpoint}_phase"),
                    'onCrossarm': bool(conn.get(f"{tag}_onCrossarm") or conn.get(f"{endpoint}_onCrossarm")),
                })

            # ---- Pattern B: iterate through sections looking for photo / wire data ----
            for sect in (conn.get('sections') or {}).values():
                result[scid].extend(_parse_attachment_blob(sect))

    # --------------------------------------------------
    # 4) Also look inside each node for attachments that are not tied to a
    #    connection (e.g. equipment mounted only on that pole).
    # --------------------------------------------------
    for nid, node in nodes.items():
        scid = scid_for_node[str(nid)]
        result[scid].extend(_parse_attachment_blob(node))

    # --------------------------------------------------
    # 5) Optional post-processing: remove empty placeholders / deduplicate.
    # --------------------------------------------------
    clean: dict[str, list[dict]] = {}
    for scid, lst in result.items():
        # Drop completely empty records (where every key is None / False)
        filtered: list[dict] = []
        for att in lst:
            if att.get('height') is None and att.get('phase') is None and not att.get('onCrossarm'):
                continue
            filtered.append(att)

        # Simple de-dup (height & phase) to avoid repeats
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

# ---------------------------------------------------------------------------
# Utility helpers – normalise raw Katapult collections into dictionaries
# ---------------------------------------------------------------------------

def _ensure_dict(collection, key_field="id", name="collection"):
    """Return *collection* as a dictionary.  Katapult sometimes serialises the
    ``nodes`` and ``connections`` arrays as *lists* in exported JSON.  The
    importer expects dictionaries keyed by their unique identifier, so we
    convert when necessary.

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
    raise ValueError(f"Katapult JSON: expected {name} to be dict or list, got {type(collection).__name__}.")

# ---------------------------------------------------------------------------
# 🔒 Deprecation shim – transition to cps_tools.core.katapult.converter
# ---------------------------------------------------------------------------

# These imports intentionally occur *at the very end* of the module so they
# override the legacy in-file definitions above.  Existing callers that rely
# on spida_utils.convert_katapult_to_spidacalc / extract_attachments will now
# be transparently served by the refactored versions under the cps_tools
# namespace.  Remove this shim once the monolithic file is deleted.

from cps_tools.core.katapult.converter import (
    convert_katapult_to_spidacalc as _kat_convert,
    extract_attachments as _kat_extract,
)

from cps_tools.core.katapult.utils import insulator_specs as _kat_specs

convert_katapult_to_spidacalc = _kat_convert  # type: ignore[assignment]
extract_attachments = _kat_extract  # type: ignore[assignment]
insulator_specs = _kat_specs  # type: ignore[assignment]

__all__ = [
    # public helpers still genuinely defined here
    "_ensure_dict",
    "extract_pole_details",
    "convert_katapult_to_spidacalc",
    "extract_attachments",
    "insulator_specs",
] 