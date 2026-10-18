"""Chart colours and sizes, kept apart from matplotlib so they load quickly.

Every chart (the time graph and the Stats tab's plots) takes its colours from here;
the slots were validated for colour-blind separation and contrast against the
theme's light and dark backgrounds.
"""

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

#: Height of the graph, in logical pixels.
GRAPH_HEIGHT: int = 190


@dataclass(frozen=True, slots=True)
class GraphColors:
    """The colours of one appearance (light or dark).

    Attributes:
        surface: Typical window colour the palette was validated against (the graph
            draws on the actual window colour).
        series: Line colours for single, ao5 and ao12 (categorical slots 1-3).
        text: Primary ink, for labels.
        muted: Muted ink, for axes and tick labels.
        grid: Gridline hairlines.
        baseline: Axis lines.

    """

    surface: str
    series: tuple[str, str, str]
    text: str
    muted: str
    grid: str
    baseline: str


# The Calm theme's colours: the first series is its violet accent, then amber and
# teal; validated (lightness, chroma, colour-blind separation, contrast) against
# its backgrounds, #f3f4f7 light and #0e1014 dark. Neutrals are its greys.
LIGHT: GraphColors = GraphColors(
    surface="#f3f4f7",
    series=("#6b5cf0", "#d97a2b", "#0f9d8f"),
    text="#3d4250",
    muted="#6a7184",
    grid="#e2e5eb",
    baseline="#cfd3dc",
)

DARK: GraphColors = GraphColors(
    surface="#0e1014",
    series=("#8c7dff", "#c8753a", "#22a493"),
    text="#c3c7d0",
    muted="#8b92a3",
    grid="#1e222b",
    baseline="#343a48",
)


def current_colors() -> GraphColors:
    """Return the colours for the app's current appearance.

    Returns:
        ``DARK`` when the system uses dark mode, else ``LIGHT``.

    """
    hints = QGuiApplication.styleHints()
    return DARK if hints.colorScheme() == Qt.ColorScheme.Dark else LIGHT
