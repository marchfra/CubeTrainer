"""Stats tab plot: histogram of times with the fitted ex-Gaussian curve.

The observed data is drawn in a neutral grey and the fit in categorical slot 1
(validated in light and dark mode), so the data reads as the reference and the fit
stands out. Hovering a bar shows its range and count.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

import numpy as np

from cubetrainer.fits import MIN_FIT_SAMPLES, ExGaussianFit, fit_ex_gaussian
from cubetrainer.ui.plot_canvas import (
    DATA_DARK,
    DATA_LIGHT,
    PlotWidget,
    style_axes,
    title_axes,
)
from cubetrainer.ui.time_graph import DARK, GraphColors

if TYPE_CHECKING:
    from collections.abc import Sequence

    from matplotlib.axes import Axes
    from PySide6.QtWidgets import QWidget

#: Height of the plot, in logical pixels.
PLOTS_HEIGHT: int = 320

#: Most bars in the histogram.
_MAX_BINS: int = 40


@dataclass(frozen=True, slots=True)
class Bar:
    """One histogram bar, for the hover tooltip.

    Attributes:
        start: Left edge, in seconds.
        end: Right edge, in seconds.
        count: Number of solves in it.

    """

    start: float
    end: float
    count: int


class HistogramPlot(PlotWidget):
    """Histogram of times with the ex-Gaussian fit.

    Attributes:
        seconds: The finished times shown, in seconds.
        fit: The ex-Gaussian fit (None with too few times).
        bars: The histogram bars.

    """

    # No y axis (the density's scale means nothing to read), so a narrow left edge.
    MARGINS: tuple[int, int, int, int] = (16, 14, 30, 42)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the (empty) plot; it's drawn on the first ``set_values``.

        Args:
            parent: Optional parent widget.

        """
        super().__init__(PLOTS_HEIGHT, parent)
        self.seconds: list[float] = []
        self.fit: ExGaussianFit | None = None
        self.bars: list[Bar] = []

    def set_values(self, values: Sequence[float]) -> None:
        """Show the distribution of some results.

        Args:
            values: Results in milliseconds (``math.inf`` for DNF; DNFs are left
                out, as they have no time).

        """
        self.seconds = [v / 1000 for v in values if math.isfinite(v)]
        self.fit = fit_ex_gaussian(self.seconds)
        self.redraw()

    @override
    def draw(self, colors: GraphColors) -> None:
        """Draw the histogram and the fitted density, or a note with few solves.

        Args:
            colors: The appearance.

        """
        axes = self.figure.add_subplot()
        surface = self.palette().window().color().name()
        self.bars = []
        if len(self.seconds) < MIN_FIT_SAMPLES:
            axes.set_facecolor(surface)
            axes.set_axis_off()
            axes.text(
                0.5,
                0.5,
                f"The distribution needs at least {MIN_FIT_SAMPLES} finished solves",
                transform=axes.transAxes,
                ha="center",
                va="center",
                color=colors.muted,
                fontsize=10,
            )
            return
        self._draw_histogram(axes, colors, surface)

    def _draw_histogram(self, axes: Axes, colors: GraphColors, surface: str) -> None:
        """Draw the bars and the fitted density.

        Args:
            axes: The plot.
            colors: The appearance.
            surface: Background colour (also the gap between bars).

        """
        style_axes(axes, colors, surface)
        title_axes(axes, "Distribution of times", colors)
        times = np.array(self.seconds)
        edges = np.histogram_bin_edges(times, bins="fd")
        if edges.size - 1 > _MAX_BINS:
            edges = np.histogram_bin_edges(times, bins=_MAX_BINS)
        axes.hist(
            times,
            bins=edges.tolist(),
            density=True,
            color=DATA_DARK if colors is DARK else DATA_LIGHT,
            edgecolor=surface,  # a gap between neighbouring bars
            linewidth=1.5,
            label="your times",
        )
        raw, _ = np.histogram(times, bins=edges)
        self.bars = [
            Bar(float(a), float(b), int(n))
            for a, b, n in zip(edges[:-1], edges[1:], raw, strict=True)
        ]
        if self.fit is not None:
            grid = np.linspace(edges[0], edges[-1], 300)
            axes.plot(
                grid,
                self.fit.pdf(grid),
                color=colors.series[0],
                linewidth=1.5,
                label="ex-Gaussian fit",
            )
        axes.set_yticks([])
        axes.spines["left"].set_visible(False)
        axes.set_xlabel("seconds", color=colors.muted, fontsize=9)
        legend = axes.legend(loc="upper right", frameon=False, fontsize=8)
        for text in legend.get_texts():
            text.set_color(colors.text)

    def describe_bar(self, seconds: float) -> str | None:
        """Describe the histogram bar containing a time.

        Args:
            seconds: A time.

        Returns:
            e.g. ``"15.0-15.5 s: 23 solves (6%)"``, or None outside the bars.

        """
        for bar in self.bars:
            if bar.start <= seconds <= bar.end:
                share = round(100 * bar.count / len(self.seconds))
                noun = "solve" if bar.count == 1 else "solves"
                return f"{bar.start:.1f}-{bar.end:.1f} s: {bar.count} {noun} ({share}%)"
        return None

    @override
    def describe_at(self, axes: Axes, x: float, y: float) -> str | None:
        """Describe the bar under the mouse.

        Args:
            axes: The plot (unused: there is one).
            x: Time under the mouse.
            y: Height under the mouse (unused).

        Returns:
            The bar's description, or None.

        """
        del axes, y
        return self.describe_bar(x)
