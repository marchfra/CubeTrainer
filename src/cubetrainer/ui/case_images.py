"""Case images as Qt pixmaps, shared by the Learn page and the solve dialog."""

from dataclasses import dataclass
from functools import cache

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QPixmap, QTransform

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
    """Draw a case's image (cached: each case look is drawn once per size).

    The image is the user's uploaded one if they chose one, otherwise it's generated
    from the algorithm: PLL images show the colours and arrows; OLL images the
    U-colour pattern; 2-look images grey out what their look ignores (the corners
    for edge orientation, the edges for corner permutation). The case's rotation is
    applied either way.

    Args:
        case: The case to draw.
        size: Width and height in logical pixels.

    Returns:
        A pixmap of ``size`` x ``size`` logical pixels, drawn at ``RENDER_SCALE``.

    """
    pixels = size * RENDER_SCALE
    image = _uploaded_image(case.image_path, pixels) if case.image_path else None
    if image is None:
        image = render_last_layer(case.state(), pixels, STYLES[case.kind])
    if case.rotation % 4:
        image = image.transformed(QTransform().rotate(90 * (case.rotation % 4)))
    pixmap = QPixmap.fromImage(image)
    pixmap.setDevicePixelRatio(RENDER_SCALE)
    return pixmap


def _uploaded_image(path: str, pixels: int) -> QImage | None:
    """Load a user's image, fitted inside a transparent square.

    Args:
        path: The image file.
        pixels: Side of the square in physical pixels.

    Returns:
        The fitted image, or None if the file can't be read as an image.

    """
    source = QImage(path)
    if source.isNull():
        return None
    scaled = source.scaled(
        pixels,
        pixels,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    square = QImage(pixels, pixels, QImage.Format.Format_ARGB32_Premultiplied)
    square.fill(Qt.GlobalColor.transparent)
    painter = QPainter(square)
    painter.drawImage(
        (pixels - scaled.width()) // 2,
        (pixels - scaled.height()) // 2,
        scaled,
    )
    painter.end()
    return square


@dataclass(frozen=True, slots=True)
class CaseInfo:
    """What the solve dialog shows about a trainer solve's case.

    Attributes:
        name: The case name.
        image: The case image.

    """

    name: str
    image: QPixmap
