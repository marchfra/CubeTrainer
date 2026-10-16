"""Tests for the OLL set: algorithms, recognition, scrambles and images."""

import numpy as np
import pytest

from cubetrainer.cases.catalog import Case, CaseKind, load_case_set
from cubetrainer.cases.recognition import (
    case_key,
    is_f2l_solved,
    is_oll_solved,
    oll_key,
    pll_key,
)
from cubetrainer.cases.trainer import CaseRecognizer, case_scramble, random_pll_state
from cubetrainer.cube.model import SOLVED, Move, parse_alg, state_solved_by

OLL = load_case_set("oll")
OLL_KEYS: dict[str, str] = {case.id: oll_key(case.state()) for case in OLL.cases}
RECOGNIZER = CaseRecognizer(OLL)


def oriented(case: Case) -> tuple[int, int]:
    """Count the edges and corners whose U sticker already faces up.

    Args:
        case: An OLL case.

    Returns:
        (oriented edges, oriented corners), ignoring the centre.

    """
    facelets = case.state().facelets()
    edges = sum(facelets[i] == "U" for i in (1, 3, 5, 7))
    corners = sum(facelets[i] == "U" for i in (0, 2, 6, 8))
    return edges, corners


def test_oll_set_contents() -> None:
    """57 cases, OLL 1 to 57, all of the OLL kind."""
    assert OLL.kind is CaseKind.OLL
    assert [case.id for case in OLL.cases] == [str(n) for n in range(1, 58)]
    assert {case.kind for case in OLL.cases} == {CaseKind.OLL}


@pytest.mark.parametrize("case", OLL.cases, ids=lambda c: c.id)
def test_alg_solves_an_oll(case: Case) -> None:
    """Each algorithm keeps F2L, and its case has the U face unsolved."""
    state = case.state()

    assert is_f2l_solved(state)
    assert not is_oll_solved(state)
    assert state.apply(parse_alg(case.alg)).is_solved()


def test_all_cases_are_distinct() -> None:
    """The 57 algorithms orient 57 different cases, none of them an OLL skip."""
    assert len(set(OLL_KEYS.values())) == 57
    assert oll_key(SOLVED) not in OLL_KEYS.values()


@pytest.mark.parametrize(
    ("numbers", "edges", "corners"),
    [
        ((1, 2), 0, 0),
        ((3, 4), 0, 1),
        ((17, 18, 19), 0, 2),
        ((20,), 0, 4),
        ((21, 22), 4, 0),
        ((23, 24, 25), 4, 2),
        ((26, 27), 4, 1),
        ((28, 57), 2, 4),
        ((47, 48, 49, 50, 51, 52, 53, 54, 55, 56), 2, 0),
        (tuple(range(5, 17)), 2, 1),
        (tuple(range(29, 47)), 2, 2),
    ],
)
def test_cases_have_the_textbook_orientation(
    numbers: tuple[int, ...],
    edges: int,
    corners: int,
) -> None:
    """Each numbered case has the known number of oriented edges and corners."""
    for number in numbers:
        assert oriented(OLL.cases[number - 1]) == (edges, corners), number


def test_line_shapes_have_opposite_edges() -> None:
    """In the Line shapes the two oriented edges face each other."""
    for case in OLL.cases:
        if case.group == "Line":
            facelets = case.state().facelets()
            up = {i for i in (1, 3, 5, 7) if facelets[i] == "U"}
            assert up in ({1, 7}, {3, 5}), case.id


def test_oll_key_ignores_pre_auf_and_permutation() -> None:
    """A U turn before the case, or a PLL after it, doesn't change the key."""
    sune = next(c for c in OLL.cases if c.id == "27")
    t_perm = parse_alg("R U R' U' R' F R2 U' R' U' R U R' F'")
    variant = SOLVED.apply(t_perm).followed_by(
        state_solved_by(parse_alg(sune.alg), before=[Move("U", 1)]),
    )

    assert oll_key(variant) == OLL_KEYS["27"]


def test_case_key_by_kind() -> None:
    """case_key picks the right recognition and rejects broken states."""
    sune_state = next(c for c in OLL.cases if c.id == "27").state()

    assert case_key(CaseKind.OLL, sune_state) == OLL_KEYS["27"]
    assert case_key(CaseKind.PLL, sune_state) is None  # U face not solved
    assert case_key(CaseKind.OLL, SOLVED.apply_alg("R")) is None
    with pytest.raises(ValueError, match="F2L"):
        oll_key(SOLVED.apply_alg("R"))


def test_random_pll_states_are_varied_plls() -> None:
    """Random permutations keep OLL solved and cover many PLL cases."""
    rng = np.random.default_rng(4)

    states = [random_pll_state(rng) for _ in range(200)]

    assert all(is_oll_solved(state) for state in states)
    assert len({pll_key(state) for state in states}) >= 15


@pytest.mark.parametrize("case", OLL.cases[::4], ids=lambda c: c.id)
def test_oll_scrambles_set_up_their_case(case: Case) -> None:
    """OLL scrambles keep F2L and are recognised as the intended case."""
    rng = np.random.default_rng(int(case.id))
    for _ in range(3):
        assert RECOGNIZER.recognize(case_scramble(case, rng)) is case


