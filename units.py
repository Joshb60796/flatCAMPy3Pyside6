"""Mixed-unit lengths: store millimetres, remember how the user typed them.

Geometry and CAM math are always millimetres. Each length field keeps a
display unit (IN or MM) so a 0.005 in V-bit and a 1.45 mm cut depth can
sit in the same project. The inch/mm radio is display/export only.
"""
from __future__ import annotations

import re

MM_PER_INCH = 25.4
INCH_PER_MM = 1.0 / 25.4

# Fields users typically know in inches (bits) vs millimetres (board, Z).
PREFERRED_LENGTH_UNITS = {
    "gerber_isotooldia": "IN",
    "gerber_cutouttooldia": "IN",
    "gerber_cutoutmargin": "MM",
    "gerber_cutoutgapsize": "MM",
    "gerber_noncoppermargin": "MM",
    "gerber_bboxmargin": "MM",
    "excellon_drillz": "MM",
    "excellon_travelz": "MM",
    "excellon_feedrate": "MM",
    "excellon_toolchangez": "MM",
    "excellon_tooldia": "IN",
    "excellon_depthperpass": "MM",
    "geometry_cutz": "MM",
    "geometry_travelz": "MM",
    "geometry_feedrate": "MM",
    "geometry_cnctooldia": "IN",
    "geometry_painttooldia": "IN",
    "geometry_paintmargin": "MM",
    "geometry_depthperpass": "MM",
    "cncjob_tooldia": "IN",
    "stock_width": "MM",
    "stock_height": "MM",
    "stock_spacing_x": "MM",
    "stock_spacing_y": "MM",
    "stock_margin": "MM",
    "stock_place_x": "MM",
    "stock_place_y": "MM",
}

_PREFIXES = ("gerber_", "excellon_", "geometry_", "cncjob_", "stock_")

# Unprefixed keys on FlatCAM objects (legacy inch projects).
OBJECT_LENGTH_OPTION_KEYS = (
    "isotooldia", "cutouttooldia", "cutoutmargin", "cutoutgapsize",
    "noncoppermargin", "bboxmargin",
    "drillz", "travelz", "feedrate", "toolchangez", "tooldia", "depthperpass",
    "cutz", "cnctooldia", "painttooldia", "paintmargin",
)

_LEN_RE = re.compile(
    r"^\s*"
    r"(?P<num>[+-]?(?:\d+\s*/\s*\d+|\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
    r"\s*"
    r"(?P<unit>in(?:ch)?|mm|mil|\"|'')?"
    r"\s*$",
    re.IGNORECASE,
)


def normalize_unit(unit):
    if unit is None or str(unit).strip() == "":
        return None
    raw = str(unit).strip().lower()
    if raw in ("in", "inch", "\"", "''"):
        return "IN"
    if raw == "mm":
        return "MM"
    if raw == "mil":
        return "MIL"
    raise ValueError("Unknown length unit: %r" % unit)


def to_mm(value, unit):
    if value is None:
        return None
    value = float(value)
    kind = normalize_unit(unit) or "MM"
    if kind == "IN":
        return value * MM_PER_INCH
    if kind == "MIL":
        return value * 0.0254
    return value


def from_mm(value_mm, unit):
    if value_mm is None:
        return None
    value_mm = float(value_mm)
    kind = normalize_unit(unit) or "MM"
    if kind == "IN":
        return value_mm * INCH_PER_MM
    if kind == "MIL":
        return value_mm / 0.0254
    return value_mm


def _eval_number(text):
    text = text.replace(" ", "")
    if "/" in text:
        num, den = text.split("/", 1)
        return float(num) / float(den)
    return float(text)


def parse_length(text, default_unit="MM"):
    """
    Parse a length string into ``(millimetres, display_unit)``.

    ``display_unit`` is ``IN`` or ``MM`` (mils become inches).
    Bare numbers use ``default_unit``.
    """
    if text is None:
        raise ValueError("Empty length")
    raw = str(text).strip()
    if raw == "":
        raise ValueError("Empty length")
    match = _LEN_RE.match(raw)
    if not match:
        raise ValueError("Cannot parse length: %r" % text)
    value = _eval_number(match.group("num"))
    typed = normalize_unit(match.group("unit"))
    if typed is None:
        typed = normalize_unit(default_unit) or "MM"
    if typed == "MIL":
        return to_mm(value, "MIL"), "IN"
    return to_mm(value, typed), typed


