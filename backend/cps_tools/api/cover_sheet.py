"""Cover-Sheet extraction API.

Converts a SPIDAcalc project JSON into the tabular data required by the
Cover-Sheet Excel generator (front-end consumes it directly).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from cps_tools.core.cover_sheet import extract_cover_sheet_data
from .schemas import CoverSheetResponse

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"json"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@router.post("/api/cover-sheet", response_model=CoverSheetResponse)
async def cover_sheet_api(spida_file: UploadFile = File(...)) -> CoverSheetResponse:
    """Generate cover-sheet JSON fragment from an uploaded SPIDAcalc file."""

    if spida_file.filename == "":
        raise HTTPException(status_code=400, detail="No file selected")
    if not _allowed_file(spida_file.filename):
        raise HTTPException(status_code=400, detail="Invalid file type (must be .json)")

    spida_path = UPLOAD_DIR / spida_file.filename

    try:
        with spida_path.open("wb") as f:
            shutil.copyfileobj(spida_file.file, f)

        # Load JSON and run extraction
        with spida_path.open("r", encoding="utf-8") as f:
            spida_json = json.load(f)

        data = extract_cover_sheet_data(spida_json).dict(by_alias=True)
        return data  # CoverSheetResponse expects a plain dict

    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        try:
            spida_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass 