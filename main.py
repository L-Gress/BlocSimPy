"""Top-level launcher for the refactored BlocSimPy application.

This file now only bootstraps the Qt application and imports the
refactored `MainWindow` from `gui.main_window`.
"""
import sys
import matplotlib
matplotlib.use('Qt5Agg')

from PySide6.QtWidgets import QApplication
from gui.main_window import MainWindow


def main(argv=None):
    app = QApplication(sys.argv if argv is None else argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())