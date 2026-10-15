"""Text formatting of solves and statistics for display."""

import math

from cubetrainer.solves import Penalty, Solve
from cubetrainer.timing import format_ms

#: Shown when there aren't enough solves for a statistic.
MISSING: str = "-"


def format_value(value: float | None) -> str:
    """Format a statistic value.

    Args:
        value: Milliseconds, ``math.inf`` for DNF, or None if not available.

    Returns:
        ``"-"`` for None, ``"DNF"`` for infinity, otherwise e.g. ``"12.34"``.

    """
    if value is None:
        return MISSING
    if math.isinf(value):
        return "DNF"
    return format_ms(int(value))


def format_solve(solve: Solve) -> str:
    """Format a solve like cstimer's list: ``"14.34+"`` for a +2, ``"DNF"`` for a DNF.

    Args:
        solve: The solve.

    Returns:
        The display text.

    """
    text = format_value(solve.value)
    return text + "+" if solve.penalty is Penalty.PLUS_TWO else text


def format_solve_detailed(solve: Solve) -> str:
    """Format a solve showing the raw time behind a penalty.

    Args:
        solve: The solve.

    Returns:
        e.g. ``"12.34"``, ``"14.34 (12.34 + 2)"`` or ``"DNF (12.34)"``.

    """
    raw = format_ms(solve.time_ms)
    if solve.penalty is Penalty.DNF:
        return f"DNF ({raw})"
    if solve.penalty is Penalty.PLUS_TWO:
        return f"{format_value(solve.value)} ({raw} + 2)"
    return raw
