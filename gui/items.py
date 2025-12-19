from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QDialog
from PySide6.QtCore import Qt, QPointF, QRectF, QLineF
from PySide6.QtGui import QPen, QBrush, QPainterPath, QColor, QPainter, QPainterPathStroker

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
        self.pen = QPen(QColor(200, 200, 200), 2)
        self.setPen(self.pen)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

        self.points = []
        
        # Dragging state
        self._drag_index = -1
        self._drag_orientation = None # 'h' or 'v'
        self._last_drag_pos = QPointF()

        self.update_path(QPointF(0, 0))

    def shape(self):
        """Thicker hit detection area."""
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(10)
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
                        # We want to drag the segment between New2 and P1 (which is now index 3 relative to start?)
                        # Index mapping: 
                        # 0: P0 -> New1 (Stub)
                        # 1: New1 -> New2 (Vertical Step)
                        # 2: New2 -> Old_P1 (The horizontal part we want to drag)
                        found_index = 2 
                    else: 
                        # Insert before last point
                        idx_ins = len(self.points) - 1
                        self.points.insert(idx_ins, new_p2)
                        self.points.insert(idx_ins, new_p1)
                        # We want to drag the segment before New1
                        # Old path: ... -> P_last_start -> P_last
                        # New path: ... -> P_last_start -> New1 -> New2 -> P_last
                        # Target segment: P_last_start -> New1
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


class UIPort(QGraphicsItem):
    def __init__(self, parent, port_model, is_input):
        super().__init__(parent)
        self.model = port_model
        self.is_input = is_input
        self.size = 14
        self.rect = QRectF(0, 0, self.size, self.size)
        self.setAcceptHoverEvents(True)
        self.connections = []
        self._hovered = False

    def boundingRect(self):
        return self.rect

    def paint(self, painter, option, widget):
        color = QColor("orange") if self.is_input else QColor("green")
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


