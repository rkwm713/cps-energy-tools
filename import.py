import json
import math
from pathlib import Path

# ——— Utility functions ———

def haversine(lat1, lon1, lat2, lon2):
    # compute distance in meters between two lat/lon points
    R = 6371000
    phi1, phi2 = map(math.radians, (lat1, lat2))
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

# ——— Load Katapult JSON ———

katapult_path = Path("/mnt/data/CPS_6457E_03_Kata.json")
with katapult_path.open() as f:
    kat = json.load(f)

# Assume your Katapult JSON has both "nodes" and "connections"
nodes = kat.get("nodes", {})
conns = kat.get("connections", {})

# ——— Build SPIDAcalc “Project Exchange” object ———

spida = {
    # schema version identifier — adjust if needed
    "schemaVersion": "11.0.2",
    "job": {
        "id": "CPS_6457E_03",            # set to your job number
        "name": "CPS Energy Make-Ready"
        # …any other job metadata required by the SPIDA schema…
    },
    "structures": []
}

# ——— Map nodes → SPIDAcalc structures ———

for node_id, node in nodes.items():
    attrs = node.get("attributes", {})
    scid = attrs.get("scid", {}).get("value", "")
    pole_no = attrs.get("PoleNumber", {}).get("value", "")
    lat = node.get("latitude")
    lon = node.get("longitude")

    structure = {
        "structureId": scid,
        "poleNumber": pole_no,
        "latitude": lat,
        "longitude": lon,
        "sections": []
    }
    spida["structures"].append(structure)

# ——— Map connections → SPIDAcalc sections ———

# Build quick lookup from scid → index in spida["structures"]
scid_index = {s["structureId"]: i for i, s in enumerate(spida["structures"])}

for conn_id, conn in conns.items():
    n1 = conn["node_id_1"]
    n2 = conn["node_id_2"]
    node1 = nodes[n1]
    node2 = nodes[n2]

    scid1 = node1["attributes"]["scid"]["value"]
    scid2 = node2["attributes"]["scid"]["value"]

    # find positions in our structures list
    idx1 = scid_index.get(scid1)
    idx2 = scid_index.get(scid2)
    if idx1 is None or idx2 is None:
        continue  # skip if missing

    # compute approximate length
    lat1, lon1 = node1["latitude"], node1["longitude"]
    lat2, lon2 = node2["latitude"], node2["longitude"]
    length_m = haversine(lat1, lon1, lat2, lon2)

    section = {
        "sectionId": conn_id,
        "fromStructureId": scid1,
        "toStructureId": scid2,
        "connectionType": conn.get("button"),   # e.g. "aerial_path"
        "length": length_m,
        # optional: include the actual shape points if you want SPIDAcalc to draw the line
        "shapePoints": [
            {"latitude": s["latitude"], "longitude": s["longitude"]}
            for s in conn.get("sections", {}).values()
        ]
    }

    # append to the “from” structure
    spida["structures"][idx1]["sections"].append(section)

# ——— Write out SPIDAcalc JSON ———

out_path = katapult_path.with_name(katapult_path.stem + "_for_spidacalc.json")
with out_path.open("w") as f:
    json.dump(spida, f, indent=2)

print(f"Wrote SPIDAcalc JSON to: {out_path}")
