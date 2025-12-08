"""Context menu for blocks."""
from PySide6.QtWidgets import QMenu, QInputDialog


class BlockContextMenu:
    """Manages context menu for UIBlock items."""
    
    @staticmethod
    def show(block_ui, scene, screen_pos):
        """
        Show context menu for a block.
        
        Args:
            block_ui: The UIBlock that was right-clicked
            scene: The NodeScene containing the block
            screen_pos: Screen position for the menu
        """
        menu = QMenu()
        
        # Actions
        action_rename = menu.addAction("Rename")
        action_rotate = menu.addAction("Rotate (R)")
        menu.addSeparator()
        action_delete = menu.addAction("Delete")

        # Execute
        selected_action = menu.exec(screen_pos)

        if selected_action == action_delete:
            scene.delete_block(block_ui)
        elif selected_action == action_rotate:
            block_ui.rotate_90()
        elif selected_action == action_rename:
            BlockContextMenu.rename_block(block_ui)
    
    @staticmethod
    def rename_block(block_ui):
        """
        Opens a dialog to rename the block via its 'BlockName' param.
        
        Args:
            block_ui: The UIBlock to rename
        """
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
