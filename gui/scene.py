"""NodeScene - The graphics scene for block diagrams."""
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor
from config.ui_config import UIConfig
from .items import UIPort, UIConnection, UIBlock, UIAnnotation
from .menus import BlockContextMenu, ConnectionContextMenu, CanvasContextMenu


class NodeScene(QGraphicsScene):
    """Graphics scene for node-based editing."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(UIConfig.BACKGROUND_COLOR)
        self.temp_connection = None
        self.start_port_ui = None
        
        # Displacement state
        self._dragging_items = False
        self._last_mouse_pos = QPointF()

    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos(), self.views()[0].transform())

        # 1. Handle Ports (Start Connection) - Left Click
        if event.button() == Qt.LeftButton and isinstance(item, UIPort):
            if not item.is_input:
                self.start_port_ui = item
                self.temp_connection = UIConnection(item)
                self.addItem(self.temp_connection)
                super().mousePressEvent(event)
                return

        # 2. Handle Right Click (Context Menu)
        if event.button() == Qt.RightButton:
            if isinstance(item, UIBlock):
                BlockContextMenu.show(item, self, event.screenPos())
                return
            elif isinstance(item, UIConnection):
                ConnectionContextMenu.show(item, self, event.screenPos())
                return
            elif not isinstance(item, UIAnnotation):
                # Empty canvas (or clicked an annotation -- let its own
                # context/edit behavior take over rather than this menu).
                CanvasContextMenu.show(self, event.scenePos(), event.screenPos())
                return

        # 3. Handle Displacement Start
        if event.button() == Qt.LeftButton and isinstance(item, UIBlock):
            self._dragging_items = True
            self._last_mouse_pos = event.scenePos()

        super().mousePressEvent(event)

    def delete_block(self, block_item):
        """Delete a block and all its connections.

        No-ops if the block is already gone -- e.g. Select All followed by
        Delete selects blocks AND their connections together, and deleting
        a block already deletes its attached connections below; without
        this guard, delete_selected() would then try to delete that same
        connection a second time when it reaches it directly, hitting
        QGraphicsScene::removeItem on an item no longer in any scene.
        """
        if block_item.scene() is not self:
            return

        # Remove all connections attached to the block's ports
        for port in list(block_item.ports_ui.values()):
            for conn in list(port.connections):
                self.delete_connection(conn)
            port.connections.clear()

        # Remove the block graphic
        self.removeItem(block_item)

        # Remove from Main Window registry
        parent = self.parent()
        if parent and hasattr(parent, 'scene_manager'):
            try:
                parent.scene_manager.blocks_ui.remove(block_item)
                parent.scene_manager.take_snapshot()
            except ValueError:
                pass

    def add_annotation(self, pos, text="Note"):
        """Create a free-text note at the given scene position."""
        annotation = UIAnnotation(text)
        annotation.setPos(pos)
        self.addItem(annotation)

        parent = self.parent()
        if parent and hasattr(parent, 'scene_manager'):
            parent.scene_manager.annotations_ui.append(annotation)
            parent.scene_manager.take_snapshot()
        return annotation

    def delete_annotation(self, annotation_item):
        """Delete a free-text annotation. No-op if already removed (see
        delete_block's docstring for why that can happen)."""
        if annotation_item.scene() is not self:
            return
        self.removeItem(annotation_item)

        parent = self.parent()
        if parent and hasattr(parent, 'scene_manager'):
            try:
                parent.scene_manager.annotations_ui.remove(annotation_item)
                parent.scene_manager.take_snapshot()
            except ValueError:
                pass

    def delete_connection(self, conn):
        """Delete a connection. No-op if already removed (see delete_block's
        docstring for why that can happen)."""
        if conn.scene() is not self:
            return
        try:
            # remove connection from ports
            if conn.start_port and conn in conn.start_port.connections:
                conn.start_port.connections.remove(conn)
            if conn.end_port and conn in conn.end_port.connections:
                conn.end_port.connections.remove(conn)
                # Clear the model connection!
                if conn.end_port.model.connected_port == conn.start_port.model:
                    conn.end_port.model.connected_port = None
            self.removeItem(conn)

            parent = self.parent()
            if parent and hasattr(parent, 'scene_manager'):
                parent.scene_manager.take_snapshot()
        except Exception:
            pass

    def select_all(self):
        """Select every item on the canvas (blocks, connections, annotations)."""
        for item in self.items():
            item.setSelected(True)

    def delete_selected(self):
        """Delete every currently-selected block/connection/annotation."""
        for item in self.selectedItems():
            if isinstance(item, UIBlock):
                self.delete_block(item)
            elif isinstance(item, UIConnection):
                self.delete_connection(item)
            elif isinstance(item, UIAnnotation):
                self.delete_annotation(item)

    def mouseMoveEvent(self, event):
        if self.temp_connection:
            self.temp_connection.update_path(event.scenePos())
        
        elif self._dragging_items:
            # Group Displacement
            new_pos = event.scenePos()
            delta = new_pos - self._last_mouse_pos
            self._last_mouse_pos = new_pos
            
            # Move all selected items that are blocks
            # (Connections update automatically when blocks move)
            for item in self.selectedItems():
                if isinstance(item, UIBlock):
                    item.moveBy(delta.x(), delta.y())
            # We don't call super() here when dragging items to avoid double movement
            # because UIBlock already has ItemIsMovable.
            # Actually, if we use moveBy for all, we should disable ItemIsMovable during drag
            # OR we call super and only move items OTHER than the one being dragged.
            # But we don't know which one is being dragged by super.
            # Better: Disable ItemIsMovable or handle everything here.
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # If we were dragging items, take a snapshot on release
        if self._dragging_items:
            parent = self.parent()
            if parent and hasattr(parent, 'scene_manager'):
                parent.scene_manager.take_snapshot()
                
        self._dragging_items = False
        
        if self.temp_connection:
            item = self.itemAt(event.scenePos(), self.views()[0].transform())
            if isinstance(item, UIPort) and item.is_input and item != self.start_port_ui:
                self.complete_connection(self.start_port_ui, item, self.temp_connection)
            else:
                self.removeItem(self.temp_connection)

            self.temp_connection = None
            self.start_port_ui = None
            
            # Snaphot for new connection
            parent = self.parent()
            if parent and hasattr(parent, 'scene_manager'):
                parent.scene_manager.take_snapshot()
        super().mouseReleaseEvent(event)

    def complete_connection(self, start_ui, end_ui, conn_ui):
        """Complete a connection between two ports."""
        # An input port carries exactly one signal: rewiring it drops
        # whatever was previously connected there.
        for old_conn in list(end_ui.connections):
            self.delete_connection(old_conn)

        conn_ui.end_port = end_ui
        conn_ui.update_path()
        start_ui.connections.append(conn_ui)
        end_ui.connections.append(conn_ui)
        end_ui.model.connected_port = start_ui.model
        conn_ui.refresh_highlight()

    def keyPressEvent(self, event):
        """Handle the one shortcut that has no menu/QAction equivalent.

        Copy/Cut/Paste/Select All/Undo/Redo/Delete are now real QActions
        with shortcuts (see MainWindow's menu bar / ToolbarManager) -- Qt's
        shortcut system intercepts those key combos before they'd ever reach
        here, so handling them in both places would just be dead code.
        Rotate ("R") stays here since it's block-selection-specific and has
        no natural menu bar/File-Edit-View home.
        """
        focus_item = self.focusItem()
        if isinstance(focus_item, UIAnnotation) and focus_item.textInteractionFlags() != Qt.NoTextInteraction:
            # Actively editing an annotation's text -- let Qt's normal text
            # editing run instead of the diagram-level shortcuts below.
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key_R:
            for item in self.selectedItems():
                if isinstance(item, UIBlock):
                    item.rotate_90()

            parent = self.parent()
            if parent and hasattr(parent, 'scene_manager'):
                parent.scene_manager.take_snapshot()
            event.accept()
            return

        super().keyPressEvent(event)