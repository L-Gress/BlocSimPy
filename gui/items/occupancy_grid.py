"""Invisible occupancy-grid pathfinder for orthogonal connection routing.

Purely an internal computation aid: a lattice of nodes is laid over the
region between a connection's two endpoints, nodes falling inside a block
body are marked occupied, and A* finds the shortest turn-minimizing path
through the free nodes. None of this is ever drawn -- UIConnection only
uses the resulting waypoints.
"""
import heapq
from PySide6.QtCore import QPointF, QRectF

DEFAULT_CELL_SIZE = 20.0
# Safety cap on node count; cell_size grows beyond DEFAULT_CELL_SIZE to
# stay under this. A* over this many (col, row, direction) states runs in
# comfortably interactive time; typical small/medium diagrams stay well
# under this and keep the finer default resolution regardless.
MAX_GRID_CELLS = 2000
TURN_PENALTY = 3.0
_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


class OccupancyGrid:
    """A lattice of nodes spaced `cell_size` apart over a rectangular
    region. A node is occupied if it falls inside any obstacle rect."""

    def __init__(self, bounds: QRectF, obstacle_rects, cell_size=DEFAULT_CELL_SIZE):
        self.origin_x = bounds.left()
        self.origin_y = bounds.top()
        self.cell_size = max(1.0, cell_size)
        self.cols = max(1, int(bounds.width() // self.cell_size) + 2)
        self.rows = max(1, int(bounds.height() // self.cell_size) + 2)

        self._occupied = [[False] * self.rows for _ in range(self.cols)]
        for rect in obstacle_rects:
            self._mark_rect(rect)

    def _mark_rect(self, rect: QRectF):
        c0 = self._clamp_col(self._col_of(rect.left()))
        c1 = self._clamp_col(self._col_of(rect.right()))
        r0 = self._clamp_row(self._row_of(rect.top()))
        r1 = self._clamp_row(self._row_of(rect.bottom()))
        for c in range(c0, c1 + 1):
            column = self._occupied[c]
            for r in range(r0, r1 + 1):
                column[r] = True

    def _col_of(self, x):
        return int(round((x - self.origin_x) / self.cell_size))

    def _row_of(self, y):
        return int(round((y - self.origin_y) / self.cell_size))

    def _clamp_col(self, c):
        return max(0, min(self.cols - 1, c))

    def _clamp_row(self, r):
        return max(0, min(self.rows - 1, r))

    def point_of(self, node):
        c, r = node
        return QPointF(self.origin_x + c * self.cell_size, self.origin_y + r * self.cell_size)

    def in_bounds(self, node):
        c, r = node
        return 0 <= c < self.cols and 0 <= r < self.rows

    def is_free(self, node):
        return self.in_bounds(node) and not self._occupied[node[0]][node[1]]

    def nearest_free_node(self, point, max_radius=8):
        """Nearest free lattice node to `point`; spirals outward if the
        naive rounded node is occupied (or off-grid). Best-effort fallback
        to the naive node if nothing free is found within max_radius."""
        c0 = self._clamp_col(self._col_of(point.x()))
        r0 = self._clamp_row(self._row_of(point.y()))
        if self.is_free((c0, r0)):
            return (c0, r0)
        for radius in range(1, max_radius + 1):
            for dc in range(-radius, radius + 1):
                for dr in range(-radius, radius + 1):
                    if max(abs(dc), abs(dr)) != radius:
                        continue
                    node = (c0 + dc, r0 + dr)
                    if self.is_free(node):
                        return node
        return (c0, r0)


def grid_cell_size(bounds: QRectF, base=DEFAULT_CELL_SIZE, max_cells=MAX_GRID_CELLS):
    """Cell size to use for `bounds`, growing beyond `base` only if needed
    to keep the total node count under `max_cells`."""
    cols = max(1.0, bounds.width() / base)
    rows = max(1.0, bounds.height() / base)
    total = cols * rows
    if total <= max_cells:
        return base
    return base * (total / max_cells) ** 0.5


MAX_EXPANSIONS = 6000  # worst-case bound: a maze needing more than this
# falls back to the caller's simpler heuristic instead of stalling the UI.


def find_orthogonal_path(grid: OccupancyGrid, start_node, goal_node, max_expansions=MAX_EXPANSIONS):
    """A* search from start_node to goal_node over free grid nodes only,
    moving in 4 directions. Turning costs extra so paths stay straight
    where possible. Returns a list of (col, row) nodes, or None if the
    goal is unreachable within `max_expansions` node expansions (a
    latency bound -- pathological mazes give up rather than freezing the
    interactive drag that triggered them)."""
    if start_node == goal_node:
        return [start_node]
    if not grid.is_free(start_node) or not grid.is_free(goal_node):
        return None

    def heuristic(node):
        return abs(node[0] - goal_node[0]) + abs(node[1] - goal_node[1])

    start_state = (start_node, None)
    g_score = {start_state: 0.0}
    came_from = {}
    counter = 0
    open_heap = [(heuristic(start_node), counter, start_state)]
    expansions = 0

    while open_heap:
        if expansions >= max_expansions:
            return None
        expansions += 1

        f, _, state = heapq.heappop(open_heap)
        node, direction = state

        # Skip stale heap entries superseded by a cheaper path already found.
        if f > g_score.get(state, float("inf")) + heuristic(node) + 1e-9:
            continue

        if node == goal_node:
            return _reconstruct(came_from, state, start_state)

        for d in _DIRECTIONS:
            neighbor = (node[0] + d[0], node[1] + d[1])
            if not grid.is_free(neighbor):
                continue
            step_cost = 1.0 if (direction is None or d == direction) else 1.0 + TURN_PENALTY
            new_state = (neighbor, d)
            tentative_g = g_score[state] + step_cost
            if tentative_g < g_score.get(new_state, float("inf")):
                g_score[new_state] = tentative_g
                came_from[new_state] = state
                counter += 1
                heapq.heappush(open_heap, (tentative_g + heuristic(neighbor), counter, new_state))

    return None


def _reconstruct(came_from, end_state, start_state):
    path = [end_state]
    state = end_state
    while state != start_state:
        state = came_from[state]
        path.append(state)
    path.reverse()
    return [s[0] for s in path]


def simplify_nodes(nodes):
    """Collapse consecutive collinear nodes into corner-only waypoints."""
    if len(nodes) < 3:
        return list(nodes)
    result = [nodes[0]]
    for i in range(1, len(nodes) - 1):
        prev, curr, nxt = nodes[i - 1], nodes[i], nodes[i + 1]
        if (curr[0] - prev[0], curr[1] - prev[1]) != (nxt[0] - curr[0], nxt[1] - curr[1]):
            result.append(curr)
    result.append(nodes[-1])
    return result
