import re
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QWidget, QLabel, QLineEdit,
                               QTextEdit, QTabWidget, QDialogButtonBox)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QTextDocument

# Shared CSS for every Help tab's <body> -- word-wrap/overflow-wrap belt-
# and-braces so long unbroken tokens (a code signature, a path) still wrap
# inside the pane instead of forcing a horizontal scrollbar that clips
# text at the right edge (see _configure_reference_text_edit()).
_BODY_STYLE = (
    "font-family: \"Segoe UI\", Arial, sans-serif; background-color: #ffffff; "
    "color: #1d1d1f; word-wrap: break-word; overflow-wrap: break-word;"
)


class _ReferenceTextEdit(QTextEdit):
    """Read-only HTML reference pane used for all three Help tabs.

    setLineWrapMode(WidgetWidth) is supposed to keep the document's wrap
    width in sync with the viewport automatically, but that sync can lag
    behind (e.g. across a live window-resize drag, or after the framed
    '<div>' cards below add their own padding/border to the layout) and
    leave stale, too-wide line breaks in place -- text then runs past the
    pane's right edge, with the disabled scrollbar (see below) hiding the
    rest instead of a new line ever showing it. Pinning the document's text
    width explicitly on every resize removes that ambiguity outright,
    rather than trusting the automatic sync to always have already run."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.document().setTextWidth(self.viewport().width())


def _configure_reference_text_edit(text_edit):
    """Common setup for every read-only HTML reference pane in this dialog.

    Forcing the horizontal scrollbar off (rather than leaving it at Qt's
    default 'AsNeeded') makes WidgetWidth line-wrapping unconditional: the
    document is always laid out at exactly the viewport's width, so text
    reflows onto a new line instead of a scrollbar appearing and the
    rightmost words being clipped out of view -- which is what "cuts off"
    words at the pane's right edge whenever content is wide enough to
    trigger that scrollbar (e.g. after shrinking the Help window)."""
    text_edit.setLineWrapMode(QTextEdit.WidgetWidth)
    text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)


def _card(inner_html, margin_bottom=10):
    """One 'framed card' row: a thin accent bar on the left plus a tinted
    content cell, both spanning the card's full height however many lines
    `inner_html` wraps to.

    Built as a <table> rather than the more obvious `<div style=
    'background-color:...'><p>...</p></div>` -- Qt's rich-text engine does
    NOT paint a <div>'s background-color behind nested block-level children
    like <p> or a second <div>; only the first line (up to the first block
    break) actually gets shaded, and every line after that renders on a
    plain white background below the box instead of inside it. That's what
    made the cards look like badly-placed/truncated frames: the box was
    only ever as tall as its title line, no matter how much description
    text followed. A <table> cell's background reliably covers its own
    full cell content instead, multi-line or not, so use `<br>`/nested
    non-backgrounded `<div>`s for line breaks *inside* `inner_html`, not
    another backgrounded block."""
    return (
        f"<table width='100%' style='border-collapse: collapse; margin-bottom: {margin_bottom}px;'>"
        "<tr>"
        "<td width='4' style='background-color: #007aff;'></td>"
        f"<td style='background-color: #f6f6f7; padding: 10px 14px;'>{inner_html}</td>"
        "</tr></table>"
    )

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
        ("action_save", "Save the active tab -- a diagram, or a Script if one is "
                         "focused (there's no separate Save button on a Script tab "
                         "anymore; this one handles both). For a diagram, writes to "
                         "the file it was opened from (or last saved to); if it "
                         "doesn't have one yet, this behaves like Save As."),
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
        ("action_toggle_console", "Show or hide the Console dock -- a single "
                                   "interactive command prompt, hidden by default. "
                                   "It runs in the exact same execution environment "
                                   "as every Script run, so a variable or "
                                   "function you define in one is visible in the "
                                   "other, for the rest of the session. Every Script "
                                   "run also logs its output here, so the Console "
                                   "doubles as one combined log of everything that's "
                                   "run, whether or not it was open at the time. See "
                                   "the Scripting API tab."),
        ("action_toggle_globals", "Show or hide the Global Variables dock -- a "
                                   "live, read-only table of every variable a "
                                   "Script's Run or the Console has defined this "
                                   "session, with a search box to filter it by name "
                                   "or value. Built-in API functions like "
                                   "add_block/sim/np aren't listed -- just what "
                                   "you've defined. Refreshes itself automatically "
                                   "about twice a second while visible -- no manual "
                                   "refresh needed -- and has a Clear All button. "
                                   "See the Scripting API tab."),
    ]),
    ("Simulation", [
        ("action_sim_settings", "Choose the simulation's duration, time step, and "
                                 "solver (fixed-step Euler, or 4th-order Runge-Kutta "
                                 "for better accuracy at the same step size)."),
        ("action_run", "Run/Stop toggle -- what it runs depends on which kind of "
                        "tab is focused: a Script tab runs that Script (same as the "
                        "old Run Script button, now shared here instead of living on "
                        "the Script tab itself); anything else runs the active "
                        "diagram's simulation. While running, the icon becomes a "
                        "Stop square and clicking it again cancels -- a simulation "
                        "cancels cleanly at its next progress checkpoint; a Script "
                        "can only be interrupted while it's inside a sim() call, "
                        "since arbitrary Python has no safe point to interrupt "
                        "mid-statement. A small inline progress bar appears next to "
                        "the button while running (real 0-100% for a simulation, "
                        "indeterminate for a Script, since there's no fine-grained "
                        "progress for arbitrary code) -- no separate popup dialog. "
                        "A diagram run first does a pre-flight check for structural "
                        "problems -- algebraic loops (blocking) and unconnected "
                        "inputs (a warning, since they read as 0.0) -- before "
                        "anything executes, and each successful run opens its "
                        "results in a new 'Simulation N' tab, so re-running with "
                        "different parameters lets you flip between runs instead of "
                        "only ever seeing the latest. A Script's output (print() "
                        "lines, errors) goes to the Console dock, revealing it if "
                        "hidden."),
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
        ("action_clear_globals", "Wipe every variable a Script run or the "
                                  "Console has defined this session -- asks for "
                                  "confirmation first, since it can't be undone. The "
                                  "built-in API (add_block, sim, np, ...) is "
                                  "unaffected; it's always available again on the "
                                  "very next run. Also reachable as Clear All in the "
                                  "Global Variables dock (View &rarr; Toggle Global "
                                  "Variables)."),
    ]),
    ("Help", [
        ("action_help", "Open this Help window."),
        ("action_about", "Show BlocSimPy's version and license information."),
    ]),
]


# (signature, description) for every function the Script Editor console
# exposes to script code (see gui/managers/script_manager.py), grouped to
# match DEFAULT_SCRIPT_TEMPLATE's own grouping in gui/library.py. Kept here,
# as static reference text, rather than introspected from ScriptManager --
# unlike the toolbar actions (which carry their own text/icon/shortcut to
# pull from live), the script functions are plain closures with nothing to
# introspect a description out of.
SCRIPTING_HELP = [
    ("Diagram File/Tab", [
        ("open_diagram(file_path)",
         "Open <code>file_path</code> in its own Diagram tab (or switch to "
         "it if already open) and make it the active target for every "
         "command below -- same as double-clicking it in User Space, or "
         "<b>File &rarr; Open...</b>, but scriptable. A bare filename (no "
         "directory) is resolved against the current Project Folder if one "
         "is open. Returns the diagram's name, or <code>None</code> on "
         "failure. Needs a file that already exists -- see "
         "<code>new_diagram()</code> to start one from scratch."),
        ("new_diagram()",
         "Create a fresh, empty diagram in its own new tab and make it the "
         "active target for every command below -- same as <b>File &rarr; "
         "New</b>, but scriptable. Unlike <code>open_diagram()</code>, "
         "there's no file to point at yet; save one with "
         "<code>save_diagram()</code> once it's built. Returns the new "
         "diagram's name (its 'Untitled'/'Untitled N' tab title)."),
        ("select_diagram(name)",
         "Switch the active diagram to an already-open tab, matched by "
         "name (see <code>list_diagrams()</code>) -- for jumping between "
         "diagrams already open this session without touching disk. Every "
         "command below then targets whichever one this selects. Returns "
         "<code>True</code>/<code>False</code>."),
        ("current_diagram()",
         "The active diagram's name -- what <code>add_block()</code>, "
         "<code>sim()</code>, etc. currently target. <code>None</code> if "
         "no diagram is open."),
        ("list_diagrams()",
         "Names of every open diagram tab, in tab order."),
        ("save_diagram(file_path=None)",
         "Save the active diagram (see <code>current_diagram()</code>) to "
         "<code>file_path</code>, or -- if omitted -- to whatever file "
         "it's already bound to (like the toolbar's Save). Unlike the "
         "GUI's Save As, this never opens a file picker; pass an explicit "
         "<code>file_path</code> for a scripted \"save as\". A bare "
         "filename (no directory) is resolved against the current Project "
         "Folder, same as <code>open_diagram()</code>. Returns the path "
         "saved to, or <code>None</code> on failure."),
    ]),
    ("Diagram", [
        ("add_block(block_type, name=None, position=None)",
         "Add a new block of type <code>block_type</code> (see "
         "<code>get_block_types()</code> for valid values) to whatever "
         "level is currently active -- Top Level, or inside a SubGraph "
         "after <code>enter_subgraph()</code>. <code>name</code> becomes "
         "its BlockName and must not already be in use at that level; if "
         "omitted, an unused name like <code>'Gain1'</code> is generated. "
         "<code>position</code> is an optional <code>(x, y)</code> tuple. "
         "Returns the block's final name, or <code>None</code> on "
         "failure."),
        ("delete_block(block_name)",
         "Delete a block by name, along with any wires attached to it, at "
         "the current level. Returns <code>True</code>/<code>False</code>."),
        ("add_line(src_block, dst_block, src_port=None, dst_port=None)",
         "Connect <code>src_block</code>'s output to <code>dst_block</code>'s "
         "input, both addressed by BlockName, at the current level. "
         "<code>src_port</code>/<code>dst_port</code> can be left out if "
         "that block has exactly one output/input. Rewires "
         "<code>dst_port</code> if it was already connected, same as "
         "dragging a new wire onto it in the canvas. Returns "
         "<code>True</code>/<code>False</code>."),
        ("delete_line(dst_block, dst_port=None)",
         "Disconnect whatever feeds <code>dst_block</code>'s input port "
         "(named by <code>dst_port</code>, or its sole input if omitted). "
         "Returns <code>True</code>/<code>False</code>."),
        ("set_param(block_name, param_name, value)",
         "Set a parameter on a block, at the current level. Only an "
         "EXISTING parameter can be set -- this respects each block's own "
         "defined interface instead of silently adding new params."),
        ("get_param(block_name, param_name)",
         "Read a parameter's current value, at the current level. Read "
         "counterpart to <code>set_param</code>."),
        ("find_system(block_type=None, name_contains=None)",
         "List block names at the current level, optionally filtered by "
         "class name (<code>block_type</code>, e.g. <code>'Gain'</code>) "
         "and/or a substring of their BlockName "
         "(<code>name_contains</code>)."),
        ("get_blocks()",
         "List every block name at the current level."),
        ("get_block_info(block_name)",
         "<code>{param_name: variable_name}</code> for every parameter on "
         "this block currently bound to a global variable (see "
         "<code>var()</code> below) -- same rule for every block type, "
         "including SubGraph. Empty dict if none are bound."),
        ("get_block_types()",
         "Every block type string usable with <code>add_block()</code> / "
         "<code>find_system()</code>, e.g. <code>'Gain'</code>, "
         "<code>'Scope'</code>, <code>'TransferFunction'</code>."),
    ]),
    ("SubGraph", [
        ("enter_subgraph(block_name)",
         "Step inside a SubGraph block (by name, at the current level) -- "
         "like double-clicking it in the canvas. Every command above then "
         "acts on ITS internal diagram: <code>add_block('InputPort', "
         "...)</code> / <code>add_block('OutputPort', ...)</code> plus "
         "<code>set_param(..., 'PortName', ...)</code> build its exposed "
         "interface, exactly like building the top-level diagram. Pair "
         "with <code>exit_subgraph()</code>. Returns "
         "<code>True</code>/<code>False</code>."),
        ("exit_subgraph()",
         "Step back out of the SubGraph currently entered (one level), "
         "syncing its exposed ports from whatever InputPort/OutputPort "
         "blocks ended up inside it. Following commands act on the parent "
         "level again. Returns <code>True</code>/<code>False</code>."),
        ("go_to_top()",
         "Navigate all the way back out to the Top Level diagram, out of "
         "every nested SubGraph at once."),
    ]),
    ("Simulation", [
        ("sim(duration=None, dt=None, solver=None)",
         "Synchronous run: blocks until the simulation "
         "finishes and returns its data directly, e.g. "
         "<code>out = sim(); y = out['scopes']['Scope1']['data']</code>. "
         "Unlike <code>run_simulation()</code>, this runs on the calling "
         "thread (no progress dialog) and hands back "
         "<code>{'time': ndarray, 'scopes': {name: {'time': ..., 'data': "
         "...}}}</code>. <code>duration</code>/<code>dt</code>/"
         "<code>solver</code> default to the current Simulation Settings "
         "if omitted."),
        ("get_signal(scope_name)",
         "<code>(time, data)</code> arrays for a Scope block from the most "
         "recent <code>sim()</code>/<code>run_simulation()</code> run, "
         "without re-running."),
        ("run_simulation()",
         "Trigger the same async Run flow as the toolbar's Run button "
         "(progress dialog, opens a new Simulation tab). Prefer "
         "<code>sim()</code> when you want the results back in the script "
         "itself."),
    ]),
    ("Workspace &amp; Utilities", [
        ("var(name)",
         "Bind a block parameter to the global variable <code>name</code> "
         "-- a plain top-level name a Script/the Console has defined, e.g. "
         "<code>Kp = 2.5</code> -- instead of a literal value, e.g. "
         "<code>set_param('G', 'Gain', var('Kp'))</code>. From the GUI, "
         "just type the variable's name directly into the block's own "
         "parameter field -- no picker: anything that isn't a valid literal "
         "for that field but reads as a plain name is treated as a binding, "
         "declared or not (an undeclared one is caught by Run's pre-flight "
         "check, not silently ignored). Replaces the old "
         "<code>\"$VarName\"</code>-prefixed-string convention -- see "
         "<code>get_block_info()</code> above and 'Inspecting &amp; "
         "Clearing Globals' below. Every top-level name a Script/the "
         "Console defines already IS a global variable -- there's no "
         "separate store to explicitly declare one into."),
        ("np",
         "The <code>numpy</code> module, for vectorized math on the arrays "
         "<code>sim()</code>/<code>get_signal()</code> return."),
        ("print(text)",
         "Write a line to the Console dock's log -- a Script run shows "
         "there (not in its own separate pane), automatically revealing "
         "the Console if it was hidden."),
        ("help / help()",
         "Open this Help window -- same as the toolbar's Help button. "
         "Works typed bare (<code>help</code>) or called "
         "(<code>help()</code>/<code>help(x)</code>, any argument "
         "ignored). A replacement for Python's own built-in "
         "<code>help()</code>, which would otherwise freeze the app: "
         "there's no real terminal here for its interactive prompt (bare "
         "<code>help()</code>) or output pager to read/write through. "
         "<code>input()</code> is blocked the same way (nothing to read a "
         "line from), and <code>exit()</code>/<code>quit()</code> are "
         "blocked too -- the real ones would close the whole app, not "
         "just the running Script."),
    ]),
    ("Inspecting &amp; Clearing Globals", [
        ("View &rarr; Toggle Global Variables",
         "Open the <b>Global Variables</b> dock: a live table of every "
         "variable, import, or function currently defined in the shared "
         "environment -- every plain top-level name a Script/the Console "
         "has defined -- with its own Clear All button. Refreshes "
         "automatically (about twice a second) while the dock is visible, "
         "so it never needs a manual click to catch up with a Script run, "
         "a Console command, or a param bound elsewhere. There's no "
         "script function for this -- it's a GUI-only dock, since it "
         "needs to show live state rather than return it to a running "
         "script."),
        ("Tools &rarr; Clear Global Variables...",
         "Wipe every name currently in the shared environment after "
         "confirming -- for starting a clean session without restarting "
         "the app. The built-in API (<code>add_block</code>, "
         "<code>sim</code>, <code>np</code>, ...) is unaffected; it's "
         "rebuilt fresh on the very next run/command regardless. Same "
         "action as the Global Variables dock's Clear All button. Any "
         "block param currently bound via <code>var(name)</code>/a typed "
         "variable name loses its value too -- Run is blocked with a "
         "pre-flight error listing every now-undeclared variable until "
         "it's redeclared (typing it again in a param field, a plain "
         "<code>name = value</code> in the Console, or re-running the "
         "Script that originally set it)."),
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
        tabs.addTab(self._build_scripting_tab(), "Scripting API")
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

        text = _ReferenceTextEdit()
        text.setReadOnly(True)
        _configure_reference_text_edit(text)
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
            f"<html><body style='{_BODY_STYLE}'>"
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
            "just leaves the workspace empty, same as at launch, rather than "
            "handing you a blank one you didn't ask for.</p>"
            "<p style='color: #3a3a3c;'>Everything BlocSimPy saves lives directly in "
            "the current <b>Project Folder</b> (<b>File &rarr; Open Project "
            "Folder...</b>) -- any folder anywhere on disk, no imposed subfolders. "
            "The <b>User Space</b> tab next to Library groups that one folder's "
            "contents into <b>Diagrams</b> (double-click to open), <b>SubGraphs</b>, "
            "and <b>Scripts</b>. Right-click the Scripts group for <b>New Script</b>, "
            "or double-click an existing one to open its Script Editor tab -- dark, "
            "IDE-style syntax highlighting for keywords/strings/comments/numbers "
            "and BlocSimPy's own scripting functions. The "
            "same toolbar <b>Save</b> (Ctrl+S) and <b>Run</b>/Stop (F5) buttons a "
            "diagram uses write straight back to that file and execute it, no "
            "separate buttons on the tab itself, with its output sent to the "
            "<b>Console</b> dock (<b>View &rarr; Toggle Console</b>), which "
            "auto-reveals if hidden. See the <b>Scripting API</b> tab for the full "
            "command reference.</p>"
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

                inner = (
                    f"<span style='font-size: 14px; font-weight: bold; color: #1d1d1f;'>"
                    f"{icon_html}{action.text()}</span>{shortcut_html}"
                    f"<div style='margin-top: 6px; color: #3a3a3c;'>{description}</div>"
                )
                html += _card(inner)

        html += "</body></html>"
        text_edit.setHtml(html)

    # --- Scripting API tab ---

    def _build_scripting_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 8, 0, 0)

        search_label = QLabel("Search API:")
        search_label_font = search_label.font()
        search_label_font.setBold(True)
        search_label.setFont(search_label_font)
        layout.addWidget(search_label)

        self.scripting_search_bar = QLineEdit()
        self.scripting_search_bar.setPlaceholderText("Type a function name or keyword to filter...")
        self.scripting_search_bar.textChanged.connect(self._filter_scripting)
        layout.addWidget(self.scripting_search_bar)

        self.scripting_text = _ReferenceTextEdit()
        self.scripting_text.setReadOnly(True)
        _configure_reference_text_edit(self.scripting_text)
        layout.addWidget(self.scripting_text)

        self._update_scripting_reference("")
        return widget

    def _filter_scripting(self, search_text):
        """Filter the Scripting API reference based on search text."""
        self._update_scripting_reference(search_text.lower())

    def _update_scripting_reference(self, search_text):
        """Reference for the functions a Script (User Space -> Scripts,
        via gui/managers/script_manager.py) can call -- distinct from the
        Python Function block (a palette block that runs code once per
        simulation timestep against its own ports; see its own in-canvas
        editor for that one's tiny 'in1..inN, t, dt, state, out1..outN'
        surface, which doesn't need a Help page).

        Filtered by search_text against each entry's signature/description
        with HTML tags stripped first -- otherwise every entry would match
        a plain search like "code" since the descriptions are full of
        <code> tags."""
        html = f"<html><body style='{_BODY_STYLE}'>"

        if not search_text:
            html += (
                "<p style='color: #3a3a3c;'>A <b>Script</b> (User Space &rarr; "
                "Scripts &rarr; New Script) is Python source that runs once, on "
                "demand, against the live diagram -- a command interface for "
                "building and driving a diagram from code instead of the "
                "mouse. It's unrelated to the <b>Python "
                "Function</b> palette block, which runs its own code every "
                "simulation timestep against only its own ports, with no access "
                "to the scene.</p>"
                "<p style='color: #3a3a3c;'>Every function below is available "
                "both when a Script runs (toolbar <b>Run</b>/F5) and in the "
                "<b>Console</b> dock (<b>View &rarr; Toggle Console</b>) -- "
                "there's nothing to import, they're just already in scope. "
                "Scripts and the Console all run in the exact same, single "
                "execution environment: a variable, import, or function "
                "defined in one is still there the next time any Script "
                "runs, or in the Console, for the rest of the session -- "
                "like one shared Python session, not an isolated sandbox "
                "per file. The Console also echoes back a bare expression's "
                "value, like a normal Python prompt (e.g. typing "
                "<code>2 + 2</code> shows <code>4</code>).</p>"
                "<p style='color: #3a3a3c;'>To see what's currently in "
                "that shared environment, open the <b>Global Variables</b> "
                "dock (<b>View &rarr; Toggle Global Variables</b>) -- a "
                "live table of every name defined so far. <b>Tools &rarr; "
                "Clear Global Variables...</b> (or that dock's own Clear "
                "All button) wipes all of it for a clean slate without "
                "restarting the app. See "
                "'Inspecting &amp; Clearing Globals' below.</p>"
            )

        matched_total = 0
        for category, items in SCRIPTING_HELP:
            matches = []
            for signature, description in items:
                if search_text:
                    searchable = re.sub(r"<[^>]+>", "", f"{signature} {description} {category}").lower()
                    if search_text not in searchable:
                        continue
                matches.append((signature, description))

            if not matches:
                continue

            html += (
                f"<h2 style='color: #007aff; border-bottom: 1px solid #e5e5ea; "
                f"padding-bottom: 6px; margin-top: 26px;'>{category}</h2>"
            )
            for signature, description in matches:
                matched_total += 1
                inner = (
                    f"<code style='font-size: 13px; font-weight: bold; color: #1d1d1f;'>{signature}</code>"
                    f"<div style='margin-top: 6px; color: #3a3a3c;'>{description}</div>"
                )
                html += _card(inner)

        if search_text and matched_total == 0:
            html += "<p style='text-align: center; color: #6e6e73; margin-top: 50px;'>No API functions found matching your search.</p>"

        html += "</body></html>"
        self.scripting_text.setHtml(html)

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

        self.reference_text = _ReferenceTextEdit()
        self.reference_text.setReadOnly(True)
        _configure_reference_text_edit(self.reference_text)
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
        html_content = f"<html><body style='{_BODY_STYLE}'>"

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
                inner = (
                    f"<span style='font-size: 15px; font-weight: bold; color: #1d1d1f;'>{block['name']}</span>"
                    f"<div style='margin-top: 8px; color: #3a3a3c;'><b style='color: #1d1d1f;'>Description:</b> {block['description']}</div>"
                    f"<div style='margin-top: 5px; color: #3a3a3c;'><b style='color: #1d1d1f;'>Parameters:</b> {block['parameters']}</div>"
                    f"<div style='margin-top: 5px; color: #3a3a3c;'><b style='color: #1d1d1f;'>Formula:</b> "
                    f"<code style='background-color: #e5e5ea; color: #1d1d1f; padding: 2px 6px; border-radius: 4px;'>{block['formula']}</code></div>"
                    f"<div style='margin-top: 5px; color: #3a3a3c;'><b style='color: #1d1d1f;'>Usage:</b> <i>{block['usage']}</i></div>"
                )
                html_content += _card(inner, margin_bottom=16)

        if matched_total == 0:
            html_content += "<p style='text-align: center; color: #6e6e73; margin-top: 50px;'>No blocks found matching your search.</p>"

        html_content += "</body></html>"
        self.reference_text.setHtml(html_content)
