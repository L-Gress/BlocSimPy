"""UI Configuration Constants."""
from PySide6.QtGui import QColor


class UIConfig:
    """Centralized UI configuration for consistent styling."""
    
    # Window
    WINDOW_TITLE = "BlocSimPy"
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    
    # Colors
    BACKGROUND_COLOR = QColor(30, 30, 30)
    BLOCK_BG_COLOR = QColor(50, 50, 50)
    BLOCK_BORDER_COLOR = QColor(0, 0, 0)
    BLOCK_SELECTED_COLOR = QColor(100, 200, 255)
    
    CONNECTION_COLOR = QColor(200, 200, 200)
    CONNECTION_WIDTH = 2
    CONNECTION_HIT_WIDTH = 10
    
    INPUT_PORT_COLOR = QColor("orange")
    OUTPUT_PORT_COLOR = QColor("green")
    PORT_SIZE = 14
    
    TEXT_COLOR = QColor(220, 220, 220)
    TITLE_COLOR = QColor(255, 255, 255)
    
    # Fonts
    PORT_FONT_SIZE = 8
    TITLE_FONT_SIZE = 10
    
    # Block Dimensions
    DEFAULT_BLOCK_WIDTH = 100
    DEFAULT_BLOCK_HEIGHT = 60
    PORT_VERTICAL_SPACING = 25
    PORT_MARGIN = 20
    
    # Rendering
    BLOCK_CORNER_RADIUS = 5
    BLOCK_BORDER_WIDTH = 2
    BOUNDING_MARGIN = 100  # Extra margin for text labels
