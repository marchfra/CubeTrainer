"""Bundled case sets and the learning status of a case."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
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
    """What a case is about, which decides how cases are told apart and drawn."""

    OLL = "oll"
    """Orienting the last layer: cases differ by which stickers face up."""
    PLL = "pll"
    """Permuting the last layer: cases differ by where the pieces go."""
    EO = "eo"
    """2-look OLL, first look: orienting the edges; the corners can be anything."""
    CO = "co"
    """2-look OLL, second look: orienting the corners, with the edges oriented."""
    CP = "cp"
    """2-look PLL, first look: permuting the corners; the edges can be anything."""
    EP = "ep"
    """2-look PLL, second look: permuting the edges, with the corners solved."""


@dataclass(frozen=True, slots=True)
class Case:
    """One algorithm case.

    Attributes:
        id: Identifier, unique within its set (e.g. ``"Ua"``).
        name: Display name.
        group: Group the case belongs to (e.g. ``"Edges Only"``).
        alg: Algorithm that solves the case (the user's, if they set one).
        kind: What the case is about (OLL, PLL, or one look of a 2-look method).
        image_path: An image file the user chose to show instead of the generated
            one, or None.
        rotation: Clockwise quarter turns applied to the image (0 to 3).

    """

    id: str
    name: str
    group: str
    alg: str
    kind: CaseKind = CaseKind.PLL
    image_path: str | None = None
    rotation: int = 0

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
        kind: The kind of most of the set's cases (cases may override it).
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


@dataclass(frozen=True, slots=True)
class CaseCustomization:
    """What the user changed about a case in the case editor.

    Attributes:
        alg: Their algorithm, or None for the default one.
        image_path: Their image file, or None for the generated image.
        rotation: Clockwise quarter turns applied to the image (0 to 3).

    """

    alg: str | None = None
    image_path: str | None = None
    rotation: int = 0

    def apply_to(self, case: Case) -> Case:
        """Return the case as the user customised it.

        Args:
            case: The bundled case.

        Returns:
            The case with the user's algorithm, image and rotation.

        """
        return replace(
            case,
            alg=self.alg or case.alg,
            image_path=self.image_path,
            rotation=self.rotation % 4,
        )


def customize(
    case_set: CaseSet,
    customizations: dict[str, CaseCustomization],
) -> CaseSet:
    """Return a set with the user's customisations applied to its cases.

    Args:
        case_set: The bundled set.
        customizations: Customisations keyed by case id; other cases are unchanged.

    Returns:
        The customised set.

    """
    cases = tuple(
        customizations[case.id].apply_to(case) if case.id in customizations else case
        for case in case_set.cases
    )
    return replace(case_set, cases=cases)


@cache
def load_case_set(set_id: str) -> CaseSet:
    """Load a bundled case set from ``cases/data/<set_id>.json``.

    The file gives the set's kind; a case may override it with its own ``"kind"``
    (2-look sets mix two kinds).

    Args:
        set_id: The set identifier, e.g. ``"pll"``.

    Returns:
        The case set.

    """
    text = resources.files(__package__).joinpath("data", f"{set_id}.json").read_text()
    data = json.loads(text)
    kind = CaseKind(data["kind"])
    cases = tuple(
        Case(
            id=c["id"],
            name=c["name"],
            group=c["group"],
            alg=c["alg"],
            kind=CaseKind(c.get("kind", kind)),
        )
        for c in data["cases"]
    )
    return CaseSet(id=data["id"], name=data["name"], kind=kind, cases=cases)
