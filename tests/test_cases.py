"""Tests for the bundled PLL set: every algorithm must really solve its named case."""

import pytest

from cubetrainer.cases.catalog import Case, CaseStatus, load_case_set
from cubetrainer.cases.recognition import is_f2l_solved, is_oll_solved, pll_key
from cubetrainer.cube.model import SOLVED, CubeState, parse_alg, state_solved_by

PLL = load_case_set("pll")
PLL_KEYS: dict[str, str] = {case.id: pll_key(case.state()) for case in PLL.cases}

#: Independent, well-known algorithms for many cases (mostly from other sources than
#: the bundled defaults). If both land on the same case, the default is named right.
ALTERNATIVE_ALGS: dict[str, str] = {
    "Aa": "x R' U R' D2 R U' R' D2 R2",
    "Ab": "x R2 D2 R U R' D2 R U' R",
    "E": "x' R U' R' D R U R' D' R U R' D R U' R' D'",
    "H": "R2 U2 R U2 R2 U2 R2 U2 R U2 R2",
    "Ja": "R' U L' U2 R U' R' U2 R L",
    "Jb": "R U2 R' U' R U2 L' U R' U' L",
    "Na": "L U' R U2 L' U R' L U' R U2 L' U R'",
    "Nb": "R' U L' U2 R U' L R' U L' U2 R U' L",
    "Ra": "R U R' F' R U2 R' U2 R' F R U R U2 R'",
    "Rb": "R' U2 R U2 R' F R U R' U' R' F' R2",
    "Ua": "R U' R U R U R U' R' U' R2",
    "Ub": "R2 U R U R' U' R' U' R' U R'",
    "V": "R' U R' d' R' F' R2 U' R' U R' F R F",
    "Z": "M2 U M2 U M' U2 M2 U2 M' U2",
}

#: Each case's inverse permutation; cases not listed are their own inverse.
INVERSE_CASE: dict[str, str] = {
    "Aa": "Ab",
    "Ab": "Aa",
    "Ga": "Gb",
    "Gb": "Ga",
    "Gc": "Gd",
    "Gd": "Gc",
    "Ua": "Ub",
    "Ub": "Ua",
}


def inverse_state(state: CubeState) -> CubeState:
    """Return the state with the inverse sticker permutation.

    Args:
        state: A cube state.

    Returns:
        The inverse state.

    """
    inverse = [0] * len(state.stickers)
    for position, sticker in enumerate(state.stickers):
        inverse[sticker] = position
    return CubeState(tuple(inverse))


def test_pll_set_contents() -> None:
    """The set has the 21 PLLs with unique ids, in three groups."""
    assert len(PLL.cases) == 21
    assert len({case.id for case in PLL.cases}) == 21
    assert PLL.groups == [
        "Adjacent Corner Swap",
        "Diagonal Corner Swap",
        "Edges Only",
    ]


@pytest.mark.parametrize("case", PLL.cases, ids=lambda c: c.id)
def test_alg_solves_a_pll(case: Case) -> None:
    """Each case is a genuine PLL that its algorithm solves."""
    state = case.state()

    assert is_oll_solved(state)
    assert not state.is_solved()
    assert state.apply(parse_alg(case.alg)).is_solved()


def test_all_cases_are_distinct() -> None:
    """The 21 algorithms solve 21 different cases, none of them a PLL skip."""
    assert len(set(PLL_KEYS.values())) == 21
    assert pll_key(SOLVED) not in PLL_KEYS.values()


@pytest.mark.parametrize("case_id", sorted(ALTERNATIVE_ALGS))
def test_alternative_alg_solves_same_case(case_id: str) -> None:
    """An independent algorithm for the case solves the same case."""
    state = state_solved_by(parse_alg(ALTERNATIVE_ALGS[case_id]))

    assert pll_key(state) == PLL_KEYS[case_id]


@pytest.mark.parametrize("case", PLL.cases, ids=lambda c: c.id)
def test_inverse_relations(case: Case) -> None:
    """A/G/U perms come in inverse pairs; every other PLL is its own inverse."""
    expected = INVERSE_CASE.get(case.id, case.id)

    assert pll_key(inverse_state(case.state())) == PLL_KEYS[expected]


def test_pll_key_ignores_aufs() -> None:
    """Turning U before and after a case doesn't change its key."""
    t_perm = parse_alg(next(c.alg for c in PLL.cases if c.id == "T"))
    with_aufs = state_solved_by([*parse_alg("U"), *t_perm, *parse_alg("U2")])

    assert pll_key(with_aufs) == PLL_KEYS["T"]


def test_pll_key_rejects_non_pll() -> None:
    """States with an unsolved U face or F2L aren't PLLs."""
    with pytest.raises(ValueError, match="OLL solved"):
        pll_key(SOLVED.apply_alg("R U R' U'"))


def test_f2l_check() -> None:
    """F2L is intact after U turns but not after an R turn."""
    assert is_f2l_solved(SOLVED.apply_alg("U2"))
    assert not is_f2l_solved(SOLVED.apply_alg("R"))


def test_status_cycle() -> None:
    """Clicking cycles unlearned → learning → finished → unlearned."""
    assert CaseStatus.UNLEARNED.next() is CaseStatus.LEARNING
    assert CaseStatus.LEARNING.next() is CaseStatus.FINISHED
    assert CaseStatus.FINISHED.next() is CaseStatus.UNLEARNED
