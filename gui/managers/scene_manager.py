"""Manages scene operations, serialization, and subsystem navigation."""
from PySide6.QtWidgets import QMessageBox, QFileDialog
from PySide6.QtCore import QPointF
import json
import os
from engine.serialization import GraphSerializer
from engine.blocks import BLOCK_REGISTRY
from ..items import UIBlock, UIConnection, UIAnnotation
from .undo_manager import UndoManager


class SceneManager:
    """Owns one open diagram: its scene, blocks, undo history, and file
    state. MainWindow can have several of these alive at once (one per
    open Diagram tab, see MainWindow.open_diagram_tab()) -- `scene` is
    THIS diagram's own NodeScene, passed in explicitly rather than
    reached via `main_window.scene` (which is a property pointing at
    whichever diagram tab is currently active, not necessarily this
    one)."""

    def __init__(self, main_window, scene):
        self.main_window = main_window
        self.scene = scene
        self.blocks_ui = []
        self.annotations_ui = []
        self.current_file_path = None
        self.is_modified = False
        self._baseline_taken = False

        self.undo_manager = UndoManager(self)
        self.take_snapshot() # Initial empty state snapshot

        # Clipboard is intentionally NOT per-instance -- it lives on
        # main_window (see copy_selection()/paste_selection() below) so
        # Ctrl+C in one diagram tab and Ctrl+V in another actually works,
        # instead of each diagram only ever seeing its own copies.

        # Subsystem navigation
        self.subsystem_stack = []
        self.breadcrumb_label = None

    def take_snapshot(self):
        """Helper to take a snapshot for undo/redo."""
        self.undo_manager.take_snapshot()
        # The very first snapshot (taken in __init__, and again whenever
        # _open_diagram_file()/_load_scene_data() re-baseline the document)
        # reflects a just-loaded/blank state, not an edit -- don't flag it
        # dirty.
        if self._baseline_taken:
            self.set_modified(True)
        else:
            self._baseline_taken = True

    def set_modified(self, modified):
        """Update the dirty flag and refresh the window title's [*]
        indicator plus this diagram's own tab label (e.g. 'sim.json •') --
        other open diagrams' tabs are untouched."""
        self.is_modified = modified
        if hasattr(self.main_window, "refresh_title"):
            self.main_window.refresh_title()
        if hasattr(self.main_window, "update_diagram_tab_title"):
            self.main_window.update_diagram_tab_title(self)

    def _status(self, message):
        """Routine, non-blocking confirmation (saved/loaded/...) shown in
        the status bar instead of an interrupting QMessageBox.information()
        -- see MainWindow.show_status()."""
        if hasattr(self.main_window, "show_status"):
            self.main_window.show_status(message)

    def confirm_discard_changes(self):
        """Ask to save this diagram's unsaved changes before closing its
        tab or the whole app (New/Open create their own tab instead of
        touching this one, so they no longer need to go through here).

        Returns True if it's safe to proceed (no changes, discarded, or saved
        successfully), False if the caller should abort (user cancelled, or
        chose Save but the save dialog was itself cancelled).
        """
        if not self.is_modified:
            return True

        reply = QMessageBox.question(
            self.main_window,
            "Unsaved Changes",
            "This diagram has unsaved changes. Save them before continuing?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Save:
            self.save_graph()
            return not self.is_modified
        return reply == QMessageBox.Discard

    def add_block_to_scene(self, list_item):
        """Add a block from the library to the scene (ListWidget version)."""
        self.add_block_by_name(list_item.text())

    def add_block_by_name(self, block_class_name):
        """Add a block from the library to the scene by string name."""
        if block_class_name in BLOCK_REGISTRY:
            new_block = BLOCK_REGISTRY[block_class_name]()
            ui_block = UIBlock(new_block)
            ui_block.setPos(100, 100)
            self.scene.addItem(ui_block)
            self.blocks_ui.append(ui_block)
            self.take_snapshot()
    
    def save_selected_subgraph_to_library(self):
        """
        Saves the selected SubGraph block to User Space.
        """
        selected = self.scene.selectedItems()
        subgraph_blocks = [item for item in selected if isinstance(item, UIBlock) 
                          and item.model.__class__.__name__ == "SubGraph"]
        
        if not subgraph_blocks:
            self._status("Select a SubGraph block first.")
            return

        if len(subgraph_blocks) > 1:
            self._status("Select only one SubGraph to save.")
            return
        
        subgraph_ui = subgraph_blocks[0]
        subgraph_model = subgraph_ui.model
        
        # Serialize the internal data
        subgraph_data = {
            "blocks": subgraph_model.internal_blocks_data,
            "connections": subgraph_model.internal_connections_data,
            "params": subgraph_model.params.copy()
        }
        
        # Ask for a name
        subgraph_name = subgraph_model.params.get("BlockName", "SubGraph")
        
        # Save via the User Space widget
        self.main_window.user_space_widget.save_subgraph(subgraph_data, subgraph_name)
    
    def spawn_subgraph_from_library(self, file_path):
        """
        Loads a JSON file from library and creates a SubGraph block.
        """
        if hasattr(self.main_window, "show_diagram_editor"):
            self.main_window.show_diagram_editor()

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                subgraph_data = json.load(f)
            
            # Create a new SubGraph block
            if "SubGraph" not in BLOCK_REGISTRY:
                QMessageBox.critical(self.main_window, "Error", "SubGraph block type not found.")
                return
            
            new_subgraph = BLOCK_REGISTRY["SubGraph"]()
            new_subgraph.internal_blocks_data = subgraph_data.get("blocks", [])
            new_subgraph.internal_connections_data = subgraph_data.get("connections", [])
            
            # Load interface parameters (custom variables & name)
            if "params" in subgraph_data:
                new_subgraph.params.update(subgraph_data["params"])
                # Ensure label updates with loaded name
                if hasattr(new_subgraph, "_update_label"):
                    new_subgraph._update_label()
            
            # Refresh ports based on internal InputPort/OutputPort blocks
            new_subgraph.refresh_io_ports()
            
            ui_block = UIBlock(new_subgraph)
            ui_block.setPos(150, 150)
            ui_block.refresh_ports()
            
            self.scene.addItem(ui_block)
            self.blocks_ui.append(ui_block)

            self._status(f"Loaded SubGraph from {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to load SubGraph: {str(e)}")
    
    def enter_subsystem(self, subsystem_ui_block):
        """Called when double-clicking a SubSystem block."""
        subsystem_model = subsystem_ui_block.model

        # Save current scene state
        current_data = GraphSerializer.serialize_graph(self.blocks_ui)
        self.subsystem_stack.append({
            "data": current_data,
            "subsystem_model": subsystem_model,
            # Snapshot each InputPort/OutputPort's name at entry time, keyed
            # by the live model object's id (stable for the duration of this
            # edit session, even though it's reassigned a fresh numeric id
            # on entry vs. whatever internal_blocks_data had saved). Used by
            # go_up_level() to detect renames and fix up the parent-level
            # wire that references the OLD name -- see there for why.
            "initial_port_names": {},
        })

        # Load subsystem internal scene
        internal_data = {
            "blocks": subsystem_model.internal_blocks_data,
            "connections": subsystem_model.internal_connections_data
        }
        self._load_scene_data(internal_data)

        initial_port_names = self.subsystem_stack[-1]["initial_port_names"]
        for ui_block in self.blocks_ui:
            if ui_block.model.__class__.__name__ in ("InputPort", "OutputPort"):
                initial_port_names[ui_block.model.id] = ui_block.model.params.get("PortName")

        self._update_breadcrumb()

    def go_up_level(self):
        """Called by Toolbar button to go back up."""
        if not self.subsystem_stack:
            self._status("Already at top level.")
            return

        # 0. Detect InputPort/OutputPort renames made while inside, so the
        # parent-level wire (recorded by name in parent_data["connections"]
        # back when we entered) can be re-pointed at the new name instead of
        # silently failing to reconnect -- sync_ports_from_data() rebuilds
        # the SubGraph's ports keyed by the CURRENT name, so a stale
        # old-name connection reference would otherwise just find nothing.
        parent_context = self.subsystem_stack[-1]
        initial_port_names = parent_context["initial_port_names"]
        input_renames = {}
        output_renames = {}
        for ui_block in self.blocks_ui:
            cls_name = ui_block.model.__class__.__name__
            if cls_name not in ("InputPort", "OutputPort"):
                continue
            old_name = initial_port_names.get(ui_block.model.id)
            new_name = ui_block.model.params.get("PortName")
            if old_name is not None and old_name != new_name:
                if cls_name == "InputPort":
                    input_renames[old_name] = new_name
                else:
                    output_renames[old_name] = new_name

        # 1. Serialize the CURRENT scene (the inside of the subsystem)
        current_subsystem_data = GraphSerializer.serialize_graph(self.blocks_ui)

        # 2. Get the parent context
        parent_data = parent_context["data"]
        subsystem_id = parent_context["subsystem_model"].id

        # 3. Update the SubGraph block in the PARENT data with new internal data
        # We must find the block data that corresponds to the subsystem we are leaving
        found = False
        for block_data in parent_data.get("blocks", []):
            if block_data.get("id") == subsystem_id:
                block_data["internal_blocks_data"] = current_subsystem_data["blocks"]
                block_data["internal_connections_data"] = current_subsystem_data["connections"]
                found = True
                break

        if not found:
            print(f"Warning: Could not find original SubGraph block (ID: {subsystem_id}) in parent data.")

        # 3b. Re-point any parent-level wire attached to a renamed port.
        if input_renames or output_renames:
            for conn_data in parent_data.get("connections", []):
                if conn_data.get("to_block_id") == subsystem_id and conn_data.get("to_port") in input_renames:
                    conn_data["to_port"] = input_renames[conn_data["to_port"]]
                if conn_data.get("from_block_id") == subsystem_id and conn_data.get("from_port") in output_renames:
                    conn_data["from_port"] = output_renames[conn_data["from_port"]]

        # 4. Restore parent scene from the UPDATED data
        # This creates NEW block instances, so the old subsystem_model reference is indeed obsolete
        # The GraphSerializer now automatically syncs ports during deserialization (Step 165),
        # so connections are restored correctly by _load_scene_data.
        # We DO NOT need to manually refresh ports here anymore; doing so breaks the just-restored connections.
        self._load_scene_data(parent_data)

        self.subsystem_stack.pop()
        self._update_breadcrumb()
        
    def go_to_top_level(self):
        """Navigate back to the top level (First Simulation Layer)."""
        while self.subsystem_stack:
            self.go_up_level()
    
    def save_graph(self):
        """Save the current graph."""
        if self.current_file_path:
            self._save_to_file(self.current_file_path)
        else:
            self.save_graph_as()
    
    def _default_open_dir(self):
        """Starting directory for the Save As file picker: the current
        project folder, if one is open."""
        project_manager = getattr(self.main_window, "project_manager", None)
        return project_manager.project_root if project_manager and project_manager.project_root else ""

    def load_file(self, file_path):
        """Load `file_path` into THIS (freshly-created, blank) diagram.
        Called by MainWindow.open_diagram_tab() right after constructing
        a new tab for it -- opening a diagram no longer overwrites
        whatever's already on screen, it gets its own tab, so there's
        nothing here to confirm discarding."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._load_scene_data(data)
            self.current_file_path = file_path
            self.undo_manager.undo_stack.clear()
            self.undo_manager.redo_stack.clear()
            self._baseline_taken = False
            self.take_snapshot()
            self.set_modified(False)
            self._status(f"Loaded {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to load: {str(e)}")

    def save_graph_as(self):
        """Save the current graph to a new file, via a picker defaulted
        into the current project folder."""
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Graph As",
            self._default_open_dir(),
            "JSON Files (*.json)"
        )
        if file_path:
            self.current_file_path = file_path
            self._save_to_file(file_path)

    def _save_to_file(self, file_path):
        """Internal method to save graph to file."""
        try:
            tm = getattr(self.main_window, 'toolbar_manager', None)
            sim_params = None
            if tm is not None:
                sim_params = {
                    "duration": tm.sim_duration,
                    "dt": tm.sim_dt,
                    "solver": tm.sim_solver,
                }
            data = GraphSerializer.serialize_graph(self.blocks_ui, self.annotations_ui, sim_params)
            # Lets User Space tell this apart from a SubGraph .json in the
            # same flat project folder -- see UserSpaceWidget._classify().
            data["blocksimpy_kind"] = "diagram"
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self.set_modified(False)

            # In case this landed in the current project folder, reflect it
            # in User Space's Diagrams list right away.
            user_space = getattr(self.main_window, "user_space_widget", None)
            if user_space is not None:
                user_space.refresh_tree()

            self._status(f"Saved {os.path.basename(file_path)}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to save: {str(e)}")
    
    def _load_scene_data(self, data):
        """Helper: Clears scene and loads from dictionary."""
        # Clear current scene
        self.scene.clear()
        self.blocks_ui.clear()
        self.annotations_ui.clear()

        # Deserialize
        block_models, connections_data = GraphSerializer.deserialize_graph(data)

        # Restore simulation settings (duration/dt/solver) if the file has
        # them -- absent for older save files or subsystem-internal data
        # (enter_subsystem/go_up_level also route through this method), in
        # which case the toolbar's current values are simply left alone.
        sim_params = GraphSerializer.deserialize_simulation_params(data)
        if sim_params:
            tm = getattr(self.main_window, 'toolbar_manager', None)
            if tm is not None:
                if "duration" in sim_params:
                    tm.sim_duration = sim_params["duration"]
                if "dt" in sim_params:
                    tm.sim_dt = sim_params["dt"]
                if "solver" in sim_params:
                    tm.sim_solver = sim_params["solver"]

        # Create UI blocks
        id_to_ui_block = {}
        for block_model in block_models:
            ui_block = UIBlock(block_model)
            
            # Restore position and rotation
            if hasattr(block_model, '_temp_position'):
                pos = block_model._temp_position
                ui_block.setPos(QPointF(pos['x'], pos['y']))
                delattr(block_model, '_temp_position')
            
            if hasattr(block_model, '_temp_rotation'):
                ui_block.setRotation(block_model._temp_rotation)
                delattr(block_model, '_temp_rotation')
            
            self.scene.addItem(ui_block)
            self.blocks_ui.append(ui_block)
            id_to_ui_block[block_model.id] = ui_block
        
        # Recreate connections
        for conn_data in connections_data:
            from_block = conn_data["from_block"]
            to_block = conn_data["to_block"]
            from_port_name = conn_data["from_port"]
            to_port_name = conn_data["to_port"]
            
            from_ui = id_to_ui_block.get(from_block.id)
            to_ui = id_to_ui_block.get(to_block.id)
            
            if from_ui and to_ui:
                from_port_ui = from_ui.ports_ui.get(from_port_name)
                to_port_ui = to_ui.ports_ui.get(to_port_name)
                
                if from_port_ui and to_port_ui:
                    conn = UIConnection(from_port_ui, to_port_ui)
                    
                    # Restore path points if available
                    if conn_data.get("points"):
                        conn.points = [QPointF(p[0], p[1]) for p in conn_data["points"]]
                    
                    conn.update_path()
                    self.scene.addItem(conn)
                    from_port_ui.connections.append(conn)
                    to_port_ui.connections.append(conn)
                    to_port_ui.model.connected_port = from_port_ui.model

        # Recreate annotations (free-text notes; no connections/id_map involved)
        for entry in GraphSerializer.deserialize_annotations(data):
            annotation = UIAnnotation(entry["text"])
            annotation.setPos(entry["x"], entry["y"])
            self.scene.addItem(annotation)
            self.annotations_ui.append(annotation)

    def copy_selection(self):
        """Copy selected blocks to the shared cross-diagram clipboard (see
        main_window.diagram_clipboard)."""
        selected = self.scene.selectedItems()
        blocks = [item for item in selected if isinstance(item, UIBlock)]
        if not blocks:
            return

        self.main_window.diagram_clipboard = GraphSerializer.serialize_graph(blocks)
        # Each fresh copy restarts the paste offset, so the first paste of a
        # new copy lands right next to the originals again instead of
        # continuing to cascade from a previous copy/paste sequence.
        self.main_window.diagram_clipboard_paste_count = 0

    def cut_selection(self):
        """Cut selected blocks to the shared cross-diagram clipboard."""
        self.copy_selection()

        # Delete selected blocks (and their connections automatically via scene.delete_block)
        selected = self.scene.selectedItems()
        blocks_to_delete = [item for item in selected if isinstance(item, UIBlock)]

        scene = self.scene
        for block in blocks_to_delete:
            scene.delete_block(block)

    def paste_selection(self):
        """Paste blocks from the shared cross-diagram clipboard into THIS
        diagram -- so Ctrl+C in one diagram tab and Ctrl+V in another (or
        the same one) both work. Cascades further each repeated paste so
        identical Ctrl+V presses don't stack blocks on top of each other."""
        clipboard_data = getattr(self.main_window, "diagram_clipboard", None)
        if not clipboard_data:
            return

        self.main_window.diagram_clipboard_paste_count = (
            getattr(self.main_window, "diagram_clipboard_paste_count", 0) + 1
        )
        offset = 20 * self.main_window.diagram_clipboard_paste_count
        self._paste_data(clipboard_data, offset, offset)

    def duplicate_selection(self):
        """Duplicate the selected blocks in place, offset slightly, without
        touching the clipboard (so it doesn't clobber a pending Copy)."""
        selected = self.scene.selectedItems()
        blocks = [item for item in selected if isinstance(item, UIBlock)]
        if not blocks:
            return

        data = GraphSerializer.serialize_graph(blocks)
        self._paste_data(data, 20, 20)

    def _paste_data(self, data, offset_x, offset_y):
        """Shared implementation behind Paste and Duplicate: deserialize
        `data` (fresh block/connection ids), place it offset from its
        original position, and select the newly created items."""
        self.scene.clearSelection()

        block_models, connections_data = GraphSerializer.deserialize_graph(data)

        id_to_ui_block = {}

        for block_model in block_models:
            ui_block = UIBlock(block_model)

            if hasattr(block_model, '_temp_position'):
                pos = block_model._temp_position
                new_x = pos['x'] + offset_x
                new_y = pos['y'] + offset_y
                ui_block.setPos(QPointF(new_x, new_y))
                delattr(block_model, '_temp_position')

            if hasattr(block_model, '_temp_rotation'):
                ui_block.setRotation(block_model._temp_rotation)
                delattr(block_model, '_temp_rotation')

            self.scene.addItem(ui_block)
            self.blocks_ui.append(ui_block)
            id_to_ui_block[block_model.id] = ui_block

            if hasattr(block_model, "refresh_io_ports"):
                block_model.refresh_io_ports()
                ui_block.refresh_ports()

            ui_block.setSelected(True)

        for conn_data in connections_data:
            from_block = conn_data["from_block"]
            to_block = conn_data["to_block"]
            from_port_name = conn_data["from_port"]
            to_port_name = conn_data["to_port"]

            from_ui = id_to_ui_block.get(from_block.id)
            to_ui = id_to_ui_block.get(to_block.id)

            if from_ui and to_ui:
                from_port_ui = from_ui.ports_ui.get(from_port_name)
                to_port_ui = to_ui.ports_ui.get(to_port_name)

                if from_port_ui and to_port_ui:
                    conn = UIConnection(from_port_ui, to_port_ui)

                    if conn_data.get("points"):
                        conn.points = [QPointF(p[0] + offset_x, p[1] + offset_y) for p in conn_data["points"]]

                    conn.update_path()
                    self.scene.addItem(conn)
                    from_port_ui.connections.append(conn)
                    to_port_ui.connections.append(conn)
                    to_port_ui.model.connected_port = from_port_ui.model

                    conn.setSelected(True)

        self.take_snapshot()

    def rename_selected(self):
        """Rename the single selected block (F2). No-ops on 0 or 2+ blocks
        selected -- there's no sensible target/name to use otherwise."""
        selected = self.scene.selectedItems()
        blocks = [item for item in selected if isinstance(item, UIBlock)]
        if len(blocks) != 1:
            return

        from ..menus.block_menu import BlockContextMenu
        BlockContextMenu.rename_block(blocks[0])
        self.take_snapshot()

    def _update_breadcrumb(self):
        """Update breadcrumb navigation label."""
        if self.breadcrumb_label:
            depth = len(self.subsystem_stack)
            if depth == 0:
                self.breadcrumb_label.setText("📍 Location: Top Level")
            else:
                self.breadcrumb_label.setText(f"📍 Location: Subsystem (Depth {depth})")
