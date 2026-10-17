"""Tests for case filters and case probabilities."""

import math
from collections import Counter
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import numpy as np
import pytest

from cubetrainer.cases.catalog import Case, CaseStatus, load_case_set
from cubetrainer.cases.filters import (
    RECENT_SOLVES,
    CaseFilter,
    MemoryTrainerPrefs,
    Odds,
    case_probability,
    pick_case,
    slowness_weights,
)
from cubetrainer.cases.trainer import (
    CaseRecognizer,
    active_cases,
    filtered_case_scrambles,
)
from cubetrainer.solves import Penalty, Solve

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
    assert default.odds is Odds.EQUAL


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
        CaseFilter(groups=EDGES_ONLY, statuses=frozenset(), odds=Odds.REALISTIC),
        CaseFilter(groups=frozenset(), statuses=frozenset({CaseStatus.FINISHED})),
        CaseFilter(odds=Odds.SLOWEST),
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

    counts = Counter(pick_case(cases, rng, Odds.REALISTIC).id for _ in range(5_000))

    assert counts["H"] / 5_000 == pytest.approx(0.2, abs=0.03)


def test_equal_picks_are_even() -> None:
    """With equal probability, H and T come up about as often."""
    rng = np.random.default_rng(0)
    cases = [c for c in PLL.cases if c.id in {"H", "T"}]

    counts = Counter(pick_case(cases, rng, Odds.EQUAL).id for _ in range(5_000))

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


def test_filters_saved_before_slowest_first_still_load() -> None:
    """Old filters stored a "realistic" flag instead of the odds."""
    old = '{"groups": null, "statuses": ["learning"], "realistic": %s}'

    assert CaseFilter.from_json(old % "true").odds is Odds.REALISTIC
    assert CaseFilter.from_json(old % "false").odds is Odds.EQUAL


START = datetime(2026, 10, 1, tzinfo=UTC)


def history_of(*runs: tuple[str, list[float]], mistakes: int = 0) -> list[Solve]:
    """Build trainer solves, a minute apart, oldest first.

    Args:
        runs: (case id, times in seconds; ``math.inf`` for a DNF) for each case.
        mistakes: How many of each case's last solves are mistakes.

    Returns:
        The solves, every case's in a row.

    """
    solves: list[Solve] = []
    for case_id, seconds in runs:
        for i, value in enumerate(seconds):
            solves.append(
                Solve(
                    int(value * 1000) if math.isfinite(value) else 5_000,
                    "",
                    Penalty.OK if math.isfinite(value) else Penalty.DNF,
                    START + timedelta(minutes=len(solves)),
                    case_id=case_id,
                    mistake=i >= len(seconds) - mistakes,
                ),
            )
    return solves


def cases_of(*ids: str) -> list[Case]:
    """Return PLL cases by id.

    Args:
        ids: The case ids.

    Returns:
        The cases, in the given order.

    """
    by_id = {case.id: case for case in PLL.cases}
    return [by_id[case_id] for case_id in ids]


def test_slowness_is_the_squared_mean_time() -> None:
    """A case twice as slow weighs four times as much."""
    history = history_of(("T", [2.0, 2.0, 2.0]), ("H", [4.0, 4.0, 4.0]))

    weights = slowness_weights(cases_of("T", "H"), history)

    assert weights.tolist() == pytest.approx([4.0, 16.0])


def test_slowness_uses_the_latest_solves_only() -> None:
    """Only the last 12 solves count, so improving a case lowers its weight."""
    history = history_of(("T", [10.0] * 20 + [2.0] * RECENT_SOLVES))

    assert slowness_weights(cases_of("T"), history).tolist() == pytest.approx([4.0])


def test_mistakes_add_weight_and_are_left_out_of_the_mean() -> None:
    """Mistakes (and DNFs) don't count as times; mistakes raise the weight."""
    times = [2.0, 2.0, math.inf, 2.0, 9.0, 9.0]  # the two 9.0 are mistakes
    history = history_of(("T", times), mistakes=2)

    weights = slowness_weights(cases_of("T"), history)

    assert weights.tolist() == pytest.approx([4.0 * (1 + 2 / 6)])


def test_cases_without_enough_times_count_as_the_slowest() -> None:
    """Cases with fewer than three timed solves get the largest weight."""
    history = history_of(
        ("T", [2.0, 2.0, 2.0]),
        ("H", [3.0, 3.0, 3.0]),
        ("Z", [1.0, 1.0]),
    )

    weights = slowness_weights(cases_of("T", "H", "Z", "Ua"), history)

    assert weights.tolist() == pytest.approx([4.0, 9.0, 9.0, 9.0])


def test_without_any_times_slowest_first_is_equal() -> None:
    """With no rated case every case weighs the same."""
    assert slowness_weights(cases_of("T", "H"), []).tolist() == [1.0, 1.0]


def test_slowest_first_picks_follow_the_weights() -> None:
    """H, three times as slow as T, comes up nine times as often."""
    rng = np.random.default_rng(0)
    history = history_of(("T", [1.0] * 5), ("H", [3.0] * 5))
    cases = cases_of("T", "H")

    counts = Counter(
        pick_case(cases, rng, Odds.SLOWEST, history).id for _ in range(5_000)
    )

    assert counts["H"] / 5_000 == pytest.approx(0.9, abs=0.02)


def test_generated_scrambles_favour_slow_cases() -> None:
    """The generator reads the history on each call and picks slow cases more."""
    prefs = MemoryTrainerPrefs(case_filter=CaseFilter(odds=Odds.SLOWEST))
    times = [(case.id, [1.0] * 3) for case in PLL.cases if case.id != "H"]
    history = history_of(*times, ("H", [5.0] * 3))
    generate = filtered_case_scrambles(
        PLL,
        prefs,
        np.random.default_rng(4),
        history=lambda: history,
    )
    recognizer = CaseRecognizer(PLL)

    picked = Counter(recognizer.recognize(generate()) for _ in range(40))

    # H weighs 25 against 1 for each of the other 20 cases: about 56% of picks.
    assert picked[next(c for c in PLL.cases if c.id == "H")] >= 15
