"""Scrambles that set up a chosen last-layer case, and recognising them again.

A case scramble is built like a full random-state scramble: the target state (the
case, with a random U turn before and after it) is solved with the two-phase solver
and the solution is inverted. The scramble therefore doesn't reveal the algorithm.
Whatever the case's algorithm doesn't solve is random, with real-solve odds, as it
would be in a real solve: e.g. OLL cases come with a random PLL.

The case of a scramble is never stored alongside it: it's recognised from the
scramble itself, so the two can never disagree.
"""

from collections.abc import Callable, Sequence
from fractions import Fraction

import numpy as np

from cubetrainer.cases.catalog import (
    Case,
    CaseKind,
    CaseSet,
    customize,
    load_case_set,
)
from cubetrainer.cases.filters import (
    LOOK_SPACE,
    SKIP_LOOKS,
    TrainerPrefs,
    case_probability,
    pick_case,
)
from cubetrainer.cases.recognition import case_key
from cubetrainer.cube.model import (
    SOLVED,
    CubeState,
    Move,
    format_alg,
    invert_alg,
    parse_alg,
    state_solved_by,
)
from cubetrainer.cube.scramble import solve_facelets
from cubetrainer.solves import Solve


def _u_turn(turns: int) -> list[Move]:
    """Return a U turn as a move list.

    Args:
        turns: Quarter turns, 0 to 3.

    Returns:
        ``[U, U2 or U']``, or an empty list for 0.

    """
    return [Move("U", turns)] if turns else []


#: What's left to solve after a case of each kind, in a real solve: e.g. after an
#: OLL comes a PLL, after the edge look of 2-look OLL comes its corner look.
REST_OF: dict[CaseKind, CaseKind | None] = {
    CaseKind.OLL: CaseKind.PLL,
    CaseKind.EO: CaseKind.CO,
    CaseKind.CO: CaseKind.PLL,
    CaseKind.CP: CaseKind.EP,
    CaseKind.PLL: None,
    CaseKind.EP: None,
}


def _cases_of(kind: CaseKind) -> list[Case]:
    """Return every case of a kind that can be "the rest" of another case.

    Args:
        kind: PLL, CO or EP.

    Returns:
        The bundled cases of that kind.

    Raises:
        ValueError: For other kinds (they never come after another case).

    """
    sources = {CaseKind.PLL: "pll", CaseKind.CO: "oll2", CaseKind.EP: "pll2"}
    if kind not in sources:
        msg = f"no case comes after another as {kind}"
        raise ValueError(msg)
    return [c for c in load_case_set(sources[kind]).cases if c.kind is kind]


def random_look(kind: CaseKind, rng: np.random.Generator) -> CubeState:
    """Return a random last layer as it looks at a given step of a real solve.

    The step's case (or its skip) is picked with real-solve odds, so every look is
    equally likely; whatever later steps solve is random too.

    Args:
        kind: The step: PLL (U face solved), CO (edges oriented) or EP (corners
            solved as well).
        rng: Random number generator.

    Returns:
        A state with F2L solved.

    """
    cases = _cases_of(kind)
    skip = Fraction(SKIP_LOOKS[kind], LOOK_SPACE[kind])
    weights = np.array([*(float(case_probability(c)) for c in cases), float(skip)])
    choice = int(rng.choice(len(weights), p=weights / weights.sum()))
    if choice < len(cases):
        return case_state(cases[choice], rng)
    rest = REST_OF[kind]
    if rest is not None:
        return random_look(rest, rng)
    return SOLVED.apply(_u_turn(int(rng.integers(4))))


def random_pll_state(rng: np.random.Generator) -> CubeState:
    """Return a random last-layer permutation with the U face solved.

    Every one of the 288 possible permutations (21 PLLs and the skip, with all their
    U turns) is equally likely, as on a randomly scrambled cube.

    Args:
        rng: Random number generator.

    Returns:
        A state with F2L and OLL solved.

    """
    return random_look(CaseKind.PLL, rng)


