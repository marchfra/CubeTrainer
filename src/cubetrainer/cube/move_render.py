"""Draw a small picture of a move: the cube from above-front-right, with arrows.

The cube is drawn solved, in isometric view (U, F and R faces showing). The stickers
on the layers the move turns keep their colours and the rest are greyed out;
arrows along the turned strips show which way the stickers go. Every move's layers
show on these three faces, so even D, L, B and the slices are visible.
"""

import math

from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

from cubetrainer.cube.model import (
    FACE_NORMALS,
    FACES,
    STICKERS,
    move_axis,
    turned_stickers,
)
from cubetrainer.cube.render import COLOR_SCHEME, INK_COLOR

type Point3 = tuple[float, float, float]

#: Colour of the stickers the move leaves where they are.
STILL_COLOR: str = "#d6d6d6"

#: The faces the isometric view shows.
VISIBLE_FACES: tuple[str, ...] = ("U", "F", "R")

_COS30: float = math.cos(math.pi / 6)
_STICKER_HALF: float = 0.44  # half a sticker's side (cells are 1 wide)
_ARROW_HALF: float = 1.15  # half an arrow's length along its strip
_HEAD: float = 0.38  # arrowhead length
_EXTENT: tuple[float, float] = (3 * _COS30, 3.0)  # half width and height of the cube


def _project(point: Point3) -> QPointF:
    """Project a point in cube coordinates to the isometric drawing plane.

    Args:
        point: (x, y, z), with x towards R, y towards U and z towards F.

    Returns:
        The point in the drawing, y pointing down.

    """
    x, y, z = point
    return QPointF((x - z) * _COS30, -y + (x + z) * 0.5)


def _add(a: Point3, b: Point3, scale: float = 1.0) -> Point3:
    """Return ``a + scale * b``.

    Args:
        a: A point.
        b: A vector.
        scale: How much of ``b`` to add.

    Returns:
        The sum.

    """
    return (a[0] + scale * b[0], a[1] + scale * b[1], a[2] + scale * b[2])


def _face_axes(normal: tuple[int, int, int]) -> tuple[Point3, Point3]:
    """Return two unit vectors spanning a face.

    Args:
        normal: The face's outward normal.

    Returns:
        The two coordinate axes the normal isn't along.

    """
    units: list[Point3] = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    first, second = (u for u, n in zip(units, normal, strict=True) if n == 0)
    return first, second


def _sticker_centre(index: int) -> Point3:
    """Return the centre of a sticker on the cube's surface.

    Args:
        index: Facelet index.

    Returns:
        The point, half a cell out from its cubie's centre.

    """
    position, normal = STICKERS[index]
    return _add(position, normal, 0.5)


def _arrow(painter: QPainter, start: QPointF, end: QPointF, scale: float) -> None:
    """Draw an arrow, with a light halo so it shows on any sticker colour.

    Args:
        painter: The painter, already scaled to the drawing.
        start: Tail.
        end: Tip.
        scale: Pixels per cube unit (keeps pen widths in pixels).

    """
    line = QLineF(start, end)
    unit = line.unitVector()
    direction = QPointF(unit.dx(), unit.dy())
    side = QPointF(-direction.y(), direction.x())
    base = end - direction * _HEAD
    head = QPolygonF(
        [end, base + side * (_HEAD * 0.55), base - side * (_HEAD * 0.55)],
    )
    shaft = QLineF(start, base)
    for color, width in (("#ffffff", 4.2), (INK_COLOR, 1.8)):
        pen = QPen(QColor(color), width / scale)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(QColor(color))
        painter.drawLine(shaft)
        painter.drawPolygon(head)


def move_arrows(base: str) -> list[tuple[Point3, Point3]]:
    """Work out the arrows for a move: one along each turned strip of a visible face.

    A face the move turns around (e.g. R for R) gets no arrow: its stickers turn in
    place. On the others, the arrow runs through the middle of the turned strip in
    the direction its stickers move.

    Args:
        base: Base move name.

    Returns:
        (tail, tip) of each arrow, in cube coordinates.

    """
    axis = move_axis(base)
    turned = turned_stickers(base)
    arrows: list[tuple[Point3, Point3]] = []
    for face in VISIBLE_FACES:
        normal = FACE_NORMALS[face]
        if any(a != 0 and n != 0 for a, n in zip(axis, normal, strict=True)):
            continue  # turns around this face's axis
        start = 9 * FACES.index(face)
        strip = [_sticker_centre(i) for i in range(start, start + 9) if i in turned]
        middle: Point3 = (
            sum(c[0] for c in strip) / len(strip),
            sum(c[1] for c in strip) / len(strip),
            sum(c[2] for c in strip) / len(strip),
        )
        # A clockwise turn moves a point p along -(axis x p); keep the part of that
        # lying in the face.
        ax, ay, az = axis
        px, py, pz = middle
        motion = (-(ay * pz - az * py), -(az * px - ax * pz), -(ax * py - ay * px))
        mx, my, mz = (m if n == 0 else 0.0 for m, n in zip(motion, normal, strict=True))
        length = math.sqrt(mx * mx + my * my + mz * mz)
        direction: Point3 = (mx / length, my / length, mz / length)
        arrows.append(
            (
                _add(middle, direction, -_ARROW_HALF),
                _add(middle, direction, _ARROW_HALF),
            ),
        )
    return arrows


