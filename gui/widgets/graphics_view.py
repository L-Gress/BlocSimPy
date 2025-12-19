from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView


class GraphicsView(QGraphicsView):
    """Custom QGraphicsView with rubber band selection and antialiasing."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
    
    def keyPressEvent(self, event):
        """Forward key events to the scene."""
        # QGraphicsView automatically forwards key events to the scene if not handled by items.
        # We just call super which handles this propagation.
        super().keyPressEvent(event)
