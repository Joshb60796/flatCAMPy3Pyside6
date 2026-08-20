############################################################
# FlatCAM: PCB material (stock) outline, fit, and tiling   #
############################################################
"""Stock rectangle at (0, 0), fit checks, and rectilinear tiling."""

from __future__ import annotations

from copy import deepcopy
from math import inf

from shapely import affinity
from shapely.ops import unary_union

# Plot title: previous 8pt was ~1/4 of a readable size on the canvas.
STOCK_LABEL_FONTSIZE = 32


def union_bounds(boxes):
    """Union of (xmin, ymin, xmax, ymax) tuples. Empty → None."""
    xmin = inf
    ymin = inf
    xmax = -inf
    ymax = -inf
    found = False
    for box in boxes:
        if box is None:
            continue
        try:
            bx0, by0, bx1, by1 = box
        except (TypeError, ValueError):
            continue
        if any(v is None for v in (bx0, by0, bx1, by1)):
            continue
        if bx0 > bx1 or by0 > by1:
            continue
        found = True
        xmin = min(xmin, float(bx0))
        ymin = min(ymin, float(by0))
        xmax = max(xmax, float(bx1))
        ymax = max(ymax, float(by1))
    if not found:
        return None
    return (xmin, ymin, xmax, ymax)


def size_of(bounds):
    if bounds is None:
        return 0.0, 0.0
    xmin, ymin, xmax, ymax = bounds
    return float(xmax - xmin), float(ymax - ymin)


def place_offset(bounds, x, y):
    """Vector that moves the bounds' min corner to (x, y)."""
    if bounds is None:
        return 0.0, 0.0
    xmin, ymin, xmax, ymax = bounds
    return (float(x) - float(xmin), float(y) - float(ymin))


def fits_in_stock(bounds, width, height, origin=(0.0, 0.0), eps=1e-9):
    """
    Whether ``bounds`` lies inside the stock rectangle.

    Returns (fits, overflow) where overflow is
    (left, bottom, right, top) — how far the design sticks out
    (0 if that side is inside).
    """
    ox, oy = origin
    width = float(width)
    height = float(height)
    if width <= 0 or height <= 0:
        return False, (0.0, 0.0, 0.0, 0.0)
    if bounds is None:
        return True, (0.0, 0.0, 0.0, 0.0)
    xmin, ymin, xmax, ymax = bounds
    left = max(0.0, (ox - xmin) - eps)
    bottom = max(0.0, (oy - ymin) - eps)
    right = max(0.0, (xmax - (ox + width)) - eps)
    top = max(0.0, (ymax - (oy + height)) - eps)
    # Snap tiny leftovers to zero so "fits" is unambiguous.
    if left < eps:
        left = 0.0
    if bottom < eps:
        bottom = 0.0
    if right < eps:
        right = 0.0
    if top < eps:
        top = 0.0
    overflow = (left, bottom, right, top)
    return (left == 0 and bottom == 0 and right == 0 and top == 0), overflow


