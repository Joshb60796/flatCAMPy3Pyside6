"""PCB material (stock) fit, placement, and rectilinear tiling."""
from __future__ import annotations

import os
import sys
import unittest

from shapely.geometry import LineString, Point, Polygon

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from stock import (
    STOCK_LABEL_FONTSIZE,
    autofill_counts,
    fits_in_stock,
    offsets_from_current,
    place_offset,
    size_of,
    tile_gcode,
    tile_offsets,
    tiled_extent,
    tiled_geometry,
    translate_geom,
    union_bounds,
)


class TestStockMath(unittest.TestCase):
    def test_label_is_large_enough_to_read(self):
        self.assertGreaterEqual(STOCK_LABEL_FONTSIZE, 28)

    def test_default_blank_size_is_100_by_70_mm(self):
        import flatcam_defaults as d
        self.assertAlmostEqual(d.STOCK_WIDTH_MM, 100.0)
        self.assertAlmostEqual(d.STOCK_HEIGHT_MM, 70.0)
        mm = d.defaults_for_units("MM")
        inch = d.defaults_for_units("IN")
        self.assertAlmostEqual(mm["stock_width"], 100.0, places=4)
        self.assertAlmostEqual(mm["stock_height"], 70.0, places=4)
        self.assertAlmostEqual(inch["stock_width"], 100.0 / 25.4, places=5)
        self.assertAlmostEqual(inch["stock_height"], 70.0 / 25.4, places=5)

    def test_migrate_old_8x10_stock_to_100x70(self):
        import flatcam_defaults as d
        mm = {"units": "MM", "stock_width": 203.2, "stock_height": 254.0}
        d.migrate_stock_defaults(mm)
        self.assertAlmostEqual(mm["stock_width"], 100.0)
        self.assertAlmostEqual(mm["stock_height"], 70.0)
        inch = {"units": "IN", "stock_width": 8.0, "stock_height": 10.0}
        d.migrate_stock_defaults(inch)
        self.assertAlmostEqual(inch["stock_width"], 100.0 / 25.4, places=5)
        self.assertAlmostEqual(inch["stock_height"], 70.0 / 25.4, places=5)

    def test_union_bounds(self):
        box = union_bounds([(1, 2, 4, 5), (0, 3, 6, 4)])
        self.assertEqual(box, (0, 2, 6, 5))
        self.assertIsNone(union_bounds([]))
        self.assertIsNone(union_bounds([None]))

    def test_fits_inside(self):
        fits, overflow = fits_in_stock((0, 0, 5, 5), 10, 10)
        self.assertTrue(fits)
        self.assertEqual(overflow, (0.0, 0.0, 0.0, 0.0))

    def test_overflow_sides(self):
        fits, overflow = fits_in_stock((-1, -0.5, 12, 11), 10, 10)
        self.assertFalse(fits)
        self.assertAlmostEqual(overflow[0], 1.0)
        self.assertAlmostEqual(overflow[1], 0.5)
        self.assertAlmostEqual(overflow[2], 2.0)
        self.assertAlmostEqual(overflow[3], 1.0)

    def test_empty_design_fits(self):
        fits, overflow = fits_in_stock(None, 8, 10)
        self.assertTrue(fits)

    def test_zero_stock_does_not_fit(self):
        fits, _ = fits_in_stock((0, 0, 1, 1), 0, 10)
        self.assertFalse(fits)

    def test_place_offset_to_origin(self):
        self.assertEqual(place_offset((3, 4, 5, 7), 0, 0), (-3, -4))
        self.assertEqual(place_offset((3, 4, 5, 7), 1, 2), (-2, -2))

    def test_autofill_1x2_on_8x10(self):
        cols, rows = autofill_counts(1, 2, 8, 10, spacing_x=0, spacing_y=0, margin=0)
        self.assertEqual((cols, rows), (8, 5))

    def test_autofill_with_spacing_and_margin(self):
        cols, rows = autofill_counts(1, 2, 8, 10, spacing_x=1, spacing_y=1, margin=0)
        self.assertEqual(cols, 4)
        self.assertEqual(rows, 3)
        w, h = tiled_extent(1, 2, cols, rows, 1, 1)
        self.assertLessEqual(w, 8 + 1e-9)
        self.assertLessEqual(h, 10 + 1e-9)

    def test_autofill_too_large(self):
        self.assertEqual(autofill_counts(9, 2, 8, 10), (0, 0))

    def test_tile_offsets_rectilinear(self):
        offs = tile_offsets(1, 2, 3, 2, spacing_x=0.5, spacing_y=1, origin_x=0.2, origin_y=0.1)
        self.assertEqual(len(offs), 6)
        self.assertEqual(offs[0], (0.2, 0.1))
        self.assertAlmostEqual(offs[1][0], 0.2 + 1.5)
        self.assertAlmostEqual(offs[3][1], 0.1 + 3.0)

    def test_offsets_from_current_moves_to_origin(self):
        offs = offsets_from_current((5, 6, 6, 8), 2, 2, 0, 0, start_at=(0, 0))
        self.assertEqual(offs[0], (-5, -6))
        self.assertEqual(offs[1], (-4, -6))
        self.assertEqual(offs[2], (-5, -4))
        self.assertEqual(offs[3], (-4, -4))

    def test_tiled_geometry_polygon(self):
        poly = Polygon([(0, 0), (1, 0), (1, 2), (0, 2)])
        geo = tiled_geometry(poly, [(0, 0), (2, 0)])
        minx, miny, maxx, maxy = geo.bounds
        self.assertAlmostEqual(minx, 0)
        self.assertAlmostEqual(maxx, 3)
        self.assertAlmostEqual(maxy, 2)

    def test_translate_geom_list(self):
        moved = translate_geom([Point(1, 1), LineString([(0, 0), (1, 0)])], 2, 3)
        self.assertAlmostEqual(moved[0].x, 3)
        self.assertAlmostEqual(list(moved[1].coords)[0][1], 3)

    def test_tile_gcode_rewrites_xy(self):
        g = (
            "G21\nG90\nF100.00\nG00 Z5.0000\nM03\n"
            "G00 X1.0000Y2.0000\nG01 Z-0.1000\nG00 Z5.0000\n"
            "G00 Z5.0000\nG00 X0.0000Y0.0000\nM05\n"
        )
        out = tile_gcode(g, [(0, 0), (10, 0)])
        self.assertIn("X1.0000Y2.0000", out)
        self.assertIn("X11.0000Y2.0000", out)
        self.assertGreaterEqual(out.count("G01"), 2)


class TestStockThemeColors(unittest.TestCase):
    def test_stock_colors_readable(self):
        import theme
        theme.assert_theme_readable(dark=True)
        theme.assert_theme_readable(dark=False)
