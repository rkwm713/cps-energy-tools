"""Headless processor for the *MRR Tool*.

This module exposes a single :func:`process` entry-point that can be called
from the CLI, FastAPI routes or tests without importing any Tkinter GUI code.

Internally we *reuse* the heavy-lifting logic that still lives in the legacy
``MattsMRR.py`` script by instantiating its ``FileProcessorGUI`` class (which
contains all helper methods) in a headless context (Tkinter is stubbed when
not available).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from .excel_writer import write_formatted_excel

__all__ = [
    "process",
]

_LOG = logging.getLogger(__name__)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def process(
    job_json: Path,
    geojson: Path | None = None,
    *,
    output: Path | None = None,
) -> Tuple[Path, Dict[str, Any]]:
    """Generate an Excel report from *SPIDAcalc* job + geo data.

    Parameters
    ----------
    job_json:
        Path to the *Job* JSON file exported from SPIDAcalc.
    geojson:
        Optional GeoJSON file containing spatial data used by some routines.
    output:
        Destination path for the generated ``.xlsx`` workbook.  If *None*, the
        file will be written next to *job_json* with a ``_Python_Output.xlsx``
        suffix (auto-versioned if the name already exists).

    Returns
    -------
    Tuple[Path, Dict[str, Any]]
        ``(output_path, stats)`` where *stats* currently contains a row count
        and can be extended later.
    """

    job_json = Path(job_json).expanduser().resolve()
    if not job_json.exists():
        raise FileNotFoundError(job_json)

    geojson_path: Optional[Path] = None
    if geojson is not None:
        geojson_path = Path(geojson).expanduser().resolve()
        if not geojson_path.exists():
            _LOG.warning("GeoJSON path not found – continuing without: %s", geojson_path)
            geojson_path = None

    # --------------------------------------------------------------
    # Import legacy implementation on demand – avoids heavy startup
    # cost when users only run the headless API.
    # --------------------------------------------------------------
    from scripts.MattsMRR import FileProcessorGUI as GuiCls
    gui_instance = GuiCls()  # tk stubs are active in headless mode

    job_data = _load_json(job_json)
    geo_data = _load_json(geojson_path) if geojson_path else None

    _LOG.debug("Running MattsMRR.process_data() …")
    df: pd.DataFrame = gui_instance.process_data(job_data, geo_data)  # type: ignore[arg-type]

    if df.empty:
        raise RuntimeError("MRR processor produced an empty DataFrame – nothing to export")

    if output is None:
        output_base = job_json.with_suffix("")
        output_base = output_base.with_name(output_base.name + "_Python_Output.xlsx")
        output = output_base
        version = 2
        stem = output_base.stem
        while output.exists():
            output = output_base.with_name(f"{stem}_v{version}.xlsx")
            version += 1

    _LOG.info("Writing Excel report to %s (%d rows, %d cols)", output, len(df), len(df.columns))
    write_formatted_excel(output, df, job_data) # Pass job_data to the formatted writer

    stats: Dict[str, Any] = {
        "rows": len(df),
        "columns": len(df.columns),
    }
    return output, stats