def autofill_counts(design_w, design_h, stock_w, stock_h,
                    spacing_x=0.0, spacing_y=0.0, margin=0.0):
    """Largest columns×rows of ``design`` that fit in stock with margin."""
    design_w = float(design_w)
    design_h = float(design_h)
    usable_w = float(stock_w) - 2.0 * float(margin)
    usable_h = float(stock_h) - 2.0 * float(margin)
    if design_w <= 0 or design_h <= 0 or usable_w + 1e-12 < design_w or usable_h + 1e-12 < design_h:
        return 0, 0
    step_x = design_w + float(spacing_x)
    step_y = design_h + float(spacing_y)
    if step_x <= 0 or step_y <= 0:
        return 0, 0
    cols = 1 + int((usable_w - design_w + 1e-12) // step_x)
    rows = 1 + int((usable_h - design_h + 1e-12) // step_y)
    return max(0, cols), max(0, rows)


def tile_offsets(design_w, design_h, columns, rows,
                 spacing_x=0.0, spacing_y=0.0,
                 origin_x=0.0, origin_y=0.0):
    """
    Lower-left corners of a rectilinear array.

    Tile (0, 0) is at (origin_x, origin_y). Columns increase X, rows increase Y.
    """
    columns = int(columns)
    rows = int(rows)
    if columns < 1 or rows < 1:
        return []
    step_x = float(design_w) + float(spacing_x)
    step_y = float(design_h) + float(spacing_y)
    out = []
    for row in range(rows):
        for col in range(columns):
            out.append((
                float(origin_x) + col * step_x,
                float(origin_y) + row * step_y,
            ))
    return out


def tiled_extent(design_w, design_h, columns, rows, spacing_x=0.0, spacing_y=0.0):
    columns = int(columns)
    rows = int(rows)
    if columns < 1 or rows < 1:
        return 0.0, 0.0
    w = columns * float(design_w) + (columns - 1) * float(spacing_x)
    h = rows * float(design_h) + (rows - 1) * float(spacing_y)
    return w, h


def offsets_from_current(bounds, columns, rows, spacing_x=0.0, spacing_y=0.0,
                         start_at=(None, None)):
    """
    Offsets to apply to geometry that is currently at ``bounds``.

    If ``start_at`` is (x, y), the first tile's min corner moves there.
    If start_at is (None, None), the first tile stays put.
    """
    if bounds is None:
        return []
    xmin, ymin, xmax, ymax = bounds
    dw, dh = size_of(bounds)
    if start_at[0] is None or start_at[1] is None:
        base_x, base_y = xmin, ymin
    else:
        base_x, base_y = float(start_at[0]), float(start_at[1])
    corners = tile_offsets(
        dw, dh, columns, rows, spacing_x, spacing_y, base_x, base_y
    )
    return [(cx - xmin, cy - ymin) for cx, cy in corners]


def translate_geom(geo, dx, dy):
    if geo is None:
        return None
    if isinstance(geo, (list, tuple)):
        return [translate_geom(g, dx, dy) for g in geo]
    return affinity.translate(geo, xoff=float(dx), yoff=float(dy))


def collect_geoms(geo):
    if geo is None:
        return []
    if isinstance(geo, (list, tuple)):
        out = []
        for part in geo:
            out.extend(collect_geoms(part))
        return out
    return [geo]


def tiled_geometry(geo, offsets):
    parts = []
    src = collect_geoms(geo)
    for dx, dy in offsets:
        for part in src:
            moved = translate_geom(part, dx, dy)
            if moved is not None:
                parts.append(moved)
    if not parts:
        return []
    try:
        merged = unary_union(parts)
        if merged is not None and not merged.is_empty:
            return merged
    except Exception:
        pass
    return parts


def tile_gcode(gcode, offsets):
    """Rewrite a CNC program to every tile and concatenate."""
    from gcode_safety import rewrite_gcode_xy

    if not gcode:
        return gcode or ""
    chunks = []
    for dx, dy in offsets:
        chunks.append(
            rewrite_gcode_xy(
                gcode,
                lambda x, y, _dx=dx, _dy=dy: (x + _dx, y + _dy),
                preserve_home_footer=True,
            )
        )
    return "".join(chunks)


class StockOverlay(object):
    """Dashed rectangle on the plot canvas from (0, 0) to (W, H)."""

    def __init__(self, plotcanvas):
        self.plotcanvas = plotcanvas
        self.artists = []

    def clear(self):
        for artist in self.artists:
            try:
                artist.remove()
            except Exception:
                pass
        self.artists = []

    def draw(self, width, height, visible=True, dark=False, overflow=False):
        from matplotlib.patches import Rectangle
        import theme as fc_theme

        self.clear()
        ax = getattr(self.plotcanvas, "axes", None)
        if ax is None or not visible:
            self._refresh()
            return
        width = float(width or 0)
        height = float(height or 0)
        if width <= 0 or height <= 0:
            self._refresh()
            return

        pal = fc_theme.palette_for(dark)
        edge = pal.get("stock_overflow" if overflow else "stock", "#38bdf8")
        label_color = pal.get("stock_label", edge)

        from matplotlib.colors import to_rgba
        rect = Rectangle(
            (0.0, 0.0),
            width,
            height,
            fill=True,
            facecolor=to_rgba(edge, 0.12),
            edgecolor=edge,
            linestyle="--",
            linewidth=2.4,
            zorder=0.4,
        )
        ax.add_patch(rect)
        # Origin marker so (0, 0) is obvious.
        origin, = ax.plot(
            [0.0], [0.0],
            marker="o",
            markersize=14,
            color=edge,
            zorder=5,
        )
        pad = 0.08 * max(width, height)
        label = ax.text(
            width * 0.5,
            height + pad,
            "PCB material  %.4g × %.4g" % (width, height),
            ha="center",
            va="bottom",
            color=label_color,
            fontsize=STOCK_LABEL_FONTSIZE,
            fontweight="bold",
            zorder=5,
            clip_on=False,
        )
        self.artists = [rect, origin, label]
        self._refresh()

    def _refresh(self):
        canvas = getattr(self.plotcanvas, "canvas", None)
        if canvas is None:
            return
        try:
            canvas.draw_idle()
        except Exception:
            pass


class StockManager(object):
    """App-level stock size, overlay, fit, translate, and tile."""

    def __init__(self, app):
        self.app = app
        self.overlay = StockOverlay(app.plotcanvas)

    def _opt(self, key, default=None):
        if key in self.app.options:
            return self.app.options[key]
        return self.app.defaults.get(key, default)

    def width(self):
        try:
            return float(self._opt("stock_width", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    def height(self):
        try:
            return float(self._opt("stock_height", 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    def visible(self):
        return bool(self._opt("stock_visible", True))

    def set_size(self, width, height, visible=None):
        self.app.options["stock_width"] = float(width)
        self.app.options["stock_height"] = float(height)
        self.app.defaults["stock_width"] = float(width)
        self.app.defaults["stock_height"] = float(height)
        if visible is not None:
            self.app.options["stock_visible"] = bool(visible)
            self.app.defaults["stock_visible"] = bool(visible)
        self.redraw()

    def set_visible(self, visible):
        self.app.options["stock_visible"] = bool(visible)
        self.app.defaults["stock_visible"] = bool(visible)
        menu = getattr(self.app.ui, "menuview_stock", None)
        if menu is not None:
            menu.blockSignals(True)
            menu.setChecked(bool(visible))
            menu.blockSignals(False)
        self.redraw()

    def object_bounds(self, objects=None):
        if objects is None:
            objects = self.app.collection.get_list()
        boxes = []
        for obj in objects:
            try:
                boxes.append(obj.bounds())
            except Exception:
                continue
        return union_bounds(boxes)

    def fit_report(self, objects=None):
        bounds = self.object_bounds(objects)
        fits, overflow = fits_in_stock(bounds, self.width(), self.height())
        return {
            "bounds": bounds,
            "stock": (0.0, 0.0, self.width(), self.height()),
            "fits": fits,
            "overflow": overflow,
        }

    def redraw(self):
        report = self.fit_report()
        overflow = not report["fits"] and report["bounds"] is not None
        self.overlay.draw(
            self.width(),
            self.height(),
            visible=self.visible(),
            dark=bool(getattr(self.app, "dark_mode", False)),
            overflow=overflow,
        )

    def zoom_bounds(self):
        """Bounds used by zoom-fit: objects union stock if shown."""
        boxes = []
        obj_box = self.object_bounds()
        if obj_box is not None:
            boxes.append(obj_box)
        if self.visible() and self.width() > 0 and self.height() > 0:
            w, h = self.width(), self.height()
            # Extra Y so the large "PCB material" title is in view.
            boxes.append((0.0, 0.0, w, h + 0.18 * max(w, h)))
        return union_bounds(boxes)

    def translate_objects(self, objects, x, y, absolute=True):
        """
        Move ``objects`` together.

        If ``absolute``, the group's min corner goes to (x, y).
        Otherwise (x, y) is a relative offset.
        """
        objects = list(objects)
        if not objects:
            raise ValueError("No objects to move.")
        if absolute:
            box = self.object_bounds(objects)
            dx, dy = place_offset(box, x, y)
        else:
            dx, dy = float(x), float(y)
        if abs(dx) < 1e-15 and abs(dy) < 1e-15:
            return (0.0, 0.0)
        for obj in objects:
            obj.offset((dx, dy))
            try:
                obj.plot()
            except Exception:
                pass
        self.redraw()
        return (dx, dy)

    def tile_objects(self, objects, columns, rows,
                     spacing_x=0.0, spacing_y=0.0,
                     margin=0.0, start_at_origin=True, outname=None,
                     replace_originals=True):
        """
        Create one new object per source, each containing the full array.

        All selected objects share the same union bounding box so a
        Gerber + Excellon pair stay aligned.

        If ``replace_originals`` is true (default), the source objects
        are removed so the array does not sit on top of the loaded design.
        """
        objects = list(objects)
        if not objects:
            raise ValueError("No objects to tile.")
        columns = int(columns)
        rows = int(rows)
        if columns < 1 or rows < 1:
            raise ValueError("Need at least 1 column and 1 row.")

        box = self.object_bounds(objects)
        if box is None:
            raise ValueError("Selected objects have no geometry.")

        if start_at_origin:
            start = (float(margin), float(margin))
        else:
            start = (None, None)
        offsets = offsets_from_current(
            box, columns, rows, spacing_x, spacing_y, start_at=start
        )
        if not offsets:
            raise ValueError("No tile positions.")

        created = []
        for obj in objects:
            name = outname if (outname and len(objects) == 1) else None
            created.append(self._new_tiled(obj, offsets, outname=name))
        if replace_originals:
            self.app.delete_objects(objects, reset_editor=False)
        first = next((c for c in created if c is not None), None)
        if first is not None:
            try:
                self.app.collection.set_all_inactive()
                self.app.collection.set_active(first.options["name"])
            except Exception:
                pass
        self.redraw()
        return created

    def _new_tiled(self, obj, offsets, outname=None):
        from FlatCAMObj import (
            FlatCAMCNCjob,
            FlatCAMExcellon,
            FlatCAMGerber,
        )

        kind = obj.kind
        outname = outname or (obj.options.get("name", kind) + "_tile")

        if isinstance(obj, FlatCAMExcellon):
            def init(new_obj, app):
                new_obj.tools = deepcopy(obj.tools)
                new_obj.zeros = getattr(obj, "zeros", new_obj.zeros)
                new_obj.drills = []
                for dx, dy in offsets:
                    for drill in obj.drills:
                        new_obj.drills.append({
                            "point": affinity.translate(
                                drill["point"], xoff=dx, yoff=dy
                            ),
                            "tool": drill["tool"],
                        })
                new_obj.create_geometry()
                for key in obj.options:
                    if key != "name":
                        new_obj.options[key] = obj.options[key]
            return self.app.new_object("excellon", outname, init)
        elif isinstance(obj, FlatCAMCNCjob):
            def init(new_obj, app):
                new_obj.z_cut = obj.z_cut
                new_obj.z_move = obj.z_move
                new_obj.feedrate = obj.feedrate
                new_obj.spindlespeed = obj.spindlespeed
                new_obj.units = obj.units
                new_obj.tooldia = obj.tooldia
                new_obj.gcode = tile_gcode(obj.gcode, offsets)
                if new_obj.gcode:
                    new_obj.gcode_parse()
                    new_obj.create_geometry()
                for key in obj.options:
                    if key != "name":
                        new_obj.options[key] = obj.options[key]
            return self.app.new_object("cncjob", outname, init)
        elif isinstance(obj, FlatCAMGerber):
            def init(new_obj, app):
                new_obj.solid_geometry = tiled_geometry(obj.solid_geometry, offsets)
                for key in obj.options:
                    if key != "name":
                        new_obj.options[key] = obj.options[key]
            return self.app.new_object("gerber", outname, init)
        else:
            def init(new_obj, app):
                new_obj.solid_geometry = tiled_geometry(obj.solid_geometry, offsets)
                for key in obj.options:
                    if key != "name":
                        new_obj.options[key] = obj.options[key]
            return self.app.new_object("geometry", outname, init)
