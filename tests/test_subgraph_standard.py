"""Tests for SubGraph's synchronous 'Standard' execution mode: I/O bridging and
variable substitution ($VarName). Threaded/Audio async modes are covered in
test_threaded_subgraph.py.
"""
import unittest

from engine.blocks.subgraph import SubGraph


class TestSubGraphStandardMode(unittest.TestCase):
    def _build_gain_subgraph(self, gain_value=2.0):
        sg = SubGraph()
        sg.params["Execution Mode"] = "Standard"

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

    def test_variable_substitution_seeds_default_and_applies_to_internal_params(self):
        sg = SubGraph()
        sg.params["Execution Mode"] = "Standard"
        sg.internal_blocks_data = [
            {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "gain1", "type": "Gain", "params": {"Gain": "$MyGain"}},
            {"id": "out1", "type": "OutputPort", "params": {"PortName": "Out"}},
        ]
        sg.internal_connections_data = [
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "gain1", "to_port": "in"},
            {"from_block_id": "gain1", "from_port": "out", "to_block_id": "out1", "to_port": "in"},
        ]
        sg.sync_ports_from_data()

        # reset() should have discovered "$MyGain" and seeded a default parameter.
        sg.reset()
        self.assertIn("MyGain", sg.params)

        # Explicitly set the variable and confirm it substitutes into the internal Gain.
        sg.params["MyGain"] = 4.0
        sg.reset()
        sg.inputs["In"].value = 2.0
        sg.compute(0.0, 0.01)
        self.assertAlmostEqual(sg.outputs["Out"].value, 8.0)

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
