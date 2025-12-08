"""UI representation of a connection between ports."""
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsItem
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPen, QPainterPath, QPainterPathStroker
from config.ui_config import UIConfig


class UIConnection(QGraphicsPathItem):
    """
    Simulink-like Orthogonal Connection with Smart Segment Handling.
    - Routes automatically with orthogonal segments.
    - Dragging a segment moves it perpendicular to its orientation.
    - Dragging a port-attached segment automatically splits the line to create a step.
    - Automatically simplifies collinear segments on release.
    """
    def __init__(self, start_port_ui, end_port_ui=None):
        super().__init__()
        self.start_port = start_port_ui
        self.end_port = end_port_ui
        
        self.setZValue(-1)
        self.pen = QPen(UIConfig.CONNECTION_COLOR, UIConfig.CONNECTION_WIDTH)
        self.setPen(self.pen)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

        self.points = []
        
        # Dragging state
        self._drag_index = -1
        self._drag_orientation = None  # 'h' or 'v'
        self._last_drag_pos = QPointF()

        self.update_path(QPointF(0, 0))

    def shape(self):
        """Thicker hit detection area."""
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(UIConfig.CONNECTION_HIT_WIDTH)
        return path_stroker.createStroke(self.path())

    def update_path(self, mouse_pos=None):
        # Compute port center in scene coordinates to avoid offsets after rotation
        p1 = self.start_port.mapToScene(self.start_port.boundingRect().center())
        
        # --- Drawing Mode ---
        if not self.end_port:
            if mouse_pos is None: return
            p2 = mouse_pos
            path = QPainterPath()
            path.moveTo(p1)
            mid_x = (p1.x() + p2.x()) / 2
            path.lineTo(mid_x, p1.y())
            path.lineTo(mid_x, p2.y())
            path.lineTo(p2)
            self.setPath(path)
            return

        # --- Connected Mode ---
        # Compute end port center robustly (handles parent rotation)
        p_end = self.end_port.mapToScene(self.end_port.boundingRect().center())

        if not self.points:
            self._create_initial_route(p1, p_end)
        else:
            # Update endpoints
            self.points[0] = p1
            self.points[-1] = p_end
            
            # Constraint: First and Last segments must remain horizontal attached to ports
            # We enforce this by matching the Y of the neighbor points.
            if len(self.points) > 1:
                self.points[1].setY(p1.y())
                self.points[-2].setY(p_end.y())

        # Build Path
        path = QPainterPath()
        if self.points:
            path.moveTo(self.points[0])
            for p in self.points[1:]:
                path.lineTo(p)
        
        self.setPath(path)

    def _create_initial_route(self, start_pos, end_pos):
        """Standard 4-point orthogonal route."""
        mid_x = (start_pos.x() + end_pos.x()) / 2.0
        if mid_x < start_pos.x() + 20: mid_x = start_pos.x() + 20
        
        self.points = [
            start_pos,
            QPointF(mid_x, start_pos.y()),
            QPointF(mid_x, end_pos.y()),
            end_pos
        ]

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.end_port is not None:
            pos = event.scenePos()
            best_dist = 10.0
            found_index = -1
            
            # 1. Hit Detection
            for i in range(len(self.points) - 1):
                p_start = self.points[i]
                p_end = self.points[i+1]
                
                is_horizontal = abs(p_start.y() - p_end.y()) < 1.0
                is_vertical = abs(p_start.x() - p_end.x()) < 1.0
                
                dist = 999
                if is_horizontal:
                    min_x, max_x = sorted((p_start.x(), p_end.x()))
                    if min_x - 5 <= pos.x() <= max_x + 5:
                        dist = abs(pos.y() - p_start.y())
                elif is_vertical:
                    min_y, max_y = sorted((p_start.y(), p_end.y()))
                    if min_y - 5 <= pos.y() <= max_y + 5:
                        dist = abs(pos.x() - p_start.x())
                
                if dist < best_dist:
                    best_dist = dist
                    found_index = i

            # 2. Handle Click
            if found_index != -1:
                p1 = self.points[found_index]
                p2 = self.points[found_index+1]
                is_horiz = abs(p1.y() - p2.y()) < 1.0
                
                # Check if this is a "locked" port segment
                is_start_seg = (found_index == 0)
                is_end_seg = (found_index == len(self.points) - 2)

                # DYNAMIC SPLITTING LOGIC
                # If user tries to drag a horizontal segment attached to a port, split it.
                if is_horiz and (is_start_seg or is_end_seg):
                    split_x = pos.x()
                    
                    # Prevent splitting too close to the port itself
                    if is_start_seg and abs(split_x - self.points[0].x()) < 10:
                        split_x = self.points[0].x() + 10
                    if is_end_seg and abs(split_x - self.points[-1].x()) < 10:
                        split_x = self.points[-1].x() - 10

                    new_p1 = QPointF(split_x, p1.y())
                    new_p2 = QPointF(split_x, p1.y())
                    
                    if is_start_seg:
                        # Insert after index 0: P0 -> New1 -> New2 -> P1 ...
                        self.points.insert(1, new_p2)
                        self.points.insert(1, new_p1)
                        found_index = 2 
                    else: 
                        # Insert before last point
                        idx_ins = len(self.points) - 1
                        self.points.insert(idx_ins, new_p2)
                        self.points.insert(idx_ins, new_p1)
                        found_index = len(self.points) - 4

                # Setup Drag
                self._drag_index = found_index
                self._drag_orientation = 'h' if is_horiz else 'v'
                self._last_drag_pos = pos
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_index != -1:
            curr_pos = event.scenePos()
            delta = curr_pos - self._last_drag_pos
            
            idx = self._drag_index
            p_start = self.points[idx]
            p_end = self.points[idx+1]
            
            if self._drag_orientation == 'h':
                # Move segment Up/Down (Change Y)
                new_y = p_start.y() + delta.y()
                p_start.setY(new_y)
                p_end.setY(new_y)
            elif self._drag_orientation == 'v':
                # Move segment Left/Right (Change X)
                new_x = p_start.x() + delta.x()
                p_start.setX(new_x)
                p_end.setX(new_x)

            self._last_drag_pos = curr_pos
            self.update_path()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_index != -1:
            self._simplify_path()
            self._drag_index = -1
            self._drag_orientation = None
            self.update_path()
        super().mouseReleaseEvent(event)

    def _simplify_path(self):
        """Removes collinear points to clean up the line."""
        if len(self.points) < 3: return
        
        # Iterate backwards to safely remove items
        i = len(self.points) - 2
        while i > 0:
            p_prev = self.points[i-1]
            p_curr = self.points[i]
            p_next = self.points[i+1]
            
            # Check for collinearity (horizontal or vertical)
            # If Prev-Curr is Horizontal AND Curr-Next is Horizontal -> Merge
            is_prev_horiz = abs(p_prev.y() - p_curr.y()) < 1.0
            is_next_horiz = abs(p_curr.y() - p_next.y()) < 1.0
            
            is_prev_vert = abs(p_prev.x() - p_curr.x()) < 1.0
            is_next_vert = abs(p_curr.x() - p_next.x()) < 1.0
            
            if (is_prev_horiz and is_next_horiz) or (is_prev_vert and is_next_vert):
                # Remove p_curr, connects p_prev directly to p_next
                self.points.pop(i)
            
            i -= 1
