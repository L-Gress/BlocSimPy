"""Tests for gui/widgets/param_value_editor.py -- a plain text field that
doubles as a variable binder: typing a literal value works like an
ordinary QLineEdit, and typing a bare NAME (anything that parses as an
identifier but not as the field's literal type) binds the parameter to
that name in the app's global variable store (see engine/variables.py for
the {"__var__": name} reference it round-trips) -- no dropdown/picker.
Covers both the default scalar (float) round-trip and a custom parse/
format pair for array/matrix-valued parameters (StateSpace's A/B/C,
TransferFunction's Numerator/Denominator, ...).
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtWidgets import QApplication

from engine.variables import make_variable_ref, is_variable_ref, set_active_variables, get_active_variables
from engine.blocks.lookup_table import LookupTable
from engine.blocks.gain import Gain
from engine.blocks.constant import Constant
from gui.widgets.param_value_editor import (
    ParamValueEditor, PARSE_ERROR, make_row_editor, row_editor_value, NON_BINDABLE_PARAM_KEYS,
)

_app = QApplication.instance() or QApplication([])


def _matrix_parse(text):
    rows = [r.strip() for r in text.split(';') if r.strip()]
    return [[float(p) for p in row.split()] for row in rows]


def _matrix_format(value):
    return "; ".join(" ".join(str(v) for v in row) for row in value)


class TestParamValueEditorScalar(unittest.TestCase):
    def setUp(self):
        self._saved = get_active_variables()
        set_active_variables({"K": 2.0, "Kp": 1.5})

    def tearDown(self):
        set_active_variables(self._saved)

    def test_literal_float_round_trips(self):
        editor = ParamValueEditor(3.5)
        self.assertEqual(editor.value_edit.text(), "3.5")
        self.assertEqual(editor.get_value(), 3.5)

    def test_set_value_with_reference_shows_bare_name(self):
        editor = ParamValueEditor(make_variable_ref("K"))
        self.assertEqual(editor.value_edit.text(), "K")

    def test_typing_a_declared_name_returns_reference(self):
        editor = ParamValueEditor(2.0)
        editor.value_edit.setText("Kp")
        value = editor.get_value()
        self.assertTrue(is_variable_ref(value))
        self.assertEqual(value, make_variable_ref("Kp"))

    def test_typing_an_undeclared_name_still_binds_not_parse_error(self):
        # No picker to "declare" a variable first anymore -- typing any
        # plain identifier binds to it regardless of whether it exists
        # yet. An undeclared one is caught at Run time by
        # SimulationEngine.check_diagram()'s pre-flight check, not here.
        editor = ParamValueEditor(2.0)
        editor.value_edit.setText("NotYetDeclared")
        self.assertEqual(editor.get_value(), make_variable_ref("NotYetDeclared"))

    def test_reverting_to_a_number_gives_back_a_literal(self):
        editor = ParamValueEditor(make_variable_ref("K"))
        editor.value_edit.setText("9.5")
        self.assertEqual(editor.get_value(), 9.5)

    def test_text_that_is_neither_a_number_nor_an_identifier_is_parse_error(self):
        editor = ParamValueEditor(2.0)
        editor.value_edit.setText("1 2 3")
        self.assertIs(editor.get_value(), PARSE_ERROR)

    def test_whitespace_around_name_still_binds(self):
        editor = ParamValueEditor(1.0)
        editor.value_edit.setText("  Kp  ")
        self.assertEqual(editor.get_value(), make_variable_ref("Kp"))


class TestParamValueEditorCustomParse(unittest.TestCase):
    """Array/matrix-valued parameters use a custom parse/format pair
    instead of the default scalar round-trip -- the SAME typed-name
    binding works unchanged since resolution never inspects the value's
    shape (see engine/variables.py's module docstring)."""

    def setUp(self):
        self._saved = get_active_variables()
        set_active_variables({"Amat": [[-2.0, 0.0], [0.0, -3.0]]})

    def tearDown(self):
        set_active_variables(self._saved)

    def test_matrix_literal_round_trips(self):
        editor = ParamValueEditor([[0.0, 1.0], [-2.0, -3.0]], parse=_matrix_parse, format_fn=_matrix_format)
        self.assertEqual(editor.value_edit.text(), "0.0 1.0; -2.0 -3.0")
        self.assertEqual(editor.get_value(), [[0.0, 1.0], [-2.0, -3.0]])

    def test_typing_a_name_binds_a_matrix_field_too(self):
        editor = ParamValueEditor([[1.0]], parse=_matrix_parse, format_fn=_matrix_format)
        editor.value_edit.setText("Amat")
        self.assertEqual(editor.get_value(), make_variable_ref("Amat"))

    def test_malformed_matrix_text_is_parse_error_not_a_phantom_variable(self):
        # "not a matrix" has spaces -- not a valid identifier -- so a bad
        # edit here must NOT silently become a binding to a variable named
        # "not a matrix" (which could never resolve); it should surface as
        # PARSE_ERROR like any other bad edit.
        editor = ParamValueEditor([[1.0]], parse=_matrix_parse, format_fn=_matrix_format)
        editor.value_edit.setText("not a matrix")
        self.assertIs(editor.get_value(), PARSE_ERROR)

    def test_valid_edit_parses_correctly(self):
        editor = ParamValueEditor([[1.0]], parse=_matrix_parse, format_fn=_matrix_format)
        editor.value_edit.setText("1 2; 3 4")
        self.assertEqual(editor.get_value(), [[1.0, 2.0], [3.0, 4.0]])


class TestRowEditorBlockNameRegression(unittest.TestCase):
    """Regression coverage for a real bug: Gain/Constant/IfElse build their
    editor dialogs by looping generically over self.params.items(), which
    includes "BlockName" (e.g. "C1") alongside the real numeric param --
    "C1" isn't a number but IS a valid identifier, so wrapping it in a
    plain ParamValueEditor made every block's own name silently become a
    variable reference the instant its dialog was accepted. make_row_editor()/
    row_editor_value() (used by get_editor_dialog() in all three) must
    keep BlockName a plain, never-bindable string."""

    def setUp(self):
        self._saved = get_active_variables()
        set_active_variables({})

    def tearDown(self):
        set_active_variables(self._saved)

    def test_block_name_is_a_reserved_key(self):
        self.assertIn("BlockName", NON_BINDABLE_PARAM_KEYS)

    def test_make_row_editor_gives_block_name_a_plain_line_edit(self):
        editor = make_row_editor("BlockName", "C1")
        self.assertFalse(hasattr(editor, "get_value"))
        self.assertEqual(editor.text(), "C1")

    def test_row_editor_value_returns_plain_text_for_block_name(self):
        editor = make_row_editor("BlockName", "C1")
        self.assertEqual(row_editor_value(editor), "C1")

    def test_make_row_editor_still_binds_ordinary_params(self):
        editor = make_row_editor("Gain", 2.0)
        self.assertTrue(hasattr(editor, "get_value"))
        editor.value_edit.setText("Kp")
        self.assertEqual(row_editor_value(editor), make_variable_ref("Kp"))

    def test_gain_dialog_keeps_block_name_untouched_after_accept(self):
        g = Gain()
        g.params["BlockName"] = "G1"
        dialog = g.get_editor_dialog(None)
        dialog.accept()
        self.assertEqual(g.params["BlockName"], "G1")

    def test_constant_dialog_keeps_block_name_untouched_after_accept(self):
        c = Constant()
        c.params["BlockName"] = "C1"
        dialog = c.get_editor_dialog(None)
        dialog.accept()
        self.assertEqual(c.params["BlockName"], "C1")


class TestLookupTableDialogBinding(unittest.TestCase):
    """LookupTable's "Table" param isn't a single text field (it's a whole
    X/Y row table), so it gets its own bind checkbox + name field in
    LookupTableDialog rather than a ParamValueEditor -- same underlying
    mechanism (type the name, make_variable_ref()), covered separately
    here."""

    def setUp(self):
        self._saved = get_active_variables()
        set_active_variables({"Curve": [(0.0, 0.0), (1.0, 1.0)]})

    def tearDown(self):
        set_active_variables(self._saved)

    def test_unbound_dialog_returns_table_rows(self):
        lut = LookupTable()
        lut.params["Table"] = [(0.0, 0.0), (1.0, 10.0)]
        dialog = lut.get_editor_dialog(None)
        self.assertFalse(dialog.bind_check.isChecked())
        self.assertEqual(dialog.get_value(), [(0.0, 0.0), (1.0, 10.0)])

    def test_checking_bind_hides_table_and_shows_name_field(self):
        lut = LookupTable()
        dialog = lut.get_editor_dialog(None)
        dialog.bind_check.setChecked(True)
        self.assertFalse(dialog.var_name_edit.isHidden())
        self.assertTrue(dialog.table_widget.isHidden())

    def test_bound_dialog_returns_variable_reference(self):
        lut = LookupTable()
        dialog = lut.get_editor_dialog(None)
        dialog.bind_check.setChecked(True)
        dialog.var_name_edit.setText("Curve")
        self.assertEqual(dialog.get_value(), make_variable_ref("Curve"))

    def test_reopening_already_bound_block_preselects_binding(self):
        lut = LookupTable()
        lut.params["Table"] = make_variable_ref("Curve")
        dialog = lut.get_editor_dialog(None)
        self.assertTrue(dialog.bind_check.isChecked())
        self.assertEqual(dialog.var_name_edit.text(), "Curve")


if __name__ == "__main__":
    unittest.main()
