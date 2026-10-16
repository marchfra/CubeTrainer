"""Tests for averages, means and bests."""

import math

import pytest

from cubetrainer import stats
from cubetrainer.solves import Solve

DNF = math.inf


@pytest.mark.parametrize(
    ("n", "trimmed"),
    [(3, 1), (5, 1), (12, 1), (20, 1), (21, 2), (50, 3), (100, 5), (1000, 50)],
)
def test_trim_count_drops_five_percent_rounded_up(n: int, trimmed: int) -> None:
    """Each end loses ceil(5%) of the results, like cstimer."""
    assert stats.trim_count(n) == trimmed


def test_ao5_drops_best_and_worst() -> None:
    """ao5 is the mean of the middle three."""
    assert stats.average_of([10_000, 12_000, 11_000, 9_000, 20_000]) == 11_000


def test_ao5_with_one_dnf_counts_it_as_worst() -> None:
    """A single DNF is trimmed away as the worst result."""
    assert stats.average_of([10_000, 12_000, DNF, 9_000, 11_000]) == 11_000


def test_ao5_with_two_dnfs_is_dnf() -> None:
    """Two DNFs can't both be trimmed, so the average is a DNF."""
    assert stats.average_of([10_000, DNF, DNF, 9_000, 11_000]) == DNF


def test_ao12_hand_computed() -> None:
    """ao12 drops one best and one worst and averages the other ten."""
    values = [float(v) for v in range(1_000, 13_000, 1_000)]  # 1..12 seconds

    assert stats.average_of(values) == pytest.approx(6_500)


def test_average_needs_three_results() -> None:
    """Fewer than three results can't be averaged."""
    with pytest.raises(ValueError, match="at least 3"):
        stats.average_of([1.0, 2.0])


def test_rolling_averages_start_after_n_solves() -> None:
    """Rolling ao5 is missing for the first four solves, then slides along."""
    values = [5_000.0, 6_000, 7_000, 8_000, 9_000, 1_000]

    rolling = stats.rolling_averages(values, 5)

    assert rolling[:4] == [None, None, None, None]
    assert rolling[4] == 7_000
    assert rolling[5] == 7_000  # 6,7,8,9,1 -> drop 1 and 9


def test_best_and_current_average() -> None:
    """Best is the minimum rolling average; current is the last one."""
    values = [9_000.0, 9_000, 9_000, 9_000, 9_000, 20_000, 20_000, 20_000]

    assert stats.best_average(values, 5) == 9_000
    assert stats.current_average(values, 5) == pytest.approx(49_000 / 3)


def test_averages_missing_without_enough_solves() -> None:
    """Best and current averages are None until there are enough solves."""
    assert stats.best_average([1.0, 2.0], 5) is None
    assert stats.current_average([1.0, 2.0], 5) is None


def test_best_single() -> None:
    """Best single ignores DNFs unless everything is a DNF."""
    assert stats.best_single([12_000, DNF, 9_500]) == 9_500
    assert stats.best_single([DNF, DNF]) == DNF
    assert stats.best_single([]) is None


def test_mean_excludes_dnfs() -> None:
    """The session mean is over finished solves only."""
    assert stats.mean_excluding_dnf([10_000, DNF, 12_000]) == 11_000
    assert stats.mean_excluding_dnf([DNF]) is None
    assert stats.mean_excluding_dnf([]) is None


def trainer_solve(
    case_id: str,
    ms: int,
    *,
    mistake: bool = False,
    hints: int = 0,
) -> Solve:
    """Build a trainer solve.

    Args:
        case_id: The case.
        ms: The time in milliseconds.
        mistake: Whether it's marked as a mistake.
        hints: Hint steps used.

    Returns:
        The solve.

    """
    return Solve(ms, "", case_id=case_id, mistake=mistake, hints=hints)


def test_case_stats_leave_out_mistakes_but_count_them() -> None:
    """Best, mean and ao5 ignore mistakes; the count and rates include them."""
    solves = [
        trainer_solve("T", 3_000),
        trainer_solve("T", 1_000, mistake=True),
        trainer_solve("T", 2_000, hints=2),
        trainer_solve("Ua", 5_000),
        Solve(9_000, ""),  # no case: ignored
    ]

    by_case = stats.case_stats(solves)

    assert set(by_case) == {"T", "Ua"}
    t = by_case["T"]
    assert (t.count, t.best, t.mean, t.current_average) == (3, 2_000, 2_500, None)
    assert t.mistake_rate == pytest.approx(1 / 3)
    assert t.hint_rate == pytest.approx(1 / 3)
    assert by_case["Ua"].count == 1


def test_case_ao5_uses_the_last_five_clean_solves() -> None:
    """A mistake in the middle doesn't break the case's ao5."""
    times = [1_000, 2_000, 3_000, 4_000, 5_000]
    solves = [trainer_solve("T", ms) for ms in times[:2]]
    solves.append(trainer_solve("T", 100, mistake=True))
    solves.extend(trainer_solve("T", ms) for ms in times[2:])

    assert stats.case_stats(solves)["T"].current_average == 3_000


def test_case_stats_with_only_mistakes() -> None:
    """A case with nothing but mistakes has no times."""
    by_case = stats.case_stats([trainer_solve("T", 1_000, mistake=True)])

    assert (by_case["T"].best, by_case["T"].mean) == (None, None)
    assert by_case["T"].mistake_rate == 1.0
