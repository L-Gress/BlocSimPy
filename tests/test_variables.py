"""Tests for engine/variables.py -- the variable-reference marker
({"__var__": name}), resolve_params()/find_variable_refs(), and the
active-variables registry that replaced the old "$VarName"-prefixed-string
convention (see engine/variables.py's module docstring)."""
import unittest

from engine.variables import (
    make_variable_ref, is_variable_ref, variable_ref_name, display_value,
    resolve_params, find_variable_refs, set_active_variables, get_active_variables,
)


class TestVariableRefMarker(unittest.TestCase):
    def test_make_and_inspect_ref(self):
        ref = make_variable_ref("Kp")
        self.assertTrue(is_variable_ref(ref))
        self.assertEqual(variable_ref_name(ref), "Kp")

    def test_non_ref_values_are_not_refs(self):
        for value in (1.0, "plain string", "$OldStyle", None, [1, 2], {"A": 1, "B": 2}):
            self.assertFalse(is_variable_ref(value))
            self.assertIsNone(variable_ref_name(value))

    def test_display_value(self):
        self.assertEqual(display_value(2.5), "2.5")
        self.assertEqual(display_value(make_variable_ref("Kp")), "Kp")


class TestResolveParams(unittest.TestCase):
    def test_no_refs_returns_same_object(self):
        params = {"Gain": 2.0, "BlockName": "G1"}
        resolved, missing = resolve_params(params, {})
        self.assertIs(resolved, params)
        self.assertEqual(missing, [])

    def test_resolves_declared_variable(self):
        params = {"Gain": make_variable_ref("Kp")}
        resolved, missing = resolve_params(params, {"Kp": 3.5})
        self.assertEqual(resolved["Gain"], 3.5)
        self.assertEqual(missing, [])
        # Original params dict is untouched -- resolution never mutates
        # the design-time value, only a copy.
        self.assertTrue(is_variable_ref(params["Gain"]))

    def test_reports_missing_variable(self):
        params = {"Gain": make_variable_ref("Kp")}
        resolved, missing = resolve_params(params, {})
        self.assertEqual(missing, ["Kp"])
        # Left as the unresolved reference rather than defaulted/crashed.
        self.assertTrue(is_variable_ref(resolved["Gain"]))

    def test_mixed_literal_and_ref_params(self):
        params = {"Gain": make_variable_ref("Kp"), "Offset": 1.0}
        resolved, missing = resolve_params(params, {"Kp": 5.0})
        self.assertEqual(resolved, {"Gain": 5.0, "Offset": 1.0})
        self.assertEqual(missing, [])


class TestFindVariableRefs(unittest.TestCase):
    def test_finds_only_bound_params(self):
        params = {"Gain": make_variable_ref("Kp"), "Offset": 1.0, "BlockName": "G1"}
        self.assertEqual(find_variable_refs(params), {"Gain": "Kp"})

    def test_empty_when_nothing_bound(self):
        self.assertEqual(find_variable_refs({"Gain": 2.0}), {})


class TestActiveVariablesRegistry(unittest.TestCase):
    def setUp(self):
        self._saved = get_active_variables()

    def tearDown(self):
        set_active_variables(self._saved)

    def test_defaults_to_empty_dict_when_never_registered(self):
        set_active_variables(None)
        self.assertEqual(get_active_variables(), {})

    def test_registered_dict_is_live_by_reference(self):
        store = {"Kp": 1.0}
        set_active_variables(store)
        store["Kp"] = 9.0
        self.assertEqual(get_active_variables()["Kp"], 9.0)
        self.assertIs(get_active_variables(), store)


if __name__ == "__main__":
    unittest.main()
