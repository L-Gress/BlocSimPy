"""Tests for gui/dialogs/python_highlighter.py -- the Script Editor's
syntax highlighter -- and its wiring into ScriptEditorWidget. Colors are
read from PythonHighlighter's own _PALETTES rather than hand-duplicated
hex strings here, so these tests can't drift out of sync with the real
palette by editing one and not the other.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtWidgets import QApplication, QTextEdit

from gui.dialogs.python_highlighter import PythonHighlighter, _PALETTES

_app = QApplication.instance() or QApplication([])

_LIGHT = _PALETTES["light"]
_DARK = _PALETTES["dark"]


def _color_at(editor, line, col):
    block = editor.document().findBlockByNumber(line)
    for fr in block.layout().formats():
        if fr.start <= col < fr.start + fr.length:
            return fr.format.foreground().color().name()
    return None


def _highlighted_editor(code, api_names=(), mode="light"):
    editor = QTextEdit()
    PythonHighlighter(editor.document(), api_names=api_names, mode=mode)
    editor.setPlainText(code)
    _app.processEvents()
    return editor


class TestPythonHighlighterSingleLine(unittest.TestCase):
    """Default (light) palette -- matches the Script Editor's default
    theme (see gui/dialogs/script_editor.py)."""

    def test_keyword_is_colored(self):
        editor = _highlighted_editor("if True:\n    pass\n")
        self.assertEqual(_color_at(editor, 0, 0), _LIGHT["keyword"])

    def test_comment_is_colored(self):
        editor = _highlighted_editor("# a comment\nx = 1\n")
        self.assertEqual(_color_at(editor, 0, 0), _LIGHT["comment"])

    def test_number_is_colored(self):
        editor = _highlighted_editor("x = 3.14\n")
        self.assertEqual(_color_at(editor, 0, 4), _LIGHT["number"])

    def test_single_quoted_string_is_colored(self):
        editor = _highlighted_editor("x = 'hello'\n")
        self.assertEqual(_color_at(editor, 0, 5), _LIGHT["string"])

    def test_double_quoted_string_is_colored(self):
        editor = _highlighted_editor('x = "hello"\n')
        self.assertEqual(_color_at(editor, 0, 5), _LIGHT["string"])

    def test_keyword_inside_a_string_reads_as_a_string_not_a_keyword(self):
        # Regression guard for the "later rules win" ordering -- "for" is
        # a Python keyword, but here it's just text inside a string.
        editor = _highlighted_editor("x = 'wait for it'\n")
        self.assertEqual(_color_at(editor, 0, 9), _LIGHT["string"])

    def test_plain_identifier_is_not_colored(self):
        editor = _highlighted_editor("my_variable = 1\n")
        self.assertIsNone(_color_at(editor, 0, 0))

    def test_self_is_colored_distinctly(self):
        editor = _highlighted_editor("self.x = 1\n")
        self.assertEqual(_color_at(editor, 0, 0), _LIGHT["self"])

    def test_decorator_is_colored(self):
        editor = _highlighted_editor("@property\ndef x(self): pass\n")
        self.assertEqual(_color_at(editor, 0, 0), _LIGHT["api"])


class TestPythonHighlighterDarkMode(unittest.TestCase):
    """Same rules, dark palette -- constructing with mode="dark" directly
    (not via set_mode()) exercises __init__'s own mode handling."""

    def test_keyword_is_colored(self):
        editor = _highlighted_editor("if True:\n    pass\n", mode="dark")
        self.assertEqual(_color_at(editor, 0, 0), _DARK["keyword"])

    def test_string_is_colored(self):
        editor = _highlighted_editor("x = 'hello'\n", mode="dark")
        self.assertEqual(_color_at(editor, 0, 5), _DARK["string"])


