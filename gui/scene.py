from PySide6.QtWidgets import QGraphicsScene, QGraphicsView
from PySide6.QtCore import QPointF, Qt

from .items import UIPort, UIConnection, UIBlock


from PySide6.QtWidgets import QGraphicsScene, QMenu, QInputDialog, QMessageBox
from PySide6.QtCore import Qt
from .items import UIPort, UIConnection, UIBlock

class NodeScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtGui import QColor
        self.setBackgroundBrush(QColor(30, 30, 30))
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
                self.open_block_context_menu(item, event.screenPos())
                return
            elif isinstance(item, UIConnection):
                self.open_connection_context_menu(item, event.screenPos())
                return

        super().mousePressEvent(event)

    def open_block_context_menu(self, block_ui, screen_pos):
        """Creates a menu with options: Rename, Rotate, Delete."""
        menu = QMenu()
        
        # Actions
        action_rename = menu.addAction("Rename")
        action_rotate = menu.addAction("Rotate (R)")
        menu.addSeparator()
        action_delete = menu.addAction("Delete")

        # Execute
        selected_action = menu.exec(screen_pos)

        if selected_action == action_delete:
            self.delete_block(block_ui)
        elif selected_action == action_rotate:
            block_ui.rotate_90()
        elif selected_action == action_rename:
            self.rename_block(block_ui)

    def open_connection_context_menu(self, conn_ui, screen_pos):
        menu = QMenu()
        action_delete = menu.addAction("Delete Connection")
        
        if menu.exec(screen_pos) == action_delete:
            self.delete_connection(conn_ui)

    def rename_block(self, block_ui):
        """Opens a dialog to rename the block via its 'BlockName' param."""
        current_name = block_ui.model.params.get("BlockName", block_ui.model.name)
        
        new_name, ok = QInputDialog.getText(None, "Rename Block", "New Name:", text=current_name)
        
        if ok and new_name:
            # Update the parameter
            block_ui.model.params["BlockName"] = new_name
            
            # Trigger the label update if the model has the method
            if hasattr(block_ui.model, "_update_label"):
                block_ui.model._update_label()
            else:
                # Fallback for simple blocks without custom label logic
                block_ui.model.name = new_name
            
            # Force redraw
            block_ui.update()

    def delete_block(self, block_item):
        # Remove all connections attached to the block's ports
        for port in list(block_item.ports_ui.values()):
            for conn in list(port.connections):
                self.delete_connection(conn)
            port.connections.clear()

        # Remove the block graphic
        self.removeItem(block_item)

        # Remove from Main Window registry
        parent = self.parent()
        if parent and hasattr(parent, 'blocks_ui'):
            try:
                parent.blocks_ui.remove(block_item)
            except ValueError:
                pass

    def delete_connection(self, conn):
        try:
            # remove connection from ports
            if conn.start_port and conn in conn.start_port.connections:
                conn.start_port.connections.remove(conn)
            if conn.end_port and conn in conn.end_port.connections:
                conn.end_port.connections.remove(conn)
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
        conn_ui.end_port = end_ui
        conn_ui.update_path()
        start_ui.connections.append(conn_ui)
        end_ui.connections.append(conn_ui)
        end_ui.model.connected_port = start_ui.model

    def keyPressEvent(self, event):
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