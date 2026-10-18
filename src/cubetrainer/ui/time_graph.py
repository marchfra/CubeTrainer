"""cstimer-style graph of a session's times, with rolling ao5 and ao12.

Colours follow the data-viz palette: three categorical slots (validated for every
pair in light and dark mode), recessive axes and gridlines, text in ink colours,
and a legend naming the lines. Hovering shows a crosshair and the values at that
solve.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, override

from matplotlib.backend_bases import Event, MouseEvent
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from cubetrainer import stats
from cubetrainer.formatting import format_average, format_solve
from cubetrainer.ui.chart_style import GRAPH_HEIGHT, GraphColors, current_colors

if TYPE_CHECKING:
    from matplotlib.lines import Line2D

    from cubetrainer.solves import SolveList

#: Fewest solves worth drawing a line for.
_MIN_SOLVES: int = 2

#: Names of the three lines, in slot order.
SERIES_NAMES: tuple[str, str, str] = ("single", "ao5", "ao12")


def _seconds(value: float | None) -> float:
    """Convert a statistic to seconds for plotting; gaps for missing or DNF.

    Args:
        value: Milliseconds, ``math.inf`` for DNF, or None.

    Returns:
        Seconds, or NaN (drawn as a gap).

    """
    if value is None or math.isinf(value):
        return math.nan
    return value / 1000


def _time_label(seconds: float, _position: float) -> str:
    """Format a y-axis tick as a time.

    Args:
        seconds: The tick value.
        _position: The tick position (unused).

    Returns:
        e.g. ``"12"`` or ``"1:05"``.

    """
    if seconds >= 60:  # noqa: PLR2004 - one minute
        return f"{int(seconds // 60)}:{int(seconds % 60):02d}"
    return f"{seconds:g}"


class TimeGraph(QWidget):
    """Line graph of single times, ao5 and ao12 over the session's solves.

    Attributes:
        canvas: The matplotlib canvas.
        figure: The figure drawn on the canvas.
        series: The plotted values in seconds (NaN for gaps), by series name.

    """

    def __init__(self, solves: SolveList, parent: QWidget | None = None) -> None:
        """Create the graph.

        Args:
            solves: The session's solves (call ``refresh`` after changes).
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self._solves: SolveList = solves
        self.figure: Figure = Figure(layout="constrained")
        self.canvas: FigureCanvasQTAgg = FigureCanvasQTAgg(self.figure)
        self.canvas.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)
        self.canvas.mpl_connect("axes_leave_event", self._on_leave)
        self.setFixedHeight(GRAPH_HEIGHT)
        self.series: dict[str, list[float]] = {}
        self._crosshair: Line2D | None = None
        self._tooltip_text: str = ""

        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.canvas)
        self.refresh()

    def set_solves(self, solves: SolveList) -> None:
        """Show another session's solves.

        Args:
            solves: The new list.

        """
        self._solves = solves
        self.refresh()

    def refresh(self) -> None:
        """Recompute the series and redraw the graph."""
        values = self._solves.values()
        self.series = {
            "single": [_seconds(v) for v in values],
            "ao5": [_seconds(v) for v in stats.rolling_averages(values, 5)],
            "ao12": [_seconds(v) for v in stats.rolling_averages(values, 12)],
        }
        self._draw(current_colors())

    @property
    def tooltip_text(self) -> str:
        """The text of the hover tooltip ("" when not hovering)."""
        return self._tooltip_text

    def _draw(self, colors: GraphColors) -> None:
        """Draw every series, the axes, the legend and the direct labels.

        Args:
            colors: The appearance to draw with.

        """
        self.figure.clear()
        # The window's own colour, so the graph sits flush in the page.
        surface = self.palette().window().color().name()
        self.figure.set_facecolor(surface)
        axes = self.figure.add_subplot()
        axes.set_facecolor(surface)
        for side in ("top", "right"):
            axes.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            axes.spines[side].set_color(colors.baseline)
        axes.tick_params(colors=colors.muted, labelsize=9, length=0)
        axes.grid(axis="y", color=colors.grid, linewidth=0.75)
        axes.set_axisbelow(True)
        axes.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=8))
        axes.yaxis.set_major_locator(MaxNLocator(nbins=4))
        axes.yaxis.set_major_formatter(FuncFormatter(_time_label))
        self._crosshair = None

        count = len(self.series["single"])
        if count < _MIN_SOLVES:
            axes.set_xticks([])
            axes.set_yticks([])
            axes.text(
                0.5,
                0.5,
                "The graph appears after a couple of solves",
                transform=axes.transAxes,
                ha="center",
                va="center",
                color=colors.muted,
                fontsize=10,
            )
            self.canvas.draw_idle()
            return

        numbers = list(range(1, count + 1))
        for name, color in zip(SERIES_NAMES, colors.series, strict=True):
            points = self.series[name]
            # 2 px lines; the singles a little lighter so the averages read on top.
            axes.plot(
                numbers,
                points,
                color=color,
                linewidth=1.5,
                alpha=0.55 if name == "single" else 1.0,
                label=name,
                solid_capstyle="round",
            )
        axes.set_xlim(1, max(count, 2))
        # Above the plot, so it never covers the lines.
        legend = axes.legend(
            loc="lower left",
            bbox_to_anchor=(0, 1),
            ncols=3,
            frameon=False,
            fontsize=8,
            handlelength=1.5,
            borderaxespad=0,
        )
        for text in legend.get_texts():
            text.set_color(colors.text)
        self._crosshair = axes.axvline(
            1,
            color=colors.muted,
            linewidth=0.75,
            visible=False,
        )
        self.canvas.draw_idle()

    def describe(self, number: int) -> str:
        """Describe one solve and the averages ending at it, for the tooltip.

        Args:
            number: The solve's 1-based number.

        Returns:
            e.g. ``"#12   12.34   ao5 11.61   ao12 -"``.

        """
        index = number - 1
        values = self._solves.values()
        ao5 = stats.rolling_averages(values, 5)[index]
        ao12 = stats.rolling_averages(values, 12)[index]
        single = format_solve(self._solves.solves[index])
        return (
            f"#{number}   {single}   ao5 {format_average(ao5)}"
            f"   ao12 {format_average(ao12)}"
        )

    def _on_hover(self, event: Event) -> None:
        """Move the crosshair to the nearest solve and show its values.

        Args:
            event: The mouse motion event.

        """
        if (
            not isinstance(event, MouseEvent)
            or event.inaxes is None
            or event.xdata is None
            or self._crosshair is None
        ):
            return
        count = len(self.series["single"])
        number = min(max(round(event.xdata), 1), count)
        self._crosshair.set_xdata([number, number])
        self._crosshair.set_visible(True)
        self._tooltip_text = self.describe(number)
        self.canvas.setToolTip(self._tooltip_text)
        self.canvas.draw_idle()

    def _on_leave(self, _event: Event) -> None:
        """Hide the crosshair when the mouse leaves the plot.

        Args:
            _event: The leave event (unused).

        """
        if self._crosshair is not None:
            self._crosshair.set_visible(False)
        self._tooltip_text = ""
        self.canvas.setToolTip("")
        self.canvas.draw_idle()

    @override
    def changeEvent(self, event: QEvent) -> None:
        """Redraw with the right colours when the system switches light/dark mode.

        Args:
            event: The change event.

        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._draw(current_colors())
