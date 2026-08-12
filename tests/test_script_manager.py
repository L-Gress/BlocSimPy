"""Tests for gui/managers/script_manager.py's scripting API
(add_block/delete_block, add_line/delete_line, set_param/get_param,
find_system, sim(), get_signal(), clear_globals()) and the Global
Variables dock (gui/widgets/globals_widget.py) that inspects that same
environment.

Lives outside the Qt-free part of the suite (see test_serialization.py's
module docstring) because add_block/add_line etc. build real
UIBlock/UIConnection/NodeScene objects, same as
test_gui_subgraph_navigation.py -- a QApplication is required, offscreen
platform keeps it runnable headlessly/in CI.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Qt

from gui.scene import NodeScene
from gui.managers.scene_manager import SceneManager
from gui.managers.script_manager import ScriptManager
from gui.widgets import ConsoleWidget, GlobalsWidget

_app = QApplication.instance() or QApplication([])


class _FakeToolbarManager:
    """Minimal stand-in for ToolbarManager -- sim() only reads the
    Simulation Settings fields and writes last_result."""

    def __init__(self):
        self.sim_duration = 1.0
        self.sim_dt = 0.1
        self.sim_solver = "euler"
        self.last_result = None


class _FakeMainWindow(QObject):
    """Minimal stand-in for MainWindow -- ScriptManager/SceneManager only
    need a QObject parent, a `.scene_manager`, and (for sim()) a
    `.toolbar_manager`. No `open_simulation_tab` is defined, matching how
    ScriptManager already guards that with hasattr()."""
    pass


def _build_manager():
    mw = _FakeMainWindow()
    mw.scene = NodeScene(mw)
    mw.scene_manager = SceneManager(mw, mw.scene)
    mw.toolbar_manager = _FakeToolbarManager()
    return ScriptManager(mw), mw


class TestAddDeleteBlock(unittest.TestCase):
    def test_add_block_auto_names_uniquely(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "a = add_block('Gain')\n"
            "b = add_block('Gain')\n"
            "print(a, b)\n"
        )
        self.assertIn("Gain1 Gain2", out)
        self.assertEqual(len(mw.scene_manager.blocks_ui), 2)

    def test_add_block_explicit_name_and_position(self):
        sm, mw = _build_manager()
        sm.execute_script("add_block('Constant', name='K', position=(50, 60))")
        self.assertEqual(len(mw.scene_manager.blocks_ui), 1)
        ui_block = mw.scene_manager.blocks_ui[0]
        self.assertEqual(ui_block.model.params.get("BlockName"), "K")
        self.assertEqual((ui_block.pos().x(), ui_block.pos().y()), (50, 60))

    def test_add_block_duplicate_name_fails(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('Constant', name='K')\n"
            "r = add_block('Constant', name='K')\n"
            "print('result:', r)\n"
        )
        self.assertIn("already exists", out)
        self.assertIn("result: None", out)
        self.assertEqual(len(mw.scene_manager.blocks_ui), 1)

    def test_add_block_unknown_type_fails(self):
        sm, mw = _build_manager()
        out = sm.execute_script("r = add_block('NotARealBlock')\nprint('result:', r)")
        self.assertIn("Unknown block type", out)
        self.assertIn("result: None", out)
        self.assertEqual(mw.scene_manager.blocks_ui, [])

    def test_delete_block_removes_it(self):
        sm, mw = _build_manager()
        sm.execute_script("add_block('Gain', name='G')")
        self.assertEqual(len(mw.scene_manager.blocks_ui), 1)
        out = sm.execute_script("delete_block('G')")
        self.assertIn("Deleted block 'G'", out)
        self.assertEqual(mw.scene_manager.blocks_ui, [])

    def test_delete_block_missing_warns(self):
        sm, mw = _build_manager()
        out = sm.execute_script("delete_block('Nope')")
        self.assertIn("not found", out)


class TestWiring(unittest.TestCase):
    def test_add_line_connects_single_ports_by_inference(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('Constant', name='C')\n"
            "add_block('Gain', name='G')\n"
            "add_line('C', 'G')\n"
        )
        self.assertIn("Connected C.out -> G.in", out)

        c_ui = next(b for b in mw.scene_manager.blocks_ui if b.model.params.get("BlockName") == "C")
        g_ui = next(b for b in mw.scene_manager.blocks_ui if b.model.params.get("BlockName") == "G")
        self.assertIs(g_ui.model.inputs["in"].connected_port, c_ui.model.outputs["out"])

    def test_add_line_ambiguous_port_requires_explicit_name(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('Constant', name='C')\n"
            "add_block('Scope', name='S')\n"  # Scope defaults to 1 input, so this is unambiguous...
        )
        # ...so make it ambiguous by growing to 2 inputs first.
        s_ui = next(b for b in mw.scene_manager.blocks_ui if b.model.params.get("BlockName") == "S")
        s_ui.model.params["NumInputs"] = 2
        s_ui.model.refresh_io_ports()

        out = sm.execute_script("r = add_line('C', 'S')\nprint('result:', r)")
        self.assertIn("specify dst_port", out)
        self.assertIn("result: False", out)

    def test_delete_line_disconnects(self):
        sm, mw = _build_manager()
        sm.execute_script(
            "add_block('Constant', name='C')\n"
            "add_block('Gain', name='G')\n"
            "add_line('C', 'G')\n"
        )
        out = sm.execute_script("delete_line('G')")
        self.assertIn("Disconnected G.in", out)

        g_ui = next(b for b in mw.scene_manager.blocks_ui if b.model.params.get("BlockName") == "G")
        self.assertIsNone(g_ui.model.inputs["in"].connected_port)


class TestParamsAndIntrospection(unittest.TestCase):
    def test_set_param_then_get_param_round_trip(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('Gain', name='G')\n"
            "set_param('G', 'Gain', 3.5)\n"
            "print('read:', get_param('G', 'Gain'))\n"
        )
        self.assertIn("read: 3.5", out)

    def test_get_param_unknown_param_fails(self):
        sm, mw = _build_manager()
        sm.execute_script("add_block('Gain', name='G')")
        out = sm.execute_script("r = get_param('G', 'NotAParam')\nprint('result:', r)")
        self.assertIn("not defined", out)
        self.assertIn("result: None", out)

    def test_set_param_num_inputs_refreshes_ports_for_add_line(self):
        # Regression guard: set_param('NumInputs', ...) on a dynamic-port
        # block (Scope, Mux, Demux, ...) used to only update the params
        # dict -- the block's actual .inputs/ports_ui never grew a second
        # port, so a following add_line(..., dst_port='in2') failed with
        # "no input port 'in2'" even though get_param reported NumInputs=2.
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('Constant', name='A')\n"
            "add_block('Constant', name='B')\n"
            "add_block('Scope', name='S')\n"
            "set_param('S', 'NumInputs', 2)\n"
            "r1 = add_line('A', 'S', dst_port='in1')\n"
            "r2 = add_line('B', 'S', dst_port='in2')\n"
            "print('results:', r1, r2)\n"
        )
        self.assertIn("results: True True", out)

        s_ui = next(b for b in mw.scene_manager.blocks_ui if b.model.params.get("BlockName") == "S")
        self.assertIn("in2", s_ui.model.inputs)
        self.assertIn("in2", s_ui.ports_ui)

    def test_find_system_filters_by_type_and_name(self):
        sm, mw = _build_manager()
        sm.execute_script(
            "add_block('Gain', name='G1')\n"
            "add_block('Gain', name='G2')\n"
            "add_block('Constant', name='C1')\n"
        )
        out = sm.execute_script("print(sorted(find_system(block_type='Gain')))")
        self.assertIn("['G1', 'G2']", out)

        out = sm.execute_script("print(find_system(name_contains='C1'))")
        self.assertIn("['C1']", out)

    def test_get_block_types_includes_known_blocks(self):
        sm, mw = _build_manager()
        out = sm.execute_script("print('Gain' in get_block_types(), 'Constant' in get_block_types())")
        self.assertIn("True True", out)

    def test_get_blocks_uses_class_default_name_not_unnamed(self):
        # Regression guard: a block added without an explicit name used to
        # be unaddressable ("Unnamed" in get_blocks(), no fallback at all in
        # set_param) -- both now fall back to the same class-default name.
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('Gain')\n"
            "print(get_blocks())\n"
        )
        self.assertIn("Gain1", out)
        self.assertNotIn("Unnamed", out)


class TestSubgraphAuthoring(unittest.TestCase):
    """enter_subgraph()/exit_subgraph() let a script build a SubGraph's
    internals the same way it builds the top-level diagram. Structural
    commands (add_block, set_param, add_line, ...) now act on whatever
    level is currently active -- the old hard "Top Level only" block was
    deliberately removed since it made scripting a SubGraph's contents
    impossible."""

    def test_structural_commands_now_work_inside_a_subsystem(self):
        sm, mw = _build_manager()
        mw.scene_manager.subsystem_stack.append({"data": {}, "subsystem_model": None, "initial_port_names": {}})

        out = sm.execute_script(
            "add_block('Gain', name='G')\n"
            "set_param('G', 'Gain', 2.0)\n"
            "add_block('Constant', name='C')\n"
            "print('add_line:', add_line('C', 'G'))\n"
            "print('gain:', get_param('G', 'Gain'))\n"
        )
        self.assertIn("add_line: True", out)
        self.assertIn("gain: 2.0", out)
        self.assertEqual(len(mw.scene_manager.blocks_ui), 2)

    def test_enter_and_exit_subgraph_builds_working_interface(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('SubGraph', name='Sub')\n"
            "print('entered:', enter_subgraph('Sub'))\n"
            "add_block('InputPort', name='InPort', position=(0, 0))\n"
            "set_param('InPort', 'PortName', 'X')\n"
            "add_block('OutputPort', name='OutPort', position=(200, 0))\n"
            "set_param('OutPort', 'PortName', 'Y')\n"
            "add_block('Gain', name='InnerGain', position=(100, 0))\n"
            "set_param('InnerGain', 'Gain', 3.0)\n"
            "add_line('InPort', 'InnerGain')\n"
            "add_line('InnerGain', 'OutPort')\n"
            "print('inner blocks:', sorted(get_blocks()))\n"
            "print('exited:', exit_subgraph())\n"
            "print('top blocks:', get_blocks())\n"
        )
        self.assertIn("entered: True", out)
        self.assertIn("exited: True", out)
        self.assertIn("inner blocks: ['InPort', 'InnerGain', 'OutPort']", out)
        self.assertIn("top blocks: ['Sub']", out)

        sub_ui = mw.scene_manager.blocks_ui[0]
        self.assertEqual(sub_ui.model.__class__.__name__, "SubGraph")
        self.assertIn("X", sub_ui.model.inputs)
        self.assertIn("Y", sub_ui.model.outputs)

    def test_top_level_wiring_can_use_the_new_subgraph_ports(self):
        sm, mw = _build_manager()
        sm.execute_script(
            "add_block('SubGraph', name='Sub')\n"
            "enter_subgraph('Sub')\n"
            "add_block('InputPort', name='InPort')\n"
            "set_param('InPort', 'PortName', 'X')\n"
            "add_block('OutputPort', name='OutPort')\n"
            "set_param('OutPort', 'PortName', 'Y')\n"
            "add_line('InPort', 'OutPort')\n"
            "exit_subgraph()\n"
            "add_block('Constant', name='C')\n"
            "add_block('Scope', name='S')\n"
        )
        out = sm.execute_script(
            "print('to sub:', add_line('C', 'Sub', dst_port='X'))\n"
            "print('from sub:', add_line('Sub', 'S', src_port='Y'))\n"
        )
        self.assertIn("to sub: True", out)
        self.assertIn("from sub: True", out)

    def test_enter_subgraph_rejects_non_subgraph_block(self):
        sm, mw = _build_manager()
        sm.execute_script("add_block('Gain', name='G')")
        out = sm.execute_script("print('result:', enter_subgraph('G'))")
        self.assertIn("not a SubGraph", out)
        self.assertIn("result: False", out)

    def test_enter_subgraph_missing_block_warns(self):
        sm, mw = _build_manager()
        out = sm.execute_script("print('result:', enter_subgraph('Nope'))")
        self.assertIn("not found", out)
        self.assertIn("result: False", out)

    def test_exit_subgraph_when_not_inside_one_warns(self):
        sm, mw = _build_manager()
        out = sm.execute_script("print('result:', exit_subgraph())")
        self.assertIn("Not inside a SubGraph", out)
        self.assertIn("result: False", out)


class TestSimAndWorkspace(unittest.TestCase):
    def test_sim_runs_and_returns_scope_data(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('Constant', name='C', position=(0, 0))\n"
            "set_param('C', 'Value', 4.0)\n"
            "add_block('Gain', name='G', position=(100, 0))\n"
            "set_param('G', 'Gain', 2.0)\n"
            "add_block('Scope', name='S', position=(200, 0))\n"
            "add_line('C', 'G')\n"
            "add_line('G', 'S')\n"
            "out = sim()\n"
            "print('scopes:', sorted(out['scopes'].keys()))\n"
            "print('last:', out['scopes']['S']['data'][-1])\n"
        )
        self.assertIn("scopes: ['S']", out)
        self.assertIn("last: 8.0", out)
        self.assertIsNotNone(mw.toolbar_manager.last_result)

    def test_sim_with_no_blocks_fails_gracefully(self):
        sm, mw = _build_manager()
        out = sm.execute_script("r = sim()\nprint('result:', r)")
        self.assertIn("No blocks in the diagram", out)
        self.assertIn("result: None", out)

    def test_get_signal_after_sim(self):
        sm, mw = _build_manager()
        sm.execute_script(
            "add_block('Constant', name='C')\n"
            "set_param('C', 'Value', 7.0)\n"
            "add_block('Scope', name='S')\n"
            "add_line('C', 'S')\n"
            "sim()\n"
        )
        out = sm.execute_script(
            "t, y = get_signal('S')\n"
            "print('n:', len(t), 'last_y:', y[-1])\n"
        )
        self.assertIn("last_y: 7.0", out)

    def test_get_signal_before_any_sim_warns(self):
        sm, mw = _build_manager()
        out = sm.execute_script("r = get_signal('S')\nprint('result:', r)")
        self.assertIn("Run sim() first", out)
        self.assertIn("result: None", out)

class TestPersistentEnvironment(unittest.TestCase):
    """Regression coverage for the single shared execution environment:
    unlike the old per-run throwaway locals dict, every top-level name a
    script or console command defines now persists automatically (see
    ScriptManager.persistent_env) -- that's also what makes it a global
    variable (see _GlobalVariablesView); there's no separate store to
    explicitly declare one into."""

    def test_variable_isolated_between_managers(self):
        sm1, _ = _build_manager()
        sm2, _ = _build_manager()
        sm1.execute_script("x = 1")
        out = sm2.execute_script("print('x is', globals().get('x'))")
        self.assertIn("x is None", out)

    def test_plain_variable_persists_across_script_runs(self):
        sm, mw = _build_manager()
        sm.execute_script("x = 10")
        out = sm.execute_script("print('x is', x)")
        self.assertIn("x is 10", out)

    def test_function_defined_in_one_run_usable_in_next(self):
        sm, mw = _build_manager()
        sm.execute_script("def double(n):\n    return n * 2\n")
        out = sm.execute_script("print('doubled:', double(21))")
        self.assertIn("doubled: 42", out)

    def test_function_can_call_sibling_function_same_run(self):
        # Regression guard: the old exec(code, {}, local_scope) split gave
        # script-defined functions an EMPTY globals dict, so one script-level
        # function calling another would NameError -- a single dict used as
        # both globals and locals fixes that.
        sm, mw = _build_manager()
        out = sm.execute_script(
            "def helper():\n"
            "    return 5\n"
            "def caller():\n"
            "    return helper() + 1\n"
            "print('result:', caller())\n"
        )
        self.assertIn("result: 6", out)

    def test_console_and_script_share_the_same_environment(self):
        sm, mw = _build_manager()
        sm.execute_command("from_console = 'hi'")
        out = sm.execute_script("print('script sees:', from_console)")
        self.assertIn("script sees: hi", out)

        sm.execute_script("from_script = 'bye'")
        out = sm.execute_command("print('console sees:', from_script)")
        self.assertIn("console sees: bye", out)

    def test_environment_isolated_between_managers(self):
        sm1, _ = _build_manager()
        sm2, _ = _build_manager()
        sm1.execute_script("leaked = True")
        out = sm2.execute_script("print('leaked' in dir())")
        self.assertIn("False", out)


class TestExecuteCommand(unittest.TestCase):
    """The Console's REPL entry point -- unlike execute_script(), a bare
    expression's value is echoed back like a real interactive prompt."""

    def test_bare_expression_is_echoed(self):
        sm, mw = _build_manager()
        self.assertEqual(sm.execute_command("2 + 2"), "4")

    def test_assignment_produces_no_echo(self):
        sm, mw = _build_manager()
        self.assertEqual(sm.execute_command("x = 5"), "")

    def test_print_and_expression_both_appear(self):
        sm, mw = _build_manager()
        sm.execute_command("add_block('Gain', name='G')")
        out = sm.execute_command("get_param('G', 'Gain')")
        self.assertEqual(out, "1.0")

    def test_syntax_error_reported_without_crashing(self):
        sm, mw = _build_manager()
        out = sm.execute_command("def bad(:")
        self.assertIn("SyntaxError", out)

    def test_runtime_error_reported_without_crashing(self):
        sm, mw = _build_manager()
        out = sm.execute_command("1 / 0")
        self.assertIn("ZeroDivisionError", out)

    def test_no_diagram_open_reports_error_not_crash(self):
        # scene_manager is None until a diagram tab exists (see MainWindow) --
        # every API function must handle that instead of raising AttributeError.
        mw = _FakeMainWindow()
        mw.scene_manager = None
        mw.toolbar_manager = _FakeToolbarManager()
        sm = ScriptManager(mw)

        out = sm.execute_command("add_block('Gain')")
        self.assertIn("No diagram is open", out)

        out = sm.execute_command("go_to_top()")
        self.assertIn("No diagram is open", out)

        out = sm.execute_command("get_blocks()")
        self.assertIn("No diagram is open", out)
        self.assertTrue(out.endswith("[]"))


