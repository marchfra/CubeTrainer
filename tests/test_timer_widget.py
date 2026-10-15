"""Tests for the timer widget, driven by simulated key events and a fake clock."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QLineEdit, QPushButton, QVBoxLayout, QWidget
from pytestqt.qtbot import QtBot

from cubetrainer.timing import TimerState
from cubetrainer.ui.timer_widget import STATE_COLORS, TimerWidget
from tests.helpers import FakeClock, do_solve


@pytest.fixture
def timer(qtbot: QtBot, clock: FakeClock) -> TimerWidget:
    """Provide a visible timer widget using the fake clock.

    Args:
        qtbot: pytest-qt helper.
        clock: The fake clock.

    Returns:
        The widget.

    """
    widget = TimerWidget(clock=clock)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_hold_shows_red_then_green(
    qtbot: QtBot,
    timer: TimerWidget,
    clock: FakeClock,
) -> None:
    """Holding space colours the display red, then green after the hold delay."""
    qtbot.keyPress(timer, Qt.Key.Key_Space)
    assert timer.machine.state is TimerState.HOLDING
    assert STATE_COLORS[TimerState.HOLDING] in timer.display.styleSheet()

    clock.advance_ms(300)
    timer.refresh()
    assert timer.machine.state is TimerState.READY
    assert STATE_COLORS[TimerState.READY] in timer.display.styleSheet()


def test_full_solve_emits_time_and_shows_it(
    qtbot: QtBot,
    timer: TimerWidget,
    clock: FakeClock,
) -> None:
    """A complete cycle emits the solve time and leaves it on the display."""
    with qtbot.waitSignal(timer.solve_finished) as blocker:
        do_solve(qtbot, timer, clock, 12_345)

    assert blocker.args == [12_345]
    assert timer.machine.state is TimerState.IDLE
    assert timer.display.text() == "12.34"
    assert timer.display.styleSheet() == ""


def test_any_key_stops_running_timer(
    qtbot: QtBot,
    timer: TimerWidget,
    clock: FakeClock,
) -> None:
    """While running, a non-space key stops the timer."""
    qtbot.keyPress(timer, Qt.Key.Key_Space)
    clock.advance_ms(300)
    qtbot.keyRelease(timer, Qt.Key.Key_Space)
    clock.advance_ms(2_000)

    with qtbot.waitSignal(timer.solve_finished) as blocker:
        qtbot.keyPress(timer, Qt.Key.Key_A)

    assert blocker.args == [2_000]


def test_escape_cancels_hold(
    qtbot: QtBot,
    timer: TimerWidget,
    clock: FakeClock,
) -> None:
    """Escape during a hold returns to idle, and the later release doesn't start."""
    qtbot.keyPress(timer, Qt.Key.Key_Space)
    clock.advance_ms(300)
    timer.refresh()

    qtbot.keyPress(timer, Qt.Key.Key_Escape)
    qtbot.keyRelease(timer, Qt.Key.Key_Space)

    assert timer.machine.state is TimerState.IDLE


def test_space_does_not_click_focused_button(
    qtbot: QtBot,
    clock: FakeClock,
) -> None:
    """Space is captured by the timer, so a focused button is not activated."""
    container = QWidget()
    qtbot.addWidget(container)
    layout = QVBoxLayout(container)
    timer = TimerWidget(clock=clock)
    button = QPushButton("click me")
    layout.addWidget(timer)
    layout.addWidget(button)
    container.show()
    button.setFocus()
    clicks: list[bool] = []
    button.clicked.connect(lambda: clicks.append(True))

    qtbot.keyPress(button, Qt.Key.Key_Space)
    qtbot.keyRelease(button, Qt.Key.Key_Space)

    assert clicks == []


def test_text_field_keeps_its_keys(qtbot: QtBot, clock: FakeClock) -> None:
    """When a text field has focus, typing a space goes to the field, not the timer."""
    container = QWidget()
    qtbot.addWidget(container)
    layout = QVBoxLayout(container)
    timer = TimerWidget(clock=clock)
    field = QLineEdit()
    layout.addWidget(timer)
    layout.addWidget(field)
    container.show()
    container.activateWindow()
    field.setFocus()
    qtbot.waitUntil(field.hasFocus)

    qtbot.keyClicks(field, "a b")

    assert field.text() == "a b"
    assert timer.machine.state is TimerState.IDLE


def test_hidden_timer_ignores_space(qtbot: QtBot, clock: FakeClock) -> None:
    """A timer that isn't visible (e.g. another tab is shown) doesn't react."""
    timer = TimerWidget(clock=clock)
    qtbot.addWidget(timer)
    other = QWidget()
    qtbot.addWidget(other)
    other.show()

    qtbot.keyPress(other, Qt.Key.Key_Space)

    assert timer.machine.state is TimerState.IDLE


@pytest.mark.parametrize("key", [Qt.Key.Key_Control, Qt.Key.Key_Meta, Qt.Key.Key_Shift])
def test_modifier_keys_do_not_stop_running_timer(
    qtbot: QtBot,
    timer: TimerWidget,
    clock: FakeClock,
    key: Qt.Key,
) -> None:
    """Pressing a modifier (e.g. Cmd for Cmd+Tab) leaves the solve running."""
    qtbot.keyPress(timer, Qt.Key.Key_Space)
    clock.advance_ms(300)
    qtbot.keyRelease(timer, Qt.Key.Key_Space)

    qtbot.keyPress(timer, key)
    qtbot.keyRelease(timer, key)

    assert timer.machine.state is TimerState.RUNNING


def test_display_digits_have_equal_width(timer: TimerWidget) -> None:
    """All digits have the same advance, so the running time doesn't jitter."""
    metrics = QFontMetrics(timer.display.font())

    widths = {metrics.horizontalAdvance(digit) for digit in "0123456789"}

    assert len(widths) == 1
