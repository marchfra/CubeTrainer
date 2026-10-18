"""Tests for the theme: fonts, palette, style sheet and light/dark switching."""

import pytest
from PySide6.QtGui import QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication, QPushButton
from pytestqt.qtbot import QtBot

from cubetrainer.solves import Solve
from cubetrainer.ui.solve_dialog import SolveDialog
from cubetrainer.ui.theme import (
    CALM,
    Colors,
    apply_theme,
    load_fonts,
    mono_font,
    palette_for,
    style_sheet,
)


@pytest.fixture
def restore_app(qapp: QApplication) -> object:
    """Put the app's look back as it was after a test that themes it.

    Args:
        qapp: The application.

    Yields:
        Nothing.

    """
    palette, font, sheet = qapp.palette(), qapp.font(), qapp.styleSheet()
    yield
    qapp.setStyleSheet(sheet)
    qapp.setPalette(palette)
    qapp.setFont(font)


def test_bundled_fonts_load(qapp: QApplication) -> None:
    """Geist and Geist Mono ship with the app and register with Qt."""
    del qapp
    families = load_fonts()

    assert {CALM.ui_font, CALM.mono_font} <= set(families)
    assert CALM.mono_font in QFontDatabase.families()
    assert mono_font(20).family() == CALM.mono_font


@pytest.mark.parametrize("colors", [CALM.light, CALM.dark], ids=["light", "dark"])
def test_palette_and_sheet_use_the_theme_colours(colors: Colors) -> None:
    """The palette and the style sheet are built from the theme's colours."""
    palette = palette_for(colors)
    sheet = style_sheet(colors)

    assert palette.color(QPalette.ColorRole.Window).name() == colors.background
    assert palette.color(QPalette.ColorRole.Accent).name() == colors.accent
    for value in (colors.surface, colors.border, colors.accent, colors.danger):
        assert value in sheet
    assert "#mistakeButton:checked" in sheet


@pytest.mark.usefixtures("restore_app")
@pytest.mark.parametrize("dark", [False, True], ids=["light", "dark"])
def test_apply_theme_sets_the_mode(qapp: QApplication, *, dark: bool) -> None:
    """Applying the theme in a mode sets that mode's colours and the UI font."""
    apply_theme(qapp, CALM, dark=dark)
    colors = CALM.dark if dark else CALM.light

    assert qapp.palette().color(QPalette.ColorRole.Window).name() == colors.background
    assert qapp.font().family() == CALM.ui_font
    assert colors.surface in qapp.styleSheet()


@pytest.mark.usefixtures("restore_app")
def test_mistake_button_is_the_same_size_checked_or_not(
    qapp: QApplication,
    qtbot: QtBot,
) -> None:
    """The themed button keeps its size when checked (no squeezing, no jumping)."""
    apply_theme(qapp, CALM, dark=False)
    button = QPushButton("Mistake")
    button.setObjectName("mistakeButton")
    button.setCheckable(True)
    qtbot.addWidget(button)
    unchecked = button.sizeHint()

    checked = QPushButton("Mistake")
    checked.setObjectName("mistakeButton")
    checked.setCheckable(True)
    checked.setChecked(True)  # laid out checked from the start
    qtbot.addWidget(checked)

    assert checked.sizeHint() == unchecked


def test_delete_is_red_and_not_the_default(qtbot: QtBot) -> None:
    """Return closes the solve dialog; Delete is styled as dangerous."""
    dialog = SolveDialog(Solve(2_000, ""), 1)
    qtbot.addWidget(dialog)

    assert dialog.delete_button.objectName() == "dangerButton"
    assert not dialog.delete_button.isDefault()
    assert "#dangerButton" in style_sheet(CALM.light)
