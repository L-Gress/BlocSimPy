"""Manages user scripts and execution environment."""
import os
from PySide6.QtWidgets import QMessageBox

class ScriptManager:
    """Manages user scripts and provides execution context."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.current_script = (
            "# BlocSimPy Scripting Interface\n"
            "# -----------------------------\n"
            "# Available functions:\n"
            "#   set_param(block_name, param_name, value)\n"
            "#   run_simulation()\n"
            "#   print(text)\n\n"
            "print('Hello from BlocSimPy!')\n"
        )
        
    def show_editor(self):
        """Show the script editor dialog."""
        from ..dialogs import ScriptEditorDialog
        dialog = ScriptEditorDialog(self.main_window, self)
        dialog.exec()
        
    def execute_script(self, script_content):
        """
        Execute the provided script content with access to the simulation environment.
        
        Returns:
            str: Output of the script (print statements)
        """
        output_lines = []
        
        # --- helper functions exposed to script ---
        
        def custom_print(*args):
            line = " ".join(str(a) for a in args)
            output_lines.append(line)
        
        def set_param(block_name, param_name, value):
            """
            Set a parameter on a block (or SubGraph interface variable).
            Strictly enforced to work only at Top Level and on existing Interface parameters.
            """
            # 1. Enforce First Simulation Layer (Top Level)
            if self.main_window.scene_manager.subsystem_stack:
                custom_print("❌ Error: set_param allowed only at Top Level (First Simulation Layer).")
                custom_print("   Please use go_to_top() or exit the subsystem.")
                return

            found_count = 0
            
            # Helper to check matching names
            def name_matches(block):
                return block.model.params.get("BlockName") == block_name

            for ui_block in self.main_window.scene_manager.blocks_ui:
                if name_matches(ui_block):
                    # 2. Enforce Interface: Only allow modifying EXISTING parameters
                    # This ensures we respect the defined SubGraph interface isolation.
                    if param_name not in ui_block.model.params:
                        custom_print(f"❌ Error: Parameter '{param_name}' not defined in interface of '{block_name}'.")
                        custom_print(f"   Open the block settings to add '{param_name}' to the exposed interface.")
                        continue # Try next block if duplicate names? Actually strict match usually unique.

                    # Convert value if needed (try float)
                    final_val = value
                    try:
                        final_val = float(value)
                    except:
                        pass
                        
                    ui_block.model.params[param_name] = final_val
                    
                    # Trigger visual update
                    if hasattr(ui_block.model, "_update_label"):
                        ui_block.model._update_label()
                    ui_block.update()
                    
                    found_count += 1
            
            if found_count > 0:
                custom_print(f"✓ Set {block_name}.{param_name} = {value}")
            else:
                custom_print(f"⚠ Warning: Block '{block_name}' not found at Top Level.")
                
        def run_simulation():
            """Trigger the simulation run."""
            # Enforce First Simulation Layer rule
            if self.main_window.scene_manager.subsystem_stack:
                custom_print("⚠ Warning: You are running simulation from inside a Subsystem.")
                custom_print("   Standard usage is to run from the Top Level (First Layer).")
                custom_print("   Current simulation is local to this subsystem.")
                
            custom_print("▶ Starting simulation...")
            # We must run this on the main thread ideally, since it opens message boxes.
            # Since exec() assumes blocking, this is fine.
            self.main_window.toolbar_manager.run_simulation()
            custom_print("✓ Simulation finished.")

        def get_blocks():
            """
            Get a list of all block names at the current (Top) level.
            Returns:
                list: List of block name strings.
            """
            # Enforce Top Level
            if self.main_window.scene_manager.subsystem_stack:
                 custom_print("⚠ Info: get_blocks listing blocks in current SUBSYSTEM (not top level).")
            
            names = []
            for ui_block in self.main_window.scene_manager.blocks_ui:
                name = ui_block.model.params.get("BlockName", "Unnamed")
                names.append(name)
            
            return names

        def get_block_info(block_name):
            """
            Get information parameter variables for a specific block.
            - For SubGraphs: Returns all interface parameters.
            - For Standard Blocks: Returns ONLY parameters set to a '$variable'.
            """
            for ui_block in self.main_window.scene_manager.blocks_ui:
                params = ui_block.model.params
                # Check user-defined Name
                if params.get("BlockName") == block_name:
                    is_subgraph = ui_block.model.__class__.__name__ == "SubGraph"
                    result_params = {}
                    
                    for key, val in params.items():
                        if key == "BlockName":
                            continue
                            
                        # Logic:
                        # 1. If value is "$Var", we always include it (stripped), regardless of block type.
                        #    This handles passing variables into SubGraphs or Standard Blocks.
                        # 2. If Block is SubGraph, we ALSO include numeric/string values (Interface defaults).
                        
                        if isinstance(val, str) and val.strip().startswith("$"):
                            # It's a variable placeholder -> strip '$'
                            result_params[key] = val.strip()[1:]
                        elif is_subgraph:
                            # SubGraph interface parameter (default value) -> include as is
                            result_params[key] = val
                            
                    return result_params
            
            custom_print(f"⚠ Warning: Block '{block_name}' not found.")
            return None

        # --- Execution Context ---
        local_scope = {
            "set_param": set_param,
            "run_simulation": run_simulation,
            "print": custom_print,
            "go_to_top": self.main_window.scene_manager.go_to_top_level,
            "get_blocks": get_blocks,
            "get_block_info": get_block_info
        }
        
        try:
            exec(script_content, {}, local_scope)
            return "\n".join(output_lines)
        except Exception as e:
            return "\n".join(output_lines) + f"\n\n❌ Script Error:\n{str(e)}"
