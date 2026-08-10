"""UI Configuration Constants."""
from PySide6.QtGui import QColor


class UIConfig:
    """Centralized UI configuration for consistent styling.

    Colors mirror the Apple-light palette in config/theme.py -- that file
    styles Qt widgets via QSS, this one styles the hand-painted
    QGraphicsScene canvas (blocks/ports/wires), so the two are kept in sync
    by hand rather than sharing one mechanism.
    """

    # Window
    WINDOW_TITLE = "BlocSimPy"
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800

    # Colors
    BACKGROUND_COLOR = QColor("#eef0f3")
    BLOCK_BG_COLOR = QColor("#ffffff")
    BLOCK_BORDER_COLOR = QColor("#d1d1d6")
    BLOCK_SELECTED_COLOR = QColor("#007aff")

    CONNECTION_COLOR = QColor("#6e6e73")
    CONNECTION_WIDTH = 2
    CONNECTION_HIT_WIDTH = 10
    FORK_DOT_COLOR = QColor("#6e6e73")

    INPUT_PORT_COLOR = QColor("#ff9500")
    OUTPUT_PORT_COLOR = QColor("#34c759")
    PORT_SIZE = 14

    TEXT_COLOR = QColor("#6e6e73")
    TITLE_COLOR = QColor("#1d1d1f")

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
