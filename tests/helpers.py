"""Helpers shared by the UI tests."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from cubetrainer.ui.timer_widget import TimerWidget

MS = 1_000_000  # nanoseconds per millisecond


class FakeClock:
    """Manually advanced monotonic clock.

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

    def advance_ms(self, ms: int) -> None:
        """Move the clock forward.

        Args:
            ms: Milliseconds to advance.

        """
        self.now_ns += ms * MS


def do_solve(qtbot: QtBot, target: QWidget, clock: FakeClock, solve_ms: int) -> None:
    """Perform a complete hold / start / stop cycle with the space bar.

    If the timer has inspection on, a first press begins inspection, and the solve
    starts right away (so without a penalty).

    Args:
        qtbot: pytest-qt helper.
        target: The timer widget, or a page with a ``timer`` (the timer captures key
            events app-wide, so they're simply sent to ``target``).
        clock: The fake clock driving the timer.
        solve_ms: How long the simulated solve lasts.

    """
    timer = getattr(target, "timer", target)
    if isinstance(timer, TimerWidget) and timer.machine.inspection:
        qtbot.keyPress(target, Qt.Key.Key_Space)
        qtbot.keyRelease(target, Qt.Key.Key_Space)
    qtbot.keyPress(target, Qt.Key.Key_Space)
    clock.advance_ms(300)
    qtbot.keyRelease(target, Qt.Key.Key_Space)
    clock.advance_ms(solve_ms)
    qtbot.keyPress(target, Qt.Key.Key_Space)
    qtbot.keyRelease(target, Qt.Key.Key_Space)