class TestConsoleWidget(unittest.TestCase):
    def test_submit_echoes_command_and_result(self):
        sm, mw = _build_manager()
        console = ConsoleWidget(mw, sm)

        console.input.setText("2 + 2")
        console._on_submit()

        text = console.output.toPlainText()
        self.assertIn(">>> 2 + 2", text)
        self.assertTrue(text.rstrip().endswith("4"))
        self.assertEqual(console.input.text(), "")

    def test_up_arrow_recalls_last_command(self):
        sm, mw = _build_manager()
        console = ConsoleWidget(mw, sm)

        console.input.setText("x = 1")
        console._on_submit()
        console.input.setText("y = 2")
        console._on_submit()

        self.assertEqual(console.input.text(), "")
        console.input._history_index = len(console.input._history)
        console.input.keyPressEvent(_make_key_event(Qt.Key_Up))
        self.assertEqual(console.input.text(), "y = 2")
        console.input.keyPressEvent(_make_key_event(Qt.Key_Up))
        self.assertEqual(console.input.text(), "x = 1")

    def test_down_arrow_returns_toward_draft(self):
        sm, mw = _build_manager()
        console = ConsoleWidget(mw, sm)

        console.input.setText("x = 1")
        console._on_submit()
        console.input.setText("unsent draft")
        console.input.keyPressEvent(_make_key_event(Qt.Key_Up))
        self.assertEqual(console.input.text(), "x = 1")
        console.input.keyPressEvent(_make_key_event(Qt.Key_Down))
        self.assertEqual(console.input.text(), "unsent draft")

    def test_blank_command_is_ignored(self):
        sm, mw = _build_manager()
        console = ConsoleWidget(mw, sm)
        before = console.output.toPlainText()

        console.input.setText("   ")
        console._on_submit()

        self.assertEqual(console.output.toPlainText(), before)
        self.assertEqual(len(console._history), 0)


