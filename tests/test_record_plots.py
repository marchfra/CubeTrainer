"""Tests for the personal-best progression plot."""

from datetime import UTC, datetime, timedelta

import numpy as np
from matplotlib.backend_bases import MouseEvent
from matplotlib.dates import date2num
from pytestqt.qtbot import QtBot

from cubetrainer.solves import Penalty, Solve
from cubetrainer.ui.record_plots import RecordsPlot

START = datetime(2026, 9, 1, tzinfo=UTC)


def solves_of(times_ms: list[float], dnf: frozenset[int] = frozenset()) -> list[Solve]:
    """Build solves an hour apart.

    Args:
        times_ms: Their times in milliseconds.
        dnf: Positions (0-based) of DNFs.

    Returns:
        The solves.

    """
    return [
        Solve(
            int(ms),
            "",
            Penalty.DNF if i in dnf else Penalty.OK,
            START + timedelta(hours=i),
        )
        for i, ms in enumerate(times_ms)
    ]


def make_plot(qtbot: QtBot, solves: list[Solve]) -> RecordsPlot:
    """Create and draw the plot.

    Args:
        qtbot: pytest-qt helper.
        solves: The solves.

    Returns:
        The plot.

    """
    plot = RecordsPlot()
    qtbot.addWidget(plot)
    plot.resize(700, 320)
    plot.show()
    plot.set_solves(solves)
    plot.canvas.draw()
    return plot


TIMES = [20_000.0, 18_000.0, 19_000.0, 17_000.0, 21_000.0, 16_000.0]


def test_records_list_single_and_ao5_bests(qtbot: QtBot) -> None:
    """Records carry the solve's date, the value and the solve number."""
    plot = make_plot(qtbot, solves_of(TIMES))

    assert [(v, n) for _when, v, n in plot.records["single"]] == [
        (20_000, 1),
        (18_000, 2),
        (17_000, 4),
        (16_000, 6),
    ]
    assert plot.records["single"][1][0] == START + timedelta(hours=1)
    assert [n for _when, _v, n in plot.records["ao5"]] == [5, 6]
    labels = [str(line.get_label()) for line in plot.figure.axes[0].get_lines()]
    assert labels == ["best single", "best ao5"]


def test_lines_carry_on_to_the_latest_solve(qtbot: QtBot) -> None:
    """The last best extends to the latest solve, which set no record."""
    plot = make_plot(qtbot, solves_of([*TIMES, 30_000.0, 31_000.0]))
    single = plot.figure.axes[0].get_lines()[0]

    assert float(np.asarray(single.get_xdata(), dtype=float)[-1]) == date2num(
        START + timedelta(hours=7),
    )


def test_note_without_finished_solves(qtbot: QtBot) -> None:
    """Without finished solves the plot says so."""
    plot = make_plot(qtbot, solves_of([5_000.0], dnf=frozenset({0})))

    assert plot.figure.axes[0].texts[0].get_text() == "No finished solves yet"


def test_description_and_hover(qtbot: QtBot) -> None:
    """The tooltip shows the bests standing at the date under the mouse."""
    plot = make_plot(qtbot, solves_of(TIMES))

    assert plot.describe_record(date2num(START - timedelta(days=1))) is None
    (axes,) = plot.figure.axes
    moment = date2num(START + timedelta(hours=3, minutes=30))
    x, y = axes.transData.transform((moment, sum(axes.get_ylim()) / 2))
    plot.canvas.callbacks.process(
        "motion_notify_event",
        MouseEvent("motion_notify_event", plot.canvas, x, y),
    )

    assert plot.tooltip_text == "best single 17.00 (#4, 2026-09-01)"