class TestPythonHighlighterSetMode(unittest.TestCase):
    def test_set_mode_recolors_and_repaints_existing_text(self):
        editor = QTextEdit()
        highlighter = PythonHighlighter(editor.document(), mode="light")
        editor.setPlainText("if True:\n    pass\n")
        _app.processEvents()
        self.assertEqual(_color_at(editor, 0, 0), _LIGHT["keyword"])

        highlighter.set_mode("dark")
        _app.processEvents()

        self.assertEqual(_color_at(editor, 0, 0), _DARK["keyword"])
        self.assertEqual(highlighter.mode, "dark")


class TestPythonHighlighterApiNames(unittest.TestCase):
    def test_api_name_gets_its_own_color(self):
        editor = _highlighted_editor("add_block('Gain')\n", api_names=["add_block", "sim"])
        self.assertEqual(_color_at(editor, 0, 0), _LIGHT["api"])

    def test_name_not_in_api_list_is_unaffected(self):
        editor = _highlighted_editor("some_other_call()\n", api_names=["add_block", "sim"])
        self.assertIsNone(_color_at(editor, 0, 0))


class TestPythonHighlighterMultilineStrings(unittest.TestCase):
    def test_triple_double_quoted_string_spans_lines(self):
        code = 'x = """line one\nline two"""\n'
        editor = _highlighted_editor(code)
        self.assertEqual(_color_at(editor, 0, 6), _LIGHT["string"])
        self.assertEqual(_color_at(editor, 1, 0), _LIGHT["string"])

    def test_triple_single_quoted_string_spans_lines(self):
        code = "x = '''line one\nline two'''\n"
        editor = _highlighted_editor(code)
        self.assertEqual(_color_at(editor, 0, 6), _LIGHT["string"])
        self.assertEqual(_color_at(editor, 1, 0), _LIGHT["string"])

    def test_block_state_resets_after_the_closing_triple_quote(self):
        code = '"""doc"""\nx = 1\n'
        editor = _highlighted_editor(code)
        self.assertEqual(editor.document().findBlockByNumber(0).userState(), 0)

    def test_line_after_open_triple_quote_carries_state_forward(self):
        code = 'x = """still open\n'
        editor = _highlighted_editor(code)
        self.assertEqual(editor.document().findBlockByNumber(0).userState(), 1)

    def test_double_and_single_triple_quotes_use_independent_state_bits(self):
        # A triple-double string containing an unmatched triple-single
        # delimiter-looking text shouldn't confuse the two trackers.
        code = 'x = """it\'s not a triple-single"""\n'
        editor = _highlighted_editor(code)
        self.assertEqual(editor.document().findBlockByNumber(0).userState(), 0)


class TestScriptEditorWidgetHighlighting(unittest.TestCase):
    def test_script_editor_attaches_a_highlighter_defaulting_to_light(self):
        from gui.dialogs.script_editor import ScriptEditorWidget
        from gui.managers.script_manager import ScriptManager
        from PySide6.QtCore import QObject

        class _FakeMainWindow(QObject):
            pass

        mw = _FakeMainWindow()
        sm = ScriptManager(mw)
        widget = ScriptEditorWidget(mw, sm, "demo.py", "add_block('Gain')\n")
        _app.processEvents()

        self.assertEqual(widget.mode, "light")
        self.assertIsInstance(widget.highlighter, PythonHighlighter)
        self.assertEqual(_color_at(widget.editor, 0, 0), _LIGHT["api"])  # add_block is API-colored

    def test_apply_theme_recolors_an_already_open_tab(self):
        from gui.dialogs.script_editor import ScriptEditorWidget
        from gui.managers.script_manager import ScriptManager
        from PySide6.QtCore import QObject

        class _FakeMainWindow(QObject):
            pass

        mw = _FakeMainWindow()
        sm = ScriptManager(mw)
        widget = ScriptEditorWidget(mw, sm, "demo.py", "add_block('Gain')\n")
        _app.processEvents()

        widget.apply_theme("dark")
        _app.processEvents()

        self.assertEqual(widget.mode, "dark")
        self.assertEqual(_color_at(widget.editor, 0, 0), _DARK["api"])


if __name__ == "__main__":
    unittest.main()
