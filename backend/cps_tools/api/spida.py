from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from jsonschema import Draft7Validator, ValidationError, RefResolver

from cps_tools.core.katapult.converter import convert_katapult_to_spidacalc, extract_attachments, insulator_specs
from cps_tools.settings import get_settings
from backend.cps_tools.api.schemas import (
    InsulatorSpecsResponse,
    SpidaProjectPayload,
    SpidaValidationResponse,
    SpidaImportResponse,
)

# ---------------------------------------------------------------------------
# Configuration (copied from fastapi_app.py, consider centralizing later if needed)
# ---------------------------------------------------------------------------

APP_ROOT = Path(__file__).resolve().parent.parent.parent.parent # Adjust path for new location
# This APP_ROOT needs to point to the root of the application where 'data' and 'uploads' are relative to.
# Since spida.py is in backend/cps_tools/api, it's 4 levels up to the project root.
# A better approach might be to pass these paths from the main app or settings.

settings = get_settings()
UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(exist_ok=True)

# Assuming data/spidacalc-v11-schema.json is at the project root level
SCHEMA_PATH = Path("data") / "spidacalc-v11-schema.json" # This path needs to be relative to the project root, not the current file.
# This will be handled by the main app's _build_validator, so we don't need to duplicate it here.
# For now, I'll keep the imports but remove the validator build logic from here.

# Globals that will hold the loaded schema and compiled validator
# These should ideally be managed by the main app and passed to routers if needed,
# or accessed via a dependency injection system. For now, we'll assume the main app
# handles validation.

# ---------------------------------------------------------------------------
# Helpers (copied from fastapi_app.py)
# ---------------------------------------------------------------------------

_FT_TO_M = 0.3048


def _seed_insulators(spida_project: Dict[str, Any], attachments_by_scid: Dict[str, List[Dict]]):
    """Add `insulators` arrays to each structure in *spida_project* from
    *attachments_by_scid* mapping (output of extract_attachments).  The routine
    modifies the project in-place and returns it for convenience."""

    for lead in spida_project.get("leads", []):
        for loc in lead.get("locations", []):
            scid = str(loc.get("poleId"))
            
            # Debug logging
            print(f"  Looking up SCID '{scid}' in attachments_by_scid")
            attachments = attachments_by_scid.get(scid, [])
            print(f"    Found {len(attachments)} attachments")
            
            designs = loc.get("designs", [])
            if not designs:
                continue
            struct = designs[0].get("structure", {})
            existing_rich = [i for i in struct.get("insulators", []) if i.get("size") or i.get("type")]  # non-placeholder

            pole_height_m = (
                struct.get("pole", {})
                .get("agl", {})
                .get("value")
            )  # already in metres in convert_katapult

            # If we already have rich insulator objects, don't add placeholders
            if existing_rich:
                continue

            struct["insulators"] = struct.get("insulators", [])
            for att in attachments_by_scid.get(scid, []):
                # Attachments from the new converter expose *height_m*; fall
                # back to legacy *height* (feet) for backward-compatibility.
                ht_m: float | None = att.get("height_m")
                if ht_m is None and (ht_ft := att.get("height")) is not None:
                    ht_m = ht_ft * _FT_TO_M

                if ht_m is None:
                    continue

                distance_m = None
                if pole_height_m is not None:
                    distance_m = round(pole_height_m - ht_m, 3)
                    if distance_m < 0:
                        distance_m = 0.0
                struct["insulators"].append(
                    {
                        "specIndex": None,
                        "distanceToTop": {"unit": "METRE", "value": distance_m},
                        "onCrossarm": bool(att.get("on_crossarm") or att.get("onCrossarm")),
                    }
                )
    return spida_project


# The _validate_project function and validator setup should remain in fastapi_app.py
# as it manages the global validator instance and schema loading.
# We will need to pass the validator to this router, or make it accessible.
# For now, I'll assume `fastapi_app.py` will handle the validation logic or pass the validator.
# I will remove the _validator and _build_validator related code from here.

router = APIRouter(prefix="/api", tags=["spidacalc"])


@router.get("/spida-debug")
async def spida_debug():
    """Debug endpoint to check if the SPIDA router is working correctly."""
    return {"status": "ok", "message": "SPIDA debug endpoint is working", "route": "/api/spida-debug"}

@router.get("/spida-routes")
async def spida_routes():
    """Return all routes registered on this router for debugging."""
    routes = []
    for route in router.routes:
        routes.append({
            "path": f"/api{route.path}",  # Include the prefix
            "name": route.name,
            "methods": list(route.methods) if hasattr(route, "methods") else []
        })
    return {"routes": routes}


@router.get("/insulator-specs", response_model=InsulatorSpecsResponse)
async def get_insulator_specs():
    """Return the full insulator_specs.json so the React UI can build selects."""
    return insulator_specs


@router.post("/validate", response_model=SpidaValidationResponse)
async def validate_spida(project: SpidaProjectPayload):
    """Validate a posted SPIDAcalc project against the v11 JSON schema."""
    # This validation logic needs access to the _validator from fastapi_app.py
    # For now, I'll put a placeholder. This will be addressed in the next step
    # when modifying fastapi_app.py to pass the validator or make it accessible.
    # For now, I'll assume _validator is accessible (e.g., via a global or dependency injection)
    # and will re-add the original validation logic.
    # Import validator from the main app module
    import sys
    if 'backend.main' in sys.modules:
        _validator = getattr(sys.modules['backend.main'], '_validator', None)
    else:
        _validator = None

    if not _validator:
        return SpidaValidationResponse(valid=True, errors=["Schema validation disabled."]) # Or raise HTTPException
    errors = [e.message for e in _validator.iter_errors(project.dict(__root__=True))]
    if errors:
        return SpidaValidationResponse(valid=False, errors=errors)
    return SpidaValidationResponse(valid=True, errors=[])


