"""Tests for the sticker-level cube model and move notation."""

import pytest

from cubetrainer.cube.model import (
    SOLVED,
    AlgorithmParseError,
    Move,
    format_alg,
    invert_alg,
    parse_alg,
    state_solved_by,
)

T_PERM = "R U R' U' R' F R2 U' R' U' R U R' F'"
ALL_BASES = list("URFDLBurfdlbMESxyz")


def test_r_move_matches_known_facelets() -> None:
    """An R turn moves F to U, U to B, B to D and D to F on the right-hand column."""
    expected = (
        "UUFUUFUUF"  # U: right column now shows F
        "RRRRRRRRR"
        "FFDFFDFFD"  # F: right column now shows D
        "DDBDDBDDB"  # D: right column now shows B
        "LLLLLLLLL"
        "UBBUBBUBB"  # B: left column (the R side) now shows U
    )

    assert SOLVED.apply_alg("R").facelets() == expected


@pytest.mark.parametrize("base", ALL_BASES)
def test_four_quarter_turns_are_identity(base: str) -> None:
    """Every move has order 4, and a single turn changes the cube."""
    moves = [Move(base, 1)]

    assert SOLVED.apply(moves) != SOLVED
    assert SOLVED.apply(moves * 4) == SOLVED


@pytest.mark.parametrize(
    ("alg", "repeats"),
    [("R U R' U'", 6), ("R U", 105), (T_PERM, 2), ("M2 E2 S2", 2)],
)
def test_known_orders(alg: str, repeats: int) -> None:
    """Well-known algorithms return to solved after their known order."""
    assert SOLVED.apply(parse_alg(alg) * repeats) == SOLVED


def test_t_perm_is_not_identity() -> None:
    """Sanity check: a single T-perm leaves the cube unsolved."""
    assert not SOLVED.apply_alg(T_PERM).is_solved()


@pytest.mark.parametrize(
    ("composite", "equivalent"),
    [
        ("r", "R M'"),
        ("Rw", "R M'"),
        ("l", "L M"),
        ("u", "U E'"),
        ("f", "F S"),
        ("x", "R M' L'"),
        ("y", "U E' D'"),
        ("z", "F S B'"),
    ],
)
def test_wide_moves_and_rotations_compose_from_layers(
    composite: str,
    equivalent: str,
) -> None:
    """Wide moves and rotations equal the corresponding layer turns."""
    assert SOLVED.apply_alg(composite) == SOLVED.apply_alg(equivalent)


def test_rotation_keeps_cube_solved() -> None:
    """A whole-cube rotation counts as solved."""
    assert SOLVED.apply_alg("x y2 z'").is_solved()


def test_alg_then_inverse_is_identity() -> None:
    """Applying an algorithm and then its inverse returns to the start."""
    moves = parse_alg("R U2 r' F M E' S2 x y' z2 Lw D B'")

    assert SOLVED.apply(moves + invert_alg(moves)) == SOLVED


def test_parse_accepts_brackets_wide_and_suffixes() -> None:
    """Brackets and spaces are ignored; Rw and R2' are normalised."""
    moves = parse_alg("(R U2') [Rw' M2]y")

    assert format_alg(moves) == "R U2 r' M2 y"


def test_parse_without_spaces() -> None:
    """Moves can be written without separating spaces."""
    assert format_alg(parse_alg("RUR'U'")) == "R U R' U'"


def test_parse_empty_string() -> None:
    """An empty algorithm parses to no moves."""
    assert parse_alg("  ") == []


@pytest.mark.parametrize("text", ["R Q", "R3", "Mw", "R U%"])
def test_parse_rejects_invalid_notation(text: str) -> None:
    """Anything that isn't a move raises a parse error."""
    with pytest.raises(AlgorithmParseError):
        parse_alg(text)


def test_move_validation() -> None:
    """Moves with unknown bases or invalid turn counts are rejected."""
    with pytest.raises(ValueError, match="unknown move"):
        Move("Q", 1)
    with pytest.raises(ValueError, match="turns"):
        Move("R", 4)


@pytest.mark.parametrize(
    "alg",
    [
        "R U R' U'",
        "x R' U R' D2 R U' R' D2 R2",
        "R' U R' U' y R' F' R2 U' R' U R' F R F",
    ],
)
def test_state_solved_by_keeps_centres_home(alg: str) -> None:
    """The returned state is held in standard orientation and the alg solves it."""
    moves = parse_alg(alg)
    state = state_solved_by(moves)

    assert all(state.stickers[9 * f + 4] == 9 * f + 4 for f in range(6))
    assert state.apply(moves).is_solved()


def test_state_solved_by_rotation_matches_rotation_free_alg() -> None:
    """An alg starting with x gives the same case as its rotation-free equivalent."""
    with_rotation = state_solved_by(parse_alg("x R' U R' D2 R U' R' D2 R2"))
    without = state_solved_by(parse_alg("R' F R' B2 R F' R' B2 R2"))

    assert with_rotation == without
