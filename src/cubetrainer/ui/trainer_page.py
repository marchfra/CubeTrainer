"""Trainer mode: the timer page drilling the cases of one set."""

import time
from collections.abc import Callable
from typing import override

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from cubetrainer.cases.catalog import Case, CaseSet
from cubetrainer.cases.trainer import CaseRecognizer, uniform_case_scrambles
from cubetrainer.solves import Solve, SolveList
from cubetrainer.ui.case_images import CaseInfo, case_pixmap
from cubetrainer.ui.solves_panel import TRAINER_LAYOUT, PanelLayout
from cubetrainer.ui.timer_page import TimerPage

#: Size of the case image in the solve dialog, in logical pixels.
DIALOG_IMAGE_SIZE: int = 160


class TrainerPage(TimerPage):
    """Timer page whose scrambles set up cases of a set, recording the case of each.

    Attributes:
        back_requested: Emitted when the user asks to return to the full timer.
        case_set: The set being trained.
        title: Header naming the set.
        back_button: Returns to the full timer.
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
            The new solve, with ``case_id`` set when the case is recognised.

        """
        case = self._recognizer.recognize(scramble)
        return Solve(
            time_ms=time_ms,
            scramble=scramble,
            case_id=case.id if case else None,
        )
