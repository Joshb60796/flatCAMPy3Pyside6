"""App-level PCB material: outline, translate, and tile."""
from __future__ import annotations

import os
import sys
import time
import unittest

from PySide6 import QtCore, QtWidgets
from shapely.geometry import Point, Polygon

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from FlatCAMApp import App
from FlatCAMCommon import qt_widget_alive
from FlatCAMObj import FlatCAMExcellon, FlatCAMGeometry, FlatCAMGerber
from stock import size_of


def pump(qapp, seconds=0.2, steps=8):
    dt = seconds / max(steps, 1)
    for _ in range(steps):
        qapp.processEvents()
        time.sleep(dt)


class TestStockApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
        QtCore.QDir.setSearchPaths(
            "share", [os.path.join(ROOT, "share"), "share", "share/flatcam"]
        )
        cls.fc = App(user_defaults=False)
        cls.fc.ui.shell_dock.show()

    def setUp(self):
        self.fc.exec_command_test("set_sys units MM")
        self.fc.exec_command_test("new")
        self.fc.exec_command_test("set_stock 203.2 254")

    @classmethod
    def tearDownClass(cls):
        try:
            cls.fc.tcl = None
        except Exception:
            pass
        try:
            cls.qapp.closeAllWindows()
        except Exception:
            pass
        del cls.fc

    def _rect(self, name, x0, y0, w, h):
        def init(obj, app):
            obj.solid_geometry = [Polygon([
                (x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)
            ])]
            obj.units = "MM"
        self.fc.new_object("geometry", name, init)
        return self.fc.collection.get_by_name(name)

    def test_default_stock_is_100_by_70_mm(self):
        import flatcam_defaults
        mm = flatcam_defaults.defaults_for_units("MM")
        inch = flatcam_defaults.defaults_for_units("IN")
        self.assertAlmostEqual(mm["stock_width"], 100.0, places=4)
        self.assertAlmostEqual(mm["stock_height"], 70.0, places=4)
        self.assertAlmostEqual(inch["stock_width"], 100.0 / 25.4, places=5)
        self.assertAlmostEqual(inch["stock_height"], 70.0 / 25.4, places=5)

    def test_set_stock_tcl(self):
        out = self.fc.exec_command_test("set_stock 200 250")
        self.assertIn("200", out)
        self.assertAlmostEqual(self.fc.stock.width(), 200)
        self.assertAlmostEqual(self.fc.stock.height(), 250)

    def test_place_on_stock_moves_min_corner(self):
        geo = self._rect("card", 12, 8, 25.4, 50.8)
        self.fc.exec_command_test("place_on_stock card 2 3")
        xmin, ymin, xmax, ymax = geo.bounds()
        self.assertAlmostEqual(xmin, 2, places=5)
        self.assertAlmostEqual(ymin, 3, places=5)
        self.assertAlmostEqual(xmax, 27.4, places=5)
        self.assertAlmostEqual(ymax, 53.8, places=5)

    def test_fit_detects_overflow_then_ok_after_place(self):
        geo = self._rect("big", 0, 0, 25.4, 50.8)
        self.fc.exec_command_test("set_stock 20 20")
        report = self.fc.stock.fit_report([geo])
        self.assertFalse(report["fits"])
        self.fc.exec_command_test("set_stock 200 250")
        self.fc.exec_command_test("place_on_stock big 0 0")
        report = self.fc.stock.fit_report([geo])
        self.assertTrue(report["fits"])

    def test_tile_2x2_geometry(self):
        geo = self._rect("unit", 0, 0, 10, 20)
        created = self.fc.stock.tile_objects(
            [geo], 2, 2, spacing_x=2, spacing_y=2, margin=0, start_at_origin=True
        )
        pump(self.qapp, 0.2)
        tiled = created[0]
        self.assertIsInstance(tiled, FlatCAMGeometry)
        xmin, ymin, xmax, ymax = tiled.bounds()
        self.assertAlmostEqual(xmin, 0, places=5)
        self.assertAlmostEqual(ymin, 0, places=5)
        self.assertAlmostEqual(xmax, 22, places=5)
        self.assertAlmostEqual(ymax, 42, places=5)
        report = self.fc.stock.fit_report([tiled])
        self.assertTrue(report["fits"])
        self.assertIsNone(self.fc.collection.get_by_name("unit"))
        tiled.build_ui()
        self.assertTrue(qt_widget_alive(tiled.ui))

    def test_tile_keeps_gerber_and_excellon_aligned(self):
        def ginit(obj, app):
            obj.solid_geometry = Polygon([(1, 1), (11, 1), (11, 6), (1, 6)])
        def einit(obj, app):
            obj.tools = {"1": {"C": 0.8}}
            obj.drills = [{"point": Point(2, 2), "tool": "1"}]
            obj.create_geometry()
        self.fc.new_object("gerber", "cu", ginit)
        self.fc.new_object("excellon", "drl", einit)
        cu = self.fc.collection.get_by_name("cu")
        drl = self.fc.collection.get_by_name("drl")
        created = self.fc.stock.tile_objects(
            [cu, drl], 2, 1, spacing_x=4, spacing_y=0, margin=0, start_at_origin=True
        )
        pump(self.qapp, 0.2)
        self.assertIsInstance(created[0], FlatCAMGerber)
        self.assertIsInstance(created[1], FlatCAMExcellon)
        # Design min is (1,1); start at origin moves first tile by (-1,-1).
        # Second tile +14 in X (width 10 + spacing 4).
        holes = [(round(d["point"].x, 4), round(d["point"].y, 4))
                 for d in created[1].drills]
        self.assertIn((1.0, 1.0), holes)
        self.assertIn((15.0, 1.0), holes)
        self.assertIsNone(self.fc.collection.get_by_name("cu"))
        self.assertIsNone(self.fc.collection.get_by_name("drl"))

    def test_clear_current_removes_selected(self):
        geo = self._rect("gone", 0, 0, 5, 5)
        self.fc.collection.set_active("gone")
        self.fc.stock_tool.on_clear_current()
        pump(self.qapp, 0.1)
        self.assertIsNone(self.fc.collection.get_by_name("gone"))

    def test_autofill_1x2_on_8x10_in(self):
        self.fc.exec_command_test("set_stock 203.2 254")
        geo = self._rect("small", 0, 0, 25.4, 50.8)
        dw, dh = size_of(geo.bounds())
        from stock import autofill_counts
        cols, rows = autofill_counts(
            dw, dh, self.fc.stock.width(), self.fc.stock.height(),
            spacing_x=0, spacing_y=0, margin=0,
        )
        self.assertEqual(cols, 8)
        self.assertEqual(rows, 5)

    def test_options_combo_keeps_application_defaults_readable(self):
        cb = self.fc.defaults_form.gerber_group.plot_cb
        self.fc.on_options_combo_change(1)
        pump(self.qapp, 0.05)
        self.fc.on_options_combo_change(0)
        pump(self.qapp, 0.05)
        self.assertTrue(qt_widget_alive(self.fc.defaults_form))
        self.assertTrue(qt_widget_alive(self.fc.options_form))
        self.assertEqual(self.fc.options_stack.currentIndex(), 0)
        self.assertEqual(cb.font().bold(), self.fc.options_form.gerber_group.plot_cb.font().bold())

    def test_zoom_bounds_include_stock(self):
        box = self.fc.stock.zoom_bounds()
        self.assertIsNotNone(box)
        self.assertAlmostEqual(box[0], 0)
        self.assertAlmostEqual(box[1], 0)
        self.assertAlmostEqual(box[2], 203.2, places=3)
        self.assertGreaterEqual(box[3], 254.0)