def _make_key_event(key):
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import QEvent
    return QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier)


class TestScriptEditorWidget(unittest.TestCase):
    """ScriptEditorWidget itself no longer owns Run/Save buttons or a
    run_script() method (see tests/test_toolbar_run_stop.py for the
    unified toolbar Run/Stop/Save flow that replaced them) -- it's just
    the editor + save_script() (still used directly by confirm_discard())
    and no output pane of its own."""

    def test_script_editor_has_no_output_pane(self):
        sm, mw = _build_manager()
        from gui.dialogs.script_editor import ScriptEditorWidget
        widget = ScriptEditorWidget(mw, sm, "demo.py", "print('hi')\n")
        self.assertFalse(hasattr(widget, "output_console"))

    def test_save_script_writes_file_and_clears_modified_flag(self):
        import tempfile
        sm, mw = _build_manager()
        from gui.dialogs.script_editor import ScriptEditorWidget

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "demo.py")
            widget = ScriptEditorWidget(mw, sm, path, "print('hi')\n")
            widget.editor.setPlainText("print('updated')\n")
            # setPlainText() (unlike real keystrokes) doesn't itself flip
            # the modified flag -- set it explicitly to simulate an edit.
            widget.editor.document().setModified(True)

            widget.save_script()

            self.assertFalse(widget.editor.document().isModified())
            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "print('updated')\n")


