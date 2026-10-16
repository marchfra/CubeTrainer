"""Bundled case sets and the learning status of a case."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum, StrEnum
from functools import cache
from importlib import resources

from cubetrainer.cube.model import CubeState, parse_alg, state_solved_by


class CaseStatus(Enum):
    """How far along the user is with learning a case (cycled by clicking its image)."""

    UNLEARNED = "unlearned"
    LEARNING = "learning"
    FINISHED = "finished"

    def next(self) -> CaseStatus:
        """Return the status a click moves to: unlearned → learning → finished → ...

        Returns:
            The next status in the cycle.

        """
        order = list(CaseStatus)
        return order[(order.index(self) + 1) % len(order)]


class CaseKind(StrEnum):
    """What a set's cases are about, which decides how they're told apart and drawn."""

    OLL = "oll"
    """Orienting the last layer: cases differ by which stickers face up."""
    PLL = "pll"
    """Permuting the last layer: cases differ by where the pieces go."""


@dataclass(frozen=True, slots=True)
class Case:
    """One algorithm case.

    Attributes:
        id: Identifier, unique within its set (e.g. ``"Ua"``).
        name: Display name.
        group: Group the case belongs to (e.g. ``"Edges Only"``).
        alg: Default algorithm that solves the case.
        kind: Whether it's an OLL or a PLL case.

    """

    id: str
    name: str
    group: str
    alg: str
    kind: CaseKind = CaseKind.PLL

    def state(self) -> CubeState:
        """Return the cube state this case's algorithm solves.

        Returns:
            The state the algorithm solves, held in standard orientation.

        """
        return state_solved_by(parse_alg(self.alg))


@dataclass(frozen=True, slots=True)
class CaseSet:
    """A named collection of cases, in display order.

    Attributes:
        id: Identifier (e.g. ``"pll"``), also used as the data file name.
        name: Display name.
        kind: Whether the set's cases are OLL or PLL cases.
        cases: The cases.

    """

    id: str
    name: str
    kind: CaseKind
    cases: tuple[Case, ...]

    @property
    def groups(self) -> list[str]:
        """The distinct groups, in order of first appearance."""
        return list(dict.fromkeys(case.group for case in self.cases))


@cache
def load_case_set(set_id: str) -> CaseSet:
    """Load a bundled case set from ``cases/data/<set_id>.json``.

    Args:
        set_id: The set identifier, e.g. ``"pll"``.

    Returns:
        The case set.

    """
    text = resources.files(__package__).joinpath("data", f"{set_id}.json").read_text()
    data = json.loads(text)
    kind = CaseKind(data["kind"])
    cases = tuple(
        Case(id=c["id"], name=c["name"], group=c["group"], alg=c["alg"], kind=kind)
        for c in data["cases"]
    )
    return CaseSet(id=data["id"], name=data["name"], kind=kind, cases=cases)
