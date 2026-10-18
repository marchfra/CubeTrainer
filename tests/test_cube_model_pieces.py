"""Tests for splitting an algorithm into shown and hidden display pieces."""

import pytest

from cubetrainer.cube.model import alg_pieces, reveal_alg

ALG = "(R U R' U') (R' F R2 U') (R' U' R U) (R' F')"


@pytest.mark.parametrize("moves", [0, 1, 4, 5, 13, 14])
def test_pieces_keep_the_whole_algorithm_and_reveal_the_start(moves: int) -> None:
    """Joined, the pieces are always the whole algorithm; the shown ones its start."""
    pieces = alg_pieces(ALG, moves)

    assert "".join(text for text, _ in pieces) == reveal_alg(ALG, 99)
    assert "".join(text for text, shown in pieces if shown).strip() == reveal_alg(
        ALG,
        moves,
    )


def test_masked_text_has_the_same_shape() -> None:
    """Masking hidden pieces keeps every space where it is, so lines wrap alike."""
    full = reveal_alg(ALG, 99)
    for moves in range(15):
        masked = "".join(
            text if shown else "".join(" " if c == " " else "·" for c in text)
            for text, shown in alg_pieces(ALG, moves)
        )
        assert [i for i, c in enumerate(masked) if c == " "] == [
            i for i, c in enumerate(full) if c == " "
        ]
