from __future__ import annotations

"""Pydantic models shared by cps_tools FastAPI routers.

These schemas are intentionally *light* – we only describe the public
contract we actually rely on inside the front-end.  In most cases the
payloads are dictionaries whose exact shape is produced by lower-level
helper classes (e.g. ``PoleComparisonTool``).  For those we expose a
``Dict[str, Any]`` field so that validation is still performed but we do
not have to duplicate the full specification.

Keeping the models in a single module avoids circular imports between
routers while making the typing readily available across the project.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Python ≥ 3.10 has Literal in the standard library typing module
from typing import Literal

# ---------------------------------------------------------------------------
# Pole comparison
# ---------------------------------------------------------------------------


class PoleComparisonSummary(BaseModel):
    """High-level statistics returned by the pole comparison tool."""

    total_poles: int = Field(..., ge=0, description="Total number of poles processed")
    poles_with_issues: int = Field(..., ge=0, description="Number of poles that breached threshold")
    threshold: float = Field(..., ge=0, description="Distance threshold given in feet")


class PoleComparisonResponse(BaseModel):
    """Response body of ``POST /api/pole-comparison``."""

    results: List[Dict[str, Any]]
    issues: List[Dict[str, Any]]
    verification: Dict[str, Any]
    summary: PoleComparisonSummary


# ---------------------------------------------------------------------------
# Cover-sheet extractor
# ---------------------------------------------------------------------------


class CoverSheetResponse(BaseModel):
    """Arbitrary JSON fragment consumed directly by the front-end."""

    __root__: Dict[str, Any]

    # Allow dot-notation access to the wrapped dict
    def __getattr__(self, item):  # pragma: no cover – convenience only
        return getattr(self.__root__, item)


# ---------------------------------------------------------------------------
# SPIDAcalc QC checker
# ---------------------------------------------------------------------------


class PoleLocation(BaseModel):
    id: str
    lat: Optional[float] = None
    lon: Optional[float] = None


class QCResponse(BaseModel):
    issues_by_pole: Dict[str, List[Any]]
    issues_count: int
    poles: List[PoleLocation]


# ---------------------------------------------------------------------------
# MRR processor
# ---------------------------------------------------------------------------


class MRRProcessResponse(BaseModel):
    """Response body of ``POST /api/mrr-process``."""

    success: bool
    message: str
    summary: Optional[Dict[str, Any]] = None
    preview: Optional[Dict[str, Any]] = None
    download_available: bool
    download_url: Optional[str] = None


# ---------------------------------------------------------------------------
# CSV export – request payload only; response is raw CSV text
# ---------------------------------------------------------------------------


class ExportCsvPayload(BaseModel):
    results: List[Dict[str, Any]]
    export_type: Literal["all", "issues"] = "all"


# ---------------------------------------------------------------------------
# SPIDAcalc Import / Validation
# ---------------------------------------------------------------------------


class InsulatorSpecsResponse(BaseModel):
    """Response body for ``GET /api/insulator-specs``."""

    __root__: List[Dict[str, Any]]


class SpidaProjectPayload(BaseModel):
    """Request body for ``POST /api/validate``."""

    __root__: Dict[str, Any]


class SpidaValidationResponse(BaseModel):
    """Response body for ``POST /api/validate``."""

    valid: bool
    errors: List[str]


class SpidaImportStructureSummary(BaseModel):
    """Summary of a single structure in SPIDAcalc import response."""

    structureId: str
    poleNumber: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    insulators: List[Dict[str, Any]]


class SpidaImportJobSummary(BaseModel):
    """Summary of the job in SPIDAcalc import response."""

    id: str
    name: str


class SpidaImportResponse(BaseModel):
    """Response body for ``POST /api/spida-import``."""

    success: bool
    download_available: bool
    filename: str
    download_url: str
    structures: List[SpidaImportStructureSummary]
    job: SpidaImportJobSummary
