from PySide6.QtWidgets import (QDialog, QVBoxLayout, QWidget, QLabel, QLineEdit,
                               QTextEdit, QTabWidget, QDialogButtonBox)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QTextDocument

# (toolbar_manager attribute name, what it does and how it works). Grouped
# to match the menu bar's own File/Edit/Simulation/... layout. Kept here
# rather than alongside the actions themselves (toolbar_manager.py) since
# a QAction has no "long description" field of its own -- this is the one
# place that needs one, and staying separate means toolbar_manager doesn't
# have to carry help-text concerns that are unrelated to building the menu.
TOOLBAR_HELP = [
    ("File", [
        ("action_open_project", "Open (or switch to) a Project Folder -- any folder "
                                 "anywhere on disk. Everything the app saves (Diagrams, "
                                 "SubGraphs, Scripts) lives directly in it, no imposed "
                                 "subfolders, shown together in the User Space tab. No "
                                 "project is opened automatically -- BlocSimPy starts "
                                 "with none open every launch, and this is the only way "
                                 "in. Switching asks to save unsaved changes in every "
                                 "open diagram, then closes them all -- a different "
                                 "project's diagrams aren't part of this one."),
        ("action_new", "Open a fresh, empty diagram in its own new tab -- your other "
                        "open diagrams are untouched."),
        ("action_load", "Open a previously saved diagram (a .json file) from disk, "
                         "in its own new tab (or switching to it if it's already "
                         "open) -- your other open diagrams are untouched. Starts "
                         "browsing from the current project folder. Menu-only -- for "
                         "a diagram already in the current project, double-clicking "
                         "it in User Space &rarr; Diagrams is quicker."),
        ("action_save", "Save the active diagram tab. Writes to the file it was "
                         "opened from (or last saved to); if it doesn't have one "
                         "yet, this behaves like Save As."),
        ("action_save_as", "Save the active diagram tab to a new file, and make that "
                            "file its file going forward. Starts browsing from the "
                            "current project folder."),
        ("action_quit", "Close BlocSimPy. If any open diagram or Script has unsaved "
                         "changes, you'll be asked whether to save them first."),
    ]),
    ("Edit", [
        ("action_undo", "Undo the most recent change -- adding, moving, or deleting "
                         "a block/wire/annotation, editing a parameter, and so on."),
        ("action_redo", "Redo a change that was just undone."),
        ("action_cut", "Remove the selected blocks from the diagram and copy them "
                        "to the clipboard."),
        ("action_copy", "Copy the selected blocks to the clipboard without removing "
                         "them."),
        ("action_paste", "Paste the clipboard's blocks into the diagram, offset "
                          "slightly so they land next to the originals -- pasting "
                          "again offsets further each time, so repeats don't stack."),
        ("action_duplicate", "Make an offset copy of the selected block(s) in place, "
                              "without touching the clipboard."),
        ("action_delete", "Delete the selected blocks, wires, or annotations."),
        ("action_rename", "Rename the single selected block (its display label, via "
                           "the 'BlockName' parameter)."),
        ("action_select_all", "Select every block, wire, and annotation on the "
                               "current canvas."),
    ]),
    ("View", [
        ("action_zoom_in", "Zoom in on the canvas, centered on the current view."),
        ("action_zoom_out", "Zoom out on the canvas, centered on the current view."),
        ("action_zoom_fit", "Zoom and pan so every block on the canvas is visible "
                             "at once. You can also zoom with the mouse wheel "
                             "(anchored under the cursor) and pan by dragging with "
                             "the middle mouse button."),
        ("action_toggle_lib", "Show or hide the Library dock on the left -- the "
                               "block palette and User Space (the current project "
                               "folder's Diagrams, SubGraphs, and Scripts)."),
    ]),
    ("Simulation", [
        ("action_sim_settings", "Choose the simulation's duration, time step, and "
                                 "solver (fixed-step Euler, or 4th-order Runge-Kutta "
                                 "for better accuracy at the same step size)."),
        ("action_run", "Run the simulation. A pre-flight check first surfaces "
                        "structural problems -- algebraic loops (blocking) and "
                        "unconnected inputs (a warning, since they read as 0.0) -- "
                        "before anything executes. The run itself happens on a "
                        "background thread with a cancellable progress bar, so the "
                        "window stays responsive even for long simulations. Each "
                        "successful run opens its results in a new 'Simulation N' "
                        "tab, so re-running with different parameters lets you flip "
                        "between runs instead of only ever seeing the latest."),
        ("action_inspector", "Bring the most recent run's results tab to the front, "
                              "reopening it if it was closed."),
    ]),
    ("Navigation", [
        ("action_up", "Step back out of the SubGraph you're currently editing, "
                       "returning to its parent diagram."),
    ]),
    ("Tools", [
        ("action_save_subgraph", "Save the selected SubGraph block as a named, "
                                  "reusable component in User Space, so it can be "
                                  "dragged into other diagrams later."),
    ]),
    ("Help", [
        ("action_help", "Open this Help window."),
        ("action_about", "Show BlocSimPy's version and license information."),
    ]),
]


