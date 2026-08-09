"""Unit tests for stateful/dynamic blocks: Integrator, Derivative, TransferFunction, PID, Delay."""
import unittest
import numpy as np

from engine.blocks.integrator import Integrator
from engine.blocks.derivative import Derivative
from engine.blocks.transfer_function import TransferFunction
from engine.blocks.pid import PID
from engine.blocks.delay import Delay

from conftest import step, set_params


class TestIntegrator(unittest.TestCase):
    def test_constant_input_accumulates_linearly(self):
        integ = Integrator()
        integ.inputs["in"].value = 2.0
        for _ in range(10):
            step([integ], 0.0, 0.1)
        # integral of a constant 2.0 over 1.0s = 2.0
        self.assertAlmostEqual(integ.state, 2.0, places=6)

    def test_initial_condition_is_first_output(self):
        integ = Integrator()
        set_params(integ, InitialCondition=5.0)
        integ.inputs["in"].value = 0.0
        integ.compute(0.0, 0.1)
        self.assertEqual(integ.outputs["out"].value, 5.0)

    def test_reset_restores_initial_condition(self):
        integ = Integrator()
        set_params(integ, InitialCondition=1.0)
        integ.inputs["in"].value = 10.0
        for _ in range(5):
            step([integ], 0.0, 0.1)
        self.assertNotAlmostEqual(integ.state, 1.0)

        integ.reset()
        integ.compute(0.0, 0.1)
        self.assertEqual(integ.state, 1.0)

    def test_compute_chunk_matches_scalar_stepping(self):
        # Scalar path
        integ_scalar = Integrator()
        integ_scalar.inputs["in"].value = 3.0
        for _ in range(5):
            step([integ_scalar], 0.0, 0.1)
        scalar_state = integ_scalar.state

        # Chunked path
        integ_chunk = Integrator()
        u_vec = np.full(5, 3.0)
        integ_chunk.inputs["in"].vector_value = u_vec
        t_vec = np.arange(5) * 0.1
        integ_chunk.compute_chunk(t_vec, 0.1)
        integ_chunk.update_state_chunk(t_vec, 0.1)

        self.assertAlmostEqual(integ_chunk.state, scalar_state, places=6)


class TestDerivative(unittest.TestCase):
    def test_first_sample_outputs_zero(self):
        d = Derivative()
        d.inputs["in"].value = 5.0
        d.compute(0.0, 0.1)
        self.assertEqual(d.outputs["out"].value, 0.0)

    def test_rate_of_change(self):
        d = Derivative()
        d.inputs["in"].value = 0.0
        d.compute(0.0, 0.1)  # prime

        d.inputs["in"].value = 1.0
        d.compute(0.1, 0.1)
        self.assertAlmostEqual(d.outputs["out"].value, 10.0)  # (1-0)/0.1

    def test_reset_reinitializes(self):
        d = Derivative()
        d.inputs["in"].value = 5.0
        d.compute(0.0, 0.1)
        d.reset()
        self.assertFalse(d.initialized)


class TestTransferFunction(unittest.TestCase):
    def test_pure_gain_when_no_dynamics(self):
        tf = TransferFunction()
        tf.params["Numerator"] = [2.0]
        tf.params["Denominator"] = [1.0]
        tf.inputs["in"].value = 3.0
        tf.compute(0.0, 0.01)
        self.assertAlmostEqual(tf.outputs["out"].value, 6.0)

    def test_first_order_step_response_converges_to_unity_gain(self):
        # H(s) = 1 / (s + 1): step input of 1.0 should settle near 1.0.
        # compute() only produces the output from current state; update_state()
        # (Euler) advances it -- mirrors Integrator's own compute/update_state
        # split, see conftest.step().
        tf = TransferFunction()
        tf.params["Numerator"] = [1.0]
        tf.params["Denominator"] = [1.0, 1.0]
        tf.inputs["in"].value = 1.0

        dt = 0.01
        for i in range(2000):
            step([tf], i * dt, dt)

        self.assertAlmostEqual(tf.outputs["out"].value, 1.0, places=2)

    def test_reset_clears_internal_states(self):
        tf = TransferFunction()
        tf.params["Numerator"] = [1.0]
        tf.params["Denominator"] = [1.0, 1.0]
        tf.inputs["in"].value = 1.0
        for i in range(100):
            step([tf], i * 0.01, 0.01)
        self.assertTrue(any(s != 0.0 for s in tf.states))

        tf.reset()
        self.assertTrue(all(s == 0.0 for s in tf.states))

    def test_compute_alone_does_not_advance_state(self):
        # Regression guard for the compute()/update_state() split: compute()
        # must be a pure read of current state, never mutate it -- RK4Solver
        # depends on being able to call compute() once per step without that
        # silently doing a Euler integration on the side.
        tf = TransferFunction()
        tf.params["Numerator"] = [1.0]
        tf.params["Denominator"] = [1.0, 1.0]
        tf.inputs["in"].value = 1.0
        tf.compute(0.0, 0.01)
        states_after_one_compute = list(tf.states)
        tf.compute(0.01, 0.01)
        self.assertEqual(tf.states, states_after_one_compute)

    def test_compute_chunk_matches_scalar_stepping(self):
        tf_scalar = TransferFunction()
        tf_scalar.params["Numerator"] = [1.0]
        tf_scalar.params["Denominator"] = [1.0, 1.0]
        tf_scalar.inputs["in"].value = 1.0
        dt = 0.01
        for i in range(50):
            step([tf_scalar], i * dt, dt)
        scalar_out = tf_scalar.outputs["out"].value

        tf_chunk = TransferFunction()
        tf_chunk.params["Numerator"] = [1.0]
        tf_chunk.params["Denominator"] = [1.0, 1.0]
        tf_chunk.inputs["in"].vector_value = np.full(50, 1.0)
        t_vec = np.arange(50) * dt
        tf_chunk.compute_chunk(t_vec, dt)
        tf_chunk.update_state_chunk(t_vec, dt)

        self.assertAlmostEqual(tf_chunk.outputs["out"].vector_value[-1], scalar_out, places=6)

    def test_get_derivative_is_pure_and_matches_manual_euler_step(self):
        tf = TransferFunction()
        tf.params["Numerator"] = [1.0]
        tf.params["Denominator"] = [1.0, 1.0]
        tf.inputs["in"].value = 1.0
        tf.compute(0.0, 0.01)  # refresh matrices/states via cache check

        deriv = tf.get_derivative(0.0, 0.01)
        self.assertEqual(len(deriv), 1)
        # H(s) = 1/(s+1) -> state-space: x' = -x + u
        self.assertAlmostEqual(deriv[0], -tf.states[0] + 1.0, places=6)

        state_before = list(tf.states)
        tf.get_derivative(0.0, 0.01)
        self.assertEqual(tf.states, state_before)  # still pure, no mutation

    def test_rk4_solver_converges_faster_than_euler_at_coarse_dt(self):
        # Both solvers should converge to the analytic steady-state (1.0),
        # but RK4 should be closer after the same number of coarse steps.
        from engine.simulation.solvers import EulerSolver, RK4Solver

        def run(solver_cls, dt, steps):
            tf = TransferFunction()
            tf.params["Numerator"] = [1.0]
            tf.params["Denominator"] = [1.0, 1.0]
            tf.inputs["in"].value = 1.0
            solver = solver_cls()
            for i in range(steps):
                solver.step([tf], [tf], i * dt, dt)
            # compute() is a pure read of the now-fully-advanced state (see
            # test_compute_alone_does_not_advance_state), so this reflects
            # the state after all `steps` integrations without adding another.
            tf.compute(steps * dt, dt)
            return tf.outputs["out"].value

        dt = 0.2  # coarse step relative to the time constant (1.0)
        steps = 15
        euler_out = run(EulerSolver, dt, steps)
        rk4_out = run(RK4Solver, dt, steps)

        analytic = 1.0 - np.exp(-dt * steps)
        self.assertLess(abs(rk4_out - analytic), abs(euler_out - analytic))


