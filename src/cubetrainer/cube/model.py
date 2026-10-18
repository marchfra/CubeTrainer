"""Sticker-level 3x3 cube model and algorithm notation.

The cube is modelled geometrically: each of the 54 stickers has a position in
{-1, 0, 1}^3 and an outward normal. A move rotates every sticker in its layer(s) by a
quarter turn, so face turns, wide turns, slices and whole-cube rotations all come from
the same rule instead of hand-written tables.

Coordinates: +x is R, +y is U, +z is F. Sticker indices follow the facelet order used
by the Kociemba solver (U1..U9, R1..R9, F1..F9, D1..D9, L1..L9, B1..B9), each face read
row by row as it appears in the standard unfolded net.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

type Vec = tuple[int, int, int]

#: Faces in Kociemba facelet order.
FACES: str = "URFDLB"

#: Outward normal of each face.
FACE_NORMALS: dict[str, Vec] = {
    "U": (0, 1, 0),
    "R": (1, 0, 0),
    "F": (0, 0, 1),
    "D": (0, -1, 0),
    "L": (-1, 0, 0),
    "B": (0, 0, -1),
}


def _sticker_position(face: str, row: int, col: int) -> Vec:
    """Return the cubie position of a sticker given its place in the unfolded net.

    Args:
        face: Face letter.
        row: Row in the face grid, 0 at the top of the net.
        col: Column in the face grid, 0 at the left of the net.

    Returns:
        The (x, y, z) position of the cubie carrying the sticker.

    """
    a, b = row - 1, col - 1
    positions: dict[str, Vec] = {
        "U": (b, 1, a),  # seen from above, B edge at the top
        "R": (1, -a, -b),  # seen from the right, F edge on the left
        "F": (b, -a, 1),
        "D": (b, -1, -a),  # seen from below, F edge at the top
        "L": (-1, -a, b),  # seen from the left, B edge on the left
        "B": (-b, -a, -1),  # seen from behind, R edge on the left
    }
    return positions[face]


#: (position, normal) of every sticker, indexed in facelet order.
STICKERS: tuple[tuple[Vec, Vec], ...] = tuple(
    (_sticker_position(face, row, col), FACE_NORMALS[face])
    for face in FACES
    for row in range(3)
    for col in range(3)
)

_STICKER_INDEX: dict[tuple[Vec, Vec], int] = {s: i for i, s in enumerate(STICKERS)}


def _dot(u: Vec, v: Vec) -> int:
    """Return the dot product of two integer vectors.

    Args:
        u: First vector.
        v: Second vector.

    Returns:
        The dot product.

    """
    return u[0] * v[0] + u[1] * v[1] + u[2] * v[2]


def rotate_clockwise(v: Vec, axis: Vec) -> Vec:
    """Rotate a vector a clockwise quarter turn as seen from the tip of ``axis``.

    Args:
        v: Vector to rotate.
        axis: Unit axis vector (one of the six face normals).

    Returns:
        The rotated vector.

    """
    # Rodrigues' formula with angle -90 degrees: v' = a(a.v) - a x v.
    cross = (
        axis[1] * v[2] - axis[2] * v[1],
        axis[2] * v[0] - axis[0] * v[2],
        axis[0] * v[1] - axis[1] * v[0],
    )
    d = _dot(axis, v)
    return (axis[0] * d - cross[0], axis[1] * d - cross[1], axis[2] * d - cross[2])


#: For each base move: (rotation axis, predicate selecting the turned layers by depth
#: along that axis, where 1 is the outer layer).
_BASE_MOVES: dict[str, tuple[Vec, Callable[[int], bool]]] = {
    **{f: (FACE_NORMALS[f], lambda d: d == 1) for f in FACES},
    **{f.lower(): (FACE_NORMALS[f], lambda d: d >= 0) for f in FACES},
    "M": (FACE_NORMALS["L"], lambda d: d == 0),
    "E": (FACE_NORMALS["D"], lambda d: d == 0),
    "S": (FACE_NORMALS["F"], lambda d: d == 0),
    "x": (FACE_NORMALS["R"], lambda _d: True),
    "y": (FACE_NORMALS["U"], lambda _d: True),
    "z": (FACE_NORMALS["F"], lambda _d: True),
}


#: Every base move the parser accepts, in table order.
BASE_MOVES: tuple[str, ...] = tuple(_BASE_MOVES)

#: Move suffixes and the clockwise quarter turns they mean.
SUFFIX_TURNS: dict[str, int] = {"": 1, "2": 2, "2'": 2, "'": 3}


def move_axis(base: str) -> Vec:
    """Return the axis a base move turns around (clockwise looking at it).

    Args:
        base: Base move name, e.g. ``"R"`` or ``"M"``.

    Returns:
        The outward normal of the face the move turns like (``M`` turns like L).

    """
    return _BASE_MOVES[base][0]


def turned_stickers(base: str) -> frozenset[int]:
    """Return the stickers (facelet indices) on the layers a base move turns.

    Args:
        base: Base move name.

    Returns:
        The indices, centres included (they turn in place).

    """
    axis, in_layer = _BASE_MOVES[base]
    return frozenset(
        i for i, (position, _) in enumerate(STICKERS) if in_layer(_dot(position, axis))
    )


@cache
def _quarter_turn_permutation(base: str) -> tuple[int, ...]:
    """Compute where each sticker goes under one clockwise quarter turn of a move.

    Args:
        base: Base move name, e.g. ``"R"``, ``"r"``, ``"M"`` or ``"y"``.

    Returns:
        A tuple ``p`` such that the sticker at index ``i`` moves to index ``p[i]``.

    """
    axis, in_layer = _BASE_MOVES[base]
    perm: list[int] = []
    for position, normal in STICKERS:
        if in_layer(_dot(position, axis)):
            target = (
                rotate_clockwise(position, axis),
                rotate_clockwise(normal, axis),
            )
            perm.append(_STICKER_INDEX[target])
        else:
            perm.append(_STICKER_INDEX[(position, normal)])
    return tuple(perm)


class AlgorithmParseError(ValueError):
    """Raised when a string is not valid move notation."""


@dataclass(frozen=True, slots=True)
class Move:
    """A single move: a base move turned clockwise ``turns`` quarter turns.

    Attributes:
        base: Base move name (``U R F D L B``, lowercase wide moves, ``M E S``,
            ``x y z``).
        turns: Number of clockwise quarter turns, 1 to 3 (3 is a prime move).

    """

    base: str
    turns: int

    def __post_init__(self) -> None:
        """Validate the move.

        Raises:
            ValueError: If the base move is unknown or ``turns`` is not 1, 2 or 3.

        """
        if self.base not in _BASE_MOVES:
            msg = f"unknown move {self.base!r}"
            raise ValueError(msg)
        if self.turns not in {1, 2, 3}:
            msg = f"turns must be 1, 2 or 3, not {self.turns}"
            raise ValueError(msg)

    def inverse(self) -> Move:
        """Return the move that undoes this one.

        Returns:
            The inverse move.

        """
        return Move(self.base, 4 - self.turns)

    def __str__(self) -> str:
        """Return the move in standard notation, e.g. ``R``, ``U2`` or ``r'``.

        Returns:
            The notation string.

        """
        return self.base + {1: "", 2: "2", 3: "'"}[self.turns]


_TOKEN_RE = re.compile(r"([URFDLB]w|[URFDLBurfdlbMESxyz])(2'|2|'|)")
_IGNORED_CHARS = re.compile(r"[\s()\[\]]+")


def parse_alg(text: str) -> list[Move]:
    """Parse an algorithm written in standard notation.

    Spaces and parentheses/brackets are ignored. Wide moves may be written ``Rw`` or
    ``r``; ``R2'`` is accepted as ``R2``.

    Args:
        text: The algorithm, e.g. ``"(R U R' U') y2 Rw2"``.

    Returns:
        The parsed moves (empty for an empty string).

    Raises:
        AlgorithmParseError: If the text contains anything that isn't a move.

    """
    compact = _IGNORED_CHARS.sub("", text)
    moves: list[Move] = []
    pos = 0
    while pos < len(compact):
        match = _TOKEN_RE.match(compact, pos)
        if match is None:
            msg = f"invalid move at {compact[pos:]!r}"
            raise AlgorithmParseError(msg)
        base, suffix = match.groups()
        if base.endswith("w"):
            base = base[0].lower()
        turns = SUFFIX_TURNS[suffix]
        moves.append(Move(base, turns))
        pos = match.end()
    return moves


def format_alg(moves: Iterable[Move]) -> str:
    """Write moves back as a space-separated notation string.

    Args:
        moves: The moves.

    Returns:
        The notation string, e.g. ``"R U R' U'"``.

    """
    return " ".join(str(m) for m in moves)


_OPENING: str = "(["
_CLOSING: str = ")]"
_DISPLAY_TOKEN_RE = re.compile(
    r"[()\[\]]|(?:[URFDLB]w|[URFDLBurfdlbMESxyz])(?:2'|2|'|)",
)


def _display_tokens(text: str) -> list[str]:
    """Split an algorithm into move tokens and brackets, keeping the user's notation.

    Args:
        text: A valid algorithm, possibly with ``(...)`` or ``[...]`` groups.

    Returns:
        The tokens, e.g. ``["(", "R", "U", "R'", ")", "Rw2"]``.

    Raises:
        AlgorithmParseError: If the text isn't valid notation.

    """
    parse_alg(text)  # validates
    return _DISPLAY_TOKEN_RE.findall(re.sub(r"\s+", "", text))


def _join_tokens(tokens: Sequence[str]) -> str:
    """Join tokens with spaces, tight against brackets: ``"(R U) F"``.

    Args:
        tokens: Move tokens and brackets.

    Returns:
        The formatted text.

    """
    text = ""
    for token in tokens:
        tight = token in _CLOSING or (text and text[-1] in _OPENING)
        text += token if tight or not text else f" {token}"
    return text


def reveal_alg(text: str, moves: int) -> str:
    """Show the first ``moves`` moves of an algorithm, keeping its brackets.

    Brackets don't count as moves: an opening bracket appears with the first move
    inside it, a closing one with the last. So for ``"(R U R' U') F"`` and 1, 4 and 5
    moves this gives ``"(R"``, ``"(R U R' U')"`` and ``"(R U R' U') F"``.

    Args:
        text: A valid algorithm, possibly with ``(...)`` or ``[...]`` groups.
        moves: How many moves to show.

    Returns:
        The shown part of the algorithm (the whole of it if ``moves`` is enough).

    """
    tokens = _display_tokens(text)
    shown: list[str] = []
    pending: list[str] = []  # opening brackets waiting for their first move
    count = 0
    for token in tokens:
        if token in _OPENING:
            pending.append(token)
        elif token in _CLOSING:
            if count <= moves:
                shown.append(token)
        else:
            count += 1
            if count > moves:
                break
            shown.extend(pending)
            pending.clear()
            shown.append(token)
    return _join_tokens(shown)


def alg_pieces(text: str, moves: int) -> list[tuple[str, bool]]:
    """Split an algorithm for display into pieces, each shown or still hidden.

    The pieces joined give the whole algorithm as ``reveal_alg`` writes it (spaces
    included), whatever ``moves`` is, so a display that masks the hidden pieces
    keeps the same length as more moves are shown. A piece is shown when
    ``reveal_alg(text, moves)`` includes it.

    Args:
        text: A valid algorithm, possibly with ``(...)`` or ``[...]`` groups.
        moves: How many moves are shown.

    Returns:
        (text, shown) pairs; the text of each piece starts with the space before it.

    """
    tokens = _display_tokens(text)
    shown: list[bool] = []
    pending: list[int] = []  # opening brackets waiting for their first move
    count = 0
    for token in tokens:
        if token in _OPENING:
            pending.append(len(shown))
            shown.append(False)
        elif token in _CLOSING:
            shown.append(count <= moves and count > 0)
        else:
            count += 1
            visible = count <= moves
            if visible:
                for index in pending:
                    shown[index] = True
            pending.clear()
            shown.append(visible)
    pieces: list[tuple[str, bool]] = []
    text_so_far = ""
    for token, visible in zip(tokens, shown, strict=True):
        tight = token in _CLOSING or (text_so_far and text_so_far[-1] in _OPENING)
        piece = token if tight or not text_so_far else f" {token}"
        text_so_far += piece
        pieces.append((piece, visible))
    return pieces


def invert_alg(moves: Sequence[Move]) -> list[Move]:
    """Return the algorithm that undoes ``moves``.

    Args:
        moves: The algorithm to invert.

    Returns:
        The inverse moves, in reverse order.

    """
    return [m.inverse() for m in reversed(moves)]


@dataclass(frozen=True, slots=True)
class CubeState:
    """An immutable cube state.

    Attributes:
        stickers: ``stickers[i]`` is the index of the sticker (in the solved cube)
            currently at facelet position ``i``.

    """

    stickers: tuple[int, ...] = tuple(range(54))

    def apply(self, moves: Iterable[Move]) -> CubeState:
        """Return the state after performing ``moves``.

        Args:
            moves: Moves to perform, in order.

        Returns:
            The new state.

        """
        current = list(self.stickers)
        for move in moves:
            perm = _quarter_turn_permutation(move.base)
            for _ in range(move.turns):
                nxt = [0] * 54
                for i, target in enumerate(perm):
                    nxt[target] = current[i]
                current = nxt
        return CubeState(tuple(current))

    def apply_alg(self, text: str) -> CubeState:
        """Return the state after performing an algorithm given as a string.

        Args:
            text: The algorithm in standard notation.

        Returns:
            The new state.

        """
        return self.apply(parse_alg(text))

    def followed_by(self, later: CubeState) -> CubeState:
        """Return the state reached by doing this state's moves, then ``later``'s.

        Both states are seen as the result of some moves on a solved cube; the
        result is as if those moves were done one after the other. To solve it,
        undo ``later`` first, then this state.

        Args:
            later: The state whose moves are done second.

        Returns:
            The combined state.

        """
        return CubeState(tuple(self.stickers[i] for i in later.stickers))

    def facelets(self) -> str:
        """Return the 54-character facelet string (colours named by their home face).

        Returns:
            A string such as ``"UUUUUUUUURRR..."`` in Kociemba facelet order.

        """
        return "".join(FACES[s // 9] for s in self.stickers)

    def is_solved(self) -> bool:
        """Check whether every face shows a single colour, in any orientation.

        Returns:
            True if the cube is solved (whole-cube rotations are allowed).

        """
        f = self.facelets()
        return all(len(set(f[i : i + 9])) == 1 for i in range(0, 54, 9))


#: The solved cube.
SOLVED: CubeState = CubeState()


def state_solved_by(
    moves: Sequence[Move],
    *,
    before: Sequence[Move] = (),
    after: Sequence[Move] = (),
) -> CubeState:
    """Return the state, held in standard orientation, that ``moves`` solve.

    For algorithms without net rotation this is just the inverse applied to a solved
    cube. Algorithms like ``x L2 D2 ...`` end with the cube held differently, so the
    inverse is applied starting from the matching rotated solved cube; that way the
    case appears in the orientation the solver holds the cube before starting.

    ``before`` and ``after`` (typically AUFs) are done in the standard orientation:
    ``before`` right before the algorithm, ``after`` once the cube has been rotated
    back after it. So the returned state is solved by ``before``, then ``moves``,
    then undoing the algorithm's rotation, then ``after``.

    Args:
        moves: An algorithm that solves the returned state (rotations allowed).
        before: Moves done before the algorithm.
        after: Moves done after the algorithm, in the standard orientation.

    Returns:
        The state with every centre on its home face.

    """
    undo_after, undo_moves, undo_before = (
        invert_alg(after),
        invert_alg(moves),
        invert_alg(before),
    )
    for rotation in _all_orientations():
        candidate = SOLVED.apply([*undo_after, *rotation, *undo_moves, *undo_before])
        if all(candidate.stickers[i] == i for i in _CENTERS):
            return candidate
    msg = "no rotation restores the centres"  # unreachable: rotations form a group
    raise AssertionError(msg)


#: Facelet indices of the six centres.
_CENTERS: tuple[int, ...] = tuple(9 * f + 4 for f in range(6))


@cache
def _all_orientations() -> tuple[tuple[Move, ...], ...]:
    """List one rotation sequence for each of the 24 orientations of the cube.

    Returns:
        24 sequences of ``x``/``y``/``z`` moves, each reaching a distinct orientation
        (the first is the empty sequence).

    """
    found: dict[tuple[int, ...], tuple[Move, ...]] = {}
    frontier: list[tuple[Move, ...]] = [()]
    while frontier:
        sequence = frontier.pop(0)
        centers = tuple(SOLVED.apply(sequence).stickers[i] for i in _CENTERS)
        if centers in found:
            continue
        found[centers] = sequence
        frontier.extend((*sequence, Move(base, 1)) for base in "xyz")
    return tuple(found.values())