class TestDiagramSwitching(unittest.TestCase):
    """open_diagram()/select_diagram()/current_diagram()/list_diagrams()
    let a script point every following command at a specific Diagram file
    (or hop between several already-open ones), instead of always acting
    on whatever tab happens to be focused.

    Exercised against a real MainWindow, unlike the rest of this file's
    _FakeMainWindow-based tests -- these drive MainWindow's actual multi-
    tab bookkeeping (._diagrams, .central_tabs, .open_diagram_tab()),
    which the lightweight fake doesn't model."""

    def _build_real_window(self):
        from gui.main_window import MainWindow
        w = MainWindow()
        return w, w.script_manager

    def _write_diagram(self, tmp_dir, name):
        import json
        path = os.path.join(tmp_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"blocks": [], "connections": [], "blocksimpy_kind": "diagram"}, f)
        return path

    def test_open_diagram_switches_active_target(self):
        import tempfile
        w, sm = self._build_real_window()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path_a = self._write_diagram(tmp_dir, "a.json")
            path_b = self._write_diagram(tmp_dir, "b.json")

            self.assertTrue(sm.execute_command(f"open_diagram({path_a!r})").endswith("'a.json'"))
            sm.execute_script("add_block('Gain', name='InA')")

            self.assertTrue(sm.execute_command(f"open_diagram({path_b!r})").endswith("'b.json'"))
            sm.execute_script("add_block('Gain', name='InB')")

            self.assertEqual(sm.execute_command("list_diagrams()"), "['a.json', 'b.json']")
            self.assertEqual(sm.execute_command("current_diagram()"), "'b.json'")

            self.assertTrue(sm.execute_command("select_diagram('a.json')").endswith("True"))
            self.assertIn("['InA']", sm.execute_script("print(get_blocks())"))

            self.assertTrue(sm.execute_command("select_diagram('b.json')").endswith("True"))
            self.assertIn("['InB']", sm.execute_script("print(get_blocks())"))

    def test_open_diagram_reuses_already_open_tab(self):
        import tempfile
        w, sm = self._build_real_window()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path_a = self._write_diagram(tmp_dir, "a.json")
            sm.execute_command(f"open_diagram({path_a!r})")
            sm.execute_script("add_block('Gain', name='InA')")

            # Re-opening the same path should switch to the SAME tab, not
            # reload a blank one over the block just added.
            sm.execute_command(f"open_diagram({path_a!r})")
            self.assertIn("['InA']", sm.execute_script("print(get_blocks())"))
            self.assertEqual(len(w._diagrams), 1)

    def test_open_diagram_resolves_bare_filename_against_project_root(self):
        import tempfile
        w, sm = self._build_real_window()
        with tempfile.TemporaryDirectory() as tmp_dir:
            self._write_diagram(tmp_dir, "a.json")
            w.project_manager.project_root = tmp_dir

            self.assertTrue(sm.execute_command("open_diagram('a.json')").endswith("'a.json'"))
            self.assertEqual(sm.execute_command("current_diagram()"), "'a.json'")

    def test_open_diagram_missing_file_reports_error(self):
        w, sm = self._build_real_window()
        out = sm.execute_command("open_diagram('/no/such/file.json')")
        self.assertIn("File not found", out)

    def test_select_diagram_unknown_name_reports_warning(self):
        w, sm = self._build_real_window()
        out = sm.execute_command("select_diagram('nope.json')")
        self.assertIn("No open diagram named", out)
        self.assertTrue(out.rstrip().endswith("False"))

    def test_current_diagram_none_when_nothing_open(self):
        w, sm = self._build_real_window()
        out = sm.execute_command("current_diagram()")
        self.assertIn("No diagram is open", out)

    def test_list_diagrams_includes_untitled_tabs(self):
        w, sm = self._build_real_window()
        w.open_diagram_tab()  # File -> New, unsaved "Untitled"
        self.assertEqual(sm.execute_command("list_diagrams()"), "['Untitled']")

    def test_new_diagram_creates_a_blank_diagram_with_no_file_needed(self):
        w, sm = self._build_real_window()
        self.assertEqual(len(w._diagrams), 0)

        out = sm.execute_command("new_diagram()")

        self.assertEqual(len(w._diagrams), 1)
        self.assertTrue(out.endswith("'Untitled'"))
        self.assertEqual(sm.execute_command("current_diagram()"), "'Untitled'")

    def test_new_diagram_becomes_the_active_target_for_add_block(self):
        w, sm = self._build_real_window()
        out = sm.execute_script("new_diagram()\nadd_block('Gain', name='G')\nprint(get_blocks())")
        self.assertIn("['G']", out)

    def test_new_diagram_multiple_calls_create_separate_tabs(self):
        w, sm = self._build_real_window()
        sm.execute_command("new_diagram()")
        sm.execute_command("new_diagram()")
        self.assertEqual(len(w._diagrams), 2)
        self.assertEqual(sm.execute_command("list_diagrams()"), "['Untitled', 'Untitled 2']")

    def test_save_diagram_writes_file_with_explicit_path(self):
        import tempfile
        w, sm = self._build_real_window()
        sm.execute_command("new_diagram()")
        sm.execute_script("add_block('Gain', name='G')")

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "out.json")
            out = sm.execute_command(f"save_diagram({path!r})")
            self.assertTrue(out.endswith(repr(path)))
            self.assertTrue(os.path.isfile(path))

    def test_save_diagram_resolves_bare_filename_against_project_root(self):
        import tempfile
        w, sm = self._build_real_window()
        with tempfile.TemporaryDirectory() as tmp_dir:
            w.project_manager.project_root = tmp_dir
            sm.execute_command("new_diagram()")

            sm.execute_command("save_diagram('out.json')")

            self.assertTrue(os.path.isfile(os.path.join(tmp_dir, "out.json")))

    def test_save_diagram_without_path_reuses_current_file(self):
        import tempfile
        w, sm = self._build_real_window()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "existing.json")
            sm.execute_command("new_diagram()")
            sm.execute_command(f"save_diagram({path!r})")

            # Change the diagram and save again with no path -- should
            # reuse the file it's now bound to, not require it again.
            sm.execute_script("add_block('Gain', name='G')")
            out = sm.execute_command("save_diagram()")
            self.assertTrue(out.endswith(repr(path)))

    def test_save_diagram_without_path_and_no_file_yet_reports_error(self):
        w, sm = self._build_real_window()
        sm.execute_command("new_diagram()")
        out = sm.execute_command("save_diagram()")
        self.assertIn("has no file yet", out)

    def test_save_diagram_with_no_diagram_open_reports_error(self):
        w, sm = self._build_real_window()
        out = sm.execute_command("save_diagram('x.json')")
        self.assertIn("No diagram is open", out)


