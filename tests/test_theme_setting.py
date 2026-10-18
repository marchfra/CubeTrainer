"""Tests for choosing the theme and light/dark mode."""

from collections.abc import Iterator

import pytest
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QRadioButton
from pytestqt.qtbot import QtBot

from cubetrainer.db import Database
from cubetrainer.settings import MemorySettings
from cubetrainer.timing import TimerState
from cubetrainer.ui import chart_style, theme
from cubetrainer.ui.main_window import MainWindow
from cubetrainer.ui.settings_dialog import SettingsDialog
from cubetrainer.ui.theme import (
    BOLD,
    CALM,
    CLEAN,
    Appearance,
    FontRole,
    save_choice,
    saved_choice,
    set_theme_font,
    use_theme,
)
from cubetrainer.ui.timer_widget import CARD_TEXT, STATE_COLORS, TimerWidget


@pytest.fixture(autouse=True)
def back_to_calm(qapp: QApplication) -> Iterator[None]:
    """Put the app back to Calm, the system's mode and its old look after a test.

    Args:
        qapp: The application.

    Yields:
        Nothing.

    """
    palette, font, sheet = qapp.palette(), qapp.font(), qapp.styleSheet()
    yield
    use_theme(qapp, CALM, Appearance.SYSTEM)
    qapp.setStyleSheet(sheet)
    qapp.setPalette(palette)
    qapp.setFont(font)


def test_choice_defaults_to_calm_and_the_system() -> None:
    """Nothing saved (or something unknown) means Calm, following the system."""
    settings = MemorySettings()
    assert saved_choice(settings) == (CALM, Appearance.SYSTEM)

    settings.set_setting(theme.THEME_SETTING, "Neon")
    settings.set_setting(theme.APPEARANCE_SETTING, "sepia")
    assert saved_choice(settings) == (CALM, Appearance.SYSTEM)


def test_choice_is_saved_and_read_back() -> None:
    """The theme and appearance survive being saved."""
    settings = MemorySettings()
    save_choice(settings, BOLD, Appearance.DARK)

    assert saved_choice(settings) == (BOLD, Appearance.DARK)


@pytest.mark.parametrize("appearance", [Appearance.LIGHT, Appearance.DARK])
def test_forcing_light_or_dark(qapp: QApplication, appearance: Appearance) -> None:
    """Light or dark can be forced, whatever the system's mode."""
    use_theme(qapp, CLEAN, appearance)

    assert theme.CURRENT is CLEAN
    assert theme.is_dark() == (appearance is Appearance.DARK)
    expected = CLEAN.dark if appearance is Appearance.DARK else CLEAN.light
    assert (
        expected.background in qapp.styleSheet() or theme.current_colors() == expected
    )


def test_switching_theme_updates_registered_fonts(
    qapp: QApplication,
    qtbot: QtBot,
) -> None:
    """Widgets with a font role get the new theme's family; flat rules apply."""
    label = QLabel("R U R' U'")
    qtbot.addWidget(label)
    use_theme(qapp, CALM, Appearance.LIGHT)
    set_theme_font(label, FontRole.MONO, 16)
    assert label.font().family() == CALM.mono_font

    use_theme(qapp, BOLD, Appearance.LIGHT)
    assert label.font().family() == BOLD.mono_font
    assert label.font().pointSizeF() == 16

    use_theme(qapp, CLEAN, Appearance.LIGHT)
    assert label.font().family() == CLEAN.mono_font
    assert "border-top: 1px solid" in qapp.styleSheet()  # flat panels


def test_chart_colours_follow_the_theme(qapp: QApplication) -> None:
    """Charts use each theme's own palette, light or dark."""
    use_theme(qapp, BOLD, Appearance.DARK)
    assert chart_style.current_colors() is chart_style.CHART_COLORS["Bold"][1]

    use_theme(qapp, CALM, Appearance.LIGHT)
    assert chart_style.current_colors() is chart_style.LIGHT


def test_timer_card_shows_hold_and_ready(qapp: QApplication, qtbot: QtBot) -> None:
    """On Bold the timer card turns red while held and green when ready."""
    use_theme(qapp, BOLD, Appearance.LIGHT)
    timer = TimerWidget()
    qtbot.addWidget(timer)
    colors = BOLD.light

    timer._paint_state(TimerState.IDLE)
    assert timer._card_color == colors.timer_card
    timer._paint_state(TimerState.HOLDING)
    assert timer._card_color == colors.danger
    timer._paint_state(TimerState.READY)
    assert timer._card_color == colors.success
    assert timer.display.color == CARD_TEXT

    use_theme(qapp, CALM, Appearance.LIGHT)  # no card: the time changes colour
    timer._paint_state(TimerState.HOLDING)
    assert timer.display.color == STATE_COLORS[TimerState.HOLDING]


