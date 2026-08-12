"""App-wide visual theme: a light palette (macOS Big Sur/Sequoia "System
Gray" light mode) and a dark palette (VS Code Dark+ / macOS dark mode
"System Gray"), both applied globally via QApplication.setStyleSheet() --
see gui/managers/theme_manager.py for the switch itself.

Kept separate from ui_config.py: this file styles Qt *widgets* (menus,
toolbars, dialogs, buttons) through QSS, while UIConfig styles the
QGraphicsScene *canvas* (blocks, ports, wires) through direct QPainter
calls -- QSS doesn't reach into custom-painted QGraphicsItems, so the two
have to be kept in visual sync by hand. Colors below are shared with/mirror
the ones in ui_config.py; if you change one palette, check the other.
"""

RADIUS = 8

# --- Palettes ---
# Every color the QSS template below references, by name, for each mode.
# Two full dicts (rather than deriving dark from light) so each palette can
# be tuned independently -- macOS dark mode isn't just light mode inverted
# (e.g. systemBlue itself shifts from #007aff to #0a84ff).
LIGHT = {
    "BG": "#ffffff",               # window / dialog background
    "PANEL": "#f6f6f7",            # toolbar / menu bar / status bar background
    "ELEVATED": "#ffffff",         # inputs, list rows
    "ELEVATED_HOVER": "#f0f0f2",   # hover state on elevated surfaces
    "HOVER": "#e5e5ea",            # hover/pressed state on menu items, buttons, toolbar buttons
    "BORDER": "#d1d1d6",           # hairline dividers/borders
    "BORDER_STRONG": "#c7c7cc",    # more visible borders / disabled text / scrollbar handle

    "TEXT": "#1d1d1f",             # primary text
    "TEXT_SECONDARY": "#6e6e73",   # secondary/disabled text
    "TEXT_ON_ACCENT": "#ffffff",

    "ACCENT": "#007aff",           # systemBlue (light)
    "ACCENT_HOVER": "#3395ff",
    "ACCENT_PRESSED": "#0060df",

    "DANGER": "#ff3b30",           # systemRed (light)
    "WARNING": "#ff9500",          # systemOrange (light)
    "SUCCESS": "#34c759",          # systemGreen (light)

    "SCROLLBAR_HANDLE_HOVER": "#aeaeb2",
}

DARK = {
    "BG": "#1e1e1e",
    "PANEL": "#252526",
    "ELEVATED": "#2d2d30",
    "ELEVATED_HOVER": "#383838",
    "HOVER": "#3e3e42",
    "BORDER": "#3c3c3c",
    "BORDER_STRONG": "#54545a",

    "TEXT": "#e4e4e6",
    "TEXT_SECONDARY": "#9d9d9f",
    "TEXT_ON_ACCENT": "#ffffff",

    "ACCENT": "#0a84ff",           # systemBlue (dark)
    "ACCENT_HOVER": "#3d9bff",
    "ACCENT_PRESSED": "#006fd6",

    "DANGER": "#ff453a",           # systemRed (dark)
    "WARNING": "#ff9f0a",          # systemOrange (dark)
    "SUCCESS": "#32d74b",          # systemGreen (dark)

    "SCROLLBAR_HANDLE_HOVER": "#6e6e73",
}

PALETTES = {"light": LIGHT, "dark": DARK}

