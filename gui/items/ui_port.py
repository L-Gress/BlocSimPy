"""UI representation of a port."""
from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import Qt, QPointF, QRectF
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

    def fork_point(self, tol=1.0):
        """Scene point where this port's outgoing wires actually diverge
        from each other -- not just "at the port" -- or None if there's
        nothing to fork (fewer than two routed connections).

        Sibling wires typically share an initial run of waypoints (they
        all leave the same port the same way) before splitting off toward
        their own destinations; this walks that shared run and returns
        the last point still common to every sibling, which is where the
        branch dot belongs.
        """
        sibling_paths = [c.points for c in self.connections if len(c.points) >= 2]
        if len(sibling_paths) < 2:
            return None

        shortest = min(len(p) for p in sibling_paths)
        last_common = sibling_paths[0][0]
        for i in range(shortest):
            candidate = sibling_paths[0][i]
            if all(abs(p[i].x() - candidate.x()) < tol and abs(p[i].y() - candidate.y()) < tol
                   for p in sibling_paths[1:]):
                last_common = candidate
            else:
                break
        return QPointF(last_common)