class TestClearGlobals(unittest.TestCase):
    """ScriptManager.clear_globals() -- the Clear Global Variables command
    (Tools menu / Global Variables dock's Clear All button)."""

    def test_clear_globals_removes_user_defined_names(self):
        sm, mw = _build_manager()
        sm.execute_script("x = 10\ndef f():\n    return 1\n")
        self.assertIn("x", sm.persistent_env)

        sm.clear_globals()

        self.assertNotIn("x", sm.persistent_env)
        self.assertNotIn("f", sm.persistent_env)

    def test_api_functions_still_work_after_clear(self):
        # clear_globals() empties persistent_env entirely, including the
        # API functions -- but execute_script()/execute_command() always
        # re-inject them via _build_api() before running, so the very next
        # call must work exactly as if nothing had been cleared.
        sm, mw = _build_manager()
        sm.execute_script("x = 1")
        sm.clear_globals()

        out = sm.execute_script("add_block('Gain', name='G')\nprint(get_blocks())")
        self.assertIn("['G']", out)

    def test_persistent_env_object_identity_preserved(self):
        # clear_globals() clears persistent_env in place rather than
        # replacing it, so anything already holding a reference (e.g.
        # global_variables, which reads self._sm.persistent_env fresh
        # each time -- see _GlobalVariablesView) keeps working correctly.
        sm, mw = _build_manager()
        env_ref = sm.persistent_env
        sm.execute_script("a = 1")

        sm.clear_globals()

        self.assertIs(sm.persistent_env, env_ref)
        self.assertNotIn("a", env_ref)