# QSS template shared by both modes -- colors are %()s-substituted (not
# str.format(), since QSS itself is full of literal { } rule-block braces)
# from LIGHT or DARK above.
_STYLESHEET_TEMPLATE = """
* {
    font-family: "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", sans-serif;
    outline: none;
}

QMainWindow, QDialog {
    background-color: %(BG)s;
    color: %(TEXT)s;
}

QWidget {
    color: %(TEXT)s;
    selection-background-color: %(ACCENT)s;
    selection-color: %(TEXT_ON_ACCENT)s;
}

QLabel {
    background: transparent;
}

/* --- Menu bar / menus --- */
QMenuBar {
    background-color: %(PANEL)s;
    color: %(TEXT)s;
    border-bottom: 1px solid %(BORDER)s;
    padding: 2px 4px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 6px;
}
QMenuBar::item:selected {
    background-color: %(HOVER)s;
}
QMenu {
    background-color: %(ELEVATED)s;
    color: %(TEXT)s;
    border: 1px solid %(BORDER)s;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 6px;
}
QMenu::item:selected {
    background-color: %(ACCENT)s;
    color: %(TEXT_ON_ACCENT)s;
}
QMenu::separator {
    height: 1px;
    background: %(HOVER)s;
    margin: 4px 8px;
}

/* --- Toolbar --- */
QToolBar {
    background-color: %(PANEL)s;
    border: none;
    border-bottom: 1px solid %(BORDER)s;
    spacing: 2px;
    padding: 4px 6px;
}
QToolBar::separator {
    background-color: %(BORDER)s;
    width: 1px;
    margin: 6px 6px;
}
QToolButton {
    background: transparent;
    color: %(TEXT)s;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 8px;
}
QToolButton:hover {
    background-color: %(HOVER)s;
}
QToolButton:pressed {
    background-color: %(BORDER)s;
}
QToolButton:disabled {
    color: %(BORDER_STRONG)s;
}

/* --- Status bar --- */
QStatusBar {
    background-color: %(PANEL)s;
    color: %(TEXT_SECONDARY)s;
    border-top: 1px solid %(BORDER)s;
}

/* --- Dock widgets --- */
QDockWidget {
    background-color: %(BG)s;
    color: %(TEXT)s;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: %(PANEL)s;
    padding: 6px 8px;
    border-bottom: 1px solid %(BORDER)s;
}

/* --- Tree / list / table widgets (block library, user library, diagram
   check, Global Variables) --- */
QTreeWidget, QListWidget, QTableWidget {
    background-color: %(ELEVATED)s;
    alternate-background-color: %(PANEL)s;
    color: %(TEXT)s;
    border: 1px solid %(BORDER)s;
    border-radius: 8px;
    outline: none;
    padding: 2px;
    gridline-color: %(BORDER)s;
}
QTreeWidget::item, QListWidget::item, QTableWidget::item {
    padding: 4px 4px;
    border-radius: 5px;
}
QTreeWidget::item:hover, QListWidget::item:hover, QTableWidget::item:hover {
    background-color: %(ELEVATED_HOVER)s;
}
QTreeWidget::item:selected, QListWidget::item:selected, QTableWidget::item:selected {
    background-color: %(ACCENT)s;
    color: %(TEXT_ON_ACCENT)s;
}
QTableWidget QTableCornerButton::section {
    background-color: %(PANEL)s;
    border: none;
    border-bottom: 1px solid %(BORDER)s;
}
QHeaderView {
    background-color: %(PANEL)s;
}
QHeaderView::section {
    background-color: %(PANEL)s;
    color: %(TEXT_SECONDARY)s;
    border: none;
    border-bottom: 1px solid %(BORDER)s;
    padding: 4px;
}

/* --- Tabs (library dock) --- */
QTabWidget::pane {
    border: 1px solid %(BORDER)s;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: %(TEXT_SECONDARY)s;
    padding: 6px 14px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:hover {
    color: %(TEXT)s;
}
QTabBar::tab:selected {
    color: %(TEXT)s;
    border-bottom: 2px solid %(ACCENT)s;
}

/* --- Inputs --- */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: %(ELEVATED)s;
    color: %(TEXT)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: %(ACCENT)s;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid %(ACCENT)s;
}
QLineEdit:disabled, QComboBox:disabled {
    color: %(BORDER_STRONG)s;
    background-color: %(PANEL)s;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: %(ELEVATED)s;
    color: %(TEXT)s;
    border: 1px solid %(BORDER)s;
    border-radius: 8px;
    selection-background-color: %(ACCENT)s;
    selection-color: %(TEXT_ON_ACCENT)s;
    outline: none;
}

/* --- Buttons --- */
QPushButton {
    background-color: %(ELEVATED_HOVER)s;
    color: %(TEXT)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    padding: 6px 16px;
}
QPushButton:hover {
    background-color: %(HOVER)s;
}
QPushButton:pressed {
    background-color: %(BORDER)s;
}
QPushButton:disabled {
    color: %(BORDER_STRONG)s;
    background-color: %(PANEL)s;
    border-color: %(HOVER)s;
}
QPushButton:default {
    background-color: %(ACCENT)s;
    border: 1px solid %(ACCENT)s;
    color: %(TEXT_ON_ACCENT)s;
    font-weight: 600;
}
QPushButton:default:hover {
    background-color: %(ACCENT_HOVER)s;
}
QPushButton:default:pressed {
    background-color: %(ACCENT_PRESSED)s;
}

/* --- Dialog buttons --- */
QDialogButtonBox QPushButton {
    min-width: 72px;
}

/* --- Progress dialog / bar --- */
QProgressBar {
    background-color: %(ELEVATED_HOVER)s;
    border: 1px solid %(BORDER)s;
    border-radius: 6px;
    text-align: center;
    color: %(TEXT)s;
}
QProgressBar::chunk {
    background-color: %(ACCENT)s;
    border-radius: 5px;
}

/* --- Scrollbars --- */
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: %(BORDER_STRONG)s;
    border-radius: 5px;
    min-height: 24px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: %(SCROLLBAR_HANDLE_HOVER)s;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 12px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: %(BORDER_STRONG)s;
    border-radius: 5px;
    min-width: 24px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: %(SCROLLBAR_HANDLE_HOVER)s;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* --- Splitters --- */
QSplitter::handle {
    background-color: %(BORDER)s;
}

QToolTip {
    background-color: %(PANEL)s;
    color: %(TEXT)s;
    border: 1px solid %(BORDER)s;
    padding: 4px 6px;
    border-radius: 4px;
}
"""


def stylesheet_for(mode):
    """The full QSS stylesheet for `mode` ("light" or "dark"), ready for
    QApplication.setStyleSheet()."""
    palette = PALETTES.get(mode, LIGHT)
    return _STYLESHEET_TEMPLATE % palette


# Default/light stylesheet, kept as a module-level constant for callers
# that don't care about theming (e.g. a first paint before ThemeManager
# applies the user's saved choice).
STYLESHEET = stylesheet_for("light")
