import json
import math
from datetime import datetime

def extract_pole_details(kat_json):
    """
    Extract pole heights, GLC, anchors, guys, and reference-pole links from Katapult JSON.
    Returns a tuple of (scid_map, details) where:
    - scid_map maps node_id to SCID
    - details contains pole measurements and relationships per node
    """
    nodes = kat_json.get("nodes") or kat_json.get("data", {}).get("nodes", {})
    conns = kat_json.get("connections") or kat_json.get("data", {}).get("connections", {})

    # Map node_id → SCID (structureId)
    scid_map = {}
    for node_id, node in nodes.items():
        attrs = node.get("attributes", {}) or {}
        scid = attrs.get("scid", {}).get("value") or str(node_id)
        scid_map[node_id] = str(scid)

    # 1) Gather raw measurements per node
    details = {}
    for nid, node in nodes.items():
        d = {}
        # Pole height from the "pole_top" measured_height
        pt = node.get("pole_top", {}).get(nid)
        if pt and "_measured_height" in pt:
            d["poleHeight"] = float(pt["_measured_height"])

        # GLC from any ground_marker entry
        gm = node.get("ground_marker", {}).get("auto_added")
        if gm and "_measured_height" in gm:
            d["groundLineClearance"] = float(gm["_measured_height"])

        # Anchors from anchor_calibration
        anchors = []
        for aid, anc in node.get("anchor_calibration", {}).items():
            h = anc.get("height")
            if h:
                anchors.append({"anchorId": aid, "height": float(h)})
        d["anchors"] = anchors

        # Guys from guying
        guys = []
        for gid, guy in node.get("guying", {}).items():
            ht = guy.get("_measured_height")
            gt = guy.get("guying_type")
            if ht is not None:
                guys.append({"guyId": gid, "height": float(ht), "type": gt})
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
    nodes = kat_json.get("nodes") or kat_json.get("data", {}).get("nodes", {})
    if not isinstance(nodes, dict):
        raise ValueError("Katapult JSON: no `nodes` dict found.")

    # Extract pole details
    scid_map, pole_details = extract_pole_details(kat_json)

    # Build locations with designs for each structure
    locations = []
    for node_id, node in nodes.items():
        attrs = node.get("attributes", {}) or {}
        scid = attrs.get("scid", {}).get("value") or attrs.get("SCID") or node.get("id")
        pole_no = attrs.get("PoleNumber", {}).get("value") or attrs.get("PoleNumber") or scid

        # latitude / longitude
        lat = node.get("latitude") or node.get("lat")
        lon = node.get("longitude") or node.get("lon")
        # fallback to geometry.coordinates
        if (lat is None or lon is None) and "geometry" in node:
            coords = node["geometry"].get("coordinates", [])
            if len(coords) >= 2:
                lon, lat = coords[0], coords[1]

        if not (scid and pole_no and lat is not None and lon is not None):
            continue

        # Get pole details
        det = pole_details.get(node_id, {})
        pole_height = det.get("poleHeight", 40.0)
        glc = det.get("groundLineClearance", 15.0)

        # Create location with design
        location = {
            "label": str(scid),
            "poleId": str(scid),
            "mapLocation": {
                "coordinates": [float(lon), float(lat)]
            },
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