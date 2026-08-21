"""
High-value G-code export coverage: Tcl commands, FlatCAMCNCJob wrappers,
save-dialog export, generatecncjob / Excellon Create CNC, and real-file
safety checks.

These are the paths a user actually runs — not just camlib unit tests.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from io import StringIO
from unittest.mock import patch

from PySide6 import QtCore, QtWidgets
from shapely.geometry import LineString, Polygon

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from FlatCAMApp import App
from FlatCAMObj import FlatCAMCNCjob, FlatCAMExcellon, FlatCAMGeometry, FlatCAMGerber
from camlib import CNCjob
from gcode_safety import GCodeSafetyError, assert_safe_gcode

GERBER = os.path.join(ROOT, "tests", "gerber_files", "simple1.gbr").replace("\\", "/")
EXCELLON = os.path.join(ROOT, "tests", "excellon_files", "case1.drl").replace("\\", "/")
KB2040_DIR = os.path.join(ROOT, "test Project")


def pump(qapp, seconds=0.3, steps=15):
    dt = seconds / max(steps, 1)
    for _ in range(steps):
        qapp.processEvents()
        time.sleep(dt)


def tcl_path(path):
    return path.replace("\\", "/")


def assert_file_safe(test, filename, z_cut, z_move):
    test.assertTrue(os.path.isfile(filename), "missing %s" % filename)
    with open(filename, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    test.assertTrue(text.strip(), "empty G-code file")
    assert_safe_gcode(text, z_cut, z_move)
    return text


class _AppTestBase(unittest.TestCase):
    """One offscreen QApplication + FlatCAM App for the class."""

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

    def _make_line_geometry(self, name="geo", coords=((0, 0), (8, 0), (8, 3))):
        def init(obj, app):
            obj.solid_geometry = [LineString(list(coords))]
            obj.units = "MM"

        self.fc.new_object("geometry", name, init)
        geo = self.fc.collection.get_by_name(name)
        self.assertIsInstance(geo, FlatCAMGeometry)
        return geo

    def _wait_name(self, name, timeout=20.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            pump(self.qapp, 0.1, steps=4)
            obj = self.fc.collection.get_by_name(name)
            if obj is not None:
                return obj
        self.fail("Timed out waiting for object %r; have %s"
                  % (name, self.fc.collection.get_names()))


# ---------------------------------------------------------------------------
# 1. Tcl export commands
# ---------------------------------------------------------------------------

class TestTclExportCommands(_AppTestBase):
    def test_cncjob_missing_object_raises(self):
        with self.assertRaises(Exception):
            self.fc.exec_command_test("cncjob does_not_exist")

    def test_cncjob_wrong_type_raises(self):
        self.fc.exec_command_test('open_gerber "%s" -outname top' % GERBER)
        with self.assertRaises(Exception):
            self.fc.exec_command_test("cncjob top")

    def test_drillcncjob_missing_and_wrong_type(self):
        with self.assertRaises(Exception):
            self.fc.exec_command_test("drillcncjob missing")
        geo = self._make_line_geometry("not_drill")
        self.assertIsNotNone(geo)
        with self.assertRaises(Exception):
            self.fc.exec_command_test("drillcncjob not_drill")

    def test_export_gcode_missing_and_wrong_type(self):
        with self.assertRaises(Exception):
            self.fc.exec_command_test("export_gcode missing")
        geo = self._make_line_geometry("geo")
        self.assertIsNotNone(geo)
        with self.assertRaises(Exception):
            self.fc.exec_command_test("export_gcode geo")

    def test_write_gcode_missing_object_returns_error(self):
        fd, path = tempfile.mkstemp(suffix=".gcode")
        os.close(fd)
        os.remove(path)
        result = self.fc.exec_command_test(
            'write_gcode missing "%s"' % tcl_path(path), reraise=False
        )
        self.assertIn("Could not retrieve object", str(result))

    def test_write_gcode_wrong_type_returns_error(self):
        self._make_line_geometry("geo")
        fd, path = tempfile.mkstemp(suffix=".gcode")
        os.close(fd)
        os.remove(path)
        result = self.fc.exec_command_test(
            'write_gcode geo "%s"' % tcl_path(path), reraise=False
        )
        self.assertIn("Expected CNC Job", str(result))

    def test_cncjob_export_gcode_write_gcode_are_safe(self):
        geo = self._make_line_geometry("iso")
        self.fc.exec_command_test(
            "cncjob iso -z_cut -0.06 -z_move 5 -feedrate 120 -outname iso_cnc"
        )
        cnc = self.fc.collection.get_by_name("iso_cnc")
        self.assertIsInstance(cnc, FlatCAMCNCjob)

        text = self.fc.exec_command_test("export_gcode iso_cnc")
        self.assertIsInstance(text, str)
        self.assertIn("G21", text)
        self.assertIn("M03", text)
        # Default cncjob dwell is on — Tcl export must apply it.
        self.assertIn("G4 P", text)
        assert_safe_gcode(text, cnc.z_cut, cnc.z_move)

        fd, path = tempfile.mkstemp(suffix=".gcode")
        os.close(fd)
        try:
            result = self.fc.exec_command_test(
                'write_gcode iso_cnc "%s"' % tcl_path(path)
            )
            # Success returns None / empty / 'None'
            self.assertTrue(result in (None, "None", "") or "fail" not in str(result).lower())
            on_disk = assert_file_safe(self, path, cnc.z_cut, cnc.z_move)
            self.assertIn("G4 P", on_disk)
        finally:
            if os.path.isfile(path):
                os.remove(path)

    def test_export_and_write_preamble_postamble(self):
        self._make_line_geometry("iso")
        self.fc.exec_command_test(
            "cncjob iso -z_cut -0.1 -z_move 5 -feedrate 80"
        )
        cnc = self.fc.collection.get_by_name("iso_cnc")
        text = self.fc.exec_command_test(
            'export_gcode iso_cnc "(preamble-mark)" "(postamble-mark)"'
        )
        self.assertIn("(preamble-mark)", text)
        self.assertIn("(postamble-mark)", text)
        assert_safe_gcode(text, cnc.z_cut, cnc.z_move)

        fd, path = tempfile.mkstemp(suffix=".gcode")
        os.close(fd)
        try:
            self.fc.exec_command_test(
                'write_gcode iso_cnc "%s" -preamble "(WPRE)" -postamble "(WPOST)"'
                % tcl_path(path)
            )
            body = assert_file_safe(self, path, cnc.z_cut, cnc.z_move)
            self.assertIn("(WPRE)", body)
            self.assertIn("(WPOST)", body)
        finally:
            if os.path.isfile(path):
                os.remove(path)

    def test_export_gcode_rejects_outstanding_promises(self):
        self._make_line_geometry("iso")
        self.fc.exec_command_test("cncjob iso -z_cut -0.06 -z_move 5 -feedrate 100")
        self.fc.collection.promise("still_coming")
        try:
            with self.assertRaises(Exception):
                self.fc.exec_command_test("export_gcode iso_cnc")
        finally:
            self.fc.collection.promises.discard("still_coming")

    def test_drillcncjob_and_write_are_safe(self):
        self.fc.exec_command_test(
            'open_excellon "%s" -outname drills' % EXCELLON
        )
        self.fc.exec_command_test(
            "drillcncjob drills -tools all -drillz -1.8 -travelz 5 "
            "-feedrate 80 -outname drills_cnc"
        )
        cnc = self.fc.collection.get_by_name("drills_cnc")
        self.assertIsInstance(cnc, FlatCAMCNCjob)
        text = self.fc.exec_command_test("export_gcode drills_cnc")
        assert_safe_gcode(text, cnc.z_cut, cnc.z_move)

        fd, path = tempfile.mkstemp(suffix=".gcode")
        os.close(fd)
        try:
            self.fc.exec_command_test(
                'write_gcode drills_cnc "%s"' % tcl_path(path)
            )
            assert_file_safe(self, path, cnc.z_cut, cnc.z_move)
        finally:
            if os.path.isfile(path):
                os.remove(path)

    def test_drillcncjob_unsafe_toolchangez_fails(self):
        self.fc.exec_command_test(
            'open_excellon "%s" -outname drills' % EXCELLON
        )
        with self.assertRaises(Exception):
            self.fc.exec_command_test(
                "drillcncjob drills -tools all -drillz -1.0 -travelz 5 "
                "-feedrate 80 -toolchange 1 -toolchangez 0.1"
            )

    def test_cncjob_unsafe_travel_fails(self):
        self._make_line_geometry("iso")
        with self.assertRaises(Exception):
            self.fc.exec_command_test(
                "cncjob iso -z_cut -1.0 -z_move -0.2 -feedrate 100"
            )

    def test_cncjob_overrides_and_custom_outname(self):
        self._make_line_geometry("iso")
        self.fc.exec_command_test(
            "cncjob iso -z_cut -0.25 -z_move 8 -feedrate 90 "
            "-tooldia 0.4 -spindlespeed 12000 -outname custom_cnc"
        )
        cnc = self.fc.collection.get_by_name("custom_cnc")
        self.assertIsInstance(cnc, FlatCAMCNCjob)
        self.assertAlmostEqual(float(cnc.z_cut), -0.25, places=4)
        self.assertAlmostEqual(float(cnc.z_move), 8.0, places=4)
        self.assertAlmostEqual(float(cnc.feedrate), 90.0, places=4)
        self.assertEqual(int(cnc.spindlespeed), 12000)
        assert_safe_gcode(cnc.gcode, cnc.z_cut, cnc.z_move)
        self.assertIn("M03 S12000", cnc.gcode)

    def test_gerber_tcl_pipeline_simple1(self):
        self.fc.exec_command_test('open_gerber "%s" -outname top' % GERBER)
        self.assertIsInstance(self.fc.collection.get_by_name("top"), FlatCAMGerber)
        self.fc.exec_command_test("isolate top -dia 0.3")
        self.assertIsInstance(
            self.fc.collection.get_by_name("top_iso"), FlatCAMGeometry
        )
        self.fc.exec_command_test(
            "cncjob top_iso -z_cut -0.06 -z_move 5 -feedrate 120"
        )
        cnc = self.fc.collection.get_by_name("top_iso_cnc")
        text = self.fc.exec_command_test("export_gcode top_iso_cnc")
        assert_safe_gcode(text, cnc.z_cut, cnc.z_move)


# ---------------------------------------------------------------------------
# 2. FlatCAMCNCJob export wrapper
# ---------------------------------------------------------------------------

class TestFlatCAMCNCJobWrapper(_AppTestBase):
    def _job(self):
        geo = self._make_line_geometry("wrap_geo")
        geo.generatecncjob(
            use_thread=False,
            z_cut=-0.08,
            z_move=5.0,
            feedrate=100,
            outname="wrap_cnc",
        )
        job = self.fc.collection.get_by_name("wrap_cnc")
        self.assertIsInstance(job, FlatCAMCNCjob)
        return job

    def test_get_gcode_applies_dwell_from_options(self):
        job = self._job()
        job.options["dwell"] = True
        job.options["dwelltime"] = 2.5
        text = job.get_gcode()
        self.assertIn("G4 P2.5", text)
        assert_safe_gcode(text, job.z_cut, job.z_move)

        job.options["dwell"] = False
        text_off = job.get_gcode()
        self.assertNotIn("G4 P", text_off)
        assert_safe_gcode(text_off, job.z_cut, job.z_move)

    def test_get_gcode_preamble_is_safe(self):
        job = self._job()
        job.options["dwell"] = False
        text = job.get_gcode(preamble="G00 X1Y1", postamble="(done)")
        self.assertIn("(done)", text)
        assert_safe_gcode(text, job.z_cut, job.z_move)

    def test_export_gcode_writes_emits_and_applies_dwell(self):
        job = self._job()
        job.options["dwell"] = True
        job.options["dwelltime"] = 1
        opened = []
        informed = []
        job.app.file_opened.connect(lambda kind, name: opened.append((kind, name)))
        job.app.inform.connect(lambda msg: informed.append(str(msg)))

        fd, path = tempfile.mkstemp(suffix=".gcode")
        os.close(fd)
        try:
            job.export_gcode(path, preamble="(UI-PRE)", postamble="(UI-POST)")
            text = assert_file_safe(self, path, job.z_cut, job.z_move)
            self.assertIn("G4 P", text)
            self.assertIn("(UI-PRE)", text)
            self.assertIn("(UI-POST)", text)
            self.assertTrue(any(kind == "cncjob" for kind, _ in opened), opened)
            self.assertTrue(any("Saved" in m for m in informed), informed)
        finally:
            if os.path.isfile(path):
                os.remove(path)

    def test_export_gcode_empty_raises(self):
        job = self._job()
        job.gcode = ""
        fd, path = tempfile.mkstemp(suffix=".gcode")
        os.close(fd)
        try:
            with self.assertRaises(GCodeSafetyError):
                job.export_gcode(path)
        finally:
            if os.path.isfile(path):
                os.remove(path)

    def test_dwell_generator_uses_options_dwelltime(self):
        job = self._job()
        job.options["dwelltime"] = 3
        out = "".join(job.dwell_generator(StringIO("M03\nG00 X1Y1\n")))
        self.assertIn("G4 P3", out)

    def test_wrapper_is_not_the_bare_cncjob_class(self):
        job = self._job()
        self.assertIsInstance(job, CNCjob)
        self.assertIsInstance(job, FlatCAMCNCjob)


# ---------------------------------------------------------------------------
# 3. Save-dialog export
# ---------------------------------------------------------------------------

class TestSaveDialogExport(_AppTestBase):
    def _cnc_with_ui(self):
        geo = self._make_line_geometry("dlg_geo")
        geo.generatecncjob(
            use_thread=False, z_cut=-0.06, z_move=5, feedrate=100, outname="dlg_cnc"
        )
        cnc = self.fc.collection.get_by_name("dlg_cnc")
        cnc.build_ui()
        return cnc

    def test_cancel_writes_nothing(self):
        cnc = self._cnc_with_ui()
        with patch(
            "FlatCAMObj.QtWidgets.QFileDialog.getSaveFileName",
            return_value=("", ""),
        ):
            cnc.on_exportgcode_button_click()
        # No crash, no stray file in cwd named after the object.
        self.assertFalse(os.path.isfile("dlg_cnc.gcode"))
        self.assertFalse(os.path.isfile("dlg_cnc.nc"))

    def test_bare_name_linuxcnc_filter_gets_ngc(self):
        cnc = self._cnc_with_ui()
        dest_dir = tempfile.mkdtemp()
        bare = os.path.join(dest_dir, "board")
        with patch(
            "FlatCAMObj.QtWidgets.QFileDialog.getSaveFileName",
            return_value=(bare, "LinuxCNC / EMC (*.ngc)"),
        ):
            cnc.on_exportgcode_button_click()
        out = bare + ".ngc"
        try:
            assert_file_safe(self, out, cnc.z_cut, cnc.z_move)
        finally:
            if os.path.isfile(out):
                os.remove(out)

    def test_bare_name_nc_and_tap_filters(self):
        cnc = self._cnc_with_ui()
        dest_dir = tempfile.mkdtemp()
        for filt, ext in (
            ("NC (*.nc)", ".nc"),
            ("Tape (*.tap)", ".tap"),
        ):
            bare = os.path.join(dest_dir, "out_" + ext.replace(".", ""))
            with patch(
                "FlatCAMObj.QtWidgets.QFileDialog.getSaveFileName",
                return_value=(bare, filt),
            ):
                cnc.on_exportgcode_button_click()
            out = bare + ext
            self.assertTrue(os.path.isfile(out), "expected %s from filter %r" % (out, filt))
            assert_file_safe(self, out, cnc.z_cut, cnc.z_move)
            os.remove(out)

    def test_dialog_suggests_nc_extension(self):
        cnc = self._cnc_with_ui()
        captured = {}

        def fake_dialog(_parent, _title, start, _filt):
            captured["start"] = start
            return ("", "")

        with patch(
            "FlatCAMObj.QtWidgets.QFileDialog.getSaveFileName",
            side_effect=fake_dialog,
        ):
            cnc.on_exportgcode_button_click()
        self.assertTrue(captured["start"].replace("\\", "/").endswith(".nc"))

    def test_existing_extension_is_kept(self):
        cnc = self._cnc_with_ui()
        dest_dir = tempfile.mkdtemp()
        named = os.path.join(dest_dir, "already.gcode")
        with patch(
            "FlatCAMObj.QtWidgets.QFileDialog.getSaveFileName",
            return_value=(named, "G-Code (*.gcode)"),
        ):
            cnc.on_exportgcode_button_click()
        self.assertTrue(os.path.isfile(named))
        self.assertFalse(os.path.isfile(named + ".gcode"))
        assert_file_safe(self, named, cnc.z_cut, cnc.z_move)
        os.remove(named)

    def test_form_preamble_postamble_and_unused_processor(self):
        cnc = self._cnc_with_ui()
        cnc.ui.prepend_text.set_value("(FORM-PRE)")
        cnc.ui.append_text.set_value("(FORM-POST)")
        cnc.ui.process_script.set_value("(PROCESSOR-SHOULD-NOT-RUN)")
        dest_dir = tempfile.mkdtemp()
        named = os.path.join(dest_dir, "form.gcode")
        with patch(
            "FlatCAMObj.QtWidgets.QFileDialog.getSaveFileName",
            return_value=(named, "G-Code (*.gcode)"),
        ):
            cnc.on_exportgcode_button_click()
        text = assert_file_safe(self, named, cnc.z_cut, cnc.z_move)
        self.assertIn("(FORM-PRE)", text)
        self.assertIn("(FORM-POST)", text)
        # processor argument is accepted but not applied (documented).
        self.assertNotIn("(PROCESSOR-SHOULD-NOT-RUN)", text)
        os.remove(named)


# ---------------------------------------------------------------------------
# 4. generatecncjob + Excellon Create CNC / mill-holes
# ---------------------------------------------------------------------------

class TestGenerateCncAndExcellonUi(_AppTestBase):
    def test_generatecncjob_sync_overrides_and_tolerance(self):
        geo = self._make_line_geometry("tol_geo")
        self.fc.options["cncjob_path_tolerance"] = 0.05
        recorded = {}
        orig = CNCjob.generate_from_geometry_2

        def spy(self_job, geometry, **kwargs):
            recorded.update(kwargs)
            return orig(self_job, geometry, **kwargs)

        CNCjob.generate_from_geometry_2 = spy
        try:
            geo.generatecncjob(
                use_thread=False,
                z_cut=-0.12,
                z_move=6.0,
                feedrate=110,
                tooldia=0.3,
                multidepth=True,
                depthperpass=0.06,
                outname="tol_cnc",
            )
        finally:
            CNCjob.generate_from_geometry_2 = orig

        self.assertAlmostEqual(recorded.get("tolerance"), 0.05)
        self.assertTrue(recorded.get("multidepth"))
        self.assertAlmostEqual(float(recorded.get("depthpercut")), 0.06)
        cnc = self.fc.collection.get_by_name("tol_cnc")
        self.assertAlmostEqual(float(cnc.z_cut), -0.12)
        self.assertAlmostEqual(float(cnc.z_move), 6.0)
        self.assertAlmostEqual(float(cnc.options["tooldia"]), 0.3)
        assert_safe_gcode(cnc.gcode, cnc.z_cut, cnc.z_move)

    def test_positive_cut_depth_writes_negative_z(self):
        """A typed depth of 0.1 mm must cut at Z-0.1, not mill in air at Z+0.1."""
        geo = self._make_line_geometry("depth_geo", coords=((0, 0), (5, 0)))
        geo.build_ui()
        geo.ui.cutz_entry.set_value("0.1mm")
        geo.ui.travelz_entry.set_value("5mm")
        geo.read_form()
        geo.generatecncjob(use_thread=False, outname="depth_cnc")
        cnc = self.fc.collection.get_by_name("depth_cnc")
        self.assertAlmostEqual(float(cnc.z_cut), -0.1, places=5)
        self.assertIn("Z-0.1000", cnc.gcode)
        self.assertNotIn("G01 Z0.1000", cnc.gcode)
        assert_safe_gcode(cnc.gcode, cnc.z_cut, cnc.z_move)

    def test_generatecncjob_default_tolerance_when_unset(self):
        geo = self._make_line_geometry("def_geo")
        self.fc.options.pop("cncjob_path_tolerance", None)
        recorded = {}
        orig = CNCjob.generate_from_geometry_2

        def spy(self_job, geometry, **kwargs):
            recorded["tolerance"] = kwargs.get("tolerance")
            return orig(self_job, geometry, **kwargs)

        CNCjob.generate_from_geometry_2 = spy
        try:
            geo.generatecncjob(use_thread=False, outname="def_cnc")
        finally:
            CNCjob.generate_from_geometry_2 = orig
        self.assertIsNotNone(recorded.get("tolerance"))
        self.assertGreater(float(recorded["tolerance"]), 0)

    def test_generatecncjob_threaded(self):
        geo = self._make_line_geometry("thr_geo")
        geo.generatecncjob(
            use_thread=True, z_cut=-0.06, z_move=5, feedrate=100, outname="thr_cnc"
        )
        cnc = self._wait_name("thr_cnc")
        self.assertIsInstance(cnc, FlatCAMCNCjob)
        assert_safe_gcode(cnc.gcode, cnc.z_cut, cnc.z_move)

    def test_generatecncjob_traced_polygon_multidepth(self):
        def init(obj, app):
            obj.solid_geometry = [Polygon([(0, 0), (10, 0), (10, 6), (0, 6)])]
            obj.units = "MM"

        self.fc.new_object("geometry", "poly_geo", init)
        geo = self.fc.collection.get_by_name("poly_geo")
        self.assertIsInstance(geo, FlatCAMGeometry)
        geo.generatecncjob(
            use_thread=False,
            z_cut=-1.6,
            z_move=5.0,
            feedrate=80,
            tooldia=0.79375,
            multidepth=True,
            depthperpass=0.2,
            traceoffset="outside",
            outname="poly_cnc",
        )
        cnc = self.fc.collection.get_by_name("poly_cnc")
        self.assertIsInstance(cnc, FlatCAMCNCjob)
        assert_safe_gcode(cnc.gcode, cnc.z_cut, cnc.z_move)
        self.assertIn("G01", cnc.gcode)
        self.assertIn("Z-1.6000", cnc.gcode)

    def test_add_drill_points_and_generate(self):
        def init(obj, app):
            obj.tools = {}
            obj.drills = []
            obj.solid_geometry = []

        self.fc.new_object("excellon", "manual_holes", init)
        exc = self.fc.collection.get_by_name("manual_holes")
        self.assertIsInstance(exc, FlatCAMExcellon)
        exc.add_drill(1.0, 1.0, diameter=0.8)
        exc.add_drill(4.0, 2.0, diameter=0.8)
        exc.options["drillz"] = -1.6
        exc.options["travelz"] = 5.0
        exc.options["feedrate"] = 80
        exc.options["multidepth"] = True
        exc.options["depthperpass"] = 0.4
        exc.build_ui()
        exc.ui.tools_table.selectColumn(0)
        exc.on_create_cncjob_button_click()
        cnc = self._wait_name("manual_holes_cnc")
        self.assertIsInstance(cnc, FlatCAMCNCjob)
        assert_safe_gcode(cnc.gcode, cnc.z_cut, cnc.z_move)
        self.assertIn("X1.0000Y1.0000", cnc.gcode.replace(" ", ""))
        self.assertIn("X4.0000Y2.0000", cnc.gcode.replace(" ", ""))

    def test_dark_mode_toggle_does_not_crash(self):
        self.fc.apply_theme(True, replot=True)
        self.assertTrue(self.fc.dark_mode)
        self.fc.apply_theme(False, replot=True)
        self.assertFalse(self.fc.dark_mode)

    def test_excellon_create_cnc_no_tools_selected(self):
        self.fc.open_excellon(os.path.join(ROOT, "tests", "excellon_files", "case1.drl"))
        pump(self.qapp, 0.4)
        names = [n for n in self.fc.collection.get_names() if n.endswith(".drl") or "case1" in n]
        self.assertTrue(names, self.fc.collection.get_names())
        exc = self.fc.collection.get_by_name(names[0])
        self.assertIsInstance(exc, FlatCAMExcellon)
        exc.build_ui()
        exc.ui.tools_table.clearSelection()
        msgs = []
        self.fc.inform.connect(lambda m: msgs.append(str(m)))
        before = list(self.fc.collection.get_names())
        exc.on_create_cncjob_button_click()
        self.assertEqual(self.fc.collection.get_names(), before)
        self.assertTrue(any("select" in m.lower() for m in msgs), msgs)

    def test_excellon_create_cnc_all_tools_is_safe(self):
        self.fc.open_excellon(os.path.join(ROOT, "tests", "excellon_files", "case1.drl"))
        pump(self.qapp, 0.4)
        names = self.fc.collection.get_names()
        exc = self.fc.collection.get_by_name(names[0])
        exc.build_ui()
        exc.ui.tools_table.selectAll()
        exc.on_create_cncjob_button_click()
        cnc_name = exc.options["name"] + "_cnc"
        cnc = self._wait_name(cnc_name)
        self.assertIsInstance(cnc, FlatCAMCNCjob)
        assert_safe_gcode(cnc.gcode, cnc.z_cut, cnc.z_move)

    def test_generate_milling_no_tools(self):
        self.fc.open_excellon(os.path.join(ROOT, "tests", "excellon_files", "case1.drl"))
        pump(self.qapp, 0.4)
        exc = self.fc.collection.get_by_name(self.fc.collection.get_names()[0])
        ok, msg = exc.generate_milling(tools=[])
        self.assertFalse(ok)
        self.assertIn("No tools", msg)

    def test_generate_milling_tool_larger_than_hole(self):
        self.fc.open_excellon(os.path.join(ROOT, "tests", "excellon_files", "case1.drl"))
        pump(self.qapp, 0.4)
        exc = self.fc.collection.get_by_name(self.fc.collection.get_names()[0])
        tool = next(iter(exc.tools))
        hole_dia = float(exc.tools[tool]["C"])
        ok, msg = exc.generate_milling(tools=[tool], tooldia=hole_dia + 1.0)
        self.assertFalse(ok)
        self.assertIn("larger than hole", msg)

    def test_gerber_cutout_copies_endmill_to_cnc(self):
        def init(obj, app):
            obj.solid_geometry = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)])
            obj.units = "MM"

        self.fc.new_object("gerber", "board", init)
        gerber = self.fc.collection.get_by_name("board")
        self.assertIsInstance(gerber, FlatCAMGerber)
        gerber.build_ui()
        gerber.ui.cutout_tooldia_entry.set_value(0.79375)
        gerber.ui.cutout_margin_entry.set_value(0.2)
        gerber.ui.cutout_gap_entry.set_value(1.0)
        gerber.ui.gaps_radio.set_value("4")
        gerber.on_generatecutout_button_click()
        geo = self.fc.collection.get_by_name("board_cutout")
        self.assertIsInstance(geo, FlatCAMGeometry)
        self.assertAlmostEqual(float(geo.options["cnctooldia"]), 0.79375, places=5)
        geo.generatecncjob(
            use_thread=False,
            z_cut=-1.6,
            z_move=5.0,
            feedrate=80,
            outname="board_cutout_cnc",
        )
        cnc = self.fc.collection.get_by_name("board_cutout_cnc")
        self.assertIsInstance(cnc, FlatCAMCNCjob)
        self.assertAlmostEqual(float(cnc.options["tooldia"]), 0.79375, places=5)
        self.assertAlmostEqual(float(cnc.tooldia), 0.79375, places=5)
        assert_safe_gcode(cnc.gcode, cnc.z_cut, cnc.z_move)

    def test_inch_cutout_keeps_thirty_second_inch_bit(self):
        self.fc.exec_command_test("set_sys units IN")
        self.fc.exec_command_test("new")

        def init(obj, app):
            obj.solid_geometry = Polygon([(0, 0), (4, 0), (4, 3), (0, 3)])
            obj.units = "IN"

        self.fc.new_object("gerber", "inch_board", init)
        gerber = self.fc.collection.get_by_name("inch_board")
        gerber.build_ui()
        gerber.ui.cutout_tooldia_entry.set_value("0.03125in")
        gerber.ui.cutout_margin_entry.set_value("0.01in")
        gerber.ui.cutout_gap_entry.set_value("0.05in")
        gerber.ui.gaps_radio.set_value("4")
        gerber.on_generatecutout_button_click()
        geo = self.fc.collection.get_by_name("inch_board_cutout")
        self.assertAlmostEqual(float(geo.options["cnctooldia"]), 0.79375, places=5)
        geo.generatecncjob(
            use_thread=False,
            z_cut=-1.6,
            z_move=5.0,
            feedrate=80,
            outname="inch_board_cutout_cnc",
        )
        cnc = self.fc.collection.get_by_name("inch_board_cutout_cnc")
        self.assertAlmostEqual(float(cnc.tooldia), 0.79375, places=5)
        self.assertIn("G21", cnc.gcode)

    def test_tcl_cutout_sets_cnctooldia(self):
        def init(obj, app):
            obj.solid_geometry = Polygon([(0, 0), (15, 0), (15, 8), (0, 8)])
            obj.units = "MM"

        self.fc.new_object("gerber", "tcl_board", init)
        self.fc.exec_command_test(
            "cutout tcl_board -dia 0.79375 -margin 0.2 -gapsize 1.0 -gaps 4"
        )
        geo = self.fc.collection.get_by_name("tcl_board_cutout")
        self.assertIsInstance(geo, FlatCAMGeometry)
        self.assertAlmostEqual(float(geo.options["cnctooldia"]), 0.79375, places=5)
        self.assertFalse(geo.solid_geometry.is_empty)

    def test_display_units_do_not_rescale_tools(self):
        before = float(self.fc.options["gerber_cutouttooldia"])
        geo = self._make_line_geometry("stay_geo", coords=((0, 0), (10, 0)))
        b0 = geo.bounds()
        self.fc.options_form.units_radio.set_value("IN")
        self.assertAlmostEqual(
            float(self.fc.options["gerber_cutouttooldia"]), before, places=6
        )
        self.assertEqual(str(self.fc.options["units"]).upper(), "IN")
        self.assertEqual(geo.bounds(), b0)
        self.assertEqual(str(geo.units).upper(), "MM")

    def test_mixed_inch_bit_and_mm_depth(self):
        geo = self._make_line_geometry("mix_geo")
        geo.build_ui()
        geo.ui.cnctooldia_entry.set_value("1/32in")
        geo.ui.cutz_entry.set_value("-1.45mm")
        geo.read_form()
        self.assertAlmostEqual(float(geo.options["cnctooldia"]), 0.79375, places=5)
        self.assertAlmostEqual(float(geo.options["cutz"]), -1.45, places=5)
        self.assertEqual(geo.options["length_units"]["cnctooldia"], "IN")
        self.assertEqual(geo.options["length_units"]["cutz"], "MM")
        geo.ui.travelz_entry.set_value("5mm")
        geo.ui.cncfeedrate_entry.set_value("120mm")
        geo.read_form()
        geo.generatecncjob(use_thread=False, outname="mix_geo_cnc")
        cnc = self.fc.collection.get_by_name("mix_geo_cnc")
        self.assertIn("G21", cnc.gcode)
        self.assertIn("Z-1.4500", cnc.gcode)
        self.assertAlmostEqual(float(cnc.tooldia), 0.79375, places=5)
        assert_safe_gcode(cnc.gcode, cnc.z_cut, cnc.z_move)

    def test_open_inch_gerber_is_stored_in_mm(self):
        self.fc.open_gerber(GERBER)
        pump(self.qapp, 0.3)
        gerber = self.fc.collection.get_by_name("simple1.gbr")
        self.assertIsInstance(gerber, FlatCAMGerber)
        self.assertEqual(str(gerber.units).upper(), "MM")
        minx, miny, maxx, maxy = gerber.bounds()
        width = maxx - minx
        # simple1 is ~0.55 in. Unconverted inches ≈ 0.55; once to mm ≈ 14;
        # converted twice ≈ 350.
        self.assertGreater(width, 5.0)
        self.assertLess(width, 50.0)

    def test_export_follows_display_units(self):
        geo = self._make_line_geometry("exp_geo")
        geo.generatecncjob(
            use_thread=False, z_cut=-1.6, z_move=25.4, feedrate=254,
            outname="exp_cnc",
        )
        cnc = self.fc.collection.get_by_name("exp_cnc")
        self.assertIn("G21", cnc.gcode)
        self.fc.options["units"] = "IN"
        text = cnc.get_gcode()
        self.assertIn("G20", text)
        self.assertNotIn("G21\n", text)
        self.assertIn("G21", cnc.gcode)
        self.assertNotIn("Z-1.6000", text)
        from gcode_safety import parse_gcode_words as _pw
        inch_z = min(
            _pw(line)["Z"] for line in text.splitlines() if "Z" in _pw(line)
        )
        self.assertAlmostEqual(inch_z, -1.6 / 25.4, places=3)

    def test_add_point_to_geometry(self):
        geo = self._make_line_geometry("pts")
        geo.add_point((1.5, 2.5))
        found = False
        geoms = geo.solid_geometry
        if not isinstance(geoms, list):
            geoms = [geoms]
        for part in geoms:
            if getattr(part, "geom_type", None) == "Point":
                self.assertAlmostEqual(part.x, 1.5, places=5)
                self.assertAlmostEqual(part.y, 2.5, places=5)
                found = True
        self.assertTrue(found, "add_point did not insert a Point")

    def test_generate_milling_success(self):
        self.fc.open_excellon(os.path.join(ROOT, "tests", "excellon_files", "case1.drl"))
        pump(self.qapp, 0.4)
        exc = self.fc.collection.get_by_name(self.fc.collection.get_names()[0])
        # Pick the largest hole so a small endmill is guaranteed to fit.
        tool = max(exc.tools, key=lambda t: float(exc.tools[t]["C"]))
        hole_dia = float(exc.tools[tool]["C"])
        ok, msg = exc.generate_milling(
            tools=[tool], tooldia=hole_dia / 4.0, outname="case1_mill"
        )
        self.assertTrue(ok, msg)
        mill = self._wait_name("case1_mill")
        self.assertIsInstance(mill, FlatCAMGeometry)
        self.assertTrue(mill.solid_geometry)


# ---------------------------------------------------------------------------
# 5. End-to-end safety on real manufacturing files
# ---------------------------------------------------------------------------

class TestRealFileExportSafety(_AppTestBase):
    def test_simple1_gerber_isolation_export_is_safe(self):
        self.fc.open_gerber(os.path.join(ROOT, "tests", "gerber_files", "simple1.gbr"))
        pump(self.qapp, 0.3)
        gerber = self.fc.collection.get_by_name("simple1.gbr")
        self.assertIsInstance(gerber, FlatCAMGerber)
        gerber.isolate(dia=0.3, passes=1, combine=True)
        geo = self.fc.collection.get_by_name("simple1.gbr_iso")
        geo.generatecncjob(
            use_thread=False, z_cut=-0.06, z_move=5, feedrate=120
        )
        cnc = self.fc.collection.get_by_name("simple1.gbr_iso_cnc")
        fd, path = tempfile.mkstemp(suffix=".gcode")
        os.close(fd)
        try:
            cnc.export_gcode(path)
            assert_file_safe(self, path, cnc.z_cut, cnc.z_move)
        finally:
            if os.path.isfile(path):
                os.remove(path)

    def test_case1_excellon_export_is_safe(self):
        self.fc.open_excellon(os.path.join(ROOT, "tests", "excellon_files", "case1.drl"))
        pump(self.qapp, 0.4)
        exc = self.fc.collection.get_by_name(self.fc.collection.get_names()[0])
        self.fc.exec_command_test(
            'drillcncjob "%s" -tools all -drillz -1.8 -travelz 5 -feedrate 80'
            % exc.options["name"]
        )
        cnc = self.fc.collection.get_by_name(exc.options["name"] + "_cnc")
        fd, path = tempfile.mkstemp(suffix=".gcode")
        os.close(fd)
        try:
            cnc.export_gcode(path)
            text = assert_file_safe(self, path, cnc.z_cut, cnc.z_move)
            self.assertGreater(text.count("G01 Z"), 0)
        finally:
            if os.path.isfile(path):
                os.remove(path)

    def test_kb2040_front_copper_and_pth_are_safe(self):
        fcu = os.path.join(KB2040_DIR, "KB2040-F_Cu.gbr")
        pth = os.path.join(KB2040_DIR, "KB2040-PTH.drl")
        self.assertTrue(os.path.isfile(fcu), fcu)
        self.assertTrue(os.path.isfile(pth), pth)

        self.fc.open_gerber(fcu)
        pump(self.qapp, 0.4)
        gerber = self.fc.collection.get_by_name("KB2040-F_Cu.gbr")
        gerber.isolate(dia=0.2, passes=1, overlap=0.15, combine=True)
        geo = self._wait_name("KB2040-F_Cu.gbr_iso")
        geo.generatecncjob(
            use_thread=False, z_cut=-0.06, z_move=5, feedrate=120, tooldia=0.2
        )
        iso_cnc = self.fc.collection.get_by_name("KB2040-F_Cu.gbr_iso_cnc")
        fd, path = tempfile.mkstemp(prefix="kb2040_iso_", suffix=".gcode")
        os.close(fd)
        try:
            iso_cnc.export_gcode(path)
            assert_file_safe(self, path, iso_cnc.z_cut, iso_cnc.z_move)
        finally:
            if os.path.isfile(path):
                os.remove(path)

        self.fc.open_excellon(pth)
        pump(self.qapp, 0.5)
        exc = self.fc.collection.get_by_name("KB2040-PTH.drl")
        self.assertIsInstance(exc, FlatCAMExcellon)
        self.fc.exec_command_test(
            'drillcncjob "KB2040-PTH.drl" -tools all -drillz -1.8 '
            "-travelz 5 -feedrate 80"
        )
        drill_cnc = self.fc.collection.get_by_name("KB2040-PTH.drl_cnc")
        fd, path = tempfile.mkstemp(prefix="kb2040_pth_", suffix=".gcode")
        os.close(fd)
        try:
            drill_cnc.export_gcode(path)
            assert_file_safe(self, path, drill_cnc.z_cut, drill_cnc.z_move)
        finally:
            if os.path.isfile(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
