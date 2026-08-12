"""Tests for the core simulation engine: execution ordering and batch running."""
import unittest
import numpy as np

from engine.simulation.executor import ExecutionOrdering, AlgebraicLoopError
from engine.simulation.engine import SimulationEngine
from engine.blocks.constant import Constant
from engine.blocks.gain import Gain
from engine.blocks.sum_block import Sum
from engine.blocks.integrator import Integrator
from engine.blocks.delay import Delay
from engine.blocks.scope import Scope
from engine.blocks.transfer_function import TransferFunction
from engine.blocks.state_space import StateSpace
from engine.blocks.discrete_transfer_function import DiscreteTransferFunction
from engine.blocks.subgraph import SubGraph

from engine.variables import make_variable_ref, is_variable_ref, get_active_variables, set_active_variables

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

    def test_loop_closed_through_strictly_proper_transfer_function_does_not_raise(self):
        # Regression test: TransferFunction's default H(s) = 1/(s+1) is
        # strictly proper (D == 0) and has no direct feedthrough, exactly
        # like Integrator -- closing a feedback loop through it (a very
        # common pattern: controller -> plant -> feedback to a Sum) must
        # sort successfully, not be flagged as an algebraic loop.
        s = Sum()
        g = Gain()
        tf = TransferFunction()  # default 1/(s+1), D == 0
        connect(s, "in2", tf)
        connect(g, "in", s)
        connect(tf, "in", g)

        ordered = ExecutionOrdering.topological_sort([s, g, tf])
        self.assertEqual(set(ordered), {s, g, tf})

    def test_loop_closed_through_proper_transfer_function_still_raises(self):
        # A proper (not strictly proper) TF, e.g. H(s) = (s+1)/(s+1), has a
        # nonzero D term -- a loop closed purely through it with nothing
        # else to break it IS a genuine algebraic loop and must still raise.
        g = Gain()
        tf = TransferFunction()
        tf.params["Numerator"] = [1.0, 1.0]
        tf.params["Denominator"] = [1.0, 1.0]
        connect(g, "in", tf)
        connect(tf, "in", g)

        with self.assertRaises(AlgebraicLoopError):
            ExecutionOrdering.topological_sort([g, tf])

    def test_loop_closed_through_state_space_with_zero_d_does_not_raise(self):
        g = Gain()
        ss = StateSpace()  # default D == 0.0
        connect(g, "in", ss)
        connect(ss, "in", g)

        ordered = ExecutionOrdering.topological_sort([g, ss])
        self.assertEqual(set(ordered), {g, ss})

    def test_loop_closed_through_two_subgraphs_broken_internally_does_not_raise(self):
        # Mirrors a real-world diagram shape: two SubGraphs
        # feeding each other directly at the top level (A.out -> B.in,
        # B.out -> A.in), each internally breaking the loop with a
        # strictly-proper TransferFunction (or Integrator) rather than a
        # top-level Delay/Integrator. Must sort successfully, not raise.
        sg_a = SubGraph()
        sg_a.internal_blocks_data = [
            {"id": "a_in", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "a_tf", "type": "TransferFunction",
             "params": {"Numerator": [1.0], "Denominator": [1.0, 1.0]}},
            {"id": "a_out", "type": "OutputPort", "params": {"PortName": "Out"}},
        ]
        sg_a.internal_connections_data = [
            {"from_block_id": "a_in", "from_port": "out", "to_block_id": "a_tf", "to_port": "in"},
            {"from_block_id": "a_tf", "from_port": "out", "to_block_id": "a_out", "to_port": "in"},
        ]
        sg_a.sync_ports_from_data()

        sg_b = SubGraph()
        sg_b.internal_blocks_data = [
            {"id": "b_in", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "b_integ", "type": "Integrator", "params": {}},
            {"id": "b_out", "type": "OutputPort", "params": {"PortName": "Out"}},
        ]
        sg_b.internal_connections_data = [
            {"from_block_id": "b_in", "from_port": "out", "to_block_id": "b_integ", "to_port": "in"},
            {"from_block_id": "b_integ", "from_port": "out", "to_block_id": "b_out", "to_port": "in"},
        ]
        sg_b.sync_ports_from_data()

        connect(sg_b, "In", sg_a, "Out")
        connect(sg_a, "In", sg_b, "Out")

        ordered = ExecutionOrdering.topological_sort([sg_a, sg_b])
        self.assertEqual(set(ordered), {sg_a, sg_b})

    def test_loop_closed_through_subgraph_with_unrelated_diagnostic_output_does_not_raise(self):
        # Regression test for a real false positive: a SubGraph whose LOOP
        # output is properly state-broken (through a strictly-proper TF),
        # but which ALSO exposes a second, unrelated output fed straight
        # (algebraically) off the same input for diagnostics -- e.g. a
        # monitoring tap nobody else is wired to. The unrelated output's
        # feedthrough must not make the loop-relevant input look coupled.
        sg = SubGraph()
        sg.internal_blocks_data = [
            {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "tf1", "type": "TransferFunction",
             "params": {"Numerator": [1.0], "Denominator": [1.0, 1.0]}},  # D == 0
            {"id": "out_loop", "type": "OutputPort", "params": {"PortName": "LoopOut"}},
            {"id": "out_diag", "type": "OutputPort", "params": {"PortName": "DiagOut"}},
        ]
        sg.internal_connections_data = [
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "tf1", "to_port": "in"},
            {"from_block_id": "tf1", "from_port": "out", "to_block_id": "out_loop", "to_port": "in"},
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "out_diag", "to_port": "in"},
        ]
        sg.sync_ports_from_data()

        g = Gain()
        connect(g, "in", sg, "LoopOut")
        connect(sg, "In", g)
        # DiagOut deliberately left unconnected -- an unused diagnostic tap.

        ordered = ExecutionOrdering.topological_sort([sg, g])
        self.assertEqual(set(ordered), {sg, g})

    def test_scope_on_subgraph_diagnostic_output_does_not_create_false_loop(self):
        # Regression test for a real bug: wiring a Scope to a SubGraph's
        # otherwise-unused diagnostic output (fed algebraically off a
        # signal that's ALSO part of an external feedback loop broken
        # elsewhere by a strictly-proper TF) used to "activate" that
        # output's internal coupling and turn an already-working diagram
        # into a false algebraic-loop error, purely because something
        # started watching it. A Scope can never legitimately be part of a
        # cycle (nothing depends on it), so it must not be able to cause one.
        sg = SubGraph()
        sg.internal_blocks_data = [
            {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "tf1", "type": "TransferFunction",
             "params": {"Numerator": [1.0], "Denominator": [1.0, 1.0]}},  # D == 0
            {"id": "out_loop", "type": "OutputPort", "params": {"PortName": "LoopOut"}},
            {"id": "out_diag", "type": "OutputPort", "params": {"PortName": "DiagOut"}},
        ]
        sg.internal_connections_data = [
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "tf1", "to_port": "in"},
            {"from_block_id": "tf1", "from_port": "out", "to_block_id": "out_loop", "to_port": "in"},
            {"from_block_id": "in1", "from_port": "out", "to_block_id": "out_diag", "to_port": "in"},
        ]
        sg.sync_ports_from_data()

        g = Gain()
        connect(g, "in", sg, "LoopOut")
        connect(sg, "In", g)

        scope = Scope()
        connect(scope, "in1", sg, "DiagOut")  # watching the diagnostic tap

        ordered = ExecutionOrdering.topological_sort([sg, g, scope])
        self.assertEqual(set(ordered), {sg, g, scope})
        # The scope must never be reported as part of a loop even when its
        # presence forces the sink-exclusion fallback path.
        self.assertLess(ordered.index(sg), ordered.index(scope))

    def test_scope_only_chain_still_orders_sources_before_sinks(self):
        # Regression guard for the fix above: excluding sink consumption
        # from cycle detection must not break the ordinary (non-cyclic)
        # case where a Scope is the ONLY consumer of a chain.
        c = Constant()
        g = Gain()
        connect(g, "in", c)
        scope = Scope()
        connect(scope, "in1", g)

        ordered = ExecutionOrdering.topological_sort([scope, g, c])
        self.assertEqual(ordered, [c, g, scope])

    def test_loop_closed_through_discrete_tf_with_zero_b0_does_not_raise(self):
        g = Gain()
        dtf = DiscreteTransferFunction()
        dtf.params["Numerator"] = [0.0, 0.5]  # b0 == 0
        dtf.params["Denominator"] = [1.0, -0.5]
        connect(g, "in", dtf)
        connect(dtf, "in", g)

        ordered = ExecutionOrdering.topological_sort([g, dtf])
        self.assertEqual(set(ordered), {g, dtf})


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

    def test_check_diagram_clean_diagram_returns_no_issues(self):
        c = Constant(); set_params(c, Value=3.0)
        g = Gain(); connect(g, "in", c)
        scope = Scope(); connect(scope, "in1", g)

        engine = SimulationEngine()
        engine.blocks = [c, g, scope]
        self.assertEqual(engine.check_diagram(), [])

    def test_check_diagram_flags_algebraic_loop_as_error(self):
        g1 = Gain()
        g2 = Gain()
        connect(g1, "in", g2)
        connect(g2, "in", g1)

        engine = SimulationEngine()
        engine.blocks = [g1, g2]
        issues = engine.check_diagram()

        self.assertTrue(any(i.startswith("ERROR:") for i in issues))

    def test_check_diagram_flags_unconnected_input_as_warning(self):
        s = Sum()  # in1, in2 both unconnected

        engine = SimulationEngine()
        engine.blocks = [s]
        issues = engine.check_diagram()

        self.assertTrue(any(i.startswith("WARNING:") and "in1" in i for i in issues))
        self.assertTrue(any(i.startswith("WARNING:") and "in2" in i for i in issues))
        self.assertFalse(any(i.startswith("ERROR:") for i in issues))

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


