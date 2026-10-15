"""Tests for solves, the solve list and their formatting."""

import math
from datetime import UTC

import pytest

from cubetrainer.formatting import (
    format_average,
    format_solve,
    format_solve_detailed,
    format_value,
)
from cubetrainer.solves import Penalty, Solve, SolveList


@pytest.mark.parametrize(
    ("penalty", "value"),
    [(Penalty.OK, 12_345.0), (Penalty.PLUS_TWO, 14_345.0), (Penalty.DNF, math.inf)],
)
def test_solve_value_applies_penalty(penalty: Penalty, value: float) -> None:
    """+2 adds two seconds; DNF becomes infinity."""
    assert Solve(12_345, "R U", penalty).value == value


def test_solve_timestamp_is_timezone_aware() -> None:
    """New solves are stamped in UTC."""
    assert Solve(1, "").created_at.tzinfo is UTC


def test_solve_list_add_delete_and_penalty() -> None:
    """The list supports adding, penalising and deleting solves."""
    solves = SolveList()
    solves.add(Solve(10_000, "a"))
    solves.add(Solve(11_000, "b"))
    solves.add(Solve(12_000, "c"))

    solves.set_penalty(-1, Penalty.PLUS_TWO)
    removed = solves.delete(0)

    assert removed.scramble == "a"
    assert len(solves) == 2
    assert solves.values() == [11_000.0, 14_000.0]


@pytest.mark.parametrize(
    ("value", "text"),
    [(None, "-"), (math.inf, "DNF"), (12_345.6, "12.34"), (61_000.0, "1:01.00")],
)
def test_format_value(value: float | None, text: str) -> None:
    """Values format as cstimer shows them."""
    assert format_value(value) == text


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (None, "-"),
        (math.inf, "DNF"),
        (12_344.9, "12.34"),
        (12_345.0, "12.35"),  # half rounds up
        (11_606.67, "11.61"),  # truncation would give 11.60
        (9_995.0, "10.00"),
        (59_995.0, "1:00.00"),
    ],
)
def test_format_average_rounds_to_centiseconds(value: float | None, text: str) -> None:
    """Averages and means are rounded half up, not truncated."""
    assert format_average(value) == text


@pytest.mark.parametrize(
    ("penalty", "short", "detailed"),
    [
        (Penalty.OK, "12.34", "12.34"),
        (Penalty.PLUS_TWO, "14.34+", "14.34 (12.34 + 2)"),
        (Penalty.DNF, "DNF", "DNF (12.34)"),
    ],
)
def test_format_solve(penalty: Penalty, short: str, detailed: str) -> None:
    """Solves show their penalty in the list and the raw time in details."""
    solve = Solve(12_345, "", penalty)

    assert format_solve(solve) == short
    assert format_solve_detailed(solve) == detailed
