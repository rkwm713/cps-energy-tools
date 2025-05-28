from __future__ import annotations

"""SPIDAcalc QC checker – modernised package wrapper.

Loads the legacy ``spidaqc.py`` script at runtime and re-exports its public
symbols (primarily :class:`QCChecker`). New code should import:

    from cps_tools.core.qc import QCChecker

Legacy imports (``import spidaqc`` or ``from spidaqc import QCChecker``) remain
functional because the loaded module is registered back into ``sys.modules``
under its historical name.
"""

import importlib.util
import sys
from pathlib import Path

_ORIGINAL_PATH = Path(__file__).resolve().parents[3] / "spidaqc.py"

_spec = importlib.util.spec_from_file_location("spidaqc", str(_ORIGINAL_PATH))
if _spec is None or _spec.loader is None:  # pragma: no cover
    raise ImportError(f"Unable to locate spidaqc.py at {_ORIGINAL_PATH}")

_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[arg-type]

globals().update(_mod.__dict__)

# Inject back under original name for compatibility
sys.modules.setdefault("spidaqc", _mod)

__all__ = [
    "QCChecker",
] 