"""UI representation of a connection between ports."""
import math
from PySide6.QtWidgets import QGraphicsPathItem, QGraphicsItem
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPen, QBrush, QPainterPath, QPainterPathStroker, QPolygonF
from config.ui_config import UIConfig
from .occupancy_grid import OccupancyGrid, grid_cell_size, find_orthogonal_path, simplify_nodes

# Blocks are treated as obstacles the route must clear by this many pixels.
_OBSTACLE_MARGIN = 12.0
# How far a route travels straight out from a port before anything else
# (pathfinding, detours) kicks in. Also guarantees the stub always clears
# the port's own block, since ports sit exactly on that block's edge.
_PORT_STUB = 20.0


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

        # Highlighted when either endpoint's block is selected.
        self._highlighted = False

        self.update_path(QPointF(0, 0))

    def shape(self):
        """Thicker hit detection area."""
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(UIConfig.CONNECTION_HIT_WIDTH)
        return path_stroker.createStroke(self.path())

    def boundingRect(self):
        """Padded to safely cover the arrowhead and highlighted pen width,
        both drawn outside what the plain path geometry implies."""
        margin = UIConfig.CONNECTION_WIDTH + 10
        return self.path().boundingRect().adjusted(-margin, -margin, margin, margin)

    def refresh_highlight(self):
        """Recompute highlight state from the current selection of both
        endpoint blocks (called by UIBlock when its selection changes)."""
        def block_selected(port_ui):
            parent = port_ui.parentItem() if port_ui else None
            return bool(parent and parent.isSelected())

        highlighted = block_selected(self.start_port) or block_selected(self.end_port)
        if highlighted != self._highlighted:
            self._highlighted = highlighted
            self.update()

    def paint(self, painter, option, widget=None):
        pen = QPen(self.pen)
        # Highlight when directly selected (e.g. about to be deleted) or
        # when either endpoint's block is selected (shows signal flow).
        if self._highlighted or self.isSelected():
            pen.setColor(UIConfig.BLOCK_SELECTED_COLOR)
            pen.setWidth(UIConfig.CONNECTION_WIDTH + 1)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        if self.end_port is not None and len(self.points) >= 2:
            self._draw_arrowhead(painter, pen.color())
            self._draw_fork_dot(painter)

    def _draw_fork_dot(self, painter):
        """Mark where this wire actually splits off from its siblings (if
        any), at the real divergence point rather than always at the
        source port -- Simulink's convention for a branched signal."""
        if not self.start_port or len(self.start_port.connections) < 2:
            return
        fork = self.start_port.fork_point()
        if fork is None:
            return
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))
        painter.drawEllipse(fork, 3.0, 3.0)

    def _draw_arrowhead(self, painter, color):
        """Draw a small triangular arrowhead pointing into the end port.

        Stops short of the port center by roughly the port's own radius so
        it renders just outside the (higher z-order) port circle instead
        of being fully hidden underneath it.
        """
        p_end = self.points[-1]
        p_prev = self.points[-2]
        dx = p_end.x() - p_prev.x()
        dy = p_end.y() - p_prev.y()
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return

        ux, uy = dx / length, dy / length
        perp_x, perp_y = -uy, ux
        size = 7.0
        port_radius = UIConfig.PORT_SIZE / 2.0

        tip = QPointF(p_end.x() - ux * port_radius, p_end.y() - uy * port_radius)
        back = QPointF(tip.x() - ux * size, tip.y() - uy * size)
        left = QPointF(back.x() + perp_x * size * 0.5, back.y() + perp_y * size * 0.5)
        right = QPointF(back.x() - perp_x * size * 0.5, back.y() - perp_y * size * 0.5)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPolygon(QPolygonF([tip, left, right]))

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

    def reroute_if_blocked(self):
        """If the current path now overlaps a block (e.g. one that just
        moved into it), recompute a clear route. Cheap no-op otherwise."""
        if self.end_port is None or not self.points:
            return
        obstacles = self._get_obstacle_rects()
        if obstacles and self._route_blocked(self.points, obstacles):
            self.points = []
            self.update_path()

    def _create_initial_route(self, start_pos, end_pos):
        """Orthogonal route from start_pos to end_pos that detours around
        any block bodies sitting in the way, Simulink-style.

        The direct route is tried first (cheap, and correct for the
        common unobstructed case). If something's in the way, an
        invisible occupancy grid + A* finds a clean path around every
        obstacle -- not just a single one -- falling back to a simpler
        single-detour heuristic, and finally the direct route, if the
        pathfinder can't find a way through.
        """
        direct = self._simple_route(start_pos, end_pos)
        obstacles = self._get_obstacle_rects()

        if not obstacles or not self._route_blocked(direct, obstacles):
            self.points = direct
            return

        routed = self._route_via_grid(start_pos, end_pos, obstacles)
        self.points = routed or self._route_around(start_pos, end_pos, obstacles)

    @staticmethod
    def _simple_route(start_pos, end_pos):
        """Standard 4-point orthogonal route, ignoring obstacles."""
        mid_x = (start_pos.x() + end_pos.x()) / 2.0
        if mid_x < start_pos.x() + 20:
            mid_x = start_pos.x() + 20

        return [
            QPointF(start_pos),
            QPointF(mid_x, start_pos.y()),
            QPointF(mid_x, end_pos.y()),
            QPointF(end_pos),
        ]

    def _get_obstacle_rects(self):
        """Scene-space body rect of every block, paired with the block
        itself so _route_blocked can tell whether a given rect is this
        connection's own source/destination (which is a real obstacle
        away from its port, but not right at the port where the wire is
        expected to touch it)."""
        scene = self.scene()
        if not scene:
            return []

        from .ui_block import UIBlock  # local import: avoids a circular import

        obstacles = []
        for item in scene.items():
            if isinstance(item, UIBlock):
                body = QRectF(0, 0, item.width, item.height)
                obstacles.append((item, item.mapRectToScene(body).normalized()))
        return obstacles

    def _route_blocked(self, points, obstacles, margin=_OBSTACLE_MARGIN):
        """True if any segment of `points` passes through an obstacle.

        Only the first _PORT_STUB px leaving the start port, and the last
        _PORT_STUB px arriving at the end port, are allowed to touch this
        connection's own start/end block -- the wire legitimately grazes
        that block right at its port. Everywhere else, even along that
        same first/last segment beyond the stub, its own endpoint blocks
        count as obstacles like any other. Without that distinction, a
        long first/last segment (e.g. the plain 4-point route's return
        leg on a backwards connection) could sweep across most of its own
        block's body and never get flagged.
        """
        start_block = self.start_port.parentItem() if self.start_port else None
        end_block = self.end_port.parentItem() if self.end_port else None
        last_index = len(points) - 2

        for i in range(len(points) - 1):
            p_a, p_b = points[i], points[i + 1]
            for block, rect in obstacles:
                own_start = i == 0 and block is start_block
                own_end = i == last_index and block is end_block
                if own_start or own_end:
                    seg_a, seg_b = self._clip_own_segment(p_a, p_b, port_at_a=own_start)
                    if seg_a is None:
                        continue  # entirely within the port's stub zone
                else:
                    seg_a, seg_b = p_a, p_b

                seg_rect = QRectF(seg_a, seg_b).normalized().adjusted(-margin, -margin, margin, margin)
                if seg_rect.intersects(rect):
                    return True
        return False

    @staticmethod
    def _clip_own_segment(p_a, p_b, port_at_a, stub=_PORT_STUB):
        """Shortens a segment by `stub` px from whichever end sits at its
        own block's port, so only the part beyond the stub zone gets
        obstacle-tested. Returns (None, None) if the whole segment is
        within the stub zone (nothing left to check)."""
        dx, dy = p_b.x() - p_a.x(), p_b.y() - p_a.y()
        length = math.hypot(dx, dy)
        if length <= stub:
            return None, None
        ux, uy = dx / length, dy / length
        if port_at_a:
            return QPointF(p_a.x() + ux * stub, p_a.y() + uy * stub), p_b
        return p_a, QPointF(p_b.x() - ux * stub, p_b.y() - uy * stub)

    def _route_around(self, start_pos, end_pos, obstacles, margin=_OBSTACLE_MARGIN):
        """Detour above or below whichever obstacles sit between the two
        endpoints, whichever side needs the shorter vertical detour."""
        rects = [r for _, r in obstacles]
        lo_x, hi_x = sorted((start_pos.x(), end_pos.x()))
        blocking = [r for r in rects if r.right() > lo_x and r.left() < hi_x]
        if not blocking:
            return self._simple_route(start_pos, end_pos)

        top = min(r.top() for r in blocking) - margin
        bottom = max(r.bottom() for r in blocking) + margin

        mid_y = (start_pos.y() + end_pos.y()) / 2.0
        detour_y = top if abs(mid_y - top) <= abs(mid_y - bottom) else bottom

        x_out = start_pos.x() + 20
        x_in = end_pos.x() - 20

        route = [
            QPointF(start_pos),
            QPointF(x_out, start_pos.y()),
            QPointF(x_out, detour_y),
            QPointF(x_in, detour_y),
            QPointF(x_in, end_pos.y()),
            QPointF(end_pos),
        ]

        # One extra pass: if this detour still clips something (e.g. a
        # taller obstacle further along the same band), widen using the
        # full obstacle set instead of recursing indefinitely.
        if self._route_blocked(route, obstacles, margin=1.0):
            top_all = min(r.top() for r in rects) - margin
            bottom_all = max(r.bottom() for r in rects) + margin
            detour_y = top_all if abs(mid_y - top_all) <= abs(mid_y - bottom_all) else bottom_all
            route[2].setY(detour_y)
            route[3].setY(detour_y)

        return route

    def _route_via_grid(self, start_pos, end_pos, obstacles, margin=_OBSTACLE_MARGIN):
        """Route start_pos -> end_pos through an invisible occupancy grid,
        via A*, around every obstacle in the way. Returns a clean list of
        QPointF, or None if no path could be found (caller falls back to
        the simpler single-detour heuristic).

        Ports stub straight out _PORT_STUB px before pathfinding starts:
        since a port sits exactly on its own block's edge, this guarantees
        the stub clears that block regardless of grid resolution, without
        needing any special-casing in the grid itself.
        """
        rects = [r.adjusted(-margin, -margin, margin, margin) for _, r in obstacles]

        stub_start = QPointF(start_pos.x() + _PORT_STUB, start_pos.y())
        stub_end = QPointF(end_pos.x() - _PORT_STUB, end_pos.y())

        bounds = self._grid_bounds(stub_start, stub_end, rects)
        # Only obstacles inside `bounds` are relevant to this local search.
        # Passing the rest to OccupancyGrid would be worse than a no-op:
        # an out-of-bounds rect gets column/row-clamped onto the grid's
        # edge, smearing a phantom wall across an entire boundary
        # row/column and potentially sealing off the real path.
        local_rects = [r for r in rects if r.intersects(bounds)]
        cell_size = grid_cell_size(bounds)
        grid = OccupancyGrid(bounds, local_rects, cell_size=cell_size)

        start_node = grid.nearest_free_node(stub_start)
        goal_node = grid.nearest_free_node(stub_end)
        node_path = find_orthogonal_path(grid, start_node, goal_node)

        if not node_path:
            return None

        grid_points = [grid.point_of(n) for n in simplify_nodes(node_path)]

        raw = [QPointF(start_pos), stub_start]
        raw += self._orthogonal_bridge(stub_start, grid_points[0])
        raw += grid_points
        raw += self._orthogonal_bridge(grid_points[-1], stub_end)
        raw += [stub_end, QPointF(end_pos)]

        return self._clean_polyline(raw)

    @staticmethod
    def _grid_bounds(a, b, rects, pad=80.0, max_extra_pad=260.0):
        """Bounding region for the grid: covers a and b plus any obstacle
        anywhere near the corridor between them, with maneuvering room
        around the outside. Obstacles far outside this corridor are left
        out so the grid -- and the A* search over it -- stays small and
        fast.

        The maneuvering margin scales with how big the obstacle cluster
        found near the corridor actually is: a single small block only
        needs a little room to go around, but a large cluster needs more,
        so a fixed small pad isn't enough to route around it (forcing an
        exhaustive, doomed search of a too-small region) while a fixed
        large pad would make every route -- even trivial ones -- pay for
        a needlessly big grid.
        """
        xs = [a.x(), b.x()]
        ys = [a.y(), b.y()]
        corridor = QRectF(min(xs) - pad, min(ys) - pad,
                           abs(xs[0] - xs[1]) + 2 * pad, abs(ys[0] - ys[1]) + 2 * pad)
        relevant = [r for r in rects if r.intersects(corridor)]
        for r in relevant:
            xs += [r.left(), r.right()]
            ys += [r.top(), r.bottom()]

        extra = 0.0
        if relevant:
            cluster_span = max(
                max(r.right() for r in relevant) - min(r.left() for r in relevant),
                max(r.bottom() for r in relevant) - min(r.top() for r in relevant),
            )
            extra = min(max_extra_pad, cluster_span * 0.3)

        total_pad = pad + extra
        return QRectF(min(xs) - total_pad, min(ys) - total_pad,
                       (max(xs) - min(xs)) + 2 * total_pad, (max(ys) - min(ys)) + 2 * total_pad)

    @staticmethod
    def _orthogonal_bridge(a, b):
        """Corner point(s) needed to connect a to b with only horizontal/
        vertical segments. Empty if already aligned on one axis."""
        if abs(a.x() - b.x()) < 0.5 or abs(a.y() - b.y()) < 0.5:
            return []
        return [QPointF(b.x(), a.y())]

    @staticmethod
    def _clean_polyline(points):
        """Drop consecutive duplicate points, then collapse runs of
        collinear points down to their endpoints."""
        deduped = [points[0]]
        for p in points[1:]:
            last = deduped[-1]
            if abs(p.x() - last.x()) > 0.5 or abs(p.y() - last.y()) > 0.5:
                deduped.append(p)

        if len(deduped) < 3:
            return deduped

        result = [deduped[0]]
        for i in range(1, len(deduped) - 1):
            prev, curr, nxt = result[-1], deduped[i], deduped[i + 1]
            prev_horiz = abs(prev.y() - curr.y()) < 0.5
            next_horiz = abs(curr.y() - nxt.y()) < 0.5
            prev_vert = abs(prev.x() - curr.x()) < 0.5
            next_vert = abs(curr.x() - nxt.x()) < 0.5
            if (prev_horiz and next_horiz) or (prev_vert and next_vert):
                continue  # curr is redundant, prev connects straight to nxt
            result.append(curr)
        result.append(deduped[-1])
        return result

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
