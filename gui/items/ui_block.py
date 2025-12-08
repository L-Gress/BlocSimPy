"""UI representation of a block."""
from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen, QBrush, QPainterPath, QColor
from config.ui_config import UIConfig
from .ui_port import UIPort


class UIBlock(QGraphicsItem):
    """Visual representation of a simulation block."""
    
    def __init__(self, block_model):
        super().__init__()
        self.model = block_model
        # CRITICAL: ItemSendsGeometryChanges ensures itemChange() is called when moving
        self.setFlags(QGraphicsItem.ItemIsMovable | 
                      QGraphicsItem.ItemIsSelectable | 
                      QGraphicsItem.ItemSendsGeometryChanges)
        self.width = UIConfig.DEFAULT_BLOCK_WIDTH
        self.height = UIConfig.DEFAULT_BLOCK_HEIGHT
        self.ports_ui = {}
        self._setup_ports()

    def _setup_ports(self):
        """Create and position UIPort objects based on block model."""
        # 1. Calculate the required height based on port counts
        num_inputs = len(self.model.inputs)
        num_outputs = len(self.model.outputs)
        
        # Formula: Top margin + (spacing * count) + Bottom margin
        req_height_in = UIConfig.PORT_MARGIN + (num_inputs * UIConfig.PORT_VERTICAL_SPACING)
        req_height_out = UIConfig.PORT_MARGIN + (num_outputs * UIConfig.PORT_VERTICAL_SPACING)
        
        # The block height is the Max of inputs, outputs, or the default
        self.height = max(UIConfig.DEFAULT_BLOCK_HEIGHT, req_height_in, req_height_out)

        # 2. Place Inputs (Left Side)
        y_offset = UIConfig.PORT_MARGIN
        for name in self.model.inputs:
            p = UIPort(self, self.model.inputs[name], True)
            p.setPos(-5, y_offset) 
            self.ports_ui[name] = p
            y_offset += UIConfig.PORT_VERTICAL_SPACING

        # 3. Place Outputs (Right Side)
        y_offset = UIConfig.PORT_MARGIN
        for name in self.model.outputs:
            p = UIPort(self, self.model.outputs[name], False)
            p.setPos(self.width - 5, y_offset)
            self.ports_ui[name] = p
            y_offset += UIConfig.PORT_VERTICAL_SPACING

    def boundingRect(self):
        """Bounding rect larger than the block to include text labels."""
        return QRectF(
            -UIConfig.BOUNDING_MARGIN, 
            -UIConfig.BOUNDING_MARGIN, 
            self.width + 2 * UIConfig.BOUNDING_MARGIN, 
            self.height + 2 * UIConfig.BOUNDING_MARGIN
        )

    def shape(self):
        """Collision detection only on the block body."""
        path = QPainterPath()
        path.addRoundedRect(
            0, 0, self.width, self.height, 
            UIConfig.BLOCK_CORNER_RADIUS, 
            UIConfig.BLOCK_CORNER_RADIUS
        )
        return path

    def paint(self, painter, option, widget):
        """Draw the block and its labels."""
        # 1. Draw Block Background
        painter.setBrush(QBrush(UIConfig.BLOCK_BG_COLOR))
        border_color = UIConfig.BLOCK_SELECTED_COLOR if self.isSelected() else UIConfig.BLOCK_BORDER_COLOR
        pen = QPen(border_color)
        pen.setWidth(UIConfig.BLOCK_BORDER_WIDTH)
        painter.setPen(pen)
        painter.drawRoundedRect(
            0, 0, self.width, self.height, 
            UIConfig.BLOCK_CORNER_RADIUS, 
            UIConfig.BLOCK_CORNER_RADIUS
        )

        # 2. Draw Port Names (Floating outside)
        port_font = painter.font()
        port_font.setPointSize(UIConfig.PORT_FONT_SIZE) 
        painter.setFont(port_font)
        painter.setPen(UIConfig.TEXT_COLOR) 

        # Normalize rotation
        rot = int(self.rotation()) % 360

        for name, port in self.ports_ui.items():
            painter.save()
            
            # Visual center of port
            px = port.pos().x() + UIConfig.PORT_SIZE / 2
            py = port.pos().y() + UIConfig.PORT_SIZE / 2
            
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
        title_font.setPointSize(UIConfig.TITLE_FONT_SIZE)
        title_font.setBold(True)
        painter.setFont(title_font)
        
        center = QPointF(self.width/2, self.height/2)
        painter.translate(center)
        painter.rotate(-self.rotation())
        
        painter.setPen(UIConfig.TITLE_COLOR)
        painter.drawText(
            QRectF(-self.width/2, -self.height/2, self.width, self.height), 
            Qt.AlignCenter, 
            self.model.name
        )
        painter.restore()

    def itemChange(self, change, value):
        """Called when the item moves or rotates."""
        if change == QGraphicsItem.ItemPositionChange or change == QGraphicsItem.ItemRotationHasChanged:
            self._update_attached_connections()
        return super().itemChange(change, value)

    def _update_attached_connections(self):
        """Update all connections attached to this block's ports."""
        for p in self.ports_ui.values():
            for conn in p.connections:
                try:
                    conn.points = [] 
                    conn.update_path()
                except Exception:
                    pass

    def mouseDoubleClickEvent(self, event):
        """Handle double-click to open editor or enter subsystem."""
        # Check specifically for "SubGraph" class name
        if self.model.__class__.__name__ == "SubGraph":
            # If Ctrl is pressed, skip entering subsystem -> open properties dialog
            modifiers = event.modifiers()
            if modifiers & Qt.ControlModifier:
                 pass # Fall through to open editor
            else:
                scene = self.scene()
                if scene:
                    views = scene.views()
                    if views:
                        main_window = views[0].parent() 
                        if hasattr(main_window, "enter_subsystem"):
                            main_window.enter_subsystem(self)
                            return

        # Open parameter editor if available
        if hasattr(self.model, 'get_editor_dialog'):
            editor = self.model.get_editor_dialog(None)
            if editor:
                editor.exec()
                
                # Check if ports need to be refreshed (e.g., Scope added/removed inputs)
                if hasattr(self.model, 'needs_port_refresh') and self.model.needs_port_refresh:
                    self.refresh_ports()
                    self.model.needs_port_refresh = False
                    
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
        
        # 2. Delete old port items
        for p in self.ports_ui.values():
            p.setParentItem(None)  # Removes from scene/group
        
        self.ports_ui = {}
        self._setup_ports()  # Uses the logic we wrote previously (max height etc)
        self.update()  # Redraw block

        # 3. Attempt to Reconnect
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
        """Rotate the block 90 degrees clockwise."""
        self.setTransformOriginPoint(self.width/2, self.height/2)
        current_rotation = self.rotation()
        self.setRotation(current_rotation + 90)
        self._update_attached_connections()