class TestConsoleSafetyGuards(unittest.TestCase):
    """Regression coverage for a real bug report: typing help() in the
    Console froze the whole app -- the real built-in help() (bare, no
    args) opens an interactive prompt that reads from stdin, which never
    arrives in a GUI console, hanging forever. input() has the identical
    freeze; exit()/quit() raise SystemExit, which isn't caught by
    execute_script()/execute_command()'s `except Exception` and would
    tear down the whole app. All four are shadowed in _build_api() so the
    real, dangerous builtins are never reachable from a Script/the Console.

    help specifically opens BlocSimPy's own Help window (see
    _HelpInvoker) rather than trying to print docs -- both bare `help`
    and a call (`help()`/`help(x)`, argument ignored) do this."""

    def test_bare_help_opens_help_window(self):
        from unittest.mock import Mock
        sm, mw = _build_manager()
        mw.show_help = Mock()

        sm.execute_command("help")

        mw.show_help.assert_called_once()

    def test_help_call_opens_help_window(self):
        from unittest.mock import Mock
        sm, mw = _build_manager()
        mw.show_help = Mock()

        sm.execute_script("help()")

        mw.show_help.assert_called_once()

    def test_help_call_with_argument_still_opens_help_window(self):
        from unittest.mock import Mock
        sm, mw = _build_manager()
        mw.show_help = Mock()

        sm.execute_script("help(sim)")

        mw.show_help.assert_called_once()

    def test_help_does_not_raise_without_show_help_on_main_window(self):
        # _FakeMainWindow (unlike the real MainWindow) has no show_help --
        # _HelpInvoker must tolerate that instead of crashing (same
        # hasattr()-guard convention used throughout this file).
        sm, mw = _build_manager()
        out = sm.execute_script("help()")
        self.assertNotIn("Script Error", out)

    def test_input_returns_empty_string_instead_of_blocking(self):
        sm, mw = _build_manager()
        out = sm.execute_script("r = input()\nprint('got:', repr(r))")
        self.assertIn("got: ''", out)
        self.assertIn("isn't available here", out)

    def test_exit_does_not_raise_system_exit(self):
        sm, mw = _build_manager()
        # A real SystemExit would propagate straight through execute_script
        # (uncaught by `except Exception`) and crash the test process
        # itself -- this call returning normally IS the assertion.
        out = sm.execute_script("exit()\nprint('still running')")
        self.assertIn("still running", out)
        self.assertIn("isn't available here", out)

    def test_quit_does_not_raise_system_exit(self):
        sm, mw = _build_manager()
        out = sm.execute_script("quit()\nprint('still running')")
        self.assertIn("still running", out)


