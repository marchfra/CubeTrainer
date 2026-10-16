"""Scrambles that set up a chosen last-layer case, and recognising them again.

A case scramble is built like a full random-state scramble: the target state (the
case, with a random U turn before and after it) is solved with the two-phase solver
and the solution is inverted. The scramble therefore doesn't reveal the algorithm.
For OLL cases the pieces are also randomly permuted (a random PLL, with realistic
odds), as they would be in a real solve.

The case of a scramble is never stored alongside it: it's recognised from the
scramble itself, so the two can never disagree.
"""

from collections.abc import Callable

import numpy as np

from cubetrainer.cases.catalog import Case, CaseKind, CaseSet, load_case_set
from cubetrainer.cases.filters import (
    PLL_SKIP_WEIGHT,
    TrainerPrefs,
    case_weight,
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


def _u_turn(turns: int) -> list[Move]:
    """Return a U turn as a move list.

    Args:
        turns: Quarter turns, 0 to 3.

    Returns:
        ``[U, U2 or U']``, or an empty list for 0.

    """
    return [Move("U", turns)] if turns else []


def random_pll_state(rng: np.random.Generator) -> CubeState:
    """Return a random last-layer permutation with the U face solved.

    Every one of the 288 possible permutations (21 PLLs and the skip, with all their
    U turns) is equally likely, as on a randomly scrambled cube.

    Args:
        rng: Random number generator.

    Returns:
        A state with F2L and OLL solved.

    """
    plls = load_case_set("pll").cases
    weights = np.array([*(case_weight(c) for c in plls), PLL_SKIP_WEIGHT], dtype=float)
    choice = int(rng.choice(len(weights), p=weights / weights.sum()))
    pre, post = (int(turns) for turns in rng.integers(0, 4, size=2))
    if choice == len(plls):  # the skip: just a U turn
        return SOLVED.apply(_u_turn(pre))
    return state_solved_by(
        parse_alg(plls[choice].alg),
        before=_u_turn(pre),
        after=_u_turn(post),
    )


def case_state(case: Case, rng: np.random.Generator) -> CubeState:
    """Return a random state showing ``case``, with random U turns around it.

    Args:
        case: The case to set up.
        rng: Random number generator.

    Returns:
        The state (for OLL cases, with the pieces randomly permuted).

    """
    pre, post = (int(turns) for turns in rng.integers(0, 4, size=2))
    alg = parse_alg(case.alg)
    if case.kind is CaseKind.OLL:
        # A random PLL first, then the OLL case: solving it takes the OLL algorithm
        # and then some PLL, as in a real solve.
        return random_pll_state(rng).followed_by(
            state_solved_by(alg, before=_u_turn(pre)),
        )
    return state_solved_by(alg, before=_u_turn(pre), after=_u_turn(post))


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
        """Index the set's cases by their AUF-independent key.

        Args:
            case_set: The cases to recognise.

        """
        self._kind: CaseKind = case_set.kind
        self._by_key: dict[str, Case] = {}
        for case in case_set.cases:
            key = case_key(case_set.kind, case.state())
            assert key is not None  # noqa: S101 - every bundled case is valid
            self._by_key[key] = case

    def recognize(self, scramble: str) -> Case | None:
        """Return the case a scramble leaves on a solved cube.

        Args:
            scramble: The scramble in standard notation.

        Returns:
            The case, or None if the scramble doesn't produce one of the set's cases.

        """
        key = case_key(self._kind, SOLVED.apply(parse_alg(scramble)))
        return None if key is None else self._by_key.get(key)


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
) -> Callable[[], str]:
    """Build a generator of scrambles for cases picked according to the filter.

    The filter and statuses are read again on every call, so changes to them (in the
    filter dialog or the Learn tab) apply from the next scramble.

    Args:
        case_set: The set being trained.
        prefs: Where the filter and the learning statuses come from.
        rng: Random number generator.

    Returns:
        A function returning a new case scramble each time it's called.

    """

    def generate() -> str:
        cases, _ = active_cases(case_set, prefs)
        case = pick_case(cases, rng, realistic=prefs.load_filter().realistic)
        return case_scramble(case, rng)

    return generate
