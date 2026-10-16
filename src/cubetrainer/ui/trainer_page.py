"""Trainer mode: the timer page drilling the cases of one set."""

import time
from collections.abc import Callable
from typing import override

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap, QShowEvent
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QWidget

from cubetrainer.cases.catalog import Case, CaseSet
from cubetrainer.cases.filters import MemoryTrainerPrefs, TrainerPrefs
from cubetrainer.cases.trainer import (
    CaseRecognizer,
    active_cases,
    filtered_case_scrambles,
)
from cubetrainer.cube.model import parse_alg, reveal_alg
from cubetrainer.sessions import SessionStore
from cubetrainer.solves import Penalty, Solve
from cubetrainer.timing import TimerState
from cubetrainer.ui.case_images import CaseInfo, case_pixmap
from cubetrainer.ui.case_stats_panel import CaseStatsPanel
from cubetrainer.ui.filter_dialog import FilterDialog
from cubetrainer.ui.solves_panel import TRAINER_LAYOUT, PanelLayout
from cubetrainer.ui.timer_page import TimerPage

#: Size of the case image in the solve dialog, in logical pixels.
DIALOG_IMAGE_SIZE: int = 160

#: Size of the case image in the hint panel, in logical pixels.
HINT_IMAGE_SIZE: int = 120

#: Shortcut revealing the next hint step.
HINT_SHORTCUT: str = "Right"

#: Shortcut marking the current (or last) solve as a mistake.
MISTAKE_SHORTCUT: str = "M"

#: Background of the Mistake button while the solve it acts on is flagged.
MISTAKE_COLOR: str = "#e5484d"

#: Width of the per-case statistics table.
CASE_STATS_WIDTH: int = 380

#: Shown in the hint panel before any hint is revealed.
HINT_PROMPT: str = "Press → for a hint"


