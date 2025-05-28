from __future__ import annotations

"""Cover-Sheet extractor package.

Preferred usage::

    from cps_tools.core.cover_sheet import extract_cover_sheet_data, print_cover_sheet

The implementation now lives in dedicated sub-modules (:pymod:`.data_extractor`
and :pymod:`.formatter`).  For backwards compatibility we *also* lazy-load the
historical root-level ``cover_sheet_tool.py`` and expose its public names so
legacy imports continue working.
"""

from types import ModuleType

# --------------------------------------------------------------------------------------
# Re-export modern API
# --------------------------------------------------------------------------------------

from .data_extractor import ProjectMeta, PoleSummary, extract_cover_sheet_data  # noqa: F401 – re-export
from .formatter import print_cover_sheet  # noqa: F401 – re-export

__all__ = [
    "extract_cover_sheet_data",
    "print_cover_sheet",
    "PoleSummary",
    "ProjectMeta",
]

# --------------------------------------------------------------------------------------
# Legacy dynamic import (kept until the root-level script is deleted)
# --------------------------------------------------------------------------------------

import importlib.util
import sys
from pathlib import Path

_ORIGINAL_PATH = Path(__file__).resolve().parents[3] / "cover_sheet_tool.py"

if _ORIGINAL_PATH.exists():
    _spec = importlib.util.spec_from_file_location("cover_sheet_tool", str(_ORIGINAL_PATH))
    if _spec and _spec.loader:
        _legacy_mod: ModuleType = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_legacy_mod)  # type: ignore[arg-type]

        # Re-export *missing* attributes that we haven't implemented yet in the new API
        globals().update(
            {
                name: obj
                for name, obj in _legacy_mod.__dict__.items()
                if name not in globals()
            }
        )

        # Ensure ``import cover_sheet_tool`` keeps returning the same module
        sys.modules.setdefault("cover_sheet_tool", _legacy_mod) 