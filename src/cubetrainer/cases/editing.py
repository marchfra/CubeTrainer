"""Checking a user's algorithm for a case."""

from cubetrainer.cases.catalog import Case
from cubetrainer.cases.recognition import case_key
from cubetrainer.cube.model import AlgorithmParseError, parse_alg, state_solved_by


def alg_problem(case: Case, alg: str) -> str | None:
    """Explain why an algorithm can't be used for a case, if it can't.

    An algorithm is accepted when it solves the same case as the default one; it may
    start from another U turn, end with an AUF, or use rotations.

    Args:
        case: The bundled case (its algorithm is the reference).
        alg: The algorithm the user typed.

    Returns:
        A short message describing the problem, or None if the algorithm is fine.

    """
    if not alg.strip():
        return "Enter an algorithm"
    try:
        moves = parse_alg(alg)
    except AlgorithmParseError as error:
        return f"Not valid notation: {error}"
    key = case_key(case.kind, state_solved_by(moves))
    if key is None or key != case_key(case.kind, case.state()):
        return f"Doesn't solve {case.name}"
    return None
