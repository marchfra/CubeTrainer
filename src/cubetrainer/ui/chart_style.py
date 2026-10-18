"""Chart colours and sizes, kept apart from matplotlib so they load quickly.

Every chart (the time graph and the Stats tab's plots) takes its colours from here,
for the theme and light/dark mode in use. Each theme's series are its accent, then
two contrasting hues, validated (lightness, chroma, colour-blind separation,
contrast) against that theme's background.
"""

from dataclasses import dataclass

from cubetrainer.ui import theme

#: Height of the graph, in logical pixels.
GRAPH_HEIGHT: int = 190


@dataclass(frozen=True, slots=True)
class GraphColors:
    """The colours of one appearance (light or dark) of a theme's charts.

    Attributes:
        surface: The background the series were validated against (charts draw on
            the actual window colour).
        series: Line colours for single, ao5 and ao12 (categorical slots 1-3).
        text: Primary ink, for labels.
        muted: Muted ink, for axes and tick labels.
        grid: Gridline hairlines.
        baseline: Axis lines.
        data: Neutral grey for observed data (histogram bars, plain points).

    """

    surface: str
    series: tuple[str, str, str]
    text: str
    muted: str
    grid: str
    baseline: str
    data: str


# Calm: violet accent, amber, teal.
LIGHT: GraphColors = GraphColors(
    surface="#f3f4f7",
    series=("#6b5cf0", "#d97a2b", "#0f9d8f"),
    text="#3d4250",
    muted="#6a7184",
    grid="#e2e5eb",
    baseline="#cfd3dc",
    data="#a7acb8",
)

DARK: GraphColors = GraphColors(
    surface="#0e1014",
    series=("#8c7dff", "#c8753a", "#22a493"),
    text="#c3c7d0",
    muted="#8b92a3",
    grid="#1e222b",
    baseline="#343a48",
    data="#5f6677",
)

#: Light and dark chart colours of each theme, by theme name.
CHART_COLORS: dict[str, tuple[GraphColors, GraphColors]] = {
    "Calm": (LIGHT, DARK),
    # Clean: system blue, orange, teal.
    "Clean": (
        GraphColors(
            surface="#ffffff",
            series=("#0071e3", "#d9772a", "#0f9d8f"),
            text="#3a3a3c",
            muted="#6e6e73",
            grid="#ececee",
            baseline="#d2d2d7",
            data="#b0b0b5",
        ),
        GraphColors(
            surface="#1e1e1e",
            series=("#2b8cff", "#c8742e", "#22a493"),
            text="#d1d1d6",
            muted="#98989d",
            grid="#2c2c2e",
            baseline="#48484a",
            data="#636366",
        ),
    ),
    # Bold: cobalt accent, coral, teal.
    "Bold": (
        GraphColors(
            surface="#eceef2",
            series=("#2f4bff", "#dd5a35", "#00957f"),
            text="#2b2e38",
            muted="#646a78",
            grid="#dfe2e8",
            baseline="#cfd3dc",
            data="#a3a8b5",
        ),
        GraphColors(
            surface="#0b0c10",
            series=("#5b74ff", "#cf6a3c", "#1f9a8a"),
            text="#c9ccd6",
            muted="#8a90a0",
            grid="#1f222b",
            baseline="#343845",
            data="#5a6070",
        ),
    ),
}


def current_colors() -> GraphColors:
    """Return the chart colours for the theme and light/dark mode in use.

    Returns:
        The colours (Calm's for a theme without its own).

    """
    light, dark = CHART_COLORS.get(theme.CURRENT.name, (LIGHT, DARK))
    return dark if theme.is_dark() else light
