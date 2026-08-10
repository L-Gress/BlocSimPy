"""App-wide visual theme: an Apple-inspired light palette (macOS Big Sur/
Sequoia "System Gray" light mode) applied globally via
QApplication.setStyleSheet().

Kept separate from ui_config.py: this file styles Qt *widgets* (menus,
toolbars, dialogs, buttons) through QSS, while UIConfig styles the
QGraphicsScene *canvas* (blocks, ports, wires) through direct QPainter
calls -- QSS doesn't reach into custom-painted QGraphicsItems, so the two
have to be kept in visual sync by hand. Colors below are shared with/mirror
the ones in ui_config.py; if you change one, check the other.
"""

# --- Palette (macOS Light Mode system colors) ---
BG = "#ffffff"               # window / dialog background
PANEL = "#f6f6f7"            # toolbar / menu bar / status bar background
ELEVATED = "#ffffff"         # inputs, list rows
ELEVATED_HOVER = "#f0f0f2"   # hover state on elevated surfaces
BORDER = "#d1d1d6"           # hairline dividers/borders
BORDER_STRONG = "#c7c7cc"    # more visible borders (e.g. focused input)

TEXT = "#1d1d1f"             # primary text
TEXT_SECONDARY = "#6e6e73"   # secondary/disabled text
TEXT_ON_ACCENT = "#ffffff"

ACCENT = "#007aff"           # systemBlue (light)
ACCENT_HOVER = "#3395ff"
ACCENT_PRESSED = "#0060df"

DANGER = "#ff3b30"           # systemRed (light)
WARNING = "#ff9500"          # systemOrange (light)
SUCCESS = "#34c759"          # systemGreen (light)

RADIUS = 8

STYLESHEET = """
* {
    font-family: "SF Pro Text", "Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", sans-serif;
    outline: none;
}

QMainWindow, QDialog {
    background-color: #ffffff;
    color: #1d1d1f;
}

QWidget {
    color: #1d1d1f;
    selection-background-color: #007aff;
    selection-color: #ffffff;
}

QLabel {
    background: transparent;
}

/* --- Menu bar / menus --- */
QMenuBar {
    background-color: #f6f6f7;
    color: #1d1d1f;
    border-bottom: 1px solid #d1d1d6;
    padding: 2px 4px;
}
QMenuBar::item {
    background: transparent;
    padding: 4px 10px;
    border-radius: 6px;
}
QMenuBar::item:selected {
    background-color: #e5e5ea;
}
QMenu {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d1d1d6;
    border-radius: 8px;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 6px;
}
QMenu::item:selected {
    background-color: #007aff;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #e5e5ea;
    margin: 4px 8px;
}

/* --- Toolbar --- */
QToolBar {
    background-color: #f6f6f7;
    border: none;
    border-bottom: 1px solid #d1d1d6;
    spacing: 2px;
    padding: 4px 6px;
}
QToolBar::separator {
    background-color: #d1d1d6;
    width: 1px;
    margin: 6px 6px;
}
QToolButton {
    background: transparent;
    color: #1d1d1f;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 5px 8px;
}
QToolButton:hover {
    background-color: #e5e5ea;
}
QToolButton:pressed {
    background-color: #d1d1d6;
}
QToolButton:disabled {
    color: #c7c7cc;
}

/* --- Status bar --- */
QStatusBar {
    background-color: #f6f6f7;
    color: #6e6e73;
    border-top: 1px solid #d1d1d6;
}

/* --- Dock widgets --- */
QDockWidget {
    background-color: #ffffff;
    color: #1d1d1f;
    titlebar-close-icon: none;
}
QDockWidget::title {
    background-color: #f6f6f7;
    padding: 6px 8px;
    border-bottom: 1px solid #d1d1d6;
}

/* --- Tree / list widgets (block library, user library, diagram check) --- */
QTreeWidget, QListWidget {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d1d1d6;
    border-radius: 8px;
    outline: none;
    padding: 2px;
}
QTreeWidget::item, QListWidget::item {
    padding: 4px 4px;
    border-radius: 5px;
}
QTreeWidget::item:hover, QListWidget::item:hover {
    background-color: #f0f0f2;
}
QTreeWidget::item:selected, QListWidget::item:selected {
    background-color: #007aff;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #f6f6f7;
    color: #6e6e73;
    border: none;
    border-bottom: 1px solid #d1d1d6;
    padding: 4px;
}

/* --- Tabs (library dock) --- */
QTabWidget::pane {
    border: 1px solid #d1d1d6;
    border-radius: 8px;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #6e6e73;
    padding: 6px 14px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:hover {
    color: #1d1d1f;
}
QTabBar::tab:selected {
    color: #1d1d1f;
    border-bottom: 2px solid #007aff;
}

/* --- Inputs --- */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d1d1d6;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: #007aff;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #007aff;
}
QLineEdit:disabled, QComboBox:disabled {
    color: #c7c7cc;
    background-color: #f6f6f7;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d1d1d6;
    border-radius: 8px;
    selection-background-color: #007aff;
    selection-color: #ffffff;
    outline: none;
}

/* --- Buttons --- */
QPushButton {
    background-color: #f0f0f2;
    color: #1d1d1f;
    border: 1px solid #d1d1d6;
    border-radius: 6px;
    padding: 6px 16px;
}
QPushButton:hover {
    background-color: #e5e5ea;
}
QPushButton:pressed {
    background-color: #d1d1d6;
}
QPushButton:disabled {
    color: #c7c7cc;
    background-color: #f6f6f7;
    border-color: #e5e5ea;
}
QPushButton:default {
    background-color: #007aff;
    border: 1px solid #007aff;
    color: #ffffff;
    font-weight: 600;
}
QPushButton:default:hover {
    background-color: #3395ff;
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
    background-color: #f0f0f2;
    border: 1px solid #d1d1d6;
    border-radius: 6px;
    text-align: center;
    color: #1d1d1f;
}
QProgressBar::chunk {
    background-color: #007aff;
    border-radius: 5px;
}

/* --- Scrollbars --- */
QScrollBar:vertical {
    background: transparent;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #c7c7cc;
    border-radius: 5px;
    min-height: 24px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #aeaeb2;
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
    background: #c7c7cc;
    border-radius: 5px;
    min-width: 24px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #aeaeb2;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* --- Splitters --- */
QSplitter::handle {
    background-color: #d1d1d6;
}

QToolTip {
    background-color: #f6f6f7;
    color: #1d1d1f;
    border: 1px solid #d1d1d6;
    padding: 4px 6px;
    border-radius: 4px;
}
"""
