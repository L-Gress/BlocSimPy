"""Manages user scripts and execution environment.

The scripting console exposes a command API for driving the live scene from
code: set_param/get_param, add_block/delete_block,
add_line/delete_line, find_system, and a synchronous sim() that returns the
run's data directly (unlike the GUI's own Run button, which is async and
just opens a results tab). See DEFAULT_SCRIPT_TEMPLATE in gui/library.py for
the quick-reference shown in new scripts.

All of that acts on whichever Diagram tab is currently active in the GUI
(main_window.scene_manager) -- open_diagram()/select_diagram() change
WHICH one that is, so a script can point every following command at a
specific file (or switch between several already-open diagrams) instead of
always operating on whatever tab happens to be focused.

Within a diagram, enter_subgraph()/exit_subgraph() change WHICH level is
active the same way -- Top Level, or a SubGraph's own internal diagram --
so a script can build a SubGraph's contents (its own blocks, wires,
InputPort/OutputPort interface) the same way it builds the top level, not
just treat SubGraphs as an opaque, GUI-only feature.

There is exactly ONE execution environment per ScriptManager (one per
MainWindow -- see ScriptManager.persistent_env): every Script run,
and every command typed into the interactive Console (gui/widgets/
console_widget.py), execs against the same dict. A variable, import, or
function a Script defines is still there the next time any Script runs, or
in the Console, for the life of the app session -- like a single shared
Python REPL, not an isolated sandbox per file.
"""
import os
import sys
from collections.abc import MutableMapping
import numpy as np
from PySide6.QtWidgets import QMessageBox
from engine.blocks import BLOCK_REGISTRY
from engine.simulation import SimulationEngine
from engine.variables import make_variable_ref, find_variable_refs, set_active_variables


def _resolve_name(model):
    """A block's script-addressable name: its explicit BlockName if set,
    else the same class-default fallback used everywhere else in the engine
    (see engine/simulation/*.py) -- NOT the "Unnamed" placeholder this file
    used to fall back to, which made freshly-added/never-renamed blocks
    unaddressable by set_param."""
    return model.params.get("BlockName", model.name)


class _HelpInvoker:
    """The `help` name exposed to Scripts/the Console: opens BlocSimPy's
    own Help window (same as the toolbar's Help button) instead of
    Python's built-in help(), which would otherwise freeze the app -- bare
    help() opens an interactive prompt, and help(x) an output pager, and
    neither has a real terminal here to read/write through.

    Works whether typed bare (`help`, via __repr__ -- the Console echoes a
    bare expression's repr) or called (`help()`/`help(x)`, via __call__):
    either way just opens the window. Any argument to help(x) is ignored --
    unlike the real help(), this never tries to print docs for a specific
    object; it's a fixed window, not a lookup."""

    def __init__(self, main_window):
        self._main_window = main_window

    def _open(self):
        if hasattr(self._main_window, "show_help"):
            self._main_window.show_help()

    def __call__(self, *args, **kwargs):
        self._open()

    def __repr__(self):
        self._open()
        return "Opening the Help window..."


class _GlobalVariablesView(MutableMapping):
    """A live, filtered view of persistent_env: every top-level name a
    Script/the Console has defined (a plain `x = 2`) MINUS the built-in
    API functions/values (add_block, sim, np, ...), which aren't user
    variables. This is what engine.variables.set_active_variables() is
    registered with -- i.e. what a block parameter binds to by name (see
    var()/gui/widgets/param_value_editor.py's "just type the name"
    binding) and what the Global Variables dock displays.

    There used to be a second, separate namespace here called `ws` (a
    private dict a variable had to be explicitly written into via
    `ws[...] = ...` to be "declared"). It's gone: every script variable
    was already a global (persistent_env is exec()'d against directly as
    both globals and locals -- see the module docstring), so `ws` was
    pure duplication with its own footgun (writing `ws['x'] = 5` and a
    bare `x = 5` created two different names, and only one of them showed
    up depending which store you asked). This view just reads/writes
    persistent_env directly -- write it via `[name] = value` and it's the
    exact same as a plain top-level assignment, immediately visible under
    its own name to the next Script/Console command."""

    def __init__(self, script_manager):
        self._sm = script_manager

    def _api_keys(self):
        return set(self._sm._build_api(lambda *args: None).keys()) | {"__builtins__"}

    def __getitem__(self, name):
        env = self._sm.persistent_env
        if name in env and name not in self._api_keys():
            return env[name]
        raise KeyError(name)

    def __setitem__(self, name, value):
        self._sm.persistent_env[name] = value

    def __delitem__(self, name):
        del self._sm.persistent_env[name]

    def __iter__(self):
        api_keys = self._api_keys()
        for name in self._sm.persistent_env:
            if name not in api_keys:
                yield name

    def __len__(self):
        return sum(1 for _ in self)

    def copy(self):
        """A plain dict snapshot -- MutableMapping doesn't provide copy()
        itself, and scripts reasonably expect this to work like it would
        on any other dict."""
        return dict(self.items())

    def __repr__(self):
        return repr(dict(self.items()))


