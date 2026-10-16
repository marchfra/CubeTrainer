"""Tests for the Stats tab's distribution plots."""

import math

import numpy as np
from matplotlib.backend_bases import MouseEvent
from pytestqt.qtbot import QtBot

from cubetrainer.ui.distribution_plots import DistributionPlots
from cubetrainer.ui.time_graph import DARK, LIGHT


def make_plots(qtbot: QtBot, values: list[float]) -> DistributionPlots:
    """Create plots of some results.

    Args:
        qtbot: pytest-qt helper.
        values: Results in milliseconds.

    Returns:
        The plots, shown and drawn.

    """
    plots = DistributionPlots()
    qtbot.addWidget(plots)
    plots.resize(1200, 340)
    plots.show()
    plots.set_values(values)
    plots.canvas.draw()
    return plots


def sample() -> list[float]:
    """Return 200 skewed solve times in milliseconds, plus two DNFs.

    Returns:
        The results.

    """
    rng = np.random.default_rng(3)
    times = (rng.normal(15, 1.5, 200) + rng.exponential(2.5, 200)) * 1000
    return [*times.tolist(), math.inf, math.inf]


def test_placeholder_with_few_solves(qtbot: QtBot) -> None:
    """Fewer than ten finished solves show a note instead of plots."""
    plots = make_plots(qtbot, [10_000.0] * 5 + [math.inf] * 10)

    assert len(plots.figure.axes) == 1
    assert "at least 10 finished solves" in plots.figure.axes[0].texts[0].get_text()
    assert plots.fit is None


def test_histogram_and_cumulative_with_the_fit(qtbot: QtBot) -> None:
    """Both plots show the data and the ex-Gaussian fit; DNFs are left out."""
    plots = make_plots(qtbot, sample())
    histogram, cumulative = plots.figure.axes

    assert len(plots.seconds) == 200
    assert plots.fit is not None
    assert sum(bar.count for bar in plots.bars) == 200
    assert len(histogram.get_lines()) == 1
    assert histogram.get_lines()[0].get_color() in {LIGHT.series[0], DARK.series[0]}
    legend = cumulative.get_legend()
    assert legend is not None
    labels = [t.get_text() for t in legend.get_texts()]
    assert labels == ["your times", "ex-Gaussian fit"]


def test_bar_and_share_descriptions(qtbot: QtBot) -> None:
    """Tooltips describe a bar's range and count, and the share under a time."""
    plots = make_plots(qtbot, [float(ms) for ms in range(10_000, 20_000, 500)])
    first = plots.bars[0]

    text = plots.describe_bar(first.start)
    assert text is not None
    assert text.startswith(f"{first.start:.1f}-{first.end:.1f} s: {first.count} solve")
    assert plots.describe_bar(1.0) is None
    assert plots.describe_share(15.0) == "under 15.00 s: 50% of solves"


def test_hover_on_each_plot(qtbot: QtBot) -> None:
    """Hovering a bar or the cumulative curve sets the tooltip."""
    plots = make_plots(qtbot, sample())
    histogram, cumulative = plots.figure.axes

    for axes, start in ((histogram, plots.bars[3].start + 0.01), (cumulative, 16.0)):
        x, y = axes.transData.transform((start, axes.get_ylim()[1] / 2))
        plots.canvas.callbacks.process(
            "motion_notify_event",
            MouseEvent("motion_notify_event", plots.canvas, x, y),
        )
        assert plots.tooltip_text
        assert plots.canvas.toolTip() == plots.tooltip_text
    assert plots.tooltip_text.startswith("under 16.00 s:")
