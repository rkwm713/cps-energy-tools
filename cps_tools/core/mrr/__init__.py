"""MRR Tool package – modernised wrapper.

The heavy-lifting logic still resides in the historical ``MattsMRR.py`` script
which ships alongside the repository root.  This package exposes a stable
import path while we migrate towards properly decomposed modules.
"""

from __future__ import annotations

from types import ModuleType

from .processor import process  # noqa: F401 – re-export

__all__ = [
    "process",
]

# ---------------------------------------------------------------------------
# Legacy dynamic import so that ``import MattsMRR`` remains functional and all
# existing helper classes (e.g. *FileProcessorGUI*) continue to work.
# ---------------------------------------------------------------------------

import importlib.util
import sys
from pathlib import Path

_ORIGINAL_PATH = Path(__file__).resolve().parents[3] / "MattsMRR.py"

if _ORIGINAL_PATH.exists():
    _spec = importlib.util.spec_from_file_location("MattsMRR", str(_ORIGINAL_PATH))
    if _spec and _spec.loader:
        _legacy_mod: ModuleType = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_legacy_mod)  # type: ignore[arg-type]
        sys.modules.setdefault("MattsMRR", _legacy_mod) 