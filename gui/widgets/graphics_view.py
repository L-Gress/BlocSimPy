"""Custom QGraphicsView that forwards key events to the scene."""
from PySide6.QtWidgets import QGraphicsView


class GraphicsView(QGraphicsView):
    """Custom QGraphicsView that properly forwards key events to the scene."""
    
    def keyPressEvent(self, event):
        """Forward key events to the scene."""
        if self.scene():
            self.scene().keyPressEvent(event)
        super().keyPressEvent(event)