class TestPID(unittest.TestCase):
    def test_proportional_only(self):
        pid = PID()
        pid.params["Kp"] = 2.0
        pid.params["Ki"] = 0.0
        pid.params["Kd"] = 0.0
        pid.inputs["in"].value = 3.0
        pid.compute(0.0, 0.1)
        self.assertAlmostEqual(pid.outputs["out"].value, 6.0)

    def test_integral_accumulates(self):
        pid = PID()
        pid.params["Kp"] = 0.0
        pid.params["Ki"] = 1.0
        pid.params["Kd"] = 0.0
        pid.inputs["in"].value = 2.0
        for i in range(10):
            pid.compute(i * 0.1, 0.1)
        # integral of constant 2.0 over 1.0s = 2.0
        self.assertAlmostEqual(pid.outputs["out"].value, 2.0, places=6)

    def test_derivative_reacts_to_change(self):
        pid = PID()
        pid.params["Kp"] = 0.0
        pid.params["Ki"] = 0.0
        pid.params["Kd"] = 1.0
        pid.inputs["in"].value = 0.0
        pid.compute(0.0, 0.1)

        pid.inputs["in"].value = 1.0
        pid.compute(0.1, 0.1)
        self.assertAlmostEqual(pid.outputs["out"].value, 10.0)

    def test_reset_clears_state(self):
        pid = PID()
        pid.params["Ki"] = 1.0
        pid.inputs["in"].value = 5.0
        pid.compute(0.0, 0.1)
        self.assertNotEqual(pid.integral, 0.0)
        pid.reset()
        self.assertEqual(pid.integral, 0.0)
        self.assertEqual(pid.prev_error, 0.0)


class TestDelay(unittest.TestCase):
    def test_zero_delay_is_passthrough(self):
        d = Delay()
        set_params(d, DelaySteps=0)
        d.inputs["in"].value = 42.0
        d.compute(0.0, 0.1)
        self.assertEqual(d.outputs["out"].value, 42.0)

    def test_n_step_delay(self):
        d = Delay()
        set_params(d, DelaySteps=3, InitialValue=0.0)

        outputs = []
        for i in range(6):
            d.inputs["in"].value = float(i + 1)  # 1, 2, 3, 4, 5, 6
            d.compute(i * 0.1, 0.1)
            outputs.append(d.outputs["out"].value)

        # First 3 outputs should be the initial value, then delayed inputs.
        self.assertEqual(outputs[:3], [0.0, 0.0, 0.0])
        self.assertEqual(outputs[3:], [1.0, 2.0, 3.0])

    def test_reset_restores_initial_value(self):
        d = Delay()
        set_params(d, DelaySteps=2, InitialValue=-1.0)
        d.inputs["in"].value = 99.0
        for i in range(3):
            d.compute(i * 0.1, 0.1)

        d.reset()
        d.inputs["in"].value = 0.0
        d.compute(0.0, 0.1)
        self.assertEqual(d.outputs["out"].value, -1.0)


if __name__ == "__main__":
    unittest.main()
