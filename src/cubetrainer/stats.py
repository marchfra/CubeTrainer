"""Solve statistics: cstimer/WCA-style averages, means and bests.

Values are times in milliseconds with penalties applied, where ``math.inf`` stands for
a DNF. That makes DNFs sort as the worst result and turn any mean containing them into
a DNF automatically. ``None`` means "not enough solves".
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np

from cubetrainer.solves import Solve


def trim_count(n: int) -> int:
    """Return how many results are dropped from each end of an average of ``n``.

    This follows cstimer: 5% rounded up on each side, so ao5 and ao12 drop one best and
    one worst, ao50 drops three and ao100 drops five.

    Args:
        n: Number of results in the average.

    Returns:
        The number trimmed from each end.

    """
    return math.ceil(n / 20)


def average_of(values: Sequence[float]) -> float:
    """Compute a trimmed average of all ``values``.

    Args:
        values: At least three results (``math.inf`` for DNF).

    Returns:
        The average, or ``math.inf`` if too many DNFs remain after trimming.

    Raises:
        ValueError: If fewer than three values are given.

    """
    n = len(values)
    if n < 3:  # noqa: PLR2004 - a trimmed average needs at least one kept result
        msg = f"an average needs at least 3 results, got {n}"
        raise ValueError(msg)
    k = trim_count(n)
    kept = sorted(values)[k : n - k]
    return sum(kept) / len(kept)


def rolling_averages(values: Sequence[float], n: int) -> list[float | None]:
    """Compute the average of ``n`` ending at each solve.

    Args:
        values: Results, oldest first.
        n: Size of the average (e.g. 5 for ao5).

    Returns:
        One entry per solve: ``None`` while fewer than ``n`` solves exist, then the
        average of the last ``n`` results (``math.inf`` for a DNF average).

    """
    return [
        average_of(values[i + 1 - n : i + 1]) if i + 1 >= n else None
        for i in range(len(values))
    ]


def best_average(values: Sequence[float], n: int) -> float | None:
    """Return the best average of ``n`` consecutive results.

    Args:
        values: Results, oldest first.
        n: Size of the average.

    Returns:
        The best average, or None if there are fewer than ``n`` results.

    """
    averages = [a for a in rolling_averages(values, n) if a is not None]
    return min(averages) if averages else None


def current_average(values: Sequence[float], n: int) -> float | None:
    """Return the average of the last ``n`` results.

    Args:
        values: Results, oldest first.
        n: Size of the average.

    Returns:
        The average, or None if there are fewer than ``n`` results.

    """
    return average_of(values[-n:]) if len(values) >= n else None


def best_single(values: Sequence[float]) -> float | None:
    """Return the best single result.

    Args:
        values: Results.

    Returns:
        The minimum (``math.inf`` if every solve is a DNF), or None if empty.

    """
    return min(values) if values else None


def mean_excluding_dnf(values: Sequence[float]) -> float | None:
    """Return the plain mean of all non-DNF results (cstimer's session mean).

    Args:
        values: Results.

    Returns:
        The mean, or None if there are no successful solves.

    """
    finished = [v for v in values if math.isfinite(v)]
    return sum(finished) / len(finished) if finished else None


#: Size of the per-case rolling average shown in the trainer.
CASE_AVERAGE_SIZE: int = 5


@dataclass(frozen=True, slots=True)
class CaseStats:
    """Trainer statistics of one case.

    Times exclude solves marked as mistakes; hinted solves count normally.

    Attributes:
        count: Number of solves of the case, mistakes included.
        best: Best time of a clean solve (``math.inf`` if all DNF), None if none.
        mean: Mean of the clean, finished solves, None if there are none.
        current_average: ao5 of the last five clean solves, None if fewer.
        mistakes: Number of solves marked as mistakes.
        hinted: Number of solves where at least one hint was used.

    """

    count: int
    best: float | None
    mean: float | None
    current_average: float | None
    mistakes: int
    hinted: int

    @property
    def mistake_rate(self) -> float:
        """Fraction of the case's solves marked as mistakes."""
        return self.mistakes / self.count if self.count else 0.0

    @property
    def hint_rate(self) -> float:
        """Fraction of the case's solves that used hints."""
        return self.hinted / self.count if self.count else 0.0


def clean_values(solves: Iterable[Solve]) -> list[float]:
    """Return the values of the solves not marked as mistakes, oldest first.

    Args:
        solves: Solves, oldest first.

    Returns:
        Their statistics values (``math.inf`` for DNF), mistakes left out.

    """
    return [s.value for s in solves if not s.mistake]


def case_stats(solves: Iterable[Solve]) -> dict[str, CaseStats]:
    """Compute the statistics of every case that appears among some solves.

    Args:
        solves: Trainer solves, oldest first; those without a case are ignored.

    Returns:
        Statistics keyed by case id, for the cases that have solves.

    """
    by_case: dict[str, list[Solve]] = {}
    for solve in solves:
        if solve.case_id is not None:
            by_case.setdefault(solve.case_id, []).append(solve)
    result: dict[str, CaseStats] = {}
    for case_id, case_solves in by_case.items():
        values = clean_values(case_solves)
        result[case_id] = CaseStats(
            count=len(case_solves),
            best=best_single(values),
            mean=mean_excluding_dnf(values),
            current_average=current_average(values, CASE_AVERAGE_SIZE),
            mistakes=sum(s.mistake for s in case_solves),
            hinted=sum(s.hints > 0 for s in case_solves),
        )
    return result


#: Averages listed on the Stats page.
SUMMARY_AVERAGES: tuple[int, ...] = (5, 12, 50, 100)


@dataclass(frozen=True, slots=True)
class Summary:
    """Statistics of a list of results (milliseconds, ``math.inf`` for DNF).

    Times are None when there's nothing to compute them from.

    Attributes:
        count: Number of results.
        dnfs: Number of DNFs.
        best: Fastest finished result.
        worst: Slowest finished result.
        mean: Mean of the finished results.
        median: Median of the finished results.
        std: Sample standard deviation of the finished results.
        percentiles: 10th, 50th and 90th percentile of the finished results.
        averages: Current and best average of n, for each n in ``SUMMARY_AVERAGES``.

    """

    count: int
    dnfs: int
    best: float | None
    worst: float | None
    mean: float | None
    median: float | None
    std: float | None
    percentiles: dict[int, float | None]
    averages: dict[int, tuple[float | None, float | None]]

    @property
    def cv(self) -> float | None:
        """Coefficient of variation (std / mean): how consistent the times are."""
        if self.std is None or not self.mean:
            return None
        return self.std / self.mean


def summarize(values: Sequence[float]) -> Summary:
    """Compute the Stats page's summary of some results.

    Args:
        values: Results, oldest first (``math.inf`` for DNF).

    Returns:
        The summary.

    """
    finished = np.array([v for v in values if math.isfinite(v)], dtype=float)
    some = finished.size > 0
    return Summary(
        count=len(values),
        dnfs=len(values) - int(finished.size),
        best=float(finished.min()) if some else None,
        worst=float(finished.max()) if some else None,
        mean=float(finished.mean()) if some else None,
        median=float(np.median(finished)) if some else None,
        std=float(finished.std(ddof=1)) if finished.size > 1 else None,
        percentiles={
            p: float(np.percentile(finished, p)) if some else None for p in (10, 50, 90)
        },
        averages={
            n: (current_average(values, n), best_average(values, n))
            for n in SUMMARY_AVERAGES
        },
    )


def sub_x_rate(values: Sequence[float], limit_ms: float) -> float | None:
    """Return the share of results under a time (DNFs count as not under it).

    Args:
        values: Results (``math.inf`` for DNF).
        limit_ms: The time to beat, in milliseconds.

    Returns:
        The fraction of results strictly under ``limit_ms``, or None if empty.

    """
    if not values:
        return None
    return sum(v < limit_ms for v in values) / len(values)


def records(values: Sequence[float], n: int = 1) -> list[tuple[int, float]]:
    """Find every new personal best, of single times or of averages of ``n``.

    Args:
        values: Results, oldest first (``math.inf`` for DNF).
        n: 1 for singles, otherwise the size of the average (e.g. 5 for ao5).

    Returns:
        ``(index, value)`` for each result (or average ending at that index) that
        beat every earlier one; DNFs never set a record.

    """
    series: Sequence[float | None] = values if n == 1 else rolling_averages(values, n)
    found: list[tuple[int, float]] = []
    best = math.inf
    for index, value in enumerate(series):
        if value is not None and value < best:
            best = value
            found.append((index, value))
    return found
