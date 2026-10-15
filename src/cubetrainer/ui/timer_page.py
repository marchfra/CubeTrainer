"""The Timer tab: scramble bar on top of the big timer, for full solves."""

import time
from collections.abc import Callable

import numpy as np
from PySide6.QtWidgets import QVBoxLayout, QWidget

from cubetrainer.cube.scramble import random_state_scramble
from cubetrainer.ui.scramble_bar import ScrambleBar
from cubetrainer.ui.timer_widget import TimerWidget


def default_scramble_generator() -> Callable[[], str]:
    """Build a generator of full-cube random-state scrambles.

    Returns:
        A function returning a new scramble each time it's called.

    """
    rng = np.random.default_rng()
    return lambda: random_state_scramble(rng)


class TimerPage(QWidget):
    """Full-solve timer page.

    Attributes:
        scramble_bar: Shows the scramble to apply before the solve.
        timer: The spacebar-driven timer.

    """

    def __init__(
        self,
        generate: Callable[[], str] | None = None,
        clock: Callable[[], int] = time.perf_counter_ns,
        parent: QWidget | None = None,
    ) -> None:
        """Create the page.

        Args:
            generate: Scramble generator; defaults to random-state full-cube scrambles.
            clock: Monotonic clock in nanoseconds, passed to the timer.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.scramble_bar: ScrambleBar = ScrambleBar(
            generate or default_scramble_generator(),
        )
        self.timer: TimerWidget = TimerWidget(clock=clock)
        self.timer.solve_finished.connect(self._on_solve_finished)

        layout = QVBoxLayout(self)
        layout.addWidget(self.scramble_bar)
        layout.addWidget(self.timer, stretch=1)

    def _on_solve_finished(self, _time_ms: int) -> None:
        """Show a new scramble once a solve is done.

        Args:
            _time_ms: The solve time (unused until solves are recorded).

        """
        self.scramble_bar.show_new()
