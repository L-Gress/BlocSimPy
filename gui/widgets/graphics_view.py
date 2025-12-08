"""Custom QGraphicsView that forwards key events to the scene."""
from PySide6.QtWidgets import QGraphicsView


class GraphicsView(QGraphicsView):
    """Custom QGraphicsView that properly forwards key events to the scene."""
    
    def keyPressEvent(self, event):
        """Forward key events to the scene."""
        # QGraphicsView automatically forwards key events to the scene if not handled by items.
        # We just call super which handles this propagation.
        super().keyPressEvent(event)
