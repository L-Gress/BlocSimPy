"""Main window orchestrator - delegates to managers."""
import os
import sys
from PySide6.QtWidgets import QMainWindow, QLabel, QTabWidget, QFileDialog
from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QIcon
from config.ui_config import UIConfig
from .scene import NodeScene
from .widgets import GraphicsView
from .managers import ToolbarManager, SceneManager, DockManager, ScriptManager, ProjectManager
from .dialogs import HelpDialog


class _DiagramDocument:
    """One open Diagram tab's scene + view + owning SceneManager, bundled
    together so MainWindow can track several at once."""

    def __init__(self, scene, view, scene_manager, blank_title=None):
        self.scene = scene
        self.view = view
        self.scene_manager = scene_manager
        # Assigned display name ("Untitled", "Untitled 2", ...) for a
        # diagram with no file yet -- update_diagram_tab_title() needs
        # this to survive repeated calls (every edit), instead of
        # collapsing every blank diagram back to the same "Untitled".
        self.blank_title = blank_title


class MainWindow(QMainWindow):
    """
    Main application window - orchestrates managers.

    This class is now a lightweight orchestrator that delegates
    all major responsibilities to specialized manager classes.

    Multiple diagrams can be open at once, each its own tab with its own
    NodeScene/GraphicsView/SceneManager (see open_diagram_tab()).
    `self.scene`/`self.view`/`self.scene_manager` are properties pointing
    at whichever diagram tab is currently active -- not fixed attributes
    -- so the rest of the app (toolbar actions, items reaching up via
    `scene.parent()`, ...) keeps working against "the current diagram"
    without needing to know which one that is.
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
            app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            logo_path = os.path.join(app_root, "logo.png")

        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        # --- Central workspace: a proper multi-page tab area. Diagrams,
        # Scripts, and simulation results all live here as tabs that stay
        # open side by side instead of one replacing another.
        self._diagrams = []          # list[_DiagramDocument], in tab order
        self._active_diagram = None  # whichever diagram tab was last focused
        self._untitled_diagram_counter = 0
        self._script_tabs = {}       # file_path -> ScriptEditorWidget
        self._simulation_tabs = {}   # id(widget) -> SimulationResultWidget
        self._last_sim_tab_widget = None
        self._simulation_tab_counter = 0

        # Shared across every diagram tab (not per-SceneManager), so
        # Ctrl+C in one diagram and Ctrl+V in another actually works --
        # see SceneManager.copy_selection()/paste_selection().
        self.diagram_clipboard = None
        self.diagram_clipboard_paste_count = 0

        self.central_tabs = QTabWidget()
        self.central_tabs.setTabsClosable(True)
        self.central_tabs.setMovable(True)
        self.central_tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.central_tabs.currentChanged.connect(self._on_current_tab_changed)
        self.setCentralWidget(self.central_tabs)

        # --- Initialize Managers ---
        self.toolbar_manager = ToolbarManager(self)
        self.dock_manager = DockManager(self)
        self.script_manager = ScriptManager(self)
        # No project folder is opened automatically -- project_root starts
        # None, same "don't open something the user didn't ask for" rule
        # as diagrams starting with no tabs. File > Open Project Folder...
        # is the only way in.
        self.project_manager = ProjectManager(self)

        # --- Toolbar Setup ---
        toolbar = self.toolbar_manager.create_toolbar()
        self.addToolBar(toolbar)

        # --- Menu Bar (reuses the same QActions as the toolbar) ---
        self._create_menu_bar()

        # --- Status Bar: depth-level breadcrumb (left) + transient status
        # text (right) -- addPermanentWidget() docks status_label at the
        # right edge, unaffected by/not hiding the breadcrumb, unlike
        # QStatusBar.showMessage()'s temporary-message area. One shared
        # breadcrumb label is handed to every diagram's SceneManager; only
        # the currently-active one ever writes to it (see
        # _on_current_tab_changed).
        self.breadcrumb_label = QLabel("📍 Location: Top Level")
        self.statusBar().addWidget(self.breadcrumb_label)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #6e6e73;")
        self.statusBar().addPermanentWidget(self.status_label)

        # --- Library Dock ---
        library_dock = self.dock_manager.create_library_dock()
        self.addDockWidget(Qt.LeftDockWidgetArea, library_dock)

        # Store reference to the User Space widget for access by scene_manager
        self.user_space_widget = self.dock_manager.user_space_widget

        # --- Console Dock --- (hidden by default, see create_console_dock())
        console_dock = self.dock_manager.create_console_dock()
        self.addDockWidget(Qt.BottomDockWidgetArea, console_dock)

        # --- Global Variables Dock --- (hidden by default, see create_globals_dock())
        globals_dock = self.dock_manager.create_globals_dock()
        self.addDockWidget(Qt.RightDockWidgetArea, globals_dock)

        # Starts with NO diagram tab open -- an empty workspace rather than
        # an unwanted blank "Untitled" every launch. Diagram-dependent
        # actions (Save, Undo, Cut, Run, ...) start disabled to match;
        # opening/creating the first diagram (New, Open, or double-clicking
        # one in User Space) re-enables them, and stays that way for the
        # rest of the session -- see open_diagram_tab().
        self.toolbar_manager.set_diagram_actions_enabled(False)

        self.refresh_title()
        self._restore_window_state()

    # --- Active-diagram properties --------------------------------------
    # Read fresh on every access (never cached), so they always reflect
    # whichever diagram tab is currently active. Signal connections that
    # need this same "always current" behavior must go through a lambda
    # (e.g. `lambda: self.scene_manager.save_graph()`), never bind
    # directly to `self.scene_manager.save_graph` -- that would capture
    # today's active diagram forever.

    @property
    def scene_manager(self):
        return self._active_diagram.scene_manager if self._active_diagram else None

    @property
    def scene(self):
        return self._active_diagram.scene if self._active_diagram else None

    @property
    def view(self):
        return self._active_diagram.view if self._active_diagram else None

    # --- Diagram tab management ------------------------------------------

    def open_diagram_tab(self, file_path=None):
        """Open `file_path` in its own Diagram tab, or a fresh blank
        ('Untitled') one if file_path is None. Reuses an existing tab if
        that file is already open rather than duplicating it. New/Open
        and double-clicking a Diagram in User Space all route through
        here, so multiple diagrams stay open side by side instead of one
        replacing another."""
        if file_path is not None:
            for doc in self._diagrams:
                if doc.scene_manager.current_file_path == file_path:
                    self.central_tabs.setCurrentWidget(doc.view)
                    return doc.scene_manager

        scene = NodeScene(self)
        view = GraphicsView()
        view.setScene(scene)
        scene_manager = SceneManager(self, scene)
        scene_manager.breadcrumb_label = self.breadcrumb_label

        if file_path is not None:
            title = os.path.basename(file_path)
            blank_title = None
        else:
            self._untitled_diagram_counter += 1
            title = "Untitled" if self._untitled_diagram_counter == 1 else f"Untitled {self._untitled_diagram_counter}"
            blank_title = title

        doc = _DiagramDocument(scene, view, scene_manager, blank_title)
        self._diagrams.append(doc)
        self.toolbar_manager.set_diagram_actions_enabled(True)  # first diagram of the session, or just another one

        index = self.central_tabs.addTab(view, title)
        self.central_tabs.setCurrentIndex(index)
        self._active_diagram = doc

        if file_path is not None:
            scene_manager.load_file(file_path)

        return scene_manager

    def open_diagram_dialog(self):
        """File > Open... -- pick a diagram file from disk and open it in
        its own tab (or switch to it if already open)."""
        start_dir = self.project_manager.project_root or ""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Graph", start_dir, "JSON Files (*.json)"
        )
        if file_path:
            self.open_diagram_tab(file_path)

    def _diagram_for_view(self, widget):
        for doc in self._diagrams:
            if doc.view is widget:
                return doc
        return None

    def _diagram_for_scene_manager(self, scene_manager):
        for doc in self._diagrams:
            if doc.scene_manager is scene_manager:
                return doc
        return None

    def update_diagram_tab_title(self, scene_manager):
        """Reflect this diagram's file name and unsaved-edits state in its
        own tab label (e.g. 'sim.json •') -- other open diagrams' tabs are
        untouched. Connected via SceneManager.set_modified()."""
        doc = self._diagram_for_scene_manager(scene_manager)
        if doc is None:
            return
        index = self.central_tabs.indexOf(doc.view)
        if index == -1:
            return
        if scene_manager.current_file_path:
            name = os.path.basename(scene_manager.current_file_path)
        else:
            name = doc.blank_title or "Untitled"
        self.central_tabs.setTabText(index, f"{name} •" if scene_manager.is_modified else name)

    def confirm_discard_all_diagrams(self):
        """Check every open diagram for unsaved changes, not just the
        active one -- used before closing the app or switching Project
        Folder."""
        for doc in self._diagrams:
            if not doc.scene_manager.confirm_discard_changes():
                return False
        return True

    def close_all_diagrams(self):
        """Close every open diagram tab without opening a replacement --
        used when switching to a different Project Folder, since a
        different project's diagrams don't belong on screen anymore, and
        (same reasoning as starting with no diagram tab at all) BlocSimPy
        shouldn't hand you a blank one you didn't ask for either. Caller
        must have already confirmed discarding unsaved changes via
        confirm_discard_all_diagrams()."""
        for doc in list(self._diagrams):
            self._remove_diagram_document(doc)

    def _remove_diagram_document(self, doc):
        index = self.central_tabs.indexOf(doc.view)
        if index != -1:
            self.central_tabs.removeTab(index)
        self._diagrams.remove(doc)
        if self._active_diagram is doc:
            self._active_diagram = self._diagrams[-1] if self._diagrams else None
        if not self._diagrams:
            self.toolbar_manager.set_diagram_actions_enabled(False)
            # set_diagram_actions_enabled(False) just disabled action_run/
            # action_save too, but those are also usable for a Script tab
            # (see active_script_widget()) -- re-enable them if one's
            # still open even though the last diagram just closed.
            self._update_run_save_enabled()
        doc.view.deleteLater()
        doc.scene.deleteLater()

    def _update_run_save_enabled(self):
        """action_run/action_save are usable whenever EITHER a diagram OR
        a Script tab exists (see active_script_widget()) -- unlike the
        rest of set_diagram_actions_enabled()'s list, which only makes
        sense with a diagram open. Called whenever a diagram or Script tab
        opens or closes."""
        enabled = bool(self._diagrams) or bool(self._script_tabs)
        self.toolbar_manager.action_run.setEnabled(enabled)
        self.toolbar_manager.action_save.setEnabled(enabled)

    def show_diagram_editor(self):
        """Switch focus to the currently-active diagram tab. Doesn't close
        or otherwise touch any open Script/Simulation tabs -- they simply
        lose focus, same as switching tabs in any other multi-page
        editor."""
        if self._active_diagram is not None:
            self.central_tabs.setCurrentWidget(self._active_diagram.view)

    def active_script_widget(self):
        """The ScriptEditorWidget for whichever Script tab is currently
        focused, or None if a Diagram/Simulation tab (or nothing) is
        active -- lets the shared Run/Save toolbar actions dispatch to the
        right target (see ToolbarManager's Run/Stop toggle and Save
        action) instead of each Script tab needing its own Run/Save
        buttons."""
        from .dialogs import ScriptEditorWidget
        widget = self.central_tabs.currentWidget()
        return widget if isinstance(widget, ScriptEditorWidget) else None

    def _on_current_tab_changed(self, index):
        widget = self.central_tabs.widget(index)
        doc = self._diagram_for_view(widget)
        if doc is not None:
            self._active_diagram = doc
            doc.scene_manager._update_breadcrumb()
        # else: a Script/Simulation tab is focused -- _active_diagram
        # stays whatever it was, so Save/Run/etc. still have a sensible
        # target, and the breadcrumb keeps reflecting that diagram.
        self.refresh_title()

    def _on_tab_close_requested(self, index):
        widget = self.central_tabs.widget(index)

        doc = self._diagram_for_view(widget)
        if doc is not None:
            if not doc.scene_manager.confirm_discard_changes():
                return
            self._remove_diagram_document(doc)
            return

        if hasattr(widget, "confirm_discard") and not widget.confirm_discard():
            return

        self.central_tabs.removeTab(index)
        was_script = widget in self._script_tabs.values()
        for path, w in list(self._script_tabs.items()):
            if w is widget:
                del self._script_tabs[path]
        for key, w in list(self._simulation_tabs.items()):
            if w is widget:
                del self._simulation_tabs[key]
        if self._last_sim_tab_widget is widget:
            self._last_sim_tab_widget = None
        widget.deleteLater()
        if was_script:
            self._update_run_save_enabled()

    # --- Menu bar ---------------------------------------------------------

    def _create_menu_bar(self):
        """Build File/Edit/View/Simulation/Help menus from the toolbar's QActions."""
        tm = self.toolbar_manager
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(tm.action_open_project)
        file_menu.addSeparator()
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
        edit_menu.addAction(tm.action_duplicate)
        edit_menu.addAction(tm.action_delete)
        edit_menu.addSeparator()
        edit_menu.addAction(tm.action_rename)
        edit_menu.addSeparator()
        edit_menu.addAction(tm.action_select_all)

        view_menu = menu_bar.addMenu("&View")
        view_menu.addAction(tm.action_zoom_in)
        view_menu.addAction(tm.action_zoom_out)
        view_menu.addAction(tm.action_zoom_fit)
        view_menu.addSeparator()
        view_menu.addAction(tm.action_toggle_lib)
        view_menu.addAction(tm.action_toggle_console)
        view_menu.addAction(tm.action_toggle_globals)
        view_menu.addAction(tm.action_up)

        sim_menu = menu_bar.addMenu("&Simulation")
        sim_menu.addAction(tm.action_sim_settings)
        sim_menu.addAction(tm.action_run)
        sim_menu.addAction(tm.action_inspector)

        tools_menu = menu_bar.addMenu("&Tools")
        tools_menu.addAction(tm.action_save_subgraph)
        tools_menu.addSeparator()
        tools_menu.addAction(tm.action_clear_globals)

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
        """Reflect the active diagram's file name and unsaved-changes
        state in the title bar (the trailing [*] is Qt's own
        modified-document marker, rendered as e.g. a dot in the close
        button on macOS)."""
        sm = self.scene_manager
        current_path = sm.current_file_path if sm else None
        name = os.path.basename(current_path) if current_path else "Untitled"

        project_manager = getattr(self, "project_manager", None)
        project_name = project_manager.project_name if project_manager and project_manager.project_root else None

        if project_name:
            self.setWindowTitle(f"{UIConfig.WINDOW_TITLE} - {project_name} - {name}[*]")
        else:
            self.setWindowTitle(f"{UIConfig.WINDOW_TITLE} - {name}[*]")
        self.setWindowModified(sm.is_modified if sm else False)

    def closeEvent(self, event):
        if not self.confirm_discard_all_diagrams():
            event.ignore()
            return

        for widget in list(self._script_tabs.values()):
            if not widget.confirm_discard():
                event.ignore()
                return

        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("windowState", self.saveState())
        super().closeEvent(event)

    def show_help(self):
        """Show help dialog."""
        dialog = HelpDialog(self)
        dialog.exec()

    def show_status(self, message, timeout_ms=5000):
        """Show a brief, non-blocking confirmation at the right side of the
        status bar (next to the depth-level breadcrumb) -- for routine
        outcomes (saved, loaded, exported, ...) that don't need an
        explicit OK click, unlike QMessageBox.information(). Pass
        timeout_ms=0 to leave it showing until the next status message."""
        self.status_label.setText(message)
        if timeout_ms:
            QTimer.singleShot(timeout_ms, lambda: self._clear_status_if_unchanged(message))

    def _clear_status_if_unchanged(self, message):
        # Guards against a stale timer (from an older message) clearing a
        # newer one that was shown in the meantime.
        if self.status_label.text() == message:
            self.status_label.setText("")

    def open_script_tab(self, file_path, make_widget):
        """Switch to file_path's tab if it's already open (keeping any
        in-progress unsaved edits rather than reloading from disk);
        otherwise call make_widget() to build it and add a new tab. This
        is how multiple Scripts stay open side by side -- opening one
        never affects any other."""
        widget = self._script_tabs.get(file_path)
        if widget is not None:
            self.central_tabs.setCurrentWidget(widget)
            return

        widget = make_widget()
        self._script_tabs[file_path] = widget
        index = self.central_tabs.addTab(widget, os.path.basename(file_path))
        self.central_tabs.setCurrentIndex(index)
        self._update_run_save_enabled()

    def update_script_tab_title(self, file_path, modified):
        """Reflect unsaved edits in the tab label (e.g. 'demo.py •'),
        mirroring how most editors mark a dirty document -- connected to
        ScriptEditorWidget's document modificationChanged signal."""
        widget = self._script_tabs.get(file_path)
        if widget is None:
            return
        index = self.central_tabs.indexOf(widget)
        if index == -1:
            return
        base = os.path.basename(file_path)
        self.central_tabs.setTabText(index, f"{base} •" if modified else base)

    def open_simulation_tab(self, result):
        """Open a new tab with this simulation run's results (Scope data +
        CSV export) -- a fresh tab per run, so multiple runs' results can
        stay open and be compared side by side instead of only the most
        recent being reachable."""
        from .widgets import SimulationResultWidget

        self._simulation_tab_counter += 1
        title = f"Simulation {self._simulation_tab_counter}"
        widget = SimulationResultWidget(result, title=title)
        self._simulation_tabs[id(widget)] = widget
        self._last_sim_tab_widget = widget

        index = self.central_tabs.addTab(widget, title)
        self.central_tabs.setCurrentIndex(index)

    def focus_or_open_simulation_tab(self, result):
        """Data Inspector: bring the most recent run's results tab to
        front if it's still open, otherwise reopen it -- doesn't pile up a
        duplicate tab for the same run every click."""
        widget = self._last_sim_tab_widget
        if widget is not None:
            index = self.central_tabs.indexOf(widget)
            if index != -1:
                self.central_tabs.setCurrentIndex(index)
                return
        self.open_simulation_tab(result)

    def enter_subsystem(self, subsystem_ui_block):
        """Delegate to the active diagram's scene_manager to enter a subsystem."""
        self.scene_manager.enter_subsystem(subsystem_ui_block)
