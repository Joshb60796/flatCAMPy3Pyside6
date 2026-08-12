# FlatCAM unit-aware defaults
#
# Source of truth is millimetres (KiCad-style). Inch values are derived by / 25.4.
#
# Machine profile target: Genmitsu PROVer Ultra 3030-class GRBL mill.
# Tooling assumptions (converted to mm):
#   * Isolation: 0.003" tip, 30° V-bit, 1/8" shank
#       tip diameter = 0.003 * 25.4 = 0.0762 mm  → isotooldia / cnctooldia for iso
#   * Endmill: 1/32" diameter, 1/8" shank, 1/8" length of cut
#       dia = 0.03125 * 25.4 = 0.79375 mm
#       flute length = 0.125 * 25.4 = 3.175 mm  (guidance only; not a CAM param)

from __future__ import annotations

from copy import deepcopy

INCH_PER_MM = 1.0 / 25.4
MM_PER_INCH = 25.4

# --- Physical tool constants (mm) ---
VBIT_TIP_DIA_MM = 0.003 * MM_PER_INCH          # 0.0762 mm (advertised tip)
ENDMILL_DIA_MM = (1.0 / 32.0) * MM_PER_INCH    # 0.79375 mm
ENDMILL_FLUTE_LEN_MM = 0.125 * MM_PER_INCH     # 3.175 mm (1/8" LOC)
SHANK_DIA_MM = 0.125 * MM_PER_INCH             # 3.175 mm (1/8")

# Keys that are lengths, depths, or feeds (scale with units).
# Fractions (overlap), counts, RPM, dwell, strings must NOT be listed.
DIMENSIONAL_OPTION_KEYS = frozenset({
    "gerber_isotooldia",
    "gerber_cutouttooldia",
    "gerber_cutoutmargin",
    "gerber_cutoutgapsize",
    "gerber_noncoppermargin",
    "gerber_bboxmargin",
    "excellon_drillz",
    "excellon_travelz",
    "excellon_feedrate",
    "excellon_toolchangez",
    "excellon_tooldia",
    "geometry_cutz",
    "geometry_travelz",
    "geometry_feedrate",
    "geometry_cnctooldia",
    "geometry_painttooldia",
    "geometry_paintmargin",
    "geometry_depthperpass",
    "cncjob_tooldia",
})

# Unitless / non-scaling keys that must never be multiplied by 25.4
UNITLESS_OPTION_KEYS = frozenset({
    "gerber_isopasses",
    "gerber_isooverlap",
    "gerber_combine_passes",
    "gerber_gaps",
    "geometry_paintoverlap",
    "geometry_pathconnect",
    "geometry_paintcontour",
    "geometry_multidepth",
    "geometry_selectmethod",
    "geometry_paintmethod",
    "excellon_spindlespeed",
    "geometry_spindlespeed",
    "cncjob_dwell",
    "cncjob_dwelltime",
    "units",
})


