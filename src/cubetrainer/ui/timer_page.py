"""The Timer tab: cstimer-like layout for full solves.

Solves list on the left; scramble bar and big timer on the right.
"""

import time
from collections.abc import Callable

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QDialog, QHBoxLayout, QMessageBox, QVBoxLayout, QWidget

from cubetrainer.cube.scramble import random_state_scramble
from cubetrainer.formatting import format_solve
from cubetrainer.solves import Penalty, Solve, SolveList
from cubetrainer.ui.scramble_bar import ScrambleBar
from cubetrainer.ui.solve_dialog import SolveDialog
from cubetrainer.ui.solves_panel import SolvesPanel
from cubetrainer.ui.timer_widget import TimerWidget

#: Keyboard shortcut for each penalty on the last solve. "Ctrl" is Cmd on macOS.
PENALTY_SHORTCUTS: dict[Penalty, str] = {
    Penalty.OK: "Ctrl+1",
    Penalty.PLUS_TWO: "Ctrl+2",
    Penalty.DNF: "Ctrl+3",
}

#: Shortcut deleting the last solve. "Ctrl" is Cmd on macOS.
DELETE_LAST_SHORTCUT: str = "Ctrl+Z"

_SOLVES_PANEL_WIDTH: int = 320


def default_scramble_generator() -> Callable[[], str]:
    """Build a generator of full-cube random-state scrambles.

    Returns:
        A function returning a new scramble each time it's called.

    """
    rng = np.random.default_rng()
    return lambda: random_state_scramble(rng)


def ask_confirmation(parent: QWidget, question: str) -> bool:
    """Ask a yes/no question in a message box.

    Args:
        parent: Parent widget of the message box.
        question: The question text.

    Returns:
        True if the user answered yes.

    """
    answer = QMessageBox.question(parent, "Confirm", question)
    return answer == QMessageBox.StandardButton.Yes


class TimerPage(QWidget):
    """Full-solve timer page.

    Attributes:
        solves: The solves done in this session.
        solves_panel: Summary and table of solves.
        scramble_bar: Shows the scramble to apply before the solve.
        timer: The spacebar-driven timer.
        shortcuts: The keyboard shortcuts, keyed by key sequence string.
        confirm: Asks a yes/no question; replaceable in tests.
        run_dialog: Runs a dialog and returns its result; replaceable in tests.

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
        self.solves: SolveList = SolveList()
        self.confirm: Callable[[str], bool] = lambda q: ask_confirmation(self, q)
        self.run_dialog: Callable[[QDialog], int] = lambda d: d.exec()
        self._solve_scramble: str = ""

        self.solves_panel: SolvesPanel = SolvesPanel(self.solves)
        self.solves_panel.setFixedWidth(_SOLVES_PANEL_WIDTH)
        self.solves_panel.solve_activated.connect(self.show_solve)
        self.scramble_bar: ScrambleBar = ScrambleBar(
            generate or default_scramble_generator(),
        )
        self.timer: TimerWidget = TimerWidget(clock=clock)
        self.timer.solve_started.connect(self._on_solve_started)
        self.timer.solve_finished.connect(self._on_solve_finished)

        right = QVBoxLayout()
        right.addWidget(self.scramble_bar)
        right.addWidget(self.timer, stretch=1)
        layout = QHBoxLayout(self)
        layout.addWidget(self.solves_panel)
        layout.addLayout(right, stretch=1)

        self.shortcuts: dict[str, QShortcut] = {}
        for penalty, keys in PENALTY_SHORTCUTS.items():
            self._add_shortcut(keys, lambda p=penalty: self.set_last_penalty(p))
        self._add_shortcut(DELETE_LAST_SHORTCUT, self.delete_last)

    def _add_shortcut(self, keys: str, handler: Callable[[], None]) -> None:
        """Register a window-wide shortcut that only works while this page is shown.

        Args:
            keys: Key sequence in portable text form, e.g. ``"Ctrl+1"``.
            handler: Function called when the shortcut fires.

        """
        shortcut = QShortcut(QKeySequence(keys), self)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(handler)
        self.shortcuts[keys] = shortcut

    def set_last_penalty(self, penalty: Penalty) -> None:
        """Set the penalty of the most recent solve (no-op without solves).

        Args:
            penalty: The new penalty.

        """
        if self.solves:
            self.solves.set_penalty(-1, penalty)
            self.solves_panel.refresh()

    def delete_last(self) -> None:
        """Delete the most recent solve, after asking for confirmation."""
        if not self.solves:
            return
        last = format_solve(self.solves.solves[-1])
        if self.confirm(f"Delete the last solve ({last})?"):
            self.solves.delete(-1)
            self.solves_panel.refresh()

    def show_solve(self, index: int) -> None:
        """Open the details dialog of a solve and apply what the user did there.

        Args:
            index: Position of the solve in the list (0 is the oldest).

        """
        dialog = SolveDialog(self.solves.solves[index], index + 1, self)
        if self.run_dialog(dialog) == SolveDialog.DELETED:
            self.solves.delete(index)
        self.solves_panel.refresh()

    def _on_solve_started(self) -> None:
        """Remember the scramble shown when the solve started."""
        self._solve_scramble = self.scramble_bar.scramble

    def _on_solve_finished(self, time_ms: int) -> None:
        """Record the solve and move on to a new scramble.

        Args:
            time_ms: The solve time in milliseconds.

        """
        self.solves.add(Solve(time_ms=time_ms, scramble=self._solve_scramble))
        self.solves_panel.refresh()
        self.scramble_bar.show_new()
