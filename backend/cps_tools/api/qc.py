"""SPIDAcalc QC checks API router."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, File, HTTPException, UploadFile

from cps_tools.core.qc import QCChecker
from .schemas import QCResponse

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"json"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@router.post("/api/spidacalc-qc", response_model=QCResponse)
async def spidacalc_qc_api(
    spida_file: UploadFile = File(...),
    katapult_file: UploadFile | None = File(None),
) -> dict[str, Any]:
    """Run QC checks between SPIDAcalc and optional Katapult JSON."""

    # Validate uploads ------------------------------------------------------
    if spida_file.filename == "":
        raise HTTPException(status_code=400, detail="SPIDAcalc JSON file not selected")
    if not _allowed_file(spida_file.filename):
        raise HTTPException(status_code=400, detail="Invalid SPIDAcalc file type")
    if katapult_file and katapult_file.filename and not _allowed_file(katapult_file.filename):
        raise HTTPException(status_code=400, detail="Invalid Katapult file type")

    spida_path = UPLOAD_DIR / spida_file.filename
    kata_path: Path | None = None

    try:
        # Save SPIDA file
        with spida_path.open("wb") as sf:
            shutil.copyfileobj(spida_file.file, sf)

        # Optional Katapult file
        if katapult_file and katapult_file.filename:
            kata_path = UPLOAD_DIR / katapult_file.filename
            with kata_path.open("wb") as kf:
                shutil.copyfileobj(katapult_file.file, kf)

        # Load JSONs
        with spida_path.open("r", encoding="utf-8") as sf:
            spida_json: Dict[str, Any] = json.load(sf)
        kata_json: Dict[str, Any] = {}
        if kata_path:
            with kata_path.open("r", encoding="utf-8") as kf:
                kata_json = json.load(kf)

        # Run QC
        checker = QCChecker(spida_json, kata_json)
        issues_by_pole = checker.run_checks()

        # Build poles list (replicates Flask helper)
        poles: List[Dict[str, Any]] = []
        for lead in spida_json.get("leads", []):
            for loc in lead.get("locations", []):
                label = loc.get("label") or loc.get("id") or loc.get("poleId")
                if not label:
                    continue
                coords = loc.get("mapLocation", {}).get("coordinates", [])
                if isinstance(coords, list) and len(coords) == 2:
                    lon, lat = coords
                    try:
                        poles.append({"id": str(label), "lat": float(lat), "lon": float(lon)})
                        continue
                    except (TypeError, ValueError):
                        pass
                poles.append({"id": str(label)})

        # Legacy nodes fallback ---------------------------------------------
        lat_keys = ["latitude", "lat", "Latitude", "y", "northing"]
        lon_keys = ["longitude", "lon", "Longitude", "x", "easting"]
        for node in spida_json.get("nodes", []):
            if not isinstance(node, dict):
                continue
            pid = node.get("id") or node.get("poleId") or node.get("nodeId")
            if not pid:
                continue
            lat = next((node.get(k) for k in lat_keys if node.get(k) is not None), None)
            lon = next((node.get(k) for k in lon_keys if node.get(k) is not None), None)
            if lat is not None and lon is not None:
                try:
                    poles.append({"id": str(pid), "lat": float(lat), "lon": float(lon)})
                    continue
                except (TypeError, ValueError):
                    pass
            poles.append({"id": str(pid)})

        # Deduplicate – prefer coords
        unique: dict[str, Dict[str, Any]] = {}
        for p in poles:
            pid = p["id"]
            if pid not in unique or ("lat" in p and "lat" not in unique[pid]):
                unique[pid] = p
        poles = list(unique.values())

        # Ensure every pole with issues present
        for pid in issues_by_pole.keys():
            if not any(p["id"] == pid for p in poles):
                poles.append({"id": pid})

        total_issues = sum(len(lst) for lst in issues_by_pole.values())

        return {
            "issues_by_pole": issues_by_pole,
            "issues_count": total_issues,
            "poles": poles,
        }

    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        try:
            spida_path.unlink(missing_ok=True)
            if kata_path:
                kata_path.unlink(missing_ok=True)
        except Exception:
            pass 