"""The Settings window: the app's theme, and light, dark or the system's mode."""

from typing import override

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from cubetrainer.settings import Settings
from cubetrainer.ui import theme
from cubetrainer.ui.shortcuts import Shortcut
from cubetrainer.ui.theme import THEMES, Appearance, Theme

#: Shortcuts that work anywhere in the app, for the shortcuts list.
APP_KEYS: tuple[Shortcut, ...] = (
    Shortcut("Ctrl+,", "Settings: theme, light or dark mode"),
)

#: Labels of the light/dark choices.
_APPEARANCE_LABELS: dict[Appearance, str] = {
    Appearance.SYSTEM: "Same as the system",
    Appearance.LIGHT: "Light",
    Appearance.DARK: "Dark",
}


class Swatches(QWidget):
    """Three small rounded squares previewing a theme: background, panel, accent.

    Attributes:
        colors: The colours shown, left to right.

    """

    def __init__(self, preview: Theme, parent: QWidget | None = None) -> None:
        """Create the preview (in the current mode's colours).

        Args:
            preview: The theme to preview.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self._theme: Theme = preview
        self.colors: list[str] = []
        self.setFixedSize(3 * 18 + 2 * 4, 18)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the squares in the theme's colours for the current mode.

        Args:
            event: The paint event (unused).

        """
        del event
        colors = theme.current_colors(self._theme)
        self.colors = [colors.background, colors.surface, colors.accent]
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            for i, color in enumerate(self.colors):
                painter.setPen(QColor(colors.border))
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(QRectF(i * 22 + 0.5, 0.5, 17, 17), 5, 5)
        finally:
            painter.end()


class SettingsDialog(QDialog):
    """Chooses the theme and light/dark mode; changes show at once and are saved.

    Attributes:
        theme_buttons: A radio button per theme, by theme name.
        appearance_buttons: A radio button per light/dark choice.

    """

    def __init__(
        self,
        settings: Settings,
        app: QApplication,
        parent: QWidget | None = None,
    ) -> None:
        """Create the window, showing the current choices.

        Args:
            settings: Where the choices are saved.
            app: The application (to restyle).
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._settings: Settings = settings
        self._app: QApplication = app
        current, appearance = theme.CURRENT, theme.APPEARANCE

        themes_box = QGroupBox("Theme")
        grid = QGridLayout(themes_box)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)
        self.theme_buttons: dict[str, QRadioButton] = {}
        theme_group = QButtonGroup(self)
        for row, choice in enumerate(THEMES.values()):
            button = QRadioButton(choice.name)
            button.setChecked(choice is current)
            theme_group.addButton(button)
            self.theme_buttons[choice.name] = button
            description = QLabel(choice.description)
            description.setObjectName("muted")
            grid.addWidget(button, row, 0)
            grid.addWidget(Swatches(choice), row, 1)
            grid.addWidget(description, row, 2)
        grid.setColumnStretch(2, 1)

        mode_box = QGroupBox("Appearance")
        modes = QHBoxLayout(mode_box)
        self.appearance_buttons: dict[Appearance, QRadioButton] = {}
        mode_group = QButtonGroup(self)
        for choice, label in _APPEARANCE_LABELS.items():
            button = QRadioButton(label)
            button.setChecked(choice is appearance)
            mode_group.addButton(button)
            modes.addWidget(button)
            self.appearance_buttons[choice] = button
        modes.addStretch()

        for button in (*self.theme_buttons.values(), *self.appearance_buttons.values()):
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.toggled.connect(self._changed)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(themes_box)
        layout.addWidget(mode_box)
        layout.addWidget(buttons)

    def chosen(self) -> tuple[Theme, Appearance]:
        """Return the theme and light/dark choice the window shows.

        Returns:
            The checked theme and appearance.

        """
        name = next(n for n, b in self.theme_buttons.items() if b.isChecked())
        mode = next(a for a, b in self.appearance_buttons.items() if b.isChecked())
        return THEMES[name], mode

    def _changed(self, checked: bool) -> None:  # noqa: FBT001 - Qt passes it
        """Apply and save the choice (once per change: only the checked button).

        Args:
            checked: Whether the button that changed is now checked.

        """
        if not checked:
            return
        chosen_theme, appearance = self.chosen()
        theme.use_theme(self._app, chosen_theme, appearance)
        theme.save_choice(self._settings, chosen_theme, appearance)
        for swatch in self.findChildren(Swatches):
            swatch.update()  # the mode may have changed
