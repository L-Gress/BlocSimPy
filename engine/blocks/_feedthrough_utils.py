"""Static (no-simulation-run-needed) feedthrough analysis over a SubGraph's
serialized internal_blocks_data/internal_connections_data, used by
SubGraph.feedthrough_pairs()/has_direct_feedthrough (see subgraph.py).

Why this exists: ExecutionOrdering.topological_sort (engine/simulation/
executor.py) only adds a same-step dependency edge for a specific
input->output pair that actually has feedthrough AND whose output is
actually read by something else in the diagram. SubGraph used to report a
single block-wide True, which meant ANY feedback loop closed through a
subsystem was flagged as an unresolvable algebraic loop even when it was
genuinely broken by internal dynamics (an Integrator, Delay, or
strictly-proper TransferFunction/StateSpace one level down) -- and even
after making that per-input-port, a single unrelated feedthrough output
(e.g. a diagnostic tap straight off a controller, unused anywhere) still
made the whole input look coupled. Both were real false positives on real
diagrams; per-(input,output)-pair analysis, combined with topological_sort
only caring about pairs whose output is actually consumed, fixes both.
"""


def block_has_feedthrough(block_data):
    """Best-effort feedthrough check for one serialized (not-yet-live)
    internal block dict ({"type"/"class", "params", ...}).

    Reuses each block class's own real has_direct_feedthrough rather than
    duplicating its logic here: most block kinds declare it as a plain
    class attribute (True/False, e.g. Gain vs. Integrator/Delay), readable
    straight off the class with no instantiation. A few kinds (TransferFunction,
    StateSpace, DiscreteTransferFunction, SubGraph itself) compute it live
    from their current coefficients/matrices/internal structure -- those are
    declared as a `@property`, detected here via isinstance(attr, property),
    and only THOSE get a throwaway instance constructed (with the block's
    serialized params applied) so the real, correct logic runs.

    This stays a coarse per-BLOCK boolean (not per-pair) for the internal
    graph traversal -- refining that further (e.g. for a nested SubGraph)
    would be diminishing returns; the precision that actually matters for
    the false positives this module exists to fix is applied at the
    top-level SubGraph boundary in feedthrough_pairs() below.
    """
    from ..blocks import BLOCK_REGISTRY  # local import: avoids a circular import at module load time

    block_type = block_data.get("type") or block_data.get("class")
    cls = BLOCK_REGISTRY.get(block_type)
    if cls is None:
        return True  # unknown block kind: conservative default, matches BlockModel's own default

    attr = getattr(cls, "has_direct_feedthrough", True)
    if not isinstance(attr, property):
        return bool(attr)

    try:
        instance = cls()
        instance.params.update(block_data.get("params", {}))
        if block_type == "SubGraph":
            instance.internal_blocks_data = block_data.get("internal_blocks_data", [])
            instance.internal_connections_data = block_data.get("internal_connections_data", [])
        return bool(instance.has_direct_feedthrough)
    except Exception:
        return True  # malformed/unparseable params: conservative default


def feedthrough_pairs(internal_blocks_data, internal_connections_data):
    """{external_output_PortName: {external_input_PortNames with a
    feedthrough-only path to it}}, keyed by PortName (matching
    SubGraph.inputs/outputs' dict keys -- see sync_ports_from_data).

    Deliberately per-(input,output)-PAIR, not a single "does this subgraph
    have feedthrough at all" boolean or even a per-input-only set: a
    container can easily have some input/output pairs coupled and others
    not (e.g. one output driven through a strictly-proper TF, another --
    an unrelated diagnostic tap -- driven straight through an algebraic
    path). topological_sort combines this with which specific outputs are
    actually consumed elsewhere in the diagram, so an unused output's
    feedthrough can't force a same-step ordering (and potentially a false
    algebraic-loop error) on an input that, for every output anyone
    actually reads, is properly state-broken.
    """
    if not internal_blocks_data:
        return {}

    feedthrough_by_id = {b.get("id"): block_has_feedthrough(b) for b in internal_blocks_data}

    adjacency = {}
    for conn in internal_connections_data:
        to_id = conn.get("to_block_id")
        if feedthrough_by_id.get(to_id, True):
            adjacency.setdefault(conn.get("from_block_id"), []).append(to_id)

    output_ports = [b for b in internal_blocks_data if b.get("type") == "OutputPort"]
    input_ports = [b for b in internal_blocks_data if b.get("type") == "InputPort"]
    output_id_to_name = {b.get("id"): b.get("params", {}).get("PortName") for b in output_ports}
    output_ids = set(output_id_to_name.keys())

    result = {name: set() for name in output_id_to_name.values()}

    for ip in input_ports:
        in_name = ip.get("params", {}).get("PortName")
        visited = set()
        stack = [ip.get("id")]
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            if current in output_ids:
                result[output_id_to_name[current]].add(in_name)
                # An OutputPort is a sink in practice, but keep traversing
                # its own adjacency (if any) too -- harmless, guarded by
                # `visited`, and avoids assuming a structural invariant
                # that isn't actually enforced anywhere.
            stack.extend(adjacency.get(current, []))

    return result
