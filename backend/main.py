from __future__ import annotations

"""FastAPI micro-service that converts Katapult Pro JSON to SPIDAcalc v11 and
validates it.  It lives alongside the existing Flask app so either server can
be used independently while we migrate endpoints.

Run with::

    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from jsonschema import Draft7Validator, RefResolver

# ---------------------------------------------------------------------------
# App settings (env overrides etc.)
# ---------------------------------------------------------------------------

from cps_tools.settings import get_settings

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

APP_ROOT = Path(__file__).resolve().parents[1] # Project root

# Settings ------------------------------------------------------------------

settings = get_settings()

# Upload directory – default "uploads" unless CPS_UPLOAD_DIR env var provided
UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(exist_ok=True)

SCHEMA_PATH = APP_ROOT / "data" / "spidacalc-v11-schema.json"

# Globals that will hold the loaded schema and compiled validator
SPIDA_SCHEMA: Dict[str, Any] = {}
_validator = None

# ---------------------------------------------------------------------------
# Build JSON-Schema validator with local store so that "$ref": "project.schema" etc.
# resolve to sibling files without requiring HTTP retrieval.
# ---------------------------------------------------------------------------

def _build_validator():
    """Compile a JSON-Schema validator that resolves the four component
    schemas (``project.schema`` etc.) *locally* so no network calls are made.

    The combined wrapper schema (``spidacalc-v11-schema.json``) lives in
    ``data/`` right beside the individual component schema files.  Those
    components are referenced like::

        { "$ref": "project.schema" }

    When a base-URI is supplied (e.g. the directory URI), the reference
    resolves to ``file:///…/data/project.schema``.  Therefore we pre-load the
    component JSON documents under their **full file URI** so the resolver can
    find them instantly and never attempt a remote fetch.
    """

    global _validator, SPIDA_SCHEMA  # noqa: PLW0603

    COMPONENT_FILENAMES = (
        "project.schema",
        "structure.schema",
        "input_assemblies.schema",
        "results.schema",
    )

    try:
        # 1) Read the wrapper schema
        with SCHEMA_PATH.open("r", encoding="utf-8") as f:
            SPIDA_SCHEMA = json.load(f)

        schema_dir = SCHEMA_PATH.parent
        base_uri = schema_dir.as_uri().rstrip("/") + "/"  # ensure trailing slash

        # 2) Build the in-memory store mapping full *file://…* URIs → document
        store: dict[str, dict] = {}
        for fname in COMPONENT_FILENAMES:
            comp_path = schema_dir / fname
            if comp_path.exists():
                with comp_path.open("r", encoding="utf-8") as cf:
                    store[comp_path.as_uri()] = json.load(cf)
            else:
                # Provide a harmless empty schema so resolution still works
                # without a network call.  This weakens validation for that
                # component but avoids hard failure when files are missing.
                store[comp_path.as_uri()] = {}

        resolver = RefResolver(base_uri=base_uri, referrer=SPIDA_SCHEMA, store=store)
        _validator = Draft7Validator(SPIDA_SCHEMA, resolver=resolver)

    except FileNotFoundError:
        print(f"[fastapi_app] WARNING – validation schema not found at {SCHEMA_PATH}.  "
              "Schema validation will be disabled.")
        _validator = None

_build_validator()

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="SPIDAcalc Importer API", version="0.1.0")

@app.get("/health")
async def health_check():
    """Health check endpoint to verify server is running and show registered routes."""
    routes = []
    for route in app.routes:
        if hasattr(route, 'methods') and hasattr(route, 'path'):
            routes.append({"path": route.path, "methods": list(route.methods)})
    return {
        "status": "healthy",
        "message": "CPS Energy Tools API is running",
        "routes": routes
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (React build)
# This assumes your React app is built into 'frontend/dist'
# and 'frontend' is at the same level as 'backend'
STATIC_FILES_DIR = APP_ROOT / "frontend" / "dist"

if STATIC_FILES_DIR.exists():
    app.mount(
        "/assets",
        StaticFiles(directory=STATIC_FILES_DIR / "assets"),
        name="react-assets",
    )
    # Serve static files from the root of the 'dist' directory,
    # including index.html for the root path.
    app.mount(
        "/", StaticFiles(directory=STATIC_FILES_DIR, html=True), name="react-app-root"
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def catch_all(full_path: str):
        """
        Catch-all to serve index.html for client-side routing.
        Ensures that refreshing a page or directly navigating to a
        React route (e.g., /my-page) still loads the React app.
        This should come AFTER specific API routes and static file mounts.
        """
        index_path = STATIC_FILES_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        return {"message": "Frontend not found"}, 404
else:
    print(
        f"[fastapi_app] WARNING – Frontend build directory not found at {STATIC_FILES_DIR}. "
        "Frontend will not be served."
    )

# ---------------------------------------------------------------------------
# Include modular routers from backend package (newly ported endpoints)
# ---------------------------------------------------------------------------

try:
    from cps_tools.api import routers as _tool_routers  # noqa: WPS433 – runtime import to avoid circular

    app.include_router(_tool_routers)
    print("[fastapi_app] Successfully included tool routers")
except ModuleNotFoundError:
    # If the backend package is not on the PYTHONPATH in certain legacy setups,
    # skip inclusion.  This keeps fastapi_app runnable standalone during the
    # transition period.
    print("[fastapi_app] Warning – cps_tools.api package not found; tool routers not included.")
