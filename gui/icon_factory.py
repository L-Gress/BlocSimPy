"""Hand-drawn, single-stroke line icons for toolbar/menu actions.

Replaces QStyle.standardIcon() (native, OS-themed pixmaps that clash with
the app's own flat Apple-style theme) with a small, self-authored icon set:
a handful of QPainterPath primitives per glyph, drawn on a 24x24 design
grid and rendered natively at whatever pixel size is requested (not just
scaled from one bitmap, so menu-size and toolbar-size icons both stay
crisp). Self-contained and dependency-free rather than pulling in an icon
font or a folder of bundled SVGs for what is a fixed, short list of
actions.
"""
import math
from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPen, QPainterPath, QColor

_GRID = 24.0
_SIZES = (16, 20, 24, 28, 32)

# Stroke/accent colors per theme -- icons are drawn fresh from these on
# every icon() call (nothing is cached here), so switching _CURRENT_MODE
# and re-calling icon() for every action already on screen (see
# ToolbarManager.refresh_icons()/UserSpaceWidget.refresh_tree()) is enough
# to re-theme every icon in the app.
_STROKE_BY_MODE = {
    "light": QColor("#3a3a3c"),   # neutral dark gray -- reads on the light toolbar/menu
    "dark": QColor("#d4d4d4"),    # neutral light gray -- reads on the dark toolbar/menu
}
_ACCENT_BY_MODE = {
    "light": QColor("#007aff"),   # systemBlue (light), used only for the primary Run glyph
    "dark": QColor("#0a84ff"),    # systemBlue (dark)
}
_CURRENT_MODE = "light"
_STROKE = _STROKE_BY_MODE[_CURRENT_MODE]
_ACCENT = _ACCENT_BY_MODE[_CURRENT_MODE]

_registry = {}


def set_theme(mode):
    """Switch the colors every icon is drawn with from here on. Doesn't
    touch icons already set on existing QActions/QTreeWidgetItems -- callers
    must re-fetch icon(name) for anything already on screen (see module
    docstring)."""
    global _CURRENT_MODE, _STROKE, _ACCENT
    _CURRENT_MODE = "dark" if mode == "dark" else "light"
    _STROKE = _STROKE_BY_MODE[_CURRENT_MODE]
    _ACCENT = _ACCENT_BY_MODE[_CURRENT_MODE]


def _register(name):
    def deco(fn):
        _registry[name] = fn
        return fn
    return deco


def _pen(color=None, width=1.7):
    # `color` isn't defaulted to `_STROKE` directly -- default arguments are
    # bound once at function-definition time, which would freeze every
    # unthemed call at whatever _STROKE was when this module first loaded,
    # ignoring later set_theme() calls. Reading the module global inside the
    # body instead picks up the current theme on every call.
    pen = QPen(_STROKE if color is None else color, width)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    return pen


# --- Icon drawers (each operates in the 24x24 design grid) ---

@_register("new")
def _draw_new(p):
    p.setPen(_pen())
    path = QPainterPath()
    path.moveTo(7, 3); path.lineTo(14, 3); path.lineTo(18, 7)
    path.lineTo(18, 21); path.lineTo(7, 21); path.closeSubpath()
    path.moveTo(14, 3); path.lineTo(14, 7); path.lineTo(18, 7)
    p.drawPath(path)


@_register("open")
def _draw_open(p):
    p.setPen(_pen())
    p.drawRoundedRect(QRectF(4, 6, 8, 3.5), 1, 1)
    p.drawRoundedRect(QRectF(3, 9.5, 18, 9.5), 2, 2)


@_register("project")
def _draw_project(p):
    # Same folder glyph as "open", plus an accent badge -- distinguishes
    # "switch the whole Project Folder" from "open a single file".
    _draw_open(p)
    p.setPen(Qt.NoPen)
    p.setBrush(_ACCENT)
    p.drawEllipse(QPointF(18.3, 17.5), 3.0, 3.0)


@_register("save")
def _draw_save(p):
    p.setPen(_pen())
    path = QPainterPath()
    path.moveTo(12, 4); path.lineTo(12, 15)
    path.moveTo(7, 10); path.lineTo(12, 15); path.lineTo(17, 10)
    path.moveTo(5, 16); path.lineTo(5, 19.5); path.lineTo(19, 19.5); path.lineTo(19, 16)
    p.drawPath(path)


@_register("save_as")
def _draw_save_as(p):
    _draw_save(p)
    p.setPen(_pen(width=1.4))
    p.drawEllipse(QPointF(19, 5.5), 4, 4)
    plus = QPainterPath()
    plus.moveTo(19, 3.6); plus.lineTo(19, 7.4)
    plus.moveTo(17.1, 5.5); plus.lineTo(20.9, 5.5)
    p.drawPath(plus)


