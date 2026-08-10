"""Context menu for right-clicking empty canvas space (not a block/connection)."""
from PySide6.QtWidgets import QMenu


class CanvasContextMenu:
    """Manages the context menu shown when right-clicking empty canvas space."""

    @staticmethod
    def show(scene, scene_pos, screen_pos):
        """
        Args:
            scene: The NodeScene that was right-clicked
            scene_pos: QPointF scene position of the click (where a new item should land)
            screen_pos: Screen position for the menu
        """
        menu = QMenu()
        action_add_annotation = menu.addAction("Add Annotation")

        selected_action = menu.exec(screen_pos)
        if selected_action is None:
            return

        if selected_action == action_add_annotation:
            scene.add_annotation(scene_pos)