def test_settings_window_applies_and_saves(qapp: QApplication, qtbot: QtBot) -> None:
    """Choosing in the Settings window restyles the app at once and saves."""
    settings = MemorySettings()
    use_theme(qapp, CALM, Appearance.SYSTEM)
    dialog = SettingsDialog(settings, qapp)
    qtbot.addWidget(dialog)
    assert dialog.theme_buttons["Calm"].isChecked()

    dialog.theme_buttons["Bold"].setChecked(True)
    dialog.appearance_buttons[Appearance.DARK].setChecked(True)

    assert theme.CURRENT is BOLD
    assert theme.is_dark()
    assert saved_choice(settings) == (BOLD, Appearance.DARK)


def test_command_comma_opens_settings(qtbot: QtBot) -> None:
    """The Settings action uses the platform's preferences shortcut (⌘,)."""
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    shown: list[QDialog] = []

    def run_dialog(dialog: QDialog) -> int:
        shown.append(dialog)
        return 0

    window.run_dialog = run_dialog
    window.settings_action.trigger()

    assert window.settings_action.shortcut() == QKeySequence(
        QKeySequence.StandardKey.Preferences,
    )
    assert isinstance(shown[0], SettingsDialog)


def test_timer_keeps_its_theme_font_after_a_solve(
    qapp: QApplication,
    qtbot: QtBot,
) -> None:
    """After switching themes, a state change doesn't bring back the old font."""
    use_theme(qapp, CLEAN, Appearance.LIGHT)
    timer = TimerWidget()
    qtbot.addWidget(timer)
    timer.show()
    qtbot.waitExposed(timer)
    use_theme(qapp, BOLD, Appearance.LIGHT)
    qtbot.wait(10)
    use_theme(qapp, CLEAN, Appearance.LIGHT)
    qtbot.wait(10)
    family = timer.display.font().family()

    for state in (TimerState.HOLDING, TimerState.READY, TimerState.IDLE):
        timer._paint_state(state)
        qtbot.wait(10)
        assert timer.display.font().family() == family != BOLD.ui_font


@pytest.mark.parametrize("chosen", [CALM, CLEAN, BOLD], ids=lambda t: t.name)
def test_radio_buttons_keep_their_size_when_chosen(
    qapp: QApplication,
    qtbot: QtBot,
    chosen: theme.Theme,
) -> None:
    """A radio button is the same size checked or not, so nothing shifts."""
    use_theme(qapp, chosen, Appearance.LIGHT)
    sizes = []
    for checked in (False, True):
        button = QRadioButton("Realistic")
        qtbot.addWidget(button)
        button.setChecked(checked)
        sizes.append(button.sizeHint())

    assert sizes[0] == sizes[1]


def test_icons_on_the_timer_card_hover_in_white(
    qapp: QApplication,
    qtbot: QtBot,
) -> None:
    """On Bold's card the corner icons don't use the accent (the card's colour)."""
    use_theme(qapp, BOLD, Appearance.LIGHT)
    timer = TimerWidget()
    qtbot.addWidget(timer)
    timer.show()
    qtbot.waitExposed(timer)

    hover = timer.options_button.ink(hovered=True, pressed=False)
    assert hover.name() == "#ffffff"
    assert hover.alphaF() == 1.0
    assert timer.options_button.ink(hovered=False, pressed=False).alphaF() < 1

    use_theme(qapp, CALM, Appearance.LIGHT)
    qtbot.waitUntil(
        lambda: (
            timer.options_button.ink(hovered=True, pressed=False).name() != "#ffffff"
        ),
    )


def test_clean_paints_its_toolbar_and_sidebars(
    qapp: QApplication,
    qtbot: QtBot,
) -> None:
    """Clean tints the header row and both side columns of the trainer."""
    use_theme(qapp, CLEAN, Appearance.LIGHT)
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    window.resize(1280, 760)
    window.show()
    window.open_trainer("pll")
    page = window.trainer_pages["pll"]
    qtbot.waitExposed(page)
    image = page.grab().toImage()
    colors = CLEAN.light

    left = page.solves_panel.table.geometry()
    right = page.case_stats.table.geometry()
    assert image.pixelColor(left.left() + 2, left.bottom() + 3).name() == colors.sidebar
    assert (
        image.pixelColor(right.right() + 2, right.bottom() + 3).name() == colors.sidebar
    )
    assert image.pixelColor(page.width() // 2, 2).name() == colors.toolbar