class TestVariableBinding(unittest.TestCase):
    """var()/set_param() binding a block param to a global variable (see
    engine/variables.py) -- replaces the old "$VarName"-prefixed-string
    convention, resolved uniformly at sim()/Run time."""

    def test_var_returns_reference_dict(self):
        sm, mw = _build_manager()
        out = sm.execute_command("var('K')")
        self.assertEqual(out, "{'__var__': 'K'}")

    def test_set_param_with_var_binds_and_sim_resolves_it(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('Constant', name='C', position=(0, 0))\n"
            "set_param('C', 'Value', 2.0)\n"
            "add_block('Gain', name='G', position=(100, 0))\n"
            "set_param('G', 'Gain', var('K'))\n"
            "add_block('Scope', name='S', position=(200, 0))\n"
            "add_line('C', 'G')\n"
            "add_line('G', 'S')\n"
            "K = 3.0\n"
            "result = sim()\n"
            "print('last:', result['scopes']['S']['data'][-1])\n"
        )
        self.assertIn("last: 6.0", out)

    def test_sim_blocked_when_bound_variable_undeclared(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('Constant', name='C')\n"
            "add_block('Gain', name='G')\n"
            "set_param('G', 'Gain', var('Missing'))\n"
            "add_block('Scope', name='S')\n"
            "add_line('C', 'G')\n"
            "add_line('G', 'S')\n"
            "r = sim()\n"
            "print('result:', r)\n"
        )
        self.assertIn("undeclared variable 'Missing'", out)
        self.assertIn("result: None", out)

    def test_get_block_info_reports_bound_params(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('Gain', name='G')\n"
            "set_param('G', 'Gain', var('K'))\n"
            "print(get_block_info('G'))\n"
        )
        self.assertIn("{'Gain': 'K'}", out)

    def test_get_block_info_empty_when_nothing_bound(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "add_block('Gain', name='G')\n"
            "print(get_block_info('G'))\n"
        )
        self.assertIn("{}", out)


