"""UI Configuration Constants."""
from PySide6.QtGui import QColor


class UIConfig:
    """Centralized UI configuration for consistent styling.

    Colors mirror the Apple-dark palette in config/theme.py -- that file
    styles Qt widgets via QSS, this one styles the hand-painted
    QGraphicsScene canvas (blocks/ports/wires), so the two are kept in sync
    by hand rather than sharing one mechanism.
    """

    # Window
    WINDOW_TITLE = "BlocSimPy"
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800

    # Colors
    BACKGROUND_COLOR = QColor("#1e1e1e")
    BLOCK_BG_COLOR = QColor("#2c2c2e")
    BLOCK_BORDER_COLOR = QColor("#48484a")
    BLOCK_SELECTED_COLOR = QColor("#0a84ff")

    CONNECTION_COLOR = QColor("#8e8e93")
    CONNECTION_WIDTH = 2
    CONNECTION_HIT_WIDTH = 10
    FORK_DOT_COLOR = QColor("#aeaeb2")

    INPUT_PORT_COLOR = QColor("#ff9f0a")
    OUTPUT_PORT_COLOR = QColor("#32d74b")
    PORT_SIZE = 14

    TEXT_COLOR = QColor("#aeaeb2")
    TITLE_COLOR = QColor("#f5f5f7")

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