class ScriptManager:
    """Manages user scripts and provides execution context."""

    def __init__(self, main_window):
        self.main_window = main_window
        # The one shared execution environment (see module docstring) --
        # exec()'d against directly (as both globals and locals) by every
        # Script run and every Console command, so top-level names a
        # script/command defines persist across all of them.
        self.persistent_env = {}
        # THE global variable store -- a filtered view of persistent_env
        # (see _GlobalVariablesView above) that's what block parameters
        # bind to by name (engine/variables.py, and
        # gui/widgets/param_value_editor.py's "just type the name" binding
        # on every block's own parameter editor). Reads/writes straight
        # through to self.persistent_env, so any later mutation (a script/
        # Console defining `Kp = 2.5`, or clear_globals() below) is picked
        # up automatically; nothing needs to re-register. Kept as an
        # attribute (not just registered and forgotten) so sim() below can
        # pass THIS manager's own view explicitly rather than trusting
        # whatever happens to be globally registered at call time. engine/
        # has no import of gui/ this way -- gui/ hands the engine layer
        # its store, rather than the engine reaching up into
        # gui/managers/script_manager.py.
        self.global_variables = _GlobalVariablesView(self)
        set_active_variables(self.global_variables)

    def clear_globals(self):
        """Reset the shared execution environment (see class/module
        docstring): forget every variable, import, or function a Script
        run or the Console has defined this session -- that IS
        clearing every global variable, since persistent_env is the only
        place they live (see _GlobalVariablesView). The API functions
        (add_block, sim, np, ...) are NOT lost: _build_api() re-adds them
        to persistent_env before the very next run/command, same as it
        already does on every call."""
        self.persistent_env.clear()

    def open_script(self, file_path):
        """Open a Script from User Space as its own tab in the main
        window's central area (not a separate dialog) -- bound to its
        file so Save writes straight back to it. Multiple Scripts can be
        open at once, each in its own tab; re-opening one that's already
        open just switches to its existing tab (open_script_tab() only
        calls make_widget(), and so only reads the file, when a new tab
        actually needs to be built). Connected to
        UserSpaceWidget.script_open_requested (double-click / New Script)."""
        from ..dialogs import ScriptEditorWidget

        def make_widget():
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return ScriptEditorWidget(self.main_window, self, file_path, content)

        try:
            self.main_window.open_script_tab(file_path, make_widget)
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to open script: {e}")

    def _build_api(self, custom_print, should_cancel=None, on_progress=None):
        """Build the dict of functions/values exposed to script code and
        the Console -- shared by execute_script() and execute_command() so
        both run against identical capabilities. `custom_print` is the
        caller's own output sink (Script output pane vs. Console log), so
        every function below routes its status/error/warning lines through
        whichever one is currently running.

        `should_cancel`/`on_progress` are only meaningful for a Script run
        via the toolbar's Run/Stop button (see ToolbarManager.run_script())
        -- sim() threads them straight through to SimulationEngine.run(),
        so a long sim() call inside a running Script can report progress
        on the same inline bar a directly-run simulation does, and can be
        interrupted by clicking Stop. Both default to None (no-op) for
        execute_command() and any other caller that doesn't pass them."""

        def _scene_manager():
            """The active diagram's SceneManager, or None (with a printed
            error) if no diagram tab is open yet -- the app can start with
            zero (see MainWindow), so every function below must check this
            instead of dereferencing main_window.scene_manager directly and
            crashing with an AttributeError before the script even runs."""
            sm = self.main_window.scene_manager
            if sm is None:
                custom_print("❌ Error: No diagram is open. Use File -> New (or Open) first.")
            return sm

        def _diagram_name(doc):
            """A diagram tab's script-facing name: its file's basename if
            saved, else its 'Untitled'/'Untitled N' tab title -- the same
            thing shown on the tab itself."""
            if doc.scene_manager.current_file_path:
                return os.path.basename(doc.scene_manager.current_file_path)
            return doc.blank_title or "Untitled"

        def open_diagram(file_path):
            """Open `file_path` in its own Diagram tab (or switch to it if
            already open) and make it the active target for every command
            below -- same effect as double-clicking it in User Space, or
            File -> Open..., but scriptable. A bare filename (no directory)
            is resolved against the current Project Folder if one is open.
            Returns the diagram's name (see list_diagrams()) on success, or
            None on failure."""
            mw = self.main_window
            if not hasattr(mw, "open_diagram_tab"):
                custom_print("❌ Error: No main window to open a diagram in.")
                return None

            path = file_path
            if not os.path.isabs(path) and not os.path.dirname(path):
                project_manager = getattr(mw, "project_manager", None)
                if project_manager is not None and project_manager.project_root:
                    path = os.path.join(project_manager.project_root, path)

            if not os.path.isfile(path):
                custom_print(f"❌ Error: File not found: {path}")
                return None

            mw.open_diagram_tab(path)
            name = os.path.basename(path)
            custom_print(f"✓ Opened '{name}' -- now the active diagram for following commands.")
            return name

        def new_diagram():
            """Create a fresh, empty diagram in its own new tab -- same as
            File -> New, but scriptable, and the only way to start one
            from scratch: open_diagram() needs a file that already exists
            on disk, this doesn't. Makes it the active target for every
            command below, same as open_diagram(). Returns the new
            diagram's name (its 'Untitled'/'Untitled N' tab title -- see
            list_diagrams()), or None on failure."""
            mw = self.main_window
            if not hasattr(mw, "open_diagram_tab"):
                custom_print("❌ Error: No main window to create a diagram in.")
                return None

            scene_manager = mw.open_diagram_tab()
            doc = mw._diagram_for_scene_manager(scene_manager)
            name = _diagram_name(doc) if doc is not None else None
            custom_print(f"✓ Created new diagram '{name}' -- now the active diagram for following commands.")
            return name

        def select_diagram(name):
            """Switch the active diagram to an already-open tab, matched by
            name (see list_diagrams()) -- for jumping between diagrams
            already open this session without touching disk. Every command
            below then targets whichever one this selects. Returns
            True/False."""
            mw = self.main_window
            for doc in getattr(mw, "_diagrams", []):
                if _diagram_name(doc) == name:
                    mw.central_tabs.setCurrentWidget(doc.view)
                    custom_print(f"✓ Selected '{name}' as the active diagram.")
                    return True
            custom_print(f"⚠ Warning: No open diagram named '{name}'. See list_diagrams().")
            return False

        def current_diagram():
            """The active diagram's name -- what add_block(), sim(), etc.
            currently target. None (with a printed error) if no diagram is
            open."""
            sm = _scene_manager()
            if sm is None:
                return None
            doc = self.main_window._diagram_for_scene_manager(sm)
            return _diagram_name(doc) if doc is not None else None

        def list_diagrams():
            """Names of every open diagram tab, in tab order -- see
            select_diagram()/current_diagram()."""
            return [_diagram_name(doc) for doc in getattr(self.main_window, "_diagrams", [])]

        def save_diagram(file_path=None):
            """Save the active diagram (see current_diagram()) to
            file_path, or -- if omitted -- to whatever file it's already
            bound to (like the toolbar's Save). Unlike the GUI's Save As,
            this never opens a file picker; pass an explicit file_path for
            a scripted "save as". A bare filename (no directory) is
            resolved against the current Project Folder, same as
            open_diagram(). Returns the path saved to, or None on failure."""
            sm = _scene_manager()
            if sm is None:
                return None

            if file_path is not None:
                path = file_path
                if not os.path.isabs(path) and not os.path.dirname(path):
                    project_manager = getattr(self.main_window, "project_manager", None)
                    if project_manager is not None and project_manager.project_root:
                        path = os.path.join(project_manager.project_root, path)
                sm.current_file_path = path
            elif not sm.current_file_path:
                custom_print(
                    "❌ Error: This diagram has no file yet -- pass a "
                    "file_path, e.g. save_diagram('my_diagram.json')."
                )
                return None

            sm.save_graph()
            custom_print(f"✓ Saved '{os.path.basename(sm.current_file_path)}'")
            return sm.current_file_path

        def _find_ui_block(block_name):
            sm = _scene_manager()
            if sm is None:
                return None
            for ui_block in sm.blocks_ui:
                if _resolve_name(ui_block.model) == block_name:
                    return ui_block
            return None

        def set_param(block_name, param_name, value):
            """
            Set a parameter on a block, at whatever level is currently
            active (Top Level, or inside a SubGraph after
            enter_subgraph()). Only an EXISTING parameter can be set --
            this respects each block's own defined interface rather than
            letting a script inject arbitrary new keys.
            """
            sm = _scene_manager()
            if sm is None:
                return

            found_count = 0

            for ui_block in sm.blocks_ui:
                if _resolve_name(ui_block.model) == block_name:
                    # Only allow modifying an EXISTING parameter -- this
                    # respects each block's own defined interface rather
                    # than letting a script inject arbitrary new keys.
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
                    # Reassigning the whole dict (not just mutating one key)
                    # re-triggers per-block __setattr__ hooks that several
                    # blocks (Gain, Constant, Delay, SineWave, Integrator,
                    # ...) rely on to refresh a cached/parsed copy of their
                    # params -- without this, a scripted set_param silently
                    # had no effect on the actual simulation even though
                    # get_param/the GUI label showed the new value.
                    ui_block.model.params = ui_block.model.params

                    # Blocks with a dynamic port count (Scope, Mux, Demux,
                    # PythonFunction, BusCreator/Selector, SubGraph) only
                    # rebuild their actual inputs/outputs dict -- what
                    # add_line() etc. see -- when refresh_io_ports() runs;
                    # setting e.g. NumInputs via set_param alone left the
                    # model saying "2 inputs" while its real ports (and the
                    # matching UIPorts add_line() needs) stayed at 1. Same
                    # two-step refresh scene_manager.py already does after
                    # paste/duplicate.
                    if hasattr(ui_block.model, "refresh_io_ports"):
                        ui_block.model.refresh_io_ports()
                        ui_block.refresh_ports()

                    # Trigger visual update
                    if hasattr(ui_block.model, "_update_label"):
                        ui_block.model._update_label()
                    ui_block.update()

                    found_count += 1

            if found_count > 0:
                custom_print(f"✓ Set {block_name}.{param_name} = {value}")
            else:
                custom_print(f"⚠ Warning: Block '{block_name}' not found at the current level.")

        def get_param(block_name, param_name):
            """Read a parameter's current value, at whatever level is
            currently active. Read counterpart to set_param."""
            sm = _scene_manager()
            if sm is None:
                return None

            for ui_block in sm.blocks_ui:
                if _resolve_name(ui_block.model) == block_name:
                    if param_name not in ui_block.model.params:
                        custom_print(f"❌ Error: Parameter '{param_name}' not defined on '{block_name}'.")
                        return None
                    return ui_block.model.params[param_name]

            custom_print(f"⚠ Warning: Block '{block_name}' not found at the current level.")
            return None

        def add_block(block_type, name=None, position=None):
            """Add a new block of type `block_type` (a BLOCK_REGISTRY key --
            see get_block_types()) to whatever level is currently active
            (Top Level, or inside a SubGraph after enter_subgraph()).
            `name` becomes its BlockName (must be unused at that level); if
            omitted, an unused '<Type><N>' name is generated, e.g. 'Gain1'.
            `position` is an optional (x, y) tuple. Returns the block's
            final name, or None on failure."""
            sm = _scene_manager()
            if sm is None:
                return None

            if block_type not in BLOCK_REGISTRY:
                custom_print(f"❌ Error: Unknown block type '{block_type}'. See get_block_types().")
                return None

            existing_names = {_resolve_name(ui_block.model) for ui_block in sm.blocks_ui}
            if name is not None:
                if name in existing_names:
                    custom_print(f"❌ Error: A block named '{name}' already exists.")
                    return None
                final_name = name
            else:
                i = 1
                while f"{block_type}{i}" in existing_names:
                    i += 1
                final_name = f"{block_type}{i}"

            new_model = BLOCK_REGISTRY[block_type]()
            new_model.params["BlockName"] = final_name
            if hasattr(new_model, "_update_label"):
                new_model._update_label()

            from ..items import UIBlock
            ui_block = UIBlock(new_model)
            x, y = position if position else (100, 100)
            ui_block.setPos(x, y)
            sm.scene.addItem(ui_block)
            sm.blocks_ui.append(ui_block)
            sm.take_snapshot()

            custom_print(f"✓ Added {block_type} block '{final_name}'")
            return final_name

        def delete_block(block_name):
            """Delete a block by name (and any connections attached to it)
            from whatever level is currently active."""
            sm = _scene_manager()
            if sm is None:
                return False

            ui_block = _find_ui_block(block_name)
            if ui_block is None:
                custom_print(f"⚠ Warning: Block '{block_name}' not found at the current level.")
                return False

            sm.scene.delete_block(ui_block)
            custom_print(f"✓ Deleted block '{block_name}'")
            return True

        def add_line(src_block, dst_block, src_port=None, dst_port=None):
            """Connect src_block's output to dst_block's input, both by
            BlockName, at whatever level is currently active. src_port/
            dst_port name which port on each block; they can be omitted if
            that block has exactly one output/input respectively. An
            existing connection into dst_port is replaced, same as
            dragging a new wire onto it in the GUI."""
            sm = _scene_manager()
            if sm is None:
                return False

            src_ui = _find_ui_block(src_block)
            dst_ui = _find_ui_block(dst_block)
            if src_ui is None:
                custom_print(f"⚠ Warning: Block '{src_block}' not found at the current level.")
                return False
            if dst_ui is None:
                custom_print(f"⚠ Warning: Block '{dst_block}' not found at the current level.")
                return False

            if src_port is None:
                if len(src_ui.model.outputs) != 1:
                    custom_print(f"❌ Error: '{src_block}' has {len(src_ui.model.outputs)} outputs; specify src_port.")
                    return False
                src_port = next(iter(src_ui.model.outputs))
            if dst_port is None:
                if len(dst_ui.model.inputs) != 1:
                    custom_print(f"❌ Error: '{dst_block}' has {len(dst_ui.model.inputs)} inputs; specify dst_port.")
                    return False
                dst_port = next(iter(dst_ui.model.inputs))

            if src_port not in src_ui.model.outputs:
                custom_print(f"❌ Error: '{src_block}' has no output port '{src_port}'.")
                return False
            if dst_port not in dst_ui.model.inputs:
                custom_print(f"❌ Error: '{dst_block}' has no input port '{dst_port}'.")
                return False

            from ..items import UIConnection
            src_port_ui = src_ui.ports_ui[src_port]
            dst_port_ui = dst_ui.ports_ui[dst_port]

            conn = UIConnection(src_port_ui)
            sm.scene.addItem(conn)
            sm.scene.complete_connection(src_port_ui, dst_port_ui, conn)
            sm.take_snapshot()

            custom_print(f"✓ Connected {src_block}.{src_port} -> {dst_block}.{dst_port}")
            return True

        def delete_line(dst_block, dst_port=None):
            """Disconnect whatever feeds dst_block's input port (named by
            dst_port, or its sole input if omitted), at whatever level is
            currently active."""
            sm = _scene_manager()
            if sm is None:
                return False

            dst_ui = _find_ui_block(dst_block)
            if dst_ui is None:
                custom_print(f"⚠ Warning: Block '{dst_block}' not found at the current level.")
                return False

            if dst_port is None:
                if len(dst_ui.model.inputs) != 1:
                    custom_print(f"❌ Error: '{dst_block}' has {len(dst_ui.model.inputs)} inputs; specify dst_port.")
                    return False
                dst_port = next(iter(dst_ui.model.inputs))

            if dst_port not in dst_ui.model.inputs:
                custom_print(f"❌ Error: '{dst_block}' has no input port '{dst_port}'.")
                return False

            dst_port_ui = dst_ui.ports_ui[dst_port]
            conns = list(dst_port_ui.connections)
            if not conns:
                custom_print(f"⚠ Warning: '{dst_block}.{dst_port}' is not connected.")
                return False

            for conn in conns:
                sm.scene.delete_connection(conn)

            custom_print(f"✓ Disconnected {dst_block}.{dst_port}")
            return True

        def find_system(block_type=None, name_contains=None):
            """List block names at the current level, optionally filtered
            by class name (block_type, e.g. 'Gain') and/or a substring of
            their BlockName (name_contains)."""
            sm = _scene_manager()
            if sm is None:
                return []
            if sm.subsystem_stack:
                custom_print("⚠ Info: find_system searching current SUBSYSTEM (not top level).")

            results = []
            for ui_block in sm.blocks_ui:
                model = ui_block.model
                if block_type is not None and model.__class__.__name__ != block_type:
                    continue
                name = _resolve_name(model)
                if name_contains is not None and name_contains not in name:
                    continue
                results.append(name)
            return results

        def get_block_types():
            """All block type strings usable with add_block()/find_system()."""
            return sorted(BLOCK_REGISTRY.keys())

        def run_simulation():
            """Trigger the simulation run."""
            # Enforce First Simulation Layer rule (toolbar_manager.run_simulation()
            # itself already tolerates no diagram being open, so no need to
            # bail out here beyond just not crashing on the subsystem check).
            sm = self.main_window.scene_manager
            if sm is not None and sm.subsystem_stack:
                custom_print("⚠ Warning: You are running simulation from inside a Subsystem.")
                custom_print("   Standard usage is to run from the Top Level (First Layer).")
                custom_print("   Current simulation is local to this subsystem.")

            custom_print("▶ Starting simulation...")
            # We must run this on the main thread ideally, since it opens message boxes.
            # Since exec() assumes blocking, this is fine.
            self.main_window.toolbar_manager.run_simulation()
            custom_print("✓ Simulation finished.")

        def sim(duration=None, dt=None, solver=None):
            """Synchronous run: blocks until the simulation finishes and
            returns its data directly, e.g.:
                out = sim()
                t, y = out["scopes"]["Scope1"]["time"], out["scopes"]["Scope1"]["data"]
            Unlike run_simulation() (the GUI's async Run button, which just
            opens a results tab and returns nothing), this runs on the
            calling thread and hands back {"time": ndarray, "scopes":
            {name: {...}}}. duration/dt/solver default to the toolbar's
            current Simulation Settings if omitted.

            When called as part of a Script run via the toolbar's Run/Stop
            button, this reports progress on the same inline bar a
            directly-run simulation does, and clicking Stop cancels it
            (see should_cancel/on_progress above) -- called directly from
            the Console/get_signal() etc. instead, both are just None
            (no-op), same as before."""
            sm = _scene_manager()
            if sm is None:
                return None
            if sm.subsystem_stack:
                custom_print("⚠ Warning: Running simulation from inside a Subsystem.")

            if not sm.blocks_ui:
                custom_print("❌ Error: No blocks in the diagram.")
                return None

            tm = self.main_window.toolbar_manager
            block_models = [ui_block.model for ui_block in sm.blocks_ui]

            engine = SimulationEngine()
            engine.configure(
                block_models,
                duration if duration is not None else tm.sim_duration,
                dt if dt is not None else tm.sim_dt,
                solver=solver if solver is not None else tm.sim_solver,
                variables=self.global_variables,
            )

            is_valid, error_msg = engine.validate()
            if not is_valid:
                custom_print(f"❌ Validation Error: {error_msg}")
                return None

            for issue in engine.check_diagram():
                if issue.startswith("ERROR"):
                    custom_print(f"❌ {issue}")
                    return None
                custom_print(f"⚠ {issue}")

            custom_print("▶ Running simulation...")
            result = engine.run(progress_callback=on_progress, should_cancel=should_cancel)
            if result.cancelled:
                custom_print("⚠ Simulation cancelled.")
                return None
            if not result.success:
                custom_print(f"❌ Simulation Error: {result.error_message}")
                return None

            tm.last_result = result
            if hasattr(self.main_window, "open_simulation_tab"):
                self.main_window.open_simulation_tab(result)

            custom_print("✓ Simulation finished.")
            return {
                "time": result.time,
                "scopes": {name: dict(data) for name, data in result.scope_data.items()},
            }

        def get_signal(scope_name):
            """(time, data) arrays for a Scope block from the most recent
            sim()/run_simulation() run, without re-running. None + a
            warning if there's no run yet or that scope wasn't in it."""
            tm = self.main_window.toolbar_manager
            if tm.last_result is None or scope_name not in tm.last_result.scope_data:
                custom_print(f"⚠ Warning: No data for scope '{scope_name}'. Run sim() first.")
                return None
            data = tm.last_result.scope_data[scope_name]
            return data["time"], data["data"]

        def get_blocks():
            """
            Get a list of all block names at the current level (Top, or
            inside a SubGraph after enter_subgraph()).
            Returns:
                list: List of block name strings.
            """
            sm = _scene_manager()
            if sm is None:
                return []
            if sm.subsystem_stack:
                 custom_print("⚠ Info: get_blocks listing blocks in current SUBSYSTEM (not top level).")

            return [_resolve_name(ui_block.model) for ui_block in sm.blocks_ui]

        def get_block_info(block_name):
            """{param_name: variable_name} for every parameter on this
            block currently bound to a global variable (see var(), or
            just typing the variable's name into the block's own parameter
            editor) -- same rule for every block type, including SubGraph.
            Empty dict if none are bound; None (with a warning) if the
            block isn't found."""
            sm = _scene_manager()
            if sm is None:
                return None
            for ui_block in sm.blocks_ui:
                if _resolve_name(ui_block.model) == block_name:
                    return find_variable_refs(ui_block.model.params)

            custom_print(f"⚠ Warning: Block '{block_name}' not found.")
            return None

        def enter_subgraph(block_name):
            """Step inside a SubGraph block (by name, at the current
            level) -- like double-clicking it in the canvas. Every
            following command (add_block, set_param, add_line, ...) then
            acts on ITS internal diagram, letting a script build a
            SubGraph's contents the same way it builds the top-level one.
            Pair with exit_subgraph() (one level) or go_to_top() (all the
            way out). Returns True/False."""
            sm = _scene_manager()
            if sm is None:
                return False
            ui_block = _find_ui_block(block_name)
            if ui_block is None:
                custom_print(f"⚠ Warning: Block '{block_name}' not found at the current level.")
                return False
            if ui_block.model.__class__.__name__ != "SubGraph":
                custom_print(f"❌ Error: '{block_name}' is a {ui_block.model.__class__.__name__}, not a SubGraph.")
                return False

            sm.enter_subsystem(ui_block)
            custom_print(f"✓ Entered SubGraph '{block_name}' -- following commands act inside it.")
            return True

        def exit_subgraph():
            """Step back out of the SubGraph currently entered (one
            level -- see enter_subgraph()), syncing its exposed ports from
            whatever InputPort/OutputPort blocks are inside it. Following
            commands act on the parent level again. Returns True/False."""
            sm = _scene_manager()
            if sm is None:
                return False
            if not sm.subsystem_stack:
                custom_print("⚠ Warning: Not inside a SubGraph.")
                return False

            sm.go_up_level()
            custom_print("✓ Exited SubGraph.")
            return True

        def go_to_top():
            """Navigate back out to the Top Level diagram, out of every
            nested SubGraph at once (see enter_subgraph()/exit_subgraph()
            for one level at a time)."""
            sm = _scene_manager()
            if sm is None:
                return
            sm.go_to_top_level()

        def blocked_input(prompt=""):
            """Replacement for the built-in input() -- same freeze as
            bare help(): it would block waiting to read a line from a
            terminal that doesn't exist here. Returns "" instead of
            hanging, after explaining why."""
            custom_print(
                "⚠ input() isn't available here -- there's no real "
                "terminal for it to read a line from; calling it would "
                "freeze the app the same way help() used to. Use a block "
                "param, a global variable, or a GUI dialog instead."
            )
            return ""

        def blocked_exit(*args):
            """Replacement for the built-in exit()/quit() -- the real ones
            raise SystemExit, which isn't caught by execute_script()/
            execute_command()'s `except Exception` and would tear down the
            whole app, not just this one Script/command."""
            custom_print(
                "⚠ exit()/quit() isn't available here -- it would close "
                "the whole app, not just this Script. Use View -> Toggle "
                "Console (Ctrl+`) to hide the Console instead."
            )

        return {
            "open_diagram": open_diagram,
            "new_diagram": new_diagram,
            "select_diagram": select_diagram,
            "current_diagram": current_diagram,
            "list_diagrams": list_diagrams,
            "save_diagram": save_diagram,
            "enter_subgraph": enter_subgraph,
            "exit_subgraph": exit_subgraph,
            "set_param": set_param,
            "get_param": get_param,
            "add_block": add_block,
            "delete_block": delete_block,
            "add_line": add_line,
            "delete_line": delete_line,
            "find_system": find_system,
            "get_block_types": get_block_types,
            "run_simulation": run_simulation,
            "sim": sim,
            "get_signal": get_signal,
            "print": custom_print,
            "go_to_top": go_to_top,
            "get_blocks": get_blocks,
            "get_block_info": get_block_info,
            "np": np,
            "var": make_variable_ref,
            "help": _HelpInvoker(self.main_window),
            "input": blocked_input,
            "exit": blocked_exit,
            "quit": blocked_exit,
        }

    def execute_script(self, script_content, should_cancel=None, on_progress=None):
        """
        Execute the provided script content against the shared persistent
        environment (see class/module docstring).

        should_cancel/on_progress: threaded through to sim() (see
        _build_api()) so a Script run via the toolbar's Run/Stop button can
        report progress and be interrupted mid-sim(); both are None
        (no-op) for a plain direct call, e.g. from tests.

        Returns:
            str: Output of the script (print statements)
        """
        output_lines = []

        def custom_print(*args):
            output_lines.append(" ".join(str(a) for a in args))

        # Re-bind the API functions/values every run (main_window's active
        # diagram may have changed since the last run) without touching any
        # variable the user's own code has already defined in persistent_env.
        self.persistent_env.update(self._build_api(custom_print, should_cancel=should_cancel, on_progress=on_progress))

        try:
            # A single dict as both globals and locals (rather than a fresh,
            # empty globals + throwaway locals) so a function the script
            # defines can see other top-level names when it's later called
            # -- exec() with separate globals/locals resolves a function's
            # free variables against ITS globals only, which would silently
            # break e.g. one script-defined function calling another.
            exec(script_content, self.persistent_env)
            return "\n".join(output_lines)
        except Exception as e:
            return "\n".join(output_lines) + f"\n\n❌ Script Error:\n{str(e)}"

    def execute_command(self, command):
        """Execute one line/statement in the SAME persistent environment as
        execute_script(), for the interactive Console. Unlike
        execute_script(), a bare trailing expression's value is echoed back
        (like typing it at a normal Python prompt), not just whatever
        print() wrote -- e.g. typing `2 + 2` shows `4`.

        Returns:
            str: Output for this one command (print() lines, the echoed
            expression value if any, and/or an error message).
        """
        output_lines = []

        def custom_print(*args):
            output_lines.append(" ".join(str(a) for a in args))

        def _echo(value):
            if value is not None:
                output_lines.append(repr(value))

        self.persistent_env.update(self._build_api(custom_print))

        try:
            # 'single' mode is what a real interactive interpreter compiles
            # each prompt line with: a bare expression statement becomes an
            # implicit "print its repr via sys.displayhook" instead of being
            # silently discarded, the way plain exec() would.
            compiled = compile(command, "<console>", "single")
        except SyntaxError as e:
            return f"SyntaxError: {e}"

        old_displayhook = sys.displayhook
        sys.displayhook = _echo
        try:
            exec(compiled, self.persistent_env)
        except Exception as e:
            output_lines.append(f"{type(e).__name__}: {e}")
        finally:
            sys.displayhook = old_displayhook

        return "\n".join(output_lines)