def _arc_point(cx, cy, r, angle_deg):
    a = math.radians(angle_deg)
    return QPointF(cx + r * math.cos(a), cy - r * math.sin(a))


def _draw_undo(p):
    """~3/4 circle open on the right, with a tangent arrowhead at its lower
    end -- the classic "circular undo arrow". Verified against a rendered
    contact sheet (arcTo's angle convention isn't obvious to eyeball)."""
    p.setPen(_pen())
    rect = QRectF(4, 4, 16, 16)
    start, sweep = 40, 270
    path = QPainterPath()
    path.arcMoveTo(rect, start)
    path.arcTo(rect, start, sweep)
    p.drawPath(path)

    cx, cy, r = rect.center().x(), rect.center().y(), rect.width() / 2
    end_angle = start + sweep
    tip = _arc_point(cx, cy, r, end_angle)
    back = _arc_point(cx, cy, r, end_angle + 32)  # a bit further around, unrendered
    ux, uy = tip.x() - back.x(), tip.y() - back.y()
    length = math.hypot(ux, uy)
    ux, uy = ux / length, uy / length
    perp_x, perp_y = -uy, ux
    wing, wing_w = 4.2, 3.6
    base = QPointF(tip.x() - ux * wing, tip.y() - uy * wing)
    head = QPainterPath()
    head.moveTo(base.x() + perp_x * wing_w, base.y() + perp_y * wing_w)
    head.lineTo(tip.x(), tip.y())
    head.lineTo(base.x() - perp_x * wing_w, base.y() - perp_y * wing_w)
    p.drawPath(head)


@_register("undo")
def _draw_undo_icon(p):
    _draw_undo(p)


@_register("redo")
def _draw_redo_icon(p):
    # Mirror image of undo -- guaranteed-correct rather than re-deriving arc
    # angles by hand for the opposite direction.
    p.save()
    p.translate(_GRID, 0)
    p.scale(-1, 1)
    _draw_undo(p)
    p.restore()


@_register("cut")
def _draw_cut(p):
    p.setPen(_pen())
    path = QPainterPath()
    path.moveTo(9, 9); path.lineTo(20, 18)
    path.moveTo(9, 15); path.lineTo(20, 6)
    p.drawPath(path)
    p.drawEllipse(QPointF(6.3, 7.5), 2.3, 2.3)
    p.drawEllipse(QPointF(6.3, 16.5), 2.3, 2.3)


@_register("copy")
def _draw_copy(p):
    p.setPen(_pen())
    p.drawRoundedRect(QRectF(8, 3, 13, 13), 2, 2)
    p.drawRoundedRect(QRectF(3, 8, 13, 13), 2, 2)


@_register("paste")
def _draw_paste(p):
    p.setPen(_pen())
    p.drawRoundedRect(QRectF(5, 5, 14, 16), 2, 2)
    p.drawRoundedRect(QRectF(9, 3, 6, 3), 1, 1)


@_register("select_all")
def _draw_select_all(p):
    p.setPen(_pen())
    path = QPainterPath()
    path.moveTo(4, 8.5); path.lineTo(4, 4); path.lineTo(8.5, 4)
    path.moveTo(15.5, 4); path.lineTo(20, 4); path.lineTo(20, 8.5)
    path.moveTo(4, 15.5); path.lineTo(4, 20); path.lineTo(8.5, 20)
    path.moveTo(20, 15.5); path.lineTo(20, 20); path.lineTo(15.5, 20)
    p.drawPath(path)


@_register("delete")
def _draw_delete(p):
    p.setPen(_pen())
    path = QPainterPath()
    path.moveTo(5, 7); path.lineTo(19, 7)
    path.moveTo(6.5, 7); path.lineTo(7.5, 20.5); path.lineTo(16.5, 20.5); path.lineTo(17.5, 7)
    path.moveTo(10, 10.5); path.lineTo(10, 17.5)
    path.moveTo(14, 10.5); path.lineTo(14, 17.5)
    p.drawPath(path)
    p.drawRoundedRect(QRectF(9.5, 3.5, 5, 3), 1, 1)


@_register("settings")
def _draw_settings(p):
    cx, cy, outer, inner, teeth = 12.0, 12.0, 9.2, 6.6, 8
    gear = QPainterPath()
    for i in range(teeth * 2):
        angle = math.pi * i / teeth
        r = outer if i % 2 == 0 else inner
        x, y = cx + r * math.cos(angle), cy + r * math.sin(angle)
        if i == 0:
            gear.moveTo(x, y)
        else:
            gear.lineTo(x, y)
    gear.closeSubpath()
    gear.addEllipse(QPointF(cx, cy), 3.0, 3.0)
    gear.setFillRule(Qt.OddEvenFill)
    p.setPen(Qt.NoPen)
    p.setBrush(_STROKE)
    p.drawPath(gear)


