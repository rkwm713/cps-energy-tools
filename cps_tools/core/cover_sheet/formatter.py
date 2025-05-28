"""Formatting helpers for the Cover Sheet Tool.

Separated from the extraction logic so they can be re-used by both the CLI and
any future FastAPI endpoints.
"""

from __future__ import annotations

import logging
from typing import Iterable

from rich.console import Console
from rich.table import Table

from .data_extractor import PoleSummary, ProjectMeta

__all__ = [
    "render_cover_sheet_table",
    "print_cover_sheet",
]

_LOG = logging.getLogger(__name__)


# --------------------------------------------------------------------------------------
# Rich-based table rendering
# --------------------------------------------------------------------------------------


def _build_table(poles: Iterable[PoleSummary]) -> Table:
    table = Table(title="POLE DATA SUMMARY", show_lines=False, title_style="bold")
    table.add_column("SCID", justify="right")
    table.add_column("Station ID")
    table.add_column("Address")
    table.add_column("Existing Loading %", justify="right")
    table.add_column("Final Loading %", justify="right")
    table.add_column("Notes")

    for pole in poles:
        existing = f"{pole.existing_loading_pct:.1f}%" if pole.existing_loading_pct is not None else "N/A"
        final = f"{pole.final_loading_pct:.1f}%" if pole.final_loading_pct is not None else "N/A"
        table.add_row(
            str(pole.scid),
            pole.station_id,
            pole.address,
            existing,
            final,
            pole.notes,
        )
    return table


def render_cover_sheet_table(meta: ProjectMeta) -> str:
    """Return a *Rich* formatted string table representing the pole data."""

    console = Console(record=True, width=120)
    table = _build_table(meta.poles)
    console.print(table)
    return console.export_text()


def print_cover_sheet(meta: ProjectMeta) -> None:  # noqa: D401 – imperative name for script entry-point
    """Print the cover-sheet summary to STDOUT using `rich` if available."""

    output = render_cover_sheet_table(meta)
    print(output)
    _LOG.debug("Cover-sheet table rendered (%d lines)", output.count("\n")) 