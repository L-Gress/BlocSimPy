import os
import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
                               QMenu, QInputDialog, QMessageBox)
from PySide6.QtCore import Qt, Signal
from . import icon_factory

DEFAULT_SCRIPT_TEMPLATE = (
    "# BlocSimPy Scripting Interface\n"
    "# -----------------------------\n"
    "# Available functions:\n"
    "#   set_param(block_name, param_name, value)\n"
    "#   run_simulation()\n"
    "#   print(text)\n\n"
    "print('Hello from BlocSimPy!')\n"
)

# Diagrams and SubGraphs both save as .json in this one flat folder (no
# subfolders -- see ProjectManager), so which bucket a .json file belongs
# to is decided by a "blocksimpy_kind" marker written at save time (see
# scene_manager._save_to_file() and save_subgraph() below), not by path.
# Scripts are unambiguous by extension.
_CATEGORY_INFO = {
    "diagrams": {"label": "Diagrams", "file_icon": "new"},
    "subgraphs": {"label": "SubGraphs", "file_icon": "subgraph"},
    "scripts": {"label": "Scripts", "file_icon": "scripts"},
}
_CATEGORY_ORDER = ["diagrams", "subgraphs", "scripts"]
_OPEN_LABELS = {"diagrams": "Open Diagram", "subgraphs": "Load to Scene", "scripts": "Open Script"}


