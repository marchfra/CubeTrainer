"""Tests for trainer mode: the trainer page and how the app switches to it."""

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel
from pytestqt.qtbot import QtBot

from cubetrainer.cases.catalog import load_case_set
from cubetrainer.cases.trainer import case_scramble
from cubetrainer.db import Database
from cubetrainer.ui.main_window import MainWindow
from cubetrainer.ui.solve_dialog import SolveDialog
from cubetrainer.ui.trainer_page import DIALOG_IMAGE_SIZE, TrainerPage
from tests.helpers import FakeClock, do_solve

PLL = load_case_set("pll")
T_CASE = next(c for c in PLL.cases if c.id == "T")


@pytest.fixture
def page(qtbot: QtBot, clock: FakeClock) -> TrainerPage:
    """Provide a visible PLL trainer whose scrambles are always a T perm.

    Args:
        qtbot: pytest-qt helper.
        clock: The fake clock.

    Returns:
        The page.

    """
    rng = np.random.default_rng(3)
    widget = TrainerPage(PLL, generate=lambda: case_scramble(T_CASE, rng), clock=clock)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_solve_records_its_case(
    qtbot: QtBot,
    page: TrainerPage,
    clock: FakeClock,
) -> None:
    """A trainer solve stores the case of its scramble, shown in the case column."""
    do_solve(qtbot, page, clock, 1_500)

    solve = page.solves.solves[0]
    assert solve.case_id == "T"
    model = page.solves_panel.model
    assert model.columnCount() == 3
    assert model.data(model.index(0, 2)) == "T"


def test_solve_dialog_names_the_case(
    qtbot: QtBot,
    page: TrainerPage,
    clock: FakeClock,
) -> None:
    """The details dialog of a trainer solve names and shows the case."""
    do_solve(qtbot, page, clock, 1_500)
    labels: list[QLabel] = []

    def run_dialog(dialog: QDialog) -> int:
        assert isinstance(dialog, SolveDialog)
        labels.extend(dialog.findChildren(QLabel))
        return 0

    page.run_dialog = run_dialog
    page.show_solve(0)

    assert "Case: T" in [label.text() for label in labels]
    images = [label.pixmap() for label in labels if not label.pixmap().isNull()]
    assert len(images) == 1
    assert images[0].deviceIndependentSize().width() == DIALOG_IMAGE_SIZE


def test_full_solve_dialog_has_no_case(
    qtbot: QtBot,
    clock: FakeClock,
) -> None:
    """Full-timer solves show neither a case name nor an image."""
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    window.show()
    window.timer_page.timer._clock = clock
    do_solve(qtbot, window.timer_page, clock, 9_000)
    labels: list[QLabel] = []

    def run_dialog(dialog: QDialog) -> int:
        labels.extend(dialog.findChildren(QLabel))
        return 0

    window.timer_page.run_dialog = run_dialog
    window.timer_page.show_solve(0)

    assert not any(label.text().startswith("Case:") for label in labels)
    assert all(label.pixmap().isNull() for label in labels)


def test_header_and_back_button(qtbot: QtBot, page: TrainerPage) -> None:
    """The header names the set; the back button asks to leave the trainer."""
    assert page.title.text() == "PLL trainer"

    with qtbot.waitSignal(page.back_requested):
        qtbot.mouseClick(page.back_button, Qt.MouseButton.LeftButton)


def test_train_button_opens_trainer_and_back_returns(qtbot: QtBot) -> None:
    """Learn → Train switches the Timer tab to the trainer; back shows the timer."""
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    window.show()
    window.tabs.setCurrentWidget(window.learn_page)

    assert window.learn_page.train_button.text() == "Train PLL"
    qtbot.mouseClick(window.learn_page.train_button, Qt.MouseButton.LeftButton)

    trainer = window.trainer_pages["pll"]
    assert window.tabs.currentWidget() is window.timer_stack
    assert window.timer_stack.currentWidget() is trainer
    assert window.tabs.tabText(window.tabs.currentIndex()) == "Timer"

    qtbot.mouseClick(trainer.back_button, Qt.MouseButton.LeftButton)
    assert window.timer_stack.currentWidget() is window.timer_page

    window.open_trainer("pll")
    assert window.trainer_pages["pll"] is trainer  # reused, not recreated


def test_trainer_solves_are_kept_apart(qtbot: QtBot, clock: FakeClock) -> None:
    """Trainer solves go to their own session, not the full timer's list."""
    db = Database(":memory:")
    window = MainWindow(db)
    qtbot.addWidget(window)
    window.show()
    window.open_trainer("pll")
    trainer = window.trainer_pages["pll"]
    trainer.timer._clock = clock

    do_solve(qtbot, trainer, clock, 2_000)

    assert len(trainer.solves) == 1
    assert len(window.timer_page.solves) == 0
    stored = db.load_solves(db.get_or_create_session("trainer:pll"))
    assert [(s.time_ms, s.case_id is not None) for s in stored] == [(2_000, True)]
