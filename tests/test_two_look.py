"""Tests for the 2-look OLL and 2-look PLL sets."""

import numpy as np
import pytest

from cubetrainer.cases.catalog import Case, CaseKind, load_case_set
from cubetrainer.cases.recognition import (
    case_key,
    cp_key,
    edges_oriented,
    eo_key,
    is_f2l_solved,
    is_oll_solved,
    oll_key,
    pll_key,
)
from cubetrainer.cases.trainer import CaseRecognizer, case_scramble
from cubetrainer.cube.model import SOLVED, Move, parse_alg

OLL2 = load_case_set("oll2")
PLL2 = load_case_set("pll2")
ALL_CASES = [*OLL2.cases, *PLL2.cases]


def by_id(case_set_id: str, case_id: str) -> Case:
    """Return a bundled case.

    Args:
        case_set_id: The set.
        case_id: The case.

    Returns:
        The case.

    """
    return next(c for c in load_case_set(case_set_id).cases if c.id == case_id)


def test_sets_mix_two_kinds() -> None:
    """Each 2-look set has one look per group."""
    assert {(c.group, c.kind) for c in OLL2.cases} == {
        ("Edges", CaseKind.EO),
        ("Corners", CaseKind.CO),
    }
    assert {(c.group, c.kind) for c in PLL2.cases} == {
        ("Corners", CaseKind.CP),
        ("Edges", CaseKind.EP),
    }
    assert (len(OLL2.cases), len(PLL2.cases)) == (10, 6)


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.id)
def test_alg_solves_its_look(case: Case) -> None:
    """Each algorithm keeps F2L, solves its case, and the case is of its kind."""
    state = case.state()

    assert is_f2l_solved(state)
    assert state.apply(parse_alg(case.alg)).is_solved()
    assert case_key(case.kind, state) is not None
    match case.kind:
        case CaseKind.EO:
            assert not edges_oriented(state)
        case CaseKind.CO:
            assert edges_oriented(state)
            assert not is_oll_solved(state)
        case CaseKind.CP:
            assert is_oll_solved(state)
            assert cp_key(state) != cp_key(SOLVED)
        case CaseKind.EP:
            assert cp_key(state) == cp_key(SOLVED)  # corners already solved


def test_cases_of_a_look_are_distinct() -> None:
    """No two cases of the same look are the same case."""
    for case_set in (OLL2, PLL2):
        keys = [(c.kind, case_key(c.kind, c.state())) for c in case_set.cases]
        assert len(set(keys)) == len(keys)


@pytest.mark.parametrize(
    ("two_look", "full"),
    [
        ("h", "21"),
        ("pi", "22"),
        ("headlights", "23"),
        ("chameleon", "24"),
        ("bowtie", "25"),
        ("antisune", "26"),
        ("sune", "27"),
    ],
)
def test_corner_cases_are_the_ocll(two_look: str, full: str) -> None:
    """The corner look of 2-look OLL is OLL 21 to 27."""
    assert oll_key(by_id("oll2", two_look).state()) == oll_key(
        by_id("oll", full).state(),
    )


@pytest.mark.parametrize("case_id", ["ua", "ub", "h", "z"])
def test_edge_cases_are_the_edge_plls(case_id: str) -> None:
    """The edge look of 2-look PLL is Ua, Ub, H and Z."""
    full = {"ua": "Ua", "ub": "Ub", "h": "H", "z": "Z"}[case_id]

    assert pll_key(by_id("pll2", case_id).state()) == pll_key(
        by_id("pll", full).state(),
    )


def test_edge_orientation_cases() -> None:
    """Dot has no edges oriented; L two adjacent; Line two opposite."""
    patterns = {c.id: eo_key(c.state()) for c in OLL2.cases if c.kind is CaseKind.EO}

    assert patterns["dot"] == "0000"
    assert patterns["l"].count("1") == 2
    assert patterns["line"].count("1") == 2
    assert patterns["l"] != patterns["line"]


@pytest.mark.parametrize("case", ALL_CASES, ids=lambda c: c.id)
def test_scrambles_set_up_their_case(case: Case) -> None:
    """Scrambles are recognised as the intended case of the right look."""
    recognizer = CaseRecognizer(OLL2 if case in OLL2.cases else PLL2)
    rng = np.random.default_rng(len(case.id))

    for _ in range(3):
        assert recognizer.recognize(case_scramble(case, rng)) is case


def test_edge_look_leaves_random_corners() -> None:
    """After the Line algorithm, the corner orientation varies, as in real solves."""
    line = by_id("oll2", "line")
    rng = np.random.default_rng(3)
    corner_cases = set()
    for _ in range(25):
        state = SOLVED.apply_alg(case_scramble(line, rng))
        for turns in range(4):
            before = [Move("U", turns)] if turns else []
            done = state.apply([*before, *parse_alg(line.alg)])
            if edges_oriented(done):
                corner_cases.add(oll_key(done))
                break

    assert len(corner_cases) >= 5


def test_corner_look_leaves_random_edges() -> None:
    """After the Headlights algorithm, the edge permutation varies."""
    headlights = by_id("pll2", "headlights")
    rng = np.random.default_rng(5)
    edge_cases = set()
    for _ in range(25):
        state = SOLVED.apply_alg(case_scramble(headlights, rng))
        for turns in range(4):
            before = [Move("U", turns)] if turns else []
            done = state.apply([*before, *parse_alg(headlights.alg)])
            if is_oll_solved(done) and cp_key(done) == cp_key(SOLVED):
                edge_cases.add(pll_key(done))
                break

    assert len(edge_cases) >= 3


def test_looks_are_recognised_apart() -> None:
    """A corner-look state isn't mistaken for an edge-look case, and vice versa."""
    recognizer = CaseRecognizer(OLL2)
    sune = by_id("oll2", "sune")
    line = by_id("oll2", "line")
    rng = np.random.default_rng(8)

    assert recognizer.recognize(case_scramble(sune, rng)) is sune
    assert recognizer.recognize(case_scramble(line, rng)) is line
    assert recognizer.recognize("") is None
