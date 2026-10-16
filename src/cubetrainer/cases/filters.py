"""Which cases the trainer picks, and how likely each one is.

A filter keeps the cases whose group *and* learning status are selected. Cases are
then picked either with equal probability or with their natural ("realistic")
frequency, i.e. how often they come up in real solves.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cache
from typing import Protocol

import numpy as np

from cubetrainer.cases.catalog import Case, CaseSet, CaseStatus
from cubetrainer.cube.model import Move, parse_alg, state_solved_by


@dataclass(frozen=True, slots=True)
class CaseFilter:
    """The trainer's case selection.

    Attributes:
        groups: Selected groups, or None for every group (including ones a set may
            gain later).
        statuses: Selected learning statuses.
        realistic: Pick cases with their natural frequency instead of equally.

    """

    groups: frozenset[str] | None = None
    statuses: frozenset[CaseStatus] = field(
        default_factory=lambda: frozenset(CaseStatus),
    )
    realistic: bool = False

    def matching(
        self,
        case_set: CaseSet,
        statuses: dict[str, CaseStatus],
    ) -> list[Case]:
        """Return the cases of a set that pass the filter.

        Args:
            case_set: The set.
            statuses: Learning status by case id; missing cases are unlearned.

        Returns:
            The cases whose group and status are both selected, in set order.

        """
        return [
            case
            for case in case_set.cases
            if (self.groups is None or case.group in self.groups)
            and statuses.get(case.id, CaseStatus.UNLEARNED) in self.statuses
        ]

    def to_json(self) -> str:
        """Serialise the filter for storage.

        Returns:
            A JSON string.

        """
        return json.dumps(
            {
                "groups": None if self.groups is None else sorted(self.groups),
                "statuses": sorted(s.value for s in self.statuses),
                "realistic": self.realistic,
            },
        )

    @classmethod
    def from_json(cls, text: str) -> CaseFilter:
        """Restore a filter saved with ``to_json``.

        Args:
            text: The JSON string.

        Returns:
            The filter.

        """
        data = json.loads(text)
        groups = data["groups"]
        return cls(
            groups=None if groups is None else frozenset(groups),
            statuses=frozenset(CaseStatus(s) for s in data["statuses"]),
            realistic=bool(data["realistic"]),
        )


class TrainerPrefs(Protocol):
    """Where the trainer reads learning statuses and keeps its filter."""

    def statuses(self) -> dict[str, CaseStatus]:
        """Return the current learning status of the set's cases.

        Returns:
            Statuses keyed by case id; missing cases are unlearned.

        """
        ...

    def load_filter(self) -> CaseFilter:
        """Return the saved filter, or the default one.

        Returns:
            The filter.

        """
        ...

    def save_filter(self, case_filter: CaseFilter) -> None:
        """Remember a filter.

        Args:
            case_filter: The filter to keep.

        """
        ...


@dataclass(slots=True)
class MemoryTrainerPrefs:
    """Trainer preferences kept in memory (nothing is saved).

    Attributes:
        case_statuses: Learning status by case id.
        case_filter: The current filter.

    """

    case_statuses: dict[str, CaseStatus] = field(default_factory=dict)
    case_filter: CaseFilter = field(default_factory=CaseFilter)

    def statuses(self) -> dict[str, CaseStatus]:
        """Return the learning statuses.

        Returns:
            Statuses keyed by case id.

        """
        return self.case_statuses

    def load_filter(self) -> CaseFilter:
        """Return the current filter.

        Returns:
            The filter.

        """
        return self.case_filter

    def save_filter(self, case_filter: CaseFilter) -> None:
        """Replace the current filter.

        Args:
            case_filter: The new filter.

        """
        self.case_filter = case_filter


@cache
def case_weight(alg: str) -> int:
    """Return how many distinct cube states a case covers, over all its AUFs.

    A uniformly random cube shows each such state equally often, so a case's
    natural frequency is proportional to this number. For PLL it's 16 for most
    cases, 8 for E and Z, and 4 for H, Na and Nb.

    Args:
        alg: The case's algorithm.

    Returns:
        The number of distinct states (1 to 16).

    """
    moves = parse_alg(alg)
    aufs: list[list[Move]] = [[], *([Move("U", turns)] for turns in (1, 2, 3))]
    states = {
        state_solved_by(moves, before=before, after=after)
        for before in aufs
        for after in aufs
    }
    return len(states)


def pick_case(cases: list[Case], rng: np.random.Generator, *, realistic: bool) -> Case:
    """Pick one of some cases.

    Args:
        cases: The candidate cases (not empty).
        rng: Random number generator.
        realistic: Weight cases by their natural frequency instead of equally.

    Returns:
        The chosen case.

    """
    if not realistic:
        return cases[int(rng.integers(len(cases)))]
    weights = np.array([case_weight(case.alg) for case in cases], dtype=float)
    return cases[int(rng.choice(len(cases), p=weights / weights.sum()))]
