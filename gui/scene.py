"""NodeScene - The graphics scene for block diagrams."""
from PySide6.QtWidgets import QGraphicsScene
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from config.ui_config import UIConfig
from .items import UIPort, UIConnection, UIBlock
from .menus import BlockContextMenu, ConnectionContextMenu


class NodeScene(QGraphicsScene):
    """Graphics scene for node-based editing."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(UIConfig.BACKGROUND_COLOR)
        self.temp_connection = None
        self.start_port_ui = None

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

        super().mousePressEvent(event)

    def delete_block(self, block_item):
        """Delete a block and all its connections."""
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
            except ValueError:
                pass

    def delete_connection(self, conn):
        """Delete a connection."""
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
        except Exception:
            pass

    def mouseMoveEvent(self, event):
        if self.temp_connection:
            self.temp_connection.update_path(event.scenePos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.temp_connection:
            item = self.itemAt(event.scenePos(), self.views()[0].transform())
            if isinstance(item, UIPort) and item.is_input and item != self.start_port_ui:
                self.complete_connection(self.start_port_ui, item, self.temp_connection)
            else:
                self.removeItem(self.temp_connection)

            self.temp_connection = None
            self.start_port_ui = None
        super().mouseReleaseEvent(event)

    def complete_connection(self, start_ui, end_ui, conn_ui):
        """Complete a connection between two ports."""
        conn_ui.end_port = end_ui
        conn_ui.update_path()
        start_ui.connections.append(conn_ui)
        end_ui.connections.append(conn_ui)
        end_ui.model.connected_port = start_ui.model

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        # Check for Copy/Cut/Paste
        modifiers = event.modifiers()
        if modifiers & Qt.ControlModifier:
            parent = self.parent()
            if parent and hasattr(parent, 'scene_manager'):
                if event.key() == Qt.Key_C:
                    parent.scene_manager.copy_selection()
                    event.accept()
                    return
                elif event.key() == Qt.Key_X:
                    parent.scene_manager.cut_selection()
                    event.accept()
                    return
                elif event.key() == Qt.Key_V:
                    parent.scene_manager.paste_selection()
                    event.accept()
                    return

        if event.key() == Qt.Key_R:
            for item in self.selectedItems():
                if isinstance(item, UIBlock):
                    item.rotate_90()
            event.accept()
        # Delete key shortcut
        elif event.key() == Qt.Key_Delete:
            for item in self.selectedItems():
                if isinstance(item, UIBlock):
                    self.delete_block(item)
                elif isinstance(item, UIConnection):
                    self.delete_connection(item)
            event.accept()
        else:
            super().keyPressEvent(event)