def _mm_table():
    """Dimensional + project CAM defaults in millimetres."""
    return {
        # --- Project ---
        "units": "MM",

        # --- Gerber / isolation (30° V-bit, 0.003" tip) ---
        "gerber_plot": True,
        "gerber_solid": True,
        "gerber_multicolored": False,
        "gerber_isotooldia": VBIT_TIP_DIA_MM,       # 0.0762 mm
        "gerber_isopasses": 1,
        "gerber_isooverlap": 0.15,                  # fraction
        "gerber_combine_passes": True,
        "gerber_cutouttooldia": ENDMILL_DIA_MM,     # 1/32" endmill
        "gerber_cutoutmargin": 0.2,
        "gerber_cutoutgapsize": 1.0,                # tab gap ~1 mm
        "gerber_gaps": "4",
        "gerber_noncoppermargin": 0.0,
        "gerber_noncopperrounded": False,
        "gerber_bboxmargin": 0.0,
        "gerber_bboxrounded": False,

        # --- Excellon / drill ---
        "excellon_plot": True,
        "excellon_solid": False,
        "excellon_drillz": -1.8,                    # through ~1.6 mm FR4 + breakthrough
        "excellon_travelz": 5.0,
        "excellon_feedrate": 100.0,                 # mm/min plunge
        "excellon_spindlespeed": None,              # blank → M03 only
        "excellon_toolchangez": 15.0,
        "excellon_tooldia": ENDMILL_DIA_MM,         # mill-holes default endmill

        # --- Geometry CNC (isolation follow / paint) ---
        "geometry_plot": True,
        "geometry_cutz": -0.06,                     # shallow isolation depth
        "geometry_travelz": 5.0,
        "geometry_feedrate": 120.0,                 # mm/min XY isolation
        "geometry_spindlespeed": None,
        "geometry_cnctooldia": VBIT_TIP_DIA_MM,     # match isolation V-bit
        "geometry_painttooldia": ENDMILL_DIA_MM,
        "geometry_paintoverlap": 0.15,              # fraction — never scale
        "geometry_paintmargin": 0.1,
        "geometry_selectmethod": "single",
        "geometry_pathconnect": True,
        "geometry_paintcontour": True,
        "geometry_multidepth": False,
        "geometry_depthperpass": 0.2,               # positive step (mm)
        "geometry_paintmethod": "standard",

        # --- CNC job display / export ---
        "cncjob_plot": True,
        "cncjob_tooldia": VBIT_TIP_DIA_MM,
        "cncjob_prepend": "",
        "cncjob_append": "",
        "cncjob_dwell": True,
        "cncjob_dwelltime": 1,

        # Path simplification tolerance for G-code (mm)
        "cncjob_path_tolerance": 0.01,
    }


def scale_dimensional(value, factor):
    if value is None:
        return None
    return value * factor


def defaults_for_units(units="MM"):
    """
    Return a full CAM defaults dict for the given unit system.

    Non-dimensional keys are copied as-is; dimensional keys are scaled
    from the mm source table when units == 'IN'.
    """
    units = (units or "MM").upper()
    base = _mm_table()
    if units == "MM":
        return base

    if units != "IN":
        raise ValueError("Unsupported units: %r (use 'MM' or 'IN')" % units)

    out = {}
    factor = INCH_PER_MM  # mm → in
    for key, val in base.items():
        if key == "units":
            out[key] = "IN"
        elif key in DIMENSIONAL_OPTION_KEYS and isinstance(val, (int, float)):
            out[key] = scale_dimensional(float(val), factor)
        else:
            out[key] = val
    return out


def app_persistent_defaults(units="MM"):
    """
    Full App.defaults dictionary: CAM table + UI/persistence/constants.
    """
    cam = defaults_for_units(units)
    d = {
        "global_mouse_pan_button": 2,
        "serial": 0,
        "stats": {},
        "background_timeout": 300000,
        "verbose_error_level": 0,
        "last_folder": None,
        "def_win_x": 100,
        "def_win_y": 100,
        "def_win_w": 1024,
        "def_win_h": 650,
        "defaults_save_period_ms": 20000,
        "shell_shape": [500, 300],
        "shell_at_startup": False,
        "recent_limit": 10,
        "fit_key": "1",
        "zoom_out_key": "2",
        "zoom_in_key": "3",
        "zoom_ratio": 1.5,
        "point_clipboard_format": "(%.4f, %.4f)",
        "zdownrate": None,
        "excellon_zeros": "L",
        "gerber_use_buffer_for_union": True,
        "cncjob_coordinate_format": "X%.4fY%.4f",
        # Tool metadata (mm always — for docs/tooltips; not scaled in UI)
        "tool_vbit_tip_mm": VBIT_TIP_DIA_MM,
        "tool_vbit_angle_deg": 30.0,
        "tool_endmill_dia_mm": ENDMILL_DIA_MM,
        "tool_endmill_flute_mm": ENDMILL_FLUTE_LEN_MM,
        "tool_shank_dia_mm": SHANK_DIA_MM,
    }
    d.update(cam)
    return d


