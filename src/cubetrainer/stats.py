"""Solve statistics: cstimer/WCA-style averages, means and bests.

Values are times in milliseconds with penalties applied, where ``math.inf`` stands for
a DNF. That makes DNFs sort as the worst result and turn any mean containing them into
a DNF automatically. ``None`` means "not enough solves".
"""

import math
from collections.abc import Sequence


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
