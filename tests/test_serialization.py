"""Tests for engine.serialization.GraphSerializer.deserialize_graph.

serialize_graph is exercised indirectly here by hand-building the same shape
of dict it produces, since it requires live Qt scene graphics items
(ui_block.pos(), ports_ui, etc.) that belong to the GUI layer, not the engine.
"""
import unittest

from engine.serialization import GraphSerializer
from engine.blocks.gain import Gain
from engine.blocks.constant import Constant
from engine.blocks.scope import Scope
from engine.blocks.mux import Mux


class TestDeserializeGraph(unittest.TestCase):
    def test_reconstructs_blocks_with_correct_types_and_params(self):
        data = {
            "blocks": [
                {"class": "Constant", "type": "Constant", "id": 1,
                 "position": {"x": 0, "y": 0}, "rotation": 0,
                 "params": {"Value": 5.0}},
                {"class": "Gain", "type": "Gain", "id": 2,
                 "position": {"x": 100, "y": 0}, "rotation": 0,
                 "params": {"Gain": 3.0}},
            ],
            "connections": [
                {"from_block_id": 1, "from_port": "out",
                 "to_block_id": 2, "to_port": "in", "points": []},
            ],
        }

        blocks, connections = GraphSerializer.deserialize_graph(data)

        self.assertEqual(len(blocks), 2)
        self.assertIsInstance(blocks[0], Constant)
        self.assertIsInstance(blocks[1], Gain)
        self.assertEqual(blocks[0].params["Value"], 5.0)
        self.assertEqual(blocks[1].params["Gain"], 3.0)

        self.assertEqual(len(connections), 1)
        self.assertIs(connections[0]["from_block"], blocks[0])
        self.assertIs(connections[0]["to_block"], blocks[1])
        self.assertEqual(connections[0]["from_port"], "out")
        self.assertEqual(connections[0]["to_port"], "in")

    def test_wiring_connections_reproduces_original_behavior(self):
        data = {
            "blocks": [
                {"class": "Constant", "type": "Constant", "id": "c",
                 "position": {"x": 0, "y": 0}, "rotation": 0,
                 "params": {"Value": 4.0}},
                {"class": "Gain", "type": "Gain", "id": "g",
                 "position": {"x": 0, "y": 0}, "rotation": 0,
                 "params": {"Gain": 2.0}},
            ],
            "connections": [
                {"from_block_id": "c", "from_port": "out",
                 "to_block_id": "g", "to_port": "in", "points": []},
            ],
        }
        blocks, connections = GraphSerializer.deserialize_graph(data)

        # Wiring is the caller's job (scene_manager); reproduce it here to
        # confirm the reconstructed models are actually connectable.
        for c in connections:
            src_port = c["from_block"].outputs[c["from_port"]]
            dst_port = c["to_block"].inputs[c["to_port"]]
            dst_port.connected_port = src_port

        const_block, gain_block = blocks
        const_block.compute(0.0, 0.01)
        gain_block.compute(0.0, 0.01)
        self.assertAlmostEqual(gain_block.outputs["out"].value, 8.0)

    def test_unknown_block_type_is_skipped_not_raised(self):
        data = {
            "blocks": [
                {"class": "TotallyMadeUpBlock", "type": "TotallyMadeUpBlock", "id": 1,
                 "position": {"x": 0, "y": 0}, "rotation": 0, "params": {}},
            ],
            "connections": [],
        }
        blocks, connections = GraphSerializer.deserialize_graph(data)
        self.assertEqual(blocks, [])

    def test_connection_referencing_missing_block_is_dropped(self):
        data = {
            "blocks": [
                {"class": "Gain", "type": "Gain", "id": 1,
                 "position": {"x": 0, "y": 0}, "rotation": 0, "params": {}},
            ],
            "connections": [
                {"from_block_id": 1, "from_port": "out",
                 "to_block_id": "does-not-exist", "to_port": "in", "points": []},
            ],
        }
        blocks, connections = GraphSerializer.deserialize_graph(data)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(connections, [])

    def test_subgraph_internal_data_is_restored_and_ports_synced(self):
        data = {
            "blocks": [
                {"class": "SubGraph", "type": "SubGraph", "id": 1,
                 "position": {"x": 0, "y": 0}, "rotation": 0,
                 "params": {"BlockName": "MySG", "Execution Mode": "Standard"},
                 "internal_blocks_data": [
                     {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
                     {"id": "out1", "type": "OutputPort", "params": {"PortName": "Out"}},
                 ],
                 "internal_connections_data": [
                     {"from_block_id": "in1", "from_port": "out",
                      "to_block_id": "out1", "to_port": "in"},
                 ]},
            ],
            "connections": [],
        }
        blocks, _ = GraphSerializer.deserialize_graph(data)
        sg = blocks[0]
        self.assertEqual(sg.__class__.__name__, "SubGraph")
        # refresh_io_ports (called by deserialize_graph) should have synced ports.
        self.assertIn("In", sg.inputs)
        self.assertIn("Out", sg.outputs)

    def test_scope_with_extra_inputs_restores_all_ports_on_load(self):
        # Regression test: Scope.num_inputs used to be a plain attribute,
        # never part of params, so a Scope saved with >1 input silently lost
        # its extra ports (and their connections) on reload. NumInputs is
        # now a real param, and deserialize_graph must call refresh_io_ports()
        # unconditionally (not just when internal_blocks_data is present,
        # which is SubGraph-specific) for this to actually restore the ports.
        data = {
            "blocks": [
                {"class": "Scope", "type": "Scope", "id": 1,
                 "position": {"x": 0, "y": 0}, "rotation": 0,
                 "params": {"NumInputs": 5}},
            ],
            "connections": [],
        }
        blocks, _ = GraphSerializer.deserialize_graph(data)
        scope = blocks[0]
        self.assertIsInstance(scope, Scope)
        self.assertEqual(sorted(scope.inputs.keys()), [f"in{i}" for i in range(1, 6)])
        self.assertEqual(scope.num_inputs, 5)

    def test_mux_with_extra_inputs_and_connections_restores_on_load(self):
        data = {
            "blocks": [
                {"class": "Constant", "type": "Constant", "id": 1,
                 "position": {"x": 0, "y": 0}, "rotation": 0,
                 "params": {"Value": 9.0}},
                {"class": "Mux", "type": "Mux", "id": 2,
                 "position": {"x": 100, "y": 0}, "rotation": 0,
                 "params": {"NumInputs": 4}},
            ],
            "connections": [
                {"from_block_id": 1, "from_port": "out",
                 "to_block_id": 2, "to_port": "in3", "points": []},
            ],
        }
        blocks, connections = GraphSerializer.deserialize_graph(data)
        mux = blocks[1]
        self.assertIsInstance(mux, Mux)
        self.assertEqual(sorted(mux.inputs.keys()), [f"in{i}" for i in range(1, 5)])
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0]["to_port"], "in3")


