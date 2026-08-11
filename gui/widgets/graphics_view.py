from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QGraphicsView, QFrame


class GraphicsView(QGraphicsView):
    """Custom QGraphicsView with rubber band selection, antialiasing,
    mouse-wheel zoom, and middle-button panning."""

    _ZOOM_STEP = 1.15
    _ZOOM_MIN = 0.15
    _ZOOM_MAX = 6.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setFrameShape(QFrame.NoFrame)  # flat canvas edge, no sunken border
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self._zoom = 1.0
        self._panning = False
        self._pan_start = None

    def keyPressEvent(self, event):
        """Forward key events to the scene."""
        # QGraphicsView automatically forwards key events to the scene if not handled by items.
        # We just call super which handles this propagation.
        super().keyPressEvent(event)

    def wheelEvent(self, event):
        """Zoom the canvas in/out, anchored under the cursor so the point
        the user is pointing at stays put."""
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return

        factor = self._ZOOM_STEP if delta > 0 else 1.0 / self._ZOOM_STEP
        new_zoom = self._zoom * factor
        if new_zoom < self._ZOOM_MIN or new_zoom > self._ZOOM_MAX:
            return

        self._zoom = new_zoom
        self.scale(factor, factor)
        event.accept()

    def zoom_in(self):
        self._apply_zoom(self._ZOOM_STEP)

    def zoom_out(self):
        self._apply_zoom(1.0 / self._ZOOM_STEP)

    def _apply_zoom(self, factor):
        new_zoom = self._zoom * factor
        if new_zoom < self._ZOOM_MIN or new_zoom > self._ZOOM_MAX:
            return
        self._zoom = new_zoom
        self.scale(factor, factor)

    def zoom_reset(self):
        """Reset to 100% around the current viewport center."""
        self.resetTransform()
        self._zoom = 1.0

    def zoom_to_fit(self):
        """Frame every item on the canvas, or reset to 100% if it's empty."""
        scene = self.scene()
        if scene is None or not scene.items():
            self.zoom_reset()
            return

        rect = scene.itemsBoundingRect()
        if rect.isEmpty():
            self.zoom_reset()
            return

        margin = 40
        rect = rect.adjusted(-margin, -margin, margin, margin)
        self.fitInView(rect, Qt.KeepAspectRatio)
        self._zoom = self.transform().m11()

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning:
            pos = event.position().toPoint()
            delta = pos - self._pan_start
            self._pan_start = pos
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._panning:
            self._panning = False
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)
