"""About dialog showing app name, version, and license info."""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
from PySide6.QtCore import Qt

from version import __version__


class AboutDialog(QDialog):
    """Simple About box."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About BlocSimPy")
        self.setFixedWidth(360)

        layout = QVBoxLayout(self)

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
