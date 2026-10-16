"""Stats tab plots: a Q-Q check of the fit, and the progression of personal bests.

The Q-Q plot compares each time with the time the ex-Gaussian fit expects at the
same rank: points on the diagonal mean the model describes you well, points above it
at the right mean your slow solves are slower than the model expects. The records
plot shows every new best single and best ao5 over time.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, override

import numpy as np
from matplotlib.backend_bases import Event, MouseEvent
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter, date2num
from matplotlib.figure import Figure
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

from cubetrainer import stats
from cubetrainer.fits import MIN_FIT_SAMPLES, fit_ex_gaussian
from cubetrainer.formatting import format_average, format_value
from cubetrainer.ui.distribution_plots import (
    DATA_DARK,
    DATA_LIGHT,
    style_axes,
    title_axes,
)
from cubetrainer.ui.time_graph import DARK, GraphColors, current_colors

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from matplotlib.axes import Axes

    from cubetrainer.solves import Solve

#: Height of the plots, in logical pixels.
RECORD_PLOTS_HEIGHT: int = 320

#: Names of the record series, in palette slot order.
RECORD_KINDS: tuple[str, str] = ("single", "ao5")


class RecordPlots(QWidget):
    """Q-Q plot against the ex-Gaussian fit, next to the personal-best progression.

    Attributes:
        figure: The figure holding both plots.
        canvas: The matplotlib canvas.
        observed: Sorted finished times, in seconds.
        expected: The fitted time at each observed time's rank (empty without fit).
        records: New bests, by kind (``"single"``, ``"ao5"``): (time, value in ms,
            solve number).
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
        self.setFixedHeight(RECORD_PLOTS_HEIGHT)
        self.observed: np.ndarray = np.array([])
        self.expected: np.ndarray = np.array([])
        self.records: dict[str, list[tuple[datetime, float, int]]] = {}
        self._last_solve: datetime | None = None
        self.tooltip_text: str = ""
        self._qq: Axes | None = None
        self._progress: Axes | None = None
        box = QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.canvas)
        # Drawn on the first set_solves, not here: that keeps building the
        # (hidden) Stats tab cheap.

    def set_solves(self, solves: Sequence[Solve]) -> None:
        """Show the fit check and records of some solves.

        Args:
            solves: The solves, oldest first.

        """
        values = [solve.value for solve in solves]
        self.observed = np.sort([v / 1000 for v in values if math.isfinite(v)])
        fit = fit_ex_gaussian(self.observed)
        if fit is None:
            self.expected = np.array([])
        else:
            # Plotting positions (i - 0.5) / n: the share of solves below each rank.
            ranks = (np.arange(1, self.observed.size + 1) - 0.5) / self.observed.size
            self.expected = fit.ppf(ranks)
        self._last_solve = solves[-1].created_at if solves else None
        self.records = {
            kind: [
                (solves[index].created_at, value, index + 1)
                for index, value in stats.records(values, 1 if kind == "single" else 5)
            ]
            for kind in RECORD_KINDS
        }
        self._draw(current_colors())

    def _draw(self, colors: GraphColors) -> None:
        """Draw both plots.

        Args:
            colors: The appearance.

        """
        self.figure.clear()
        surface = self.palette().window().color().name()
        self.figure.set_facecolor(surface)
        qq, progress = self.figure.subplots(1, 2)
        self._qq, self._progress = qq, progress
        data = DATA_DARK if colors is DARK else DATA_LIGHT
        self._draw_qq(qq, colors, surface, data)
        self._draw_progress(progress, colors, surface)
        self.canvas.draw_idle()

    @staticmethod
    def _note(axes: Axes, text: str, colors: GraphColors) -> None:
        """Write a note in the middle of an empty plot.

        Args:
            axes: The plot.
            text: The note.
            colors: The appearance.

        """
        axes.set_xticks([])
        axes.set_yticks([])
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

    def _draw_qq(
        self,
        axes: Axes,
        colors: GraphColors,
        surface: str,
        data: str,
    ) -> None:
        """Draw observed against expected times, with the diagonal as reference.

        Args:
            axes: The plot.
            colors: The appearance.
            surface: Background colour.
            data: Colour of the points.

        """
        style_axes(axes, colors, surface)
        title_axes(axes, "Fit check: your times vs the model's", colors)
        if self.expected.size == 0:
            self._note(
                axes,
                f"Needs at least {MIN_FIT_SAMPLES} finished solves",
                colors,
            )
            return
        low = float(min(self.expected[0], self.observed[0]))
        high = float(max(self.expected[-1], self.observed[-1]))
        axes.plot(
            [low, high],
            [low, high],
            color=colors.series[0],
            linewidth=1.5,
            label="perfect fit",
        )
        axes.plot(
            self.expected,
            self.observed,
            linestyle="none",
            marker="o",
            markersize=4.5,
            markerfacecolor=data,
            markeredgecolor=surface,  # a thin ring keeps overlapping points apart
            markeredgewidth=0.3,
            label="your times",
        )
        axes.set_xlabel("expected (seconds)", color=colors.muted, fontsize=9)
        axes.set_ylabel("yours (seconds)", color=colors.muted, fontsize=9)
        legend = axes.legend(loc="upper left", frameon=False, fontsize=8)
        for text in legend.get_texts():
            text.set_color(colors.text)

    def _draw_progress(self, axes: Axes, colors: GraphColors, surface: str) -> None:
        """Draw the best single and best ao5 as steps over time.

        Args:
            axes: The plot.
            colors: The appearance.
            surface: Background colour.

        """
        style_axes(axes, colors, surface)
        title_axes(axes, "Personal bests over time", colors)
        if not self.records.get("single"):
            self._note(axes, "No finished solves yet", colors)
            return
        locator = AutoDateLocator()
        axes.xaxis.set_major_locator(locator)
        axes.xaxis.set_major_formatter(ConciseDateFormatter(locator))
        for kind, color in zip(RECORD_KINDS, colors.series, strict=False):
            found = self.records[kind]
            if not found:
                continue
            when = [date2num(moment) for moment, _value, _number in found]
            seconds = [value / 1000 for _moment, value, _number in found]
            # Carry the current best on to the latest solve: it still stands.
            if self._last_solve is not None and date2num(self._last_solve) > when[-1]:
                when.append(date2num(self._last_solve))
                seconds.append(seconds[-1])
            axes.step(
                when,
                seconds,
                where="post",
                color=color,
                linewidth=1.5,
                marker="o",
                markersize=4,
                markevery=list(range(len(found))),  # markers on the records only
                markeredgecolor=surface,
                label=f"best {kind}",
            )
        axes.set_ylabel("seconds", color=colors.muted, fontsize=9)
        legend = axes.legend(loc="upper right", frameon=False, fontsize=8)
        for text in legend.get_texts():
            text.set_color(colors.text)

    def describe_point(self, expected: float) -> str | None:
        """Describe the Q-Q point nearest an expected time.

        Args:
            expected: An expected time, in seconds.

        Returns:
            e.g. ``"yours 23.40 s, expected 21.90 s (at the 95% mark)"``, or None
            without a fit.

        """
        if self.expected.size == 0:
            return None
        index = int(np.argmin(np.abs(self.expected - expected)))
        percentile = round(100 * (index + 0.5) / self.expected.size)
        return (
            f"yours {self.observed[index]:.2f} s, expected {self.expected[index]:.2f} s"
            f" (at the {percentile}% mark)"
        )

    def describe_record(self, moment: float) -> str | None:
        """Describe the latest new best at or before a date.

        Args:
            moment: A date, as a matplotlib date number.

        Returns:
            e.g. ``"best single 11.82 (#263, 2026-10-02)"``, plus the ao5 if there is
            one; None before the first record.

        """
        parts: list[str] = []
        for kind in RECORD_KINDS:
            earlier = [
                r for r in self.records.get(kind, []) if date2num(r[0]) <= moment
            ]
            if earlier:
                when, value, number = earlier[-1]
                shown = (
                    format_value(value) if kind == "single" else format_average(value)
                )
                parts.append(f"best {kind} {shown} (#{number}, {when:%Y-%m-%d})")
        return "   ".join(parts) or None

    def _on_hover(self, event: Event) -> None:
        """Show the tooltip for the point or date under the mouse.

        Args:
            event: The mouse motion event.

        """
        if not isinstance(event, MouseEvent) or event.xdata is None:
            return
        text: str | None = None
        if event.inaxes is self._qq:
            text = self.describe_point(event.xdata)
        elif event.inaxes is self._progress:
            text = self.describe_record(event.xdata)
        self.tooltip_text = text or ""
        self.canvas.setToolTip(self.tooltip_text)

    def _on_leave(self, _event: Event) -> None:
        """Clear the tooltip when the mouse leaves a plot.

        Args:
            _event: The leave event (unused).

        """
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
