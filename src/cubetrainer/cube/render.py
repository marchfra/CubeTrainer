"""Draw jperm-style top-down images of the last layer.

The image shows the U face as a 3x3 grid with the top row of each side face as a thin
strip around it (B above, F below, L left, R right), optionally with arrows showing
where each piece goes when the case's algorithm is performed.
"""

from dataclasses import dataclass

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

from cubetrainer.cube.model import STICKERS, CubeState, Vec, rotate_clockwise

#: Sticker colour for each face, for a cube held yellow on top and green in front.
COLOR_SCHEME: dict[str, str] = {
    "U": "#ffd500",
    "D": "#ffffff",
    "F": "#009e60",
    "B": "#0051ba",
    "R": "#ff5800",
    "L": "#c41e3a",
}

#: Outline colour of stickers and colour of arrows.
INK_COLOR: str = "#1a1a1a"

# Arrow geometry, in units of one U-face cell. Heads end close to the target cell's
# centre and are small enough to stay inside its sticker, clear of the gaps.
_ARROW_TAIL_GAP: float = 0.2  # distance from the start cell's centre to the tail
_ARROW_TIP_GAP: float = 0.08  # distance from the end cell's centre to the tip
_HEAD_LENGTH: float = 0.22
_HEAD_HALF_WIDTH: float = 0.1

# Layout, in units of one U-face cell.
_STRIP: float = 0.35  # thickness of a side strip
_GAP: float = 0.1  # space between a strip and the U face
_INSET: float = 0.04  # space around each sticker
_OFFSET: float = _STRIP + _GAP  # where the U face starts
_TOTAL: float = 3 + 2 * _OFFSET  # image side length


@dataclass(frozen=True, slots=True)
class Arrow:
    """An arrow between two U-face cells.

    Attributes:
        start: (column, row) of the cell the piece starts in.
        end: (column, row) of the cell the piece moves to.
        both_ways: Whether the two pieces swap (drawn with two heads).

    """

    start: tuple[int, int]
    end: tuple[int, int]
    both_ways: bool


def _cell(x: int, z: int) -> tuple[int, int]:
    """Convert a top-layer cubie position to its (column, row) in the image.

    Args:
        x: Cubie x coordinate (-1 is L, 1 is R).
        z: Cubie z coordinate (-1 is B, 1 is F).

    Returns:
        The column (0 on the left) and row (0 at the top, the B side).

    """
    return x + 1, z + 1


def _turn_u(position: Vec, quarter_turns: int) -> Vec:
    """Move a position around the U axis as a clockwise U turn would.

    Args:
        position: Cubie position.
        quarter_turns: Number of clockwise quarter turns (0 to 3).

    Returns:
        The new position.

    """
    for _ in range(quarter_turns):
        position = rotate_clockwise(position, (0, 1, 0))
    return position


type _Cell = tuple[int, int]


def _merge_swaps(moves: dict[_Cell, _Cell]) -> list[Arrow]:
    """Turn piece moves into arrows, merging each two-piece swap into one arrow.

    Args:
        moves: Target cell of each moving piece, keyed by its current cell.

    Returns:
        The arrows.

    """
    arrows: list[Arrow] = []
    for start, end in moves.items():
        swapped = moves.get(end) == start
        if swapped and start > end:
            continue  # already added from the other end
        arrows.append(Arrow(start, end, both_ways=swapped))
    return arrows


def _piece_moves(state: CubeState, auf: int) -> dict[_Cell, _Cell]:
    """Find where each top-layer piece goes, relative to a final U turn.

    Args:
        state: A state whose bottom two layers are solved.
        auf: Final U turn (0 to 3 quarter turns) the targets are measured against.

    Returns:
        Target cell of each moving piece, keyed by its current cell.

    """
    moves: dict[_Cell, _Cell] = {}
    for index, (position, normal) in enumerate(STICKERS):
        if normal != (0, 1, 0) or position == (0, 1, 0):
            continue
        home = _turn_u(STICKERS[state.stickers[index]][0], auf)
        if home != position:
            moves[_cell(position[0], position[2])] = _cell(home[0], home[2])
    return moves


def _longest_cycle(moves: dict[_Cell, _Cell]) -> int:
    """Return the length of the longest cycle among the moving pieces.

    Args:
        moves: Target cell of each moving piece, keyed by its current cell.

    Returns:
        The longest cycle length (0 if nothing moves).

    """
    longest = 0
    seen: set[_Cell] = set()
    for start in moves:
        length, cell = 0, start
        while cell not in seen:
            seen.add(cell)
            cell = moves[cell]
            length += 1
        longest = max(longest, length)
    return longest


def _stationary_blocks(moves: dict[_Cell, _Cell]) -> int:
    """Count corner-edge pairs that are adjacent and both stay in place.

    Two pieces that both stay put are solved relative to each other, so they show up
    as a block in the stickers.

    Args:
        moves: Target cell of each moving piece, keyed by its current cell.

    Returns:
        The number of stationary adjacent corner-edge pairs.

    """
    cells = [(col, row) for col in range(3) for row in range(3) if (col, row) != (1, 1)]
    still = [c for c in cells if c not in moves]
    corners = [c for c in still if c[0] != 1 and c[1] != 1]
    edges = [c for c in still if (c[0] == 1) != (c[1] == 1)]
    return sum(
        1
        for corner in corners
        for edge in edges
        if abs(corner[0] - edge[0]) + abs(corner[1] - edge[1]) == 1
    )


