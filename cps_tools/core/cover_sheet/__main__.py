"""CLI entry-point for the Cover Sheet Tool.

Usage::

    python -m cps_tools.core.cover_sheet path/to/spida.json [--verbose]

The command prints a nicely formatted pole summary table to STDOUT.  Logging
verbosity is controlled via ``--verbose``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .data_extractor import extract_cover_sheet_data
from .formatter import print_cover_sheet

_LOG_FORMAT = "%(levelname)s | %(name)s:%(lineno)d | %(message)s"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:  # noqa: D401 – not part of public API
    parser = argparse.ArgumentParser(prog="cps-cover-sheet", description="Generate cover-sheet summary from a SPIDAcalc JSON file.")
    parser.add_argument("spida_file", type=Path, help="Path to the SPIDAcalc JSON file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:  # noqa: D401 – conventional name
    args = _parse_args(argv)
    logging.basicConfig(format=_LOG_FORMAT, level=logging.DEBUG if args.verbose else logging.INFO)

    if not args.spida_file.exists():
        _LOG = logging.getLogger("cps_tools.cover_sheet")
        _LOG.error("SPIDAcalc file not found: %s", args.spida_file)
        sys.exit(1)

    try:
        json_data = json.loads(args.spida_file.read_text(encoding="utf-8"))
    except Exception as exc:
        _LOG = logging.getLogger("cps_tools.cover_sheet")
        _LOG.error("Failed to read JSON: %s", exc)
        sys.exit(1)

    meta = extract_cover_sheet_data(json_data)
    print_cover_sheet(meta)


if __name__ == "__main__":
    main() 