"""Recorded solves and the in-memory list of a session's solves."""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

#: Milliseconds added by a +2 penalty.
PLUS_TWO_MS: int = 2000


class Penalty(Enum):
    """WCA penalty applied to a solve."""

    OK = "ok"
    PLUS_TWO = "+2"
    DNF = "dnf"


@dataclass(slots=True)
class Solve:
    """A single timed solve.

    Attributes:
        time_ms: Raw measured time in milliseconds, without penalties.
        scramble: The scramble that was shown for this solve.
        penalty: Penalty applied to the solve.
        created_at: When the solve finished (timezone-aware, UTC).
        id: Database id, or None if the solve hasn't been stored.
        case_id: For trainer solves, the case that was scrambled; None for full solves.

    """

    time_ms: int
    scramble: str
    penalty: Penalty = Penalty.OK
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    id: int | None = None
    case_id: str | None = None

    @property
    def value(self) -> float:
        """The time used for statistics: penalties applied, ``math.inf`` for a DNF."""
        if self.penalty is Penalty.DNF:
            return math.inf
        if self.penalty is Penalty.PLUS_TWO:
            return float(self.time_ms + PLUS_TWO_MS)
        return float(self.time_ms)


class SolveList:
    """The solves of one session, oldest first.

    Attributes:
        solves: The solves, in the order they were done.

    """

    def __init__(self) -> None:
        """Create an empty list."""
        self.solves: list[Solve] = []

    def __len__(self) -> int:
        """Return the number of solves.

        Returns:
            The number of solves.

        """
        return len(self.solves)

    def add(self, solve: Solve) -> None:
        """Append a newly finished solve.

        Args:
            solve: The solve to add.

        """
        self.solves.append(solve)

    def delete(self, index: int) -> Solve:
        """Remove a solve.

        Args:
            index: Position of the solve (0 is the oldest; -1 is the newest).

        Returns:
            The removed solve.

        """
        return self.solves.pop(index)

    def set_penalty(self, index: int, penalty: Penalty) -> None:
        """Change the penalty of a solve.

        Args:
            index: Position of the solve (0 is the oldest; -1 is the newest).
            penalty: The new penalty.

        """
        self.solves[index].penalty = penalty

    def values(self) -> list[float]:
        """Return every solve's statistics value, oldest first.

        Returns:
            Times in milliseconds with penalties applied, ``math.inf`` for DNFs.

        """
        return [s.value for s in self.solves]