def test_oll_scrambles_have_random_permutations() -> None:
    """After the OLL algorithm the PLL varies, as in a real solve."""
    sune = next(c for c in OLL.cases if c.id == "27")
    rng = np.random.default_rng(9)
    plls = set()
    for _ in range(25):
        state = SOLVED.apply_alg(case_scramble(sune, rng))
        for turns in range(4):
            before = [Move("U", turns)] if turns else []
            solved = state.apply([*before, *parse_alg(sune.alg)])
            if is_oll_solved(solved):
                plls.add(pll_key(solved))
                break

    assert len(plls) >= 8


#: Algorithms from the SpeedSolving wiki's OLL page (fetched 2026-10-16), some with a
#: U turn or y rotation in front. Each must land on the case with the same number,
#: independently confirming the bundled numbering.
REFERENCE_ALGS: dict[str, str] = {
    "1": "R U2' R2' F R F' U2 R' F R F'",
    "2": "(U') R U' R2' D' r U r' D R2 U R'",
    "3": "(U) f (R U R' U') f' U' F (R U R' U') F'",
    "4": "f R U R' U' f' U F R U R' U' F'",
    "5": "(U2) l' U2 L U L' U l",
    "6": "(U2) r U2 R' U' R U' r'",
    "7": "r U R' U R U2 r'",
    "8": "l' U' L U' L' U2 l",
    "9": "(U') R U R' U' R' F R2 U R' U' F'",
    "10": "(U') R U R' U R' F R F' R U2' R'",
    "11": "(U') r' R2 U R' U R U2' R' U M'",
    "12": "(U') r R2' U' R U' R' U2 R U' r' R",
    "13": "F U R U2' R' U' R U R' F'",
    "14": "R' F R U R' F' R F U' F'",
    "15": "(U2) l' U' l L' U' L U l' U l",
    "16": "(U2) r U r' R U R' U' r U' r'",
    "17": "R U R' U R' F R F' U2 R' F R F'",
    "18": "R U2 R2 F R F' U2 M' U R U' r'",
    "19": "S' R U R' S U' R' F R F'",
    "20": "r' R U R U R' U' r R' M' U R U' r'",
    "21": "R U R' U R U' R' U R U2 R'",
    "22": "R U2' R2' U' R2 U' R2' U2' R",
    "23": "R2' D' R U2 R' D R U2 R",
    "24": "r U R' U' r' F R F'",
    "25": "(U2) F R' F' r U R U' r'",
    "26": "(y') R U2 R' U' R U' R'",
    "27": "R U R' U R U2' R'",
    "28": "r U R' U' r' R U R U' R'",
    "29": "(U) R U R' U' R U' R' F' U' F R U R'",
    "30": "(U2) F U R U2' R' U' R U2 R' U' F'",
    "31": "(U2) R' U' F U R U' R' F' R",
    "32": "S R U R' U' R' F R f'",
    "33": "R U R' U' R' F R F'",
    "34": "R U R2' U' R' F R U R U' F'",
    "35": "R U2' R2' F R F' R U2' R'",
    "36": "(U2) L' U' L U' L' U L U L F' L' F",
    "37": "(U) F R' F' R U R U' R'",
    "38": "(U2) R U R' U R U' R' U' R' F R F'",
    "39": "L F' L' U' L U F U' L'",
    "40": "R' F R U R' U' F' U R",
    "41": "(U2) R U R' U R U2 R' F R U R' U' F'",
    "42": "R' U' R U' R' U2' R F R U R' U' F'",
    "43": "(U) R' U' F' U F R",
    "44": "(U2) F (U R U' R') F'",
    "45": "F R U R' U' F'",
    "46": "R' U' R' F R F' U R",
    "47": "(U') F R' F' R U2 R U' R' U R U2' R'",
    "48": "F R U R' U' R U R' U' F'",
    "49": "(U2) r U' r2' U r2 U r2' U' r",
    "50": "(U2) R' F R2 B' R2' F' R2 B R'",
    "51": "F U R U' R' U R U' R' F'",
    "52": "R U R' U R U' B U' B' R'",
    "53": "l' U' L U' L' U L U' L' U2 l",
    "54": "r U R' U R U' R' U R U2' r'",
    "55": "(U) R' F R U R U' R2' F' R2 U' R' U R U R'",
    "56": "r U r' U R U' R' U R U' R' r U' r'",
    "57": "R U R' U' M' U R U' r'",
}


@pytest.mark.parametrize("number", sorted(REFERENCE_ALGS, key=int))
def test_reference_alg_solves_same_numbered_case(number: str) -> None:
    """A reference algorithm for OLL n solves the bundled OLL n."""
    state = state_solved_by(parse_alg(REFERENCE_ALGS[number]))

    assert oll_key(state) == OLL_KEYS[number]


def test_default_algs_use_balanced_brackets() -> None:
    """Groups in the bundled algorithms are well formed: no stray or nested brackets."""
    for case in OLL.cases:
        depth = 0
        for char in case.alg:
            depth += {"(": 1, ")": -1}.get(char, 0)
            assert depth in {0, 1}, case.id
        assert depth == 0, case.id
