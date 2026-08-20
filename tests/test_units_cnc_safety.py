"""
Mill-safety lockstep for mixed units.

A 25.4× slip (inch number used as mm, or mm left in a G20 file) will
plunge through the spoilboard or mill a board at 4% of real size.
These tests follow typed lengths → millimetre storage → G-code → export.
"""
from __future__ import annotations

import os
import sys
import unittest

from shapely.geometry import LineString, Polygon

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import units
from camlib import CNCjob, Gerber, Geometry
from gcode_safety import assert_safe_gcode, parse_gcode_words

GERBER_IN = os.path.join(ROOT, "tests", "gerber_files", "simple1.gbr")
MM_PER_INCH = 25.4


def words(gcode, letter):
    out = []
    for line in gcode.splitlines():
        w = parse_gcode_words(line)
        if letter in w:
            out.append(w[letter])
    return out


def make_job_mm(z_cut, z_move, feedrate, tooldia=0.8):
    return CNCjob(
        units="MM",
        z_cut=z_cut,
        z_move=z_move,
        feedrate=feedrate,
        tooldia=tooldia,
    )


class TestParseDoesNotDropSignOrUnit(unittest.TestCase):
    def test_negative_mm_cut_depth(self):
        mm, unit = units.parse_length("-1.45mm")
        self.assertAlmostEqual(mm, -1.45)
        self.assertEqual(unit, "MM")

    def test_bare_number_uses_field_unit(self):
        mm, unit = units.parse_length("0.005", default_unit="IN")
        self.assertAlmostEqual(mm, 0.005 * MM_PER_INCH, places=8)
        self.assertEqual(unit, "IN")
        mm2, unit2 = units.parse_length("0.005", default_unit="MM")
        self.assertAlmostEqual(mm2, 0.005, places=8)
        self.assertEqual(unit2, "MM")

    def test_mil_is_thousandth_inch(self):
        mm, unit = units.parse_length("5mil")
        self.assertAlmostEqual(mm, 0.005 * MM_PER_INCH, places=8)
        self.assertEqual(unit, "IN")

    def test_inch_word(self):
        mm, _ = units.parse_length("0.005 inch")
        self.assertAlmostEqual(mm, 0.127, places=4)

    def test_format_parse_round_trip(self):
        for mm, unit in ((0.127, "IN"), (1.45, "MM"), (-1.6, "MM"), (0.79375, "IN")):
            text = units.format_length(mm, unit)
            back, got = units.parse_length(text)
            self.assertEqual(got, unit)
            self.assertAlmostEqual(back, mm, places=5)

    def test_migrate_twice_is_stable(self):
        opts = {
            "units": "IN",
            "gerber_cutouttooldia": 0.03125,
            "stock_width": 3.937,
        }
        import flatcam_defaults as d
        units.migrate_storage_to_mm(opts, d.DIMENSIONAL_OPTION_KEYS)
        once = float(opts["gerber_cutouttooldia"])
        units.migrate_storage_to_mm(opts, d.DIMENSIONAL_OPTION_KEYS)
        self.assertAlmostEqual(opts["gerber_cutouttooldia"], once, places=8)


class TestInchToolOnMmBoard(unittest.TestCase):
    def test_vbit_offset_is_inch_converted_not_raw_0_005(self):
        board = Polygon([(0, 0), (10, 0), (10, 8), (0, 8)])
        geo = Geometry()
        geo.units = "MM"
        geo.solid_geometry = board
        tip_mm, _ = units.parse_length("0.005in")
        iso = geo.isolation_geometry(tip_mm / 2.0)
        minx, miny, maxx, maxy = iso.bounds
        # 0.005 in ≈ 0.127 mm, so half-width ≈ 0.0635 mm around a 10×8 board.
        self.assertAlmostEqual(minx, -tip_mm / 2.0, places=4)
        self.assertAlmostEqual(maxx, 10.0 + tip_mm / 2.0, places=4)
        self.assertGreater(tip_mm / 2.0, 0.05)
        self.assertLess(tip_mm / 2.0, 0.08)
        # Using 0.005 as millimetres would only grow the board by 0.0025 mm.
        self.assertGreater(10.0 - minx, 0.05)

    def test_cutout_1_32_on_mm_rectangle(self):
        tooldia, _ = units.parse_length("1/32in")
        margin, _ = units.parse_length("0.2mm")
        from camlib import board_cutout_geometry
        geom = board_cutout_geometry(
            (0, 0, 50, 30), tooldia, margin=margin, gapsize=1.0, gaps="4"
        )
        minx, miny, maxx, maxy = geom.bounds
        offset = margin + tooldia / 2.0
        self.assertAlmostEqual(minx, -offset, places=5)
        self.assertAlmostEqual(maxx, 50.0 + offset, places=5)
        self.assertAlmostEqual(tooldia, 0.79375, places=5)
        # A forgotten conversion (0.03125 mm bit) would only offset ~0.22 mm.
        self.assertGreater(offset, 0.5)


