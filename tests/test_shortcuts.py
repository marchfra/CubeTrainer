"""Tests for the keyboard shortcuts list."""

from typing import TYPE_CHECKING

import pytest
from PySide6.QtWidgets import QDialog
from pytestqt.qtbot import QtBot

from cubetrainer.cases.catalog import load_case_set
from cubetrainer.ui.icon_buttons import CogButton, KeyboardButton
from cubetrainer.ui.shortcuts import (
    Shortcut,
    ShortcutsDialog,
    key_label,
)
from cubetrainer.ui.timer_page import TimerPage
from cubetrainer.ui.timer_widget import TIMER_KEYS
from cubetrainer.ui.trainer_page import TrainerPage

if TYPE_CHECKING:
    from PySide6.QtGui import QColor


@pytest.mark.parametrize(
    ("keys", "label"),
    [("Esc", "Esc"), ("M", "M"), ("Any key", "Any key")],
)
def test_key_labels(keys: str, label: str) -> None:
    """Esc is spelled out; text that isn't a key sequence is kept as it is."""
    assert key_label(keys) == label


def test_dialog_lists_sections_in_order(qtbot: QtBot) -> None:
    """Each section lists its keys and actions."""
    dialog = ShortcutsDialog(
        [("First", [Shortcut("Esc", "Leave")]), ("Second", [Shortcut("M", "Mark")])],
    )
    qtbot.addWidget(dialog)

    assert dialog.rows == {"First": [("Esc", "Leave")], "Second": [("M", "Mark")]}


def shown_dialog(page: TimerPage) -> ShortcutsDialog:
    """Click the page's shortcuts button and return the dialog it opens.

    Args:
        page: The page.

    Returns:
        The dialog.

    """
    shown: list[ShortcutsDialog] = []

    def run_dialog(dialog: QDialog) -> int:
        assert isinstance(dialog, ShortcutsDialog)
        shown.append(dialog)
        return 0

    page.run_dialog = run_dialog
    page.timer.shortcuts_button.click()
    (dialog,) = shown
    return dialog


@pytest.mark.parametrize("trainer", [False, True], ids=["timer", "trainer"])
def test_link_lists_every_registered_shortcut(qtbot: QtBot, *, trainer: bool) -> None:
    """The list shows the timer's keys and exactly the shortcuts the page has."""
    page = TrainerPage(load_case_set("pll")) if trainer else TimerPage()
    qtbot.addWidget(page)

    dialog = shown_dialog(page)

    assert list(dialog.rows) == ["Timer", page.title.text()]
    assert [key for key, _ in dialog.rows["Timer"]] == [
        key_label(s.keys) for s in TIMER_KEYS
    ]
    listed = [key for key, _ in dialog.rows[page.title.text()]]
    assert listed == [key_label(keys) for keys in page.shortcuts]
    assert (key_label("Right") in listed) == trainer
    assert (key_label("M") in listed) == trainer


def test_button_sits_in_the_timer_corner(qtbot: QtBot) -> None:
    """Cog and keyboard sit in the timer's bottom-right corner, whatever its size."""
    page = TimerPage()
    qtbot.addWidget(page)
    page.resize(1100, 700)
    page.show()
    qtbot.waitExposed(page)

    for width in (1100, 1300):
        page.resize(width, 700)
        qtbot.wait(10)
        shortcuts = page.timer.shortcuts_button
        assert shortcuts.geometry().bottomRight() == page.timer.rect().bottomRight()
        cog = page.timer.options_button
        assert cog.geometry().right() + 1 == shortcuts.geometry().left()
        assert cog.geometry().bottom() == shortcuts.geometry().bottom()


@pytest.mark.parametrize("kind", [KeyboardButton, CogButton])
def test_icon_buttons_light_up_on_hover(
    qtbot: QtBot,
    kind: type[KeyboardButton | CogButton],
) -> None:
    """The icon is faint at rest, the accent colour on hover, darker when pressed."""
    button = kind()
    qtbot.addWidget(button)
    accent = button.palette().accent().color()

    rest = button.ink(hovered=False, pressed=False)
    assert rest.alphaF() < 1
    assert button.ink(hovered=True, pressed=False) == accent
    assert button.ink(hovered=True, pressed=True) == accent.darker(130)
    assert not button.grab().isNull()  # paints without errors


def test_cog_opens_the_options_menu_above_it(qtbot: QtBot) -> None:
    """Clicking the cog pops the options menu up, ending at the cog's top."""
    page = TimerPage()
    qtbot.addWidget(page)
    page.show()
    qtbot.waitExposed(page)

    page.options_button.click()
    qtbot.waitUntil(page.options_menu.isVisible)

    cog_top = page.options_button.mapToGlobal(page.options_button.rect().topLeft())
    assert page.options_menu.geometry().bottom() < cog_top.y() + 1
    page.options_menu.hide()


def test_highlight_clears_when_the_pointer_leaves_unseen(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a click opens a menu, the button turns grey again by itself.

    The menu takes the mouse, so no "leave" event arrives; the button re-checks
    the pointer while it's highlighted.
    """
    button = CogButton()
    qtbot.addWidget(button)
    button.show()
    qtbot.waitExposed(button)
    drawn: list[QColor] = []
    monkeypatch.setattr(
        button,
        "draw_icon",
        lambda _painter, color: drawn.append(color),
    )
    accent = button.palette().accent().color()

    monkeypatch.setattr(button, "pointer_inside", lambda: True)
    button.update()
    qtbot.waitUntil(lambda: bool(drawn) and drawn[-1] == accent)

    monkeypatch.setattr(button, "pointer_inside", lambda: False)  # no event, no update
    qtbot.waitUntil(lambda: drawn[-1] != accent, timeout=1000)
