"""Unit tests for conditional/logic blocks: IfElse, LogicalOperator, RelationalOperator, Switch."""
import unittest
import numpy as np

from engine.blocks.if_else import IfElse
from engine.blocks.logical_operator import LogicalOperator
from engine.blocks.relational_operator import RelationalOperator
from engine.blocks.switch import Switch


class TestIfElse(unittest.TestCase):
    def test_true_branch_when_cond_meets_threshold(self):
        b = IfElse()
        b.params["Threshold"] = 0.5
        b.inputs["cond"].value = 1.0
        b.inputs["true"].value = 100.0
        b.inputs["false"].value = -100.0
        b.compute(0, 0.01)
        self.assertEqual(b.outputs["out"].value, 100.0)

    def test_false_branch_when_cond_below_threshold(self):
        b = IfElse()
        b.params["Threshold"] = 0.5
        b.inputs["cond"].value = 0.0
        b.inputs["true"].value = 100.0
        b.inputs["false"].value = -100.0
        b.compute(0, 0.01)
        self.assertEqual(b.outputs["out"].value, -100.0)

    def test_boundary_is_inclusive(self):
        b = IfElse()
        b.params["Threshold"] = 0.5
        b.inputs["cond"].value = 0.5
        b.inputs["true"].value = 1.0
        b.inputs["false"].value = 0.0
        b.compute(0, 0.01)
        self.assertEqual(b.outputs["out"].value, 1.0)


class TestLogicalOperator(unittest.TestCase):
    def _run(self, op, a, b):
        block = LogicalOperator()
        block.params["Operator"] = op
        block.inputs["in1"].value = a
        block.inputs["in2"].value = b
        block.compute(0, 0.01)
        return block.outputs["out"].value

    def test_and(self):
        self.assertEqual(self._run("AND", 1.0, 1.0), 1.0)
        self.assertEqual(self._run("AND", 1.0, 0.0), 0.0)

    def test_or(self):
        self.assertEqual(self._run("OR", 0.0, 1.0), 1.0)
        self.assertEqual(self._run("OR", 0.0, 0.0), 0.0)

    def test_not_ignores_second_input(self):
        self.assertEqual(self._run("NOT", 0.0, 1.0), 1.0)
        self.assertEqual(self._run("NOT", 1.0, 0.0), 0.0)

    def test_xor(self):
        self.assertEqual(self._run("XOR", 1.0, 0.0), 1.0)
        self.assertEqual(self._run("XOR", 1.0, 1.0), 0.0)

    def test_nand(self):
        self.assertEqual(self._run("NAND", 1.0, 1.0), 0.0)
        self.assertEqual(self._run("NAND", 1.0, 0.0), 1.0)

    def test_nor(self):
        self.assertEqual(self._run("NOR", 0.0, 0.0), 1.0)
        self.assertEqual(self._run("NOR", 1.0, 0.0), 0.0)

    def test_compute_chunk_matches_scalar(self):
        block = LogicalOperator()
        block.params["Operator"] = "AND"
        a = np.array([1.0, 1.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 1.0, 0.0])
        block.inputs["in1"].vector_value = a
        block.inputs["in2"].vector_value = b
        block.compute_chunk(np.arange(4) * 0.01, 0.01)
        np.testing.assert_allclose(block.outputs["out"].vector_value, [1.0, 0.0, 0.0, 0.0])


class TestRelationalOperator(unittest.TestCase):
    def _run(self, op, a, b):
        block = RelationalOperator()
        block.params["Operator"] = op
        block.inputs["in1"].value = a
        block.inputs["in2"].value = b
        block.compute(0, 0.01)
        return block.outputs["out"].value

    def test_greater_than(self):
        self.assertEqual(self._run(">", 5.0, 3.0), 1.0)
        self.assertEqual(self._run(">", 3.0, 5.0), 0.0)

    def test_less_than(self):
        self.assertEqual(self._run("<", 3.0, 5.0), 1.0)

    def test_equal(self):
        self.assertEqual(self._run("==", 4.0, 4.0), 1.0)
        self.assertEqual(self._run("==", 4.0, 5.0), 0.0)

    def test_not_equal(self):
        self.assertEqual(self._run("!=", 4.0, 5.0), 1.0)

    def test_ge_le(self):
        self.assertEqual(self._run(">=", 4.0, 4.0), 1.0)
        self.assertEqual(self._run("<=", 4.0, 4.0), 1.0)

    def test_compute_chunk_matches_scalar(self):
        block = RelationalOperator()
        block.params["Operator"] = ">"
        a = np.array([5.0, 1.0, 3.0])
        b = np.array([3.0, 1.0, 5.0])
        block.inputs["in1"].vector_value = a
        block.inputs["in2"].vector_value = b
        block.compute_chunk(np.arange(3) * 0.01, 0.01)
        np.testing.assert_allclose(block.outputs["out"].vector_value, [1.0, 0.0, 0.0])


class TestSwitch(unittest.TestCase):
    def test_passes_in1_when_ctrl_above_threshold(self):
        s = Switch()
        s.params["Threshold"] = 0.5
        s.inputs["in1"].value = 10.0
        s.inputs["in2"].value = -10.0
        s.inputs["ctrl"].value = 1.0
        s.compute(0, 0.01)
        self.assertEqual(s.outputs["out"].value, 10.0)

    def test_passes_in2_when_ctrl_below_threshold(self):
        s = Switch()
        s.params["Threshold"] = 0.5
        s.inputs["in1"].value = 10.0
        s.inputs["in2"].value = -10.0
        s.inputs["ctrl"].value = 0.0
        s.compute(0, 0.01)
        self.assertEqual(s.outputs["out"].value, -10.0)


if __name__ == "__main__":
    unittest.main()
