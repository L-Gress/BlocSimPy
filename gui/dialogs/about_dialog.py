"""About dialog showing app name, version, and license info."""
import os
import sys
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from version import __version__


def _logo_path():
    """Same resolution logic as MainWindow's window icon: relative to this
    file's location (not cwd) so it works regardless of launch directory,
    except when frozen, where logo.png is bundled next to the executable."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, "logo.png")
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_root, "logo.png")


class AboutDialog(QDialog):
    """Simple About box."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About BlocSimPy")
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)

        logo_path = _logo_path()
        if os.path.exists(logo_path):
            logo = QLabel()
            pixmap = QPixmap(logo_path).scaled(
                72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            logo.setPixmap(pixmap)
            logo.setAlignment(Qt.AlignCenter)
            layout.addWidget(logo)

        title = QLabel(f"BlocSimPy {__version__}")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("A desktop block-diagram simulator built with Python and Qt.")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        info = QLabel(
            "<a href='https://github.com/L-Gress/BlocSimPy'>github.com/L-Gress/BlocSimPy</a>"
            "<br>Licensed under the MIT License."
        )
        info.setOpenExternalLinks(True)
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)

        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)
