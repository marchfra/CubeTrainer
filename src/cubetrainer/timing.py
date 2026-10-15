"""Qt-free timer logic: the cstimer-style spacebar state machine and time formatting.

Keeping this separate from the widget means it can be tested with a fake clock,
without simulating real key presses or waiting for real time to pass.
"""

from enum import Enum, auto

#: How long the start key must be held before the timer is armed (cstimer default).
DEFAULT_HOLD_DELAY_NS: int = 300_000_000

_NS_PER_MS: int = 1_000_000


class TimerState(Enum):
    """Phases of a single timed attempt."""

    IDLE = auto()
    """Waiting for the start key; shows the previous result."""
    HOLDING = auto()
    """Start key held, but not long enough yet (display is red)."""
    READY = auto()
    """Start key held long enough; releasing it starts the timer (display is green)."""
    RUNNING = auto()
    """Timing a solve; any key press stops it."""
    STOPPED = auto()
    """Solve finished; waiting for the stopping key to be released."""


class TimerMachine:
    """State machine for a hold-to-arm, release-to-start, press-to-stop timer.

    All methods take the current time in nanoseconds (from a monotonic clock) so the
    caller decides where time comes from.

    Attributes:
        hold_delay_ns: How long the start key must be held to arm the timer.
        state: The current phase.
        last_result_ms: Duration of the last completed solve, if any.

    """

    def __init__(self, hold_delay_ns: int = DEFAULT_HOLD_DELAY_NS) -> None:
        """Create an idle timer.

        Args:
            hold_delay_ns: How long the start key must be held to arm the timer.

        """
        self.hold_delay_ns: int = hold_delay_ns
        self.state: TimerState = TimerState.IDLE
        self.last_result_ms: int | None = None
        self._hold_start_ns: int = 0
        self._run_start_ns: int = 0

    def key_down(self, now_ns: int, *, is_start_key: bool) -> int | None:
        """Handle a (non auto-repeat) key press.

        Args:
            now_ns: Current monotonic time in nanoseconds.
            is_start_key: Whether the pressed key is the start key (space).

        Returns:
            The solve time in milliseconds if this press stopped the timer, else None.

        """
        if self.state is TimerState.RUNNING:
            self.state = TimerState.STOPPED
            self.last_result_ms = (now_ns - self._run_start_ns) // _NS_PER_MS
            return self.last_result_ms
        if self.state is TimerState.IDLE and is_start_key:
            self.state = TimerState.HOLDING
            self._hold_start_ns = now_ns
        return None

    def key_up(self, now_ns: int, *, is_start_key: bool) -> None:
        """Handle a (non auto-repeat) key release.

        Args:
            now_ns: Current monotonic time in nanoseconds.
            is_start_key: Whether the released key is the start key (space).

        """
        self.update(now_ns)
        cancelled_hold = is_start_key and self.state is TimerState.HOLDING
        if self.state is TimerState.STOPPED or cancelled_hold:
            self.state = TimerState.IDLE
        elif is_start_key and self.state is TimerState.READY:
            self.state = TimerState.RUNNING
            self._run_start_ns = now_ns

    def update(self, now_ns: int) -> None:
        """Advance time-based transitions (arming the timer after the hold delay).

        Args:
            now_ns: Current monotonic time in nanoseconds.

        """
        if (
            self.state is TimerState.HOLDING
            and now_ns - self._hold_start_ns >= self.hold_delay_ns
        ):
            self.state = TimerState.READY

    def cancel(self) -> None:
        """Abort a hold in progress (e.g. on Escape); running solves are unaffected."""
        if self.state in {TimerState.HOLDING, TimerState.READY}:
            self.state = TimerState.IDLE

    def elapsed_ms(self, now_ns: int) -> int:
        """Return the time to display right now.

        Args:
            now_ns: Current monotonic time in nanoseconds.

        Returns:
            The running time while a solve is in progress, otherwise the last result
            (0 if there is none).

        """
        if self.state is TimerState.RUNNING:
            return (now_ns - self._run_start_ns) // _NS_PER_MS
        return self.last_result_ms or 0


def format_ms(ms: int) -> str:
    """Format a duration like cstimer: truncated to centiseconds, minutes when needed.

    Args:
        ms: Duration in milliseconds (non-negative).

    Returns:
        A string such as ``"0.00"``, ``"9.87"`` or ``"1:02.34"``.

    """
    centis = ms // 10
    minutes, centis = divmod(centis, 6000)
    seconds, centis = divmod(centis, 100)
    if minutes:
        return f"{minutes}:{seconds:02d}.{centis:02d}"
    return f"{seconds}.{centis:02d}"