class TestGcodeNeverMixesMmNumbersIntoG20(unittest.TestCase):
    def test_user_workflow_inch_bit_mm_depth_mm_board(self):
        tooldia, _ = units.parse_length("1/32in")
        z_cut, _ = units.parse_length("-1.45mm")
        z_move, _ = units.parse_length("5mm")
        job = make_job_mm(z_cut, z_move, feedrate=120.0, tooldia=tooldia)
        geo = Geometry()
        geo.units = "MM"
        geo.solid_geometry = [LineString([(0, 0), (25.4, 0)])]
        job.generate_from_geometry_2(geo, tooldia=tooldia, tolerance=0.01)
        self.assertIn("G21", job.gcode)
        self.assertNotIn("G20", job.gcode)
        zs = [z for z in words(job.gcode, "Z") if z < -0.1]
        self.assertTrue(zs)
        self.assertAlmostEqual(min(zs), -1.45, places=3)
        self.assertIn("X25.4000", job.gcode)
        assert_safe_gcode(job.gcode, z_cut, z_move)

        inch = job.get_gcode(export_units="IN")
        self.assertIn("G20", inch)
        self.assertNotIn("G21\n", inch)
        # Spoilboard killer: mm depth left in an inch file is ~1.45 inches deep.
        self.assertNotIn("Z-1.4500", inch)
        self.assertNotIn("Z-1.45", inch.replace("Z-1.4500", ""))
        inch_zs = [z for z in words(inch, "Z") if z < -0.01]
        self.assertTrue(inch_zs)
        self.assertAlmostEqual(min(inch_zs), -1.45 / MM_PER_INCH, places=3)
        self.assertAlmostEqual(min(inch_zs), -0.0571, places=3)
        self.assertIn("X1.0000", inch)
        assert_safe_gcode(
            inch,
            units.from_mm(z_cut, "IN"),
            units.from_mm(z_move, "IN"),
        )
        # In-memory job stays millimetres so the plot still matches the Gerber.
        self.assertIn("G21", job.gcode)
        self.assertAlmostEqual(job.z_cut, -1.45, places=5)

    def test_export_scales_x_y_z_f_by_the_same_factor(self):
        job = make_job_mm(-25.4, 25.4, feedrate=254.0, tooldia=1.0)
        geo = Geometry()
        geo.units = "MM"
        geo.solid_geometry = [LineString([(0, 0), (25.4, 50.8)])]
        job.generate_from_geometry_2(geo, tolerance=0.01)
        mm_g = job.gcode
        inch_g = job.get_gcode(export_units="IN")
        factor = 1.0 / MM_PER_INCH
        for letter in "XYF":
            mm_vals = words(mm_g, letter)
            in_vals = words(inch_g, letter)
            self.assertEqual(len(mm_vals), len(in_vals), letter)
            for a, b in zip(mm_vals, in_vals):
                self.assertAlmostEqual(b, a * factor, places=3, msg=letter)
        mm_z = words(mm_g, "Z")
        in_z = words(inch_g, "Z")
        self.assertEqual(len(mm_z), len(in_z))
        for a, b in zip(mm_z, in_z):
            self.assertAlmostEqual(b, a * factor, places=3, msg="Z")

    def test_inch_export_round_trip_back_to_mm(self):
        src = "G21\nG90\nF120.00\nG00 Z5.0000\nG00 X25.4000Y0.0000\nG01 Z-1.4500\nG00 Z5.0000\nM05\n"
        inch = units.convert_gcode_units(src, "MM", "IN")
        back = units.convert_gcode_units(inch, "IN", "MM")
        self.assertAlmostEqual(min(words(back, "Z")), -1.45, places=3)
        self.assertAlmostEqual(max(words(back, "X")), 25.4, places=3)