class TestPlainVariableIsGlobal(unittest.TestCase):
    """A bare `x = 2` at the Console/in a Script IS a global variable --
    there's no separate store (the old `ws`) to explicitly declare one
    into. Covers var('x')/set_param(..., var('x')) resolving it, and
    _GlobalVariablesView (gui/managers/script_manager.py) exposing it."""

    def test_bare_assignment_resolves_in_sim(self):
        sm, mw = _build_manager()
        out = sm.execute_script(
            "x = 2\n"
            "add_block('Constant', name='C', position=(0, 0))\n"
            "set_param('C', 'Value', 3.0)\n"
            "add_block('Gain', name='G', position=(100, 0))\n"
            "set_param('G', 'Gain', var('x'))\n"
            "add_block('Scope', name='S', position=(200, 0))\n"
            "add_line('C', 'G')\n"
            "add_line('G', 'S')\n"
            "result = sim()\n"
            "print('last:', result['scopes']['S']['data'][-1])\n"
        )
        self.assertIn("last: 6.0", out)

    def test_bare_assignment_shows_up_in_global_variables_view(self):
        sm, mw = _build_manager()
        sm.execute_command("x = 2")
        self.assertIn("x", sm.global_variables)
        self.assertEqual(sm.global_variables["x"], 2)

    def test_api_functions_not_treated_as_declarable_variables(self):
        sm, mw = _build_manager()
        self.assertNotIn("add_block", sm.global_variables)
        self.assertNotIn("sim", sm.global_variables)
        self.assertNotIn("__builtins__", sm.global_variables)

    def test_writing_through_the_view_lands_in_persistent_env(self):
        # global_variables is just a filtered view over persistent_env now
        # (no second private dict) -- writing through it is the same as a
        # plain top-level assignment, immediately visible under its own
        # name to the next Script/Console command.
        sm, mw = _build_manager()
        sm.global_variables["NewVar"] = 0.0
        self.assertIn("NewVar", sm.persistent_env)
        out = sm.execute_script("print(NewVar)")
        self.assertIn("0.0", out)

    def test_clear_globals_removes_bare_assignment_from_view(self):
        sm, mw = _build_manager()
        sm.execute_command("x = 2")
        sm.clear_globals()
        self.assertNotIn("x", sm.global_variables)


class TestGlobalsWidget(unittest.TestCase):
    """Global Variables dock (gui/widgets/globals_widget.py) -- a
    read-only table over ScriptManager.persistent_env, filtered to
    exclude the built-in API functions/values."""

    def test_refresh_lists_user_defined_globals(self):
        sm, mw = _build_manager()
        sm.execute_script("x = 10\na = 'hi'")

        widget = GlobalsWidget(mw, sm)

        names = {widget.table.item(row, 0).text() for row in range(widget.table.rowCount())}
        self.assertIn("x", names)
        self.assertIn("a", names)
        # API functions/values are not user-defined globals -- they
        # shouldn't clutter this table.
        self.assertNotIn("add_block", names)
        self.assertNotIn("__builtins__", names)

    def test_refresh_reflects_new_state_after_more_script_runs(self):
        sm, mw = _build_manager()
        widget = GlobalsWidget(mw, sm)
        self.assertEqual(widget.table.rowCount(), 0)

        sm.execute_script("y = 5")
        widget.refresh()

        names = {widget.table.item(row, 0).text() for row in range(widget.table.rowCount())}
        self.assertIn("y", names)

    def test_clear_all_button_wipes_globals_and_refreshes(self):
        # No confirmation prompt -- Clear All is a single click, unlike the
        # Tools menu/toolbar's "Clear Global Variables..." action, which
        # still confirms (see ToolbarManager.clear_globals()).
        sm, mw = _build_manager()
        sm.execute_script("x = 10")
        widget = GlobalsWidget(mw, sm)
        self.assertGreater(widget.table.rowCount(), 0)

        widget._on_clear_clicked()

        self.assertNotIn("x", sm.persistent_env)
        self.assertEqual(widget.table.rowCount(), 0)

    def test_auto_refresh_picks_up_new_variable_without_manual_refresh(self):
        # What the QTimer calls on each tick -- no user-clicked Refresh
        # involved, matching the actual auto-refresh behavior while the
        # dock is visible.
        sm, mw = _build_manager()
        widget = GlobalsWidget(mw, sm)
        self.assertEqual(widget.table.rowCount(), 0)

        sm.execute_script("z = 42")
        widget._auto_refresh()

        names = {widget.table.item(row, 0).text() for row in range(widget.table.rowCount())}
        self.assertIn("z", names)

    def test_auto_refresh_skips_rebuild_when_nothing_changed(self):
        # Avoids resetting scroll/selection state on every tick when the
        # environment hasn't actually changed -- same table item object,
        # not just an equal-looking new one.
        sm, mw = _build_manager()
        sm.execute_script("x = 10")
        widget = GlobalsWidget(mw, sm)
        item_before = widget.table.item(0, 0)

        widget._auto_refresh()

        self.assertIs(widget.table.item(0, 0), item_before)

    def test_show_event_starts_timer_and_hide_event_stops_it(self):
        sm, mw = _build_manager()
        widget = GlobalsWidget(mw, sm)
        self.assertFalse(widget._timer.isActive())

        widget.show()
        self.assertTrue(widget._timer.isActive())

        widget.hide()
        self.assertFalse(widget._timer.isActive())


if __name__ == "__main__":
    unittest.main()
