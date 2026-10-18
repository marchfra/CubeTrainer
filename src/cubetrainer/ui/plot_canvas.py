"""matplotlib canvases and plot widgets for plots inside scrolling pages."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from matplotlib.backend_bases import Event, MouseEvent
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, MaxNLocator
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget

from cubetrainer.ui.time_graph import current_colors

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from PySide6.QtGui import QResizeEvent, QWheelEvent

    from cubetrainer.ui.time_graph import GraphColors


#: Colour of the observed data (a neutral grey, cool like the theme's), for light
#: and dark mode.
DATA_LIGHT: str = "#a7acb8"
DATA_DARK: str = "#5f6677"


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


class PlotCanvas(FigureCanvasQTAgg):
    """A canvas that lets the scroll wheel scroll the page instead of the plot.

    matplotlib's canvas accepts every wheel event (for its own zoom and pan), so a
    page full of plots would stop scrolling whenever the pointer is over one. These
    plots don't zoom, so the wheel is passed on to the page.
    """

    def __init__(self, figure: Figure) -> None:
        """Create the canvas.

        Args:
            figure: The figure to show.

        """
        super().__init__(figure)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Leave the wheel to the scrolling page around the plot.

        Args:
            event: The wheel event.

        """
        event.ignore()


class PlotWidget(QWidget):
    """A plot on a canvas: hover tooltips, light/dark redraws, page scrolling.

    Subclasses implement ``draw`` (and optionally ``describe_at`` for tooltips) and
    call ``redraw`` when their data changes.

    Margins are fixed in pixels (``MARGINS``) rather than worked out by matplotlib's
    layout engine on every draw, which makes drawing about 40% faster.

    Attributes:
        figure: The figure.
        canvas: The canvas showing it.
        tooltip_text: The text of the hover tooltip ("" when not hovering).
        MARGINS: Space around the plots, in pixels: left, right, top, bottom.
        GAP: Horizontal space between side-by-side plots, as a fraction of a plot.

    """

    MARGINS: tuple[int, int, int, int] = (56, 14, 30, 42)
    GAP: float = 0.25

    def __init__(self, height: int, parent: QWidget | None = None) -> None:
        """Create the canvas (drawn when given data).

        Args:
            height: Height in logical pixels.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.figure: Figure = Figure()
        self.canvas: PlotCanvas = PlotCanvas(self.figure)
        self.canvas.mpl_connect("motion_notify_event", self._hover)
        self.canvas.mpl_connect("axes_leave_event", self._leave)
        self.tooltip_text: str = ""
        self.setFixedHeight(height)
        box = QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self.canvas)

    def draw(self, colors: GraphColors) -> None:
        """Draw the plot (subclasses implement this).

        Args:
            colors: The appearance.

        """

    def describe_at(self, axes: Axes, x: float, y: float) -> str | None:  # noqa: ARG002
        """Describe what's under the mouse (subclasses implement this).

        Args:
            axes: The plot under the mouse.
            x: The mouse position, in data units.
            y: The mouse position, in data units.

        Returns:
            The tooltip text, or None.

        """
        return None

    def _hover(self, event: Event) -> None:
        """Update the tooltip for the mouse position.

        Args:
            event: The mouse motion event.

        """
        if (
            not isinstance(event, MouseEvent)
            or event.inaxes is None
            or event.xdata is None
            or event.ydata is None
        ):
            return
        self.tooltip_text = (
            self.describe_at(event.inaxes, event.xdata, event.ydata) or ""
        )
        self.canvas.setToolTip(self.tooltip_text)

    def _leave(self, _event: Event) -> None:
        """Clear the tooltip when the mouse leaves a plot.

        Args:
            _event: The leave event (unused).

        """
        self.tooltip_text = ""
        self.canvas.setToolTip("")

    def redraw(self) -> None:
        """Draw with the current colours, on the window's background."""
        self.figure.clear()
        self.figure.set_facecolor(self.palette().window().color().name())
        self.draw(current_colors())
        self._apply_margins()
        self.canvas.draw_idle()

    def _apply_margins(self) -> None:
        """Convert the pixel margins to the figure's fractions at its current size."""
        width, height = self.canvas.width(), self.canvas.height()
        if width <= 0 or height <= 0:
            return
        left, right, top, bottom = self.MARGINS
        self.figure.subplots_adjust(
            left=min(left / width, 0.45),
            right=max(1 - right / width, 0.55),
            top=max(1 - top / height, 0.55),
            bottom=min(bottom / height, 0.45),
            wspace=self.GAP,
        )

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the margins the same number of pixels when the plot is resized.

        Args:
            event: The resize event.

        """
        super().resizeEvent(event)
        self._apply_margins()

    @override
    def changeEvent(self, event: QEvent) -> None:
        """Redraw with the right colours when the system switches light/dark mode.

        Args:
            event: The change event.

        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self.redraw()
