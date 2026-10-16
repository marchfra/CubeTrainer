"""The Timer tab: cstimer-like layout for full solves.

Solves list on the left; scramble bar and big timer on the right.
"""

import time
from collections.abc import Callable

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cubetrainer.cube.scramble import random_state_scramble
from cubetrainer.formatting import format_solve
from cubetrainer.settings import MemorySettings, Settings, get_flag, set_flag
from cubetrainer.solves import Penalty, Solve, SolveList
from cubetrainer.sound import InspectionAudio
from cubetrainer.ui.case_images import CaseInfo
from cubetrainer.ui.scramble_bar import ScrambleBar
from cubetrainer.ui.solve_dialog import SolveDialog
from cubetrainer.ui.solves_panel import TIMER_LAYOUT, PanelLayout, SolvesPanel
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
    """Full-solve timer page; also the base of the trainer page.

    Attributes:
        solves: The solves done in this session.
        solves_panel: Summary and table of solves.
        scramble_bar: Shows the scramble to apply before the solve.
        timer: The spacebar-driven timer.
        right_column: Layout holding the header, the scramble bar and the timer.
        header: Top row of the right column; ends with the Options button.
        columns: The page's main layout: solves panel, then the right column.
        settings: Where the options are kept.
        options_button: Opens ``options_menu``.
        options_menu: The inspection options.
        inspection_action: Turns inspection on or off.
        hold_action: Makes inspection start with a hold until green, like a solve.
        audio_action: Turns the 8 s / 12 s beeps on or off.
        play_warning: Plays an inspection warning; replaceable in tests.
        shortcuts: The keyboard shortcuts, keyed by key sequence string.
        confirm: Asks a yes/no question; replaceable in tests.
        run_dialog: Runs a dialog and returns its result; replaceable in tests.
        PANEL_LAYOUT: Statistics and columns of the solves panel.
        SETTINGS_PREFIX: Start of this page's setting names.
        INSPECTION_DEFAULT: Whether inspection is on until the user changes it.

    """

    PANEL_LAYOUT: PanelLayout = TIMER_LAYOUT
    SETTINGS_PREFIX: str = "timer"
    INSPECTION_DEFAULT: bool = True

    def __init__(
        self,
        solves: SolveList | None = None,
        generate: Callable[[], str] | None = None,
        clock: Callable[[], int] = time.perf_counter_ns,
        settings: Settings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create the page.

        Args:
            solves: The session's solves; an empty, unsaved list if omitted.
            generate: Scramble generator; defaults to random-state full-cube scrambles.
            clock: Monotonic clock in nanoseconds, passed to the timer.
            settings: Where the options are kept; in memory if omitted.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.settings: Settings = settings if settings is not None else MemorySettings()
        self.solves: SolveList = solves if solves is not None else SolveList()
        self.confirm: Callable[[str], bool] = lambda q: ask_confirmation(self, q)
        self.run_dialog: Callable[[QDialog], int] = lambda d: d.exec()
        self._solve_scramble: str = ""

        self.solves_panel: SolvesPanel = SolvesPanel(
            self.solves,
            self.PANEL_LAYOUT,
            # A bound method is looked up per call, so subclasses' attributes exist.
            self.case_name,
        )
        self.solves_panel.setFixedWidth(_SOLVES_PANEL_WIDTH)
        self.solves_panel.solve_activated.connect(self.show_solve)
        self.scramble_bar: ScrambleBar = ScrambleBar(
            generate or default_scramble_generator(),
        )
        self.timer: TimerWidget = TimerWidget(clock=clock)
        self.timer.solve_started.connect(self._on_solve_started)
        self.timer.solve_finished.connect(self._on_solve_finished)

        self.header: QHBoxLayout = QHBoxLayout()
        self.header.addStretch()
        self.header.addWidget(self._build_options())
        self.right_column: QVBoxLayout = QVBoxLayout()
        self.right_column.addLayout(self.header)
        self.right_column.addWidget(self.scramble_bar)
        self.right_column.addWidget(self.timer, stretch=1)
        self.columns: QHBoxLayout = QHBoxLayout(self)
        self.columns.addWidget(self.solves_panel)
        self.columns.addLayout(self.right_column, stretch=1)

        self.shortcuts: dict[str, QShortcut] = {}
        for penalty, keys in PENALTY_SHORTCUTS.items():
            self._add_shortcut(keys, lambda p=penalty: self.set_last_penalty(p))
        self._add_shortcut(DELETE_LAST_SHORTCUT, self.delete_last)

    def _build_options(self) -> QPushButton:
        """Create the Options button and its menu, set from the saved settings.

        Returns:
            The button.

        """
        audio = InspectionAudio()
        self.play_warning: Callable[[int], None] = audio.play
        self.timer.inspection_warning.connect(self._on_inspection_warning)

        self.options_menu: QMenu = QMenu(self)
        self.inspection_action: QAction = self.options_menu.addAction(
            "Inspection (15 s)",
        )
        self.inspection_action.setCheckable(True)
        self.inspection_action.setChecked(
            get_flag(
                self.settings,
                self._key("inspection"),
                default=self.INSPECTION_DEFAULT,
            ),
        )
        self.hold_action: QAction = self.options_menu.addAction(
            "Hold space to start inspection",
        )
        self.hold_action.setCheckable(True)
        self.hold_action.setChecked(
            get_flag(self.settings, self._key("inspection_hold"), default=False),
        )
        self.audio_action: QAction = self.options_menu.addAction(
            "Beep at 8 s and 12 s of inspection",
        )
        self.audio_action.setCheckable(True)
        self.audio_action.setChecked(
            get_flag(self.settings, self._key("inspection_audio"), default=True),
        )
        for action in (self.inspection_action, self.hold_action, self.audio_action):
            action.toggled.connect(self._on_options_changed)
        self._on_options_changed()

        # A plain button popping up the menu, aligned with the other buttons (see
        # the Learn tab's set picker).
        self.options_button: QPushButton = QPushButton("Options  ▾")
        self.options_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.options_button.clicked.connect(
            lambda: self.options_menu.popup(
                self.options_button.mapToGlobal(
                    self.options_button.rect().bottomLeft(),
                ),
            ),
        )
        return self.options_button

    def _key(self, name: str) -> str:
        """Return the full name of one of this page's settings.

        Args:
            name: The short name, e.g. ``"inspection"``.

        Returns:
            e.g. ``"timer.inspection"``.

        """
        return f"{self.SETTINGS_PREFIX}.{name}"

    def _on_options_changed(self) -> None:
        """Apply and save the options; the other two only make sense with inspection."""
        inspection = self.inspection_action.isChecked()
        hold = self.hold_action.isChecked()
        self.timer.set_inspection(enabled=inspection, hold=hold)
        self.hold_action.setEnabled(inspection)
        self.audio_action.setEnabled(inspection)
        set_flag(self.settings, self._key("inspection"), value=inspection)
        set_flag(self.settings, self._key("inspection_hold"), value=hold)
        set_flag(
            self.settings,
            self._key("inspection_audio"),
            value=self.audio_action.isChecked(),
        )

    def _on_inspection_warning(self, warning_ms: int) -> None:
        """Beep for an 8 s or 12 s warning, if beeps are on.

        Args:
            warning_ms: The warning (8000 or 12000).

        """
        if self.audio_action.isChecked():
            self.play_warning(warning_ms)

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
            self.refresh_solves()

    def delete_last(self) -> None:
        """Delete the most recent solve, after asking for confirmation."""
        if not self.solves:
            return
        last = format_solve(self.solves.solves[-1])
        if self.confirm(f"Delete the last solve ({last})?"):
            self.solves.delete(-1)
            self.refresh_solves()

    def show_solve(self, index: int) -> None:
        """Open the details dialog of a solve and apply what the user did there.

        Args:
            index: Position of the solve in the list (0 is the oldest).

        """
        solve = self.solves.solves[index]
        case = self.case_info(solve.case_id) if solve.case_id else None
        dialog = SolveDialog(solve, index + 1, case=case, parent=self)
        if self.run_dialog(dialog) == SolveDialog.DELETED:
            self.solves.delete(index)
        else:
            # The dialog edits the solve in place; go through the list so it's saved.
            self.solves.set_penalty(index, solve.penalty)
            self.solves.set_mistake(index, mistake=solve.mistake)
        self.refresh_solves()

    def refresh_solves(self) -> None:
        """Redraw everything showing the solves (subclasses add their own views)."""
        self.solves_panel.refresh()

    def case_name(self, case_id: str) -> str:
        """Return the display name of a case (subclasses with cases override this).

        Args:
            case_id: The case id.

        Returns:
            The name to show.

        """
        return case_id

    def case_info(self, case_id: str) -> CaseInfo | None:  # noqa: ARG002
        """Return what the solve dialog shows about a case (trainers override this).

        Args:
            case_id: The case id.

        Returns:
            None: full solves have no case.

        """
        return None

    def make_solve(self, time_ms: int, scramble: str, penalty: Penalty) -> Solve:
        """Build the record of a finished solve (subclasses add details).

        Args:
            time_ms: The solve time in milliseconds.
            scramble: The scramble shown when the solve started.
            penalty: The inspection penalty (OK without inspection).

        Returns:
            The new solve.

        """
        return Solve(time_ms=time_ms, scramble=scramble, penalty=penalty)

    def _on_solve_started(self) -> None:
        """Remember the scramble shown when the solve started."""
        self._solve_scramble = self.scramble_bar.scramble

    def _on_solve_finished(self, time_ms: int, penalty: str) -> None:
        """Record the solve and move on to a new scramble.

        Args:
            time_ms: The solve time in milliseconds.
            penalty: The value of its inspection ``Penalty``.

        """
        self.solves.add(
            self.make_solve(time_ms, self._solve_scramble, Penalty(penalty)),
        )
        self.refresh_solves()
        self.scramble_bar.show_new()
