"""Tests for gui/managers/theme_manager.py -- the app-wide light/dark mode
toggle. Every test resets QSettings/UIConfig/icon_factory module state in
tearDown: MainWindow() writes the current theme to the SAME real
QSettings("BlocSimPy", "BlocSimPy") store the actual app uses (see
_restore_window_state()/closeEvent() -- geometry does the same), and
UIConfig/icon_factory hold their current palette as plain module/class
state, not per-instance -- leaving either on "dark" after a test would
leak into every test file that runs after this one, and into the next
real app launch on this machine.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

_SETTINGS_KEY = "theme/mode"


def _build_window():
    from gui.main_window import MainWindow
    return MainWindow()


class _ThemeTestCase(unittest.TestCase):
    def setUp(self):
        self._settings = QSettings("BlocSimPy", "BlocSimPy")
        self._had_saved_value = self._settings.contains(_SETTINGS_KEY)
        self._saved_value = self._settings.value(_SETTINGS_KEY)
        self._settings.remove(_SETTINGS_KEY)

    def tearDown(self):
        from gui import icon_factory
        from config.ui_config import UIConfig
        icon_factory.set_theme("light")
        UIConfig.apply_theme("light")
        if self._had_saved_value:
            self._settings.setValue(_SETTINGS_KEY, self._saved_value)
        else:
            self._settings.remove(_SETTINGS_KEY)


class TestThemeDefaultsToLight(_ThemeTestCase):
    def test_no_saved_preference_defaults_to_light(self):
        w = _build_window()
        self.assertEqual(w.theme_manager.mode, "light")

    def test_script_editor_defaults_to_light(self):
        import tempfile
        w = _build_window()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "demo.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            w.script_manager.open_script(path)
            self.assertEqual(w.active_script_widget().mode, "light")


class TestThemeToggle(_ThemeTestCase):
    def test_toggle_switches_mode_and_persists(self):
        w = _build_window()
        self.assertEqual(w.theme_manager.mode, "light")

        w.theme_manager.toggle()
        self.assertEqual(w.theme_manager.mode, "dark")
        self.assertEqual(self._settings.value(_SETTINGS_KEY), "dark")

        w.theme_manager.toggle()
        self.assertEqual(w.theme_manager.mode, "light")
        self.assertEqual(self._settings.value(_SETTINGS_KEY), "light")

    def test_saved_dark_preference_is_restored_on_next_construction(self):
        w = _build_window()
        w.theme_manager.toggle()  # -> dark, persisted
        self.assertEqual(self._settings.value(_SETTINGS_KEY), "dark")

        w2 = _build_window()
        self.assertEqual(w2.theme_manager.mode, "dark")

    def test_toggle_updates_qapplication_stylesheet(self):
        from config import theme as theme_config
        w = _build_window()
        w.theme_manager.toggle()
        self.assertEqual(_app.styleSheet(), theme_config.stylesheet_for("dark"))

        w.theme_manager.toggle()
        self.assertEqual(_app.styleSheet(), theme_config.stylesheet_for("light"))

    def test_toggle_updates_canvas_colors(self):
        from config.ui_config import UIConfig
        w = _build_window()
        w.theme_manager.toggle()
        self.assertEqual(UIConfig.BACKGROUND_COLOR.name(), "#1b1b1d")
        self.assertEqual(UIConfig.CURRENT_THEME, "dark")

        w.theme_manager.toggle()
        self.assertEqual(UIConfig.BACKGROUND_COLOR.name(), "#eef0f3")
        self.assertEqual(UIConfig.CURRENT_THEME, "light")

    def test_toggle_updates_icon_stroke_color(self):
        from gui import icon_factory
        w = _build_window()
        w.theme_manager.toggle()
        self.assertEqual(icon_factory._STROKE.name(), "#d4d4d4")

        w.theme_manager.toggle()
        self.assertEqual(icon_factory._STROKE.name(), "#3a3a3c")

    def test_toggle_theme_action_is_wired_to_toggle(self):
        w = _build_window()
        self.assertEqual(w.theme_manager.mode, "light")
        w.toolbar_manager.action_toggle_theme.trigger()
        self.assertEqual(w.theme_manager.mode, "dark")


class TestThemeRefreshesOpenWidgets(_ThemeTestCase):
    def test_toggle_recolors_open_script_tab(self):
        import tempfile
        w = _build_window()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = os.path.join(tmp_dir, "demo.py")
            with open(path, "w", encoding="utf-8") as f:
                f.write("x = 1\n")
            w.script_manager.open_script(path)
            widget = w.active_script_widget()
            self.assertEqual(widget.mode, "light")

            w.theme_manager.toggle()
            self.assertEqual(widget.mode, "dark")

    def test_toggle_recolors_console(self):
        w = _build_window()
        console = w.dock_manager.console_widget
        self.assertEqual(console.mode, "light")

        w.theme_manager.toggle()
        self.assertEqual(console.mode, "dark")

    def test_toggle_repaints_open_diagram_background(self):
        from config.ui_config import UIConfig
        w = _build_window()
        w.open_diagram_tab()
        doc = w._diagrams[0]

        w.theme_manager.toggle()

        self.assertEqual(doc.scene.backgroundBrush().color().name(), UIConfig.BACKGROUND_COLOR.name())
        self.assertEqual(UIConfig.BACKGROUND_COLOR.name(), "#1b1b1d")


if __name__ == "__main__":
    unittest.main()