class UIBlock(QGraphicsItem):
    def __init__(self, block_model):
        super().__init__()
        self.model = block_model
        # CRITICAL: ItemSendsGeometryChanges ensures itemChange() is called when moving
        self.setFlags(QGraphicsItem.ItemIsMovable | 
                      QGraphicsItem.ItemIsSelectable | 
                      QGraphicsItem.ItemSendsGeometryChanges)
        self.width = 100
        self.height = 60
        self.ports_ui = {}
        self._setup_ports()

    def _setup_ports(self):
        # 1. Calculate the required height based on port counts
        num_inputs = len(self.model.inputs)
        num_outputs = len(self.model.outputs)
        
        # Formula: Top margin (20) + (25 * count) + Bottom margin
        req_height_in = 20 + (num_inputs * 25)
        req_height_out = 20 + (num_outputs * 25)
        
        # The block height is the Max of inputs, outputs, or the default 60
        self.height = max(60, req_height_in, req_height_out)

        # 2. Place Inputs (Left Side)
        y_offset = 20
        for name in self.model.inputs:
            p = UIPort(self, self.model.inputs[name], True)
            p.setPos(-7, y_offset) 
            self.ports_ui[name] = p
            y_offset += 25  # Increased spacing for larger ports

        # 3. Place Outputs (Right Side)
        y_offset = 20
        for name in self.model.outputs:
            p = UIPort(self, self.model.outputs[name], False)
            p.setPos(self.width - 7, y_offset)
            self.ports_ui[name] = p
            y_offset += 25  # Increased spacing for larger ports

    def boundingRect(self):
        # We make the bounding rect larger than the block to include the text labels.
        margin = 100 
        return QRectF(-margin, -margin, self.width + 2*margin, self.height + 2*margin)

    def shape(self):
        # Collision detection only on the block body
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width, self.height, 5, 5)
        return path

    def paint(self, painter, option, widget):
        # 1. Draw Block Background
        painter.setBrush(QBrush(QColor(50, 50, 50)))
        pen = QPen(QColor(100, 200, 255) if self.isSelected() else QColor(0, 0, 0))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(0, 0, self.width, self.height, 5, 5)

        # 2. Draw Port Names (Floating outside)
        port_font = painter.font()
        port_font.setPointSize(8) 
        painter.setFont(port_font)
        painter.setPen(QColor(220, 220, 220)) 

        # Normalize rotation
        rot = int(self.rotation()) % 360

        for name, port in self.ports_ui.items():
            painter.save()
            
            # Visual center of port
            center = port.boundingRect().center()
            px = port.pos().x() + center.x()
            py = port.pos().y() + center.y()
            
            painter.translate(px, py)
            painter.rotate(-self.rotation())

            side = 0 if port.is_input else 1 
            
            is_screen_left   = (side == 0 and rot == 0)   or (side == 1 and rot == 180)
            is_screen_right  = (side == 0 and rot == 180) or (side == 1 and rot == 0)
            is_screen_top    = (side == 0 and rot == 90)  or (side == 1 and rot == 270)
            is_screen_bottom = (side == 0 and rot == 270) or (side == 1 and rot == 90)

            text_margin = 12 
            w_text = 100      
            h_text = 20       
            
            rect = QRectF()
            align = Qt.AlignmentFlag.AlignCenter

            if is_screen_left:
                rect = QRectF(-w_text - text_margin, -h_text/2 + text_margin, w_text, h_text)
                align = Qt.AlignRight | Qt.AlignVCenter
            elif is_screen_right:
                rect = QRectF(text_margin, -h_text/2 + text_margin, w_text, h_text)
                align = Qt.AlignLeft | Qt.AlignVCenter
            elif is_screen_top:
                rect = QRectF(-w_text/2 + text_margin, -h_text - text_margin, w_text, h_text)
                align = Qt.AlignCenter | Qt.AlignBottom
            elif is_screen_bottom:
                rect = QRectF(-w_text/2 + text_margin, text_margin, w_text, h_text)
                align = Qt.AlignCenter | Qt.AlignTop

            painter.drawText(rect, align, name)
            painter.restore()

        # 3. Draw Main Block Name
        painter.save()
        title_font = painter.font()
        title_font.setPointSize(10)
        title_font.setBold(True)
        painter.setFont(title_font)
        
        center = QPointF(self.width/2, self.height/2)
        painter.translate(center)
        painter.rotate(-self.rotation())
        
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRectF(-self.width/2, -self.height/2, self.width, self.height), 
                         Qt.AlignCenter, self.model.name)
        painter.restore()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange or change == QGraphicsItem.ItemRotationHasChanged:
            self._update_attached_connections()
        return super().itemChange(change, value)

    def _update_attached_connections(self):
        for p in self.ports_ui.values():
            for conn in p.connections:
                try:
                    conn.points = [] 
                    conn.update_path()
                except Exception:
                    pass

    def mouseDoubleClickEvent(self, event):
        # Check for container blocks (like SubGraph)
        if getattr(self.model, "is_container", False):
            scene = self.scene()
            if scene:
                views = scene.views()
                if views:
                    main_window = views[0].parent() 
                    if hasattr(main_window, "enter_subsystem"):
                        main_window.enter_subsystem(self)
                        return

        if hasattr(self.model, 'get_editor_dialog'):
            editor = self.model.get_editor_dialog(None)
            if editor:
                if editor.exec() == QDialog.Accepted:
                    scene = self.scene()
                    if scene:
                        views = scene.views()
                        if views:
                            main_window = views[0].parent()
                            if hasattr(main_window, 'scene_manager'):
                                main_window.scene_manager.take_snapshot()
        super().mouseDoubleClickEvent(event)

    def refresh_ports(self):
        """
        Re-reads the model inputs/outputs and recreates the UIPorts.
        Tries to preserve existing connections if port names match.
        """
        # 1. Save existing connections mapping: {PortName: [List of UIConnections]}
        saved_connections = {}
        for name, port_ui in self.ports_ui.items():
            if port_ui.connections:
                saved_connections[name] = list(port_ui.connections)
        
        # 2. Remove old ports from scene
        for p in self.ports_ui.values():
            # Remove from scene if needed, though they are children of this Item
            # so usually recreating the dictionary is enough, 
            # BUT we need to detach connections visually or they might crash
            pass 

        # 3. Clear and Rebuild
        # We need to remove child items corresponding to ports?
        # Since UIPort is a child item of UIBlock, we should explicitly scene.removeItem them?
        # simpler approach: just clear dict, QGraphicsItem children management handles deletion? 
        # No, we must manually delete child items if we want them gone physically.
        for child in self.childItems():
            if isinstance(child, UIPort):
                # Detach connections from these dying ports
                for conn in child.connections:
                    # Set the end of the connection to None temporarily?
                    pass 
                # We simply rebuild. Connections might look detached until reconnected.
                pass

        # Since modifying childItems list while iterating is risky, 
        # let's just wipe `self.ports_ui` and call `_setup_ports`.
        # Visual artifacts might remain if we don't handle child removal correctly.
        # Let's try the simple approach:
        
        # Delete old port items
        for p in self.ports_ui.values():
            p.setParentItem(None) # Removes from scene/group
        
        self.ports_ui = {}
        self._setup_ports() # Uses the logic we wrote previously (max height etc)
        self.update() # Redraw block

        # 4. Attempt to Reconnect
        # This is tricky. The `UIConnection` objects still exist in the scene,
        # but they point to deleted UIPort objects.
        # We need to update those connections to point to the NEW UIPort objects.
        
        for name, old_conns in saved_connections.items():
            if name in self.ports_ui:
                new_port = self.ports_ui[name]
                for conn in old_conns:
                    # Update connection references
                    if conn.start_port and conn.start_port.parentItem() == self:
                        # This block was the start
                        conn.start_port = new_port
                    elif conn.end_port and conn.end_port.parentItem() == self:
                        # This block was the end
                        conn.end_port = new_port
                    
                    # Add to new port list
                    new_port.connections.append(conn)
                    conn.update_path()
            else:
                # Port no longer exists (deleted inside subsystem)
                # We should remove these connections from the scene
                scene = self.scene()
                for conn in old_conns:
                    if scene: scene.removeItem(conn)

    def rotate_90(self):
        self.setTransformOriginPoint(self.width/2, self.height/2)
        current_rotation = self.rotation()
        self.setRotation(current_rotation + 90)
        self._update_attached_connections()