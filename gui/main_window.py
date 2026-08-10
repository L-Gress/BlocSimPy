"""Main window orchestrator - delegates to managers."""
import os
import sys
from PySide6.QtWidgets import QMainWindow, QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QIcon
from config.ui_config import UIConfig
from .scene import NodeScene
from .widgets import GraphicsView
from .managers import ToolbarManager, SceneManager, DockManager, ScriptManager
from .dialogs import HelpDialog


class MainWindow(QMainWindow):
    """
    Main application window - orchestrates managers.

    This class is now a lightweight orchestrator that delegates
    all major responsibilities to specialized manager classes.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle(UIConfig.WINDOW_TITLE)
        self.resize(UIConfig.WINDOW_WIDTH, UIConfig.WINDOW_HEIGHT)
        self.settings = QSettings("BlocSimPy", "BlocSimPy")

        # Set Window Icon. Resolved relative to this file (not cwd) so it
        # works no matter where the app is launched from, except when frozen
        # by PyInstaller, where logo.png is bundled next to the executable.
        if hasattr(sys, '_MEIPASS'):
            logo_path = os.path.join(sys._MEIPASS, "logo.png")
        else:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_path = os.path.join(project_root, "logo.png")

        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        # --- Initialize Managers ---
        self.scene_manager = SceneManager(self)
        self.toolbar_manager = ToolbarManager(self)
        self.dock_manager = DockManager(self)
        self.script_manager = ScriptManager(self)

        # --- Scene Setup ---
        self.scene = NodeScene(self)

        # --- View Setup ---
        self.view = GraphicsView()
        self.view.setScene(self.scene)
        self.setCentralWidget(self.view)

        # --- Toolbar Setup ---
        toolbar = self.toolbar_manager.create_toolbar()
        self.addToolBar(toolbar)

        # --- Menu Bar (reuses the same QActions as the toolbar) ---
        self._create_menu_bar()

        # --- Status Bar with Breadcrumb ---
        breadcrumb = QLabel("📍 Location: Top Level")
        self.statusBar().addWidget(breadcrumb)
        self.scene_manager.breadcrumb_label = breadcrumb

        # --- Library Dock ---
        library_dock = self.dock_manager.create_library_dock()
        self.addDockWidget(Qt.LeftDockWidgetArea, library_dock)

        # Store reference to user library widget for access by scene_manager
        self.user_library_widget = self.dock_manager.user_library_widget

        self.refresh_title()
        self._restore_window_state()

    def _create_menu_bar(self):
        """Build File/Edit/View/Simulation/Help menus from the toolbar's QActions."""
        tm = self.toolbar_manager
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(tm.action_new)
        file_menu.addAction(tm.action_load)
        file_menu.addSeparator()
        file_menu.addAction(tm.action_save)
        file_menu.addAction(tm.action_save_as)
        file_menu.addSeparator()
        file_menu.addAction(tm.action_quit)

        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(tm.action_undo)
        edit_menu.addAction(tm.action_redo)
        edit_menu.addSeparator()
        edit_menu.addAction(tm.action_cut)
        edit_menu.addAction(tm.action_copy)
        edit_menu.addAction(tm.action_paste)
        edit_menu.addAction(tm.action_delete)
        edit_menu.addSeparator()
        edit_menu.addAction(tm.action_select_all)

        view_menu = menu_bar.addMenu("&View")
        view_menu.addAction(tm.action_toggle_lib)
        view_menu.addAction(tm.action_up)

        sim_menu = menu_bar.addMenu("&Simulation")
        sim_menu.addAction(tm.action_sim_settings)
        sim_menu.addAction(tm.action_run)
        sim_menu.addAction(tm.action_inspector)

        tools_menu = menu_bar.addMenu("&Tools")
        tools_menu.addAction(tm.action_save_subgraph)
        tools_menu.addAction(tm.action_scripts)

        help_menu = menu_bar.addMenu("&Help")
        help_menu.addAction(tm.action_help)
        help_menu.addSeparator()
        help_menu.addAction(tm.action_about)

    def _restore_window_state(self):
        geometry = self.settings.value("geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        state = self.settings.value("windowState")
        if state is not None:
            self.restoreState(state)

    def refresh_title(self):
        """Reflect the current file name and unsaved-changes state in the
        title bar (the trailing [*] is Qt's own modified-document marker,
        rendered as e.g. a dot in the close button on macOS)."""
        current_path = self.scene_manager.current_file_path
        name = os.path.basename(current_path) if current_path else "Untitled"
        self.setWindowTitle(f"{UIConfig.WINDOW_TITLE} - {name}[*]")
        self.setWindowModified(self.scene_manager.is_modified)

    def closeEvent(self, event):
        if not self.scene_manager.confirm_discard_changes():
            event.ignore()
            return

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        super().closeEvent(event)

    def show_help(self):
        """Show help dialog."""
        dialog = HelpDialog(self)
        dialog.exec()

    def enter_subsystem(self, subsystem_ui_block):
        """Delegate to scene_manager to enter a subsystem."""
        self.scene_manager.enter_subsystem(subsystem_ui_block)
