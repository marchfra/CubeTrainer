"""Tests for the Qt-free timer state machine and time formatting."""

import pytest

from cubetrainer.timing import TimerMachine, TimerState, format_ms

MS = 1_000_000  # nanoseconds per millisecond


def armed_machine() -> TimerMachine:
    """Return a machine that has been held long enough to be READY at t=300 ms.

    Returns:
        The armed machine.

    """
    machine = TimerMachine(hold_delay_ns=300 * MS)
    machine.key_down(0, is_start_key=True)
    machine.update(300 * MS)
    return machine


def test_starts_idle_with_zero_display() -> None:
    """A fresh machine is idle and shows 0."""
    machine = TimerMachine()

    assert machine.state is TimerState.IDLE
    assert machine.elapsed_ms(123 * MS) == 0


def test_holding_turns_ready_only_after_delay() -> None:
    """Holding space arms the timer exactly when the hold delay has elapsed."""
    machine = TimerMachine(hold_delay_ns=300 * MS)
    machine.key_down(0, is_start_key=True)
    assert machine.state is TimerState.HOLDING

    machine.update(299 * MS)
    assert machine.state is TimerState.HOLDING

    machine.update(300 * MS)
    assert machine.state is TimerState.READY


def test_early_release_cancels_hold() -> None:
    """Releasing space before the delay goes back to idle without starting."""
    machine = TimerMachine(hold_delay_ns=300 * MS)
    machine.key_down(0, is_start_key=True)

    machine.key_up(100 * MS, is_start_key=True)

    assert machine.state is TimerState.IDLE


def test_release_after_delay_starts_even_without_update() -> None:
    """Release checks the hold delay itself, so a missed refresh tick doesn't matter."""
    machine = TimerMachine(hold_delay_ns=300 * MS)
    machine.key_down(0, is_start_key=True)

    machine.key_up(400 * MS, is_start_key=True)

    assert machine.state is TimerState.RUNNING


def test_full_solve_cycle_returns_elapsed_time() -> None:
    """Release starts the clock, any key stops it, and the release returns to idle."""
    machine = armed_machine()
    machine.key_up(1_000 * MS, is_start_key=True)
    assert machine.state is TimerState.RUNNING
    assert machine.elapsed_ms(2_500 * MS) == 1_500

    result = machine.key_down(13_345 * MS, is_start_key=False)
    assert result == 12_345
    assert machine.state is TimerState.STOPPED

    machine.key_up(13_400 * MS, is_start_key=False)
    assert machine.state is TimerState.IDLE
    assert machine.elapsed_ms(99_999 * MS) == 12_345


def test_holding_space_after_stop_does_not_rearm() -> None:
    """The space press that stopped the timer must be released before a new hold."""
    machine = armed_machine()
    machine.key_up(300 * MS, is_start_key=True)
    machine.key_down(1_000 * MS, is_start_key=True)

    machine.update(5_000 * MS)

    assert machine.state is TimerState.STOPPED


def test_non_start_key_does_not_begin_hold() -> None:
    """Only the start key arms the timer."""
    machine = TimerMachine()

    machine.key_down(0, is_start_key=False)

    assert machine.state is TimerState.IDLE


def test_cancel_aborts_hold_but_not_running_solve() -> None:
    """Cancel only affects holds."""
    machine = armed_machine()
    machine.cancel()
    assert machine.state is TimerState.IDLE

    machine = armed_machine()
    machine.key_up(300 * MS, is_start_key=True)
    machine.cancel()
    assert machine.state is TimerState.RUNNING


@pytest.mark.parametrize(
    ("ms", "expected"),
    [
        (0, "0.00"),
        (9, "0.00"),
        (9_879, "9.87"),
        (59_999, "59.99"),
        (60_000, "1:00.00"),
        (62_345, "1:02.34"),
        (3_600_000, "60:00.00"),
    ],
)
def test_format_ms_truncates_to_centiseconds(ms: int, expected: str) -> None:
    """Times are truncated (not rounded), with minutes once past 60 s."""
    assert format_ms(ms) == expected
