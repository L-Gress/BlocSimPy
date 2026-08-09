"""Unit tests for bus/vector signal routing blocks: Mux, Demux, BusCreator, BusSelector."""
import unittest
import numpy as np

from engine.blocks.mux import Mux
from engine.blocks.demux import Demux
from engine.blocks.bus_creator import BusCreator
from engine.blocks.bus_selector import BusSelector

from conftest import connect, set_params


class TestMux(unittest.TestCase):
    def test_combines_scalar_inputs_into_bus(self):
        m = Mux()
        m.inputs["in1"].value = 1.0
        m.inputs["in2"].value = 2.0
        m.compute(0.0, 0.01)
        np.testing.assert_allclose(m.outputs["out"].bus_value, [1.0, 2.0])

    def test_refresh_io_ports_grows_and_shrinks(self):
        m = Mux()
        m.params["NumInputs"] = 5
        m.refresh_io_ports()
        self.assertEqual(sorted(m.inputs.keys()), [f"in{i}" for i in range(1, 6)])

        m.params["NumInputs"] = 2
        m.refresh_io_ports()
        self.assertEqual(sorted(m.inputs.keys()), ["in1", "in2"])

    def test_num_inputs_clamped_to_valid_range(self):
        m = Mux()
        m.params["NumInputs"] = 99
        m.refresh_io_ports()
        self.assertEqual(len(m.inputs), 16)
        self.assertEqual(m.params["NumInputs"], 16)


class TestDemux(unittest.TestCase):
    def test_splits_bus_into_scalar_outputs(self):
        d = Demux()
        d.inputs["in"].bus_value = np.array([10.0, 20.0])
        d.compute(0.0, 0.01)
        self.assertEqual(d.outputs["out1"].value, 10.0)
        self.assertEqual(d.outputs["out2"].value, 20.0)

    def test_width_mismatch_pads_with_zero_instead_of_crashing(self):
        d = Demux()
        d.params["NumOutputs"] = 4
        d.refresh_io_ports()
        d.inputs["in"].bus_value = np.array([1.0, 2.0])  # narrower than NumOutputs
        d.compute(0.0, 0.01)
        self.assertEqual(d.outputs["out1"].value, 1.0)
        self.assertEqual(d.outputs["out2"].value, 2.0)
        self.assertEqual(d.outputs["out3"].value, 0.0)
        self.assertEqual(d.outputs["out4"].value, 0.0)

    def test_mux_then_demux_round_trips_values(self):
        m = Mux()
        d = Demux()
        connect(d, "in", m)  # d.inputs["in"] <- m.outputs["out"]
        m.inputs["in1"].value = 3.0
        m.inputs["in2"].value = 4.0
        m.compute(0.0, 0.01)
        d.compute(0.0, 0.01)
        self.assertEqual(d.outputs["out1"].value, 3.0)
        self.assertEqual(d.outputs["out2"].value, 4.0)

    def test_scalar_source_wired_into_bus_consumer_degrades_gracefully(self):
        # No port type-checking anywhere in this codebase (see PortModel
        # docs) -- a scalar output wired into a Demux input should degrade
        # to a 1-wide bus rather than crash.
        from engine.blocks.constant import Constant
        c = Constant()
        set_params(c, Value=7.0)
        d = Demux()
        connect(d, "in", c)
        c.compute(0.0, 0.01)
        d.compute(0.0, 0.01)
        self.assertEqual(d.outputs["out1"].value, 7.0)
        self.assertEqual(d.outputs["out2"].value, 0.0)


class TestBusCreatorSelector(unittest.TestCase):
    def test_bus_creator_names_drive_port_count(self):
        bc = BusCreator()
        bc.params["SignalNames"] = ["Speed", "Heading", "Altitude"]
        bc.refresh_io_ports()
        self.assertEqual(sorted(bc.inputs.keys()), ["in1", "in2", "in3"])

    def test_bus_selector_picks_channels_by_name(self):
        bc = BusCreator()
        bc.params["SignalNames"] = ["Speed", "Heading"]
        bc.refresh_io_ports()
        bc.inputs["in1"].value = 100.0
        bc.inputs["in2"].value = 45.0
        bc.compute(0.0, 0.01)

        bs = BusSelector()
        connect(bs, "in", bc)
        bs.params["SelectedSignals"] = ["Heading", "Speed"]
        bs.refresh_io_ports()
        bs.compute(0.0, 0.01)

        self.assertEqual(bs.outputs["out1"].value, 45.0)
        self.assertEqual(bs.outputs["out2"].value, 100.0)

    def test_bus_selector_falls_back_to_index_when_name_unresolvable(self):
        bc = BusCreator()  # not connected -> no names available downstream
        m = Mux()
        m.inputs["in1"].value = 1.0
        m.inputs["in2"].value = 2.0
        m.compute(0.0, 0.01)

        bs = BusSelector()
        connect(bs, "in", m)
        bs.params["SelectedSignals"] = ["2"]  # 1-based index, not a name
        bs.refresh_io_ports()
        bs.compute(0.0, 0.01)

        self.assertEqual(bs.outputs["out1"].value, 2.0)

    def test_bus_selector_unresolvable_selector_outputs_zero(self):
        bc = BusCreator()
        bc.params["SignalNames"] = ["A"]
        bc.refresh_io_ports()
        bc.inputs["in1"].value = 5.0
        bc.compute(0.0, 0.01)

        bs = BusSelector()
        connect(bs, "in", bc)
        bs.params["SelectedSignals"] = ["DoesNotExist"]
        bs.refresh_io_ports()
        bs.compute(0.0, 0.01)

        self.assertEqual(bs.outputs["out1"].value, 0.0)


if __name__ == "__main__":
    unittest.main()
