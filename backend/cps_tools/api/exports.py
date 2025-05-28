"""Generic export endpoints (CSV etc.)."""

from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Body
from fastapi.responses import Response

from .schemas import ExportCsvPayload  # NEW

router = APIRouter()


@router.post("/api/export-csv")
async def export_csv(payload: ExportCsvPayload = Body(...)) -> Response:
    """Return a CSV built from the posted JSON *results* list.

    Expects a JSON body like::

        {
            "results": [...],  # list of dict rows
            "export_type": "all" | "issues"  # optional
        }
    """

    # After validation ``payload`` is already a typed Pydantic object
    results = payload.results
    export_type: str = payload.export_type.lower()

    if export_type == "issues":
        results = [r for r in results if r.get("has_issue")]

    # Build CSV using pandas for convenience
    df = pd.DataFrame(results)
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)

    filename = f"pole_comparison_{'issues' if export_type == 'issues' else 'all'}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    ) 