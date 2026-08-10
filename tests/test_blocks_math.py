"""Unit tests for stateless math/arithmetic blocks."""
import unittest
import numpy as np

from engine.blocks.gain import Gain
from engine.blocks.sum_block import Sum
from engine.blocks.product import Product
from engine.blocks.divide import Divide
from engine.blocks.modulo import Modulo
from engine.blocks.abs import Abs
from engine.blocks.math_func import MathFunction
from engine.blocks.max import Max
from engine.blocks.min import Min
from engine.blocks.saturation import Saturation

from conftest import connect, set_params


class TestGain(unittest.TestCase):
    def test_multiplies_input_by_gain(self):
        g = Gain()
        set_params(g, Gain=2.5)
        g.inputs["in"].value = 4.0
        g.compute(0, 0.01)
        self.assertAlmostEqual(g.outputs["out"].value, 10.0)

    def test_compute_chunk_matches_scalar(self):
        g = Gain()
        set_params(g, Gain=3.0)
        u = np.array([1.0, 2.0, 3.0])
        g.inputs["in"].vector_value = u
        g.compute_chunk(np.arange(3) * 0.01, 0.01)
        np.testing.assert_allclose(g.outputs["out"].vector_value, u * 3.0)

    def test_invalid_gain_param_falls_back_to_zero(self):
        g = Gain()
        set_params(g, Gain="not-a-number")
        g.inputs["in"].value = 5.0
        g.compute(0, 0.01)
        self.assertEqual(g.outputs["out"].value, 0.0)


class TestSum(unittest.TestCase):
    def test_adds_two_inputs(self):
        s = Sum()
        s.inputs["in1"].value = 3.0
        s.inputs["in2"].value = 4.0
        s.compute(0, 0.01)
        self.assertEqual(s.outputs["out"].value, 7.0)


class TestProduct(unittest.TestCase):
    def test_multiplies_two_inputs(self):
        p = Product()
        p.inputs["in1"].value = 3.0
        p.inputs["in2"].value = -2.0
        p.compute(0, 0.01)
        self.assertEqual(p.outputs["out"].value, -6.0)


class TestDivide(unittest.TestCase):
    def test_divides_num_by_den(self):
        d = Divide()
        d.inputs["num"].value = 10.0
        d.inputs["den"].value = 4.0
        d.compute(0, 0.01)
        self.assertEqual(d.outputs["out"].value, 2.5)

    def test_division_by_zero_yields_zero_not_exception(self):
        d = Divide()
        d.inputs["num"].value = 10.0
        d.inputs["den"].value = 0.0
        d.compute(0, 0.01)
        self.assertEqual(d.outputs["out"].value, 0.0)

    def test_compute_chunk_division_by_zero_yields_zero(self):
        d = Divide()
        d.inputs["num"].vector_value = np.array([1.0, 2.0, 3.0])
        d.inputs["den"].vector_value = np.array([1.0, 0.0, 2.0])
        d.compute_chunk(np.arange(3) * 0.01, 0.01)
        np.testing.assert_allclose(d.outputs["out"].vector_value, [1.0, 0.0, 1.5])


class TestModulo(unittest.TestCase):
    def test_remainder(self):
        m = Modulo()
        m.inputs["in"].value = 7.0
        m.inputs["mod"].value = 3.0
        m.compute(0, 0.01)
        self.assertEqual(m.outputs["out"].value, 1.0)

    def test_mod_by_zero_yields_zero(self):
        m = Modulo()
        m.inputs["in"].value = 7.0
        m.inputs["mod"].value = 0.0
        m.compute(0, 0.01)
        self.assertEqual(m.outputs["out"].value, 0.0)


class TestAbs(unittest.TestCase):
    def test_negative_input_becomes_positive(self):
        a = Abs()
        a.inputs["in"].value = -5.5
        a.compute(0, 0.01)
        self.assertEqual(a.outputs["out"].value, 5.5)


