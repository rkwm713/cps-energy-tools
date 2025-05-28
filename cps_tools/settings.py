from __future__ import annotations

"""Application settings module powered by **Pydantic**.

All configuration values can be overridden via environment variables that share
an ``CPS_`` prefix.  For instance::

    export CPS_UPLOAD_DIR=/var/lib/cps-energy-tools/uploads

The helper :func:`get_settings` returns a cached instance so modules can simply::

    from cps_tools.settings import get_settings

    settings = get_settings()
    print(settings.upload_dir)
"""

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Runtime configuration values for the CPS-Energy-Tools backend."""

    # ------------------------------------------------------------------
    # General ----------------------------------------------------------------
    # ------------------------------------------------------------------
    app_name: str = Field("cps-energy-tools", description="Human-readable app title")
    debug: bool = Field(False, description="Enable verbose debug logging & features")

    # ------------------------------------------------------------------
    # File paths -------------------------------------------------------------
    # ------------------------------------------------------------------
    # Where uploaded & generated files are stored.  The directory will be created
    # automatically at runtime if it doesn't exist.
    upload_dir: Path = Field("uploads", description="Directory for user uploads")

    # ------------------------------------------------------------------
    # Web / API --------------------------------------------------------------
    # ------------------------------------------------------------------
    cors_origins: List[str] = Field(default_factory=lambda: ["*"], description="CORS origins")
    max_upload_size_mb: int = Field(50, description="Maximum allowed upload size in MB")

    class Config:
        env_prefix = "CPS_"
        case_sensitive = False
        env_file = ".env"

    # ------------------------------------------------------------------
    # Validators -------------------------------------------------------------
    # ------------------------------------------------------------------
    @validator("upload_dir", pre=True)
    def _ensure_path(cls, v):  # noqa: D401, N805
        """Convert strings → ``Path`` and create the directory if necessary."""
        p = Path(v) if not isinstance(v, Path) else v
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception:  # noqa: BLE001
            # Fail silently – FastAPI will raise later when trying to write.
            pass
        return p


@lru_cache(maxsize=1)
def get_settings() -> Settings:  # noqa: D401
    """Return a cached :class:`Settings` instance (singleton)."""

    return Settings() 