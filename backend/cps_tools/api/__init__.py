"""FastAPI routers for cps_tools backend.

Each tool lives in its own module (pole_compare, cover_sheet, etc.).
This package imports and re-exports their `router` objects so callers can easily
include all of them in a single call::

    from backend.cps_tools.api import routers
    app.include_router(routers)
"""

from fastapi import APIRouter

# Dynamically import routers so one failing module doesn't break the whole API
_module_names = [
    "pole_compare",
    "cover_sheet",
    "mrr_process",
    "qc",
    "exports",
    "spida",
]

routers = APIRouter()

for _name in _module_names:
    try:
        _mod = __import__(f"backend.cps_tools.api.{_name}", fromlist=["router"])
        if hasattr(_mod, "router"):
            routers.include_router(getattr(_mod, "router"))
    except Exception as exc:  # noqa: BLE001
        # Log the error and continue – critical for optional tools that have heavy deps
        import logging

        logging.getLogger(__name__).warning("Skipping router %s due to import error: %s", _name, exc)

__all__ = [
    "routers",
]
