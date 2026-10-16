"""Stats tab plot: the progression of personal bests over time.

Every new best single and best ao5 is a step down, with a dot at each record; the
lines carry on to the latest solve, so it's clear how long a record has stood.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from matplotlib.dates import AutoDateLocator, ConciseDateFormatter, date2num

from cubetrainer import stats
from cubetrainer.formatting import format_average, format_value
from cubetrainer.ui.plot_canvas import PlotWidget, style_axes, title_axes

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from matplotlib.axes import Axes
    from PySide6.QtWidgets import QWidget

    from cubetrainer.solves import Solve
    from cubetrainer.ui.time_graph import GraphColors

#: Height of the plot, in logical pixels.
RECORD_PLOTS_HEIGHT: int = 320

#: Names of the record series, in palette slot order.
RECORD_KINDS: tuple[str, str] = ("single", "ao5")


class RecordsPlot(PlotWidget):
    """Best single and best ao5 as steps over time.

    Attributes:
        records: New bests, by kind (``"single"``, ``"ao5"``): (time, value in ms,
            solve number).

    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the (empty) plot; it's drawn on the first ``set_solves``.

        Args:
            parent: Optional parent widget.

        """
        super().__init__(RECORD_PLOTS_HEIGHT, parent)
        self.records: dict[str, list[tuple[datetime, float, int]]] = {}
        self._last_solve: datetime | None = None

    def set_solves(self, solves: Sequence[Solve]) -> None:
        """Show the records of some solves.

        Args:
            solves: The solves, oldest first.

        """
        values = [solve.value for solve in solves]
        self._last_solve = solves[-1].created_at if solves else None
        self.records = {
            kind: [
                (solves[index].created_at, value, index + 1)
                for index, value in stats.records(values, 1 if kind == "single" else 5)
            ]
            for kind in RECORD_KINDS
        }
        self.redraw()

    @override
    def draw(self, colors: GraphColors) -> None:
        """Draw the record steps, or a note without finished solves.

        Args:
            colors: The appearance.

        """
        axes = self.figure.add_subplot()
        surface = self.palette().window().color().name()
        style_axes(axes, colors, surface)
        title_axes(axes, "Personal bests over time", colors)
        if not self.records.get("single"):
            axes.set_xticks([])
            axes.set_yticks([])
            axes.text(
                0.5,
                0.5,
                "No finished solves yet",
                transform=axes.transAxes,
                ha="center",
                va="center",
                color=colors.muted,
                fontsize=10,
            )
            return
        self._draw_steps(axes, colors, surface)

    def _draw_steps(self, axes: Axes, colors: GraphColors, surface: str) -> None:
        """Draw one step line per record kind.

        Args:
            axes: The plot.
            colors: The appearance.
            surface: Background colour (rings around the markers).

        """
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

    def describe_record(self, moment: float) -> str | None:
        """Describe the bests standing at a date.

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

    @override
    def describe_at(self, axes: Axes, x: float, y: float) -> str | None:
        """Describe the bests standing at the date under the mouse.

        Args:
            axes: The plot (unused: there is one).
            x: Date under the mouse, as a matplotlib date number.
            y: Time under the mouse (unused).

        Returns:
            The records' description, or None.

        """
        del axes, y
        return self.describe_record(x)
