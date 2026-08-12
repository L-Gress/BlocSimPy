"""Unit tests for signal source blocks: Constant, SineWave, Ramp, Clock, LookupTable."""
import unittest

from engine.blocks.constant import Constant
from engine.blocks.sine_wave import SineWave
from engine.blocks.ramp import Ramp
from engine.blocks.clock import Clock
from engine.blocks.lookup_table import LookupTable
from engine.simulation.engine import SimulationEngine
from engine.variables import make_variable_ref, get_active_variables, set_active_variables

from conftest import set_params, connect


class TestConstant(unittest.TestCase):
    def test_outputs_configured_value(self):
        c = Constant()
        set_params(c, Value=42.0)
        c.compute(0, 0.01)
        self.assertEqual(c.outputs["out"].value, 42.0)

    def test_value_is_constant_over_time(self):
        c = Constant()
        set_params(c, Value=7.0)
        for t in [0.0, 1.0, 5.0]:
            c.compute(t, 0.01)
            self.assertEqual(c.outputs["out"].value, 7.0)


class TestSineWave(unittest.TestCase):
    def test_formula_matches_amplitude_freq_phase(self):
        s = SineWave()
        set_params(s, Amplitude=2.0, Frequency=1.0, Phase=0.0)
        s.compute(0.25, 0.01)  # quarter period -> sin(2*pi*0.25) = 1
        self.assertAlmostEqual(s.outputs["out"].value, 2.0, places=6)

    def test_zero_at_t_zero_with_no_phase(self):
        s = SineWave()
        s.compute(0.0, 0.01)
        self.assertAlmostEqual(s.outputs["out"].value, 0.0)

    def test_external_time_adds_input_port(self):
        s = SineWave()
        self.assertNotIn("time", s.inputs)
        s.params = dict(s.params, **{"Use External Time": "True"})
        self.assertIn("time", s.inputs)

        s.params = dict(s.params, **{"Use External Time": "False"})
        self.assertNotIn("time", s.inputs)

    def test_external_time_drives_output_instead_of_t(self):
        s = SineWave()
        set_params(s, Amplitude=1.0, Frequency=1.0, Phase=0.0)
        s.params = dict(s.params, **{"Use External Time": "True"})
        s.inputs["time"].value = 0.25
        # Called with a "wrong" simulation time to prove the external port wins.
        s.compute(999.0, 0.01)
        self.assertAlmostEqual(s.outputs["out"].value, 1.0, places=6)


class TestRamp(unittest.TestCase):
    def test_holds_initial_value_before_start(self):
        r = Ramp()
        set_params(r, Slope=2.0, **{"Start Time": 1.0, "Initial Output": 0.5})
        r.compute(0.5, 0.01)
        self.assertEqual(r.outputs["out"].value, 0.5)

    def test_ramps_linearly_after_start(self):
        r = Ramp()
        set_params(r, Slope=2.0, **{"Start Time": 1.0, "Initial Output": 0.0})
        r.compute(2.0, 0.01)  # 1 second past start
        self.assertAlmostEqual(r.outputs["out"].value, 2.0)


class TestClock(unittest.TestCase):
    def test_outputs_current_time(self):
        c = Clock()
        c.compute(3.14, 0.01)
        self.assertAlmostEqual(c.outputs["out"].value, 3.14)


class TestLookupTable(unittest.TestCase):
    def test_interpolates_between_points(self):
        lut = LookupTable()
        lut.params["Table"] = [(0.0, 0.0), (1.0, 10.0), (2.0, 20.0)]
        lut.inputs["in"].value = 0.5
        lut.compute(0, 0.01)
        self.assertAlmostEqual(lut.outputs["out"].value, 5.0)

    def test_exact_point_lookup(self):
        lut = LookupTable()
        lut.params["Table"] = [(0.0, 0.0), (1.0, 10.0), (2.0, 4.0)]
        lut.inputs["in"].value = 2.0
        lut.compute(0, 0.01)
        self.assertAlmostEqual(lut.outputs["out"].value, 4.0)

    def test_empty_table_outputs_zero(self):
        lut = LookupTable()
        lut.params["Table"] = []
        lut.inputs["in"].value = 1.0
        lut.compute(0, 0.01)
        self.assertEqual(lut.outputs["out"].value, 0.0)

    def test_table_can_bind_to_declared_array_variable(self):
        # The whole X/Y table can be a global variable's value (see
        # engine/variables.py and LookupTableDialog's "Bind entire table"
        # toggle), not just a scalar -- resolved the same way any other
        # variable-bound param is.
        saved = get_active_variables()
        try:
            set_active_variables({})
            lut = LookupTable()
            lut.params["Table"] = make_variable_ref("Curve")
            c = Constant()
            set_params(c, Value=0.5)
            connect(lut, "in", c)

            engine = SimulationEngine()
            engine.configure([c, lut], duration=0.02, dt=0.01,
                              variables={"Curve": [(0.0, 0.0), (1.0, 10.0), (2.0, 20.0)]})
            result = engine.run()

            self.assertTrue(result.success, result.error_message)
            self.assertAlmostEqual(lut.outputs["out"].value, 5.0)
        finally:
            set_active_variables(saved)


if __name__ == "__main__":
    unittest.main()
