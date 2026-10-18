"""Stats tab plots: the learning curve, and (for trainers) which cases to drill.

The learning curve shows every time against its solve number, a fitted exponential
trend, its projection forward and the plateau it levels off at. The case charts
are small multiples sharing the case axis: mean time, mistake rate and hint use,
slowest cases first, each in its own chart (never two scales on one axis).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

import numpy as np
from matplotlib.ticker import MaxNLocator, PercentFormatter

from cubetrainer import stats
from cubetrainer.fits import MIN_CURVE_SAMPLES, LearningCurve, fit_learning_curve
from cubetrainer.formatting import format_percent
from cubetrainer.ui.plot_canvas import (
    PlotWidget,
    style_axes,
    title_axes,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from matplotlib.axes import Axes
    from PySide6.QtWidgets import QWidget

    from cubetrainer.solves import Solve
    from cubetrainer.ui.chart_style import GraphColors

#: Height of the learning curve, in logical pixels.
CURVE_HEIGHT: int = 300

#: How far ahead the trend is projected, as a fraction of the solves so far.
PROJECTION: float = 0.5

#: Most cases shown in the case charts (the slowest ones).
MAX_CASES: int = 15


def _note(axes: Axes, text: str, colors: GraphColors) -> None:
    """Write a note in the middle of an empty plot.

    Args:
        axes: The plot.
        text: The note.
        colors: The appearance.

    """
    axes.set_axis_off()
    axes.text(
        0.5,
        0.5,
        text,
        transform=axes.transAxes,
        ha="center",
        va="center",
        color=colors.muted,
        fontsize=10,
    )


class LearningCurvePlot(PlotWidget):
    """Times by solve number with the fitted learning curve and its plateau.

    Attributes:
        seconds: The finished times shown, oldest first, in seconds.
        numbers: Their solve numbers (1-based, counting DNFs).
        curve: The fitted learning curve, or None.

    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the (empty) plot.

        Args:
            parent: Optional parent widget.

        """
        super().__init__(CURVE_HEIGHT, parent)
        self.seconds: list[float] = []
        self.numbers: list[int] = []
        self.curve: LearningCurve | None = None

    def set_values(self, values: Sequence[float]) -> None:
        """Show the learning curve of some results.

        Args:
            values: Results in milliseconds, oldest first (``math.inf`` for DNF).

        """
        finished = [(i + 1, v / 1000) for i, v in enumerate(values) if math.isfinite(v)]
        self.numbers = [n for n, _ in finished]
        self.seconds = [s for _, s in finished]
        self.curve = fit_learning_curve(self.seconds)
        self.redraw()

    def summary(self) -> str:
        """Describe the trend in one line, for the title.

        Returns:
            e.g. ``"levelling off at 18.21 s; the gap halves every 39 solves"``.

        """
        if self.curve is None:
            return ""
        if not self.curve.improving:
            return "no clear improvement"
        return (
            f"levelling off at {self.curve.plateau:.2f} s;"
            f" the gap halves every {round(self.curve.half_life)} solves"
        )

    @override
    def draw(self, colors: GraphColors) -> None:
        """Draw the times, the trend, its projection and the plateau.

        Args:
            colors: The appearance.

        """
        axes = self.figure.add_subplot()
        surface = self.palette().window().color().name()
        style_axes(axes, colors, surface)
        if self.curve is None:
            _note(
                axes,
                f"The learning curve needs {MIN_CURVE_SAMPLES} finished solves",
                colors,
            )
            return
        title_axes(axes, f"Learning curve: {self.summary()}", colors)
        data = colors.data
        axes.plot(
            self.numbers,
            self.seconds,
            linestyle="none",
            marker="o",
            markersize=3.5,
            markerfacecolor=data,
            markeredgewidth=0,
            alpha=0.7,
            label="your times",
        )
        last = self.numbers[-1]
        fitted = np.linspace(1, last, 300)
        ahead = np.linspace(last, last * (1 + PROJECTION), 100)
        trend = colors.series[0]
        axes.plot(
            fitted,
            self.curve.at(fitted - 1),
            color=trend,
            linewidth=2,
            label="trend",
        )
        axes.plot(
            ahead,
            self.curve.at(ahead - 1),
            color=trend,
            linewidth=2,
            linestyle=(0, (4, 3)),
            label="projection",
        )
        if self.curve.improving:
            axes.axhline(
                self.curve.plateau,
                color=colors.muted,
                linewidth=1,
                linestyle=(0, (1, 2)),
                label=f"plateau {self.curve.plateau:.2f} s",
            )
        axes.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
        axes.set_xlabel("solve number", color=colors.muted, fontsize=9)
        axes.set_ylabel("seconds", color=colors.muted, fontsize=9)
        legend = axes.legend(loc="upper right", frameon=False, fontsize=8)
        for text in legend.get_texts():
            text.set_color(colors.text)

    @override
    def describe_at(self, axes: Axes, x: float, y: float) -> str | None:
        """Describe the solve nearest the mouse and the trend there.

        Args:
            axes: The plot under the mouse (unused: there is one).
            x: Solve number under the mouse.
            y: Time under the mouse (unused).

        Returns:
            e.g. ``"#120  17.32 s  (trend 19.10 s)"``, or None without a curve.

        """
        del axes, y
        if self.curve is None or not self.numbers:
            return None
        index = int(np.argmin(np.abs(np.array(self.numbers) - x)))
        number = self.numbers[index]
        trend = float(self.curve.at(np.array([number - 1.0]))[0])
        return f"#{number}  {self.seconds[index]:.2f} s  (trend {trend:.2f} s)"


@dataclass(frozen=True, slots=True)
class CaseRow:
    """One case in the case charts.

    Attributes:
        name: The case name.
        stats: The case's statistics.

    """

    name: str
    stats: stats.CaseStats


class CaseCharts(PlotWidget):
    """Mean time, mistake rate and hint use of the slowest cases, side by side.

    Attributes:
        rows: The cases shown, slowest first.

    """

    # Room for the case names on the left and the suptitle on top.
    MARGINS: tuple[int, int, int, int] = (60, 14, 52, 30)
    GAP: float = 0.12

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the (empty) charts.

        Args:
            parent: Optional parent widget.

        """
        super().__init__(120, parent)
        self.rows: list[CaseRow] = []

    def set_solves(
        self,
        solves: Sequence[Solve],
        case_name: Callable[[str], str],
    ) -> None:
        """Show the slowest cases among some trainer solves.

        Args:
            solves: Trainer solves, mistakes included (they make the mistake rate).
            case_name: Display name of a case id.

        """
        by_case = stats.case_stats(solves)
        ranked = sorted(
            by_case.items(),
            key=lambda item: -math.inf if item[1].mean is None else item[1].mean,
            reverse=True,
        )
        self.rows = [CaseRow(case_name(cid), case) for cid, case in ranked[:MAX_CASES]]
        self.setFixedHeight(80 + 24 * max(len(self.rows), 2))
        self.redraw()

    @override
    def draw(self, colors: GraphColors) -> None:
        """Draw the three charts (or a note without solves).

        Args:
            colors: The appearance.

        """
        surface = self.palette().window().color().name()
        if not self.rows:
            axes = self.figure.add_subplot()
            axes.set_facecolor(surface)
            _note(axes, "No trainer solves yet", colors)
            return
        names = [row.name for row in self.rows]
        positions = np.arange(len(self.rows))
        measures: list[tuple[str, list[float], bool]] = [
            ("mean time (s)", [(r.stats.mean or 0) / 1000 for r in self.rows], False),
            ("mistakes", [r.stats.mistake_rate for r in self.rows], True),
            ("hints used", [r.stats.hint_rate for r in self.rows], True),
        ]
        charts = self.figure.subplots(1, 3, sharey=True)
        for chart, (title, values, percent) in zip(charts, measures, strict=True):
            style_axes(chart, colors, surface)
            chart.grid(axis="y", visible=False)
            chart.grid(axis="x", color=colors.grid, linewidth=0.75)
            title_axes(chart, title, colors)
            chart.barh(positions, values, color=colors.series[0], height=0.7)
            if percent:
                chart.set_xlim(0, max(0.05, *values) * 1.1)
                chart.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
            chart.xaxis.set_major_locator(MaxNLocator(nbins=4))
        charts[0].set_yticks(positions, names)
        charts[0].invert_yaxis()  # slowest at the top
        if len(self.rows) == MAX_CASES:
            self.figure.suptitle(
                f"The {MAX_CASES} slowest cases",
                x=0.0,
                ha="left",
                fontsize=10,
                color=colors.text,
            )

    @override
    def describe_at(self, axes: Axes, x: float, y: float) -> str | None:
        """Describe the case under the mouse.

        Args:
            axes: The chart under the mouse (unused: all share the case axis).
            x: Value under the mouse (unused).
            y: Case position under the mouse.

        Returns:
            e.g. ``"T: mean 2.31 s · mistakes 12% · hints 30% (25 solves)"``.

        """
        del axes, x
        index = round(y)
        if not 0 <= index < len(self.rows):
            return None
        row = self.rows[index]
        mean = "-" if row.stats.mean is None else f"{row.stats.mean / 1000:.2f} s"
        return (
            f"{row.name}: mean {mean}"
            f" · mistakes {format_percent(row.stats.mistake_rate)}"
            f" · hints {format_percent(row.stats.hint_rate)} ({row.stats.count} solves)"
        )
