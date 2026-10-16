"""Tests for case scrambles and recognising cases from scrambles."""

from collections import Counter

import numpy as np
import pytest

from cubetrainer.cases.catalog import Case, load_case_set
from cubetrainer.cases.recognition import is_oll_solved
from cubetrainer.cases.trainer import (
    CaseRecognizer,
    case_scramble,
    uniform_case_scrambles,
)
from cubetrainer.cube.model import SOLVED, Move, parse_alg

PLL = load_case_set("pll")
RECOGNIZER = CaseRecognizer(PLL)


@pytest.mark.parametrize("case", PLL.cases, ids=lambda c: c.id)
def test_case_scrambles_set_up_their_case(case: Case) -> None:
    """Scrambles (with random AUFs) leave F2L solved and are recognised as the case.

    This includes algorithms that start with a rotation (Aa, Ab, E, Ja), whose AUFs
    have to be done in the standard orientation.
    """
    rng = np.random.default_rng(hash(case.id) % 2**32)
    for _ in range(16):
        scramble = case_scramble(case, rng)
        state = SOLVED.apply(parse_alg(scramble))

        assert is_oll_solved(state)
        assert RECOGNIZER.recognize(scramble) is case


@pytest.mark.parametrize("case", PLL.cases, ids=lambda c: c.id)
def test_alg_solves_the_scramble_up_to_aufs(case: Case) -> None:
    """After the scramble, some U turn, the algorithm and some U turn solve the cube."""
    scramble = parse_alg(case_scramble(case, np.random.default_rng(7)))
    alg = parse_alg(case.alg)
    scrambled = SOLVED.apply(scramble)
    pre_aufs: list[list[Move]] = [[], *([Move("U", turns)] for turns in (1, 2, 3))]
    # After e.g. "x L2 D2 ..." the cube is held rotated, so the last layer may be on
    # any face: allow a final turn of any face. is_solved accepts the rotation.
    post_aufs: list[list[Move]] = [[]] + [
        [Move(face, turns)] for face in "URFDLB" for turns in (1, 2, 3)
    ]

    assert any(
        scrambled.apply([*pre, *alg, *post]).is_solved()
        for pre in pre_aufs
        for post in post_aufs
    )


def test_recognizer_rejects_other_scrambles() -> None:
    """A scramble that breaks F2L, or solves the cube, isn't one of the cases."""
    assert RECOGNIZER.recognize("R U R' U'") is None
    assert RECOGNIZER.recognize("") is None


def test_uniform_generator_covers_the_set() -> None:
    """Uniform picking reaches every case and favours none of them."""
    generate = uniform_case_scrambles(PLL, np.random.default_rng(1))

    counts = Counter(RECOGNIZER.recognize(generate()) for _ in range(420))

    assert None not in counts
    assert len(counts) == 21
    assert max(counts.values()) < 3 * min(counts.values())