class _FakePos:
    """Duck-types QPointF's .x()/.y() for annotation serialization tests
    without needing a live QApplication -- see module docstring."""
    def __init__(self, x, y):
        self._x, self._y = x, y

    def x(self):
        return self._x

    def y(self):
        return self._y


class _FakeAnnotation:
    """Duck-types UIAnnotation's .toPlainText()/.pos() for the same reason."""
    def __init__(self, text, x, y):
        self._text = text
        self._pos = _FakePos(x, y)

    def toPlainText(self):
        return self._text

    def pos(self):
        return self._pos


class TestAnnotations(unittest.TestCase):
    def test_serialize_and_deserialize_round_trip(self):
        fake = _FakeAnnotation("Remember to tune Kp", 120.0, 45.0)
        data = GraphSerializer.serialize_graph([], [fake])
        self.assertIn("annotations", data)

        annotations = GraphSerializer.deserialize_annotations(data)
        self.assertEqual(len(annotations), 1)
        self.assertEqual(annotations[0]["text"], "Remember to tune Kp")
        self.assertEqual(annotations[0]["x"], 120.0)
        self.assertEqual(annotations[0]["y"], 45.0)

    def test_serialize_without_annotations_omits_key(self):
        # Backward compatibility: callers not passing annotations_ui (or
        # passing an empty list) produce a dict with no "annotations" key,
        # so old save files stay byte-for-byte the same shape.
        data = GraphSerializer.serialize_graph([])
        self.assertNotIn("annotations", data)


class TestSimulationParams(unittest.TestCase):
    def test_serialize_and_deserialize_round_trip(self):
        data = GraphSerializer.serialize_graph([], sim_params={"duration": 5.0, "dt": 0.02, "solver": "rk4"})
        self.assertIn("simulation", data)

        params = GraphSerializer.deserialize_simulation_params(data)
        self.assertEqual(params, {"duration": 5.0, "dt": 0.02, "solver": "rk4"})

    def test_serialize_without_sim_params_omits_key(self):
        # Backward compatibility: same rationale as annotations above -- old
        # save files (and any caller not passing sim_params) stay unaffected.
        data = GraphSerializer.serialize_graph([])
        self.assertNotIn("simulation", data)

    def test_deserialize_sim_params_defaults_to_empty_when_key_missing(self):
        # Old save files (no "simulation" key) must load cleanly, and the
        # caller (scene_manager) is expected to leave current toolbar values
        # untouched when this comes back empty.
        self.assertEqual(GraphSerializer.deserialize_simulation_params({}), {})

    def test_deserialize_annotations_defaults_to_empty_when_key_missing(self):
        # Old save files (no "annotations" key at all) must load cleanly.
        self.assertEqual(GraphSerializer.deserialize_annotations({}), [])


if __name__ == "__main__":
    unittest.main()