def project_options_defaults(units="MM"):
    """Project options subset (what App.options starts with before merge)."""
    cam = defaults_for_units(units)
    # Match historical options keys (no pathconnect etc. if not in form —
    # still include for object init).
    keys = [
        "units",
        "gerber_plot", "gerber_solid", "gerber_multicolored",
        "gerber_isotooldia", "gerber_isopasses", "gerber_isooverlap",
        "gerber_combine_passes",
        "gerber_cutouttooldia", "gerber_cutoutmargin", "gerber_cutoutgapsize",
        "gerber_gaps", "gerber_noncoppermargin", "gerber_noncopperrounded",
        "gerber_bboxmargin", "gerber_bboxrounded",
        "excellon_plot", "excellon_solid",
        "excellon_drillz", "excellon_travelz", "excellon_feedrate",
        "excellon_spindlespeed", "excellon_toolchangez", "excellon_tooldia",
        "geometry_plot", "geometry_cutz", "geometry_travelz", "geometry_feedrate",
        "geometry_spindlespeed", "geometry_cnctooldia", "geometry_painttooldia",
        "geometry_paintoverlap", "geometry_paintmargin", "geometry_selectmethod",
        "geometry_pathconnect", "geometry_paintcontour",
        "geometry_multidepth", "geometry_depthperpass", "geometry_paintmethod",
        "cncjob_plot", "cncjob_tooldia", "cncjob_prepend", "cncjob_append",
        "cncjob_dwell", "cncjob_dwelltime",
        "cncjob_path_tolerance",
        "background_timeout", "verbose_error_level",
    ]
    return {k: cam[k] if k in cam else app_persistent_defaults(units).get(k)
            for k in keys if k in cam or k in ("background_timeout", "verbose_error_level")}


def object_option_defaults(kind, units="MM"):
    """
    Defaults for a new FlatCAM object of the given kind, in project units.

    kind: 'gerber' | 'excellon' | 'geometry' | 'cncjob'
    """
    units = (units or "MM").upper()
    cam = defaults_for_units(units)
    prefix = kind + "_"
    out = {"plot": True}
    for key, val in cam.items():
        if key.startswith(prefix):
            out[key[len(prefix):]] = val
    # Object-local names that don't use the prefix pattern cleanly
    if kind == "gerber":
        out.setdefault("combine_passes", cam.get("gerber_combine_passes", True))
    if kind == "excellon":
        out.setdefault("toolchange", False)
    if kind == "geometry":
        out.setdefault("multidepth", cam.get("geometry_multidepth", False))
        out.setdefault("depthperpass", cam.get("geometry_depthperpass", 0.2 if units == "MM" else 0.2 * INCH_PER_MM))
        out.setdefault("paintmethod", cam.get("geometry_paintmethod", "standard"))
        out.setdefault("pathconnect", cam.get("geometry_pathconnect", True))
        out.setdefault("paintcontour", cam.get("geometry_paintcontour", True))
    if kind == "cncjob":
        out.setdefault("append", cam.get("cncjob_append", ""))
        out.setdefault("prepend", cam.get("cncjob_prepend", ""))
        out.setdefault("dwell", cam.get("cncjob_dwell", True))
        out.setdefault("dwelltime", cam.get("cncjob_dwelltime", 1))
    return out


def scale_project_options(options, factor):
    """Scale dimensional keys in an options dict in-place; return options."""
    for key in DIMENSIONAL_OPTION_KEYS:
        if key in options and options[key] is not None:
            try:
                options[key] = float(options[key]) * factor
            except (TypeError, ValueError):
                pass
    return options


def path_tolerance_for_units(units):
    units = (units or "MM").upper()
    if units == "IN":
        return 0.01 * INCH_PER_MM  # ~0.00039 in
    return 0.01  # mm