@router.post("/spida-import", response_model=SpidaImportResponse)
async def spida_import(
    katapult_file: UploadFile = File(...),
    job_name: str = Form("Untitled Job"),
):
    """Convert a Katapult JSON to SPIDAcalc v11, seed insulators, validate, save.

    The endpoint returns a minimal summary plus a download link for the full file.
    """

    # ------------------------------------------------------------------
    # 1) Read upload into memory – Katapult files are typically < 10 MB
    # ------------------------------------------------------------------
    try:
        raw = await katapult_file.read()
        kata_json = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Invalid JSON upload: {exc}") from exc

    # ------------------------------------------------------------------
    # 2) Derive job_id from filename (drop extension) or UUID
    # ------------------------------------------------------------------
    base_name = Path(katapult_file.filename or "job").stem
    job_id = base_name or uuid.uuid4().hex[:8]

    nodes = kata_json.get("nodes", {}) or kata_json.get("data", {}).get("nodes", {})
    connections = kata_json.get("connections", {}) or kata_json.get("data", {}).get("connections", {})

    # Pass the full kata_json to extract_attachments so it can access photos
    attachments = extract_attachments(kata_json)

    # ------------------------------------------------------------------
    # 3) Build SPIDA project & seed insulators
    # ------------------------------------------------------------------
    try:
        spida_project = convert_katapult_to_spidacalc(kata_json, job_id, job_name)
        
        # Debug logging for attachments
        from pprint import pformat
        print("\n=== Attachments by SCID ===")
        for scid, atts in attachments.items():
            print(f"  SCID {scid}: {len(atts)} attachments")
            if atts:
                print(f"    Sample: {pformat(atts[0])}")
        
        spida_project = _seed_insulators(spida_project, attachments)
        
        # Debug logging for insulators after seeding
        print("\n=== Full SPIDA Project insulators ===")
        for lead in spida_project.get("leads", []):
            for loc in lead.get("locations", []):
                struct = loc["designs"][0]["structure"]
                print(f"  SCID {loc['poleId']}: {len(struct.get('insulators', []))} insulators")
        
        # ------------------------------------------------------------------
        # 3a) Check for unassigned (placeholder) insulators.  If any exist,
        #     we defer file creation so the UI can prompt the user.
        # ------------------------------------------------------------------
        def _has_placeholders(project: Dict[str, Any]) -> bool:
            for lead in project.get("leads", []):
                for loc in lead.get("locations", []):
                    struct = loc.get("designs", [])[0].get("structure", {})
                    for ins in struct.get("insulators", []):
                        # A placeholder has specIndex == None (null in JSON)
                        # or is missing a concrete "size" field.
                        if ins.get("specIndex") is None and not ins.get("size"):
                            return True
            return False

        placeholders_remaining = _has_placeholders(spida_project)

    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc

    # ------------------------------------------------------------------
    # 4) If placeholders remain, skip validation + file write and tell the UI
    # ------------------------------------------------------------------
    if placeholders_remaining:
        structures_summary = []
        for lead in spida_project.get("leads", []):
            for loc in lead.get("locations", []):
                struct = loc.get("designs", [])[0].get("structure", {})
                structures_summary.append({
                    "structureId": str(loc.get("poleId")),
                    "poleNumber": loc.get("label"),
                    "lat": loc.get("mapLocation", {}).get("coordinates", [None, None])[1],
                    "lon": loc.get("mapLocation", {}).get("coordinates", [None, None])[0],
                    "insulators": struct.get("insulators", []),
                })

        return SpidaImportResponse(
            success=True,
            download_available=False,  # user must complete insulator specs first
            filename="",
            download_url="",
            structures=structures_summary,
            job={"id": job_id, "name": job_name},
        )

    # ------------------------------------------------------------------
    # 5) Validate (only if no placeholders)
    # ------------------------------------------------------------------
    import sys
    if 'backend.main' in sys.modules:
        _validator = getattr(sys.modules['backend.main'], '_validator', None)
    else:
        _validator = None

    errors = [e.message for e in _validator.iter_errors(spida_project)]
    if errors:
        return JSONResponse({"error": "Schema validation failed", "errors": errors}, status_code=400)

    # ------------------------------------------------------------------
    # 6) Persist to disk so user can download
    # ------------------------------------------------------------------
    filename = f"{job_id}_for_spidacalc.json"
    file_path = UPLOAD_DIR / filename
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(spida_project, f, indent=2)

    # Build narrow structures summary for UI (no heavy wires array)
    structures_summary = []
    for lead in spida_project.get("leads", []):
        for loc in lead.get("locations", []):
            struct = loc.get("designs", [])[0].get("structure", {})
            structures_summary.append({
                "structureId": str(loc.get("poleId")),
                "poleNumber": loc.get("label"),
                "lat": loc.get("mapLocation", {}).get("coordinates", [None, None])[1],
                "lon": loc.get("mapLocation", {}).get("coordinates", [None, None])[0],
                "insulators": struct.get("insulators", []),
            })

    # ------------------------------------------------------------------
    # 7) Response
    # ------------------------------------------------------------------
    return SpidaImportResponse(
        success=True,
        download_available=True,
        filename=filename,
        download_url=f"/api/download/{filename}",
        structures=structures_summary,
        job={"id": job_id, "name": job_name},
    )


@router.get("/download/{filename}")
async def download_file(filename: str):
    path = UPLOAD_DIR / Path(filename).name  # security – strip subdirs
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type="application/json", filename=path.name)
