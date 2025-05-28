from __future__ import annotations

"""Pole Comparison Tool – modernised package wrapper.

Provides an import-stable path ``cps_tools.core.pole_compare`` that exposes the
original :class:`PoleComparisonTool` and related dataclasses whilst we finish
carving the real logic into smaller units.

Rationale
---------
The *monolithic* ``pole_comparison_tool.py`` script lives at the project root
(for now).  To avoid a disruptive big-bang move, we load that module at runtime
and re-export all its public names.  Downstream code can immediately switch to::

    from cps_tools.core.pole_compare import PoleComparisonTool

without breaking legacy imports such as ``import pole_comparison_tool`` which
continue to work (the loaded module is inserted into ``sys.modules`` under the
old name).
"""

import importlib.util
import sys
from pathlib import Path

_ORIGINAL_PATH = Path(__file__).resolve().parents[3] / "pole_comparison_tool.py"

_spec = importlib.util.spec_from_file_location("pole_comparison_tool", str(_ORIGINAL_PATH))
if _spec is None or _spec.loader is None:  # pragma: no cover – should never happen
    raise ImportError(f"Unable to locate original pole_comparison_tool.py at {_ORIGINAL_PATH}")

_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)  # type: ignore[arg-type]

# Re-export everything at package level so `from cps_tools.core.pole_compare import PoleComparisonTool` works
globals().update(_module.__dict__)

# Ensure legacy import path keeps returning the same loaded module
sys.modules.setdefault("pole_comparison_tool", _module)

__all__ = [
    "PoleComparisonTool",
    "ProcessedRow",
    "VerificationResult",
] 