def render_move(base: str, size: int) -> QImage:
    """Draw a move: the cube with the turned layers in colour and arrows on them.

    Args:
        base: Base move name, e.g. ``"R"``, ``"r"``, ``"M"`` or ``"y"``.
        size: Width and height of the image, in pixels.

    Returns:
        The image, on a transparent background.

    """
    return _render_cube(size, turned_stickers(base), move_arrows(base))


def render_solved_cube(
    size: int,
    *,
    stickers: bool = True,
    line: float = 1.0,
) -> QImage:
    """Draw the solved cube, every sticker in colour, without arrows (the app icon).

    Args:
        size: Width and height of the image, in pixels.
        stickers: Draw the 3x3 stickers; False draws each face as one block of
            colour, which stays readable at icon sizes of a few pixels.
        line: Thickness of the dark lines, relative to the usual.

    Returns:
        The image, on a transparent background.

    """
    if not stickers:
        return _render_faces(size, line)
    return _render_cube(size, frozenset(range(len(STICKERS))), [], line)


def _scale_for(size: int) -> float:
    """Return the drawing scale fitting the cube in a square image.

    Args:
        size: The image's side, in pixels.

    Returns:
        Pixels per cube unit.

    """
    half_width, half_height = _EXTENT
    margin = 0.15
    return size / (2 * max(half_width, half_height) + 2 * margin)


def _render_faces(size: int, line: float) -> QImage:
    """Draw the solved cube's visible faces as solid blocks of colour.

    Args:
        size: Width and height of the image, in pixels.
        line: Thickness of the lines between faces, relative to the usual.

    Returns:
        The image, on a transparent background.

    """
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    scale = _scale_for(size)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(size / 2, size / 2)
        painter.scale(scale, scale)
        pen = QPen(QColor(INK_COLOR), line / scale)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        for face in VISIBLE_FACES:
            normal = FACE_NORMALS[face]
            u, v = _face_axes(normal)
            centre: Point3 = (1.5 * normal[0], 1.5 * normal[1], 1.5 * normal[2])
            corners = [
                _project(_add(_add(centre, u, du), v, dv))
                for du, dv in ((-1.5, -1.5), (1.5, -1.5), (1.5, 1.5), (-1.5, 1.5))
            ]
            painter.setBrush(QColor(COLOR_SCHEME[face]))
            painter.drawPolygon(QPolygonF(corners))
    finally:
        painter.end()
    return image


def _render_cube(
    size: int,
    coloured: frozenset[int],
    arrows: list[tuple[Point3, Point3]],
    line: float = 1.0,
) -> QImage:
    """Draw the cube in isometric view, some stickers in colour, with arrows.

    Args:
        size: Width and height of the image, in pixels.
        coloured: Stickers (facelet indices) drawn in their colour; the rest grey.
        arrows: (tail, tip) of each arrow, in cube coordinates.
        line: Thickness of the sticker outlines, relative to the usual.

    Returns:
        The image, on a transparent background.

    """
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    scale = _scale_for(size)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(size / 2, size / 2)
        painter.scale(scale, scale)
        outline = QPen(QColor(INK_COLOR), line / scale)
        outline.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        for face in VISIBLE_FACES:
            u, v = _face_axes(FACE_NORMALS[face])
            start = 9 * FACES.index(face)
            for index in range(start, start + 9):
                centre = _sticker_centre(index)
                corners = [
                    _project(_add(_add(centre, u, du), v, dv))
                    for du, dv in (
                        (-_STICKER_HALF, -_STICKER_HALF),
                        (_STICKER_HALF, -_STICKER_HALF),
                        (_STICKER_HALF, _STICKER_HALF),
                        (-_STICKER_HALF, _STICKER_HALF),
                    )
                ]
                color = COLOR_SCHEME[face] if index in coloured else STILL_COLOR
                painter.setPen(outline)
                painter.setBrush(QColor(color))
                painter.drawPolygon(QPolygonF(corners))
        for tail, tip in arrows:
            _arrow(painter, _project(tail), _project(tip), scale)
    finally:
        painter.end()
    return image