class TestMathFunction(unittest.TestCase):
    def test_sqrt(self):
        mf = MathFunction()
        set_params(mf, Function="Sqrt")
        mf.inputs["in"].value = 9.0
        mf.compute(0, 0.01)
        self.assertAlmostEqual(mf.outputs["out"].value, 3.0)

    def test_sin(self):
        mf = MathFunction()
        set_params(mf, Function="Sin")
        mf.inputs["in"].value = 0.0
        mf.compute(0, 0.01)
        self.assertAlmostEqual(mf.outputs["out"].value, 0.0)

    def test_sinh(self):
        mf = MathFunction()
        set_params(mf, Function="Sinh")
        mf.inputs["in"].value = 0.0
        mf.compute(0, 0.01)
        self.assertAlmostEqual(mf.outputs["out"].value, 0.0)

    def test_cosh(self):
        mf = MathFunction()
        set_params(mf, Function="Cosh")
        mf.inputs["in"].value = 0.0
        mf.compute(0, 0.01)
        self.assertAlmostEqual(mf.outputs["out"].value, 1.0)

    def test_tanh(self):
        mf = MathFunction()
        set_params(mf, Function="Tanh")
        mf.inputs["in"].value = 0.0
        mf.compute(0, 0.01)
        self.assertAlmostEqual(mf.outputs["out"].value, 0.0)

    def test_unknown_function_falls_back_to_abs(self):
        mf = MathFunction()
        set_params(mf, Function="NotARealFunction")
        mf.inputs["in"].value = -4.0
        mf.compute(0, 0.01)
        self.assertAlmostEqual(mf.outputs["out"].value, 4.0)

    def test_compute_chunk_matches_scalar(self):
        mf = MathFunction()
        set_params(mf, Function="Square")
        u = np.array([1.0, 2.0, 3.0])
        mf.inputs["in"].vector_value = u
        mf.compute_chunk(np.arange(3) * 0.01, 0.01)
        np.testing.assert_allclose(mf.outputs["out"].vector_value, u ** 2)


class TestMaxMin(unittest.TestCase):
    def test_max_scalar(self):
        m = Max()
        m.inputs["in1"].value = 3.0
        m.inputs["in2"].value = 7.0
        m.compute(0, 0.01)
        self.assertEqual(m.outputs["out"].value, 7.0)

    def test_min_scalar(self):
        m = Min()
        m.inputs["in1"].value = 3.0
        m.inputs["in2"].value = 7.0
        m.compute(0, 0.01)
        self.assertEqual(m.outputs["out"].value, 3.0)

    def test_max_compute_chunk(self):
        m = Max()
        m.inputs["in1"].vector_value = np.array([1.0, 5.0, 2.0])
        m.inputs["in2"].vector_value = np.array([3.0, 1.0, 6.0])
        m.compute_chunk(np.arange(3) * 0.01, 0.01)
        np.testing.assert_allclose(m.outputs["out"].vector_value, [3.0, 5.0, 6.0])

    def test_min_compute_chunk(self):
        m = Min()
        m.inputs["in1"].vector_value = np.array([1.0, 5.0, 2.0])
        m.inputs["in2"].vector_value = np.array([3.0, 1.0, 6.0])
        m.compute_chunk(np.arange(3) * 0.01, 0.01)
        np.testing.assert_allclose(m.outputs["out"].vector_value, [1.0, 1.0, 2.0])


class TestSaturation(unittest.TestCase):
    def test_clamps_above_upper(self):
        s = Saturation()
        s.params["Upper Limit"] = 1.0
        s.params["Lower Limit"] = -1.0
        s.inputs["in"].value = 5.0
        s.compute(0, 0.01)
        self.assertEqual(s.outputs["out"].value, 1.0)

    def test_clamps_below_lower(self):
        s = Saturation()
        s.params["Upper Limit"] = 1.0
        s.params["Lower Limit"] = -1.0
        s.inputs["in"].value = -5.0
        s.compute(0, 0.01)
        self.assertEqual(s.outputs["out"].value, -1.0)

    def test_passes_through_within_range(self):
        s = Saturation()
        s.inputs["in"].value = 0.3
        s.compute(0, 0.01)
        self.assertAlmostEqual(s.outputs["out"].value, 0.3)

    def test_compute_chunk_clips(self):
        s = Saturation()
        s.params["Upper Limit"] = 1.0
        s.params["Lower Limit"] = -1.0
        s.inputs["in"].vector_value = np.array([-5.0, 0.5, 5.0])
        s.compute_chunk(np.arange(3) * 0.01, 0.01)
        np.testing.assert_allclose(s.outputs["out"].vector_value, [-1.0, 0.5, 1.0])


class TestBlockChaining(unittest.TestCase):
    def test_gain_reads_from_connected_constant(self):
        from engine.blocks.constant import Constant
        c = Constant()
        set_params(c, Value=4.0)
        g = Gain()
        set_params(g, Gain=2.0)
        connect(g, "in", c)

        c.compute(0, 0.01)
        g.compute(0, 0.01)
        self.assertEqual(g.outputs["out"].value, 8.0)


if __name__ == "__main__":
    unittest.main()
