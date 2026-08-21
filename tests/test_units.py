"""Mixed-unit lengths: millimetre storage, per-field display units."""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import units
import flatcam_defaults as d


class TestParseFormat(unittest.TestCase):
    def test_bare_mm(self):
        mm, unit = units.parse_length("1.45", default_unit="MM")
        self.assertAlmostEqual(mm, 1.45)
        self.assertEqual(unit, "MM")

    def test_inch_suffix(self):
        mm, unit = units.parse_length("0.005in")
        self.assertAlmostEqual(mm, 0.005 * 25.4, places=8)
        self.assertEqual(unit, "IN")
        mm2, unit2 = units.parse_length("0.005 in")
        self.assertAlmostEqual(mm2, mm)
        self.assertEqual(unit2, "IN")

    def test_fraction_inch(self):
        mm, unit = units.parse_length("1/32in")
        self.assertAlmostEqual(mm, 0.03125 * 25.4, places=8)
        self.assertEqual(unit, "IN")
        mm2, _ = units.parse_length('1/32"')
        self.assertAlmostEqual(mm2, mm, places=8)

    def test_mm_suffix_on_default_inch_field(self):
        mm, unit = units.parse_length("1.45mm", default_unit="IN")
        self.assertAlmostEqual(mm, 1.45)
        self.assertEqual(unit, "MM")

    def test_format_round_trip(self):
        self.assertEqual(units.format_length(0.005 * 25.4, "IN"), "0.005 in")
        self.assertEqual(units.format_length(1.45, "MM"), "1.45 mm")
        self.assertEqual(units.format_length(0.79375, "IN"), "0.03125 in")

    def test_bad_text_raises(self):
        with self.assertRaises(ValueError):
            units.parse_length("nope")


class TestStorageMigration(unittest.TestCase):
    def test_inch_saved_defaults_become_mm(self):
        opts = {
            "units": "IN",
            "gerber_cutouttooldia": 0.03125,
            "stock_width": 100.0 / 25.4,
            "stock_height": 70.0 / 25.4,
        }
        units.migrate_storage_to_mm(opts, d.DIMENSIONAL_OPTION_KEYS)
        self.assertEqual(opts["storage_units"], "MM")
        self.assertEqual(opts["units"], "IN")
        self.assertAlmostEqual(opts["gerber_cutouttooldia"], 0.79375, places=5)
        self.assertAlmostEqual(opts["stock_width"], 100.0, places=4)

    def test_already_mm_is_left_alone(self):
        opts = {
            "units": "IN",
            "storage_units": "MM",
            "gerber_cutouttooldia": 0.79375,
        }
        units.migrate_storage_to_mm(opts, d.DIMENSIONAL_OPTION_KEYS)
        self.assertAlmostEqual(opts["gerber_cutouttooldia"], 0.79375, places=5)

    def test_mm_project_not_scaled(self):
        opts = {"units": "MM", "gerber_cutouttooldia": 0.79375, "stock_width": 100.0}
        units.migrate_storage_to_mm(opts, d.DIMENSIONAL_OPTION_KEYS)
        self.assertAlmostEqual(opts["gerber_cutouttooldia"], 0.79375, places=5)
        self.assertEqual(opts["storage_units"], "MM")


class TestMillProfileDefaults(unittest.TestCase):
    def test_isolation_defaults(self):
        mm = d.defaults_for_units("MM")
        self.assertAlmostEqual(mm["geometry_cutz"], -0.1)
        self.assertAlmostEqual(mm["geometry_feedrate"], 400.0)
        self.assertEqual(mm["geometry_spindlespeed"], 13000)
        geo = d.object_option_defaults("geometry")
        self.assertAlmostEqual(geo["cutz"], -0.1)
        self.assertAlmostEqual(geo["feedrate"], 400.0)
        self.assertEqual(geo["spindlespeed"], 13000)

    def test_migrate_replaces_old_official_profile(self):
        opts = {
            "geometry_cutz": -0.06,
            "geometry_feedrate": 120.0,
            "geometry_spindlespeed": None,
            "excellon_spindlespeed": None,
        }
        d.migrate_mill_profile_defaults(opts)
        self.assertAlmostEqual(opts["geometry_cutz"], -0.1)
        self.assertAlmostEqual(opts["geometry_feedrate"], 400.0)
        self.assertEqual(opts["geometry_spindlespeed"], 13000)
        self.assertEqual(opts["excellon_spindlespeed"], 13000)

    def test_migrate_keeps_custom_feed_and_depth(self):
        opts = {
            "geometry_cutz": -1.45,
            "geometry_feedrate": 254.0,
            "geometry_spindlespeed": 8000,
            "excellon_spindlespeed": 9000,
        }
        d.migrate_mill_profile_defaults(opts)
        self.assertAlmostEqual(opts["geometry_cutz"], -1.45)
        self.assertAlmostEqual(opts["geometry_feedrate"], 254.0)
        self.assertEqual(opts["geometry_spindlespeed"], 8000)
        self.assertEqual(opts["excellon_spindlespeed"], 9000)


