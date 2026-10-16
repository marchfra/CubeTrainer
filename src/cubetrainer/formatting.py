"""Text formatting of solves and statistics for display."""

import math

from cubetrainer.solves import Penalty, Solve
from cubetrainer.timing import format_ms

#: Shown when there aren't enough solves for a statistic.
MISSING: str = "-"


def format_value(value: float | None) -> str:
    """Format a single time, truncated to centiseconds (WCA 9f1).

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


def format_average(value: float | None) -> str:
    """Format an average or mean, rounded half up to the nearest centisecond (WCA 9f2).

    Single times are truncated instead (see ``format_value``), as on a stackmat.

    Args:
        value: Milliseconds, ``math.inf`` for DNF, or None if not available.

    Returns:
        ``"-"`` for None, ``"DNF"`` for infinity, otherwise e.g. ``"12.35"`` for
        12345 ms.

    """
    if value is None or math.isinf(value):
        return format_value(value)
    return format_ms(math.floor(value / 10 + 0.5) * 10)


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


#: Marker for a solve flagged as a mistake.
MISTAKE_MARK: str = "✗"

#: Marker for a solve that used hints, followed by how many steps were revealed.
HINT_MARK: str = "💡"


def format_flags(solve: Solve) -> str:
    """Describe a trainer solve's flags: ``"✗"`` for a mistake, ``"💡3"`` for hints.

    Args:
        solve: The solve.

    Returns:
        The markers separated by a space, or an empty string.

    """
    flags: list[str] = []
    if solve.mistake:
        flags.append(MISTAKE_MARK)
    if solve.hints:
        flags.append(f"{HINT_MARK}{solve.hints}")
    return " ".join(flags)


def format_percent(fraction: float) -> str:
    """Format a fraction as a whole percentage.

    Args:
        fraction: A value between 0 and 1.

    Returns:
        e.g. ``"33%"``.

    """
    return f"{round(fraction * 100)}%"
