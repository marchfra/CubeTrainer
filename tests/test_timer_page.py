"""Tests for the Timer tab: scramble bar wiring and buttons."""

from itertools import count

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QPushButton
from pytestqt.qtbot import QtBot

from cubetrainer.ui.scramble_bar import _reserve_width
from cubetrainer.ui.timer_page import TimerPage

MS = 1_000_000  # nanoseconds per millisecond


class FakeClock:
    """Manually advanced clock returning nanoseconds.

    Attributes:
        now_ns: The current time in nanoseconds.

    """

    def __init__(self) -> None:
        """Start the clock at zero."""
        self.now_ns: int = 0

    def __call__(self) -> int:
        """Return the current time.

        Returns:
            The current time in nanoseconds.

        """
        return self.now_ns


@pytest.fixture
def clock() -> FakeClock:
    """Provide a fresh fake clock.

    Returns:
        The clock.

    """
    return FakeClock()


@pytest.fixture
def page(qtbot: QtBot, clock: FakeClock) -> TimerPage:
    """Provide a visible timer page with predictable scrambles "s0", "s1", ...

    Args:
        qtbot: pytest-qt helper.
        clock: The fake clock.

    Returns:
        The page.

    """
    counter = count()
    widget = TimerPage(generate=lambda: f"s{next(counter)}", clock=clock)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_shows_first_scramble_with_back_disabled(page: TimerPage) -> None:
    """The page opens on a scramble and there is nothing to go back to."""
    assert page.scramble_bar.label.text() == "s0"
    assert not page.scramble_bar.prev_button.isEnabled()


def test_buttons_browse_scrambles(qtbot: QtBot, page: TimerPage) -> None:
    """▶ goes forward (generating), ◀ goes back."""
    bar = page.scramble_bar
    qtbot.mouseClick(bar.next_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(bar.next_button, Qt.MouseButton.LeftButton)
    assert bar.label.text() == "s2"
    assert bar.prev_button.isEnabled()

    qtbot.mouseClick(bar.prev_button, Qt.MouseButton.LeftButton)
    assert bar.label.text() == "s1"


def test_copy_puts_scramble_on_clipboard(qtbot: QtBot, page: TimerPage) -> None:
    """Copy places the current scramble on the clipboard and confirms it."""
    qtbot.mouseClick(page.scramble_bar.copy_button, Qt.MouseButton.LeftButton)

    assert QGuiApplication.clipboard().text() == "s0"
    assert page.scramble_bar.copy_button.text() == "Copied ✓"


def test_copy_button_width_is_fixed(page: TimerPage) -> None:
    """The copy button has a fixed width that fits the "Copied ✓" label."""
    button = page.scramble_bar.copy_button

    assert button.minimumWidth() == button.maximumWidth()
    button.setText("Copied ✓")
    assert button.sizeHint().width() <= button.width()


def test_reserve_width_fits_longest_label(qtbot: QtBot) -> None:
    """A button sized for a long label doesn't resize when it shows that label."""
    button = QPushButton("Copy")
    qtbot.addWidget(button)
    long_text = "Copied to the clipboard, all good"

    _reserve_width(button, long_text)
    width = button.width()
    button.setText(long_text)

    assert button.text() == long_text
    assert button.minimumWidth() == button.maximumWidth() == width
    assert button.sizeHint().width() <= width


def test_solve_moves_to_new_scramble(
    qtbot: QtBot,
    page: TimerPage,
    clock: FakeClock,
) -> None:
    """Finishing a solve shows a freshly generated scramble."""
    page.scramble_bar.show_next()
    page.scramble_bar.show_previous()

    qtbot.keyPress(page, Qt.Key.Key_Space)
    clock.now_ns += 300 * MS
    qtbot.keyRelease(page, Qt.Key.Key_Space)
    clock.now_ns += 5_000 * MS
    qtbot.keyPress(page, Qt.Key.Key_Space)

    assert page.scramble_bar.label.text() == "s2"


def test_buttons_do_not_take_focus(page: TimerPage) -> None:
    """Buttons can't be focused, so space never triggers them."""
    bar = page.scramble_bar
    for button in (bar.prev_button, bar.next_button, bar.copy_button):
        assert button.focusPolicy() == Qt.FocusPolicy.NoFocus
