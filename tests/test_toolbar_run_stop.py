"""Tests for the unified Run/Stop toggle and shared Save action
(gui/managers/toolbar_manager.py) that replaced the Script Editor's own
Run Script/Save buttons -- Run/Save now dispatch to whichever kind of tab
(Diagram vs Script) is focused (see MainWindow.active_script_widget()),
Run becomes a Stop button while something is running with an inline
progress indicator instead of a modal popup, and a Script run stays
non-blocking for the UI via cooperative event-loop pumping tied to any
sim() call it makes (see ToolbarManager.run_script()'s own docstring for
why that's not a background QThread the way a diagram simulation is).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def _build_window():
    from gui.main_window import MainWindow
    return MainWindow()


def _write_script(tmp_dir, name, content):
    path = os.path.join(tmp_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


class TestActiveScriptWidget(unittest.TestCase):
    def test_none_when_a_diagram_tab_is_active(self):
        w = _build_window()
        w.open_diagram_tab()
        self.assertIsNone(w.active_script_widget())

    def test_none_when_nothing_is_open(self):
        w = _build_window()
        self.assertIsNone(w.active_script_widget())

    def test_returns_widget_when_a_script_tab_is_active(self):
        w = _build_window()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_script(tmp_dir, "demo.py", "print('hi')\n")
            w.script_manager.open_script(path)
            self.assertIsNotNone(w.active_script_widget())
            self.assertEqual(w.active_script_widget().file_path, path)

    def test_none_again_after_switching_back_to_a_diagram(self):
        w = _build_window()
        w.open_diagram_tab()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_script(tmp_dir, "demo.py", "print('hi')\n")
            w.script_manager.open_script(path)
            self.assertIsNotNone(w.active_script_widget())

            w.show_diagram_editor()
            self.assertIsNone(w.active_script_widget())


class TestRunSaveEnabledWithOnlyAScriptOpen(unittest.TestCase):
    """Regression coverage: Run/Save are shared with Scripts now, so they
    must be usable even with zero diagram tabs open -- a Script only needs
    a Project Folder, not a Diagram (see MainWindow._update_run_save_enabled())."""

    def test_run_and_save_enabled_by_opening_a_script_with_no_diagram(self):
        w = _build_window()
        self.assertFalse(w.toolbar_manager.action_run.isEnabled())
        self.assertFalse(w.toolbar_manager.action_save.isEnabled())

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_script(tmp_dir, "demo.py", "print('hi')\n")
            w.script_manager.open_script(path)

        self.assertTrue(w.toolbar_manager.action_run.isEnabled())
        self.assertTrue(w.toolbar_manager.action_save.isEnabled())

    def test_closing_last_diagram_keeps_run_save_enabled_if_script_open(self):
        w = _build_window()
        w.open_diagram_tab()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_script(tmp_dir, "demo.py", "print('hi')\n")
            w.script_manager.open_script(path)

            index = w.central_tabs.indexOf(w._diagrams[0].view)
            w._on_tab_close_requested(index)

        self.assertEqual(len(w._diagrams), 0)
        self.assertTrue(w.toolbar_manager.action_run.isEnabled())
        self.assertTrue(w.toolbar_manager.action_save.isEnabled())

    def test_closing_last_script_disables_run_save_with_no_diagram(self):
        w = _build_window()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_script(tmp_dir, "demo.py", "print('hi')\n")
            w.script_manager.open_script(path)
            widget = w.active_script_widget()

            index = w.central_tabs.indexOf(widget)
            w._on_tab_close_requested(index)

        self.assertFalse(w.toolbar_manager.action_run.isEnabled())
        self.assertFalse(w.toolbar_manager.action_save.isEnabled())


class TestSaveDispatch(unittest.TestCase):
    def test_save_action_saves_the_active_script_when_focused(self):
        w = _build_window()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_script(tmp_dir, "demo.py", "print('old')\n")
            w.script_manager.open_script(path)
            widget = w.active_script_widget()
            widget.editor.setPlainText("print('new')\n")
            widget.editor.document().setModified(True)

            w.toolbar_manager._on_save_clicked()

            self.assertFalse(widget.editor.document().isModified())
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "print('new')\n")

    def test_save_action_saves_the_diagram_when_no_script_focused(self):
        w = _build_window()
        w.open_diagram_tab()
        with patch.object(w.scene_manager, "save_graph") as mock_save:
            w.toolbar_manager._on_save_clicked()
            mock_save.assert_called_once()


class TestRunDispatch(unittest.TestCase):
    def test_run_executes_the_active_script(self):
        w = _build_window()
        w.open_diagram_tab()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_script(tmp_dir, "demo.py", "add_block('Gain', name='G')\nprint('ran')\n")
            w.script_manager.open_script(path)

            w.toolbar_manager._on_run_or_stop_clicked()

        block_types = [ui.model.__class__.__name__ for ui in w.scene_manager.blocks_ui]
        self.assertIn("Gain", block_types)
        console_text = w.dock_manager.console_widget.output.toPlainText()
        self.assertIn("ran", console_text)
        self.assertIn(f"Run Script: {os.path.basename(path)}", console_text)

    def test_run_starts_a_simulation_when_no_script_focused(self):
        w = _build_window()
        w.open_diagram_tab()
        with patch.object(w.toolbar_manager, "run_simulation") as mock_run:
            w.toolbar_manager._on_run_or_stop_clicked()
            mock_run.assert_called_once()

    def test_run_toggle_reverts_to_idle_after_a_script_finishes(self):
        w = _build_window()
        w.open_diagram_tab()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_script(tmp_dir, "demo.py", "print('hi')\n")
            w.script_manager.open_script(path)
            w.toolbar_manager._on_run_or_stop_clicked()

        self.assertIsNone(w.toolbar_manager._run_kind)
        self.assertEqual(w.toolbar_manager.action_run.text(), "Run")
        self.assertTrue(w.toolbar_manager.run_progress.isHidden())

    def test_console_input_disabled_during_script_run_and_reenabled_after(self):
        w = _build_window()
        w.open_diagram_tab()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_script(tmp_dir, "demo.py", "print('hi')\n")
            w.script_manager.open_script(path)
            widget = w.active_script_widget()

            seen_enabled_mid_run = []
            orig_process_events = QApplication.processEvents

            def spy(*a, **kw):
                seen_enabled_mid_run.append(w.dock_manager.console_widget.input.isEnabled())
                return orig_process_events(*a, **kw)

            with patch.object(QApplication, "processEvents", side_effect=spy):
                w.toolbar_manager.run_script(widget)

        self.assertTrue(all(not enabled for enabled in seen_enabled_mid_run))
        self.assertTrue(w.dock_manager.console_widget.input.isEnabled())


class TestRunStopToggleState(unittest.TestCase):
    def test_set_running_shows_stop_icon_and_progress_bar(self):
        # isHidden() (the widget's own explicit flag) rather than
        # isVisible() (which also requires every ancestor up to a shown
        # top-level window -- MainWindow is never .show()n in this
        # headless test).
        w = _build_window()
        tm = w.toolbar_manager
        tm._set_running("sim")
        self.assertEqual(tm.action_run.text(), "Stop")
        self.assertFalse(tm.run_progress.isHidden())
        self.assertEqual(tm._run_kind, "sim")

    def test_set_running_script_uses_indeterminate_progress(self):
        w = _build_window()
        tm = w.toolbar_manager
        tm._set_running("script")
        self.assertEqual(tm.run_progress.minimum(), 0)
        self.assertEqual(tm.run_progress.maximum(), 0)

    def test_set_idle_restores_run_icon_and_hides_progress(self):
        w = _build_window()
        tm = w.toolbar_manager
        tm._set_running("sim")
        tm._set_idle()
        self.assertEqual(tm.action_run.text(), "Run")
        self.assertTrue(tm.run_progress.isHidden())
        self.assertIsNone(tm._run_kind)

    def test_clicking_run_while_running_stops_instead_of_starting_another(self):
        w = _build_window()
        w.open_diagram_tab()
        tm = w.toolbar_manager
        tm._set_running("sim")
        with patch.object(tm, "_stop_current_run") as mock_stop, \
             patch.object(tm, "run_simulation") as mock_run:
            tm._on_run_or_stop_clicked()
            mock_stop.assert_called_once()
            mock_run.assert_not_called()


class TestScriptCancellation(unittest.TestCase):
    """A Script can only be interrupted while it's inside a sim() call
    (should_cancel/on_progress threaded through -- see
    ScriptManager.execute_script()); Stop sets the flag ToolbarManager's
    own cooperative event pump checks on every processEvents() call."""

    def test_stop_click_mid_sim_cancels_it(self):
        w = _build_window()
        w.open_diagram_tab()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = _write_script(tmp_dir, "longsim.py", (
                "add_block('Constant', name='C')\n"
                "add_block('Scope', name='S')\n"
                "add_line('C', 'S')\n"
                "r = sim(duration=1000.0, dt=0.001)\n"
                "print('sim result:', r)\n"
            ))
            w.script_manager.open_script(path)
            widget = w.active_script_widget()

            orig_process_events = QApplication.processEvents
            call_count = [0]

            def fake_process_events(*a, **kw):
                call_count[0] += 1
                if call_count[0] == 2:
                    w.toolbar_manager._stop_current_run()
                return orig_process_events(*a, **kw)

            with patch.object(QApplication, "processEvents", side_effect=fake_process_events):
                w.toolbar_manager.run_script(widget)

        console_text = w.dock_manager.console_widget.output.toPlainText()
        self.assertIn("Simulation cancelled", console_text)
        self.assertIn("sim result: None", console_text)
        self.assertIsNone(w.toolbar_manager._run_kind)


class TestGlobalsSearchBar(unittest.TestCase):
    def test_search_filters_by_name(self):
        w = _build_window()
        w.script_manager.execute_command("apple = 1")
        w.script_manager.execute_command("banana = 2")
        gw = w.dock_manager.globals_widget
        gw.refresh()

        gw.search_edit.setText("app")

        visible = [
            gw.table.item(r, 0).text()
            for r in range(gw.table.rowCount())
            if not gw.table.isRowHidden(r)
        ]
        self.assertEqual(visible, ["apple"])

    def test_search_filters_by_value(self):
        w = _build_window()
        w.script_manager.execute_command("x = 'findme'")
        w.script_manager.execute_command("y = 'other'")
        gw = w.dock_manager.globals_widget
        gw.refresh()

        gw.search_edit.setText("findme")

        visible = [
            gw.table.item(r, 0).text()
            for r in range(gw.table.rowCount())
            if not gw.table.isRowHidden(r)
        ]
        self.assertEqual(visible, ["x"])

    def test_clearing_search_shows_everything_again(self):
        w = _build_window()
        w.script_manager.execute_command("x = 1")
        w.script_manager.execute_command("y = 2")
        gw = w.dock_manager.globals_widget
        gw.refresh()

        gw.search_edit.setText("x")
        gw.search_edit.setText("")

        hidden = [gw.table.isRowHidden(r) for r in range(gw.table.rowCount())]
        self.assertTrue(all(not h for h in hidden))

    def test_search_persists_across_auto_refresh(self):
        w = _build_window()
        w.script_manager.execute_command("apple = 1")
        gw = w.dock_manager.globals_widget
        gw.refresh()
        gw.search_edit.setText("apple")

        w.script_manager.execute_command("banana = 2")
        gw.refresh()  # simulates the auto-refresh timer tick

        visible = [
            gw.table.item(r, 0).text()
            for r in range(gw.table.rowCount())
            if not gw.table.isRowHidden(r)
        ]
        self.assertEqual(visible, ["apple"])


class TestStopIcon(unittest.TestCase):
    def test_stop_icon_registered_and_non_empty(self):
        from gui import icon_factory
        icon = icon_factory.icon("stop")
        self.assertFalse(icon.isNull())


if __name__ == "__main__":
    unittest.main()
