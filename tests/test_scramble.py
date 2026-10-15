"""Tests for random-state scramble generation."""

import numpy as np
import pytest

from cubetrainer.cube.model import (
    SOLVED,
    STICKERS,
    format_alg,
    invert_alg,
    parse_alg,
)
from cubetrainer.cube.scramble import (
    CORNER_FACELETS,
    EDGE_FACELETS,
    _permutation_parity,
    random_facelets,
    random_state_scramble,
    solve_facelets,
)


@pytest.mark.parametrize("pieces", [CORNER_FACELETS, EDGE_FACELETS])
def test_piece_tables_match_cube_geometry(pieces: tuple[tuple[int, ...], ...]) -> None:
    """Each piece's facelets sit on one cubie, and the first is on the U or D face."""
    for facelets in pieces:
        positions = {STICKERS[i][0] for i in facelets}
        assert len(positions) == 1
    for facelets in CORNER_FACELETS:
        assert facelets[0] // 9 in {0, 3}  # U or D


@pytest.mark.parametrize(
    ("perm", "parity"),
    [([0, 1, 2], 0), ([1, 0, 2], 1), ([1, 2, 0], 0), ([1, 0, 3, 2], 0)],
)
def test_permutation_parity(perm: list[int], parity: int) -> None:
    """Parity counts transpositions modulo 2."""
    assert _permutation_parity(perm) == parity


def test_solved_cube_needs_no_moves() -> None:
    """Solving an already solved cube returns an empty solution."""
    assert solve_facelets(SOLVED.facelets()) == []


def test_unsolvable_state_raises() -> None:
    """A state with a single twisted corner is rejected."""
    facelets = list(SOLVED.facelets())
    # Twist the URF corner in place (U9, R1, F3 = facelets 8, 9, 20).
    facelets[8], facelets[9], facelets[20] = facelets[20], facelets[8], facelets[9]

    with pytest.raises(ValueError, match="unsolvable"):
        solve_facelets("".join(facelets))


@pytest.mark.parametrize("seed", range(30))
def test_scramble_reproduces_random_state(seed: int) -> None:
    """Applying the inverted solution to a solved cube yields the random state."""
    facelets = random_facelets(np.random.default_rng(seed))

    scramble = invert_alg(solve_facelets(facelets))

    assert SOLVED.apply(scramble).facelets() == facelets


def test_random_states_look_uniform() -> None:
    """Every sticker colour shows up at every non-centre position across many states."""
    rng = np.random.default_rng(0)
    seen: list[set[str]] = [set() for _ in range(54)]
    for _ in range(300):
        for i, colour in enumerate(random_facelets(rng)):
            seen[i].add(colour)

    for i, colours in enumerate(seen):
        assert len(colours) == (1 if i % 9 == 4 else 6)


def test_random_state_scramble_is_reasonable() -> None:
    """Scrambles parse, have a sensible length and differ from each other."""
    rng = np.random.default_rng(42)

    scrambles = [random_state_scramble(rng) for _ in range(10)]

    assert len(set(scrambles)) == 10
    for scramble in scrambles:
        moves = parse_alg(scramble)
        assert 10 <= len(moves) <= 25
        assert format_alg(moves) == scramble
