"""Execution ordering for block simulation."""
from typing import List, Dict
from ..models import BlockModel


class AlgebraicLoopError(RuntimeError):
    """Raised when the block graph has a feedback cycle with no state
    (Integrator/Delay/etc.) to break it -- i.e. block A's output this step
    depends, transitively through direct-feedthrough blocks, on its own
    output this same step. There is no well-defined order to compute such
    blocks in.
    """

    def __init__(self, blocks: List[BlockModel]):
        self.blocks = blocks
        names = ", ".join(b.params.get("BlockName", b.name) for b in blocks)
        super().__init__(
            f"Algebraic loop detected involving: {names}. "
            "Break the loop by inserting a Delay or Integrator block."
        )


class ExecutionOrdering:
    """Determines the correct order to execute blocks in a graph."""

    @staticmethod
    def topological_sort(blocks: List[BlockModel]) -> List[BlockModel]:
        """
        Returns blocks in topologically sorted order (dependencies first).

        Only wires into a port whose owning block has direct feedthrough
        (block.has_direct_feedthrough, default True) count as same-step
        dependencies for ordering purposes. A block that doesn't read its
        inputs while producing this step's output (e.g. Integrator, Delay --
        they settle new input into their state for a *later* step, via
        update_state()) doesn't force ordering on whatever feeds it, so a
        feedback loop broken by one of those is perfectly well-defined and
        sorts normally.

        Raises AlgebraicLoopError if a genuine feedthrough cycle remains
        after that -- e.g. two Gain blocks feeding each other directly,
        which has no well-defined evaluation order.
        """
        in_degree = {block: 0 for block in blocks}
        adjacency: Dict[BlockModel, List[BlockModel]] = {block: [] for block in blocks}

        for block in blocks:
            if not getattr(block, "has_direct_feedthrough", True):
                continue
            for inp in block.inputs.values():
                if inp.connected_port and inp.connected_port.owner in blocks:
                    source_block = inp.connected_port.owner
                    adjacency[source_block].append(block)
                    in_degree[block] += 1

        # Start with blocks that have no dependencies
        queue = [block for block in blocks if in_degree[block] == 0]
        sorted_blocks = []

        while queue:
            current = queue.pop(0)
            sorted_blocks.append(current)

            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(sorted_blocks) != len(blocks):
            stuck = [b for b in blocks if in_degree[b] > 0]
            raise AlgebraicLoopError(stuck)

        return sorted_blocks
