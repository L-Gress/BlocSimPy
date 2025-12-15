"""Manages dock widgets (library, etc)."""
from PySide6.QtWidgets import QDockWidget, QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout, QLineEdit, QLabel, QTabWidget
from PySide6.QtCore import Qt
from engine.blocks import BLOCK_REGISTRY
from ..library import UserLibraryWidget


class DockManager:
    """Manages dock widgets in the main window."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.library_dock = None
        self.user_library_widget = None
        self.block_tree = None
        
    def create_library_dock(self):
        """Create the library dock with categorized block tree and user library."""
        
        # Create dock
        self.library_dock = QDockWidget("Library", self.main_window)
        self.library_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Container widget with tabs
        library_container = QWidget()
        library_layout = QVBoxLayout(library_container)
        library_layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget
        library_tabs = QTabWidget()
        
        # Tab 1: Block Library
        blocks_tab = QWidget()
        blocks_layout = QVBoxLayout(blocks_tab)
        blocks_layout.setContentsMargins(5, 5, 5, 5)
        
        # Search bar
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search blocks...")
        search_bar.textChanged.connect(self._filter_blocks)
        blocks_layout.addWidget(search_bar)
        
        # Block Tree
        self.block_tree = QTreeWidget()
        self.block_tree.setHeaderHidden(True)
        self.block_tree.itemDoubleClicked.connect(self._on_tree_double_click)
        blocks_layout.addWidget(self.block_tree)
        
        # Populate block tree
        self._populate_library()
        
        library_tabs.addTab(blocks_tab, "Blocks")
        
        # Tab 2: User Library
        self.user_library_widget = UserLibraryWidget()
        self.user_library_widget.load_requested.connect(
            self.main_window.scene_manager.spawn_subgraph_from_library
        )
        library_tabs.addTab(self.user_library_widget, "User Library")
        
        library_layout.addWidget(library_tabs)
        
        self.library_dock.setWidget(library_container)
        return self.library_dock
    
    def _populate_library(self):
        """Populate the block tree with categories from BLOCK_INFO."""
        
        # Default categorized structure
        category_map = {}
        
        for name, block_cls in BLOCK_REGISTRY.items():
            # Get category from BLOCK_INFO, default to "Common"
            category = "Common"
            if hasattr(block_cls, "BLOCK_INFO"):
                category = block_cls.BLOCK_INFO.get("category", "Common")
            
            if category not in category_map:
                category_map[category] = []
            category_map[category].append(name)
        
        # Create Tree Items
        self.block_tree.clear()
        
        # Sort categories (Common last or first? Alphabetical seems fine)
        sorted_cats = sorted(category_map.keys())
        # Ensure Common/Standard is last if you prefer
        
        for cat_name in sorted_cats:
            cat_item = QTreeWidgetItem(self.block_tree)
            cat_item.setText(0, cat_name)
            cat_item.setExpanded(True)
            
            for b_name in sorted(category_map[cat_name]):
                b_item = QTreeWidgetItem(cat_item)
                b_item.setText(0, b_name)
        
    def _on_tree_double_click(self, item, column):
        """Handle tree double click - if leaf node, add block."""
        if item.childCount() == 0:
            # It's a block
            block_class_name = item.text(0)
            if block_class_name in BLOCK_REGISTRY:
                # Mock a list interface because scene_manager expects an item with .text()
                # Actually scene_manager expects an item.
                # let's modify the way we call it.
                # We can reuse the item directly because item.text(0) works, 
                # but scene_manager.add_block_to_scene calls list_item.text().
                # QTreeWidgetItem.text(column) takes an arg. list_item.text() takes 0.
                
                # We should update SceneManager to accept a string name, 
                # OR wrap this call.
                # Easiest: SceneManager.add_block_by_name
                self.main_window.scene_manager.add_block_by_name(block_class_name)

    def toggle_library(self):
        """Toggle visibility of the library dock."""
        if self.library_dock:
            self.library_dock.setVisible(not self.library_dock.isVisible())
    
    def _filter_blocks(self, search_text):
        """Filter blocks in the library tree based on search text."""
        search_lower = search_text.lower()
        root = self.block_tree.invisibleRootItem()
        
        for i in range(root.childCount()):
            category = root.child(i)
            cat_visible_children = 0
            
            for j in range(category.childCount()):
                child = category.child(j)
                text = child.text(0)
                
                if search_lower in text.lower():
                    child.setHidden(False)
                    cat_visible_children += 1
                else:
                    child.setHidden(True)
            
            # Hide category if no children visible
            category.setHidden(cat_visible_children == 0)
