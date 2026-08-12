"""Shared representation for a block parameter bound to a name declared in
the app's global variable store (see gui/managers/script_manager.py's
_GlobalVariablesView -- a plain top-level name a Script/the Console has
defined, e.g. `Kp = 2.5`, IS a global variable; the same names the Global
Variables dock reads) -- the one mechanism used both by ordinary blocks
and by blocks nested inside a SubGraph, replacing the old
"$VarName"-prefixed-string convention. That
convention only ever worked inside a SubGraph (resolved against that one
SubGraph's own params), was silently dropped or rejected by several block
types' editor dialogs, and needed a bespoke parsing pass in
ScriptManager.get_block_info() just to discover it.

A reference is a small, JSON-serializable marker dict -- NOT a bare or
prefixed string -- so it can never collide with a literal string parameter
value (a file path, an operator symbol, ...) the way a "$" sigil inside an
ordinary string always risked:

    {"__var__": "Kp"}

Everything that builds or inspects that shape should go through
make_variable_ref()/is_variable_ref()/variable_ref_name() rather than the
dict literal directly, so the representation can change in one place later
if needed.
"""
from typing import Any, Dict, List, Tuple

_KEY = "__var__"

# The live global variable store every variable reference resolves
# against -- registered once by ScriptManager.__init__ (pointing at its own
# global_variables, a filtered view over persistent_env -- the exact
# top-level names scripts/the Console already read and write) so engine
# code never has to import anything from gui/ to reach it. Defaults to an
# empty dict so headless/test code that never registers one (no GUI, no
# ScriptManager) still works -- just with no variables declared, same as a
# fresh session.
_active_variables: Dict[str, Any] = {}


def set_active_variables(variables: Dict[str, Any]) -> None:
    """Register the dict variable references resolve against. Takes the
    dict BY REFERENCE, not a copy -- callers (ScriptManager, tests) that
    keep mutating their own dict afterward see those changes picked up
    automatically, with nothing needing to re-register."""
    global _active_variables
    _active_variables = variables if variables is not None else {}


def get_active_variables() -> Dict[str, Any]:
    return _active_variables


def make_variable_ref(name: str) -> Dict[str, str]:
    """The param value meaning "bound to the global variable `name`"."""
    return {_KEY: name}


def is_variable_ref(value: Any) -> bool:
    return isinstance(value, dict) and set(value.keys()) == {_KEY}


def variable_ref_name(value: Any):
    """The referenced variable's name, or None if `value` isn't a
    reference."""
    return value[_KEY] if is_variable_ref(value) else None


def display_value(value: Any) -> str:
    """Human-readable form for showing a param value on a block's label --
    plain str(value) for a literal, or just the variable's own name for a
    reference, so a bound param doesn't show as the raw {'__var__': ...}
    dict."""
    name = variable_ref_name(value)
    return name if name is not None else str(value)


def resolve_params(params: Dict[str, Any], variables: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """A copy of `params` with every variable-reference value replaced by
    its current value from `variables` -- or `params` itself, UNCHANGED
    (same identity), if nothing in it is a reference, so callers can
    cheaply tell "did anything change" via `is`.

    Returns (resolved_params, missing_names): missing_names lists every
    referenced name not currently present in `variables`, in the order
    encountered. Callers (SimulationEngine.check_diagram_detailed())
    surface these as pre-flight errors rather than silently defaulting --
    an undeclared/renamed/cleared variable is a real mistake, not a 0.0
    default worth guessing at."""
    missing: List[str] = []
    resolved = None
    for key, value in params.items():
        name = variable_ref_name(value)
        if name is None:
            continue
        if resolved is None:
            resolved = dict(params)
        if name in variables:
            resolved[key] = variables[name]
        else:
            missing.append(name)
    return (resolved if resolved is not None else params), missing


def find_variable_refs(params: Dict[str, Any]) -> Dict[str, str]:
    """{param_name: variable_name} for every parameter in `params` bound to
    a global variable -- the introspection half of resolve_params(), used
    by ScriptManager.get_block_info() and anything else that needs to name
    the bound parameter, not just look up its value."""
    return {
        key: variable_ref_name(value)
        for key, value in params.items()
        if is_variable_ref(value)
    }
