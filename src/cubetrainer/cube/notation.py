"""A reference of the move notation the algorithm parser accepts.

Everything here is derived from the parser's move table (``BASE_MOVES``, the axis
each move turns around, ``SUFFIX_TURNS``), so the reference can't list a move the
app doesn't understand or miss one it does.
"""

from dataclasses import dataclass
from enum import StrEnum

from cubetrainer.cube.model import (
    BASE_MOVES,
    FACE_NORMALS,
    FACES,
    SUFFIX_TURNS,
    move_axis,
)

#: Plain names of the faces.
FACE_NAMES: dict[str, str] = {
    "U": "up",
    "D": "down",
    "R": "right",
    "L": "left",
    "F": "front",
    "B": "back",
}

#: Where you look at each face from.
_VIEWPOINTS: dict[str, str] = {
    "U": "above",
    "D": "below",
    "R": "the right",
    "L": "the left",
    "F": "the front",
    "B": "behind",
}

#: The face opposite each face.
_OPPOSITE: dict[str, str] = {"U": "D", "D": "U", "R": "L", "L": "R", "F": "B", "B": "F"}


class MoveGroup(StrEnum):
    """Kinds of moves, in the order the reference lists them."""

    FACE = "Face turns"
    WIDE = "Wide moves"
    SLICE = "Slice moves"
    ROTATION = "Cube rotations"


@dataclass(frozen=True, slots=True)
class NotationEntry:
    """One base move in the reference.

    Attributes:
        base: The move as written, e.g. ``"R"`` or ``"r"``.
        group: What kind of move it is.
        description: What it does.

    """

    base: str
    group: MoveGroup
    description: str


def _group(base: str) -> MoveGroup:
    """Classify a base move by how it's written.

    Args:
        base: Base move name.

    Returns:
        Its group: face letters are face turns, lowercase ones wide moves, M/E/S
        slices, and x/y/z rotations.

    """
    if base in FACES:
        return MoveGroup.FACE
    if base.upper() in FACES:
        return MoveGroup.WIDE
    if base in "MES":
        return MoveGroup.SLICE
    return MoveGroup.ROTATION


def _turns_like(base: str) -> str:
    """Return the face a move turns in the same direction as.

    Args:
        base: Base move name.

    Returns:
        The face whose clockwise turn has the same axis, e.g. ``"L"`` for ``M``.

    """
    axis = move_axis(base)
    return next(face for face, normal in FACE_NORMALS.items() if normal == axis)


def describe(base: str) -> str:
    """Describe what a base move does.

    Args:
        base: Base move name.

    Returns:
        e.g. ``"The right face, clockwise as seen from the right."``.

    """
    like = _turns_like(base)
    name = FACE_NAMES[like]
    match _group(base):
        case MoveGroup.FACE:
            return f"The {name} face, clockwise as seen from {_VIEWPOINTS[like]}."
        case MoveGroup.WIDE:
            return (
                f"The {name} face and the middle layer together, like {like}."
                f" Also written {like}w."
            )
        case MoveGroup.SLICE:
            return (
                f"The middle layer between {like} and {_OPPOSITE[like]},"
                f" in the direction of {like}."
            )
        case MoveGroup.ROTATION:
            return f"The whole cube, in the direction of {like}."


def notation_entries() -> list[NotationEntry]:
    """List every base move the parser accepts, grouped by kind.

    Returns:
        The entries: face turns, then wide moves, slices and rotations, each in
        the parser's table order.

    """
    entries = [NotationEntry(base, _group(base), describe(base)) for base in BASE_MOVES]
    order = list(MoveGroup)
    return sorted(entries, key=lambda entry: order.index(entry.group))


def suffix_notes() -> list[tuple[str, str]]:
    """Explain the move suffixes, from the parser's suffix table.

    Returns:
        (example, meaning) pairs, e.g. ``("R'", "anticlockwise (the inverse)")``.

    """
    meanings = {1: "a quarter turn clockwise", 2: "a half turn", 3: "anticlockwise"}
    notes = []
    # Shortest first: R, R', R2, R2'.
    for suffix, turns in sorted(SUFFIX_TURNS.items(), key=lambda s: (len(s[0]), s[0])):
        meaning = meanings[turns]
        if suffix == "2'":
            meaning = "accepted, and the same as R2 (a half turn either way)"
        notes.append((f"R{suffix}", meaning))
    notes.append(("( )  [ ]", "group moves into blocks; ignored when reading"))
    return notes
