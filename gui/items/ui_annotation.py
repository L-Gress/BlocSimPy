"""Free-text canvas annotation -- a movable, editable note not attached to
any block, for documenting a diagram."""
from PySide6.QtWidgets import QGraphicsTextItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont


class UIAnnotation(QGraphicsTextItem):
    """A movable, editable free-text note on the canvas."""

    def __init__(self, text="Note"):
        super().__init__(text)
        self.setFlags(
            QGraphicsTextItem.ItemIsMovable |
            QGraphicsTextItem.ItemIsSelectable |
            QGraphicsTextItem.ItemSendsGeometryChanges
        )
        self.setDefaultTextColor(QColor("#F4D35E"))
        font = QFont()
        font.setPointSize(10)
        self.setFont(font)
        # Not editable until double-clicked (see mouseDoubleClickEvent) --
        # otherwise a single click to select/drag would also drop the user
        # into text-edit mode.
        self.setTextInteractionFlags(Qt.NoTextInteraction)

    def mouseDoubleClickEvent(self, event):
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setFocus(Qt.MouseFocusReason)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        # Stop editing once focus leaves, and snapshot the text change for undo.
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        scene = self.scene()
        if scene:
            main_window = scene.parent()
            if main_window and hasattr(main_window, 'scene_manager'):
                main_window.scene_manager.take_snapshot()
        super().focusOutEvent(event)

    def mouseReleaseEvent(self, event):
        # NodeScene's own mouseReleaseEvent only snapshots UIBlock drags
        # (its group-move logic in mouseMoveEvent only moves UIBlocks) --
        # an annotation drag uses Qt's default single-item move via
        # ItemIsMovable instead, so it needs its own snapshot-on-release.
        super().mouseReleaseEvent(event)
        scene = self.scene()
        if scene:
            main_window = scene.parent()
            if main_window and hasattr(main_window, 'scene_manager'):
                main_window.scene_manager.take_snapshot()