class HelpDialog(QDialog):
    """Help dialog: a reference for the toolbar/menu actions, and a
    searchable reference for every block kind."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Help - BlocSimPy")
        self.resize(900, 700)

        # Load block descriptions dynamically from block classes
        self.block_descriptions = self._load_block_descriptions()

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("BlocSimPy Help")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_toolbar_tab(), "Toolbar && Menus")
        tabs.addTab(self._build_blocks_tab(), "Blocks")
        layout.addWidget(tabs)

        # Close button
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)

    # --- Toolbar & Menus tab ---

    def _build_toolbar_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)

        text = QTextEdit()
        text.setReadOnly(True)
        self._populate_toolbar_reference(text)
        layout.addWidget(text)
        return widget

    def _populate_toolbar_reference(self, text_edit):
        """Every toolbar/menu action's icon (pulled live from the actual
        QAction, via an embedded document resource, so it's always the same
        icon the user sees in the toolbar), shortcut, and description."""
        doc = text_edit.document()
        toolbar_manager = getattr(self.main_window, "toolbar_manager", None)

        html = (
            "<html><body style='font-family: \"Segoe UI\", Arial, sans-serif; "
            "background-color: #ffffff; color: #1d1d1f;'>"
            "<p style='color: #3a3a3c;'>Drag blocks from the Library onto the canvas, "
            "connect output ports to input ports, double-click a block to edit its "
            "parameters, then use <b>Simulation &rarr; Run</b>. Double-click a "
            "SubGraph to step inside it; double-click a Scope after running to see "
            "its data. Everything below is also reachable from the menu bar, with "
            "the same keyboard shortcuts.</p>"
            "<p style='color: #3a3a3c;'>The central area is a proper multi-page "
            "workspace, like a code editor's tab bar: every Diagram, Script, and "
            "simulation run gets its own tab, and they all stay open side by side "
            "instead of one replacing another. Open as many diagrams as you like at "
            "once (<b>File &rarr; New</b> or <b>Open...</b>, or double-click one in "
            "User Space &rarr; Diagrams) -- toolbar actions like Save, Undo, and Run "
            "always act on whichever diagram tab is currently active. Same for "
            "Scripts: open several at once, each keeping its own unsaved-edits state, "
            "marked with a <b>&bull;</b> on its tab. Every successful <b>Run</b> adds "
            "a new <b>Simulation N</b> tab so you can compare multiple runs' results "
            "side by side. Click a tab's <b>&times;</b> to close it (Diagrams and "
            "Scripts confirm first if unsaved) -- closing the last open diagram "
            "immediately opens a fresh blank one, so there's always at least one.</p>"
            "<p style='color: #3a3a3c;'>Everything BlocSimPy saves lives directly in "
            "the current <b>Project Folder</b> (<b>File &rarr; Open Project "
            "Folder...</b>) -- any folder anywhere on disk, no imposed subfolders. "
            "The <b>User Space</b> tab next to Library groups that one folder's "
            "contents into <b>Diagrams</b> (double-click to open), <b>SubGraphs</b>, "
            "and <b>Scripts</b>. Right-click the Scripts group for <b>New Script</b>, "
            "or double-click an existing one to open its Script Editor tab -- Save "
            "always writes straight back to that file, and Run executes it with "
            "access to <code>set_param()</code>, <code>run_simulation()</code>, "
            "<code>get_blocks()</code>, and <code>get_block_info()</code> against "
            "the current diagram.</p>"
        )

        if toolbar_manager is None:
            html += (
                "<p style='color: #6e6e73;'>Toolbar reference unavailable "
                "(no active window).</p></body></html>"
            )
            text_edit.setHtml(html)
            return

        for category, items in TOOLBAR_HELP:
            html += (
                f"<h2 style='color: #007aff; border-bottom: 1px solid #e5e5ea; "
                f"padding-bottom: 6px; margin-top: 26px;'>{category}</h2>"
            )
            for attr_name, description in items:
                action = getattr(toolbar_manager, attr_name, None)
                if action is None:
                    continue

                icon_html = ""
                pixmap = action.icon().pixmap(20, 20)
                if not pixmap.isNull():
                    resource_url = QUrl(f"icon://{attr_name}")
                    doc.addResource(QTextDocument.ImageResource, resource_url, pixmap)
                    icon_html = (
                        f"<img src='{resource_url.toString()}' width='18' height='18' "
                        f"style='vertical-align: middle; margin-right: 10px;'>"
                    )

                shortcuts = [s.toString() for s in action.shortcuts() if not s.isEmpty()]
                shortcut_html = ""
                if shortcuts:
                    shortcut_html = (
                        " <code style='background-color: #e5e5ea; color: #3a3a3c; "
                        "padding: 2px 6px; border-radius: 4px; font-size: 11px;'>"
                        + " / ".join(shortcuts) + "</code>"
                    )

                html += f"""
                <div style='margin-bottom: 10px; padding: 10px 14px; background-color: #f6f6f7; border-left: 3px solid #007aff; border-radius: 0 8px 8px 0;'>
                    <span style='font-size: 14px; font-weight: bold; color: #1d1d1f;'>{icon_html}{action.text()}</span>{shortcut_html}
                    <p style='margin: 6px 0 0 0; color: #3a3a3c;'>{description}</p>
                </div>
                """

        html += "</body></html>"
        text_edit.setHtml(html)

    # --- Blocks tab ---

    def _build_blocks_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)

        search_label = QLabel("Search Blocks:")
        search_label_font = search_label.font()
        search_label_font.setBold(True)
        search_label.setFont(search_label_font)
        layout.addWidget(search_label)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Type block name or keyword to filter...")
        self.search_bar.textChanged.connect(self._filter_blocks)
        layout.addWidget(self.search_bar)

        self.reference_text = QTextEdit()
        self.reference_text.setReadOnly(True)
        layout.addWidget(self.reference_text)

        self._update_reference("")
        return widget

    def _load_block_descriptions(self):
        """Load block descriptions from each block's BLOCK_INFO attribute."""
        # Use absolute import to avoid issues
        from engine.blocks import BLOCK_REGISTRY

        descriptions = {}
        for block_name, block_class in BLOCK_REGISTRY.items():
            if hasattr(block_class, 'BLOCK_INFO'):
                descriptions[block_name] = block_class.BLOCK_INFO
            else:
                # Default info if block doesn't have BLOCK_INFO yet
                descriptions[block_name] = {
                    "description": f"{block_name} block",
                    "parameters": "See block properties",
                    "formula": "Not documented yet",
                    "usage": "Documentation pending"
                }
        return descriptions

    def _filter_blocks(self, search_text):
        """Filter blocks based on search text."""
        self._update_reference(search_text.lower())

    def _update_reference(self, search_text):
        """Update the reference text with filtered blocks, grouped by category."""
        html_content = (
            "<html><body style='font-family: \"Segoe UI\", Arial, sans-serif; "
            "background-color: #ffffff; color: #1d1d1f;'>"
        )

        # 1. Organize blocks by category
        categories = {}
        for block_name, info in self.block_descriptions.items():
            cat = info.get('category', 'General')

            description = info.get('description', info.get('doc', 'Generic block'))
            params = info.get('parameters', 'N/A')
            formula = info.get('formula', 'N/A')
            usage = info.get('usage', 'N/A')

            # Filter based on search
            if search_text:
                searchable = f"{block_name} {description} {usage} {cat}".lower()
                if search_text not in searchable:
                    continue

            if cat not in categories:
                categories[cat] = []

            categories[cat].append({
                'name': block_name,
                'description': description,
                'parameters': params,
                'formula': formula,
                'usage': usage
            })

        # 2. Sort categories alphabetically
        sorted_category_names = sorted(categories.keys())

        matched_total = 0
        for cat_name in sorted_category_names:
            blocks = sorted(categories[cat_name], key=lambda x: x['name'])
            if not blocks:
                continue

            html_content += (
                f"<h2 style='color: #007aff; border-bottom: 1px solid #e5e5ea; "
                f"padding-bottom: 6px; margin-top: 30px;'>{cat_name}</h2>"
            )

            for block in blocks:
                matched_total += 1
                html_content += f"""
                <div style='margin-bottom: 16px; padding: 12px 14px; background-color: #f6f6f7; border-left: 3px solid #007aff; border-radius: 0 8px 8px 0;'>
                    <h3 style='margin: 0 0 8px 0; color: #1d1d1f;'>{block['name']}</h3>
                    <p style='margin: 5px 0; color: #3a3a3c;'><b style='color: #1d1d1f;'>Description:</b> {block['description']}</p>
                    <p style='margin: 5px 0; color: #3a3a3c;'><b style='color: #1d1d1f;'>Parameters:</b> {block['parameters']}</p>
                    <p style='margin: 5px 0; color: #3a3a3c;'><b style='color: #1d1d1f;'>Formula:</b> <code style='background-color: #e5e5ea; color: #1d1d1f; padding: 2px 6px; border-radius: 4px;'>{block['formula']}</code></p>
                    <p style='margin: 5px 0; color: #3a3a3c;'><b style='color: #1d1d1f;'>Usage:</b> <i>{block['usage']}</i></p>
                </div>
                """

        if matched_total == 0:
            html_content += "<p style='text-align: center; color: #6e6e73; margin-top: 50px;'>No blocks found matching your search.</p>"

        html_content += "</body></html>"
        self.reference_text.setHtml(html_content)
