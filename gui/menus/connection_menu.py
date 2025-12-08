"""Context menu for connections."""
from PySide6.QtWidgets import QMenu


class ConnectionContextMenu:
    """Manages context menu for UIConnection items."""
    
    @staticmethod
    def show(conn_ui, scene, screen_pos):
        """
        Show context menu for a connection.
        
        Args:
            conn_ui: The UIConnection that was right-clicked
            scene: The NodeScene containing the connection
            screen_pos: Screen position for the menu
        """
        menu = QMenu()
        action_delete = menu.addAction("Delete Connection")
        
        if menu.exec(screen_pos) == action_delete:
            scene.delete_connection(conn_ui)
