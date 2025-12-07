import os
import json
import shutil
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem, 
                               QMenu, QInputDialog, QMessageBox, QStyle)  # <--- Added QStyle import
from PySide6.QtCore import Qt, Signal

# Define the root directory for user library
LIBRARY_ROOT = "user_library"

class UserLibraryWidget(QWidget):
    """
    Widget that displays folders and saved SubGraphs.
    Emits 'item_double_clicked' with the file path when a user wants to load one.
    """
    load_requested = Signal(str) # Path to the .json file

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Ensure library directory exists
        if not os.path.exists(LIBRARY_ROOT):
            os.makedirs(LIBRARY_ROOT)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Tree Widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("User SubGraphs")
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        self.tree.itemDoubleClicked.connect(self.on_double_click)
        self.tree.setDragEnabled(False) 
        
        self.layout.addWidget(self.tree)
        self.refresh_tree()

    def refresh_tree(self):
        """Reloads the tree from the file system."""
        self.tree.clear()
        
        # 1. List Folders
        if os.path.exists(LIBRARY_ROOT):
            for entry in os.listdir(LIBRARY_ROOT):
                path = os.path.join(LIBRARY_ROOT, entry)
                if os.path.isdir(path):
                    folder_item = QTreeWidgetItem(self.tree)
                    folder_item.setText(0, entry)
                    
                    # --- FIXED LINE BELOW ---
                    # Use QStyle.StandardPixmap.SP_DirIcon
                    folder_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                    
                    folder_item.setData(0, Qt.UserRole, "folder")
                    folder_item.setData(0, Qt.UserRole + 1, path)
                    
                    # 2. List Files inside Folder
                    for sub_entry in os.listdir(path):
                        if sub_entry.endswith(".json"):
                            file_path = os.path.join(path, sub_entry)
                            file_item = QTreeWidgetItem(folder_item)
                            file_item.setText(0, sub_entry[:-5]) 
                            
                            # --- FIXED LINE BELOW ---
                            # Use QStyle.StandardPixmap.SP_FileIcon
                            file_item.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                            
                            file_item.setData(0, Qt.UserRole, "file")
                            file_item.setData(0, Qt.UserRole + 1, file_path)

        self.tree.expandAll()

    def open_context_menu(self, position):
        item = self.tree.itemAt(position)
        menu = QMenu()

        if item is None:
            # Clicked on whitespace -> New Folder
            action_new_folder = menu.addAction("New Folder")
            if menu.exec(self.tree.viewport().mapToGlobal(position)) == action_new_folder:
                self.create_folder()
        else:
            item_type = item.data(0, Qt.UserRole)
            path = item.data(0, Qt.UserRole + 1)
            
            if item_type == "folder":
                menu.addAction("New Folder (Root)").triggered.connect(self.create_folder)
                menu.addSeparator()
                menu.addAction("Rename Folder").triggered.connect(lambda: self.rename_item(item))
                menu.addAction("Delete Folder").triggered.connect(lambda: self.delete_item(item))
            elif item_type == "file":
                menu.addAction("Load to Scene").triggered.connect(lambda: self.load_requested.emit(path))
                menu.addSeparator()
                menu.addAction("Rename SubGraph").triggered.connect(lambda: self.rename_item(item))
                menu.addAction("Delete SubGraph").triggered.connect(lambda: self.delete_item(item))

            menu.exec(self.tree.viewport().mapToGlobal(position))

    def create_folder(self):
        name, ok = QInputDialog.getText(self, "New Folder", "Folder Name:")
        if ok and name:
            path = os.path.join(LIBRARY_ROOT, name)
            try:
                os.makedirs(path)
                self.refresh_tree()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def rename_item(self, item):
        old_path = item.data(0, Qt.UserRole + 1)
        item_type = item.data(0, Qt.UserRole)
        
        old_name = item.text(0)
        new_name, ok = QInputDialog.getText(self, "Rename", "New Name:", text=old_name)
        
        if ok and new_name:
            if item_type == "file" and not new_name.endswith(".json"):
                new_filename = new_name + ".json"
            else:
                new_filename = new_name

            base_dir = os.path.dirname(old_path)
            new_path = os.path.join(base_dir, new_filename)
            
            try:
                os.rename(old_path, new_path)
                self.refresh_tree()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def delete_item(self, item):
        path = item.data(0, Qt.UserRole + 1)
        item_type = item.data(0, Qt.UserRole)
        
        res = QMessageBox.question(self, "Confirm Delete", f"Delete '{item.text(0)}'?", 
                                   QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            try:
                if item_type == "folder":
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                self.refresh_tree()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def on_double_click(self, item, column):
        item_type = item.data(0, Qt.UserRole)
        path = item.data(0, Qt.UserRole + 1)
        if item_type == "file":
            self.load_requested.emit(path)

    def save_subgraph(self, subgraph_data, subgraph_name):
        """
        Public method called by MainWindow to save a JSON blob.
        Prompts user for folder selection.
        """
        # Get list of folders
        folders = [d for d in os.listdir(LIBRARY_ROOT) if os.path.isdir(os.path.join(LIBRARY_ROOT, d))]
        if not folders:
            QMessageBox.warning(self, "No Folders", "Create a folder in the library first.")
            return

        folder, ok = QInputDialog.getItem(self, "Select Folder", "Save to Folder:", folders, 0, False)
        if not ok or not folder:
            return

        # Sanitize name
        filename = f"{subgraph_name}.json"
        save_path = os.path.join(LIBRARY_ROOT, folder, filename)

        # Check overwrite
        if os.path.exists(save_path):
            res = QMessageBox.question(self, "Overwrite", f"{filename} exists. Overwrite?", 
                                       QMessageBox.Yes | QMessageBox.No)
            if res != QMessageBox.Yes:
                return

        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(subgraph_data, f, indent=4)
            self.refresh_tree()
            QMessageBox.information(self, "Success", f"Saved to {folder}/{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))