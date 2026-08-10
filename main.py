"""Top-level launcher for the refactored BlocSimPy application.

This file now only bootstraps the Qt application and imports the
refactored `MainWindow` from `gui.main_window`.
"""
import sys
import matplotlib
matplotlib.use('QtAgg')

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from gui.main_window import MainWindow
from config.theme import STYLESHEET


def main(argv=None):
    app = QApplication(sys.argv if argv is None else argv)

    # Fusion is the cross-platform base style QSS theming is designed
    # against -- native styles (e.g. windowsvista) don't reliably honor
    # QSS colors on every widget, which is what the dark theme below relies
    # on throughout.
    app.setStyle("Fusion")

    font = QFont()
    font.setFamilies(["SF Pro Text", "Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", "Arial"])
    font.setPointSize(10)
    app.setFont(font)

    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())