class TestInchGerberBecomesMillimetres(unittest.TestCase):
    def test_simple1_moin_converts_to_mm(self):
        g = Gerber()
        g.parse_file(GERBER_IN)
        self.assertEqual(str(g.units).upper(), "IN")
        minx, miny, maxx, maxy = g.bounds()
        self.assertLess(maxx - minx, 5.0, "still in inches before convert: %s" % (g.bounds(),))
        g.convert_units("MM")
        self.assertEqual(str(g.units).upper(), "MM")
        minx2, miny2, maxx2, maxy2 = g.bounds()
        self.assertAlmostEqual(maxx2 - minx2, (maxx - minx) * MM_PER_INCH, places=3)
        self.assertGreater(maxx2 - minx2, 5.0)
        self.assertLess(maxx2 - minx2, 50.0)
        # Isolation with 0.005 in tip must use millimetre offset on this geometry.
        tip_mm, _ = units.parse_length("0.005in")
        iso = g.isolation_geometry(tip_mm / 2.0)
        iminx, _, imaxx, _ = iso.bounds
        self.assertAlmostEqual(iminx, minx2 - tip_mm / 2.0, places=2)


class TestArcIJExport(unittest.TestCase):
    def test_g02_ij_scale_with_xy_on_inch_export(self):
        # 25.4 mm radius arc: I=25.4 J=0 must become I=1 J=0 in G20.
        g = (
            "G21\nG90\nF120.00\nG00 Z5.0000\nM03\n"
            "G00 X0.0000Y0.0000\n"
            "G01 Z-1.4500\n"
            "G02 X25.4000Y25.4000 I25.4000 J0.0000\n"
            "G00 Z5.0000\nG00 X0.0000Y0.0000\nM05\n"
        )
        inch = units.convert_gcode_units(g, "MM", "IN")
        self.assertIn("G20", inch)
        self.assertIn("I1.0000", inch)
        self.assertIn("J0.0000", inch)
        self.assertIn("X1.0000Y1.0000", inch)
        self.assertNotIn("I25.4000", inch)
        zs = [z for z in words(inch, "Z") if z < -0.01]
        self.assertAlmostEqual(min(zs), -1.45 / MM_PER_INCH, places=3)
        assert_safe_gcode(inch, -1.45 / MM_PER_INCH, 5.0 / MM_PER_INCH)

    def test_live_job_arc_export_keeps_centre(self):
        job = make_job_mm(-1.45, 5.0, 120.0, tooldia=0.79375)
        job.gcode = (
            "G21\nG90\nG94\nF120.00\nG00 Z5.0000\nM03\n"
            "G00 X0.0000Y0.0000\n"
            "G01 Z-1.4500\n"
            "G03 X0.0000Y25.4000 I0.0000 J12.7000\n"
            "G00 Z5.0000\nG00 X0.0000Y0.0000\nM05\n"
        )
        inch = job.get_gcode(export_units="IN")
        self.assertIn("G20", inch)
        js = words(inch, "J")
        self.assertTrue(js)
        self.assertAlmostEqual(js[0], 12.7 / MM_PER_INCH, places=3)
        self.assertAlmostEqual(js[0], 0.5, places=3)
        self.assertIn("G21", job.gcode)

    def test_convert_units_scales_xy_ij_z_and_tooldia_once(self):
        job = make_job_mm(-1.45, 5.0, 254.0, tooldia=0.79375)
        job.gcode = (
            "G21\nG90\nF254.00\nG00 Z5.0000\nM03\n"
            "G00 X25.4000Y0.0000\n"
            "G01 Z-1.4500\n"
            "G02 X50.8000Y0.0000 I12.7000 J0.0000\n"
            "G00 Z5.0000\nG00 X0.0000Y0.0000\nM05\n"
        )
        job.convert_units("IN")
        self.assertIn("G20", job.gcode)
        self.assertIn("X1.0000", job.gcode)
        self.assertIn("I0.5000", job.gcode)
        zs = [z for z in words(job.gcode, "Z") if z < -0.01]
        self.assertAlmostEqual(min(zs), -1.45 / MM_PER_INCH, places=3)
        self.assertAlmostEqual(job.tooldia, 0.03125, places=5)
        job.convert_units("MM")
        self.assertIn("G21", job.gcode)
        self.assertIn("X25.4000", job.gcode)
        self.assertIn("I12.7000", job.gcode)
        self.assertAlmostEqual(job.tooldia, 0.79375, places=4)
        assert_safe_gcode(job.gcode, job.z_cut, job.z_move)
