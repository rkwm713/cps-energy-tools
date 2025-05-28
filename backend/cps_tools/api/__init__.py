"""FastAPI routers for cps_tools backend.

Each tool lives in its own module (pole_compare, cover_sheet, etc.).
This package imports and re-exports their `router` objects so callers can easily
include all of them in a single call::

    from backend.cps_tools.api import routers
    app.include_router(routers)
"""

from fastapi import APIRouter

# Individual routers ---------------------------------------------------------

from . import pole_compare  # noqa: E402
from . import cover_sheet  # noqa: E402
from . import mrr_process  # noqa: E402
from . import qc  # noqa: E402
from . import exports  # noqa: E402
from . import spida  # noqa: E402

routers = APIRouter()
routers.include_router(pole_compare.router)
routers.include_router(cover_sheet.router)
routers.include_router(mrr_process.router)
routers.include_router(qc.router)
routers.include_router(exports.router)
routers.include_router(spida.router)

__all__ = [
    "routers",
]
