"""Case images as Qt pixmaps, shared by the Learn page and the solve dialog."""

from dataclasses import dataclass
from functools import cache

from PySide6.QtGui import QPixmap

from cubetrainer.cases.catalog import Case, CaseKind
from cubetrainer.cube.render import RenderStyle, render_last_layer

_ORIENTATION = RenderStyle(arrows=False, orientation_only=True)

#: How each kind of case is drawn: what its step ignores is grey.
STYLES: dict[CaseKind, RenderStyle] = {
    CaseKind.PLL: RenderStyle(),
    CaseKind.EP: RenderStyle(),
    CaseKind.CP: RenderStyle(hide_edges=True),
    CaseKind.OLL: _ORIENTATION,
    CaseKind.CO: _ORIENTATION,
    CaseKind.EO: RenderStyle(arrows=False, orientation_only=True, hide_corners=True),
}

#: Images are rendered at this multiple of their size so they stay sharp on Retina.
RENDER_SCALE: int = 2


@cache
def case_pixmap(case: Case, size: int) -> QPixmap:
    """Render a case's last-layer image (cached: each case is drawn once per size).

    PLL images show the colours and arrows; OLL images show the U-colour pattern.
    2-look images grey out what their look ignores: the corners for edge orientation,
    the edges for corner permutation.

    Args:
        case: The case to draw.
        size: Width and height in logical pixels.

    Returns:
        A pixmap of ``size`` x ``size`` logical pixels, drawn at ``RENDER_SCALE``.

    """
    image = render_last_layer(case.state(), size * RENDER_SCALE, STYLES[case.kind])
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(RENDER_SCALE)
    return pixmap


@dataclass(frozen=True, slots=True)
class CaseInfo:
    """What the solve dialog shows about a trainer solve's case.

    Attributes:
        name: The case name.
        image: The case image.

    """

    name: str
    image: QPixmap
