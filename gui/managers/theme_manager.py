"""Light/dark mode for the whole app: switches the QSS stylesheet (config/
theme.py), the QGraphicsScene canvas palette (config/ui_config.py), the
hand-drawn toolbar/menu/tree icon colors (gui/icon_factory.py), and the
Script Editor/Console's own surface colors, then repaints whatever's
already on screen so the switch is visible immediately without restarting
the app. Persisted via the same QSettings instance MainWindow already uses
for window geometry, so the choice survives across sessions.

Defaults to light -- same "don't surprise the user with something they
didn't ask for" rule as every other default in this app (no diagram tab
open at startup, no auto-reopened Script, ...).
"""
from PySide6.QtWidgets import QApplication
from .. import icon_factory
from config import theme as theme_config
from config.ui_config import UIConfig

_SETTINGS_KEY = "theme/mode"


class ThemeManager:
    def __init__(self, main_window):
        self.main_window = main_window
        saved = main_window.settings.value(_SETTINGS_KEY, "light")
        self.mode = "dark" if saved == "dark" else "light"

    def apply(self, mode=None):
        """Apply `mode` ("light"/"dark", or the current self.mode if
        omitted) everywhere: app QSS, canvas colors, icon colors, and every
        already-open Script/Console/diagram surface. Persists the choice."""
        if mode is not None:
            self.mode = "dark" if mode == "dark" else "light"

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(theme_config.stylesheet_for(self.mode))

        UIConfig.apply_theme(self.mode)
        icon_factory.set_theme(self.mode)
        self.main_window.settings.setValue(_SETTINGS_KEY, self.mode)

        self._refresh_open_widgets()

    def toggle(self):
        self.apply("dark" if self.mode == "light" else "light")

    def _refresh_open_widgets(self):
        mw = self.main_window

        toolbar_manager = getattr(mw, "toolbar_manager", None)
        if toolbar_manager is not None and hasattr(toolbar_manager, "refresh_icons"):
            toolbar_manager.refresh_icons()

        user_space_widget = getattr(mw, "user_space_widget", None)
        if user_space_widget is not None:
            user_space_widget.refresh_tree()

        dock_manager = getattr(mw, "dock_manager", None)
        console_widget = getattr(dock_manager, "console_widget", None) if dock_manager else None
        if console_widget is not None:
            console_widget.apply_theme(self.mode)

        for widget in getattr(mw, "_script_tabs", {}).values():
            if hasattr(widget, "apply_theme"):
                widget.apply_theme(self.mode)

        for doc in getattr(mw, "_diagrams", []):
            scene = doc.scene
            scene.setBackgroundBrush(UIConfig.BACKGROUND_COLOR)
            scene.update()
