"""Tests for averages, means and bests."""

import math

import pytest

from cubetrainer import stats

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
