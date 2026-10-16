"""Tests for the Q-Q and personal-best plots."""

from datetime import UTC, datetime, timedelta

import numpy as np
from matplotlib.backend_bases import MouseEvent
from matplotlib.dates import date2num
from pytestqt.qtbot import QtBot

from cubetrainer.solves import Penalty, Solve
from cubetrainer.ui.record_plots import RecordPlots

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


def make_plots(qtbot: QtBot, solves: list[Solve]) -> RecordPlots:
    """Create and draw the plots.

    Args:
        qtbot: pytest-qt helper.
        solves: The solves.

    Returns:
        The plots.

    """
    plots = RecordPlots()
    qtbot.addWidget(plots)
    plots.resize(1200, 320)
    plots.show()
    plots.set_solves(solves)
    plots.canvas.draw()
    return plots


def skewed(n: int = 120) -> list[float]:
    """Return skewed solve times in milliseconds.

    Args:
        n: How many.

    Returns:
        The times.

    """
    rng = np.random.default_rng(5)
    return ((rng.normal(15, 1.5, n) + rng.exponential(2.5, n)) * 1000).tolist()


def test_qq_compares_sorted_times_with_the_fit(qtbot: QtBot) -> None:
    """Observed and expected times line up rank by rank; DNFs are left out."""
    plots = make_plots(qtbot, solves_of(skewed(), dnf=frozenset({0, 1})))

    assert plots.observed.size == plots.expected.size == 118
    assert np.all(np.diff(plots.observed) >= 0)
    assert np.all(np.diff(plots.expected) > 0)
    # A good fit: expected and observed medians agree within half a second.
    assert abs(np.median(plots.expected) - np.median(plots.observed)) < 0.5


def test_records_list_single_and_ao5_bests(qtbot: QtBot) -> None:
    """Records carry the solve's date, the value and the solve number."""
    times = [20_000.0, 18_000.0, 19_000.0, 17_000.0, 21_000.0, 16_000.0]
    plots = make_plots(qtbot, solves_of(times))

    assert [(v, n) for _when, v, n in plots.records["single"]] == [
        (20_000, 1),
        (18_000, 2),
        (17_000, 4),
        (16_000, 6),
    ]
    assert plots.records["single"][1][0] == START + timedelta(hours=1)
    assert [n for _when, _v, n in plots.records["ao5"]] == [5, 6]


def test_notes_without_enough_solves(qtbot: QtBot) -> None:
    """Few solves give notes instead of plots."""
    plots = make_plots(qtbot, solves_of([10_000.0, 11_000.0]))
    qq, progress = plots.figure.axes

    assert "at least 10 finished solves" in qq.texts[0].get_text()
    assert len(progress.texts) == 0  # two solves are enough for single records
    empty = make_plots(qtbot, [])
    assert empty.figure.axes[1].texts[0].get_text() == "No finished solves yet"


def test_descriptions(qtbot: QtBot) -> None:
    """Tooltips describe a Q-Q point and the bests standing at a date."""
    times = [20_000.0, 18_000.0, 19_000.0, 17_000.0, 21_000.0, 16_000.0, *skewed(20)]
    plots = make_plots(qtbot, solves_of(times))

    point = plots.describe_point(float(plots.expected[0]))
    assert point is not None
    assert point.startswith(f"yours {plots.observed[0]:.2f} s, expected")
    record = plots.describe_record(date2num(START + timedelta(hours=3, minutes=30)))
    assert record == "best single 17.00 (#4, 2026-09-01)"
    assert plots.describe_record(date2num(START - timedelta(days=1))) is None


def test_hover_on_each_plot(qtbot: QtBot) -> None:
    """Hovering either plot sets the tooltip."""
    plots = make_plots(qtbot, solves_of(skewed()))
    qq, progress = plots.figure.axes
    targets = (
        (qq, float(plots.expected[50])),
        (progress, date2num(START + timedelta(hours=60))),
    )

    for axes, x_value in targets:
        x, y = axes.transData.transform((x_value, sum(axes.get_ylim()) / 2))
        plots.canvas.callbacks.process(
            "motion_notify_event",
            MouseEvent("motion_notify_event", plots.canvas, x, y),
        )
        assert plots.tooltip_text
    assert plots.tooltip_text.startswith("best single")
