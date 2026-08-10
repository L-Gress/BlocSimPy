"""Unit tests for the PythonFunction block (per-timestep user code)."""
import unittest

from engine.blocks.python_function import PythonFunction
from engine.simulation.engine import SimulationEngine

from conftest import set_params


class TestPythonFunction(unittest.TestCase):
    def test_default_code_doubles_input(self):
        pf = PythonFunction()
        pf.inputs["in1"].value = 3.0
        pf.compute(0.0, 0.01)
        self.assertAlmostEqual(pf.outputs["out1"].value, 6.0)

    def test_custom_code_uses_t_and_dt(self):
        pf = PythonFunction()
        set_params(pf, Code="out1 = t + dt")
        pf.compute(2.0, 0.5)
        self.assertAlmostEqual(pf.outputs["out1"].value, 2.5)

    def test_persistent_state_across_calls(self):
        pf = PythonFunction()
        set_params(pf, Code="state.setdefault('n', 0); state['n'] += 1; out1 = state['n']")
        pf.compute(0.0, 0.01)
        pf.compute(0.01, 0.01)
        pf.compute(0.02, 0.01)
        self.assertEqual(pf.outputs["out1"].value, 3.0)

    def test_reset_clears_persistent_state(self):
        pf = PythonFunction()
        set_params(pf, Code="state.setdefault('n', 0); state['n'] += 1; out1 = state['n']")
        pf.compute(0.0, 0.01)
        pf.compute(0.01, 0.01)
        self.assertEqual(pf.outputs["out1"].value, 2.0)

        pf.reset()
        pf.compute(0.0, 0.01)
        self.assertEqual(pf.outputs["out1"].value, 1.0)

    def test_dynamic_ports_grow_and_shrink(self):
        pf = PythonFunction()
        set_params(pf, NumInputs=3, NumOutputs=2)
        pf.refresh_io_ports()
        self.assertEqual(sorted(pf.inputs.keys()), ["in1", "in2", "in3"])
        self.assertEqual(sorted(pf.outputs.keys()), ["out1", "out2"])

    def test_runtime_error_holds_last_output_without_crashing(self):
        pf = PythonFunction()
        set_params(pf, Code="out1 = 5.0")
        pf.compute(0.0, 0.01)
        self.assertEqual(pf.outputs["out1"].value, 5.0)

        set_params(pf, Code="out1 = 1 / 0")
        pf.compute(0.01, 0.01)  # should not raise
        self.assertEqual(pf.outputs["out1"].value, 5.0)  # held last value
        self.assertIn("ZeroDivisionError", pf._last_error)

    def test_syntax_error_holds_last_output_without_crashing(self):
        pf = PythonFunction()
        set_params(pf, Code="out1 = 7.0")
        pf.compute(0.0, 0.01)
        self.assertEqual(pf.outputs["out1"].value, 7.0)

        set_params(pf, Code="this is not : valid python (")
        pf.compute(0.01, 0.01)  # should not raise
        self.assertEqual(pf.outputs["out1"].value, 7.0)
        self.assertIn("SyntaxError", pf._last_error)

    def test_math_module_is_available(self):
        pf = PythonFunction()
        set_params(pf, Code="out1 = math.sqrt(16.0)")
        pf.compute(0.0, 0.01)
        self.assertAlmostEqual(pf.outputs["out1"].value, 4.0)

    def test_runs_inside_simulation_engine_without_crashing_on_bad_code(self):
        pf = PythonFunction()
        set_params(pf, Code="out1 = 1 / 0")

        engine = SimulationEngine()
        engine.configure([pf], duration=0.05, dt=0.01)
        result = engine.run()

        # A per-call exception inside PythonFunction.compute() is caught
        # internally (see test_runtime_error_holds_last_output_without_crashing);
        # the engine's own run() should report overall success.
        self.assertTrue(result.success, result.error_message)


if __name__ == "__main__":
    unittest.main()
