"""A single parameter's value editor: one plain text field. Typing a
literal value (a number, or -- with a custom `parse`/`format_fn` pair -- a
matrix/vector/whatever else a field needs) works exactly like a bare
QLineEdit always did. Typing a bare NAME instead -- anything that doesn't
parse as a literal but reads as a plain identifier (letters/digits/
underscore, not leading with a digit) -- binds the parameter to that name
in the app's global variable store (engine/variables.py's
get_active_variables(), the same top-level names the Global Variables
dock shows and Tools -> Clear Global Variables wipes), whether or not it's
declared yet: an undeclared one is caught by SimulationEngine.check_diagram()
as a clear pre-flight error, not silently defaulted. No dropdown/picker --
you just type the name, the same as the old "$VarName" convention read,
minus the "$" and minus that convention's silent failure modes (see
engine/variables.py's module docstring for the full history).

Used by a block's own get_editor_dialog() in place of a bare QLineEdit
wherever a parameter should be bindable this way.
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLineEdit
from engine.variables import make_variable_ref, variable_ref_name


class ParseError:
    """Sentinel returned by ParamValueEditor.get_value() when the literal
    text couldn't be parsed AND doesn't read as a plausible variable name
    either -- callers should leave that parameter's previous value
    untouched rather than apply a bad one, matching this app's existing
    convention for an invalid edit (see e.g. StateSpace's old per-field
    `except ValueError: pass`), applied consistently now across every
    editor that uses this widget instead of varying bespoke handling
    (silently discard vs. crash vs. reject-and-reopen) per block."""


PARSE_ERROR = ParseError()


def _default_parse(text):
    # No fallback-to-string here (unlike the old default): every retrofit
    # of this widget so far is a numeric field, and a value that isn't a
    # number now either reads as a variable name (see get_value()) or is a
    # genuine bad edit (PARSE_ERROR) -- there's no third "keep it as a
    # literal string" case among them anymore.
    return float(text)


class ParamValueEditor(QWidget):
    """Drop-in replacement for a parameter QLineEdit: get_value()/
    set_value() round-trip either a literal value or a variable reference
    dict (see engine.variables.make_variable_ref) -- both through the SAME
    plain text field.

    parse(text) -> value / format_fn(value) -> text customize the literal
    side for a non-scalar parameter (a matrix, a coefficient vector, ...);
    both default to a plain float. A `parse` that raises should raise
    ValueError or TypeError -- get_value() then checks whether the typed
    text looks like a variable name before giving up with PARSE_ERROR."""

    def __init__(self, value, parent=None, parse=None, format_fn=None):
        super().__init__(parent)
        self._parse = parse or _default_parse
        self._format = format_fn or str

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.value_edit = QLineEdit()
        layout.addWidget(self.value_edit)

        self.set_value(value)

    def set_value(self, value):
        name = variable_ref_name(value)
        if name is not None:
            self.value_edit.setText(name)
        else:
            self.value_edit.setText("" if value is None else self._format(value))

    def get_value(self):
        text = self.value_edit.text()
        try:
            return self._parse(text)
        except (ValueError, TypeError):
            stripped = text.strip()
            if stripped.isidentifier():
                return make_variable_ref(stripped)
            return PARSE_ERROR


# Param keys that are names/labels, not values -- never variable-bindable,
# so a block's own get_editor_dialog() (looping generically over
# self.params.items()) must NOT wrap these in a ParamValueEditor: "G1"
# typed into BlockName isn't a literal number, so it would otherwise read
# as a plain identifier and silently get bound as if it were a variable
# name (see make_row_editor()'s docstring for the incident this fixes).
NON_BINDABLE_PARAM_KEYS = {"BlockName", "MaskIconPath"}


def make_row_editor(key, value):
    """A plain QLineEdit for a reserved name/label key (NON_BINDABLE_PARAM_
    KEYS), else a ParamValueEditor -- for a block's get_editor_dialog()
    that builds its rows generically from self.params.items() (Gain,
    Constant, IfElse, ...) rather than one field at a time. Read the
    result back with row_editor_value() so callers don't need to branch on
    which widget type they got."""
    if key in NON_BINDABLE_PARAM_KEYS:
        return QLineEdit(str(value))
    return ParamValueEditor(value)


def row_editor_value(editor):
    """The edited value back out of whatever make_row_editor() built --
    ParamValueEditor.get_value() (which may be PARSE_ERROR) for a bindable
    param, or the plain text for a reserved name/label key."""
    return editor.get_value() if hasattr(editor, "get_value") else editor.text()
