"""Pole Comparison Tool API (FastAPI router).

Replaces the Flask `/api/pole-comparison` endpoint.  Uses the existing
`PoleComparisonTool` class under the hood.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from cps_tools.core.pole_compare import (
    PoleComparisonTool,
    ProcessedRow,
    VerificationResult,
)
from .schemas import PoleComparisonResponse  # NEW

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Configuration – reuse uploads directory at project root
# ---------------------------------------------------------------------------

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {"xlsx", "xls", "json"}


def _allowed_file(filename: str) -> bool:  # noqa: WPS110 – name mirrors Flask helper
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/pole-compare-debug")
async def pole_compare_debug():
    """Debug endpoint to check if the Pole Comparison router is working correctly."""
    return {"status": "ok", "message": "Pole Comparison debug endpoint is working", "route": "/api/pole-compare-debug"}

@router.get("/pole-compare-routes")
async def pole_compare_routes():
    """Return all routes registered on this router for debugging."""
    routes = []
    for route in router.routes:
        routes.append({
            "path": f"/api{route.path}",  # Include the prefix
            "name": route.name,
            "methods": list(route.methods) if hasattr(route, "methods") else []
        })
    return {"routes": routes}

@router.post("/pole-comparison", response_model=PoleComparisonResponse)
async def pole_comparison_api(
    katapult_file: UploadFile = File(...),
    spida_file: UploadFile = File(...),
    threshold: float = Form(5.0),
) -> dict[str, Any]:
    """Compare Katapult Excel with SPIDAcalc JSON and flag pole discrepancies."""

    # Guard: file presence ---------------------------------------------------
    if katapult_file.filename == "" or spida_file.filename == "":  # noqa: WPS520 – explicit empty check
        raise HTTPException(status_code=400, detail="No files selected")

    # Guard: extension -------------------------------------------------------
    if not (_allowed_file(katapult_file.filename) and _allowed_file(spida_file.filename)):
        raise HTTPException(status_code=400, detail="Invalid file types")

    # Persist uploads to disk (PoleComparisonTool expects file paths) --------
    k_path = UPLOAD_DIR / katapult_file.filename
    s_path = UPLOAD_DIR / spida_file.filename

    try:
        with k_path.open("wb") as k_f:
            shutil.copyfileobj(katapult_file.file, k_f)
        with s_path.open("wb") as s_f:
            shutil.copyfileobj(spida_file.file, s_f)

        # ------------------------------------------------------------------
        # Run comparison ---------------------------------------------------
        # ------------------------------------------------------------------
        tool = PoleComparisonTool(threshold=threshold)
        comparison_data, verification_result = tool.process_files(str(k_path), str(s_path))
        issues_data = tool.apply_threshold_and_find_issues(comparison_data)

        # Serialise dataclass rows -----------------------------------------
        results: List[dict[str, Any]] = [asdict(r) if isinstance(r, ProcessedRow) else r for r in comparison_data]
        issues: List[dict[str, Any]] = [asdict(r) if isinstance(r, ProcessedRow) else r for r in issues_data]
        verification: dict[str, Any]
        if isinstance(verification_result, VerificationResult):
            verification = asdict(verification_result)  # type: ignore[arg-type]
        else:
            verification = verification_result  # if tool returns dict already

        summary = {
            "total_poles": len(results),
            "poles_with_issues": len(issues),
            "threshold": threshold,
        }

        return {
            "results": results,
            "issues": issues,
            "verification": verification,
            "summary": summary,
        }
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        # Clean-up temp files ------------------------------------------------
        try:
            k_path.unlink(missing_ok=True)
            s_path.unlink(missing_ok=True)
        except Exception:  # noqa: BLE001
            pass