@_register("run")
def _draw_run(p):
    p.setPen(Qt.NoPen)
    p.setBrush(_ACCENT)
    path = QPainterPath()
    path.moveTo(8, 5); path.lineTo(8, 19); path.lineTo(20, 12); path.closeSubpath()
    p.drawPath(path)


@_register("stop")
def _draw_stop(p):
    # Pairs with "run": same fill/no-pen treatment, a plain filled square
    # standing in for the play triangle -- what the Run button turns into
    # while a simulation/Script is running (see ToolbarManager._set_running()).
    p.setPen(Qt.NoPen)
    p.setBrush(_ACCENT)
    p.drawRoundedRect(QRectF(7, 7, 10, 10), 1.5, 1.5)


@_register("inspector")
def _draw_inspector(p):
    p.setPen(Qt.NoPen)
    p.setBrush(_STROKE)
    p.drawRoundedRect(QRectF(5, 14, 4, 6), 1, 1)
    p.drawRoundedRect(QRectF(10, 9, 4, 11), 1, 1)
    p.drawRoundedRect(QRectF(15, 4, 4, 16), 1, 1)


@_register("up")
def _draw_up(p):
    p.setPen(_pen())
    path = QPainterPath()
    path.moveTo(6, 15); path.lineTo(12, 9); path.lineTo(18, 15)
    p.drawPath(path)


@_register("subgraph")
def _draw_subgraph(p):
    p.setPen(_pen(width=1.5))
    path = QPainterPath()
    path.moveTo(4, 8.5); path.lineTo(12, 4.5); path.lineTo(20, 8.5)
    path.lineTo(12, 12.5); path.closeSubpath()
    path.moveTo(4, 8.5); path.lineTo(4, 16.5); path.lineTo(12, 20.5); path.lineTo(12, 12.5)
    path.moveTo(20, 8.5); path.lineTo(20, 16.5); path.lineTo(12, 20.5)
    p.drawPath(path)


@_register("scripts")
def _draw_scripts(p):
    p.setPen(_pen())
    path = QPainterPath()
    path.moveTo(10, 6); path.lineTo(4, 12); path.lineTo(10, 18)
    path.moveTo(14, 6); path.lineTo(20, 12); path.lineTo(14, 18)
    p.drawPath(path)


@_register("help")
def _draw_help(p):
    p.setPen(_pen())
    p.drawEllipse(QPointF(12, 12), 9, 9)
    hook = QPainterPath()
    hook.moveTo(9.3, 9.5)
    hook.cubicTo(9.3, 6.2, 14.7, 6.2, 14.7, 9.5)
    hook.cubicTo(14.7, 11.8, 12, 11.5, 12, 14.2)
    p.drawPath(hook)
    p.setPen(Qt.NoPen)
    p.setBrush(_STROKE)
    p.drawEllipse(QPointF(12, 17.6), 1.15, 1.15)


@_register("about")
def _draw_about(p):
    p.setPen(_pen())
    p.drawEllipse(QPointF(12, 12), 9, 9)
    p.drawLine(QPointF(12, 11), QPointF(12, 17))
    p.setPen(Qt.NoPen)
    p.setBrush(_STROKE)
    p.drawEllipse(QPointF(12, 7.3), 1.15, 1.15)


@_register("quit")
def _draw_quit(p):
    p.setPen(_pen())
    rect = QRectF(4.5, 4.5, 15, 15)
    path = QPainterPath()
    path.arcMoveTo(rect, 125)
    path.arcTo(rect, 125, 290)
    p.drawPath(path)
    p.drawLine(QPointF(12, 3.5), QPointF(12, 12))


def _draw_magnifier(p, sign):
    p.setPen(_pen())
    p.drawEllipse(QPointF(10.5, 10.5), 6.5, 6.5)
    p.drawLine(QPointF(15.2, 15.2), QPointF(20, 20))
    plus = QPainterPath()
    plus.moveTo(7.3, 10.5); plus.lineTo(13.7, 10.5)
    if sign == "+":
        plus.moveTo(10.5, 7.3); plus.lineTo(10.5, 13.7)
    p.drawPath(plus)


@_register("zoom_in")
def _draw_zoom_in(p):
    _draw_magnifier(p, "+")


@_register("zoom_out")
def _draw_zoom_out(p):
    _draw_magnifier(p, "-")


