"""Unit tests for signal source blocks: Constant, SineWave, Ramp, Clock, LookupTable."""
import unittest
import numpy as np

from engine.blocks.constant import Constant
from engine.blocks.sine_wave import SineWave
from engine.blocks.ramp import Ramp
from engine.blocks.clock import Clock
from engine.blocks.lookup_table import LookupTable

from conftest import set_params


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

    def test_compute_chunk_fills_buffer(self):
        c = Constant()
        set_params(c, Value=3.0)
        c.outputs["out"].ensure_buffer(5)
        c.compute_chunk(np.arange(5) * 0.01, 0.01)
        np.testing.assert_allclose(c.outputs["out"].vector_value, np.full(5, 3.0))


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

    def test_compute_chunk_matches_scalar(self):
        r = Ramp()
        set_params(r, Slope=3.0, **{"Start Time": 0.0, "Initial Output": 1.0})
        t_vec = np.array([0.0, 1.0, 2.0])
        r.compute_chunk(t_vec, 0.01)
        np.testing.assert_allclose(r.outputs["out"].vector_value, [1.0, 4.0, 7.0])


class TestClock(unittest.TestCase):
    def test_outputs_current_time(self):
        c = Clock()
        c.compute(3.14, 0.01)
        self.assertAlmostEqual(c.outputs["out"].value, 3.14)

    def test_compute_chunk_outputs_time_vector(self):
        c = Clock()
        t_vec = np.array([0.0, 0.1, 0.2])
        c.compute_chunk(t_vec, 0.01)
        np.testing.assert_allclose(c.outputs["out"].vector_value, t_vec)


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

    def test_compute_chunk_matches_scalar(self):
        lut = LookupTable()
        lut.params["Table"] = [(0.0, 0.0), (1.0, 10.0), (2.0, 20.0)]
        lut.inputs["in"].vector_value = np.array([0.5, 1.5])
        lut.compute_chunk(np.arange(2) * 0.01, 0.01)
        np.testing.assert_allclose(lut.outputs["out"].vector_value, [5.0, 15.0])


if __name__ == "__main__":
    unittest.main()
