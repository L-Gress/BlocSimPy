"""UI Configuration Constants."""
from PySide6.QtGui import QColor

# --- Canvas palettes (light/dark) ---
# Mirror config/theme.py's LIGHT/DARK QSS palettes -- that file styles Qt
# widgets via QSS, this one styles the hand-painted QGraphicsScene canvas
# (blocks/ports/wires) via direct QPainter calls, so the two are kept in
# sync by hand rather than sharing one mechanism. UIConfig.apply_theme()
# swaps the QColor class attributes below in place; every canvas item reads
# them fresh at paint time (see gui/items/*.py), so a repaint after
# switching is all that's needed to pick up the new colors.
_LIGHT_CANVAS = {
    "BACKGROUND_COLOR": "#eef0f3",
    "BLOCK_BG_COLOR": "#ffffff",
    "BLOCK_BORDER_COLOR": "#d1d1d6",
    "BLOCK_SELECTED_COLOR": "#007aff",
    "CONNECTION_COLOR": "#6e6e73",
    "FORK_DOT_COLOR": "#6e6e73",
    "INPUT_PORT_COLOR": "#ff9500",
    "OUTPUT_PORT_COLOR": "#34c759",
    "TEXT_COLOR": "#6e6e73",
    "TITLE_COLOR": "#1d1d1f",
}

_DARK_CANVAS = {
    "BACKGROUND_COLOR": "#1b1b1d",
    "BLOCK_BG_COLOR": "#2d2d30",
    "BLOCK_BORDER_COLOR": "#3c3c3c",
    "BLOCK_SELECTED_COLOR": "#0a84ff",
    "CONNECTION_COLOR": "#9d9d9f",
    "FORK_DOT_COLOR": "#9d9d9f",
    "INPUT_PORT_COLOR": "#ff9f0a",
    "OUTPUT_PORT_COLOR": "#32d74b",
    "TEXT_COLOR": "#9d9d9f",
    "TITLE_COLOR": "#e4e4e6",
}

_CANVAS_PALETTES = {"light": _LIGHT_CANVAS, "dark": _DARK_CANVAS}


class UIConfig:
    """Centralized UI configuration for consistent styling."""

    # Window
    WINDOW_TITLE = "BlocSimPy"
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800

    # Colors -- default (light); see apply_theme() below.
    BACKGROUND_COLOR = QColor(_LIGHT_CANVAS["BACKGROUND_COLOR"])
    BLOCK_BG_COLOR = QColor(_LIGHT_CANVAS["BLOCK_BG_COLOR"])
    BLOCK_BORDER_COLOR = QColor(_LIGHT_CANVAS["BLOCK_BORDER_COLOR"])
    BLOCK_SELECTED_COLOR = QColor(_LIGHT_CANVAS["BLOCK_SELECTED_COLOR"])

    CONNECTION_COLOR = QColor(_LIGHT_CANVAS["CONNECTION_COLOR"])
    CONNECTION_WIDTH = 2
    CONNECTION_HIT_WIDTH = 10
    FORK_DOT_COLOR = QColor(_LIGHT_CANVAS["FORK_DOT_COLOR"])

    INPUT_PORT_COLOR = QColor(_LIGHT_CANVAS["INPUT_PORT_COLOR"])
    OUTPUT_PORT_COLOR = QColor(_LIGHT_CANVAS["OUTPUT_PORT_COLOR"])
    PORT_SIZE = 14

    TEXT_COLOR = QColor(_LIGHT_CANVAS["TEXT_COLOR"])
    TITLE_COLOR = QColor(_LIGHT_CANVAS["TITLE_COLOR"])

    CURRENT_THEME = "light"

    # Fonts
    PORT_FONT_SIZE = 8
    TITLE_FONT_SIZE = 10

    # Block Dimensions
    DEFAULT_BLOCK_WIDTH = 100
    DEFAULT_BLOCK_HEIGHT = 60
    PORT_VERTICAL_SPACING = 25
    PORT_MARGIN = 20

    # Rendering
    BLOCK_CORNER_RADIUS = 10
    BLOCK_BORDER_WIDTH = 1
    BLOCK_BORDER_WIDTH_SELECTED = 2
    BOUNDING_MARGIN = 100  # Extra margin for text labels

    @classmethod
    def apply_theme(cls, mode):
        """Swap every canvas QColor to `mode`'s ("light"/"dark") palette.
        Callers still need to repaint/update() any open QGraphicsScene
        afterwards -- this only changes what the next paint will read (see
        gui/managers/theme_manager.py)."""
        palette = _CANVAS_PALETTES.get(mode, _LIGHT_CANVAS)
        for name, hex_color in palette.items():
            setattr(cls, name, QColor(hex_color))
        cls.CURRENT_THEME = "dark" if mode == "dark" else "light"
