"""Tests for the solves table and the summary panel."""

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from cubetrainer.solves import Penalty, Solve, SolveList
from cubetrainer.ui.solves_panel import COLUMNS, SolvesPanel


@pytest.fixture
def solves() -> SolveList:
    """Provide six solves: 10, 11, 12, 13, 14 s and a DNF.

    Returns:
        The solve list.

    """
    solve_list = SolveList()
    for seconds in range(10, 15):
        solve_list.add(Solve(seconds * 1_000, f"scramble {seconds}"))
    solve_list.add(Solve(9_000, "last", Penalty.DNF))
    return solve_list


@pytest.fixture
def panel(qtbot: QtBot, solves: SolveList) -> SolvesPanel:
    """Provide a visible panel showing ``solves``.

    Args:
        qtbot: pytest-qt helper.
        solves: The solve list.

    Returns:
        The panel.

    """
    widget = SolvesPanel(solves)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def cell(panel: SolvesPanel, row: int, column: int) -> str:
    """Return the text of a table cell.

    Args:
        panel: The panel.
        row: Table row (0 is the newest solve).
        column: Column number.

    Returns:
        The cell text.

    """
    text = panel.model.data(panel.model.index(row, column))
    assert isinstance(text, str)
    return text


def test_table_lists_newest_first_with_rolling_averages(panel: SolvesPanel) -> None:
    """Rows go newest to oldest; ao5 appears from the fifth solve; ao12 is missing."""
    assert [panel.model.headerData(i, Qt.Orientation.Horizontal) for i in range(4)] == [
        *COLUMNS,
    ]
    assert panel.model.rowCount() == 6
    # Newest: the DNF, whose ao5 is (12 + 13 + 14) / 3 after trimming 11 and the DNF.
    assert [cell(panel, 0, c) for c in range(4)] == ["6", "DNF", "13.00", "-"]
    # Fifth solve: first ao5, (11 + 12 + 13) / 3 after trimming 10 and 14.
    assert [cell(panel, 1, c) for c in range(4)] == ["5", "14.00", "12.00", "-"]
    # Oldest solve.
    assert [cell(panel, 5, c) for c in range(4)] == ["1", "10.00", "-", "-"]


def test_summary_shows_current_best_and_mean(panel: SolvesPanel) -> None:
    """The summary grid matches hand-computed statistics."""
    cells = panel.summary.cells

    assert cells["time", "current"].text() == "DNF"
    assert cells["time", "best"].text() == "10.00"
    assert cells["ao5", "current"].text() == "13.00"
    assert cells["ao5", "best"].text() == "12.00"
    assert cells["ao12", "current"].text() == "-"
    assert panel.summary.mean_label.text() == "solves: 5/6    mean: 12.00"


def test_refresh_reflects_changes(panel: SolvesPanel, solves: SolveList) -> None:
    """After a change and a refresh, the table and summary update."""
    solves.set_penalty(-1, Penalty.OK)  # the 9.00 DNF becomes a valid 9.00

    panel.refresh()

    assert cell(panel, 0, 1) == "9.00"
    assert panel.summary.cells["time", "best"].text() == "9.00"


def test_clicking_a_row_emits_solve_index(qtbot: QtBot, panel: SolvesPanel) -> None:
    """Clicking the second row reports the second-newest solve's list index."""
    rect = panel.table.visualRect(panel.model.index(1, 1))

    with qtbot.waitSignal(panel.solve_activated) as blocker:
        qtbot.mouseClick(
            panel.table.viewport(),
            Qt.MouseButton.LeftButton,
            pos=rect.center(),
        )

    assert blocker.args == [4]


def test_empty_list(qtbot: QtBot) -> None:
    """An empty session shows dashes everywhere."""
    panel = SolvesPanel(SolveList())
    qtbot.addWidget(panel)

    assert panel.model.rowCount() == 0
    assert panel.summary.cells["time", "current"].text() == "-"
    assert panel.summary.mean_label.text() == "solves: 0/0    mean: -"


def test_averages_are_rounded_but_singles_truncated(qtbot: QtBot) -> None:
    """ao5 of 11.606... shows 11.61, while a 12.349 single shows 12.34."""
    solve_list = SolveList()
    for ms in (12_340, 10_980, 16_020, 11_500, 9_870, 12_349):
        solve_list.add(Solve(ms, ""))
    panel = SolvesPanel(solve_list)
    qtbot.addWidget(panel)

    assert cell(panel, 1, 2) == "11.61"  # (12.34 + 10.98 + 11.50) / 3 = 11.6067
    assert cell(panel, 0, 1) == "12.34"
    assert panel.summary.cells["ao5", "best"].text() == "11.61"
