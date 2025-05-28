from importlib import import_module

_kata = import_module("cps_tools.core.katapult.converter")

convert_katapult_to_spidacalc = _kata.convert_katapult_to_spidacalc  # type: ignore[attr-defined]
extract_attachments = _kata.extract_attachments  # type: ignore[attr-defined]
insulator_specs = _kata.insulator_specs  # type: ignore[attr-defined]

__all__ = [
    "convert_katapult_to_spidacalc",
    "extract_attachments",
    "insulator_specs",
] 