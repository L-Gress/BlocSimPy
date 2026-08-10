"""App-wide visual theme: an Apple-inspired dark palette (in the vein of
Xcode/Logic Pro) applied globally via QApplication.setStyleSheet().

Kept separate from ui_config.py: this file styles Qt *widgets* (menus,
toolbars, dialogs, buttons) through QSS, while UIConfig styles the
QGraphicsScene *canvas* (blocks, ports, wires) through direct QPainter
calls -- QSS doesn't reach into custom-painted QGraphicsItems, so the two
have to be kept in visual sync by hand. Colors below are shared with/mirror
the ones in ui_config.py; if you change one, check the other.
"""

# --- Palette (macOS Dark Mode system colors) ---
BG = "#1e1e1e"              # window background
PANEL = "#252526"           # toolbar / menu bar / dock background
ELEVATED = "#2c2c2e"        # dialogs, input fields, list rows
ELEVATED_HOVER = "#3a3a3c"  # hover state on elevated surfaces
BORDER = "#3a3a3c"          # hairline dividers/borders
BORDER_STRONG = "#48484a"   # more visible borders (e.g. focused input)

TEXT = "#f5f5f7"            # primary text
TEXT_SECONDARY = "#98989d"  # secondary/disabled text
TEXT_ON_ACCENT = "#ffffff"

ACCENT = "#0a84ff"          # systemBlue (dark)
ACCENT_HOVER = "#3a9bff"
ACCENT_PRESSED = "#0060df"

DANGER = "#ff453a"          # systemRed (dark)
WARNING = "#ff9f0a"         # systemOrange (dark)
SUCCESS = "#32d74b"         # systemGreen (dark)

RADIUS = 8

STYLESHEET = """
* {
    font-family: "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", sans-serif;
    outline: none;
}

QMainWindow, QDialog {
    background-color: #1e1e1e;
    color: #f5f5f7;
}

QWidget {
    color: #f5f5f7;
    selection-background-color: #0a84ff;
    selection-color: #ffffff;
}

QLabel {
    background: transparent;
}

/* --- Menu bar / menus --- */
QMenuBar {
    background-color: #252526;
    color: #f5f5f7;
    border-bottom: 1px solid #3a3a3c;
    padding: 2px 4px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 6px;
}
QMenuBar::item:selected {
    background-color: #3a3a3c;
}
QMenu {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 6px;
}
QMenu::item:selected {
    background-color: #0a84ff;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #3a3a3c;
    margin: 4px 8px;
}

/* --- Toolbar --- */
QToolBar {
    background-color: #252526;
    border: none;
    border-bottom: 1px solid #3a3a3c;
    spacing: 2px;
    padding: 4px 6px;
}
QToolBar::separator {
    background-color: #3a3a3c;
    width: 1px;
    margin: 6px 6px;
}
QToolButton {
    background: transparent;
    color: #f5f5f7;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 8px;
}
QToolButton:hover {
    background-color: #3a3a3c;
}
QToolButton:pressed {
    background-color: #48484a;
}
QToolButton:disabled {
    color: #636366;
}

/* --- Status bar --- */
QStatusBar {
    background-color: #252526;
    color: #98989d;
    border-top: 1px solid #3a3a3c;
}

/* --- Dock widgets --- */
QDockWidget {
    background-color: #1e1e1e;
    color: #f5f5f7;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: #252526;
    padding: 6px 8px;
    border-bottom: 1px solid #3a3a3c;
}

/* --- Tree / list widgets (block library, user library, diagram check) --- */
QTreeWidget, QListWidget {
    background-color: #1e1e1e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 8px;
    outline: none;
    padding: 2px;
}
QTreeWidget::item, QListWidget::item {
    padding: 4px 4px;
    border-radius: 5px;
}
QTreeWidget::item:hover, QListWidget::item:hover {
    background-color: #2c2c2e;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #0a84ff;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #252526;
    color: #98989d;
    border: none;
    border-bottom: 1px solid #3a3a3c;
    padding: 4px;
}

/* --- Tabs (library dock) --- */
QTabWidget::pane {
    border: 1px solid #3a3a3c;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #98989d;
    padding: 6px 14px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:hover {
    color: #f5f5f7;
}
QTabBar::tab:selected {
    color: #f5f5f7;
    border-bottom: 2px solid #0a84ff;
}

/* --- Inputs --- */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: #0a84ff;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #0a84ff;
}
QLineEdit:disabled, QComboBox:disabled {
    color: #636366;
    background-color: #252526;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 8px;
    selection-background-color: #0a84ff;
    selection-color: #ffffff;
    outline: none;
}

/* --- Buttons --- */
QPushButton {
    background-color: #3a3a3c;
    color: #f5f5f7;
    border: 1px solid #48484a;
    border-radius: 6px;
    padding: 6px 16px;
}
QPushButton:hover {
    background-color: #48484a;
}
QPushButton:pressed {
    background-color: #545456;
}
QPushButton:disabled {
    color: #636366;
    background-color: #2c2c2e;
    border-color: #3a3a3c;
}
QPushButton:default {
    background-color: #0a84ff;
    border: 1px solid #0a84ff;
    color: #ffffff;
    font-weight: 600;
}
QPushButton:default:hover {
    background-color: #3a9bff;
}
QPushButton:default:pressed {
    background-color: #0060df;
}

/* --- Dialog buttons --- */
QDialogButtonBox QPushButton {
    min-width: 72px;
}

/* --- Progress dialog / bar --- */
QProgressBar {
    background-color: #2c2c2e;
    border: 1px solid #3a3a3c;
    border-radius: 6px;
    text-align: center;
    color: #f5f5f7;
}
QProgressBar::chunk {
    background-color: #0a84ff;
    border-radius: 5px;
}

/* --- Scrollbars --- */
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #48484a;
    border-radius: 5px;
    min-height: 24px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #636366;
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
    background: #48484a;
    border-radius: 5px;
    min-width: 24px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #636366;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* --- Splitters --- */
QSplitter::handle {
    background-color: #3a3a3c;
}

QToolTip {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    padding: 4px 6px;
    border-radius: 4px;
}
"""