def case_state(case: Case, rng: np.random.Generator) -> CubeState:
    """Return a random state showing ``case``, with random U turns around it.

    What the case's algorithm doesn't solve is random, as in a real solve: e.g. an
    OLL case comes with a random permutation, the edge look of 2-look OLL with
    random corners.

    Args:
        case: The case to set up.
        rng: Random number generator.

    Returns:
        The state.

    """
    pre, post = (int(turns) for turns in rng.integers(0, 4, size=2))
    alg = parse_alg(case.alg)
    rest = REST_OF[case.kind]
    if rest is None:
        return state_solved_by(alg, before=_u_turn(pre), after=_u_turn(post))
    # The rest first, then the case: solving it takes the case's algorithm, then
    # whatever the rest needs.
    return random_look(rest, rng).followed_by(state_solved_by(alg, before=_u_turn(pre)))


def case_scramble(case: Case, rng: np.random.Generator) -> str:
    """Generate a scramble that leaves the cube in ``case``, randomly AUFed.

    Args:
        case: The case to set up.
        rng: Random number generator (chooses the U turns around the case, and for
            OLL the permutation of the pieces).

    Returns:
        The scramble in standard notation.

    """
    state = case_state(case, rng)
    return format_alg(invert_alg(solve_facelets(state.facelets())))


class CaseRecognizer:
    """Finds which case of a set a scramble produces."""

    def __init__(self, case_set: CaseSet) -> None:
        """Index the set's cases by their kind and AUF-independent key.

        Args:
            case_set: The cases to recognise (2-look sets mix two kinds).

        """
        self._kinds: list[CaseKind] = list(
            dict.fromkeys(c.kind for c in case_set.cases),
        )
        self._by_key: dict[tuple[CaseKind, str], Case] = {}
        for case in case_set.cases:
            key = case_key(case.kind, case.state())
            assert key is not None  # noqa: S101 - every bundled case is valid
            self._by_key[case.kind, key] = case

    def recognize(self, scramble: str) -> Case | None:
        """Return the case a scramble leaves on a solved cube.

        Args:
            scramble: The scramble in standard notation.

        Returns:
            The case, or None if the scramble doesn't produce one of the set's cases.

        """
        state = SOLVED.apply(parse_alg(scramble))
        for kind in self._kinds:
            key = case_key(kind, state)
            if key is not None and (kind, key) in self._by_key:
                return self._by_key[kind, key]
        return None


def active_cases(case_set: CaseSet, prefs: TrainerPrefs) -> tuple[list[Case], bool]:
    """Return the cases the trainer currently picks from.

    Args:
        case_set: The set being trained.
        prefs: Where the filter and the learning statuses come from.

    Returns:
        The cases passing the filter, and False; or, if none pass (e.g. after
        statuses changed in the Learn tab), every case of the set and True.

    """
    matching = prefs.load_filter().matching(case_set, prefs.statuses())
    if matching:
        return matching, False
    return list(case_set.cases), True


def filtered_case_scrambles(
    case_set: CaseSet,
    prefs: TrainerPrefs,
    rng: np.random.Generator,
    history: Callable[[], Sequence[Solve]] = tuple,
) -> Callable[[], str]:
    """Build a generator of scrambles for cases picked according to the filter.

    The filter and statuses are read again on every call, so changes to them (in the
    filter dialog or the Learn tab) apply from the next scramble.

    Args:
        case_set: The set being trained.
        prefs: Where the filter and the learning statuses come from.
        rng: Random number generator.
        history: Returns the set's solves, oldest first, for slowest-first odds
            (read on every call, so it includes the latest solve).

    Returns:
        A function returning a new case scramble each time it's called.

    """

    def generate() -> str:
        # The user's algorithms decide the orientation the case is set up in.
        current = customize(case_set, prefs.customizations())
        cases, _ = active_cases(current, prefs)
        case = pick_case(cases, rng, prefs.load_filter().odds, history())
        return case_scramble(case, rng)

    return generate