def format_length(value_mm, unit="MM", digits=6):
    """Format a millimetre value in ``unit`` with a suffix, e.g. ``0.005 in``."""
    if value_mm is None:
        return ""
    unit = normalize_unit(unit) or "MM"
    if unit == "MIL":
        unit = "IN"
    shown = from_mm(float(value_mm), unit)
    if shown is None:
        return ""
    text = ("%.*f" % (digits, shown)).rstrip("0").rstrip(".")
    if text in ("", "-", "+"):
        text = "0"
    suffix = "in" if unit == "IN" else "mm"
    return "%s %s" % (text, suffix)


def unit_for_option(options, key, fallback="MM"):
    table = options.get("length_units") if options else None
    if isinstance(table, dict) and key in table:
        try:
            return normalize_unit(table[key]) or preferred_unit_for(key, fallback)
        except ValueError:
            pass
    return preferred_unit_for(key, fallback)


def copy_length_units_for_kind(src_options, kind):
    table = src_options.get("length_units") if src_options else None
    table = table if isinstance(table, dict) else {}
    prefix = str(kind) + "_"
    out = {}
    for key, unit in table.items():
        if key.startswith(prefix):
            out[key[len(prefix):]] = unit
    for full, unit in PREFERRED_LENGTH_UNITS.items():
        if full.startswith(prefix):
            out.setdefault(full[len(prefix):], unit)
    return out


def scale_object_length_options(options, factor, keys):
    if not options or factor == 1:
        return
    for key in keys:
        if key in options and options[key] is not None:
            try:
                options[key] = float(options[key]) * factor
            except (TypeError, ValueError):
                pass


def preferred_unit_for(key, fallback="MM"):
    if not key:
        return fallback
    if key in PREFERRED_LENGTH_UNITS:
        return PREFERRED_LENGTH_UNITS[key]
    for prefix in _PREFIXES:
        prefixed = prefix + key
        if prefixed in PREFERRED_LENGTH_UNITS:
            return PREFERRED_LENGTH_UNITS[prefixed]
    return fallback


def default_length_units():
    return dict(PREFERRED_LENGTH_UNITS)


def looks_like_inch_storage(options):
    """True when saved dimensional values are in inches (pre-storage-mm)."""
    if options is None:
        return False
    try:
        dia = options.get("gerber_cutouttooldia")
        if dia is not None:
            return float(dia) < 0.2
    except (TypeError, ValueError):
        pass
    try:
        width = options.get("stock_width")
        if width is not None:
            return float(width) < 20.0
    except (TypeError, ValueError):
        pass
    return False


def migrate_storage_to_mm(options, dimensional_keys=None):
    """
    Convert an options/defaults dict so dimensional values are millimetres.

    ``units`` is left as the display/export preference. Sets
    ``storage_units`` to ``MM`` so this runs once.
    """
    if options is None:
        return options
    if str(options.get("storage_units", "")).upper() == "MM":
        if "length_units" not in options:
            options["length_units"] = default_length_units()
        return options

    if str(options.get("units", "MM")).upper() == "IN" and looks_like_inch_storage(options):
        if dimensional_keys is None:
            from flatcam_defaults import DIMENSIONAL_OPTION_KEYS
            dimensional_keys = DIMENSIONAL_OPTION_KEYS
        for key in dimensional_keys:
            if key in options and options[key] is not None:
                try:
                    options[key] = float(options[key]) * MM_PER_INCH
                except (TypeError, ValueError):
                    pass
    options["storage_units"] = "MM"
    if "length_units" not in options or not isinstance(options.get("length_units"), dict):
        options["length_units"] = default_length_units()
    return options


def convert_gcode_units(gcode, from_units, to_units):
    """Rewrite G-code coordinates and G20/G21. Does not mutate a job."""
    from gcode_safety import (
        replace_unit_codes,
        rewrite_gcode_xy,
        scale_gcode_z_and_f,
    )

    src = str(from_units or "MM").upper()
    dst = str(to_units or "MM").upper()
    if src == dst or not gcode:
        return gcode
    if src == "MM" and dst == "IN":
        factor = INCH_PER_MM
    elif src == "IN" and dst == "MM":
        factor = MM_PER_INCH
    else:
        raise ValueError("Unsupported unit conversion %s -> %s" % (src, dst))
    out = rewrite_gcode_xy(gcode, lambda x, y: (x * factor, y * factor))
    out = scale_gcode_z_and_f(out, factor)
    return replace_unit_codes(out, dst)
