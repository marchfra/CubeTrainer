"""Tests for the trainer's per-case statistics table."""

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from cubetrainer.cases.catalog import load_case_set
from cubetrainer.solves import Penalty, Solve, SolveList
from cubetrainer.ui.case_stats_panel import COLUMNS, CaseStatsPanel

PLL = load_case_set("pll")


def make_panel(qtbot: QtBot, solves: SolveList) -> CaseStatsPanel:
    """Create a per-case panel for the PLL set.

    Args:
        qtbot: pytest-qt helper.
        solves: The trainer solves.

    Returns:
        The panel.

    """
    panel = CaseStatsPanel(PLL, solves)
    qtbot.addWidget(panel)
    return panel


def rows(panel: CaseStatsPanel) -> list[list[str]]:
    """Return the table's text as shown (sorted), row by row.

    Args:
        panel: The panel.

    Returns:
        The displayed cells.

    """
    proxy = panel.proxy
    return [
        [proxy.data(proxy.index(r, c)) for c in range(proxy.columnCount())]
        for r in range(proxy.rowCount())
    ]


def sample_solves() -> SolveList:
    """Build solves of three cases: T (with a mistake and a hint), Ua and Aa (DNF).

    Returns:
        The solve list.

    """
    solves = SolveList()
    for solve in (
        Solve(3_000, "", case_id="T"),
        Solve(1_000, "", case_id="T", mistake=True),
        Solve(2_000, "", case_id="T", hints=1),
        Solve(1_500, "", case_id="Ua"),
        Solve(4_000, "", Penalty.DNF, case_id="Aa"),
    ):
        solves.add(solve)
    return solves


def test_one_row_per_case_in_set_order(qtbot: QtBot) -> None:
    """Only cases with solves appear, in the set's order, mistakes left out."""
    panel = make_panel(qtbot, sample_solves())

    assert [panel.proxy.headerData(c, Qt.Orientation.Horizontal) for c in range(7)] == [
        *COLUMNS,
    ]
    assert rows(panel) == [
        ["Aa", "1", "DNF", "-", "-", "0%", "0%"],
        ["T", "3", "2.00", "2.50", "-", "33%", "33%"],
        ["Ua", "1", "1.50", "1.50", "-", "0%", "0%"],
    ]


def test_sorting_uses_numbers_not_text(qtbot: QtBot) -> None:
    """Sorting by best puts 1.50 before 2.00, and DNF last."""
    panel = make_panel(qtbot, sample_solves())

    panel.table.sortByColumn(COLUMNS.index("best"), Qt.SortOrder.AscendingOrder)

    assert [row[0] for row in rows(panel)] == ["Ua", "T", "Aa"]


def test_refresh_picks_up_new_solves(qtbot: QtBot) -> None:
    """New solves show after a refresh."""
    solves = SolveList()
    panel = make_panel(qtbot, solves)
    assert rows(panel) == []

    solves.add(Solve(2_000, "", case_id="H"))
    panel.refresh()

    assert rows(panel)[0][:3] == ["H", "1", "2.00"]
