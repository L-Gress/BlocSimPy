"""UI representation of a port."""
from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QPen
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
        self._hovered = False

    def boundingRect(self):
        return self.rect

    def paint(self, painter, option, widget):
        color = UIConfig.INPUT_PORT_COLOR if self.is_input else UIConfig.OUTPUT_PORT_COLOR
        if self._hovered:
            color = color.lighter(130)
            
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(150), 1) if self._hovered else Qt.NoPen)
        painter.drawEllipse(self.rect)
        
        if self._hovered:
            # Subtle glow
            glow = QColor(color)
            glow.setAlpha(50)
            painter.setBrush(QBrush(glow))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(self.rect.adjusted(-2, -2, 2, 2))

    def hoverEnterEvent(self, event):
        self._hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._hovered = False
        self.update()
        super().hoverLeaveEvent(event)