class HintPanel(QWidget):
    """Shows the case image and the first few moves of its algorithm.

    Attributes:
        image: The case image (empty until the first hint).
        moves: The revealed moves, or a prompt before the first hint.

    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create an empty panel showing the prompt.

        Args:
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.image: QLabel = QLabel()
        self.image.setFixedSize(HINT_IMAGE_SIZE, HINT_IMAGE_SIZE)
        self.moves: QLabel = QLabel()
        font = QFont()
        font.setPointSize(22)
        self.moves.setFont(font)
        self.moves.setWordWrap(True)
        box = QHBoxLayout(self)
        box.addStretch()
        box.addWidget(self.image)
        box.addWidget(self.moves)
        box.addStretch()
        self.clear()

    def clear(self) -> None:
        """Hide the hint, showing only the prompt.

        The (empty) image keeps its space, so the timer below doesn't move when the
        first hint appears.
        """
        self.image.clear()
        self.moves.setText(HINT_PROMPT)

    def show_hint(self, image: QPixmap, alg: str, revealed: int) -> None:
        """Show the case image and the first ``revealed`` moves of its algorithm.

        Brackets in the algorithm are kept but aren't moves: ``"(R U R' U') F"`` with
        one move revealed shows ``"(R"``.

        Args:
            image: The case image.
            alg: The algorithm, as written.
            revealed: How many moves to show.

        """
        self.image.setPixmap(image)
        hidden = len(parse_alg(alg)) - revealed
        more = f"   (+{hidden} more)" if hidden > 0 else ""
        self.moves.setText(reveal_alg(alg, revealed) + more)


class TrainerPage(TimerPage):
    """Timer page whose scrambles set up cases of a set, recording the case of each.

    Attributes:
        back_requested: Emitted when the user asks to return to the full timer.
        case_set: The set being trained.
        prefs: Learning statuses and the case filter.
        title: Header naming the set.
        filter_button: Shows the case filter; clicking it opens the filter dialog.
        back_button: Returns to the full timer.
        hint_panel: Shows the hints for the current scramble.
        hints_shown: How many hint steps have been revealed for the current scramble.
        mistake_button: Marks the current (or last) solve as a mistake, like M.
        case_stats: Per-case statistics table.
        PANEL_LAYOUT: The trainer table, with a case column.
        SETTINGS_PREFIX: Trainer options are shared by every set.
        INSPECTION_DEFAULT: Inspection is off in the trainer until turned on.
        SHOW_GRAPH: No time graph: times of different cases don't make a trend.

    """

    back_requested = Signal()
    PANEL_LAYOUT: PanelLayout = TRAINER_LAYOUT
    SETTINGS_PREFIX: str = "trainer"
    INSPECTION_DEFAULT: bool = False
    SHOW_GRAPH: bool = False

    def __init__(
        self,
        case_set: CaseSet,
        sessions: SessionStore | None = None,
        prefs: TrainerPrefs | None = None,
        clock: Callable[[], int] = time.perf_counter_ns,
        parent: QWidget | None = None,
    ) -> None:
        """Create the trainer for a set.

        Args:
            case_set: The cases to train.
            sessions: The trainer's sessions for this set; in memory if omitted.
            prefs: Learning statuses and the case filter; in-memory defaults (every
                case, equally likely) if omitted.
            clock: Monotonic clock in nanoseconds, passed to the timer.
            parent: Optional parent widget.

        """
        prefs = prefs if prefs is not None else MemoryTrainerPrefs()
        super().__init__(
            sessions=sessions,
            generate=filtered_case_scrambles(case_set, prefs, np.random.default_rng()),
            clock=clock,
            settings=prefs,
            parent=parent,
        )
        self.case_set: CaseSet = case_set
        self.prefs: TrainerPrefs = prefs
        self._cases: dict[str, Case] = {case.id: case for case in case_set.cases}
        self._recognizer: CaseRecognizer = CaseRecognizer(case_set)

        self._pending_mistake: bool = False
        self._fill_header()

        self.hints_shown: int = 0
        self._hint_alg: str = ""
        self._hint_length: int = 0
        self._hint_image: QPixmap = QPixmap()
        self.hint_panel: HintPanel = HintPanel()
        # Between the scramble bar and the timer.
        self.right_column.insertWidget(2, self.hint_panel)
        self.scramble_bar.scramble_changed.connect(self._reset_hints)
        # A shortcut fires before the timer sees the key press, so → never stops a
        # running solve: a hint can be asked for mid-solve.
        self._add_shortcut(HINT_SHORTCUT, self.show_next_hint)
        # Likewise M marks a mistake without ending the solve.
        self._add_shortcut(MISTAKE_SHORTCUT, self.toggle_mistake)
        self.timer.solve_started.connect(self._update_mistake_button)

        self.case_stats: CaseStatsPanel = CaseStatsPanel(case_set, self.solves)
        self.case_stats.setFixedWidth(CASE_STATS_WIDTH)
        self.columns.insertWidget(1, self.case_stats)
        self._update_mistake_button()
        self.update_filter_button()

    def _fill_header(self) -> None:
        """Add the trainer's controls around the Options button in the header.

        The row ends up as: title, filter button, (space), Mistake, Options, back.
        """
        self.title: QLabel = QLabel(f"{self.case_set.name} trainer")
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        self.title.setFont(font)
        self.back_button: QPushButton = QPushButton("← Full timer")
        self.back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_button.clicked.connect(self.back_requested)
        self.header.insertWidget(0, self.title)
        self.filter_button: QPushButton = QPushButton()
        self.filter_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.filter_button.setToolTip("Choose which cases to train")
        self.filter_button.clicked.connect(self.edit_filter)
        self.header.insertWidget(1, self.filter_button)
        self.mistake_button: QPushButton = QPushButton("Mistake")
        self.mistake_button.setCheckable(True)
        self.mistake_button.setObjectName("mistakeButton")
        # Only the checked state is styled, so the unchecked button stays native; the
        # margins match where macOS draws the native bezel inside the button, so the
        # two states are the same size. Scoped by object name so the tooltip keeps
        # its default look.
        self.mistake_button.setStyleSheet(
            f"#mistakeButton:checked {{ background-color: {MISTAKE_COLOR};"
            " color: white; border-radius: 5px; margin: 4px 0px 5px 0px; }",
        )
        # The checked rule has no padding, so its size hint is smaller than the native
        # button's; if the page is laid out while checked (the last solve was a
        # mistake) the layout would squeeze the button, and once unchecked the native
        # bezel no longer fits. Keep at least the native size (it starts unchecked).
        self.mistake_button.setMinimumSize(self.mistake_button.sizeHint())
        self.mistake_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mistake_button.setToolTip(
            "Mark the solve in progress, or else the last solve, as a mistake (M)",
        )
        self.mistake_button.clicked.connect(self.toggle_mistake)
        options_index = self.header.indexOf(self.options_button)
        self.header.insertWidget(options_index, self.mistake_button)
        self.header.addWidget(self.back_button)

    def edit_filter(self) -> None:
        """Open the filter dialog; apply and save the filter if accepted.

        Accepting moves on to a new scramble, so it matches the new filter.
        """
        dialog = FilterDialog(
            self.case_set,
            self.prefs.statuses(),
            self.prefs.load_filter(),
            self,
        )
        if self.run_dialog(dialog) == QDialog.DialogCode.Accepted:
            self.prefs.save_filter(dialog.case_filter())
            self.update_filter_button()
            self.scramble_bar.show_new()

    def update_filter_button(self) -> None:
        """Describe the current filter on its button, e.g. ``"12 cases · equal ▾"``."""
        cases, fell_back = active_cases(self.case_set, self.prefs)
        mode = "realistic" if self.prefs.load_filter().realistic else "equal"
        if fell_back:
            self.filter_button.setText(f"No case matches: all {len(cases)} · {mode}  ▾")
        else:
            noun = "case" if len(cases) == 1 else "cases"
            self.filter_button.setText(f"{len(cases)} {noun} · {mode}  ▾")

    @override
    def showEvent(self, event: QShowEvent) -> None:
        """Refresh the filter button: statuses may have changed in the Learn tab.

        Args:
            event: The show event.

        """
        super().showEvent(event)
        self.update_filter_button()

    def toggle_mistake(self) -> None:
        """Flip the mistake flag of the solve in progress, or else of the last solve.

        A flag set during a solve is applied when the solve finishes.
        """
        if self.timer.machine.state is TimerState.RUNNING:
            self._pending_mistake = not self._pending_mistake
        elif self.solves:
            last = self.solves.solves[-1]
            self.solves.set_mistake(-1, mistake=not last.mistake)
            self.refresh_solves()
        self._update_mistake_button()

    def _update_mistake_button(self) -> None:
        """Show whether the solve the button acts on is marked as a mistake."""
        if self.timer.machine.state is TimerState.RUNNING:
            marked = self._pending_mistake
        else:
            marked = bool(self.solves) and self.solves.solves[-1].mistake
        self.mistake_button.setChecked(marked)

    @override
    def show_session_solves(self) -> None:
        """Point the solves table and the per-case table at the new session."""
        super().show_session_solves()
        self.case_stats.set_solves(self.solves)
        self._update_mistake_button()

    @override
    def refresh_solves(self) -> None:
        """Redraw the solves table, the per-case table and the mistake button."""
        super().refresh_solves()
        self.case_stats.refresh()
        self._update_mistake_button()

    def show_next_hint(self) -> None:
        """Reveal one more hint step: the case image and first move, then a move more.

        The moves are the case's algorithm as written, starting from the case as the
        image shows it; turning the U layer to match the image is left to the user.
        Brackets in the algorithm are shown but don't count as steps.
        Does nothing if the current scramble isn't one of the set's cases.
        """
        if not self._hint_alg:
            recognized = self._recognizer.recognize(self.scramble_bar.scramble)
            if recognized is None:
                return
            case = self.current_case(recognized.id)
            self._hint_alg = case.alg
            self._hint_length = len(parse_alg(case.alg))
            self._hint_image = case_pixmap(case, HINT_IMAGE_SIZE)
        self.hints_shown = min(self.hints_shown + 1, self._hint_length)
        self.hint_panel.show_hint(self._hint_image, self._hint_alg, self.hints_shown)

    def _reset_hints(self) -> None:
        """Forget the hints when a different scramble is shown."""
        self.hints_shown = 0
        self._hint_alg = ""
        self.hint_panel.clear()

    @override
    def case_name(self, case_id: str) -> str:
        """Return the display name of one of the set's cases.

        Args:
            case_id: The case id.

        Returns:
            The case's name, or the id itself for an unknown case.

        """
        case = self._cases.get(case_id)
        return case.name if case else case_id

    @override
    def case_info(self, case_id: str) -> CaseInfo | None:
        """Return the name and image of one of the set's cases.

        Args:
            case_id: The case id.

        Returns:
            The case's name and image, or None for a case not in the set.

        """
        if case_id not in self._cases:
            return None
        case = self.current_case(case_id)
        return CaseInfo(name=case.name, image=case_pixmap(case, DIALOG_IMAGE_SIZE))

    def current_case(self, case_id: str) -> Case:
        """Return one of the set's cases with the user's changes (algorithm, image).

        Read afresh each time, so edits made in the Learn tab show straight away.

        Args:
            case_id: A case of the set.

        Returns:
            The case as the user customised it.

        """
        case = self._cases[case_id]
        customization = self.prefs.customizations().get(case_id)
        return customization.apply_to(case) if customization else case

    @override
    def make_solve(self, time_ms: int, scramble: str, penalty: Penalty) -> Solve:
        """Record a trainer solve together with the case its scramble set up.

        Args:
            time_ms: The solve time in milliseconds.
            scramble: The scramble shown when the solve started.
            penalty: The inspection penalty (OK without inspection).

        Returns:
            The new solve, with ``case_id`` set when the case is recognised, the
            number of hint steps revealed for it, and the mistake flag set during it.

        """
        case = self._recognizer.recognize(scramble)
        mistake, self._pending_mistake = self._pending_mistake, False
        return Solve(
            time_ms=time_ms,
            scramble=scramble,
            penalty=penalty,
            case_id=case.id if case else None,
            hints=self.hints_shown,
            mistake=mistake,
        )
