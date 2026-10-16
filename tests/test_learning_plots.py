"""Tests for the learning curve and the trainer's case charts."""

import math

import numpy as np
from pytestqt.qtbot import QtBot

from cubetrainer.solves import Solve
from cubetrainer.ui.learning_plots import MAX_CASES, CaseCharts, LearningCurvePlot


def make_curve(qtbot: QtBot, values: list[float]) -> LearningCurvePlot:
    """Create and draw a learning curve.

    Args:
        qtbot: pytest-qt helper.
        values: Results in milliseconds.

    Returns:
        The plot.

    """
    plot = LearningCurvePlot()
    qtbot.addWidget(plot)
    plot.resize(1200, 300)
    plot.show()
    plot.set_values(values)
    plot.canvas.draw()
    return plot


def improving_ms(n: int = 200) -> list[float]:
    """Return improving times in milliseconds, with one DNF.

    Args:
        n: How many.

    Returns:
        The results.

    """
    rng = np.random.default_rng(4)
    times = (16 + 6 * np.exp(-np.arange(n) / 60) + rng.normal(0, 1, n)) * 1000
    values = times.tolist()
    values[10] = math.inf
    return values


def test_learning_curve_with_trend_projection_and_plateau(qtbot: QtBot) -> None:
    """Improving times give a trend, its projection and a plateau line."""
    plot = make_curve(qtbot, improving_ms())
    axes = plot.figure.axes[0]

    assert plot.curve is not None
    assert len(plot.seconds) == 199  # the DNF is left out
    assert plot.numbers[10] == 12  # numbering counts the DNF
    labels = [str(line.get_label()) for line in axes.get_lines()]
    assert labels[:3] == ["your times", "trend", "projection"]
    assert labels[3].startswith("plateau ")
    assert plot.summary().startswith("levelling off at ")
    assert axes.get_title(loc="left").startswith("Learning curve: levelling off")


def test_learning_curve_without_improvement(qtbot: QtBot) -> None:
    """Flat times say so and draw no plateau."""
    flat = (np.random.default_rng(6).normal(15, 1, 100) * 1000).tolist()

    plot = make_curve(qtbot, flat)

    assert plot.summary() == "no clear improvement"
    labels = [str(line.get_label()) for line in plot.figure.axes[0].get_lines()]
    assert not any(label.startswith("plateau") for label in labels)


def test_learning_curve_note_and_hover(qtbot: QtBot) -> None:
    """Few solves show a note; hovering describes the nearest solve."""
    assert "needs 30 finished solves" in (
        make_curve(qtbot, [10_000.0] * 5).figure.axes[0].texts[0].get_text()
    )
    plot = make_curve(qtbot, improving_ms())

    text = plot.describe_at(plot.figure.axes[0], 50.2, 0)

    assert text is not None
    assert text.startswith("#50  ")
    assert "(trend " in text


def solves_for(case_id: str, times: list[int], mistakes: int = 0) -> list[Solve]:
    """Build trainer solves of a case, the last few marked as mistakes.

    Args:
        case_id: The case.
        times: Their times in milliseconds.
        mistakes: How many of the last ones are mistakes.

    Returns:
        The solves.

    """
    return [
        Solve(ms, "", case_id=case_id, mistake=i >= len(times) - mistakes, hints=0)
        for i, ms in enumerate(times)
    ]


def make_charts(qtbot: QtBot, solves: list[Solve]) -> CaseCharts:
    """Create and draw case charts.

    Args:
        qtbot: pytest-qt helper.
        solves: Trainer solves.

    Returns:
        The charts.

    """
    charts = CaseCharts()
    qtbot.addWidget(charts)
    charts.resize(1200, 400)
    charts.show()
    charts.set_solves(solves, lambda case_id: f"case {case_id}")
    charts.canvas.draw()
    return charts


def test_cases_are_ranked_slowest_first(qtbot: QtBot) -> None:
    """Rows go from the slowest mean to the fastest; rates include mistakes."""
    solves = [
        *solves_for("a", [2_000, 2_000]),
        *solves_for("b", [5_000, 5_000, 9_000], mistakes=1),
        *solves_for("c", [3_000]),
    ]

    charts = make_charts(qtbot, solves)

    assert [row.name for row in charts.rows] == ["case b", "case c", "case a"]
    assert charts.rows[0].stats.mean == 5_000  # the 9 s mistake is left out
    assert charts.rows[0].stats.mistake_rate == 1 / 3
    assert len(charts.figure.axes) == 3


def test_only_the_slowest_cases_are_shown(qtbot: QtBot) -> None:
    """With many cases, the charts keep the slowest ones and say so."""
    solves = [s for i in range(25) for s in solves_for(str(i), [1_000 + 100 * i])]

    charts = make_charts(qtbot, solves)

    assert len(charts.rows) == MAX_CASES
    assert charts.rows[0].name == "case 24"
    assert charts.figure.get_suptitle() == f"The {MAX_CASES} slowest cases"


def test_case_hover_and_empty_note(qtbot: QtBot) -> None:
    """Hovering a row describes its case; no solves give a note."""
    charts = make_charts(qtbot, solves_for("T", [2_000, 3_000], mistakes=1))

    text = charts.describe_at(charts.figure.axes[0], 0, 0.1)
    assert text == "case T: mean 2.00 s · mistakes 50% · hints 0% (2 solves)"
    assert charts.describe_at(charts.figure.axes[0], 0, 5) is None

    empty = make_charts(qtbot, [])
    assert empty.figure.axes[0].texts[0].get_text() == "No trainer solves yet"
