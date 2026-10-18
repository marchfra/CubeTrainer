"""Tests for the time graph under the full timer."""

import math

from matplotlib.backend_bases import MouseEvent
from pytestqt.qtbot import QtBot

from cubetrainer.db import Database
from cubetrainer.solves import Penalty, Solve, SolveList
from cubetrainer.ui.chart_style import DARK, GRAPH_HEIGHT, LIGHT
from cubetrainer.ui.main_window import MainWindow
from cubetrainer.ui.time_graph import SERIES_NAMES, TimeGraph
from cubetrainer.ui.timer_page import TimerPage
from tests.helpers import FakeClock, do_solve


def make_graph(
    qtbot: QtBot,
    times: list[int],
    dnf: frozenset[int] = frozenset(),
) -> TimeGraph:
    """Create a graph of some times.

    Args:
        qtbot: pytest-qt helper.
        times: Solve times in milliseconds.
        dnf: Positions (0-based) of solves that are DNFs.

    Returns:
        The graph, shown and laid out.

    """
    solves = SolveList()
    for i, ms in enumerate(times):
        solves.add(Solve(ms, "", Penalty.DNF if i in dnf else Penalty.OK))
    graph = TimeGraph(solves)
    qtbot.addWidget(graph)
    graph.resize(700, 190)
    graph.show()
    graph.canvas.draw()
    return graph


def test_series_values_and_gaps(qtbot: QtBot) -> None:
    """Singles in seconds with DNFs as gaps; averages start once there are enough."""
    graph = make_graph(
        qtbot,
        [10_000, 12_000, 11_000, 13_000, 14_000, 9_000],
        frozenset({2}),
    )

    single = graph.series["single"]
    assert single[:2] == [10.0, 12.0]
    assert math.isnan(single[2])
    ao5 = graph.series["ao5"]
    assert all(math.isnan(v) for v in ao5[:4])
    assert ao5[4] == 13.0  # 10, 12, DNF, 13, 14 -> drop 10 and the DNF
    assert all(math.isnan(v) for v in graph.series["ao12"])


def test_three_lines_with_legend(qtbot: QtBot) -> None:
    """Each series is a line in its slot colour, named in the legend (no end labels)."""
    graph = make_graph(qtbot, [10_000 + 100 * i for i in range(15)])
    axes = graph.figure.axes[0]

    lines = [line for line in axes.get_lines() if line.get_label() in SERIES_NAMES]
    assert [line.get_label() for line in lines] == list(SERIES_NAMES)
    assert {line.get_color() for line in lines} <= {*LIGHT.series, *DARK.series}
    legend = axes.get_legend()
    assert legend is not None
    assert [t.get_text() for t in legend.get_texts()] == list(SERIES_NAMES)
    assert len(axes.texts) == 0


def test_placeholder_before_two_solves(qtbot: QtBot) -> None:
    """With fewer than two solves the graph says so instead of drawing lines."""
    graph = make_graph(qtbot, [10_000])
    axes = graph.figure.axes[0]

    assert axes.get_lines() == []
    assert [t.get_text() for t in axes.texts] == [
        "The graph appears after a couple of solves",
    ]


def test_hover_shows_the_nearest_solve(qtbot: QtBot) -> None:
    """Moving over the plot puts the crosshair on a solve and describes it."""
    graph = make_graph(qtbot, [10_000, 12_000, 11_000, 13_000, 14_000, 9_000])
    axes = graph.figure.axes[0]
    x, y = axes.transData.transform((5.2, 12.0))

    graph.canvas.callbacks.process(
        "motion_notify_event",
        MouseEvent("motion_notify_event", graph.canvas, x, y),
    )

    assert graph.tooltip_text == "#5   14.00   ao5 12.00   ao12 -"
    assert graph.canvas.toolTip() == graph.tooltip_text


def test_timer_page_graph_follows_solves_and_sessions(
    qtbot: QtBot,
    clock: FakeClock,
) -> None:
    """The timer's graph follows solves and sessions; the trainer has none."""
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    window.show()
    page = window.timer_page
    page.timer._clock = clock
    qtbot.waitUntil(lambda: page.time_graph is not None)  # built just after showing
    assert page.time_graph is not None

    do_solve(qtbot, page, clock, 9_000)
    do_solve(qtbot, page, clock, 8_000)
    assert page.time_graph.series["single"] == [9.0, 8.0]

    page.ask_text = lambda _label, _text: "Other"
    page.new_session()
    assert page.time_graph.series["single"] == []

    window.open_trainer("pll")
    assert window.trainer_pages["pll"].time_graph is None


def test_window_opens_before_the_graph_is_built(qtbot: QtBot) -> None:
    """The graph (and matplotlib) come just after the page appears, in its space."""
    page = TimerPage()
    qtbot.addWidget(page)
    assert page.time_graph is None  # not built before the page is shown

    page.show()
    qtbot.waitUntil(lambda: page.time_graph is not None)
    assert page.time_graph is not None
    assert page.time_graph.height() == GRAPH_HEIGHT
