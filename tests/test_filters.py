"""Tests for case filters and case probabilities."""

from collections import Counter
from fractions import Fraction

import numpy as np
import pytest

from cubetrainer.cases.catalog import CaseStatus, load_case_set
from cubetrainer.cases.filters import (
    CaseFilter,
    MemoryTrainerPrefs,
    case_probability,
    pick_case,
)
from cubetrainer.cases.trainer import (
    CaseRecognizer,
    active_cases,
    filtered_case_scrambles,
)

PLL = load_case_set("pll")
EDGES_ONLY = frozenset({"Edges Only"})

#: Known frequency of each PLL case in real solves (out of 72, skip = 1/72).
PLL_FREQUENCY: dict[str, Fraction] = {
    case.id: Fraction(1, 18) for case in PLL.cases
} | {
    "E": Fraction(1, 36),
    "Z": Fraction(1, 36),
    "H": Fraction(1, 72),
    "Na": Fraction(1, 72),
    "Nb": Fraction(1, 72),
}


def test_default_filter_keeps_everything() -> None:
    """The default filter selects every case, with equal probability."""
    default = CaseFilter()

    assert default.matching(PLL, {}) == list(PLL.cases)
    assert not default.realistic


def test_filter_by_group_and_status() -> None:
    """A case must match both a selected group and a selected status."""
    statuses = {
        "H": CaseStatus.LEARNING,
        "Ua": CaseStatus.FINISHED,
        "T": CaseStatus.LEARNING,
    }
    case_filter = CaseFilter(
        groups=EDGES_ONLY,
        statuses=frozenset({CaseStatus.LEARNING}),
    )

    assert [c.id for c in case_filter.matching(PLL, statuses)] == ["H"]


def test_missing_status_counts_as_unlearned() -> None:
    """Cases never clicked are unlearned."""
    case_filter = CaseFilter(
        groups=EDGES_ONLY,
        statuses=frozenset({CaseStatus.UNLEARNED}),
    )

    assert [c.id for c in case_filter.matching(PLL, {"H": CaseStatus.FINISHED})] == [
        "Ua",
        "Ub",
        "Z",
    ]


@pytest.mark.parametrize(
    "case_filter",
    [
        CaseFilter(),
        CaseFilter(groups=EDGES_ONLY, statuses=frozenset(), realistic=True),
        CaseFilter(groups=frozenset(), statuses=frozenset({CaseStatus.FINISHED})),
    ],
)
def test_json_round_trip(case_filter: CaseFilter) -> None:
    """Filters survive being saved and loaded."""
    assert CaseFilter.from_json(case_filter.to_json()) == case_filter


def test_pll_probabilities_are_the_known_ones() -> None:
    """Each PLL comes up as often as in real solves; with the skip they add to 1."""
    probabilities = {case.id: case_probability(case) for case in PLL.cases}

    assert probabilities == PLL_FREQUENCY
    assert sum(probabilities.values()) + Fraction(1, 72) == 1


def test_oll_probabilities_are_the_known_ones() -> None:
    """OLL 20 is 1/216; 1, 21, 55, 56 and 57 are 1/108; the rest 1/54."""
    probabilities = {
        case.id: case_probability(case) for case in load_case_set("oll").cases
    }

    rare = {"20": Fraction(1, 216)} | dict.fromkeys(
        ["1", "21", "55", "56", "57"],
        Fraction(1, 108),
    )
    assert probabilities == {
        cid: rare.get(cid, Fraction(1, 54)) for cid in probabilities
    }
    assert sum(probabilities.values()) + Fraction(1, 216) == 1


@pytest.mark.parametrize(
    ("set_id", "expected"),
    [
        (
            "oll2",
            {"dot": Fraction(1, 8), "l": Fraction(1, 2), "line": Fraction(1, 4)}
            | dict.fromkeys(
                ["sune", "antisune", "pi", "headlights", "chameleon", "bowtie"],
                Fraction(4, 27),
            )
            | {"h": Fraction(2, 27)},
        ),
        (
            "pll2",
            {
                "headlights": Fraction(2, 3),
                "diagonal": Fraction(1, 6),
                "ua": Fraction(1, 3),
                "ub": Fraction(1, 3),
                "z": Fraction(1, 6),
                "h": Fraction(1, 12),
            },
        ),
    ],
)
def test_two_look_probabilities_are_per_look(
    set_id: str,
    expected: dict[str, Fraction],
) -> None:
    """In 2-look sets each case's odds are within its own look."""
    probabilities = {c.id: case_probability(c) for c in load_case_set(set_id).cases}

    assert probabilities == expected


def test_realistic_picks_follow_the_weights() -> None:
    """Over many picks, H (weight 4) comes up about a quarter as often as T (16)."""
    rng = np.random.default_rng(0)
    cases = [c for c in PLL.cases if c.id in {"H", "T"}]

    counts = Counter(pick_case(cases, rng, realistic=True).id for _ in range(5_000))

    assert counts["H"] / 5_000 == pytest.approx(0.2, abs=0.03)


def test_equal_picks_are_even() -> None:
    """With equal probability, H and T come up about as often."""
    rng = np.random.default_rng(0)
    cases = [c for c in PLL.cases if c.id in {"H", "T"}]

    counts = Counter(pick_case(cases, rng, realistic=False).id for _ in range(5_000))

    assert counts["H"] / 5_000 == pytest.approx(0.5, abs=0.03)


def test_active_cases_fall_back_to_the_whole_set() -> None:
    """If nothing matches (e.g. statuses changed), the trainer uses every case."""
    prefs = MemoryTrainerPrefs(
        case_filter=CaseFilter(statuses=frozenset({CaseStatus.FINISHED})),
    )

    cases, fell_back = active_cases(PLL, prefs)

    assert fell_back
    assert cases == list(PLL.cases)


def test_generated_scrambles_respect_the_filter() -> None:
    """Scrambles only set up cases that pass the filter, read on every call."""
    prefs = MemoryTrainerPrefs(case_filter=CaseFilter(groups=EDGES_ONLY))
    generate = filtered_case_scrambles(PLL, prefs, np.random.default_rng(2))
    recognizer = CaseRecognizer(PLL)

    seen = {recognizer.recognize(generate()) for _ in range(60)}
    assert {case.id for case in seen if case} == {"H", "Ua", "Ub", "Z"}

    prefs.save_filter(CaseFilter(groups=frozenset({"Diagonal Corner Swap"})))
    seen = {recognizer.recognize(generate()) for _ in range(20)}
    assert {case.group for case in seen if case} == {"Diagonal Corner Swap"}
