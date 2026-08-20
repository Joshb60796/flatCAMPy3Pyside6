############################################################
# FlatCAM: GUI theme (light / dark)                        #
############################################################
"""Application theme: palettes, stylesheets, matplotlib, contrast checks.

Dark mode is designed so no text, tick, or placeholder is black-on-black.
All primary text/background pairs meet WCAG AA contrast (>= 4.5:1).
Disabled text is still well above 3:1 against the window background.
"""

from __future__ import annotations

import re

from PySide6 import QtGui, QtWidgets

# Matplotlib plot text. Default ~10pt on a 50-DPI canvas is ~7px.
# 12pt is about 1/3 of the previous 36pt labels.
PLOT_FONTSIZE = 12
PLOT_ANNOTATION_FONTSIZE = 12


# Never use #000000 as a foreground in dark mode.
DARK = {
    "window": "#1e1e1e",
    "window_text": "#e8e8e8",
    "base": "#252526",
    "alternate_base": "#2d2d30",
    "text": "#e8e8e8",
    "button": "#3c3c3c",
    "button_text": "#f2f2f2",
    "highlight": "#0e639c",
    "highlighted_text": "#ffffff",
    "tooltip_base": "#2b2b2b",
    "tooltip_text": "#f2f2f2",
    "bright_text": "#ff8a80",
    "link": "#4fc1ff",
    "disabled_text": "#a0a0a0",
    "disabled_button_text": "#a0a0a0",
    "border": "#5a5a5a",
    "input": "#2a2a2a",
    "input_text": "#f2f2f2",
    "placeholder": "#b4b4b4",
    "tab": "#2b2b2b",
    "tab_selected": "#3a3a3a",
    "canvas": "#1a1a1a",
    "grid": "#4a4a4a",
    "axis": "#c8c8c8",
    "tick": "#d4d4d4",
    "geometry": "#5cdb95",
    "draw_normal": "#4da6ff",
    "draw_selected": "#ffe66d",
    "draw_utility": "#ffb347",
    "gerber_line": "#d8d8d8",
    "shell_bg": "#1e1e1e",
    "shell_fg": "#e8e8e8",
    "shell_in": "#ffffff",
    "error": "#ff8a80",
    "stock": "#38bdf8",
    "stock_overflow": "#ff8a80",
    "stock_label": "#7dd3fc",
}

LIGHT = {
    "window": "#f0f0f0",
    "window_text": "#202020",
    "base": "#ffffff",
    "alternate_base": "#f5f5f5",
    "text": "#202020",
    "button": "#e6e6e6",
    "button_text": "#202020",
    "highlight": "#0078d7",
    "highlighted_text": "#ffffff",
    "tooltip_base": "#ffffe1",
    "tooltip_text": "#202020",
    "bright_text": "#c00000",
    "link": "#0066cc",
    "disabled_text": "#6a6a6a",
    "disabled_button_text": "#6a6a6a",
    "border": "#a0a0a0",
    "input": "#ffffff",
    "input_text": "#202020",
    "placeholder": "#707070",
    "tab": "#e8e8e8",
    "tab_selected": "#ffffff",
    "canvas": "#ffffff",
    "grid": "#cccccc",
    "axis": "#000000",
    "tick": "#202020",
    "geometry": "#1F9D55",
    "draw_normal": "#1f77b4",
    "draw_selected": "#000000",
    "draw_utility": "#444444",
    "gerber_line": "#000000",
    "shell_bg": "#ffffff",
    "shell_fg": "#202020",
    "shell_in": "#000000",
    "error": "#cc0000",
    "stock": "#0369a1",
    "stock_overflow": "#b91c1c",
    "stock_label": "#0369a1",
}


def palette_for(dark):
    return DARK if dark else LIGHT


