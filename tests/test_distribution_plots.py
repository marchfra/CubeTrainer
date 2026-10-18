"""Tests for the Stats tab's histogram."""

import math

import numpy as np
from matplotlib.backend_bases import MouseEvent
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from pytestqt.qtbot import QtBot

from cubetrainer.ui.chart_style import DARK, LIGHT
from cubetrainer.ui.distribution_plots import HistogramPlot


def make_plot(qtbot: QtBot, values: list[float]) -> HistogramPlot:
    """Create a histogram of some results.

    Args:
        qtbot: pytest-qt helper.
        values: Results in milliseconds.

    Returns:
        The plot, shown and drawn.

    """
    plot = HistogramPlot()
    qtbot.addWidget(plot)
    plot.resize(700, 320)
    plot.show()
    plot.set_values(values)
    plot.canvas.draw()
    return plot


def sample() -> list[float]:
    """Return 200 skewed solve times in milliseconds, plus two DNFs.

    Returns:
        The results.

    """
    rng = np.random.default_rng(3)
    times = (rng.normal(15, 1.5, 200) + rng.exponential(2.5, 200)) * 1000
    return [*times.tolist(), math.inf, math.inf]


def test_placeholder_with_few_solves(qtbot: QtBot) -> None:
    """Fewer than ten finished solves show a note instead of a histogram."""
    plot = make_plot(qtbot, [10_000.0] * 5 + [math.inf] * 10)

    assert "at least 10 finished solves" in plot.figure.axes[0].texts[0].get_text()
    assert plot.fit is None


def test_histogram_with_the_fit(qtbot: QtBot) -> None:
    """The histogram shows the data and the ex-Gaussian fit; DNFs are left out."""
    plot = make_plot(qtbot, sample())
    (axes,) = plot.figure.axes

    assert len(plot.seconds) == 200
    assert plot.fit is not None
    assert sum(bar.count for bar in plot.bars) == 200
    assert len(axes.get_lines()) == 1
    assert axes.get_lines()[0].get_color() in {LIGHT.series[0], DARK.series[0]}


def test_bar_description_and_hover(qtbot: QtBot) -> None:
    """Hovering a bar describes its range and count."""
    plot = make_plot(qtbot, [float(ms) for ms in range(10_000, 20_000, 500)])
    first = plot.bars[0]
    assert plot.describe_bar(1.0) is None

    (axes,) = plot.figure.axes
    x, y = axes.transData.transform((first.start + 0.01, axes.get_ylim()[1] / 2))
    plot.canvas.callbacks.process(
        "motion_notify_event",
        MouseEvent("motion_notify_event", plot.canvas, x, y),
    )

    assert plot.tooltip_text.startswith(
        f"{first.start:.1f}-{first.end:.1f} s: {first.count} solve",
    )


def test_wheel_is_left_to_the_page(qtbot: QtBot) -> None:
    """The plot doesn't take wheel events, so the page around it scrolls."""
    plot = make_plot(qtbot, sample())
    event = QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 0),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,  # noqa: FBT003 - Qt's positional "inverted" flag
    )

    plot.canvas.wheelEvent(event)

    assert not event.isAccepted()
