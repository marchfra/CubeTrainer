"""Scrambles that set up a chosen last-layer case, and recognising them again.

A case scramble is built like a full random-state scramble: the target state (the
case, with a random U turn before and after it) is solved with the two-phase solver
and the solution is inverted. The scramble therefore doesn't reveal the algorithm.

The case of a scramble is never stored alongside it: it's recognised from the
scramble itself, so the two can never disagree.
"""

from collections.abc import Callable

import numpy as np

from cubetrainer.cases.catalog import Case, CaseSet
from cubetrainer.cases.recognition import is_oll_solved, pll_key
from cubetrainer.cube.model import (
    SOLVED,
    Move,
    format_alg,
    invert_alg,
    parse_alg,
    state_solved_by,
)
from cubetrainer.cube.scramble import solve_facelets


def case_scramble(case: Case, rng: np.random.Generator) -> str:
    """Generate a scramble that leaves the cube in ``case``, randomly AUFed.

    Args:
        case: The case to set up.
        rng: Random number generator (chooses the U turns around the case).

    Returns:
        The scramble in standard notation.

    """
    pre, post = (int(turns) for turns in rng.integers(0, 4, size=2))
    state = state_solved_by(
        parse_alg(case.alg),
        before=[Move("U", pre)] if pre else [],
        after=[Move("U", post)] if post else [],
    )
    return format_alg(invert_alg(solve_facelets(state.facelets())))


class CaseRecognizer:
    """Finds which case of a set a scramble produces."""

    def __init__(self, case_set: CaseSet) -> None:
        """Index the set's cases by their AUF-independent key.

        Args:
            case_set: The cases to recognise (currently PLL cases).

        """
        self._by_key: dict[str, Case] = {
            pll_key(case.state()): case for case in case_set.cases
        }

    def recognize(self, scramble: str) -> Case | None:
        """Return the case a scramble leaves on a solved cube.

        Args:
            scramble: The scramble in standard notation.

        Returns:
            The case, or None if the scramble doesn't produce one of the set's cases.

        """
        state = SOLVED.apply(parse_alg(scramble))
        if not is_oll_solved(state):
            return None
        return self._by_key.get(pll_key(state))


def uniform_case_scrambles(
    case_set: CaseSet,
    rng: np.random.Generator,
) -> Callable[[], str]:
    """Build a generator of scrambles for cases picked with equal probability.

    Args:
        case_set: The set to pick cases from.
        rng: Random number generator.

    Returns:
        A function returning a new case scramble each time it's called.

    """

    def generate() -> str:
        case = case_set.cases[int(rng.integers(len(case_set.cases)))]
        return case_scramble(case, rng)

    return generate
