"""Tests for MainWindow's diagram tab closing -- regression coverage for a
real bug report: closing the last open diagram tab used to immediately
reopen a fresh blank ("Untitled") one, which the user didn't ask for and
couldn't avoid. Closing the last diagram now just leaves the workspace
empty, matching the app's own startup state (zero diagram tabs is already
a normal, fully-supported state -- see MainWindow.__init__).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def _build_window():
    from gui.main_window import MainWindow
    return MainWindow()


class TestClosingLastDiagramTab(unittest.TestCase):
    def test_closing_only_open_diagram_leaves_none_open(self):
        w = _build_window()
        w.open_diagram_tab()
        self.assertEqual(len(w._diagrams), 1)

        index = w.central_tabs.indexOf(w._diagrams[0].view)
        w._on_tab_close_requested(index)

        self.assertEqual(len(w._diagrams), 0)
        self.assertIsNone(w.scene_manager)

    def test_closing_last_diagram_disables_diagram_actions(self):
        w = _build_window()
        w.open_diagram_tab()
        self.assertTrue(w.toolbar_manager.action_save.isEnabled())

        index = w.central_tabs.indexOf(w._diagrams[0].view)
        w._on_tab_close_requested(index)

        self.assertFalse(w.toolbar_manager.action_save.isEnabled())

    def test_closing_one_of_several_diagrams_does_not_close_the_others(self):
        w = _build_window()
        w.open_diagram_tab()
        w.open_diagram_tab()
        self.assertEqual(len(w._diagrams), 2)

        index = w.central_tabs.indexOf(w._diagrams[0].view)
        w._on_tab_close_requested(index)

        self.assertEqual(len(w._diagrams), 1)
        self.assertIsNotNone(w.scene_manager)


if __name__ == "__main__":
    unittest.main()
