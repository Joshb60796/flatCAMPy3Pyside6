"""Board cutout tool diameter: inch units must keep 1/32\" and pass it to CNC."""
from __future__ import annotations

import os
import sys
import unittest

from shapely.geometry import LineString, MultiLineString

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import flatcam_defaults as d
from camlib import CNCjob, Geometry, board_cutout_geometry, init_board_cutout


class _Geo:
    def __init__(self):
        self.solid_geometry = None
        self.options = {"cnctooldia": d.VBIT_TIP_DIA_MM * d.INCH_PER_MM}


class TestCutoutToolDiameterUnits(unittest.TestCase):
    def test_inch_cutout_default_is_one_thirty_second(self):
        inch = d.defaults_for_units("IN")
        self.assertAlmostEqual(inch["gerber_cutouttooldia"], 0.03125, places=6)
        self.assertAlmostEqual(
            inch["gerber_cutouttooldia"] * 25.4,
            d.ENDMILL_DIA_MM,
            places=6,
        )

    def test_mm_cutout_default_is_endmill_mm(self):
        mm = d.defaults_for_units("MM")
        self.assertAlmostEqual(mm["gerber_cutouttooldia"], d.ENDMILL_DIA_MM, places=6)

    def test_geometry_cnc_default_is_vbit_not_endmill(self):
        # Isolation CNC inherits the V-bit tip. Cutout must overwrite this
        # or a 1/32" cutout is plotted/exported as a 0.003" isolation bit.
        inch = d.defaults_for_units("IN")
        self.assertAlmostEqual(inch["geometry_cnctooldia"], 0.003, places=6)
        self.assertAlmostEqual(inch["cncjob_tooldia"], 0.003, places=6)
        self.assertGreater(inch["gerber_cutouttooldia"] / inch["geometry_cnctooldia"], 8)

    def test_display_inch_table_still_has_fractional_inch(self):
        opts = d.defaults_for_units("IN")
        self.assertAlmostEqual(opts["gerber_cutouttooldia"], 0.03125, places=6)


class TestBoardCutoutGeometry(unittest.TestCase):
    def test_inch_centerline_offset_uses_endmill_not_vbit(self):
        bounds = (0.0, 0.0, 4.0, 3.0)
        tooldia = 0.03125
        margin = 0.2 / 25.4
        geom = board_cutout_geometry(
            bounds, tooldia, margin=margin, gapsize=0.04, gaps="4"
        )
        minx, miny, maxx, maxy = geom.bounds
        offset = margin + tooldia / 2.0
        self.assertAlmostEqual(minx, -offset, places=6)
        self.assertAlmostEqual(miny, -offset, places=6)
        self.assertAlmostEqual(maxx, 4.0 + offset, places=6)
        self.assertAlmostEqual(maxy, 3.0 + offset, places=6)
        # If 0.03125 were wrongly treated as millimetres on an inch board,
        # the extra offset vs a V-bit (0.003") would be ~0.0005" instead of
        # the 0.0156" half-width of a 1/32" endmill.
        vbit_offset = margin + 0.003 / 2.0
        self.assertGreater(offset - vbit_offset, 0.01)

    def test_cutout_propagates_endmill_to_cnctooldia(self):
        geo = _Geo()
        tooldia = 0.03125
        init_board_cutout(
            geo,
            bounds=(0.0, 0.0, 2.0, 1.0),
            tooldia=tooldia,
            margin=0.01,
            gapsize=0.05,
            gaps="4",
        )
        self.assertAlmostEqual(float(geo.options["cnctooldia"]), tooldia, places=6)
        self.assertIsNotNone(geo.solid_geometry)
        self.assertFalse(geo.solid_geometry.is_empty)

    def test_cutout_paths_are_linestrings(self):
        geom = board_cutout_geometry((0, 0, 1, 1), tooldia=0.1, margin=0.0, gapsize=0.2)
        parts = _parts(geom)
        self.assertGreaterEqual(len(parts), 2)
        for part in parts:
            self.assertIsInstance(part, LineString)

    def test_gap_layouts(self):
        bounds = (0, 0, 10, 8)
        four = _parts(board_cutout_geometry(bounds, 0.8, margin=0.2, gapsize=1.0, gaps="4"))
        tb = _parts(board_cutout_geometry(bounds, 0.8, margin=0.2, gapsize=1.0, gaps="tb"))
        lr = _parts(board_cutout_geometry(bounds, 0.8, margin=0.2, gapsize=1.0, gaps="lr"))
        self.assertEqual(len(four), 4)
        self.assertEqual(len(tb), 2)
        self.assertEqual(len(lr), 2)

    def test_invalid_gaps_raise(self):
        with self.assertRaises(ValueError):
            board_cutout_geometry((0, 0, 1, 1), 0.1, gaps="diagonal")

    def test_cnc_job_uses_cutout_endmill_not_vbit(self):
        geo = Geometry()
        geo.options = {"cnctooldia": 0.003}
        init_board_cutout(
            geo, (0, 0, 12, 8), tooldia=0.79375, margin=0.2, gapsize=1.0, gaps="4"
        )
        job = CNCjob(
            units="MM", z_cut=-1.6, z_move=5.0, feedrate=100.0, tooldia=0.0762
        )
        job.generate_from_geometry_2(
            geo, tooldia=geo.options["cnctooldia"], tolerance=0.01
        )
        self.assertAlmostEqual(job.tooldia, 0.79375, places=5)
        self.assertIn("G01", job.gcode)


def _parts(geom):
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    if geom.geom_type == "LineString":
        return [geom]
    return list(getattr(geom, "geoms", [geom]))
