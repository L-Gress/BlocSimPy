"""Tests for SubGraph's synchronous execution: I/O bridging and variable
binding (see engine/variables.py -- an internal block's param can be bound
to a name declared in the global variable store, the same mechanism a
top-level block's param uses).
"""
import unittest

from engine.blocks.subgraph import SubGraph
from engine.variables import make_variable_ref, set_active_variables, get_active_variables


class TestSubGraphStandardMode(unittest.TestCase):
    def _build_gain_subgraph(self, gain_value=2.0):
        sg = SubGraph()

        sg.internal_blocks_data = [
            {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "gain1", "type": "Gain", "params": {"Gain": gain_value}},
            {"id": "out1", "type": "OutputPort", "params": {"PortName": "Out"}},
        ]
        sg.internal_connections_data = [
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "gain1", "to_port": "in"},
            {"from_block_id": "gain1", "from_port": "out", "to_block_id": "out1", "to_port": "in"},
        ]
        sg.sync_ports_from_data()
        return sg

    def test_ports_synced_from_internal_data(self):
        sg = self._build_gain_subgraph()
        self.assertIn("In", sg.inputs)
        self.assertIn("Out", sg.outputs)

    def test_has_direct_feedthrough_true_for_pure_algebraic_subgraph(self):
        # A plain Gain passthrough has no state -- the output combinatorially
        # depends on the input, so this subgraph must be treated as having
        # direct feedthrough (same as any ordinary algebraic block).
        sg = self._build_gain_subgraph()
        self.assertTrue(sg.has_direct_feedthrough)

    def test_has_direct_feedthrough_false_when_broken_by_integrator(self):
        sg = SubGraph()
        sg.internal_blocks_data = [
            {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "integ1", "type": "Integrator", "params": {}},
            {"id": "out1", "type": "OutputPort", "params": {"PortName": "Out"}},
        ]
        sg.internal_connections_data = [
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "integ1", "to_port": "in"},
            {"from_block_id": "integ1", "from_port": "out", "to_block_id": "out1", "to_port": "in"},
        ]
        sg.sync_ports_from_data()
        self.assertFalse(sg.has_direct_feedthrough)

    def test_has_direct_feedthrough_false_for_strictly_proper_transfer_function(self):
        # Regression test: a SubGraph wrapping a strictly-proper TF (D == 0,
        # e.g. TransferFunction's own default 1/(s+1)) must NOT report
        # direct feedthrough -- this used to be unconditionally True,
        # which flagged the common pattern of closing a feedback loop
        # through a subsystem (a "plant" modeled as its own subgraph) as an
        # unresolvable algebraic loop, even though the loop was genuinely
        # broken by the TF's own internal dynamics.
        sg = SubGraph()
        sg.internal_blocks_data = [
            {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "tf1", "type": "TransferFunction",
             "params": {"Numerator": [1.0], "Denominator": [1.0, 1.0]}},
            {"id": "out1", "type": "OutputPort", "params": {"PortName": "Out"}},
        ]
        sg.internal_connections_data = [
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "tf1", "to_port": "in"},
            {"from_block_id": "tf1", "from_port": "out", "to_block_id": "out1", "to_port": "in"},
        ]
        sg.sync_ports_from_data()
        self.assertFalse(sg.has_direct_feedthrough)

    def test_has_direct_feedthrough_true_for_proper_transfer_function(self):
        sg = SubGraph()
        sg.internal_blocks_data = [
            {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "tf1", "type": "TransferFunction",
             "params": {"Numerator": [1.0, 1.0], "Denominator": [1.0, 1.0]}},  # D != 0
            {"id": "out1", "type": "OutputPort", "params": {"PortName": "Out"}},
        ]
        sg.internal_connections_data = [
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "tf1", "to_port": "in"},
            {"from_block_id": "tf1", "from_port": "out", "to_block_id": "out1", "to_port": "in"},
        ]
        sg.sync_ports_from_data()
        self.assertTrue(sg.has_direct_feedthrough)

    def test_feedthrough_pairs_distinguishes_coupled_from_unrelated_output(self):
        # Regression test: a SubGraph with TWO outputs -- one reached only
        # through a strictly-proper TF (state-broken), the other an
        # unrelated diagnostic tap fed straight (algebraically) off the
        # same input -- must report feedthrough for ONLY the pair that's
        # actually coupled, not treat every input as feedthrough to every
        # output just because ONE output happens to be reachable.
        sg = SubGraph()
        sg.internal_blocks_data = [
            {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "tf1", "type": "TransferFunction",
             "params": {"Numerator": [1.0], "Denominator": [1.0, 1.0]}},  # D == 0
            {"id": "out_main", "type": "OutputPort", "params": {"PortName": "MainOut"}},
            {"id": "out_diag", "type": "OutputPort", "params": {"PortName": "DiagOut"}},
        ]
        sg.internal_connections_data = [
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "tf1", "to_port": "in"},
            {"from_block_id": "tf1", "from_port": "out", "to_block_id": "out_main", "to_port": "in"},
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "out_diag", "to_port": "in"},  # straight algebraic tap
        ]
        sg.sync_ports_from_data()

        pairs = sg.feedthrough_pairs()
        self.assertEqual(pairs["MainOut"], set())
        self.assertEqual(pairs["DiagOut"], {"In"})
        # Coarse flag still True (SOME output is coupled) -- topological_sort
        # uses the precise per-pair version above, not this.
        self.assertTrue(sg.has_direct_feedthrough)

    def test_feedthrough_cache_invalidates_when_internal_data_changes(self):
        sg = self._build_gain_subgraph()
        self.assertTrue(sg.has_direct_feedthrough)

        sg.internal_blocks_data = [
            {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "integ1", "type": "Integrator", "params": {}},
            {"id": "out1", "type": "OutputPort", "params": {"PortName": "Out"}},
        ]
        sg.internal_connections_data = [
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "integ1", "to_port": "in"},
            {"from_block_id": "integ1", "from_port": "out", "to_block_id": "out1", "to_port": "in"},
        ]
        self.assertFalse(sg.has_direct_feedthrough)

    def test_standard_mode_bridges_input_to_output_through_internal_graph(self):
        sg = self._build_gain_subgraph(gain_value=3.0)
        sg.reset()

        sg.inputs["In"].value = 5.0
        sg.compute(0.0, 0.01)

        self.assertAlmostEqual(sg.outputs["Out"].value, 15.0)

    def test_standard_mode_updates_when_input_changes(self):
        sg = self._build_gain_subgraph(gain_value=2.0)
        sg.reset()

        sg.inputs["In"].value = 1.0
        sg.compute(0.0, 0.01)
        self.assertAlmostEqual(sg.outputs["Out"].value, 2.0)

        sg.inputs["In"].value = 10.0
        sg.compute(0.1, 0.01)
        self.assertAlmostEqual(sg.outputs["Out"].value, 20.0)

    def test_internal_block_param_resolves_against_global_variables(self):
        # An internal block's param bound via make_variable_ref() (typing a
        # name into a param editor / var() in a script) resolves against the SAME global
        # variable store any top-level block would -- not a private
        # per-SubGraph table -- read fresh via get_active_variables() every
        # reset() (see _instantiate_internal_blocks()).
        saved = get_active_variables()
        try:
            set_active_variables({})
            sg = SubGraph()
            sg.internal_blocks_data = [
                {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
                {"id": "gain1", "type": "Gain", "params": {"Gain": make_variable_ref("MyGain")}},
                {"id": "out1", "type": "OutputPort", "params": {"PortName": "Out"}},
            ]
            sg.internal_connections_data = [
                {"from_block_id": "in1", "from_port": "out", "to_block_id": "gain1", "to_port": "in"},
                {"from_block_id": "gain1", "from_port": "out", "to_block_id": "out1", "to_port": "in"},
            ]
            sg.sync_ports_from_data()

            # Undeclared: resolve_params() leaves the reference in place
            # rather than crashing or silently defaulting to 0.0 (pre-flight
            # validation -- see SimulationEngine.check_diagram_detailed() --
            # is what's expected to catch this before a real run).
            sg.reset()
            sg.inputs["In"].value = 2.0
            sg.compute(0.0, 0.01)
            self.assertAlmostEqual(sg.outputs["Out"].value, 0.0)

            # Declaring the variable and re-running picks up its value.
            get_active_variables()["MyGain"] = 4.0
            sg.reset()
            sg.inputs["In"].value = 2.0
            sg.compute(0.0, 0.01)
            self.assertAlmostEqual(sg.outputs["Out"].value, 8.0)

            # The SubGraph's OWN params (the design-time internal_blocks_data
            # entry) are untouched by resolution -- still the reference, not
            # a baked-in number -- so editing the variable and re-running
            # again picks up the NEW value too.
            get_active_variables()["MyGain"] = 10.0
            sg.reset()
            sg.compute(0.0, 0.01)
            self.assertAlmostEqual(sg.outputs["Out"].value, 20.0)
        finally:
            set_active_variables(saved)

    def test_nested_subgraph_computes_without_ever_being_entered(self):
        # Regression test: a SubGraph nested INSIDE another SubGraph must
        # compute correctly on reset()/compute() alone, with no prior UI
        # step of "entering" it to populate live scene state. Previously,
        # _instantiate_internal_blocks() constructed a fresh nested
        # SubGraph instance via BLOCK_REGISTRY but never copied the design-time
        # internal_blocks_data/internal_connections_data (or refreshed its
        # ports) onto it before calling reset() -- so the nested instance
        # always instantiated ZERO execution_blocks and silently produced
        # 0.0 instead of the expected value.
        inner = SubGraph()
        inner.internal_blocks_data = [
            {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "gain1", "type": "Gain", "params": {"Gain": 2.0}},
            {"id": "out1", "type": "OutputPort", "params": {"PortName": "Out"}},
        ]
        inner.internal_connections_data = [
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "gain1", "to_port": "in"},
            {"from_block_id": "gain1", "from_port": "out", "to_block_id": "out1", "to_port": "in"},
        ]

        outer = SubGraph()
        outer.internal_blocks_data = [
            {"id": "oin1", "type": "InputPort", "params": {"PortName": "In"}},
            {
                "id": "nested1", "type": "SubGraph", "params": {},
                "internal_blocks_data": inner.internal_blocks_data,
                "internal_connections_data": inner.internal_connections_data,
            },
            {"id": "oout1", "type": "OutputPort", "params": {"PortName": "Out"}},
        ]
        outer.internal_connections_data = [
            {"from_block_id": "oin1", "from_port": "out", "to_block_id": "nested1", "to_port": "In"},
            {"from_block_id": "nested1", "from_port": "Out", "to_block_id": "oout1", "to_port": "in"},
        ]
        outer.sync_ports_from_data()

        # No enter_subsystem()/exit round-trip anywhere -- straight to reset().
        outer.reset()
        outer.inputs["In"].value = 5.0
        outer.compute(0.0, 0.01)

        self.assertAlmostEqual(outer.outputs["Out"].value, 10.0)

    def test_reset_reinstantiates_internal_blocks(self):
        sg = self._build_gain_subgraph()
        sg.reset()
        first_gen = sg.execution_blocks
        sg.reset()
        second_gen = sg.execution_blocks
        # Distinct instances after each reset (internal graph rebuilt).
        self.assertIsNot(first_gen, second_gen)
        self.assertEqual(len(second_gen), len(first_gen))


if __name__ == "__main__":
    unittest.main()
