"""App-level unit coverage: Excellon, project files, Tcl, plot ticks, forms."""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest

from PySide6 import QtCore, QtWidgets
from shapely.geometry import Polygon

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from FlatCAMApp import App
from FlatCAMObj import FlatCAMCNCjob, FlatCAMExcellon, FlatCAMGeometry, FlatCAMGerber
from GUIElements import LengthEntry
from gcode_safety import assert_safe_gcode, parse_gcode_words
import units

EXCELLON = os.path.join(ROOT, "tests", "excellon_files", "case1.drl").replace("\\", "/")
GERBER = os.path.join(ROOT, "tests", "gerber_files", "simple1.gbr").replace("\\", "/")
MM_PER_INCH = 25.4


def pump(qapp, seconds=0.2, steps=8):
    dt = seconds / max(steps, 1)
    for _ in range(steps):
        qapp.processEvents()
        time.sleep(dt)


class TestUnitsAppGaps(unittest.TestCase):
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

    def test_inch_excellon_tools_and_holes_are_millimetres(self):
        self.fc.open_excellon(EXCELLON)
        pump(self.qapp, 0.4)
        names = self.fc.collection.get_names()
        self.assertTrue(names)
        exc = self.fc.collection.get_by_name(names[0])
        self.assertIsInstance(exc, FlatCAMExcellon)
        self.assertEqual(str(exc.units).upper(), "MM")
        sizes = sorted(float(t["C"]) for t in exc.tools.values())
        self.assertAlmostEqual(min(sizes), 0.0200 * MM_PER_INCH, places=3)
        self.assertAlmostEqual(max(sizes), 0.1181 * MM_PER_INCH, places=3)
        xs = [d["point"].x for d in exc.drills]
        ys = [d["point"].y for d in exc.drills]
        self.assertTrue(xs)
        # Unconverted inch holes sit around ±6; mm holes reach tens of mm.
        self.assertGreater(max(abs(x) for x in xs), 10.0)
        self.assertLess(max(abs(x) for x in xs), 200.0)
        self.assertGreater(max(abs(y) for y in ys), 5.0)

    def test_loaded_inch_cncjob_scales_xy_not_tooldia_twice(self):
        from shapely.geometry import LineString

        def init(obj, app):
            obj.solid_geometry = [LineString([(0, 0), (25.4, 0)])]
            obj.units = "MM"

        self.fc.new_object("geometry", "cnc_src", init)
        geo = self.fc.collection.get_by_name("cnc_src")
        geo.generatecncjob(
            use_thread=False,
            z_cut=-1.45,
            z_move=5.0,
            feedrate=254,
            tooldia=0.79375,
            outname="inch_job",
        )
        job = self.fc.collection.get_by_name("inch_job")
        self.assertIsInstance(job, FlatCAMCNCjob)
        job.convert_units("IN")
        self.assertEqual(str(job.units).upper(), "IN")
        fd, path = tempfile.mkstemp(suffix=".FlatCAM")
        os.close(fd)
        try:
            self.fc.save_project(path)
            self.fc.exec_command_test("new")
            self.fc.open_project(path)
            pump(self.qapp, 0.3)
            loaded = self.fc.collection.get_by_name("inch_job")
            self.assertIsInstance(loaded, FlatCAMCNCjob)
            self.assertEqual(str(loaded.units).upper(), "MM")
            self.assertIn("G21", loaded.gcode)
            self.assertIn("X25.4000", loaded.gcode)
            zs = []
            for line in loaded.gcode.splitlines():
                w = parse_gcode_words(line)
                if "Z" in w and w["Z"] < -0.1:
                    zs.append(w["Z"])
            self.assertTrue(zs)
            self.assertAlmostEqual(min(zs), -1.45, places=2)
            self.assertAlmostEqual(float(loaded.tooldia), 0.79375, places=3)
            self.assertAlmostEqual(float(loaded.options["tooldia"]), 0.79375, places=3)
            assert_safe_gcode(loaded.gcode, loaded.z_cut, loaded.z_move)
        finally:
            if os.path.isfile(path):
                os.remove(path)

    def test_project_round_trip_keeps_mm_storage_and_mixed_fields(self):
        def init(obj, app):
            obj.solid_geometry = [Polygon([(0, 0), (10, 0), (10, 6), (0, 6)])]
            obj.units = "MM"

        self.fc.new_object("geometry", "mix_save", init)
        geo = self.fc.collection.get_by_name("mix_save")
        geo.build_ui()
        geo.ui.cnctooldia_entry.set_value("1/32in")
        geo.ui.cutz_entry.set_value("-1.45mm")
        geo.ui.travelz_entry.set_value("5mm")
        geo.read_form()
        b0 = geo.bounds()
        fd, path = tempfile.mkstemp(suffix=".FlatCAM")
        os.close(fd)
        try:
            self.fc.save_project(path)
            self.fc.exec_command_test("new")
            self.fc.open_project(path)
            pump(self.qapp, 0.3)
            loaded = self.fc.collection.get_by_name("mix_save")
            self.assertIsInstance(loaded, FlatCAMGeometry)
            self.assertEqual(str(loaded.units).upper(), "MM")
            self.assertAlmostEqual(float(loaded.options["cnctooldia"]), 0.79375, places=5)
            self.assertAlmostEqual(float(loaded.options["cutz"]), -1.45, places=5)
            self.assertEqual(loaded.bounds(), b0)
            self.assertEqual(str(self.fc.options.get("storage_units", "MM")).upper(), "MM")
        finally:
            if os.path.isfile(path):
                os.remove(path)

    def test_tcl_bare_dia_is_millimetres(self):
        def init(obj, app):
            obj.solid_geometry = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
            obj.units = "MM"

        self.fc.new_object("gerber", "pad", init)
        self.fc.exec_command_test("isolate pad -dia 0.8 -passes 1 -combine 1")
        pump(self.qapp, 0.4)
        iso = self.fc.collection.get_by_name("pad_iso")
        self.assertIsInstance(iso, FlatCAMGeometry)
        minx, miny, maxx, maxy = iso.bounds()
        self.assertAlmostEqual(minx, -0.4, places=3)
        self.assertAlmostEqual(maxx, 10.4, places=3)
        # If 0.8 were inches, the pad would grow by 10.16 mm each side.
        self.assertLess(maxx - 10.0, 2.0)

    def test_tcl_cncjob_bare_numbers_are_millimetres(self):
        def init(obj, app):
            from shapely.geometry import LineString
            obj.solid_geometry = [LineString([(0, 0), (5, 0)])]
            obj.units = "MM"

        self.fc.new_object("geometry", "seg", init)
        self.fc.exec_command_test(
            "cncjob seg -z_cut -1.45 -z_move 5 -feedrate 120 -tooldia 0.79375 "
            "-outname seg_cnc"
        )
        pump(self.qapp, 0.4)
        cnc = self.fc.collection.get_by_name("seg_cnc")
        self.assertIsNotNone(cnc)
        self.assertIn("G21", cnc.gcode)
        self.assertIn("Z-1.4500", cnc.gcode)
        self.assertAlmostEqual(float(cnc.tooldia), 0.79375, places=5)
        assert_safe_gcode(cnc.gcode, cnc.z_cut, cnc.z_move)

    def test_plot_ticks_show_inches_when_display_is_inch(self):
        pc = self.fc.plotcanvas
        pc.set_display_units("IN")
        inch_txt = pc.axes.xaxis.get_major_formatter().format_data(25.4)
        self.assertAlmostEqual(float(inch_txt), 1.0, places=5)
        pc.set_display_units("MM")
        mm_txt = pc.axes.xaxis.get_major_formatter().format_data(25.4)
        self.assertAlmostEqual(float(mm_txt), 25.4, places=5)

    def test_app_forms_every_length_entry_converts(self):
        entries = []
        for root in (
            self.fc.defaults_form,
            self.fc.options_form,
            getattr(self.fc, "stock_tool", None),
        ):
            if root is None:
                continue
            entries.extend(root.findChildren(LengthEntry))
        self.assertGreaterEqual(len(entries), 20)
        for i, entry in enumerate(entries):
            entry.set_value("1/32in")
            self.assertAlmostEqual(
                entry.get_value(), 0.79375, places=5, msg="form[%d]" % i
            )

    def test_defaults_form_preferred_keys(self):
        fields = self.fc.defaults_form_fields
        for key, unit in units.PREFERRED_LENGTH_UNITS.items():
            if key not in fields:
                continue
            widget = fields[key]
            if not isinstance(widget, LengthEntry):
                continue
            if unit == "IN":
                widget.set_value("0.005in")
                self.assertAlmostEqual(widget.get_value(), 0.127, places=4, msg=key)
            else:
                widget.set_value("1.45mm")
                self.assertAlmostEqual(widget.get_value(), 1.45, places=5, msg=key)

    def test_draw_and_stock_and_dblsided_length_entries(self):
        from FlatCAMDraw import BufferSelectionTool, PaintOptionsTool
        from ToolDblSided import DblSidedTool

        buf = BufferSelectionTool(self.fc, None)
        buf.buffer_distance_entry.set_value("0.2mm")
        self.assertAlmostEqual(buf.buffer_distance_entry.get_value(), 0.2, places=5)
        buf.buffer_distance_entry.set_value("1/32in")
        self.assertAlmostEqual(buf.buffer_distance_entry.get_value(), 0.79375, places=5)

        paint = PaintOptionsTool(self.fc, None)
        for entry in (
            paint.painttooldia_entry,
            paint.paintoverlap_entry,
            paint.paintmargin_entry,
        ):
            entry.set_value("1/32in")
            self.assertAlmostEqual(entry.get_value(), 0.79375, places=5)

        dbl = DblSidedTool(self.fc)
        dbl.drill_dia.set_value("0.8mm")
        self.assertAlmostEqual(dbl.drill_dia.get_value(), 0.8, places=5)
        dbl.drill_dia.set_value("0.03125in")
        self.assertAlmostEqual(dbl.drill_dia.get_value(), 0.79375, places=5)

        if getattr(self.fc, "stock_tool", None) is not None:
            self.fc.stock_tool.width_entry.set_value("100mm")
            self.assertAlmostEqual(self.fc.stock_tool.width_entry.get_value(), 100.0, places=4)
            self.fc.stock_tool.width_entry.set_value('3.937in')
            self.assertAlmostEqual(
                self.fc.stock_tool.width_entry.get_value(), 3.937 * MM_PER_INCH, places=2
            )
