"""Trainer mode: the timer page drilling the cases of one set."""

import time
from collections.abc import Callable
from typing import override

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from cubetrainer.cases.catalog import Case, CaseSet
from cubetrainer.cases.trainer import (
    CaseRecognizer,
    uniform_case_scrambles,
)
from cubetrainer.cube.model import parse_alg, reveal_alg
from cubetrainer.solves import Solve, SolveList
from cubetrainer.ui.case_images import CaseInfo, case_pixmap
from cubetrainer.ui.solves_panel import TRAINER_LAYOUT, PanelLayout
from cubetrainer.ui.timer_page import TimerPage

#: Size of the case image in the solve dialog, in logical pixels.
DIALOG_IMAGE_SIZE: int = 160

#: Size of the case image in the hint panel, in logical pixels.
HINT_IMAGE_SIZE: int = 120

#: Shortcut revealing the next hint step.
HINT_SHORTCUT: str = "Right"

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
        title: Header naming the set.
        back_button: Returns to the full timer.
        hint_panel: Shows the hints for the current scramble.
        hints_shown: How many hint steps have been revealed for the current scramble.
        PANEL_LAYOUT: The trainer table, with a case column.

    """

    back_requested = Signal()
    PANEL_LAYOUT: PanelLayout = TRAINER_LAYOUT

    def __init__(
        self,
        case_set: CaseSet,
        solves: SolveList | None = None,
        generate: Callable[[], str] | None = None,
        clock: Callable[[], int] = time.perf_counter_ns,
        parent: QWidget | None = None,
    ) -> None:
        """Create the trainer for a set.

        Args:
            case_set: The cases to train.
            solves: The trainer session's solves; an empty, unsaved list if omitted.
            generate: Scramble generator; defaults to cases picked with equal
                probability.
            clock: Monotonic clock in nanoseconds, passed to the timer.
            parent: Optional parent widget.

        """
        super().__init__(
            solves=solves,
            generate=generate
            or uniform_case_scrambles(case_set, np.random.default_rng()),
            clock=clock,
            parent=parent,
        )
        self.case_set: CaseSet = case_set
        self._cases: dict[str, Case] = {case.id: case for case in case_set.cases}
        self._recognizer: CaseRecognizer = CaseRecognizer(case_set)

        self.title: QLabel = QLabel(f"{case_set.name} trainer")
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        self.title.setFont(font)
        self.back_button: QPushButton = QPushButton("← Full timer")
        self.back_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.back_button.clicked.connect(self.back_requested)
        header = QHBoxLayout()
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.back_button)
        self.right_column.insertLayout(0, header)

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

    def show_next_hint(self) -> None:
        """Reveal one more hint step: the case image and first move, then a move more.

        The moves are the case's algorithm as written, starting from the case as the
        image shows it; turning the U layer to match the image is left to the user.
        Brackets in the algorithm are shown but don't count as steps.
        Does nothing if the current scramble isn't one of the set's cases.
        """
        if not self._hint_alg:
            case = self._recognizer.recognize(self.scramble_bar.scramble)
            if case is None:
                return
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
        case = self._cases.get(case_id)
        if case is None:
            return None
        return CaseInfo(name=case.name, image=case_pixmap(case, DIALOG_IMAGE_SIZE))

    @override
    def make_solve(self, time_ms: int, scramble: str) -> Solve:
        """Record a trainer solve together with the case its scramble set up.

        Args:
            time_ms: The solve time in milliseconds.
            scramble: The scramble shown when the solve started.

        Returns:
            The new solve, with ``case_id`` set when the case is recognised and the
            number of hint steps revealed for it.

        """
        case = self._recognizer.recognize(scramble)
        return Solve(
            time_ms=time_ms,
            scramble=scramble,
            case_id=case.id if case else None,
            hints=self.hints_shown,
        )
