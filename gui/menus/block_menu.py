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
        
        # Determine block type content
        action_params = None
        action_enter = None
        is_subgraph = block_ui.model.__class__.__name__ == "SubGraph"
        
        if is_subgraph:
            action_params = menu.addAction("Settings (Ctrl+DblClick)")
            action_enter = menu.addAction("Enter Subsystem (DblClick)")
        else:
            action_params = menu.addAction("Parameters (DblClick)")
            
        menu.addSeparator()
        action_delete = menu.addAction("Delete")

        # Execute
        selected_action = menu.exec(screen_pos)

        if selected_action is None:
            return

        if selected_action == action_delete:
            scene.delete_block(block_ui)
        elif selected_action == action_rotate:
            block_ui.rotate_90()
        elif selected_action == action_rename:
            BlockContextMenu.rename_block(block_ui)
            BlockContextMenu._take_snapshot(scene)
        elif selected_action == action_params:
            if hasattr(block_ui.model, 'get_editor_dialog'):
                editor = block_ui.model.get_editor_dialog(None)
                if editor:
                    editor.exec()
                    # Refresh if needed
                    if hasattr(block_ui.model, 'needs_port_refresh') and block_ui.model.needs_port_refresh:
                        block_ui.refresh_ports()
                        block_ui.model.needs_port_refresh = False
                    # SubGraph updates label on edit, force redraw
                    block_ui.update()
                    BlockContextMenu._take_snapshot(scene)
        elif selected_action == action_enter:
            # Logic to enter subsystem
            main_window = scene.parent()
            if hasattr(main_window, "enter_subsystem"):
                main_window.enter_subsystem(block_ui)
    
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

    @staticmethod
    def _take_snapshot(scene):
        """Record an undo snapshot after a menu action that edited the model
        in place (rename, parameter edit) -- take_snapshot() dedups against
        the last state, so this is a no-op if nothing actually changed."""
        main_window = scene.parent()
        if hasattr(main_window, "scene_manager"):
            main_window.scene_manager.take_snapshot()
