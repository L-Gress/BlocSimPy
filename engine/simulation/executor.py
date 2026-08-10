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

        A same-step dependency edge is only added for a wire feeding a
        SPECIFIC input port that has a feedthrough path to a SPECIFIC output
        port that is itself actually read by something else in this diagram
        (see BlockModel.feedthrough_pairs). A block that doesn't read a
        given input while producing a given output (e.g. Integrator/Delay's
        sole input, for their sole output -- it's settled into state for a
        *later* step, via update_state()) doesn't force ordering on
        whatever feeds THAT port, so a feedback loop broken by one of those
        is perfectly well-defined and sorts normally.

        This is deliberately per-(input,output)-PAIR, and restricted to
        outputs that are actually consumed -- not a single per-block flag,
        and not even just per-input: a container (SubGraph) can easily have
        some input/output pairs coupled and others not (e.g. one output
        driven through a strictly-proper TransferFunction, another -- an
        unrelated diagnostic tap -- driven straight through an algebraic
        path). Collapsing that to one block-wide boolean (or even a
        per-input one that ignores whether the coupled output matters)
        caused real false positives on exactly that diagram shape.

        Pure sinks (blocks with NO output ports at all, e.g. Scope,
        AudioOutput) can never legitimately be PART of a cycle -- nothing
        can ever depend on a sink's output, since it doesn't have one. So:
        first try ordering with sink consumption counted normally (so an
        ordinary source -> ... -> Scope chain still gets sources-first
        ordering). If THAT reveals a cycle, retry with sink consumption
        excluded -- a cycle that only appears because something started
        watching an otherwise-unused output (e.g. wiring a Scope to a
        subsystem's diagnostic tap) is not a real requirement, and a sink
        degrading to best-effort (possibly one-step-stale) freshness in
        that one spot is far better than refusing to run the whole
        simulation. A cycle that persists even with sinks fully excluded is
        a genuine algebraic loop among the core (non-sink) blocks and is
        raised as such.
        """
        sinks = [block for block in blocks if not block.outputs]
        non_sinks = [block for block in blocks if block.outputs]

        try:
            return ExecutionOrdering._sort_core_then_place_sinks(
                blocks, sinks, non_sinks, count_sink_consumers=True
            )
        except AlgebraicLoopError:
            return ExecutionOrdering._sort_core_then_place_sinks(
                blocks, sinks, non_sinks, count_sink_consumers=False
            )

    @staticmethod
    def _sort_core_then_place_sinks(blocks, sinks, non_sinks, count_sink_consumers):
        in_degree = {block: 0 for block in non_sinks}
        adjacency: Dict[BlockModel, List[BlockModel]] = {block: [] for block in non_sinks}

        # Which of each non-sink block's OWN output ports are actually read
        # elsewhere in this diagram. Whether sink (Scope/AudioOutput/...)
        # consumers count is the one thing that differs between the two
        # passes described above.
        consumed_outputs: Dict[BlockModel, set] = {block: set() for block in non_sinks}
        reader_blocks = blocks if count_sink_consumers else non_sinks
        for block in reader_blocks:
            for inp in block.inputs.values():
                src = inp.connected_port
                if src is not None and src.owner in in_degree:
                    consumed_outputs[src.owner].add(src.name)

        for block in non_sinks:
            pairs = block.feedthrough_pairs()
            needed_inputs = set()
            for output_name in consumed_outputs[block]:
                needed_inputs |= pairs.get(output_name, set())

            for input_name in needed_inputs:
                inp = block.inputs.get(input_name)
                if inp is not None and inp.connected_port and inp.connected_port.owner in in_degree:
                    source_block = inp.connected_port.owner
                    adjacency[source_block].append(block)
                    in_degree[block] += 1

        # Kahn's algorithm over the CORE (non-sink) graph only.
        queue = [block for block in non_sinks if in_degree[block] == 0]
        sorted_blocks = []

        while queue:
            current = queue.pop(0)
            sorted_blocks.append(current)

            for neighbor in adjacency[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_blocks) != len(non_sinks):
            stuck = [b for b in non_sinks if in_degree[b] > 0]
            raise AlgebraicLoopError(stuck)

        # Slot each sink in right after the last of its own feedthrough
        # sources in the core order -- best-effort freshness, never
        # blocking (a sink can't be part of a cycle by construction). A
        # sink with no connected/feedthrough sources just goes at the end.
        position = {block: i for i, block in enumerate(sorted_blocks)}
        for sink in sinks:
            needed_inputs = set(sink.inputs.keys()) if sink.has_direct_feedthrough else set()
            insert_after = -1
            for input_name in needed_inputs:
                inp = sink.inputs.get(input_name)
                if inp is not None and inp.connected_port and inp.connected_port.owner in position:
                    insert_after = max(insert_after, position[inp.connected_port.owner])
            sorted_blocks.insert(insert_after + 1, sink)
            position = {block: i for i, block in enumerate(sorted_blocks)}

        return sorted_blocks
