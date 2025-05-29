"""MRR processing API router.

Runs the MattsMRR heavy Excel generation without GUI and returns a summary
payload plus a download link for the generated XLSX.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from cps_tools.core.mrr import process  # Import the headless process function
from cps_tools.settings import get_settings # Import get_settings
from .schemas import MRRProcessResponse

# Create router with an explicit prefix to avoid path conflicts
router = APIRouter(prefix="/api")

settings = get_settings() # Get settings instance
UPLOAD_DIR = Path(settings.upload_dir) # Use the centralized upload directory

ALLOWED_EXTENSIONS = {"json", "geojson"}


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@router.post("/mrr-process", response_model=MRRProcessResponse)
async def mrr_process_api(
    job_file: UploadFile = File(...),
    geojson_file: UploadFile | None = File(None),
) -> MRRProcessResponse:
    """Process MRR job & optional GeoJSON; returns summary + preview."""

    # Validate --------------------------------------------------------------
    if job_file.filename == "":
        raise HTTPException(status_code=400, detail="No Job JSON file selected")
    if not _allowed_file(job_file.filename):
        raise HTTPException(status_code=400, detail="Invalid Job JSON file type")
    if geojson_file and geojson_file.filename and not _allowed_file(geojson_file.filename):
        raise HTTPException(status_code=400, detail="Invalid GeoJSON file type")

    # Persist uploads -------------------------------------------------------
    job_path = UPLOAD_DIR / job_file.filename
    with job_path.open("wb") as jf:
        shutil.copyfileobj(job_file.file, jf)

    geojson_path: Path | None = None
    if geojson_file and geojson_file.filename:
        geojson_path = UPLOAD_DIR / geojson_file.filename
        with geojson_path.open("wb") as gf:
            shutil.copyfileobj(geojson_file.file, gf)

    try:
        # Use the 'process' function directly
        output_path, stats = process(
            job_json=job_path,
            geojson=geojson_path,
        )

        if not output_path:
            # The 'process' function should raise an exception if it fails,
            # so this check might be redundant if 'process' is robust.
            # However, keeping it for safety.
            raise HTTPException(status_code=500, detail="MRR processing failed to produce an output file.")

        filename = Path(output_path).name

        # Front-end expects this key to show the Download button
        stats["output_filename"] = filename

        response = MRRProcessResponse(
            success=True,
            message="MRR processing completed successfully",
            summary=stats,  # 'stats' from 'process' function
            preview=None,   # 'process' function does not return a 'preview'
            download_available=True,
            download_url=f"/api/download-mrr/{filename}",  # Keep this URL format for frontend compatibility
        )
        return response

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        # Clean-up uploads (keep output file for download)
        try:
            job_path.unlink(missing_ok=True)
            if geojson_path:
                geojson_path.unlink(missing_ok=True)
        except Exception:
            pass


# Add a debug endpoint to help diagnose routing issues
@router.get("/mrr-debug")
async def mrr_debug():
    """Debug endpoint to check if the router is working correctly."""
    return {"status": "ok", "message": "MRR debug endpoint is working", "route": "/api/mrr-debug"}

@router.get("/mrr-routes")
async def mrr_routes():
    """Return all routes registered on this router for debugging."""
    routes = []
    for route in router.routes:
        routes.append({
            "path": f"/api{route.path}",  # Include the prefix
            "name": route.name,
            "methods": list(route.methods) if hasattr(route, "methods") else []
        })
    return {"routes": routes}

@router.get("/download-mrr/{filename}")
async def download_mrr_file(filename: str):
    """Download the generated MRR Excel file by filename."""
    path = UPLOAD_DIR / Path(filename).name  # security – prevent path traversal
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=path.name)