def _hex_to_rgb01(color):
    color = str(color).strip()
    if color.startswith("#"):
        color = color[1:]
    if len(color) == 3:
        color = "".join(ch * 2 for ch in color)
    if len(color) != 6:
        raise ValueError("Not a hex color: %r" % color)
    return tuple(int(color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def relative_luminance(color):
    """WCAG relative luminance of a #rrggbb color."""
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _hex_to_rgb01(color)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(fg, bg):
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter, darker = (l1, l2) if l1 >= l2 else (l2, l1)
    return (lighter + 0.05) / (darker + 0.05)


def text_background_pairs(dark=True):
    """Foreground/background pairs that must stay readable."""
    p = palette_for(dark)
    return [
        ("window_text", p["window_text"], p["window"]),
        ("text_on_base", p["text"], p["base"]),
        ("text_on_alternate", p["text"], p["alternate_base"]),
        ("button_text", p["button_text"], p["button"]),
        ("input_text", p["input_text"], p["input"]),
        ("placeholder", p["placeholder"], p["input"]),
        ("tooltip", p["tooltip_text"], p["tooltip_base"]),
        ("highlighted", p["highlighted_text"], p["highlight"]),
        ("disabled_on_window", p["disabled_text"], p["window"]),
        ("disabled_on_base", p["disabled_text"], p["base"]),
        ("disabled_button", p["disabled_button_text"], p["button"]),
        ("tick_on_canvas", p["tick"], p["canvas"]),
        ("axis_on_canvas", p["axis"], p["canvas"]),
        ("geometry_on_canvas", p["geometry"], p["canvas"]),
        ("draw_normal_on_canvas", p["draw_normal"], p["canvas"]),
        ("draw_selected_on_canvas", p["draw_selected"], p["canvas"]),
        ("draw_utility_on_canvas", p["draw_utility"], p["canvas"]),
        ("gerber_line_on_canvas", p["gerber_line"], p["canvas"]),
        ("shell", p["shell_fg"], p["shell_bg"]),
        ("shell_input", p["shell_in"], p["shell_bg"]),
        ("error_on_window", p["error"], p["window"]),
        ("stock_on_canvas", p["stock"], p["canvas"]),
        ("stock_overflow_on_canvas", p["stock_overflow"], p["canvas"]),
        ("stock_label_on_canvas", p["stock_label"], p["canvas"]),
    ]


def assert_theme_readable(dark=True, min_primary=4.5, min_secondary=3.0):
    """Raise ValueError if any designed pair is unreadable (black-on-black)."""
    secondary = {
        "placeholder",
        "disabled_on_window",
        "disabled_on_base",
        "disabled_button",
        "highlighted",
        "axis_on_canvas",
        "geometry_on_canvas",
        "draw_normal_on_canvas",
        "draw_selected_on_canvas",
        "draw_utility_on_canvas",
        "gerber_line_on_canvas",
        "stock_on_canvas",
        "stock_overflow_on_canvas",
        "stock_label_on_canvas",
    }
    problems = []
    for name, fg, bg in text_background_pairs(dark):
        ratio = contrast_ratio(fg, bg)
        need = min_secondary if name in secondary else min_primary
        if ratio < need:
            problems.append(
                "%s %s on %s contrast %.2f < %.1f" % (name, fg, bg, ratio, need)
            )
        if dark and fg.lower() in ("#000", "#000000", "black"):
            problems.append("%s uses black foreground on dark theme" % name)
    if problems:
        raise ValueError("Unreadable theme colors:\n  " + "\n  ".join(problems))
    return True


def build_stylesheet(dark=True):
    p = palette_for(dark)
    return """
    QWidget {{
        color: {window_text};
        background-color: {window};
    }}
    QMainWindow, QDialog, QDockWidget, QStatusBar, QMenuBar, QMenu, QToolBar {{
        color: {window_text};
        background-color: {window};
    }}
    QLabel, QCheckBox, QRadioButton, QGroupBox {{
        color: {window_text};
        background-color: transparent;
    }}
    QGroupBox {{
        font-size: 16px;
        font-weight: bold;
        color: {window_text};
        background-color: transparent;
    }}
    QGroupBox::title {{
        color: {window_text};
        font-size: 16px;
        font-weight: bold;
        subcontrol-origin: margin;
        left: 8px;
        padding: 0 4px;
    }}
    QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox, QComboBox {{
        color: {input_text};
        background-color: {input};
        selection-background-color: {highlight};
        selection-color: {highlighted_text};
        border: 1px solid {border};
        border-radius: 2px;
        padding: 2px;
    }}
    QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
    QAbstractSpinBox:disabled, QComboBox:disabled {{
        color: {disabled_text};
        background-color: {alternate_base};
    }}
    QTextEdit, QPlainTextEdit {{
        color: {input_text};
        background-color: {base};
    }}
    QPushButton {{
        color: {button_text};
        background-color: {button};
        border: 1px solid {border};
        border-radius: 3px;
        padding: 4px 10px;
    }}
    QPushButton:hover {{
        background-color: {tab_selected};
    }}
    QPushButton:disabled {{
        color: {disabled_button_text};
        background-color: {alternate_base};
    }}
    QToolButton {{
        color: {window_text};
        background-color: transparent;
        border: 1px solid transparent;
        padding: 2px;
    }}
    QToolButton:hover, QToolButton:checked {{
        background-color: {button};
        border: 1px solid {border};
    }}
    QTabWidget::pane {{
        border: 1px solid {border};
        background-color: {window};
    }}
    QTabBar::tab {{
        color: {window_text};
        background-color: {tab};
        border: 1px solid {border};
        padding: 5px 10px;
    }}
    QTabBar::tab:selected {{
        color: {window_text};
        background-color: {tab_selected};
    }}
    QHeaderView::section {{
        color: {window_text};
        background-color: {button};
        border: 1px solid {border};
        padding: 3px;
    }}
    QTableView, QTableWidget, QListView, QTreeView, QAbstractItemView {{
        color: {text};
        background-color: {base};
        alternate-background-color: {alternate_base};
        selection-background-color: {highlight};
        selection-color: {highlighted_text};
        border: 1px solid {border};
        outline: 0;
    }}
    QTableView::item, QListView::item, QTreeView::item {{
        color: {text};
    }}
    QTableView::item:selected, QListView::item:selected, QTreeView::item:selected {{
        color: {highlighted_text};
        background-color: {highlight};
    }}
    QMenuBar::item {{
        color: {window_text};
        background: transparent;
    }}
    QMenuBar::item:selected {{
        color: {highlighted_text};
        background-color: {highlight};
    }}
    QMenu::item {{
        color: {window_text};
        background-color: {window};
        padding: 4px 24px;
    }}
    QMenu::item:selected {{
        color: {highlighted_text};
        background-color: {highlight};
    }}
    QMenu::item:disabled {{
        color: {disabled_text};
    }}
    QMenu::separator {{
        height: 1px;
        background: {border};
    }}
    QScrollBar:vertical, QScrollBar:horizontal {{
        background: {alternate_base};
        border: none;
    }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background: {border};
        min-height: 20px;
        min-width: 20px;
        border-radius: 3px;
    }}
    QSplitter::handle {{
        background-color: {border};
    }}
    QStatusBar, QStatusBar QLabel {{
        color: {window_text};
        background-color: {window};
    }}
    QProgressBar {{
        color: {window_text};
        background-color: {base};
        border: 1px solid {border};
        text-align: center;
    }}
    QProgressBar::chunk {{
        background-color: {highlight};
    }}
    QToolTip {{
        color: {tooltip_text};
        background-color: {tooltip_base};
        border: 1px solid {border};
    }}
    QDockWidget::title {{
        color: {window_text};
        background-color: {button};
        padding: 4px;
    }}
    QComboBox QAbstractItemView {{
        color: {text};
        background-color: {base};
        selection-background-color: {highlight};
        selection-color: {highlighted_text};
    }}
    QCheckBox:disabled, QRadioButton:disabled, QLabel:disabled {{
        color: {disabled_text};
    }}
    """.format(**p)


def build_palette(dark=True):
    p = palette_for(dark)
    pal = QtGui.QPalette()

    def c(name):
        return QtGui.QColor(p[name])

    pal.setColor(QtGui.QPalette.ColorRole.Window, c("window"))
    pal.setColor(QtGui.QPalette.ColorRole.WindowText, c("window_text"))
    pal.setColor(QtGui.QPalette.ColorRole.Base, c("base"))
    pal.setColor(QtGui.QPalette.ColorRole.AlternateBase, c("alternate_base"))
    pal.setColor(QtGui.QPalette.ColorRole.Text, c("text"))
    pal.setColor(QtGui.QPalette.ColorRole.Button, c("button"))
    pal.setColor(QtGui.QPalette.ColorRole.ButtonText, c("button_text"))
    pal.setColor(QtGui.QPalette.ColorRole.Highlight, c("highlight"))
    pal.setColor(QtGui.QPalette.ColorRole.HighlightedText, c("highlighted_text"))
    pal.setColor(QtGui.QPalette.ColorRole.ToolTipBase, c("tooltip_base"))
    pal.setColor(QtGui.QPalette.ColorRole.ToolTipText, c("tooltip_text"))
    pal.setColor(QtGui.QPalette.ColorRole.BrightText, c("bright_text"))
    pal.setColor(QtGui.QPalette.ColorRole.Link, c("link"))
    pal.setColor(QtGui.QPalette.ColorRole.PlaceholderText, c("placeholder"))

    disabled = QtGui.QPalette.ColorGroup.Disabled
    pal.setColor(disabled, QtGui.QPalette.ColorRole.WindowText, c("disabled_text"))
    pal.setColor(disabled, QtGui.QPalette.ColorRole.Text, c("disabled_text"))
    pal.setColor(disabled, QtGui.QPalette.ColorRole.ButtonText, c("disabled_button_text"))
    pal.setColor(disabled, QtGui.QPalette.ColorRole.PlaceholderText, c("disabled_text"))
    return pal


_FORBIDDEN_DARK_FG = re.compile(
    r"color\s*:\s*(?:#000(?:000)?|black)\s*;",
    re.IGNORECASE,
)


def dark_stylesheet_has_black_text(qss=None):
    text = qss if qss is not None else build_stylesheet(True)
    return bool(_FORBIDDEN_DARK_FG.search(text))


def apply_qt_theme(qapp, dark=True):
    """Apply Fusion + palette + stylesheet to the QApplication."""
    if qapp is None:
        return
    qapp.setStyle("Fusion")
    qapp.setPalette(build_palette(dark))
    qapp.setStyleSheet(build_stylesheet(dark))


def style_matplotlib_axes(axes, figure=None, dark=True):
    """Color a matplotlib Axes (and optional Figure) for the theme."""
    p = palette_for(dark)
    if figure is not None:
        figure.patch.set_visible(True)
        figure.patch.set_facecolor(p["canvas"])
    if axes is None:
        return
    axes.set_facecolor(p["canvas"])
    axes.tick_params(
        colors=p["tick"], which="both", labelsize=PLOT_FONTSIZE, length=8, width=1.4
    )
    axes.xaxis.label.set_color(p["tick"])
    axes.yaxis.label.set_color(p["tick"])
    axes.xaxis.label.set_fontsize(PLOT_FONTSIZE)
    axes.yaxis.label.set_fontsize(PLOT_FONTSIZE)
    for label in axes.get_xticklabels() + axes.get_yticklabels():
        label.set_fontsize(PLOT_FONTSIZE)
    for spine in axes.spines.values():
        spine.set_color(p["axis"])
    axes.grid(True, color=p["grid"])
    for line in list(axes.lines):
        # Recolor the origin axes lines created as axhline/axvline.
        if getattr(line, "get_label", lambda: "")() in ("_nolegend_",):
            pass
    # Origin crosshair
    for artist in list(getattr(axes, "lines", [])):
        pass


def apply_plotcanvas_theme(plotcanvas, dark=True):
    if plotcanvas is None:
        return
    p = palette_for(dark)
    plotcanvas.dark_mode = bool(dark)
    if getattr(plotcanvas, "figure", None) is not None:
        plotcanvas.figure.patch.set_visible(True)
        plotcanvas.figure.patch.set_facecolor(p["canvas"])
    if getattr(plotcanvas, "axes", None) is not None:
        style_matplotlib_axes(plotcanvas.axes, plotcanvas.figure, dark)
        # Rebuild origin lines in a readable color.
        for line in list(plotcanvas.axes.lines):
            xd = line.get_xdata()
            yd = line.get_ydata()
            if len(xd) == 2 and list(xd) == [0, 0]:
                line.set_color(p["axis"])
            elif len(yd) == 2 and list(yd) == [0, 0]:
                line.set_color(p["axis"])
    canvas = getattr(plotcanvas, "canvas", None)
    if canvas is not None:
        canvas.setStyleSheet("background-color: %s; color: %s;" % (p["canvas"], p["tick"]))
        try:
            canvas.draw_idle()
        except Exception:
            pass


def apply_termwidget_theme(widget, dark=True):
    if widget is None:
        return
    p = palette_for(dark)
    qss = (
        'font: 9pt "Courier";'
        " color: %s; background-color: %s;" % (p["shell_fg"], p["shell_bg"])
    )
    browser = getattr(widget, "_browser", None)
    edit = getattr(widget, "_edit", None)
    widget._theme_fg = QtGui.QColor(p["shell_fg"])
    widget._theme_bg = QtGui.QColor(p["shell_bg"])
    if browser is not None:
        browser.setStyleSheet(qss)
        browser.setTextColor(QtGui.QColor(p["shell_fg"]))
    if edit is not None:
        edit.setStyleSheet(qss)
        try:
            edit.setTextColor(QtGui.QColor(p["shell_fg"]))
            edit.setTextBackgroundColor(QtGui.QColor(p["shell_bg"]))
        except Exception:
            pass


def geometry_plot_color(dark=True):
    return palette_for(dark)["geometry"]


def draw_linespec(role, dark=True):
    """Matplotlib format string / kwargs for the geometry editor."""
    p = palette_for(dark)
    if role == "selected":
        return {"color": p["draw_selected"], "linestyle": "-", "linewidth": 2}
    if role == "utility":
        return {"color": p["draw_utility"], "linestyle": "--", "linewidth": 1}
    return {"color": p["draw_normal"], "linestyle": "-", "linewidth": 1}


def resolve_gerber_linecolor(stored, dark=True):
    """Keep stored custom colors; replace black wireframe on a dark canvas."""
    if not dark:
        return stored
    if stored is None:
        return DARK["gerber_line"]
    key = str(stored).strip().lower()
    if key in ("#000", "#000000", "black", "k"):
        return DARK["gerber_line"]
    return stored
