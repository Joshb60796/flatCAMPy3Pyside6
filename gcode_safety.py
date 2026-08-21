"""
Hardware-safety analysis and helpers for FlatCAM G-code.

Convention (FlatCAM / typical CNC):
  * Z+ is up, Z=0 is the stock surface, Z- is into the material.
  * G00 is a rapid (must never drag the tool through stock).
  * G01 is a feed move (plunge / cut).

This module is imported by camlib and by the test suite. It must not
import camlib (no circular import).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


# Coordinate words are formatted to 4 decimals in FlatCAM; allow a little slack.
COORD_EPS = 5.0e-5

# G-code word: letter + number (optional exponent).
_WORD_RE = re.compile(
    r"([A-Za-z])\s*([+\-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+\-]?\d+)?)"
)
_PAREN_COMMENT_RE = re.compile(r"\([^)]*\)")
_M3M4_RE = re.compile(r"^\s*[mM]0*[34](?!\d)")
_G4_RE = re.compile(r"^\s*[gG]0*4\b")
class GCodeSafetyError(ValueError):
    """Raised when parameters or generated G-code could damage a machine."""


def strip_comments(line: str) -> str:
    """Remove ``(comment)`` and ``; comment`` tails."""
    line = _PAREN_COMMENT_RE.sub("", line)
    if ";" in line:
        line = line[: line.index(";")]
    return line


def parse_gcode_words(line: str) -> Dict[str, float]:
    """
    Parse one G-code line into ``{'G': 1.0, 'X': 1.2, ...}``.

    Comments are ignored. Letter keys are upper-case. Invalid numbers
    are skipped rather than raising, so a bad comment cannot abort a job.
    """
    command: Dict[str, float] = {}
    cleaned = strip_comments(line)
    for match in _WORD_RE.finditer(cleaned):
        letter = match.group(1).upper()
        raw = match.group(2).replace(" ", "")
        try:
            command[letter] = float(raw)
        except ValueError:
            continue
    return command


def normalize_cut_z(z_cut):
    """
    Cut Z is below the stock surface (Z=0). A positive value is a
    cutting *depth* (``0.1`` mm → ``Z-0.1``). Already-negative values
    and zero are left unchanged.
    """
    if z_cut is None:
        return None
    try:
        from decimal import Decimal
        if isinstance(z_cut, Decimal):
            return -z_cut if z_cut > 0 else z_cut
    except Exception:
        pass
    value = float(z_cut)
    if value > 0:
        return -value
    return z_cut


def validate_cnc_parameters(
    z_cut,
    z_move,
    feedrate,
    toolchangez=None,
    spindlespeed=None,
    units=None,
):
    """
    Reject parameter combinations that make safe G-code impossible.

    Raises
    ------
    GCodeSafetyError
    """
    errors: List[str] = []

    if units is not None and str(units).upper() not in ("IN", "MM"):
        errors.append("Units must be IN or MM, got %r" % (units,))

    try:
        z_cut_f = float(z_cut)
        z_move_f = float(z_move)
        feed_f = float(feedrate)
    except (TypeError, ValueError):
        raise GCodeSafetyError(
            "Cut Z, travel Z and feed rate must be finite numbers"
        )

    if not math.isfinite(z_cut_f) or not math.isfinite(z_move_f):
        errors.append("Cut Z and travel Z must be finite")
    if not math.isfinite(feed_f) or feed_f <= 0:
        errors.append("Feed rate must be a finite number > 0 (got %r)" % (feedrate,))

    if math.isfinite(z_move_f) and z_move_f <= 0:
        errors.append(
            "Travel Z must be above the stock surface (z_move > 0), got %s" % z_move_f
        )

    if math.isfinite(z_cut_f) and math.isfinite(z_move_f) and z_cut_f >= z_move_f:
        errors.append(
            "Cut Z (%s) must be below travel Z (%s)" % (z_cut_f, z_move_f)
        )

    if toolchangez is not None:
        try:
            tcz = float(toolchangez)
        except (TypeError, ValueError):
            errors.append("Tool-change Z must be a number")
        else:
            if not math.isfinite(tcz):
                errors.append("Tool-change Z must be finite")
            elif math.isfinite(z_move_f) and tcz + COORD_EPS < z_move_f:
                errors.append(
                    "Tool-change Z (%s) must be at or above travel Z (%s)"
                    % (tcz, z_move_f)
                )

    if spindlespeed is not None:
        try:
            rpm = float(spindlespeed)
        except (TypeError, ValueError):
            errors.append("Spindle speed must be a number or None")
        else:
            if not math.isfinite(rpm) or rpm <= 0:
                errors.append(
                    "Spindle speed must be > 0 when set (got %r)" % (spindlespeed,)
                )

    if errors:
        raise GCodeSafetyError("; ".join(errors))


@dataclass
class MachineState:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    feed: Optional[float] = None
    spindle_on: bool = False
    spindle_speed: Optional[float] = None
    motion: int = 0  # last G0/G1/G2/G3
    abs_mode: bool = True
    units: Optional[str] = None  # "IN" or "MM"
    feed_per_min: bool = True


@dataclass
class SimReport:
    min_z: float = math.inf
    max_z: float = -math.inf
    min_x: float = math.inf
    max_x: float = -math.inf
    min_y: float = math.inf
    max_y: float = -math.inf
    rapid_xy_min_z: float = math.inf
    spindle_on_at_end: bool = False
    z_at_end: float = 0.0
    xy_at_end: Tuple[float, float] = (0.0, 0.0)
    units: Optional[str] = None
    feed_moves: int = 0
    rapid_moves: int = 0
    plunges: int = 0
    z_values_cut: List[float] = field(default_factory=list)
    xy_rapids: List[Tuple[float, float, float]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def _dest_xyz(state: MachineState, words: Dict[str, float]) -> Tuple[float, float, float]:
    dx = words["X"] if "X" in words else (0.0 if not state.abs_mode else state.x)
    dy = words["Y"] if "Y" in words else (0.0 if not state.abs_mode else state.y)
    dz = words["Z"] if "Z" in words else (0.0 if not state.abs_mode else state.z)
    if state.abs_mode:
        x = words["X"] if "X" in words else state.x
        y = words["Y"] if "Y" in words else state.y
        z = words["Z"] if "Z" in words else state.z
        return x, y, z
    return state.x + dx, state.y + dy, state.z + dz


def simulate_gcode(
    gcode: str,
    z_cut: float,
    z_move: float,
    *,
    assume_start_z: float = 0.0,
    require_spindle_before_cut: bool = True,
    require_units: bool = True,
    require_absolute: bool = True,
    require_safe_end: bool = True,
) -> SimReport:
    """
    Walk G-code like a machine would and raise :class:`GCodeSafetyError`
    on motion that can break a bit, crash the spindle, or gouge the bed.
    """
    z_cut_f = float(z_cut)
    z_move_f = float(z_move)
    state = MachineState(z=assume_start_z)
    report = SimReport()
    saw_motion = False
    saw_xy = False
    saw_g90 = False

    def record_pos():
        report.min_z = min(report.min_z, state.z)
        report.max_z = max(report.max_z, state.z)
        report.min_x = min(report.min_x, state.x)
        report.max_x = max(report.max_x, state.x)
        report.min_y = min(report.min_y, state.y)
        report.max_y = max(report.max_y, state.y)

    record_pos()

    for lineno, raw in enumerate(gcode.splitlines(), start=1):
        words = parse_gcode_words(raw)
        if not words:
            continue

        if "F" in words:
            state.feed = words["F"]
            if state.feed is not None and state.feed <= 0:
                raise GCodeSafetyError(
                    "Line %d: feed rate must be > 0 (F%s)" % (lineno, state.feed)
                )

        if "S" in words:
            state.spindle_speed = words["S"]

        if "M" in words:
            m = int(round(words["M"]))
            if m in (3, 4):
                state.spindle_on = True
            elif m == 5:
                state.spindle_on = False

        if "G" in words:
            g = int(round(words["G"]))
            if g == 20:
                state.units = "IN"
                continue
            if g == 21:
                state.units = "MM"
                continue
            if g == 90:
                state.abs_mode = True
                saw_g90 = True
                continue
            if g == 91:
                state.abs_mode = False
                continue
            if g == 94:
                state.feed_per_min = True
                continue
            if g == 4:
                continue
            if g in (0, 1, 2, 3):
                state.motion = g

        has_xyz = any(k in words for k in ("X", "Y", "Z"))
        if not has_xyz:
            continue

        nx, ny, nz = _dest_xyz(state, words)
        for name, val in (("X", nx), ("Y", ny), ("Z", nz)):
            if not math.isfinite(val):
                raise GCodeSafetyError(
                    "Line %d: non-finite %s coordinate %r" % (lineno, name, val)
                )

        moving_xy = abs(nx - state.x) > COORD_EPS or abs(ny - state.y) > COORD_EPS
        moving_z = abs(nz - state.z) > COORD_EPS
        is_rapid = state.motion == 0

        if moving_xy or moving_z:
            saw_motion = True
            if require_units and state.units is None:
                raise GCodeSafetyError(
                    "Line %d: motion before units (G20/G21) are set" % lineno
                )
            if require_absolute and not saw_g90:
                raise GCodeSafetyError(
                    "Line %d: motion before absolute mode (G90) is set" % lineno
                )

        if nz < z_cut_f - COORD_EPS:
            raise GCodeSafetyError(
                "Line %d: Z=%.6f is below commanded cut depth %.6f"
                % (lineno, nz, z_cut_f)
            )

        if is_rapid and moving_z and nz < state.z - COORD_EPS:
            # Rapid down is only allowed while staying at/above travel height.
            if nz < z_move_f - COORD_EPS:
                raise GCodeSafetyError(
                    "Line %d: rapid Z descent to %.6f is below travel Z %.6f"
                    % (lineno, nz, z_move_f)
                )

        if is_rapid and moving_xy:
            z_during = min(state.z, nz) if moving_z else state.z
            report.rapid_xy_min_z = min(report.rapid_xy_min_z, z_during)
            report.xy_rapids.append((nx, ny, z_during))
            if z_during < z_move_f - COORD_EPS:
                raise GCodeSafetyError(
                    "Line %d: rapid XY while Z=%.6f is below travel Z %.6f "
                    "(would gouge or snap the tool)"
                    % (lineno, z_during, z_move_f)
                )
            if not saw_xy and z_during <= 0:
                # Reached when travel Z is 0 (already rejected by
                # validate_cnc_parameters) or the first XY happens on the
                # stock surface after a G00 Z0.
                raise GCodeSafetyError(
                    "Line %d: first XY move happens at Z=%.6f (must raise first)"
                    % (lineno, z_during)
                )
            saw_xy = True

        if (not is_rapid) and moving_z and nz < state.z - COORD_EPS:
            if state.feed is None or state.feed <= 0:
                raise GCodeSafetyError(
                    "Line %d: plunge without a positive feed rate" % lineno
                )
            if require_spindle_before_cut and nz < -COORD_EPS and not state.spindle_on:
                raise GCodeSafetyError(
                    "Line %d: plunging into material with spindle off" % lineno
                )
            report.plunges += 1
            report.z_values_cut.append(nz)

        if is_rapid:
            report.rapid_moves += 1
        else:
            report.feed_moves += 1

        state.x, state.y, state.z = nx, ny, nz
        record_pos()

    report.spindle_on_at_end = state.spindle_on
    report.z_at_end = state.z
    report.xy_at_end = (state.x, state.y)
    report.units = state.units

    if saw_motion and require_safe_end:
        if state.spindle_on:
            raise GCodeSafetyError("Program ends with spindle still running (missing M05)")
        if state.z < z_move_f - COORD_EPS:
            raise GCodeSafetyError(
                "Program ends at Z=%.6f; tool must retract to travel Z %.6f"
                % (state.z, z_move_f)
            )

    return report


def assert_safe_gcode(gcode: str, z_cut, z_move, **kwargs) -> SimReport:
    """Simulate and return the report, or raise :class:`GCodeSafetyError`."""
    if gcode is None or not str(gcode).strip():
        raise GCodeSafetyError("Refusing to export empty G-code")
    return simulate_gcode(str(gcode), float(z_cut), float(z_move), **kwargs)


def insert_dwell_after_spindle(gcode: str, dwelltime) -> str:
    """
    Insert ``G4 P<dwelltime>`` after each M03/M04 that is not already
    followed by a dwell. Mirrors (and slightly hardens) the historical
    ``dwell_generator`` behaviour.
    """
    try:
        dwell_f = float(dwelltime)
    except (TypeError, ValueError):
        return gcode
    if dwell_f <= 0:
        return gcode

    lines = gcode.splitlines(keepends=True)
    if not lines:
        return gcode

    out: List[str] = []
    pending = False
    dwell_line = "G4 P%s\n" % dwelltime
    for line in lines:
        if pending:
            pending = False
            out.append(dwell_line)
            if _G4_RE.search(strip_comments(line)):
                continue
            out.append(line)
            continue
        out.append(line)
        if _M3M4_RE.search(strip_comments(line)):
            pending = True
    if pending:
        out.append(dwell_line)
    return "".join(out)


def split_standard_footer(gcode: str) -> Tuple[str, str]:
    """
    Peel a FlatCAM-style footer off the end:

        G00 Z<travel>
        G00 X0Y0
        M05

    Any of the three trailing lines may be present. Returns ``(body, footer)``.
    """
    lines = gcode.splitlines(keepends=True)
    footer: List[str] = []

    def pop_blank():
        while lines and not lines[-1].strip():
            footer.insert(0, lines.pop())

    pop_blank()
    if lines:
        w = parse_gcode_words(lines[-1])
        if int(round(w.get("M", -1))) == 5 and set(w.keys()) <= {"M"}:
            footer.insert(0, lines.pop())
            pop_blank()

    if lines:
        w = parse_gcode_words(lines[-1])
        if (
            int(round(w.get("G", -1))) == 0
            and "X" in w
            and "Y" in w
            and abs(w.get("X", 1)) <= COORD_EPS
            and abs(w.get("Y", 1)) <= COORD_EPS
            and "Z" not in w
        ):
            footer.insert(0, lines.pop())
            pop_blank()

    if lines:
        w = parse_gcode_words(lines[-1])
        if int(round(w.get("G", -1))) == 0 and "Z" in w and "X" not in w and "Y" not in w:
            footer.insert(0, lines.pop())

    return "".join(lines), "".join(footer)


def rewrite_gcode_xy(
    gcode: str,
    transform_xy: Callable[[float, float], Tuple[float, float]],
    *,
    preserve_home_footer: bool = True,
    coord_fmt: str = "X%.4fY%.4f",
) -> str:
    """
    Apply ``transform_xy(x, y) -> (x', y')`` to every motion line.

    Modal X-only / Y-only words are expanded to both axes after the
    transform so rotations cannot drop a needed coordinate. I/J offsets
    are rewritten as the transformed centre minus the transformed start.

    The standard end-of-job ``G00 X0Y0`` home is left alone when
    ``preserve_home_footer`` is true.
    """
    body, footer = (split_standard_footer(gcode) if preserve_home_footer
                    else (gcode, ""))
    # Track *source* coordinates so modal X/Y (and I/J centres) stay in
    # the original space; only the emitted words are transformed.
    ox = 0.0
    oy = 0.0
    out: List[str] = []
    for raw in body.splitlines(keepends=True):
        words = parse_gcode_words(raw)
        if "X" not in words and "Y" not in words:
            out.append(raw)
            continue
        old_ox, old_oy = ox, oy
        if "X" in words:
            ox = words["X"]
        if "Y" in words:
            oy = words["Y"]
        nx, ny = transform_xy(ox, oy)
        words["X"] = nx
        words["Y"] = ny
        if "I" in words or "J" in words:
            i = words.get("I", 0.0)
            j = words.get("J", 0.0)
            nsx, nsy = transform_xy(old_ox, old_oy)
            cx, cy = transform_xy(old_ox + i, old_oy + j)
            words["I"] = cx - nsx
            words["J"] = cy - nsy
        out.append(_reconstruct_line(raw, words, coord_fmt))
    return "".join(out) + footer


def _reconstruct_line(original: str, words: Dict[str, float], coord_fmt: str) -> str:
    """Rebuild a motion line, preserving newline style."""
    nl = "\n"
    if original.endswith("\r\n"):
        nl = "\r\n"
    elif original.endswith("\n"):
        nl = "\n"
    else:
        nl = ""

    # Keep leading whitespace.
    lead = original[: len(original) - len(original.lstrip())] if original.strip() else ""

    ordered: List[str] = []
    if "G" in words:
        g = words["G"]
        gi = int(round(g))
        if abs(g - gi) < 1e-12 and gi < 10:
            ordered.append("G0%d" % gi)
        elif abs(g - gi) < 1e-12:
            ordered.append("G%d" % gi)
        else:
            ordered.append("G%s" % g)
    if "X" in words or "Y" in words:
        ordered.append(coord_fmt % (words.get("X", 0.0), words.get("Y", 0.0)))
    for key in words:
        if key in ("G", "X", "Y"):
            continue
        val = words[key]
        if key == "Z":
            ordered.append("Z%.4f" % val)
        elif key == "F":
            ordered.append("F%.2f" % val)
        elif key in ("I", "J"):
            ordered.append("%s%.4f" % (key, val))
        elif abs(val - int(round(val))) < 1e-12:
            ordered.append("%s%d" % (key, int(round(val))))
        else:
            ordered.append("%s%s" % (key, val))
    return lead + " ".join(ordered) + nl


def scale_gcode_z_and_f(gcode: str, factor: float, z_floor=None) -> str:
    """
    Scale every Z and F word by ``factor`` (unit conversion).

    ``z_floor`` (typically the already-scaled cut Z) is a hard minimum:
    formatted-number round-trip must never command a deeper cut than
    the job's cut depth.
    """
    if factor == 1:
        return gcode
    out: List[str] = []
    for raw in gcode.splitlines(keepends=True):
        words = parse_gcode_words(raw)
        if "Z" not in words and "F" not in words:
            out.append(raw)
            continue
        if "Z" in words:
            words["Z"] = words["Z"] * factor
            if z_floor is not None and words["Z"] < float(z_floor):
                words["Z"] = float(z_floor)
        if "F" in words:
            words["F"] = words["F"] * factor
        out.append(_reconstruct_line(raw, words, "X%.4fY%.4f"))
    return "".join(out)


def replace_unit_codes(gcode: str, units: str) -> str:
    """Force every G20/G21 in ``gcode`` to match ``units`` (IN or MM)."""
    units = str(units).upper()
    target = "G20" if units == "IN" else "G21"

    out: List[str] = []
    for raw in gcode.splitlines(keepends=True):
        words = parse_gcode_words(raw)
        if int(round(words.get("G", -1))) in (20, 21):
            nl = "\r\n" if raw.endswith("\r\n") else ("\n" if raw.endswith("\n") else "")
            out.append(target + nl)
        else:
            out.append(raw)
    return "".join(out)


def compose_export_text(
    gcode: str,
    preamble: str = "",
    postamble: str = "",
    *,
    z_move: float,
    dwell: bool = False,
    dwelltime=1,
    prepend_safe_retract: bool = True,
    units: str = "MM",
) -> str:
    """
    Build the exact text that should hit the disk / Tcl ``export_gcode``.

    A rapid to travel Z is inserted *before* a non-empty user preamble so
    a preamble that contains XY motion cannot fire at an unknown height.
    Units and absolute mode are declared first so that lead-in is legal.
    """
    body = gcode or ""
    if dwell:
        body = insert_dwell_after_spindle(body, dwelltime)

    chunks: List[str] = []
    if preamble and str(preamble).strip():
        if prepend_safe_retract:
            unit_code = "G20" if str(units).upper() == "IN" else "G21"
            chunks.append("%s\nG90\nG00 Z%.4f\n" % (unit_code, float(z_move)))
        pre = str(preamble)
        if not pre.endswith("\n"):
            pre += "\n"
        chunks.append(pre)
    chunks.append(body)
    if postamble:
        chunks.append(str(postamble))
    return "".join(chunks)
