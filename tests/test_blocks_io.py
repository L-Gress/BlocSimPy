"""Unit tests for I/O and structural blocks: Scope, InputPort/OutputPort."""
import unittest
import numpy as np

from engine.blocks.scope import Scope
from engine.blocks.input_port import InputPort
from engine.blocks.output_port import OutputPort


class TestScope(unittest.TestCase):
    def test_records_time_and_value_data(self):
        s = Scope()
        for i, t in enumerate([0.0, 0.1, 0.2]):
            s.inputs["in1"].value = float(i)
            s.compute(t, 0.1)

        self.assertEqual(s.time_data, [0.0, 0.1, 0.2])
        self.assertEqual(s.value_data, [0.0, 1.0, 2.0])

    def test_multiple_inputs_recorded_independently(self):
        s = Scope()
        s.add_input("in2")
        s.num_inputs = 2

        s.inputs["in1"].value = 1.0
        s.inputs["in2"].value = 2.0
        s.compute(0.0, 0.1)

        self.assertEqual(s.input_data["in1"], [1.0])
        self.assertEqual(s.input_data["in2"], [2.0])

    def test_reset_clears_stored_data(self):
        s = Scope()
        s.inputs["in1"].value = 1.0
        s.compute(0.0, 0.1)
        self.assertTrue(s.time_data)

        s.reset()
        self.assertEqual(s.time_data, [])
        self.assertEqual(s.value_data, [])
        self.assertEqual(s.input_data, {})

    def test_get_data_arrays_returns_numpy_arrays(self):
        s = Scope()
        s.inputs["in1"].value = 3.0
        s.compute(0.0, 0.1)
        time_arr, data_dict = s.get_data_arrays()
        self.assertIsInstance(time_arr, np.ndarray)
        self.assertIsInstance(data_dict["in1"], np.ndarray)
        self.assertEqual(data_dict["in1"][0], 3.0)

    def test_export_csv_rows_header_and_data(self):
        s = Scope()
        for i, t in enumerate([0.0, 0.1]):
            s.inputs["in1"].value = float(i * 10)
            s.compute(t, 0.1)

        rows = s.export_csv_rows()
        self.assertEqual(rows[0], ["time", "in1"])
        self.assertEqual(rows[1], [0.0, 0.0])
        self.assertEqual(rows[2], [0.1, 10.0])

    def test_export_csv_rows_multiple_inputs(self):
        s = Scope()
        s.add_input("in2")
        s.num_inputs = 2

        s.inputs["in1"].value = 1.0
        s.inputs["in2"].value = 2.0
        s.compute(0.0, 0.1)

        rows = s.export_csv_rows()
        self.assertEqual(rows[0], ["time", "in1", "in2"])
        self.assertEqual(rows[1], [0.0, 1.0, 2.0])

    def test_export_csv_rows_empty_when_no_data(self):
        s = Scope()
        rows = s.export_csv_rows()
        self.assertEqual(rows, [["time"]])


class TestInputOutputPort(unittest.TestCase):
    def test_input_port_compute_is_noop_value_injected_externally(self):
        p = InputPort()
        p.outputs["out"].value = 5.0
        p.compute(0.0, 0.01)  # should not touch outputs itself
        self.assertEqual(p.outputs["out"].value, 5.0)

    def test_output_port_compute_is_noop(self):
        p = OutputPort()
        p.inputs["in"].value = 9.0
        p.compute(0.0, 0.01)
        # OutputPort doesn't write an output port itself; value stays on 'in'.
        self.assertEqual(p.inputs["in"].value, 9.0)

    def test_port_name_param_updates_label(self):
        p = InputPort()
        p.params["PortName"] = "Speed"
        p._update_label()
        self.assertIn("Speed", p.name)


if __name__ == "__main__":
    unittest.main()
