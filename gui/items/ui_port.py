"""UI representation of a port."""
from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor
from config.ui_config import UIConfig


class UIPort(QGraphicsItem):
    """Visual representation of a block port."""
    
    def __init__(self, parent, port_model, is_input):
        super().__init__(parent)
        self.model = port_model
        self.is_input = is_input
        self.rect = QRectF(0, 0, UIConfig.PORT_SIZE, UIConfig.PORT_SIZE)
        self.setAcceptHoverEvents(True)
        self.connections = []

    def boundingRect(self):
        return self.rect

    def paint(self, painter, option, widget):
        color = UIConfig.INPUT_PORT_COLOR if self.is_input else UIConfig.OUTPUT_PORT_COLOR
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.rect)
