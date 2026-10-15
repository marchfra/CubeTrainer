"""Tests for the solve details dialog."""

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from cubetrainer.solves import Penalty, Solve
from cubetrainer.ui.solve_dialog import SolveDialog


def test_shows_solve_details(qtbot: QtBot) -> None:
    """The dialog shows the number, time and current penalty."""
    solve = Solve(12_345, "R U R'", Penalty.PLUS_TWO)
    dialog = SolveDialog(solve, 7)
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "Solve #7"
    assert dialog.time_label.text() == "14.34 (12.34 + 2)"
    assert dialog.penalty_buttons[Penalty.PLUS_TWO].isChecked()


def test_penalty_buttons_update_solve(qtbot: QtBot) -> None:
    """Choosing a penalty changes the solve right away."""
    solve = Solve(12_345, "R U R'")
    dialog = SolveDialog(solve, 1)
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.mouseClick(dialog.penalty_buttons[Penalty.DNF], Qt.MouseButton.LeftButton)

    assert solve.penalty is Penalty.DNF
    assert dialog.time_label.text() == "DNF (12.34)"


def test_delete_button_finishes_with_deleted(qtbot: QtBot) -> None:
    """Delete closes the dialog with the DELETED result."""
    dialog = SolveDialog(Solve(1_000, ""), 1)
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.mouseClick(dialog.delete_button, Qt.MouseButton.LeftButton)

    assert dialog.result() == SolveDialog.DELETED