class TestSimulationEngineVariables(unittest.TestCase):
    """A block param bound via make_variable_ref() (typing a name into a
    param editor / a script's var()) resolves against SimulationEngine.variables -- see
    engine/variables.py, which replaced the old "$VarName"-prefixed-string
    convention."""

    def setUp(self):
        self._saved = get_active_variables()

    def tearDown(self):
        set_active_variables(self._saved)

    def test_configure_registers_and_resolves_variables(self):
        c = Constant()
        set_params(c, Value=3.0)
        g = Gain()
        g.params["Gain"] = make_variable_ref("K")
        connect(g, "in", c)
        scope = Scope()
        connect(scope, "in1", g)

        engine = SimulationEngine()
        engine.configure([c, g, scope], duration=0.05, dt=0.01, variables={"K": 2.0})
        result = engine.run()

        self.assertTrue(result.success, result.error_message)
        data = result.scope_data["Scope"]["data"]
        self.assertTrue((data == 6.0).all())

    def test_design_time_param_unchanged_after_run(self):
        # run() must restore the live block's params (reference intact)
        # after the run, not leave the resolved literal baked in --
        # otherwise the binding would only ever work for one run.
        g = Gain()
        g.params["Gain"] = make_variable_ref("K")
        c = Constant()
        connect(g, "in", c)

        engine = SimulationEngine()
        engine.configure([c, g], duration=0.05, dt=0.01, variables={"K": 5.0})
        engine.run()

        self.assertTrue(is_variable_ref(g.params["Gain"]))

    def test_check_diagram_flags_undeclared_top_level_variable(self):
        g = Gain()
        g.params["Gain"] = make_variable_ref("Missing")
        c = Constant()
        connect(g, "in", c)

        engine = SimulationEngine()
        engine.configure([c, g], duration=1.0, dt=0.1, variables={})
        issues = engine.check_diagram()

        self.assertTrue(any(
            i.startswith("ERROR:") and "Missing" in i and "Gain" in i for i in issues
        ))

    def test_check_diagram_flags_undeclared_variable_nested_in_subgraph(self):
        sg = SubGraph()
        sg.internal_blocks_data = [
            {"id": "in1", "type": "InputPort", "params": {"PortName": "In"}},
            {"id": "gain1", "type": "Gain", "params": {"Gain": make_variable_ref("Deep")}},
            {"id": "out1", "type": "OutputPort", "params": {"PortName": "Out"}},
        ]
        sg.internal_connections_data = []
        sg.sync_ports_from_data()

        engine = SimulationEngine()
        engine.configure([sg], duration=1.0, dt=0.1, variables={})
        issues = engine.check_diagram()

        self.assertTrue(any(i.startswith("ERROR:") and "Deep" in i for i in issues))

    def test_check_diagram_passes_when_variable_declared(self):
        g = Gain()
        g.params["Gain"] = make_variable_ref("K")
        c = Constant()
        connect(g, "in", c)

        engine = SimulationEngine()
        engine.configure([c, g], duration=1.0, dt=0.1, variables={"K": 1.0})
        issues = engine.check_diagram()

        self.assertFalse(any(i.startswith("ERROR:") for i in issues))

    def test_matrix_valued_param_can_bind_to_array_variable(self):
        # Not just scalars: resolve_params() substitutes whatever the
        # variable's value IS -- here a whole 1x1 matrix -- straight into
        # the param, and StateSpace's own matrix handling (already tolerant
        # of any numpy-convertible input) takes it from there. No engine
        # code needed to know this is "a matrix" vs. a plain float.
        sg = StateSpace()
        sg.params["A"] = make_variable_ref("Amat")
        sg.params["B"] = [1.0]
        sg.params["C"] = [1.0]
        sg.params["D"] = 0.0
        c = Constant()
        set_params(c, Value=1.0)
        connect(sg, "in", c)

        engine = SimulationEngine()
        engine.configure([c, sg], duration=0.05, dt=0.01, variables={"Amat": [[-2.0]]})
        result = engine.run()

        self.assertTrue(result.success, result.error_message)
        self.assertTrue(np.allclose(sg._A, [[-2.0]]))
        # Design-time param is untouched -- still the reference, not a
        # baked-in number -- so a later run with a different value works.
        self.assertTrue(is_variable_ref(sg.params["A"]))

    def test_vector_valued_param_can_bind_to_array_variable(self):
        tf = TransferFunction()
        tf.params["Numerator"] = make_variable_ref("Num")
        tf.params["Denominator"] = [1.0, 1.0]
        c = Constant()
        connect(tf, "in", c)

        engine = SimulationEngine()
        engine.configure([c, tf], duration=0.05, dt=0.01, variables={"Num": [2.0, 0.0]})
        result = engine.run()

        self.assertTrue(result.success, result.error_message)
        self.assertTrue(is_variable_ref(tf.params["Numerator"]))


if __name__ == "__main__":
    unittest.main()