@_register("zoom_fit")
def _draw_zoom_fit(p):
    p.setPen(_pen())
    path = QPainterPath()
    path.moveTo(4, 9); path.lineTo(4, 4); path.lineTo(9, 4)
    path.moveTo(15, 4); path.lineTo(20, 4); path.lineTo(20, 9)
    path.moveTo(4, 15); path.lineTo(4, 20); path.lineTo(9, 20)
    path.moveTo(20, 15); path.lineTo(20, 20); path.lineTo(15, 20)
    p.drawPath(path)
    p.drawRoundedRect(QRectF(9, 9, 6, 6), 1, 1)


@_register("rename")
def _draw_rename(p):
    p.setPen(_pen())
    path = QPainterPath()
    path.moveTo(5, 19); path.lineTo(6, 15); path.lineTo(16, 5)
    path.lineTo(19, 8); path.lineTo(9, 18); path.closeSubpath()
    path.moveTo(13, 8); path.lineTo(16, 11)
    p.drawPath(path)


@_register("duplicate")
def _draw_duplicate(p):
    p.setPen(_pen())
    p.drawRoundedRect(QRectF(3, 7, 12, 14), 2, 2)
    p.drawRoundedRect(QRectF(9, 3, 12, 14), 2, 2)


@_register("console")
def _draw_console(p):
    # Classic terminal glyph: a ">" prompt chevron plus a cursor bar,
    # inside a rounded frame.
    p.setPen(_pen())
    p.drawRoundedRect(QRectF(3, 4.5, 18, 15), 2.5, 2.5)
    chevron = QPainterPath()
    chevron.moveTo(6.5, 9.5); chevron.lineTo(10.5, 12.5); chevron.lineTo(6.5, 15.5)
    p.drawPath(chevron)
    p.drawLine(QPointF(12.5, 15.5), QPointF(17, 15.5))


def _globals_table_path():
    # Shared base glyph for "globals"/"clear_globals": a mini 2-col x
    # 3-row table, standing in for a name/value variable list (same idea
    # as the "inspector" bars standing in for a data plot).
    path = QPainterPath()
    path.addRoundedRect(QRectF(3.5, 4.5, 17, 15), 2, 2)
    path.moveTo(11, 4.5); path.lineTo(11, 19.5)
    path.moveTo(3.5, 9.5); path.lineTo(20.5, 9.5)
    path.moveTo(3.5, 14.5); path.lineTo(20.5, 14.5)
    return path


@_register("globals")
def _draw_globals(p):
    p.setPen(_pen())
    p.drawPath(_globals_table_path())


@_register("clear_globals")
def _draw_clear_globals(p):
    # Same table glyph as "globals", plus an accent strike-through --
    # mirrors how "project" reuses "open" plus a badge to signal "same
    # thing, destructive/alternate action".
    p.setPen(_pen())
    p.drawPath(_globals_table_path())
    p.setPen(_pen(_ACCENT, width=2.2))
    p.drawLine(QPointF(2.5, 21), QPointF(21.5, 2.5))


@_register("theme")
def _draw_theme(p):
    # Crescent moon: a circle with a second, offset circle subtracted from
    # it (QPainterPath.subtracted(), exact boolean "A minus B" -- unlike an
    # even-odd fill over two overlapping circles, which would leave a
    # stray sliver of the second circle behind).
    p.setPen(Qt.NoPen)
    p.setBrush(_STROKE)
    moon = QPainterPath()
    moon.addEllipse(QPointF(12, 12.5), 7.5, 7.5)
    cutout = QPainterPath()
    cutout.addEllipse(QPointF(16, 9), 6.5, 6.5)
    p.drawPath(moon.subtracted(cutout))


@_register("library")
def _draw_library(p):
    # Bookshelf glyph: a baseline shelf with three book spines of
    # different heights standing on it -- the block palette/User Space
    # dock this toggles is literally a shelf of reusable pieces.
    p.setPen(_pen())
    p.drawLine(QPointF(3.5, 20), QPointF(20.5, 20))
    p.drawRoundedRect(QRectF(4.5, 7, 4, 13), 1, 1)
    p.drawRoundedRect(QRectF(10, 4, 4, 16), 1, 1)
    p.drawRoundedRect(QRectF(15.5, 9, 4, 11), 1, 1)


def icon(name, color=None):
    """Build a QIcon for `name` with several natively-rendered pixmap sizes
    (crisp at both menu and toolbar scale, unlike scaling a single bitmap)."""
    drawer = _registry.get(name)
    if drawer is None:
        raise KeyError(f"No icon registered for {name!r}")

    result = QIcon()
    for size in _SIZES:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.scale(size / _GRID, size / _GRID)
        drawer(painter)
        painter.end()
        result.addPixmap(pixmap)
    return result
