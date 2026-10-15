"""Random-state scramble generation.

A scramble is made by picking a uniformly random solvable cube state, solving it with
Kociemba's two-phase algorithm and inverting the solution. This is how WCA scramblers
(and cstimer) work, and gives scrambles of about 20 moves.
"""

import kociemba
import numpy as np

from cubetrainer.cube.model import Move, format_alg, invert_alg, parse_alg

#: Facelets of each corner position (URF, UFL, ULB, UBR, DFR, DLF, DBL, DRB), starting
#: with the U/D sticker and going clockwise. Indices are in facelet order.
CORNER_FACELETS: tuple[tuple[int, int, int], ...] = (
    (8, 9, 20),
    (6, 18, 38),
    (0, 36, 47),
    (2, 45, 11),
    (29, 26, 15),
    (27, 44, 24),
    (33, 53, 42),
    (35, 17, 51),
)

#: Facelets of each edge position (UR, UF, UL, UB, DR, DF, DL, DB, FR, FL, BL, BR).
EDGE_FACELETS: tuple[tuple[int, int], ...] = (
    (5, 10),
    (7, 19),
    (3, 37),
    (1, 46),
    (32, 16),
    (28, 25),
    (30, 43),
    (34, 52),
    (23, 12),
    (21, 41),
    (50, 39),
    (48, 14),
)

_FACE_OF = "URFDLB"


def _permutation_parity(perm: list[int]) -> int:
    """Return the parity of a permutation (0 for even, 1 for odd).

    Args:
        perm: A permutation of ``range(len(perm))``.

    Returns:
        0 if the permutation is even, 1 if odd.

    """
    seen = [False] * len(perm)
    parity = 0
    for start in range(len(perm)):
        length = 0
        i = start
        while not seen[i]:
            seen[i] = True
            i = perm[i]
            length += 1
        if length:
            parity ^= (length - 1) & 1
    return parity


def random_facelets(rng: np.random.Generator) -> str:
    """Generate the facelet string of a uniformly random solvable cube state.

    Args:
        rng: Random number generator.

    Returns:
        A 54-character facelet string in Kociemba order.

    """
    cp = [int(i) for i in rng.permutation(8)]
    ep = [int(i) for i in rng.permutation(12)]
    if _permutation_parity(cp) != _permutation_parity(ep):
        # Swapping two edges fixes the parity while keeping the distribution uniform.
        ep[0], ep[1] = ep[1], ep[0]
    co = [int(i) for i in rng.integers(0, 3, size=7)]
    co.append(-sum(co) % 3)
    eo = [int(i) for i in rng.integers(0, 2, size=11)]
    eo.append(sum(eo) % 2)

    facelets = ["U"] * 54
    for i in range(8):
        for k in range(3):
            source = CORNER_FACELETS[cp[i]][k]
            facelets[CORNER_FACELETS[i][(k + co[i]) % 3]] = _FACE_OF[source // 9]
    for i in range(12):
        for k in range(2):
            source = EDGE_FACELETS[ep[i]][k]
            facelets[EDGE_FACELETS[i][(k + eo[i]) % 2]] = _FACE_OF[source // 9]
    for f in range(6):
        facelets[9 * f + 4] = _FACE_OF[f]
    return "".join(facelets)


def solve_facelets(facelets: str) -> list[Move]:
    """Solve a cube state with the two-phase algorithm.

    Args:
        facelets: 54-character facelet string in Kociemba order.

    Returns:
        A move sequence that solves the state (empty if already solved).

    Raises:
        ValueError: If the facelet string doesn't describe a solvable cube.

    """
    if facelets == "".join(f * 9 for f in _FACE_OF):
        return []
    try:
        solution = kociemba.solve(facelets)
    except ValueError as exc:
        msg = f"unsolvable state {facelets!r}"
        raise ValueError(msg) from exc
    return parse_alg(solution)


def random_state_scramble(rng: np.random.Generator) -> str:
    """Generate a WCA-style random-state scramble for the full cube.

    Args:
        rng: Random number generator.

    Returns:
        The scramble in standard notation.

    """
    return format_alg(invert_alg(solve_facelets(random_facelets(rng))))
