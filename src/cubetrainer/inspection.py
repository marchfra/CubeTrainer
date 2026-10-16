"""WCA inspection timeline: countdown text, penalties and the 8 s / 12 s calls.

Pure functions of the time elapsed since inspection began, so they can be tested
without a clock, a timer widget or audio.
"""

from cubetrainer.solves import Penalty

#: Inspection time allowed without penalty (WCA regulation A3a1).
INSPECTION_MS: int = 15_000

#: Starting later than this is a DNF; between 15 s and this it's +2 (A3a2, A3a3).
INSPECTION_DNF_MS: int = 17_000

#: Elapsed times at which a judge calls out the time (A3a5): 8 and 12 seconds.
WARNINGS_MS: tuple[int, ...] = (8_000, 12_000)


def inspection_penalty(elapsed_ms: int) -> Penalty:
    """Return the penalty for starting a solve after some inspection time.

    Args:
        elapsed_ms: Time between the start of inspection and the start of the solve.

    Returns:
        OK within 15 s, +2 up to 17 s, DNF after that.

    """
    if elapsed_ms < INSPECTION_MS:
        return Penalty.OK
    if elapsed_ms < INSPECTION_DNF_MS:
        return Penalty.PLUS_TWO
    return Penalty.DNF


def inspection_text(elapsed_ms: int) -> str:
    """Return what the display shows during inspection, like cstimer.

    Args:
        elapsed_ms: Time since inspection began.

    Returns:
        The seconds left, counting down from ``"15"`` to ``"1"``; then ``"+2"``;
        then ``"DNF"``.

    """
    penalty = inspection_penalty(elapsed_ms)
    if penalty is Penalty.DNF:
        return "DNF"
    if penalty is Penalty.PLUS_TWO:
        return "+2"
    remaining_ms = INSPECTION_MS - elapsed_ms
    return str(-(-remaining_ms // 1000))  # whole seconds, rounded up


def warnings_between(previous_ms: int, now_ms: int) -> list[int]:
    """Return the warnings whose time was reached since the last check.

    Args:
        previous_ms: Elapsed time at the previous check (-1 before the first one).
        now_ms: Elapsed time now.

    Returns:
        The warning times in ``(previous_ms, now_ms]``, in order.

    """
    return [w for w in WARNINGS_MS if previous_ms < w <= now_ms]
