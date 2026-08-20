from PySide6 import QtWidgets

from FlatCAMTool import FlatCAMTool
from GUIElements import FCCheckBox, IntEntry, LengthEntry
from stock import autofill_counts, size_of


class ToolStock(FlatCAMTool):
    """PCB material size, fit overlay, translate, and rectilinear tiling."""

    toolName = "PCB Material"

    def __init__(self, app):
        FlatCAMTool.__init__(self, app)

        title = QtWidgets.QLabel("<font size=4><b>%s</b></font>" % self.toolName)
        self.layout.addWidget(title)
        hint = QtWidgets.QLabel(
            "Stock rectangle lives at origin (0, 0).\n"
            "Open Gerber / Excellon / G-code on top of it\n"
            "to see whether the job fits, then move or tile."
        )
        hint.setWordWrap(True)
        self.layout.addWidget(hint)

        size_label = QtWidgets.QLabel("<b>Size</b>")
        self.layout.addWidget(size_label)

        form = QtWidgets.QFormLayout()
        self.layout.addLayout(form)

        self.width_entry = LengthEntry()
        self.width_entry.setToolTip(
            "Stock width (X). Bottom-left corner is (0, 0).\n"
            "Units follow the project (mm or in).\n"
            "You can type 100mm or 3.937in."
        )
        form.addRow("Width:", self.width_entry)

        self.height_entry = LengthEntry()
        self.height_entry.setToolTip(
            "Stock height (Y). Bottom-left corner is (0, 0)."
        )
        form.addRow("Height:", self.height_entry)

        self.show_cb = FCCheckBox("Show outline on plot")
        self.show_cb.setToolTip(
            "Draw the material rectangle over Gerber,\n"
            "Excellon, geometry, and G-code plots."
        )
        self.layout.addWidget(self.show_cb)

        apply_row = QtWidgets.QHBoxLayout()
        self.apply_btn = QtWidgets.QPushButton("Apply size")
        self.apply_btn.setToolTip("Update the stock outline and fit check.")
        apply_row.addWidget(self.apply_btn)
        self.layout.addLayout(apply_row)

        self.clear_btn = QtWidgets.QPushButton("Clear current design")
        self.clear_btn.setToolTip(
            "Delete the selected object(s) from the project.\n"
            "If nothing is selected, deletes every object.\n"
            "The stock outline stays."
        )
        self.layout.addWidget(self.clear_btn)

        self.fit_label = QtWidgets.QLabel("Fit: —")
        self.fit_label.setWordWrap(True)
        self.fit_label.setToolTip("Whether current objects sit inside the stock.")
        self.layout.addWidget(self.fit_label)

        self.layout.addWidget(QtWidgets.QLabel("<b>Translate</b>"))
        move_hint = QtWidgets.QLabel(
            "Place the selected design so its bottom-left\n"
            "corner sits at X, Y on the stock."
        )
        move_hint.setWordWrap(True)
        self.layout.addWidget(move_hint)

        move_form = QtWidgets.QFormLayout()
        self.layout.addLayout(move_form)
        self.x_entry = LengthEntry()
        self.y_entry = LengthEntry()
        self.x_entry.setToolTip("Target X of the design's min corner.")
        self.y_entry.setToolTip("Target Y of the design's min corner.")
        move_form.addRow("X:", self.x_entry)
        move_form.addRow("Y:", self.y_entry)

        self.place_selected_btn = QtWidgets.QPushButton("Place selected at X, Y")
        self.place_selected_btn.setToolTip(
            "Move every selected object together so the\n"
            "group's bottom-left lands at X, Y."
        )
        self.layout.addWidget(self.place_selected_btn)

        self.place_origin_btn = QtWidgets.QPushButton("Place selected at 0, 0")
        self.place_origin_btn.setToolTip(
            "Move the selected group to the stock origin."
        )
        self.layout.addWidget(self.place_origin_btn)

        self.place_all_origin_btn = QtWidgets.QPushButton("Place all at 0, 0")
        self.place_all_origin_btn.setToolTip(
            "Move every object in the project as one group\n"
            "to the stock origin."
        )
        self.layout.addWidget(self.place_all_origin_btn)

        self.layout.addWidget(QtWidgets.QLabel("<b>Tile array</b>"))
        tile_hint = QtWidgets.QLabel(
            "Copy the selected design in a grid so several\n"
            "boards come out of one sheet / one job."
        )
        tile_hint.setWordWrap(True)
        self.layout.addWidget(tile_hint)

        tile_form = QtWidgets.QFormLayout()
        self.layout.addLayout(tile_form)
        self.cols_entry = IntEntry()
        self.rows_entry = IntEntry()
        self.cols_entry.setToolTip("Number of copies in X.")
        self.rows_entry.setToolTip("Number of copies in Y.")
        tile_form.addRow("Columns:", self.cols_entry)
        tile_form.addRow("Rows:", self.rows_entry)

        self.spacing_x_entry = LengthEntry()
        self.spacing_y_entry = LengthEntry()
        self.spacing_x_entry.setToolTip("Gap between copies in X (not including the design width).")
        self.spacing_y_entry.setToolTip("Gap between copies in Y (not including the design height).")
        tile_form.addRow("Spacing X:", self.spacing_x_entry)
        tile_form.addRow("Spacing Y:", self.spacing_y_entry)

        self.margin_entry = LengthEntry()
        self.margin_entry.setToolTip(
            "Keep this much stock around the array when\n"
            "starting at the origin."
        )
        tile_form.addRow("Margin:", self.margin_entry)

        self.origin_cb = FCCheckBox("Start array at origin + margin")
        self.origin_cb.setToolTip(
            "If checked, tile (0,0) is placed at (margin, margin).\n"
            "If not, tiling grows from the design's current position."
        )
        self.origin_cb.set_value(True)
        self.layout.addWidget(self.origin_cb)

        self.fill_btn = QtWidgets.QPushButton("Fill stock")
        self.fill_btn.setToolTip(
            "Set columns and rows to the maximum that fit\n"
            "in the stock with the current spacing and margin."
        )
        self.layout.addWidget(self.fill_btn)

        self.tile_selected_btn = QtWidgets.QPushButton("Tile selected")
        self.tile_selected_btn.setToolTip(
            "Create new objects (name_tile) containing the array.\n"
            "The original design is removed so it does not sit\n"
            "under the first tile. Layers share one bounding box."
        )
        self.layout.addWidget(self.tile_selected_btn)

        self.tile_all_btn = QtWidgets.QPushButton("Tile all")
        self.tile_all_btn.setToolTip("Tile every object in the project as one design.")
        self.layout.addWidget(self.tile_all_btn)

        self.layout.addStretch()

        self.apply_btn.clicked.connect(self.on_apply)
        self.clear_btn.clicked.connect(self.on_clear_current)
        self.show_cb.stateChanged.connect(self.on_show)
        self.place_selected_btn.clicked.connect(self.on_place_selected)
        self.place_origin_btn.clicked.connect(lambda: self._place(self._selected(), 0.0, 0.0))
        self.place_all_origin_btn.clicked.connect(
            lambda: self._place(self.app.collection.get_list(), 0.0, 0.0)
        )
        self.fill_btn.clicked.connect(self.on_fill)
        self.tile_selected_btn.clicked.connect(self.on_tile_selected)
        self.tile_all_btn.clicked.connect(self.on_tile_all)

        self.load_from_app()

    def run(self):
        self.sync_units()
        self.load_from_app()
        self.refresh_fit()
        FlatCAMTool.run(self)
        self.app.inform.emit("PCB material: stock is at (0, 0).")

    def sync_units(self):
        import units as fc_units
        keys = (
            "stock_width", "stock_height", "stock_place_x", "stock_place_y",
            "stock_spacing_x", "stock_spacing_y", "stock_margin",
        )
        for entry, key in zip(
            (
                self.width_entry, self.height_entry, self.x_entry, self.y_entry,
                self.spacing_x_entry, self.spacing_y_entry, self.margin_entry,
            ),
            keys,
        ):
            entry.output_units = fc_units.unit_for_option(self.app.options, key)

    def load_from_app(self):
        self.sync_units()
        stock = self.app.stock
        self.width_entry.set_value(stock.width())
        self.height_entry.set_value(stock.height())
        self.show_cb.blockSignals(True)
        self.show_cb.set_value(stock.visible())
        self.show_cb.blockSignals(False)
        self.x_entry.set_value(self.app.options.get("stock_place_x", 0.0))
        self.y_entry.set_value(self.app.options.get("stock_place_y", 0.0))
        self.cols_entry.set_value(int(self.app.options.get("stock_columns", 1) or 1))
        self.rows_entry.set_value(int(self.app.options.get("stock_rows", 1) or 1))
        self.spacing_x_entry.set_value(self.app.options.get("stock_spacing_x", 0.0))
        self.spacing_y_entry.set_value(self.app.options.get("stock_spacing_y", 0.0))
        self.margin_entry.set_value(self.app.options.get("stock_margin", 0.0))
        self.origin_cb.set_value(bool(self.app.options.get("stock_start_origin", True)))
        self.refresh_fit()

    def _read_length(self, entry, name):
        try:
            val = entry.get_value()
        except Exception:
            val = None
        if val is None:
            raise ValueError("Enter a number for %s." % name)
        return float(val)

    def on_apply(self):
        try:
            width = self._read_length(self.width_entry, "width")
            height = self._read_length(self.height_entry, "height")
        except ValueError as exc:
            self.app.inform.emit("[warning] %s" % exc)
            return
        if width <= 0 or height <= 0:
            self.app.inform.emit("[warning] Stock width and height must be positive.")
            return
        self.app.stock.set_size(width, height, visible=self.show_cb.get_value())
        self.refresh_fit()
        try:
            self.app.on_zoom_fit(None)
        except Exception:
            pass
        self.app.inform.emit(
            "Stock set to %.4g × %.4g (origin 0, 0)." % (width, height)
        )

    def on_show(self, *_args):
        self.app.stock.set_visible(self.show_cb.get_value())
        self.refresh_fit()

    def on_clear_current(self):
        objects = self._selected() or list(self.app.collection.get_list())
        if not objects:
            self.app.inform.emit("[warning] Nothing to clear.")
            return
        self.app.delete_objects(objects)
        self.refresh_fit()
        try:
            self.app.on_zoom_fit(None)
        except Exception:
            pass

    def refresh_fit(self):
        report = self.app.stock.fit_report()
        w, h = self.app.stock.width(), self.app.stock.height()
        units = (self.app.options.get("units") or "MM").lower()
        if w <= 0 or h <= 0:
            self.fit_label.setText("Fit: set a positive stock size.")
            return
        bounds = report["bounds"]
        if bounds is None:
            self.fit_label.setText(
                "Fit: stock %.4g × %.4g %s at (0, 0). No objects yet."
                % (w, h, units)
            )
            return
        dw, dh = size_of(bounds)
        xmin, ymin, xmax, ymax = bounds
        if report["fits"]:
            text = (
                "Fit: YES. Design %.4g × %.4g %s\n"
                "from (%.4g, %.4g) to (%.4g, %.4g)\n"
                "inside stock %.4g × %.4g."
                % (dw, dh, units, xmin, ymin, xmax, ymax, w, h)
            )
        else:
            left, bottom, right, top = report["overflow"]
            bits = []
            if left:
                bits.append("left %.4g" % left)
            if bottom:
                bits.append("bottom %.4g" % bottom)
            if right:
                bits.append("right %.4g" % right)
            if top:
                bits.append("top %.4g" % top)
            text = (
                "Fit: NO — overhang %s.\n"
                "Design %.4g × %.4g from (%.4g, %.4g) to (%.4g, %.4g).\n"
                "Stock %.4g × %.4g at (0, 0)."
                % (", ".join(bits) or "?", dw, dh, xmin, ymin, xmax, ymax, w, h)
            )
        self.fit_label.setText(text)

    def _selected(self):
        objs = self.app.collection.get_selected()
        if objs:
            return objs
        active = self.app.collection.get_active()
        if active is not None:
            return [active]
        return []

    def on_place_selected(self):
        try:
            x = self._read_length(self.x_entry, "X")
            y = self._read_length(self.y_entry, "Y")
        except ValueError as exc:
            self.app.inform.emit("[warning] %s" % exc)
            return
        self.app.options["stock_place_x"] = x
        self.app.options["stock_place_y"] = y
        self._place(self._selected(), x, y)

    def _place(self, objects, x, y):
        if not objects:
            self.app.inform.emit("[warning] Select one or more objects to move.")
            return
        try:
            dx, dy = self.app.stock.translate_objects(objects, x, y, absolute=True)
        except ValueError as exc:
            self.app.inform.emit("[warning] %s" % exc)
            return
        self.refresh_fit()
        names = ", ".join(o.options.get("name", "?") for o in objects)
        self.app.inform.emit(
            "Moved %s so min corner is (%.4g, %.4g)  Δ=(%.4g, %.4g)."
            % (names, x, y, dx, dy)
        )

    def _tile_params(self):
        cols = max(1, int(self.cols_entry.get_value() or 1))
        rows = max(1, int(self.rows_entry.get_value() or 1))
        spacing_x = self._read_length(self.spacing_x_entry, "spacing X")
        spacing_y = self._read_length(self.spacing_y_entry, "spacing Y")
        margin = self._read_length(self.margin_entry, "margin")
        if spacing_x < 0 or spacing_y < 0:
            raise ValueError("Spacing cannot be negative.")
        if margin < 0:
            raise ValueError("Margin cannot be negative.")
        self.app.options["stock_columns"] = cols
        self.app.options["stock_rows"] = rows
        self.app.options["stock_spacing_x"] = spacing_x
        self.app.options["stock_spacing_y"] = spacing_y
        self.app.options["stock_margin"] = margin
        self.app.options["stock_start_origin"] = self.origin_cb.get_value()
        return cols, rows, spacing_x, spacing_y, margin

    def on_fill(self):
        objects = self._selected() or self.app.collection.get_list()
        box = self.app.stock.object_bounds(objects)
        if box is None:
            self.app.inform.emit("[warning] No geometry to measure for tiling.")
            return
        try:
            spacing_x = self._read_length(self.spacing_x_entry, "spacing X")
            spacing_y = self._read_length(self.spacing_y_entry, "spacing Y")
            margin = self._read_length(self.margin_entry, "margin")
        except ValueError as exc:
            self.app.inform.emit("[warning] %s" % exc)
            return
        dw, dh = size_of(box)
        cols, rows = autofill_counts(
            dw, dh, self.app.stock.width(), self.app.stock.height(),
            spacing_x, spacing_y, margin,
        )
        if cols < 1 or rows < 1:
            self.app.inform.emit(
                "[warning] Design does not fit on the stock even once. "
                "Move it or use a larger sheet."
            )
            self.cols_entry.set_value(1)
            self.rows_entry.set_value(1)
            return
        self.cols_entry.set_value(cols)
        self.rows_entry.set_value(rows)
        self.app.inform.emit(
            "Fill stock: %d × %d = %d copies." % (cols, rows, cols * rows)
        )

    def on_tile_selected(self):
        self._tile(self._selected())

    def on_tile_all(self):
        self._tile(self.app.collection.get_list())

    def _tile(self, objects):
        if not objects:
            self.app.inform.emit("[warning] Select objects (or use Tile all).")
            return
        try:
            cols, rows, spacing_x, spacing_y, margin = self._tile_params()
        except (ValueError, TypeError) as exc:
            self.app.inform.emit("[warning] %s" % exc)
            return
        try:
            created = self.app.stock.tile_objects(
                objects, cols, rows, spacing_x, spacing_y, margin,
                start_at_origin=self.origin_cb.get_value(),
            )
        except ValueError as exc:
            self.app.inform.emit("[warning] %s" % exc)
            return
        names = ", ".join(
            c.options.get("name", "?") for c in created if c is not None
        )
        self.refresh_fit()
        try:
            self.app.on_zoom_fit(None)
        except Exception:
            pass
        self.app.inform.emit(
            "Tiled %d × %d → %s" % (cols, rows, names or "new objects")
        )