def piece_arrows(state: CubeState) -> list[Arrow]:
    """Compute where each top-layer piece goes when the state is solved.

    Many algorithms finish with the top layer a turn away from solved (a final AUF).
    The arrows ignore that, using the final U turn that moves the fewest pieces. Ties
    go to the shortest cycles, then to the turn that keeps a corner-edge block still.
    So a G perm shows as a corner 3-cycle plus an edge 3-cycle (not a corner swap plus
    an edge 4-cycle), with the block you recognise it by staying in place.

    Args:
        state: A state whose bottom two layers are solved.

    Returns:
        One arrow per moving piece, with swaps merged into a single two-headed arrow.

    """
    options = [_piece_moves(state, auf) for auf in range(4)]
    best = min(
        options,
        key=lambda m: (len(m), _longest_cycle(m), -_stationary_blocks(m)),
    )
    return _merge_swaps(best)


def _sticker_rect(position: Vec, normal: Vec) -> QRectF:
    """Return the rectangle of a top-layer sticker, in cell units.

    Args:
        position: The sticker's cubie position.
        normal: The sticker's outward normal.

    Returns:
        The rectangle within the ``_TOTAL`` x ``_TOTAL`` image.

    """
    col, row = _cell(position[0], position[2])
    long_x = _OFFSET + col + _INSET
    long_y = _OFFSET + row + _INSET
    length = 1 - 2 * _INSET
    if normal == (0, 1, 0):
        return QRectF(long_x, long_y, length, length)
    if normal == (0, 0, -1):
        return QRectF(long_x, 0, length, _STRIP)
    if normal == (0, 0, 1):
        return QRectF(long_x, _TOTAL - _STRIP, length, _STRIP)
    if normal == (-1, 0, 0):
        return QRectF(0, long_y, _STRIP, length)
    return QRectF(_TOTAL - _STRIP, long_y, _STRIP, length)


def _cell_center(cell: tuple[int, int]) -> QPointF:
    """Return the centre of a U-face cell, in cell units.

    Args:
        cell: (column, row) of the cell.

    Returns:
        The centre point.

    """
    return QPointF(_OFFSET + cell[0] + 0.5, _OFFSET + cell[1] + 0.5)


def _arrow_head(painter: QPainter, tip: QPointF, line: QLineF) -> None:
    """Draw a filled arrow head at ``tip``, pointing along ``line``.

    Args:
        painter: The painter (already scaled to cell units).
        tip: Where the head points to.
        line: The arrow's shaft, ending at ``tip``.

    """
    unit = line.unitVector()
    direction = QPointF(unit.dx(), unit.dy())
    normal = QPointF(-direction.y(), direction.x())
    base = tip - direction * _HEAD_LENGTH
    painter.drawPolygon(
        QPolygonF(
            [tip, base + normal * _HEAD_HALF_WIDTH, base - normal * _HEAD_HALF_WIDTH],
        ),
    )


def _draw_arrow(painter: QPainter, arrow: Arrow) -> None:
    """Draw one arrow between two cell centres.

    Args:
        painter: The painter (already scaled to cell units).
        arrow: The arrow to draw.

    """
    start, end = _cell_center(arrow.start), _cell_center(arrow.end)
    full = QLineF(start, end)
    tail_gap = _ARROW_TIP_GAP if arrow.both_ways else _ARROW_TAIL_GAP
    shaft = QLineF(
        full.pointAt(tail_gap / full.length()),
        full.pointAt(1 - _ARROW_TIP_GAP / full.length()),
    )
    painter.drawLine(shaft)
    _arrow_head(painter, shaft.p2(), shaft)
    if arrow.both_ways:
        reverse = QLineF(shaft.p2(), shaft.p1())
        _arrow_head(painter, reverse.p2(), reverse)


def render_last_layer(state: CubeState, size: int, *, arrows: bool = True) -> QImage:
    """Render the top-down view of a state's last layer.

    Args:
        state: The cube state, in standard orientation.
        size: Width and height of the image in pixels.
        arrows: Whether to draw arrows showing how the pieces move.

    Returns:
        A square image with a transparent background.

    """
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / _TOTAL, size / _TOTAL)

    facelets = state.facelets()
    outline = QPen(QColor(INK_COLOR), 0.04)
    painter.setPen(outline)
    for index, (position, normal) in enumerate(STICKERS):
        if position[1] != 1 or normal[1] == -1:
            continue
        painter.setBrush(QColor(COLOR_SCHEME[facelets[index]]))
        painter.drawRoundedRect(_sticker_rect(position, normal), 0.08, 0.08)

    if arrows:
        painter.setPen(
            QPen(
                QColor(INK_COLOR),
                0.07,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
            ),
        )
        painter.setBrush(QColor(INK_COLOR))
        for arrow in piece_arrows(state):
            _draw_arrow(painter, arrow)
    painter.end()
    return image
