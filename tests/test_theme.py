"""Dark-mode contrast: no black-on-black text, WCAG-ish pairs."""
from __future__ import annotations

import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import theme


class TestThemeContrast(unittest.TestCase):
    def test_dark_pairs_readable(self):
        theme.assert_theme_readable(dark=True)

    def test_light_pairs_readable(self):
        theme.assert_theme_readable(dark=False)

    def test_dark_stylesheet_has_no_black_text(self):
        self.assertFalse(theme.dark_stylesheet_has_black_text())

    def test_dark_foregrounds_are_not_black(self):
        for name, fg, bg in theme.text_background_pairs(dark=True):
            self.assertNotIn(fg.lower(), ("#000", "#000000", "black"), name)
            self.assertGreater(theme.contrast_ratio(fg, bg), 2.9, name)

    def test_plot_annotation_is_one_third_of_prior_size(self):
        self.assertEqual(theme.PLOT_ANNOTATION_FONTSIZE, 12)
        self.assertEqual(theme.PLOT_FONTSIZE, 12)

    def test_window_text_vs_window_is_aa(self):
        p = theme.DARK
        self.assertGreaterEqual(
            theme.contrast_ratio(p["window_text"], p["window"]), 4.5
        )
        self.assertGreaterEqual(
            theme.contrast_ratio(p["input_text"], p["input"]), 4.5
        )
        self.assertGreaterEqual(
            theme.contrast_ratio(p["tick"], p["canvas"]), 4.5
        )


class TestParkScrollWidget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6 import QtWidgets
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    def test_swap_does_not_delete_previous(self):
        from PySide6 import QtWidgets
        from FlatCAMCommon import park_scroll_widget, qt_widget_alive

        scroll = QtWidgets.QScrollArea()
        a = QtWidgets.QLabel("A")
        b = QtWidgets.QLabel("B")
        park_scroll_widget(scroll, a)
        park_scroll_widget(scroll, b)
        self.assertTrue(qt_widget_alive(a))
        self.assertTrue(qt_widget_alive(b))
        self.assertIs(scroll.widget(), b)
        park_scroll_widget(scroll, a)
        self.assertTrue(qt_widget_alive(a))
        self.assertTrue(qt_widget_alive(b))
        self.assertIs(scroll.widget(), a)


class TestThemeQt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6 import QtWidgets
        cls.qapp = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    def test_apply_qt_theme_sets_light_text_on_dark_window(self):
        from PySide6 import QtGui
        theme.apply_qt_theme(self.qapp, dark=True)
        pal = self.qapp.palette()
        window = pal.color(QtGui.QPalette.ColorRole.Window)
        text = pal.color(QtGui.QPalette.ColorRole.WindowText)
        self.assertLess(window.lightness(), 80)
        self.assertGreater(text.lightness(), 180)
        disabled = pal.color(
            QtGui.QPalette.ColorGroup.Disabled,
            QtGui.QPalette.ColorRole.WindowText,
        )
        self.assertGreater(disabled.lightness(), 120)
        self.assertNotEqual(text.rgb() & 0xFFFFFF, 0)

    def test_apply_qt_theme_light_restores_dark_text(self):
        from PySide6 import QtGui
        theme.apply_qt_theme(self.qapp, dark=False)
        pal = self.qapp.palette()
        text = pal.color(QtGui.QPalette.ColorRole.WindowText)
        self.assertLess(text.lightness(), 80)
