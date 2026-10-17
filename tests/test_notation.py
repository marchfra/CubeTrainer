"""Tests for the notation reference, its move pictures and its dialog."""

import pytest
from pytestqt.qtbot import QtBot

from cubetrainer.cube.model import BASE_MOVES, FACES, CubeState, Move, parse_alg
from cubetrainer.cube.move_render import (
    _sticker_centre,
    move_arrows,
    render_move,
)
from cubetrainer.cube.notation import (
    MoveGroup,
    describe,
    notation_entries,
    suffix_notes,
)
from cubetrainer.db import Database
from cubetrainer.ui.learn_page import LearnPage
from cubetrainer.ui.notation_dialog import NotationDialog


def test_every_parser_move_is_listed_once() -> None:
    """The reference lists exactly the parser's moves, grouped by kind."""
    entries = notation_entries()

    assert sorted(entry.base for entry in entries) == sorted(BASE_MOVES)
    groups = [entry.group for entry in entries]
    assert groups == sorted(groups, key=list(MoveGroup).index)
    counts = {group: groups.count(group) for group in MoveGroup}
    assert counts == {
        MoveGroup.FACE: 6,
        MoveGroup.WIDE: 6,
        MoveGroup.SLICE: 3,
        MoveGroup.ROTATION: 3,
    }


@pytest.mark.parametrize(
    ("base", "text"),
    [
        ("R", "The right face, clockwise as seen from the right."),
        ("D", "The down face, clockwise as seen from below."),
        ("r", "The right face and the middle layer together, like R. Also written Rw."),
        ("M", "The middle layer between L and R, in the direction of L."),
        ("y", "The whole cube, in the direction of U."),
    ],
)
def test_descriptions(base: str, text: str) -> None:
    """Descriptions follow from each move's axis and kind."""
    assert describe(base) == text


def test_suffix_examples_are_accepted() -> None:
    """Every suffix example parses, to the number of turns it describes."""
    notes = dict(suffix_notes())

    assert list(notes)[:4] == ["R", "R'", "R2", "R2'"]
    assert [parse_alg(example)[0].turns for example in list(notes)[:4]] == [1, 3, 2, 2]
    assert parse_alg("(R U) [R']") == parse_alg("R U R'")


@pytest.mark.parametrize("base", BASE_MOVES)
def test_arrows_point_the_way_stickers_move(base: str) -> None:
    """Every turned sticker on an arrowed face moves the way its arrow points."""
    arrows = {
        _face_of(tail): tuple(b - a for a, b in zip(tail, tip, strict=True))
        for tail, tip in move_arrows(base)
    }
    after = CubeState().apply([Move(base, 1)]).stickers
    checked = 0
    for position, sticker in enumerate(after):
        face = FACES[sticker // 9]  # where the sticker started
        if sticker == position or face not in arrows:
            continue
        start, end = _sticker_centre(sticker), _sticker_centre(position)
        moved = [b - a for a, b in zip(start, end, strict=True)]
        assert sum(m * d for m, d in zip(moved, arrows[face], strict=True)) > 0
        checked += 1
    assert checked >= 3 * len(arrows)  # at least a strip's worth per arrow


def _face_of(point: tuple[float, float, float]) -> str:
    """Return the visible face a point on the cube's surface lies on.

    Args:
        point: A point on the U, F or R face.

    Returns:
        The face letter.

    """
    x, y, z = point
    if y == 1.5:
        return "U"
    if z == 1.5:
        return "F"
    assert x == 1.5
    return "R"


@pytest.mark.parametrize(
    ("base", "faces"),
    [("R", 2), ("U", 2), ("D", 2), ("M", 2), ("x", 2), ("y", 2)],
)
def test_no_arrow_on_the_face_a_move_turns_around(base: str, faces: int) -> None:
    """R gets arrows on U and F, not on R (whose stickers turn in place)."""
    assert len(move_arrows(base)) == faces


def test_picture_is_drawn(qtbot: QtBot) -> None:
    """A move's picture has the requested size and isn't blank."""
    del qtbot  # a QApplication is needed for painting
    image = render_move("R", 60)

    assert image.size().toTuple() == (60, 60)
    assert image.pixelColor(30, 30).alpha() > 0


def test_learn_page_opens_the_notation(qtbot: QtBot) -> None:
    """The Notation button shows every move with its picture."""
    page = LearnPage(Database(":memory:"))
    qtbot.addWidget(page)
    shown: list[NotationDialog] = []

    def run_dialog(dialog: object) -> int:
        assert isinstance(dialog, NotationDialog)
        shown.append(dialog)
        return 0

    page.run_dialog = run_dialog  # type: ignore[assignment]
    page.notation_button.click()

    (dialog,) = shown
    assert sorted(dialog.moves) == sorted(BASE_MOVES)
    assert all(not label.pixmap().isNull() for label in dialog.pictures.values())