class UserSpaceWidget(QWidget):
    """
    Your personal workspace: every Diagram, SubGraph, and Script in the
    current Project Folder (see gui/managers/project_manager.py) -- one
    flat folder, no subfolders, so it can be pointed at any folder on
    disk. The three groups shown here are a display-time classification
    of that one folder's contents, not separate physical locations.

    Emits 'diagram_open_requested' with a Diagram's file path when the
    user wants it opened (replacing the canvas), 'load_requested' with a
    SubGraph's file path when they want it dropped onto the canvas, and
    'script_open_requested' with a Script's file path when they want it
    opened in the Script Editor.
    """
    diagram_open_requested = Signal(str)  # Diagram .json path
    load_requested = Signal(str)          # SubGraph .json path
    script_open_requested = Signal(str)   # Script .py path

    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        self.tree.itemDoubleClicked.connect(self.on_double_click)
        self.tree.setDragEnabled(False)

        self.layout.addWidget(self.tree)
        self.set_root(root)

    def set_root(self, root):
        """Point this widget at a project's (flat) folder, or at nothing
        (root=None, the initial state -- no project is opened
        automatically) to show an empty placeholder instead. Called once
        at construction, and again by ProjectManager whenever the user
        opens/switches a project folder."""
        self.root = root
        if root is not None:
            os.makedirs(self.root, exist_ok=True)
        self.refresh_tree()

    def _status(self, message):
        """Routine, non-blocking confirmation shown in the main window's
        status bar instead of an interrupting QMessageBox.information() --
        see MainWindow.show_status(). self.window() resolves to MainWindow
        since this widget lives docked (not floating) inside it."""
        main_window = self.window()
        if hasattr(main_window, "show_status"):
            main_window.show_status(message)

    def refresh_tree(self):
        """Reloads the tree from the file system."""
        self.tree.clear()

        if self.root is None:
            placeholder = QTreeWidgetItem(self.tree)
            placeholder.setText(0, "No Project Folder open")
            placeholder.setToolTip(0, "File → Open Project Folder... to get started.")
            placeholder.setFlags(Qt.ItemIsEnabled)  # visible, but not selectable/interactive
            return

        category_items = {}
        for key in _CATEGORY_ORDER:
            info = _CATEGORY_INFO[key]
            cat_item = QTreeWidgetItem(self.tree)
            cat_item.setText(0, info["label"])
            cat_item.setIcon(0, icon_factory.icon("open"))
            cat_item.setData(0, Qt.UserRole, "category")
            cat_item.setData(0, Qt.UserRole + 2, key)
            cat_item.setExpanded(True)
            category_items[key] = cat_item

        if os.path.isdir(self.root):
            for entry in sorted(os.listdir(self.root)):
                path = os.path.join(self.root, entry)
                if os.path.isdir(path):
                    continue  # Flat layout -- other folders here aren't ours to manage.

                key = self._classify(path)
                if key is None:
                    continue

                ext_len = 3 if key == "scripts" else 5  # len(".py") vs len(".json")
                file_item = QTreeWidgetItem(category_items[key])
                file_item.setText(0, entry[:-ext_len])
                file_item.setIcon(0, icon_factory.icon(_CATEGORY_INFO[key]["file_icon"]))
                file_item.setData(0, Qt.UserRole, "file")
                file_item.setData(0, Qt.UserRole + 1, path)
                file_item.setData(0, Qt.UserRole + 2, key)

        self.tree.expandAll()

    # blocksimpy_kind marker value (singular -- see scene_manager._save_to_file()
    # and save_subgraph() below) -> the category key it belongs under (plural,
    # matching _CATEGORY_INFO).
    _KIND_TO_CATEGORY = {"diagram": "diagrams", "subgraph": "subgraphs"}

    def _classify(self, path):
        """Which category a file belongs to, or None to leave it out of
        the tree entirely (not a BlocSimPy file)."""
        if path.endswith(".py"):
            return "scripts"
        if not path.endswith(".json"):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return None

        kind = data.get("blocksimpy_kind")
        if kind not in self._KIND_TO_CATEGORY:
            # Legacy file saved before this marker existed: a SubGraph's
            # file is exactly {"blocks", "connections", "params"} (its own
            # interface parameters); a Diagram's never has a top-level
            # "params" key. Good enough to place old files correctly
            # without requiring a resave.
            kind = "subgraph" if "params" in data else "diagram"

        return self._KIND_TO_CATEGORY[kind]

    def _emit_open(self, category_key, path):
        if category_key == "diagrams":
            self.diagram_open_requested.emit(path)
        elif category_key == "scripts":
            self.script_open_requested.emit(path)
        else:
            self.load_requested.emit(path)

    def open_context_menu(self, position):
        item = self.tree.itemAt(position)
        if item is None:
            return

        item_type = item.data(0, Qt.UserRole)
        category_key = item.data(0, Qt.UserRole + 2)
        path = item.data(0, Qt.UserRole + 1)

        menu = QMenu()
        if item_type == "category" and category_key == "scripts":
            menu.addAction("New Script").triggered.connect(self.create_script)
        elif item_type == "file":
            menu.addAction(_OPEN_LABELS[category_key]).triggered.connect(
                lambda: self._emit_open(category_key, path)
            )
            menu.addSeparator()
            menu.addAction("Rename").triggered.connect(lambda: self.rename_item(item))
            menu.addAction("Delete").triggered.connect(lambda: self.delete_item(item))

        if menu.actions():
            menu.exec(self.tree.viewport().mapToGlobal(position))

    def create_script(self):
        """Create a new .py file (from a starter template) directly in
        the project root, and open it right away in the Script Editor."""
        if self.root is None:
            return  # Not reachable via the UI (no Scripts category without a project), belt and suspenders.

        name, ok = QInputDialog.getText(self, "New Script", "Script Name:")
        if not (ok and name):
            return

        filename = name if name.endswith(".py") else f"{name}.py"
        save_path = os.path.join(self.root, filename)
        if os.path.exists(save_path):
            self._status(f"'{filename}' already exists.")
            return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(DEFAULT_SCRIPT_TEMPLATE)
            self.refresh_tree()
            self.script_open_requested.emit(save_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def rename_item(self, item):
        old_path = item.data(0, Qt.UserRole + 1)
        category_key = item.data(0, Qt.UserRole + 2)

        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, "Rename", "New Name:", text=old_name)
        if not (ok and new_name):
            return

        ext = ".py" if category_key == "scripts" else ".json"
        new_filename = new_name if new_name.endswith(ext) else new_name + ext
        new_path = os.path.join(self.root, new_filename)

        try:
            os.rename(old_path, new_path)
            self.refresh_tree()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def delete_item(self, item):
        path = item.data(0, Qt.UserRole + 1)

        res = QMessageBox.question(self, "Confirm Delete", f"Delete '{item.text(0)}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            try:
                os.remove(path)
                self.refresh_tree()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def on_double_click(self, item, column):
        if item.data(0, Qt.UserRole) != "file":
            return
        path = item.data(0, Qt.UserRole + 1)
        category_key = item.data(0, Qt.UserRole + 2)
        self._emit_open(category_key, path)

    def save_subgraph(self, subgraph_data, subgraph_name):
        """
        Public method called by MainWindow to save a SubGraph's data as a
        named .json file directly in the project root.
        """
        if self.root is None:
            self._status("Open a Project Folder first (File → Open Project Folder...).")
            return

        filename = f"{subgraph_name}.json"
        save_path = os.path.join(self.root, filename)

        if os.path.exists(save_path):
            res = QMessageBox.question(self, "Overwrite", f"{filename} exists. Overwrite?",
                                       QMessageBox.Yes | QMessageBox.No)
            if res != QMessageBox.Yes:
                return

        data_to_write = dict(subgraph_data)
        data_to_write["blocksimpy_kind"] = "subgraph"

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data_to_write, f, indent=4)
            self.refresh_tree()
            self._status(f"Saved {filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
