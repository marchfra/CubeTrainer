"""Stats tab plots: histogram of times with fitted curves, and the cumulative view.

The observed data is drawn in a neutral grey and the ex-Gaussian fit in categorical
slot 1 (validated in light and dark mode), so the data reads as the reference and
the fit stands out. Hovering a bar shows its range and
count; hovering the cumulative plot shows the share of solves under that time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

import numpy as np
from matplotlib.backend_bases import Event, MouseEvent
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator, PercentFormatter
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

from cubetrainer.fits import (
    MIN_FIT_SAMPLES,
    ExGaussianFit,
    empirical_cdf,
    fit_ex_gaussian,
)
from cubetrainer.ui.time_graph import DARK, GraphColors, current_colors

if TYPE_CHECKING:
    from collections.abc import Sequence

    from matplotlib.axes import Axes
    from matplotlib.lines import Line2D

#: Height of the plots, in logical pixels.
PLOTS_HEIGHT: int = 340

#: Most bars in the histogram.
_MAX_BINS: int = 40

#: Colour of the observed data (a neutral grey), for light and dark mode.
DATA_LIGHT: str = "#a9a7a0"
DATA_DARK: str = "#77756f"


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


def style_axes(axes: Axes, colors: GraphColors, surface: str) -> None:
    """Give a plot the recessive look: hairline grid, muted ticks, no box.

    Args:
        axes: The plot.
        colors: The appearance.
        surface: Background colour.

    """
    axes.set_facecolor(surface)
    for side in ("top", "right"):
        axes.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        axes.spines[side].set_color(colors.baseline)
    axes.tick_params(colors=colors.muted, labelsize=9, length=0)
    axes.grid(axis="y", color=colors.grid, linewidth=0.75)
    axes.set_axisbelow(True)
    axes.xaxis.set_major_locator(MaxNLocator(nbins=8))
    axes.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:g}"))


def title_axes(axes: Axes, text: str, colors: GraphColors) -> None:
    """Title a plot in the text ink.

    Args:
        axes: The plot.
        text: The title.
        colors: The appearance.

    """
    axes.set_title(text, loc="left", fontsize=10, color=colors.text)


class DistributionPlots(QWidget):
    """Histogram with the ex-Gaussian fit next to the cumulative distribution.

    Attributes:
        figure: The figure holding both plots.
        canvas: The matplotlib canvas.
        seconds: The finished times shown, in seconds.
        fit: The ex-Gaussian fit (None with too few times).
        bars: The histogram bars.
        tooltip_text: The text of the hover tooltip ("" when not hovering).

    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the (empty) plots.

        Args:
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.figure: Figure = Figure(layout="constrained")
        self.canvas: FigureCanvasQTAgg = FigureCanvasQTAgg(self.figure)
        self.canvas.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)
        self.canvas.mpl_connect("axes_leave_event", self._on_leave)
        self.setFixedHeight(PLOTS_HEIGHT)
        self.seconds: list[float] = []
        self.fit: ExGaussianFit | None = None
        self.bars: list[Bar] = []
        self.tooltip_text: str = ""
        self._histogram: Axes | None = None
        self._cumulative: Axes | None = None
        self._crosshair: Line2D | None = None
        box = QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.canvas)
        # Drawn on the first set_values, not here: that keeps building the
        # (hidden) Stats tab cheap.

    def set_values(self, values: Sequence[float]) -> None:
        """Show the distribution of some results.

        Args:
            values: Results in milliseconds (``math.inf`` for DNF; DNFs are left
                out, as they have no time).

        """
        self.seconds = [v / 1000 for v in values if math.isfinite(v)]
        self.fit = fit_ex_gaussian(self.seconds)
        self._draw(current_colors())

    def _draw(self, colors: GraphColors) -> None:
        """Draw both plots.

        Args:
            colors: The appearance.

        """
        self.figure.clear()
        surface = self.palette().window().color().name()
        self.figure.set_facecolor(surface)
        self._histogram = self._cumulative = None
        self._crosshair = None
        self.bars = []
        if len(self.seconds) < MIN_FIT_SAMPLES:
            self._draw_placeholder(colors, surface)
        else:
            histogram, cumulative = self.figure.subplots(1, 2)
            self._histogram, self._cumulative = histogram, cumulative
            data = DATA_DARK if colors is DARK else DATA_LIGHT
            self._draw_histogram(histogram, colors, surface, data)
            self._draw_cumulative(cumulative, colors, surface, data)
        self.canvas.draw_idle()

    def _draw_placeholder(self, colors: GraphColors, surface: str) -> None:
        """Say that there aren't enough solves yet.

        Args:
            colors: The appearance.
            surface: Background colour.

        """
        axes = self.figure.add_subplot()
        axes.set_facecolor(surface)
        axes.set_axis_off()
        axes.text(
            0.5,
            0.5,
            f"The distribution plots need at least {MIN_FIT_SAMPLES} finished solves",
            transform=axes.transAxes,
            ha="center",
            va="center",
            color=colors.muted,
            fontsize=10,
        )

    def _draw_histogram(
        self,
        axes: Axes,
        colors: GraphColors,
        surface: str,
        data: str,
    ) -> None:
        """Draw the histogram of times with the fitted densities.

        Args:
            axes: The plot.
            colors: The appearance.
            surface: Background colour (also the gap between bars).
            data: Colour of the bars.

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
            color=data,
            edgecolor=surface,  # a gap between neighbouring bars
            linewidth=1.5,
            label="your times",
        )
        raw, _ = np.histogram(times, bins=edges)
        self.bars = [
            Bar(float(a), float(b), int(n))
            for a, b, n in zip(edges[:-1], edges[1:], raw, strict=True)
        ]
        grid = np.linspace(edges[0], edges[-1], 300)
        if self.fit is not None:
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

    def _draw_cumulative(
        self,
        axes: Axes,
        colors: GraphColors,
        surface: str,
        data: str,
    ) -> None:
        """Draw the observed cumulative distribution with the fitted ones.

        Args:
            axes: The plot.
            colors: The appearance.
            surface: Background colour.
            data: Colour of the observed curve.

        """
        style_axes(axes, colors, surface)
        title_axes(axes, "Share of solves under a time", colors)
        times, shares = empirical_cdf(self.seconds)
        axes.step(
            times,
            shares,
            where="post",
            color=data,
            linewidth=2,
            label="your times",
        )
        grid = np.linspace(times[0], times[-1], 300)
        if self.fit is not None:
            axes.plot(
                grid,
                self.fit.cdf(grid),
                color=colors.series[0],
                linewidth=1.5,
                label="ex-Gaussian fit",
            )
        axes.set_ylim(0, 1)
        axes.yaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
        axes.set_xlabel("seconds", color=colors.muted, fontsize=9)
        legend = axes.legend(loc="lower right", frameon=False, fontsize=8)
        for text in legend.get_texts():
            text.set_color(colors.text)
        self._crosshair = axes.axvline(
            times[0],
            color=colors.muted,
            linewidth=0.75,
            visible=False,
        )

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

    def describe_share(self, seconds: float) -> str:
        """Describe the share of solves under a time.

        Args:
            seconds: A time.

        Returns:
            e.g. ``"under 18.00 s: 52% of solves"``.

        """
        under = sum(t < seconds for t in self.seconds)
        share = round(100 * under / len(self.seconds))
        return f"under {seconds:.2f} s: {share}% of solves"

    def _on_hover(self, event: Event) -> None:
        """Show the tooltip for the bar or the time under the mouse.

        Args:
            event: The mouse motion event.

        """
        if not isinstance(event, MouseEvent) or event.xdata is None:
            return
        text: str | None = None
        if event.inaxes is self._histogram:
            text = self.describe_bar(event.xdata)
        elif event.inaxes is self._cumulative and self._crosshair is not None:
            self._crosshair.set_xdata([event.xdata, event.xdata])
            self._crosshair.set_visible(True)
            text = self.describe_share(event.xdata)
            self.canvas.draw_idle()
        self.tooltip_text = text or ""
        self.canvas.setToolTip(self.tooltip_text)

    def _on_leave(self, _event: Event) -> None:
        """Hide the crosshair and tooltip when the mouse leaves a plot.

        Args:
            _event: The leave event (unused).

        """
        if self._crosshair is not None:
            self._crosshair.set_visible(False)
            self.canvas.draw_idle()
        self.tooltip_text = ""
        self.canvas.setToolTip("")

    @override
    def changeEvent(self, event: QEvent) -> None:
        """Redraw with the right colours when the system switches light/dark mode.

        Args:
            event: The change event.

        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._draw(current_colors())
