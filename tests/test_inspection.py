"""Tests for the inspection timeline and the timer's inspection phase."""

import pytest

from cubetrainer.inspection import inspection_penalty, inspection_text, warnings_between
from cubetrainer.solves import Penalty
from cubetrainer.timing import TimerMachine, TimerState

MS = 1_000_000  # nanoseconds per millisecond


@pytest.mark.parametrize(
    ("elapsed_ms", "penalty"),
    [
        (0, Penalty.OK),
        (14_999, Penalty.OK),
        (15_000, Penalty.PLUS_TWO),
        (16_999, Penalty.PLUS_TWO),
        (17_000, Penalty.DNF),
        (60_000, Penalty.DNF),
    ],
)
def test_penalty_thresholds(elapsed_ms: int, penalty: Penalty) -> None:
    """Up to 15 s is fine, then +2 until 17 s, then DNF (WCA A3a)."""
    assert inspection_penalty(elapsed_ms) is penalty


@pytest.mark.parametrize(
    ("elapsed_ms", "text"),
    [
        (0, "15"),
        (999, "15"),
        (1_000, "14"),
        (14_001, "1"),
        (14_999, "1"),
        (15_000, "+2"),
        (17_000, "DNF"),
    ],
)
def test_countdown_text(elapsed_ms: int, text: str) -> None:
    """The display counts the seconds left, then shows the penalty."""
    assert inspection_text(elapsed_ms) == text


def test_warnings_fire_once_each() -> None:
    """Each warning is reported once, when its time is first reached."""
    assert warnings_between(-1, 7_999) == []
    assert warnings_between(7_999, 8_000) == [8_000]
    assert warnings_between(8_000, 11_000) == []
    assert warnings_between(5_000, 13_000) == [8_000, 12_000]


def inspecting(at_ms: int = 0) -> TimerMachine:
    """Return a machine with inspection on, inspecting since ``at_ms``.

    Args:
        at_ms: When inspection began.

    Returns:
        The machine.

    """
    machine = TimerMachine(hold_delay_ns=300 * MS)
    machine.inspection = True
    machine.key_down(at_ms * MS, is_start_key=True)
    machine.key_up(at_ms * MS + 50 * MS, is_start_key=True)
    return machine


def start_at(machine: TimerMachine, ms: int) -> None:
    """Hold space from ``ms`` and release it once green.

    Args:
        machine: The machine.
        ms: When the hold starts.

    """
    machine.key_down(ms * MS, is_start_key=True)
    machine.key_up((ms + 300) * MS, is_start_key=True)


def test_first_press_starts_inspection() -> None:
    """With inspection on, the first press and release begin inspection."""
    machine = inspecting()

    assert machine.state is TimerState.INSPECTING
    assert machine.inspection_elapsed_ms(5_000 * MS) == 5_000


@pytest.mark.parametrize(
    ("hold_from_ms", "penalty"),
    [(5_000, Penalty.OK), (15_000, Penalty.PLUS_TWO), (17_000, Penalty.DNF)],
)
def test_starting_late_earns_a_penalty(hold_from_ms: int, penalty: Penalty) -> None:
    """The penalty depends on when the solve starts (at the end of the hold)."""
    machine = inspecting()

    start_at(machine, hold_from_ms - 300)

    assert machine.state is TimerState.RUNNING
    assert machine.last_penalty is penalty
    assert machine.inspection_elapsed_ms((hold_from_ms + 1_000) * MS) is None


def test_letting_go_too_early_keeps_inspecting() -> None:
    """A hold released before green goes back to the countdown."""
    machine = inspecting()
    machine.key_down(3_000 * MS, is_start_key=True)
    machine.key_up(3_100 * MS, is_start_key=True)

    assert machine.state is TimerState.INSPECTING


def test_cancel_during_inspection() -> None:
    """Escape while holding returns to inspecting; once more ends inspection."""
    machine = inspecting()
    machine.key_down(3_000 * MS, is_start_key=True)

    machine.cancel()
    assert machine.state is TimerState.INSPECTING
    machine.cancel()
    assert machine.state is TimerState.IDLE
    assert machine.inspection_elapsed_ms(4_000 * MS) is None


def test_penalty_resets_for_the_next_solve() -> None:
    """A clean solve after a late one has no penalty."""
    machine = inspecting()
    start_at(machine, 16_000)
    machine.key_down(20_000 * MS, is_start_key=True)
    machine.key_up(20_100 * MS, is_start_key=True)
    assert machine.last_penalty is Penalty.PLUS_TWO

    machine.key_down(30_000 * MS, is_start_key=True)
    machine.key_up(30_050 * MS, is_start_key=True)
    start_at(machine, 31_000)

    assert machine.last_penalty is Penalty.OK


def holding_to_inspect() -> TimerMachine:
    """Return an idle machine with inspection that starts with a hold.

    Returns:
        The machine.

    """
    machine = TimerMachine(hold_delay_ns=300 * MS)
    machine.inspection = True
    machine.hold_to_inspect = True
    return machine


def test_tap_does_not_start_inspection_when_holding_is_required() -> None:
    """With hold_to_inspect, a quick tap leaves the timer idle."""
    machine = holding_to_inspect()

    machine.key_down(0, is_start_key=True)
    assert machine.arming_inspection
    machine.key_up(100 * MS, is_start_key=True)

    assert machine.state is TimerState.IDLE
    assert not machine.arming_inspection


def test_hold_until_green_starts_inspection_on_release() -> None:
    """Holding until green and releasing starts inspection, then a solve as usual."""
    machine = holding_to_inspect()
    machine.key_down(0, is_start_key=True)
    machine.update(300 * MS)
    assert machine.state is TimerState.READY

    machine.key_up(1_000 * MS, is_start_key=True)
    assert machine.state is TimerState.INSPECTING
    assert machine.inspection_elapsed_ms(3_000 * MS) == 2_000  # from the release

    start_at(machine, 5_000)
    assert machine.state is TimerState.RUNNING
    assert machine.last_penalty is Penalty.OK


def test_escape_while_holding_to_inspect() -> None:
    """Cancelling the hold that would start inspection goes back to idle."""
    machine = holding_to_inspect()
    machine.key_down(0, is_start_key=True)
    machine.update(300 * MS)

    machine.cancel()

    assert machine.state is TimerState.IDLE
    assert not machine.arming_inspection
