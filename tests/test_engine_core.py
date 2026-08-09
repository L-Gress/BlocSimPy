"""Tests for the core simulation engine: execution ordering and batch running."""
import unittest

from engine.simulation.executor import ExecutionOrdering, AlgebraicLoopError
from engine.simulation.engine import SimulationEngine
from engine.blocks.constant import Constant
from engine.blocks.gain import Gain
from engine.blocks.sum_block import Sum
from engine.blocks.integrator import Integrator
from engine.blocks.delay import Delay
from engine.blocks.scope import Scope

from conftest import connect, set_params


class TestExecutionOrdering(unittest.TestCase):

    def test_topological_sort_linear_chain(self):
        c = Constant()
        g = Gain()
        s = Scope()
        connect(g, "in", c)
        connect(s, "in1", g)

        # Deliberately out-of-order input list.
        ordered = ExecutionOrdering.topological_sort([s, g, c])

        self.assertEqual(ordered.index(c), 0)
        self.assertLess(ordered.index(g), ordered.index(s))

    def test_topological_sort_independent_blocks_keeps_all(self):
        c1 = Constant()
        c2 = Constant()
        ordered = ExecutionOrdering.topological_sort([c1, c2])
        self.assertEqual(set(ordered), {c1, c2})

    def test_topological_sort_pure_algebraic_cycle_raises(self):
        # Two Gain blocks feeding each other directly have no well-defined
        # evaluation order (each one's output this step depends on the
        # other's output this same step) -- this must be reported, not
        # silently resolved by an arbitrary order.
        g1 = Gain()
        g2 = Gain()
        connect(g1, "in", g2)
        connect(g2, "in", g1)

        with self.assertRaises(AlgebraicLoopError) as ctx:
            ExecutionOrdering.topological_sort([g1, g2])
        self.assertEqual(set(ctx.exception.blocks), {g1, g2})

    def test_topological_sort_loop_broken_by_integrator_does_not_raise(self):
        # Gain -> Integrator -> Gain feedback: the Integrator's output this
        # step comes from its state (set up by a prior update_state() pass),
        # not from this step's input, so this loop is well-defined and must
        # sort successfully.
        g1 = Gain()
        integ = Integrator()
        g2 = Gain()
        connect(integ, "in", g1)
        connect(g2, "in", integ)
        connect(g1, "in", g2)

        ordered = ExecutionOrdering.topological_sort([g1, integ, g2])
        self.assertEqual(set(ordered), {g1, integ, g2})

    def test_topological_sort_loop_broken_by_delay_does_not_raise(self):
        g1 = Gain()
        d = Delay()
        connect(d, "in", g1)
        connect(g1, "in", d)

        ordered = ExecutionOrdering.topological_sort([g1, d])
        self.assertEqual(set(ordered), {g1, d})


class TestSimulationEngineValidate(unittest.TestCase):

    def test_rejects_non_positive_dt(self):
        engine = SimulationEngine()
        engine.configure([Constant()], duration=1.0, dt=0.0)
        ok, msg = engine.validate()
        self.assertFalse(ok)
        self.assertIn("Time step", msg)

    def test_rejects_non_positive_duration(self):
        engine = SimulationEngine()
        engine.configure([Constant()], duration=0.0, dt=0.01)
        ok, msg = engine.validate()
        self.assertFalse(ok)
        self.assertIn("Duration", msg)

    def test_rejects_dt_larger_than_duration(self):
        engine = SimulationEngine()
        engine.configure([Constant()], duration=0.01, dt=1.0)
        ok, msg = engine.validate()
        self.assertFalse(ok)

    def test_rejects_empty_block_list(self):
        engine = SimulationEngine()
        engine.configure([], duration=1.0, dt=0.01)
        ok, msg = engine.validate()
        self.assertFalse(ok)
        self.assertIn("blocks", msg.lower())

    def test_accepts_valid_configuration(self):
        engine = SimulationEngine()
        engine.configure([Constant()], duration=1.0, dt=0.01)
        ok, msg = engine.validate()
        self.assertTrue(ok)


class TestSimulationEngineRun(unittest.TestCase):

    def test_batch_run_propagates_constant_through_gain(self):
        c = Constant()
        set_params(c, Value=3.0)
        g = Gain()
        set_params(g, Gain=2.0)
        connect(g, "in", c)

        scope = Scope()
        connect(scope, "in1", g)

        engine = SimulationEngine()
        engine.configure([c, g, scope], duration=0.1, dt=0.01)
        result = engine.run()

        self.assertTrue(result.success, result.error_message)
        self.assertIn("Scope", result.scope_data)
        data = result.scope_data["Scope"]["data"]
        self.assertTrue((data == 6.0).all())

    def test_batch_run_calls_update_state_so_integrator_accumulates(self):
        # Regression test: SimulationEngine.run() must call update_state()
        # on stateful blocks (like Integrator), or the integral never moves.
        c = Constant()
        c.params["Value"] = 1.0
        integ = Integrator()
        connect(integ, "in", c)

        engine = SimulationEngine()
        engine.configure([c, integ], duration=1.0, dt=0.1)
        result = engine.run()

        self.assertTrue(result.success, result.error_message)
        self.assertAlmostEqual(integ.state, 1.0, places=6)

    def test_run_reports_failure_instead_of_raising(self):
        # A block whose compute() blows up should be caught and reported,
        # not crash the whole engine run.
        class ExplodingBlock(Constant):
            def compute(self, t, dt, context=None):
                raise RuntimeError("boom")

        engine = SimulationEngine()
        engine.configure([ExplodingBlock()], duration=0.1, dt=0.01)
        result = engine.run()

        self.assertFalse(result.success)
        self.assertIn("boom", result.error_message)

    def test_sum_block_combines_two_inputs(self):
        c1 = Constant(); set_params(c1, Value=2.0)
        c2 = Constant(); set_params(c2, Value=5.0)
        s = Sum()
        connect(s, "in1", c1)
        connect(s, "in2", c2)

        engine = SimulationEngine()
        engine.configure([c1, c2, s], duration=0.05, dt=0.01)
        result = engine.run()

        self.assertTrue(result.success)
        self.assertAlmostEqual(s.outputs["out"].value, 7.0)

    def test_run_reports_failure_for_algebraic_loop(self):
        g1 = Gain()
        g2 = Gain()
        connect(g1, "in", g2)
        connect(g2, "in", g1)

        engine = SimulationEngine()
        engine.configure([g1, g2], duration=0.1, dt=0.01)
        result = engine.run()

        self.assertFalse(result.success)
        self.assertIn("loop", result.error_message.lower())

    def test_run_accepts_rk4_solver_and_still_integrates(self):
        c = Constant()
        c.params["Value"] = 1.0
        integ = Integrator()
        connect(integ, "in", c)

        engine = SimulationEngine()
        engine.configure([c, integ], duration=1.0, dt=0.1, solver="rk4")
        result = engine.run()

        self.assertTrue(result.success, result.error_message)
        self.assertAlmostEqual(integ.state, 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
