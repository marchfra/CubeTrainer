"""Which cases the trainer picks, and how likely each one is.

A filter keeps the cases whose group *and* learning status are selected. Cases are
then picked with equal probability, with their natural ("realistic") frequency,
i.e. how often they come up in real solves, or slowest first: weighted by how slow
and error-prone your recent solves of each case are.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction
from functools import cache
from typing import TYPE_CHECKING, Protocol

import numpy as np

from cubetrainer.cases.catalog import (
    Case,
    CaseCustomization,
    CaseKind,
    CaseSet,
    CaseStatus,
)
from cubetrainer.cases.recognition import corner_pattern, eo_pattern, oll_pattern
from cubetrainer.cube.model import Move, parse_alg, state_solved_by
from cubetrainer.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cubetrainer.solves import Solve


class Odds(StrEnum):
    """How likely each case passing the filter is to come up."""

    EQUAL = "equal"
    REALISTIC = "realistic"
    SLOWEST = "slowest first"

    @property
    def short(self) -> str:
        """Return a one-word name, for the trainer's filter button.

        Returns:
            e.g. ``"slowest"``.

        """
        return self.value.split()[0]


@dataclass(frozen=True, slots=True)
class CaseFilter:
    """The trainer's case selection.

    Attributes:
        groups: Selected groups, or None for every group (including ones a set may
            gain later).
        statuses: Selected learning statuses.
        odds: How likely each case is to be picked.

    """

    groups: frozenset[str] | None = None
    statuses: frozenset[CaseStatus] = field(
        default_factory=lambda: frozenset(CaseStatus),
    )
    odds: Odds = Odds.EQUAL

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
                "odds": self.odds.value,
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
        if "odds" in data:
            odds = Odds(data["odds"])
        else:  # saved before slowest first existed: a "realistic" flag
            odds = Odds.REALISTIC if data.get("realistic") else Odds.EQUAL
        return cls(
            groups=None if groups is None else frozenset(groups),
            statuses=frozenset(CaseStatus(s) for s in data["statuses"]),
            odds=odds,
        )


class TrainerPrefs(Settings, Protocol):
    """Where the trainer reads learning statuses and keeps its filter and options."""

    def statuses(self) -> dict[str, CaseStatus]:
        """Return the current learning status of the set's cases.

        Returns:
            Statuses keyed by case id; missing cases are unlearned.

        """
        ...

    def customizations(self) -> dict[str, CaseCustomization]:
        """Return what the user changed about the set's cases (their algorithms).

        Returns:
            Customisations keyed by case id.

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
        case_customizations: The user's changes to cases, by case id.
        settings: Other settings (the trainer's options), by name.

    """

    case_statuses: dict[str, CaseStatus] = field(default_factory=dict)
    case_filter: CaseFilter = field(default_factory=CaseFilter)
    case_customizations: dict[str, CaseCustomization] = field(default_factory=dict)
    settings: dict[str, str] = field(default_factory=dict)

    def get_setting(self, key: str) -> str | None:
        """Read a setting.

        Args:
            key: The setting's name.

        Returns:
            Its value, or None if it was never set.

        """
        return self.settings.get(key)

    def set_setting(self, key: str, value: str) -> None:
        """Store a setting.

        Args:
            key: The setting's name.
            value: Its new value.

        """
        self.settings[key] = value

    def customizations(self) -> dict[str, CaseCustomization]:
        """Return the user's changes to cases.

        Returns:
            Customisations keyed by case id.

        """
        return self.case_customizations

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


#: Number of distinct looks the last layer can have, for each kind of case. A case's
#: probability is its number of looks divided by this; what's left is the skip.
LOOK_SPACE: dict[CaseKind, int] = {
    CaseKind.PLL: 288,  # 72 permutations x 4 U turns
    CaseKind.OLL: 216,  # 27 corner x 8 edge orientations
    CaseKind.EO: 8,  # 2^3 edge orientations
    CaseKind.CO: 27,  # 3^3 corner orientations
    CaseKind.CP: 24,  # 4! corner permutations
    CaseKind.EP: 48,  # 12 even edge permutations x 4 U turns
}

#: Number of looks of each kind's skip (already solved, up to a U turn).
SKIP_LOOKS: dict[CaseKind, int] = {
    CaseKind.PLL: 4,
    CaseKind.OLL: 1,
    CaseKind.EO: 1,
    CaseKind.CO: 1,
    CaseKind.CP: 4,
    CaseKind.EP: 4,
}


def case_probability(case: Case) -> Fraction:
    """Return how often a case comes up in real solves, at its step of the method.

    A uniformly random cube shows each look of the last layer equally often, so the
    probability is the number of distinct looks the case has, over all its U turns,
    divided by the number of looks there are. For PLL a look is the whole last
    layer; for OLL and CO the orientation pattern; for EO just the edges; for CP
    just the corners. E.g. most PLLs are 1/18 and H is 1/72; most OLLs are 1/54.

    Args:
        case: The case.

    Returns:
        The probability (the cases of a kind plus its skip add up to 1).

    """
    return Fraction(_case_looks(case.alg, case.kind), LOOK_SPACE[case.kind])


@cache
def _case_looks(alg: str, kind: CaseKind) -> int:
    """Count a case's distinct looks over its U turns (cached by algorithm and kind).

    Args:
        alg: The case's algorithm.
        kind: The kind of case.

    Returns:
        The number of distinct looks.

    """
    moves = parse_alg(alg)
    aufs: list[list[Move]] = [[], *([Move("U", turns)] for turns in (1, 2, 3))]
    match kind:
        case CaseKind.OLL | CaseKind.CO:
            return len({oll_pattern(state_solved_by(moves, before=b)) for b in aufs})
        case CaseKind.EO:
            return len({eo_pattern(state_solved_by(moves, before=b)) for b in aufs})
        case CaseKind.CP:
            return len(
                {
                    corner_pattern(state_solved_by(moves, before=b, after=a))
                    for b in aufs
                    for a in aufs
                },
            )
        case CaseKind.PLL | CaseKind.EP:
            return len(
                {state_solved_by(moves, before=b, after=a) for b in aufs for a in aufs},
            )


#: Slowest first: how many of a case's latest solves describe it.
RECENT_SOLVES: int = 12

#: Slowest first: fewest timed solves (finished, not mistakes) to rate a case;
#: cases with fewer are treated like the slowest one, so they get practised.
MIN_TIMED_SOLVES: int = 3

#: Slowest first: the weight grows with the mean time to this power.
SLOWNESS_POWER: int = 2


def slowness_weights(cases: Sequence[Case], history: Sequence[Solve]) -> np.ndarray:
    """Weight cases by how slow and error-prone their latest solves are.

    Each case is rated on its last ``RECENT_SOLVES`` solves: its weight is the mean
    time of those that are finished and not mistakes, to the power
    ``SLOWNESS_POWER``, times (1 + the share of them that are mistakes). Cases with
    fewer than ``MIN_TIMED_SOLVES`` timed solves get the largest weight of the
    others (all cases are equal if none can be rated).

    Args:
        cases: The candidate cases.
        history: Solves of the set, oldest first (other cases' solves are ignored).

    Returns:
        One positive weight per case, in order (not normalised).

    """
    recent: dict[str | None, list[Solve]] = defaultdict(list)
    for solve in history:
        recent[solve.case_id].append(solve)
    rated: list[float | None] = []
    for case in cases:
        latest = recent[case.id][-RECENT_SOLVES:]
        timed = [s.value for s in latest if not s.mistake and math.isfinite(s.value)]
        if len(timed) < MIN_TIMED_SOLVES:
            rated.append(None)
            continue
        mean_seconds = sum(timed) / len(timed) / 1000
        mistakes = sum(s.mistake for s in latest) / len(latest)
        rated.append(mean_seconds**SLOWNESS_POWER * (1 + mistakes))
    known = [w for w in rated if w is not None]
    unknown = max(known, default=1.0)
    return np.array([unknown if w is None else w for w in rated])


def pick_case(
    cases: list[Case],
    rng: np.random.Generator,
    odds: Odds,
    history: Sequence[Solve] = (),
) -> Case:
    """Pick one of some cases.

    Args:
        cases: The candidate cases (not empty).
        rng: Random number generator.
        odds: How to weight the cases: equally; by their real-solve probability (in
            2-look sets each look is weighted within its own step); or slowest
            first (see ``slowness_weights``).
        history: The set's solves, oldest first (used by slowest first).

    Returns:
        The chosen case.

    """
    match odds:
        case Odds.EQUAL:
            return cases[int(rng.integers(len(cases)))]
        case Odds.REALISTIC:
            weights = np.array([float(case_probability(case)) for case in cases])
        case Odds.SLOWEST:
            weights = slowness_weights(cases, history)
    return cases[int(rng.choice(len(cases), p=weights / weights.sum()))]
