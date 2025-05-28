"""Data extraction logic for Cover Sheet Tool.

This module contains *pure* functions (no console IO) that parse the
SPIDAcalc JSON payload and return strongly-typed data-structures ready for
formatting.  It replaces the monolithic logic that previously lived inside
``cover_sheet_tool.py``.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from pydantic import BaseModel, Field, validator

__all__ = [
    "PoleSummary",
    "ProjectMeta",
    "extract_cover_sheet_data",
]

_LOG = logging.getLogger(__name__)
_CACHE_PATH = Path.home() / ".cache" / "cps_tools" / "nominatim_cache.json"
_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------------------
# Pydantic models
# --------------------------------------------------------------------------------------


class PoleSummary(BaseModel):
    """Typed representation of a single pole row on the cover-sheet."""

    scid: int = Field(..., alias="SCID")
    station_id: str = Field(..., alias="Station ID")
    address: str = Field("", alias="Address")
    existing_loading_pct: Optional[float] = Field(None, alias="Existing Loading %")
    final_loading_pct: Optional[float] = Field(None, alias="Final Loading %")
    notes: str = Field("", alias="Notes")

    class Config:
        allow_population_by_field_name = True
        frozen = True
        anystr_strip_whitespace = True


class ProjectMeta(BaseModel):
    """High-level project information returned alongside pole summaries."""

    job_number: str = Field(..., alias="Job Number")
    client: str = Field(..., alias="Client")
    date: str = Field(..., alias="Date")
    location: str = Field(..., alias="Location")
    city: str = Field(..., alias="City")
    engineer: str = Field(..., alias="Engineer")
    comments: str = Field(..., alias="Comments")
    poles: List[PoleSummary] = Field(..., alias="Poles")

    class Config:
        allow_population_by_field_name = True
        frozen = True

    @validator("date", pre=True)
    def _fmt_date(cls, v: str) -> str:  # noqa: N805 – pydantic validator signature
        return _format_date(v)


# --------------------------------------------------------------------------------------
# Helper utilities
# --------------------------------------------------------------------------------------


def _format_date(date_str: str) -> str:
    """Return *MM/DD/YYYY* if ``date_str`` is ISO-like, else pass through."""

    try:
        date = datetime.fromisoformat(date_str)
        return date.strftime("%m/%d/%Y")
    except Exception:  # pragma: no cover – best-effort formatting only
        return date_str


def _load_cache() -> Dict[str, str]:
    if not _CACHE_PATH.exists():
        return {}
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: Dict[str, str]) -> None:
    try:
        _CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:  # pragma: no cover – cache failure is non-fatal
        _LOG.debug("Failed to write Nominatim cache: %s", exc)


# Cache kept in module memory to avoid disk hit every call
_GEOCODE_CACHE: Dict[str, str] = _load_cache()


def _reverse_geocode(latitude: float, longitude: float) -> str:
    """Return human-readable address or *Address lookup failed* placeholder."""

    key = f"{latitude:.6f},{longitude:.6f}"
    if key in _GEOCODE_CACHE:
        _LOG.debug("Geocode cache hit for %s", key)
        return _GEOCODE_CACHE[key]

    # Comply with Nominatim 1-request-per-second rule
    time.sleep(1)

    url = (
        "https://nominatim.openstreetmap.org/reverse"
        f"?format=json&lat={latitude}&lon={longitude}"
    )
    headers = {"User-Agent": "CPS-Energy-Tools/1.0"}

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        address = data.get("address", {})
        house_no = address.get("house_number", "")
        road = address.get("road", "")
        city = address.get("city", "") or address.get("town", "") or address.get("village", "")
        full_addr = " ".join(filter(None, [house_no, road]))
        if city:
            full_addr += f", {city}"
        full_addr = full_addr or "Address not found"
    except requests.RequestException as exc:
        _LOG.warning("Reverse-geocode failed (%s) – returning stub address", exc)
        full_addr = "Address lookup failed"

    _GEOCODE_CACHE[key] = full_addr
    _save_cache(_GEOCODE_CACHE)
    return full_addr


# --------------------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------------------


def extract_cover_sheet_data(json_data: Dict[str, Any]) -> ProjectMeta:  # noqa: C901 – keep single entry point
    """Return :class:`ProjectMeta` computed from raw *SPIDAcalc* JSON."""

    if not isinstance(json_data, dict):
        raise TypeError("json_data must be a dict")

    job_number = json_data.get("label", "")
    date = json_data.get("date", "")
    client_data = json_data.get("clientData", {}) if isinstance(json_data.get("clientData", {}), dict) else {}
    location = client_data.get("generalLocation", "")
    address_block = json_data.get("address", {}) if isinstance(json_data.get("address", {}), dict) else {}
    city = address_block.get("city", "")
    engineer = json_data.get("engineer", "")

    poles: List[PoleSummary] = []
    total_plas = 0
    unique_pole_ids: set[str] = set()
    project_address = ""

    leads = json_data.get("leads", []) if isinstance(json_data.get("leads", []), list) else []
    for lead in leads:
        if not isinstance(lead, dict):
            continue
        locations = lead.get("locations", []) if isinstance(lead.get("locations", []), list) else []
        for loc in locations:
            if not isinstance(loc, dict):
                continue
            pole_id = loc.get("label", "")
            unique_pole_ids.add(pole_id)
            existing_loading: Optional[float] = None
            final_loading: Optional[float] = None

            # Geo decode once from first pole
            if not project_address:
                geo = loc.get("geographicCoordinate", {})
                coords = geo.get("coordinates", [])
                if isinstance(coords, list) and len(coords) == 2:
                    longitude, latitude = coords
                    project_address = _reverse_geocode(latitude, longitude)

            # Extract stress values
            for design in loc.get("designs", []):
                if not isinstance(design, dict):
                    continue
                design_label = str(design.get("label", "")).lower()
                analysis_list = design.get("analysis", []) if isinstance(design.get("analysis", []), list) else []
                stress_values: list[float] = []
                for design_case in analysis_list:
                    if not isinstance(design_case, dict):
                        continue
                    for result in design_case.get("results", []):
                        if (
                            isinstance(result, dict)
                            and result.get("analysisType", "").upper() == "STRESS"
                            and result.get("unit", "").upper() == "PERCENT"
                        ):
                            stress_values.append(float(result.get("actual", 0)))
                if not stress_values:
                    continue
                stress_pct = max(stress_values)
                if any(key in design_label for key in ("measured", "existing")):
                    existing_loading = stress_pct
                elif any(key in design_label for key in ("recommended", "final", "proposed")):
                    final_loading = stress_pct
                else:
                    if existing_loading is None:
                        existing_loading = stress_pct
                    else:
                        final_loading = stress_pct

            if "attachments" in loc and isinstance(loc["attachments"], list):
                total_plas += len(loc["attachments"])

            # Extract digits after "-PL"
            import re

            formatted_pole_id = pole_id
            match = re.search(r"\d+-PL(\d+)", pole_id)
            if match:
                formatted_pole_id = match.group(1)

            poles.append(
                PoleSummary(
                    SCID=len(poles) + 1,
                    **{
                        "Station ID": formatted_pole_id,
                        "Address": project_address if len(poles) == 0 else "",
                        "Existing Loading %": existing_loading,
                        "Final Loading %": final_loading,
                    },
                )
            )

    comments = f"{total_plas} PLAs on {len(unique_pole_ids)} poles"
    if project_address:
        location = project_address

    meta = ProjectMeta(
        **{
            "Job Number": job_number,
            "Client": "Charter/Spectrum",
            "Date": date,
            "Location": location,
            "City": city,
            "Engineer": engineer,
            "Comments": comments,
            "Poles": poles,
        }
    )
    return meta 