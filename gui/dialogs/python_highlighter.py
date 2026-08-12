"""Python syntax highlighter for the Script Editor -- rule-based (regex +
QTextCharFormat via QSyntaxHighlighter, the standard Qt approach), giving
ScriptEditorWidget's plain QTextEdit the same color-coded reading a real
Python IDE would: keywords, strings, comments, numbers, decorators, and
(as a BlocSimPy-specific touch) the scripting API's own function names
(add_block, sim, set_param, ...) in their own color so they visually stand
out from ordinary Python keywords/builtins -- they're what a Script
actually spends most of its time calling.

Like most regex-based highlighters (this isn't a real tokenizer), it has
one known blind spot: a "#" that appears INSIDE a string literal is still
treated as starting a comment, since the comment rule doesn't know it's
inside a string. Harmless in practice for the short, imperative
automation scripts this editor is meant for, and fixing it properly would
need a real lexer, not worth it for this.
"""
import keyword
import builtins
from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont

# One palette per app theme (see gui/managers/theme_manager.py) -- LIGHT is
# VS Code "Light+"-inspired, DARK is VS Code "Dark+"-inspired, so the editor
# reads like a real IDE in either mode instead of a dark-on-dark or
# light-on-dark mismatch with the rest of the app.
_PALETTES = {
    "light": {
        "keyword": "#0000ff",
        "builtin": "#267f99",
        "api": "#795e26",
        "self": "#001080",
        "number": "#098658",
        "string": "#a31515",
        "comment": "#008000",
    },
    "dark": {
        "keyword": "#569cd6",
        "builtin": "#4ec9b0",
        "api": "#dcdcaa",
        "self": "#9cdcfe",
        "number": "#b5cea8",
        "string": "#ce9178",
        "comment": "#6a9955",
    },
}

# Two independent bits so a line can (in principle) be resumed out of
# either kind of triple-quoted string without one clobbering the other's
# in-progress state -- see highlightBlock()/_highlight_multiline_string().
_IN_TRIPLE_DOUBLE = 1
_IN_TRIPLE_SINGLE = 2


def _char_format(color, bold=False, italic=False):
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(color))
    if bold:
        fmt.setFontWeight(QFont.Bold)
    if italic:
        fmt.setFontItalic(True)
    return fmt


class PythonHighlighter(QSyntaxHighlighter):
    """Attach to a QTextEdit's document (`PythonHighlighter(editor.document())`)
    and it repaints automatically as the user types -- QSyntaxHighlighter
    hooks QTextDocument's own change signals, nothing else needs to call
    it. `api_names` (optional) are colored like BlocSimPy's own scripting
    functions instead of plain identifiers. `mode` ("light"/"dark") picks
    which palette above to color with -- see set_mode() to switch it later,
    e.g. when the app-wide theme toggles (gui/managers/theme_manager.py)."""

    def __init__(self, document, api_names=(), mode="light"):
        super().__init__(document)

        # Patterns are theme-independent and built once; only the
        # QTextCharFormat colors depend on `mode`, so set_mode() just
        # rebuilds the (pattern, format) pairing rather than re-deriving
        # every QRegularExpression from scratch.
        self._keyword_patterns = [QRegularExpression(rf"\b{word}\b") for word in keyword.kwlist]
        self._builtin_patterns = [
            QRegularExpression(rf"\b{name}\b") for name in dir(builtins) if not name.startswith("_")
        ]
        self._api_patterns = [QRegularExpression(rf"\b{name}\b") for name in api_names]
        self._self_pattern = QRegularExpression(r"\bself\b")
        self._decorator_pattern = QRegularExpression(r"@[A-Za-z_][A-Za-z0-9_.]*")
        self._number_pattern = QRegularExpression(r"\b[0-9]+\.?[0-9]*([eE][+-]?[0-9]+)?\b")
        self._single_string_pattern = QRegularExpression(r"'[^'\\\n]*(\\.[^'\\\n]*)*'")
        self._double_string_pattern = QRegularExpression(r'"[^"\\\n]*(\\.[^"\\\n]*)*"')
        self._comment_pattern = QRegularExpression(r"#[^\n]*")

        self._triple_double = QRegularExpression(r'"""')
        self._triple_single = QRegularExpression(r"'''")

        self.set_mode(mode)

    def set_mode(self, mode):
        """Re-color every rule for `mode` ("light"/"dark") and repaint."""
        colors = _PALETTES.get(mode, _PALETTES["light"])
        self.mode = "dark" if mode == "dark" else "light"

        keyword_fmt = _char_format(colors["keyword"], bold=True)
        builtin_fmt = _char_format(colors["builtin"])
        api_fmt = _char_format(colors["api"], bold=True)
        string_fmt = _char_format(colors["string"])

        # Ordered so later entries win where they overlap a match from an
        # earlier one (setFormat() on a span simply overwrites) -- keywords/
        # builtins/numbers/decorators first, strings and comments last, so
        # e.g. a keyword-looking word inside a string reads as a string,
        # not a keyword.
        self._rules = []
        self._rules += [(p, keyword_fmt) for p in self._keyword_patterns]
        self._rules += [(p, builtin_fmt) for p in self._builtin_patterns]
        self._rules += [(p, api_fmt) for p in self._api_patterns]
        self._rules.append((self._self_pattern, _char_format(colors["self"], italic=True)))
        self._rules.append((self._decorator_pattern, _char_format(colors["api"])))
        self._rules.append((self._number_pattern, _char_format(colors["number"])))
        self._rules.append((self._single_string_pattern, string_fmt))
        self._rules.append((self._double_string_pattern, string_fmt))
        self._rules.append((self._comment_pattern, _char_format(colors["comment"], italic=True)))

        self._string_fmt = string_fmt
        self.rehighlight()

    def highlightBlock(self, text):
        for pattern, fmt in self._rules:
            match_iter = pattern.globalMatch(text)
            while match_iter.hasNext():
                m = match_iter.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)

        self.setCurrentBlockState(0)
        self._highlight_multiline_string(text, self._triple_double, _IN_TRIPLE_DOUBLE)
        self._highlight_multiline_string(text, self._triple_single, _IN_TRIPLE_SINGLE)

    def _highlight_multiline_string(self, text, delimiter, state_bit):
        """Paint text spanned by a delimiter...delimiter (e.g. \"\"\"..\"\"\")
        pair that may cross line boundaries, tracked via
        previous/currentBlockState() -- the standard QSyntaxHighlighter
        pattern for multi-line constructs."""
        previous_state = self.previousBlockState()
        start = 0
        if previous_state > 0 and (previous_state & state_bit):
            end_match = delimiter.match(text)
            if not end_match.hasMatch():
                # The whole line is still inside the string from a
                # previous block; carry the state forward and stop.
                self.setFormat(0, len(text), self._string_fmt)
                self.setCurrentBlockState(self.currentBlockState() | state_bit)
                return
            start = end_match.capturedEnd()
            self.setFormat(0, start, self._string_fmt)

        while True:
            open_match = delimiter.match(text, start)
            if not open_match.hasMatch():
                break
            open_pos = open_match.capturedStart()
            close_match = delimiter.match(text, open_match.capturedEnd())
            if close_match.hasMatch():
                length = close_match.capturedEnd() - open_pos
                self.setFormat(open_pos, length, self._string_fmt)
                start = close_match.capturedEnd()
            else:
                self.setFormat(open_pos, len(text) - open_pos, self._string_fmt)
                self.setCurrentBlockState(self.currentBlockState() | state_bit)
                break
