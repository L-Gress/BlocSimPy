"""Tests for gui/managers/dock_manager.py's Library tree double-click
handling -- regression coverage for a real crash report: double-clicking a
block in the Library before any diagram tab is open (main_window.scene_manager
is None at startup -- see MainWindow) raised an unhandled AttributeError
instead of telling the user what to do.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtWidgets import QApplication, QTreeWidgetItem

_app = QApplication.instance() or QApplication([])


def _build_window():
    from gui.main_window import MainWindow
    return MainWindow()


class TestLibraryDoubleClickNoDiagramOpen(unittest.TestCase):
    def test_double_click_with_no_diagram_open_does_not_raise(self):
        w = _build_window()
        self.assertIsNone(w.scene_manager)

        item = QTreeWidgetItem()
        item.setText(0, "Gain")

        w.dock_manager._on_tree_double_click(item, 0)  # must not raise

    def test_double_click_with_no_diagram_open_shows_status_message(self):
        w = _build_window()

        item = QTreeWidgetItem()
        item.setText(0, "Gain")
        w.dock_manager._on_tree_double_click(item, 0)

        self.assertIn("Open or create a diagram", w.status_label.text())

    def test_double_click_on_category_node_does_not_raise(self):
        # A category node (childCount() > 0) isn't a block leaf -- the
        # existing early-return path, unaffected by this fix, still holds.
        w = _build_window()
        category = QTreeWidgetItem()
        category.setText(0, "Math")
        QTreeWidgetItem(category)  # give it a child so childCount() > 0

        w.dock_manager._on_tree_double_click(category, 0)  # must not raise


class TestLibraryDoubleClickWithDiagramOpen(unittest.TestCase):
    def test_double_click_adds_block_once_a_diagram_is_open(self):
        w = _build_window()
        w.open_diagram_tab()
        self.assertIsNotNone(w.scene_manager)

        item = QTreeWidgetItem()
        item.setText(0, "Gain")
        w.dock_manager._on_tree_double_click(item, 0)

        block_types = [ui.model.__class__.__name__ for ui in w.scene_manager.blocks_ui]
        self.assertIn("Gain", block_types)


if __name__ == "__main__":
    unittest.main()
