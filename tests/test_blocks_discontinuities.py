"""Unit tests for discontinuity blocks: Dead Zone, Rate Limiter, Quantizer, Backlash."""
import unittest

from engine.blocks.dead_zone import DeadZone
from engine.blocks.rate_limiter import RateLimiter
from engine.blocks.quantizer import Quantizer
from engine.blocks.backlash import Backlash

from conftest import step, set_params


class TestDeadZone(unittest.TestCase):
    def test_inside_band_outputs_zero(self):
        dz = DeadZone()
        dz.inputs["in"].value = 0.2
        dz.compute(0.0, 0.01)
        self.assertEqual(dz.outputs["out"].value, 0.0)

    def test_above_band_passes_through_shifted(self):
        dz = DeadZone()
        set_params(dz, **{"Upper Limit": 0.5, "Lower Limit": -0.5})
        dz.inputs["in"].value = 2.0
        dz.compute(0.0, 0.01)
        self.assertAlmostEqual(dz.outputs["out"].value, 1.5)

    def test_below_band_passes_through_shifted(self):
        dz = DeadZone()
        set_params(dz, **{"Upper Limit": 0.5, "Lower Limit": -0.5})
        dz.inputs["in"].value = -2.0
        dz.compute(0.0, 0.01)
        self.assertAlmostEqual(dz.outputs["out"].value, -1.5)

class TestRateLimiter(unittest.TestCase):
    def test_first_sample_passes_through_unlimited(self):
        rl = RateLimiter()
        rl.inputs["in"].value = 10.0
        rl.compute(0.0, 0.1)
        self.assertEqual(rl.outputs["out"].value, 10.0)

    def test_rising_rate_is_clamped(self):
        rl = RateLimiter()
        set_params(rl, **{"Rising Slew Rate": 1.0, "Falling Slew Rate": -1.0})
        rl.inputs["in"].value = 0.0
        rl.compute(0.0, 0.1)  # prime at 0.0

        rl.inputs["in"].value = 100.0  # big jump
        rl.compute(0.1, 0.1)
        # max change per step = rate * dt = 1.0 * 0.1 = 0.1
        self.assertAlmostEqual(rl.outputs["out"].value, 0.1)

    def test_falling_rate_is_clamped(self):
        rl = RateLimiter()
        set_params(rl, **{"Rising Slew Rate": 1.0, "Falling Slew Rate": -1.0})
        rl.inputs["in"].value = 0.0
        rl.compute(0.0, 0.1)

        rl.inputs["in"].value = -100.0
        rl.compute(0.1, 0.1)
        self.assertAlmostEqual(rl.outputs["out"].value, -0.1)

    def test_within_rate_passes_through_exactly(self):
        rl = RateLimiter()
        set_params(rl, **{"Rising Slew Rate": 100.0, "Falling Slew Rate": -100.0})
        rl.inputs["in"].value = 0.0
        rl.compute(0.0, 0.1)
        rl.inputs["in"].value = 1.0
        rl.compute(0.1, 0.1)
        self.assertAlmostEqual(rl.outputs["out"].value, 1.0)

    def test_reset_reinitializes(self):
        rl = RateLimiter()
        rl.inputs["in"].value = 5.0
        rl.compute(0.0, 0.1)
        rl.reset()
        self.assertFalse(rl.initialized)
        self.assertEqual(rl.state, 0.0)


class TestQuantizer(unittest.TestCase):
    def test_rounds_to_nearest_interval(self):
        q = Quantizer()
        set_params(q, Interval=0.5)
        q.inputs["in"].value = 0.65
        q.compute(0.0, 0.01)
        self.assertAlmostEqual(q.outputs["out"].value, 0.5)

    def test_rounds_up_at_midpoint_and_above(self):
        q = Quantizer()
        set_params(q, Interval=1.0)
        q.inputs["in"].value = 2.6
        q.compute(0.0, 0.01)
        self.assertAlmostEqual(q.outputs["out"].value, 3.0)

class TestBacklash(unittest.TestCase):
    def test_first_sample_passes_through(self):
        b = Backlash()
        b.inputs["in"].value = 3.0
        b.compute(0.0, 0.01)
        self.assertEqual(b.outputs["out"].value, 3.0)

    def test_small_reversal_within_deadband_does_not_move_output(self):
        b = Backlash()
        set_params(b, **{"Deadband Width": 1.0})
        b.inputs["in"].value = 0.0
        b.compute(0.0, 0.01)  # output settles at 0.0

        b.inputs["in"].value = 0.3  # within +-0.5 deadband
        b.compute(0.01, 0.01)
        self.assertEqual(b.outputs["out"].value, 0.0)

    def test_large_move_drags_output_by_half_deadband(self):
        b = Backlash()
        set_params(b, **{"Deadband Width": 1.0})
        b.inputs["in"].value = 0.0
        b.compute(0.0, 0.01)

        b.inputs["in"].value = 10.0
        b.compute(0.01, 0.01)
        self.assertAlmostEqual(b.outputs["out"].value, 9.5)

    def test_reset_reinitializes(self):
        b = Backlash()
        b.inputs["in"].value = 5.0
        b.compute(0.0, 0.01)
        b.reset()
        self.assertFalse(b.initialized)
        self.assertEqual(b.state, 0.0)


if __name__ == "__main__":
    unittest.main()
