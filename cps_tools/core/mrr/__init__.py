"""MRR Tool package – modernised wrapper.

This package now uses the final_code_output.py implementation as the primary processor.
The module exposes a stable import path for the MRR tool functionality.
"""

from __future__ import annotations

from types import ModuleType

from .final_code_output import process  # noqa: F401 – re-export

__all__ = [
    "process",
]

# ---------------------------------------------------------------------------
# Make the FileProcessorGUI class available for direct import if needed
# ---------------------------------------------------------------------------
from .final_code_output import FileProcessorGUI  # noqa: F401

# ---------------------------------------------------------------------------
# Legacy dynamic import so that ``import MattsMRR`` remains functional
# ---------------------------------------------------------------------------

import importlib.util
import sys
from pathlib import Path

# First try to use final_code_output.py as MattsMRR for backward compatibility
_MODULE_PATH = Path(__file__).resolve().parent / "final_code_output.py"

if _MODULE_PATH.exists():
    _spec = importlib.util.spec_from_file_location("MattsMRR", str(_MODULE_PATH))
    if _spec and _spec.loader:
        _legacy_mod: ModuleType = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_legacy_mod)  # type: ignore[arg-type]
        sys.modules.setdefault("MattsMRR", _legacy_mod)