class TestGcodeExportUnits(unittest.TestCase):
    def test_mm_to_in_rewrites_header_and_xy(self):
        g = "G21\nG90\nF254.00\nG00 Z25.4000\nG00 X25.4000Y0.0000\nM05\n"
        out = units.convert_gcode_units(g, "MM", "IN")
        self.assertIn("G20", out)
        self.assertNotIn("G21\n", out)
        self.assertIn("X1.0000", out)
        self.assertIn("Z1.0000", out)
        self.assertIn("F10.00", out)

    def test_same_units_identity(self):
        g = "G21\nG00 X1.0000Y2.0000\n"
        self.assertEqual(units.convert_gcode_units(g, "MM", "MM"), g)


class TestLengthEntryMixedUnits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6 import QtWidgets
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    def test_typed_inch_returns_mm_keeps_suffix(self):
        from GUIElements import LengthEntry
        e = LengthEntry()
        e.set_value("0.005in")
        self.assertEqual(e.display_units, "IN")
        self.assertAlmostEqual(e.get_value(), 0.005 * 25.4, places=8)
        self.assertIn("in", e.text().lower())
        self.assertIn("0.005", e.text())

    def test_typed_mm_on_inch_field(self):
        from GUIElements import LengthEntry
        e = LengthEntry(output_units="IN")
        e.set_value("1.45mm")
        self.assertEqual(e.display_units, "MM")
        self.assertAlmostEqual(e.get_value(), 1.45, places=6)
        self.assertIn("mm", e.text().lower())

    def test_number_is_mm(self):
        from GUIElements import LengthEntry
        e = LengthEntry(output_units="IN")
        e.set_value(0.79375)
        self.assertAlmostEqual(e.get_value(), 0.79375, places=5)
        self.assertIn("0.03125", e.text())

    def test_bare_typed_number_follows_field_unit(self):
        from GUIElements import LengthEntry
        e = LengthEntry(output_units="IN")
        e.setText("0.005")
        self.assertAlmostEqual(e.get_value(), 0.005 * 25.4, places=8)
        e2 = LengthEntry(output_units="MM")
        e2.setText("1.45")
        self.assertAlmostEqual(e2.get_value(), 1.45, places=6)

    def _assert_entry_converts(self, entry, name):
        entry.set_value("1/32in")
        self.assertAlmostEqual(
            entry.get_value(), 0.79375, places=5, msg="%s 1/32in" % name
        )
        entry.set_value("-1.45mm")
        self.assertAlmostEqual(
            entry.get_value(), -1.45, places=5, msg="%s -1.45mm" % name
        )
        entry.set_value("0.005in")
        self.assertAlmostEqual(
            entry.get_value(), 0.127, places=4, msg="%s 0.005in" % name
        )

    def test_every_object_and_options_length_entry(self):
        from GUIElements import LengthEntry
        from ObjectUI import (
            CNCObjectUI,
            ExcellonObjectUI,
            GeometryObjectUI,
            GerberObjectUI,
        )
        from FlatCAMGUI import GlobalOptionsUI

        roots = {
            "GerberObjectUI": GerberObjectUI(),
            "GeometryObjectUI": GeometryObjectUI(),
            "ExcellonObjectUI": ExcellonObjectUI(),
            "CNCObjectUI": CNCObjectUI(),
            "GlobalOptionsUI": GlobalOptionsUI(),
        }
        found = []
        for name, root in roots.items():
            kids = root.findChildren(LengthEntry)
            self.assertGreater(len(kids), 0, name)
            for i, entry in enumerate(kids):
                self._assert_entry_converts(entry, "%s[%d]" % (name, i))
                found.append(entry)
        # Isolation, cutout, Z, feed, paint, stock-related options, CNC plot.
        self.assertGreaterEqual(len(found), 30)

    def test_preferred_keys_cover_dimensional_cam_fields(self):
        for key in (
            "gerber_isotooldia",
            "gerber_cutouttooldia",
            "geometry_cutz",
            "geometry_cnctooldia",
            "excellon_drillz",
            "excellon_tooldia",
            "cncjob_tooldia",
            "stock_width",
        ):
            self.assertIn(key, units.PREFERRED_LENGTH_UNITS)
