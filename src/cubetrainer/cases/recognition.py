"""Identify last-layer cases independently of the AUFs around them."""

from cubetrainer.cases.catalog import CaseKind
from cubetrainer.cube.model import STICKERS, CubeState, Move

#: Side faces in the order a U turn cycles their top-row colours.
_SIDE_CYCLE: str = "FLBR"

#: Facelet indices of the 12 side stickers of the top layer.
_TOP_SIDE_STICKERS: tuple[int, ...] = tuple(
    i
    for i, (position, normal) in enumerate(STICKERS)
    if position[1] == 1 and normal[1] == 0
)

#: Facelet indices of the stickers in the bottom two layers (F2L).
_F2L_STICKERS: tuple[int, ...] = tuple(
    i for i, (position, _normal) in enumerate(STICKERS) if position[1] < 1
)


def is_f2l_solved(state: CubeState) -> bool:
    """Check that the first two layers are solved.

    Args:
        state: A cube state in standard orientation.

    Returns:
        True if every sticker below the top layer is on its home face.

    """
    facelets = state.facelets()
    return all(facelets[i] == "URFDLB"[i // 9] for i in _F2L_STICKERS)


def is_oll_solved(state: CubeState) -> bool:
    """Check that F2L is solved and the whole U face shows the U colour.

    Args:
        state: A cube state in standard orientation.

    Returns:
        True if only the permutation of the last layer may be wrong.

    """
    return is_f2l_solved(state) and state.facelets()[:9] == "U" * 9


def pll_key(state: CubeState) -> str:
    """Return a key identifying a PLL case regardless of pre- and post-AUF.

    Two states have the same key exactly when they are the same PLL case: the key is
    the smallest top-layer side pattern over the four pre-AUFs (turning the U layer)
    and the four post-AUFs (cyclically relabelling the side colours).

    Args:
        state: A cube state with OLL solved, in standard orientation.

    Returns:
        A 12-character key.

    Raises:
        ValueError: If the state is not a PLL (the F2L or the U face isn't solved).

    """
    if not is_oll_solved(state):
        msg = "pll_key needs a state with F2L and OLL solved"
        raise ValueError(msg)
    candidates: list[str] = []
    for pre in range(4):
        turned = state.apply([Move("U", pre)]) if pre else state
        pattern = "".join(turned.facelets()[i] for i in _TOP_SIDE_STICKERS)
        for post in range(4):
            relabel = {
                face: _SIDE_CYCLE[(_SIDE_CYCLE.index(face) + post) % 4]
                for face in _SIDE_CYCLE
            }
            candidates.append("".join(relabel[c] for c in pattern))
    return min(candidates)


#: Facelet indices of all 21 top-layer stickers (U face and the sides' top rows).
_TOP_LAYER_STICKERS: tuple[int, ...] = tuple(
    i for i, (position, _normal) in enumerate(STICKERS) if position[1] == 1
)


def oll_pattern(state: CubeState) -> str:
    """Return which top-layer stickers show the U colour, as a string of 0s and 1s.

    This is what an OLL case looks like; the permutation of the pieces is ignored.

    Args:
        state: A cube state in standard orientation.

    Returns:
        A 21-character string, one character per top-layer sticker.

    """
    facelets = state.facelets()
    return "".join("1" if facelets[i] == "U" else "0" for i in _TOP_LAYER_STICKERS)


def oll_key(state: CubeState) -> str:
    """Return a key identifying an OLL case regardless of the U turn before it.

    Args:
        state: A cube state with F2L solved, in standard orientation.

    Returns:
        The smallest orientation pattern over the four turns of the U layer.

    Raises:
        ValueError: If F2L isn't solved.

    """
    if not is_f2l_solved(state):
        msg = "oll_key needs a state with F2L solved"
        raise ValueError(msg)
    return min(
        oll_pattern(state.apply([Move("U", turns)]) if turns else state)
        for turns in range(4)
    )


def case_key(kind: CaseKind, state: CubeState) -> str | None:
    """Identify the case a state shows, for sets of the given kind.

    Args:
        kind: OLL or PLL.
        state: A cube state in standard orientation.

    Returns:
        The case key (``oll_key`` or ``pll_key``), or None if the state isn't a case
        of that kind (F2L broken, or for PLL, the U face not solved).

    """
    if kind is CaseKind.PLL:
        return pll_key(state) if is_oll_solved(state) else None
    return oll_key(state) if is_f2l_solved(state) else None
