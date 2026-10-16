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
    return _permutation_key(state, _TOP_SIDE_STICKERS)


def _permutation_key(state: CubeState, stickers: tuple[int, ...]) -> str:
    """Return the smallest colour pattern of some side stickers over all AUFs.

    Args:
        state: A cube state with OLL solved.
        stickers: Facelet indices of the top-layer side stickers to look at.

    Returns:
        The smallest pattern over the four pre-AUFs (turning the U layer) and the
        four post-AUFs (cyclically relabelling the side colours).

    """
    candidates: list[str] = []
    for pre in range(4):
        turned = state.apply([Move("U", pre)]) if pre else state
        pattern = "".join(turned.facelets()[i] for i in stickers)
        for post in range(4):
            relabel = {
                face: _SIDE_CYCLE[(_SIDE_CYCLE.index(face) + post) % 4]
                for face in _SIDE_CYCLE
            }
            candidates.append("".join(relabel[c] for c in pattern))
    return min(candidates)


#: Facelet indices of the 8 side stickers of the top-layer corners.
TOP_CORNER_SIDE_STICKERS: tuple[int, ...] = tuple(
    i for i in _TOP_SIDE_STICKERS if STICKERS[i][0][0] != 0 and STICKERS[i][0][2] != 0
)

#: Facelet indices of the U-face stickers of the four top-layer edges.
_U_FACE_EDGES: tuple[int, ...] = (1, 3, 5, 7)


def cp_key(state: CubeState) -> str:
    """Return a key identifying a corner permutation regardless of AUFs.

    Only the corners are looked at, as in the first look of 2-look PLL.

    Args:
        state: A cube state with OLL solved, in standard orientation.

    Returns:
        An 8-character key.

    Raises:
        ValueError: If the state is not a PLL (the F2L or the U face isn't solved).

    """
    if not is_oll_solved(state):
        msg = "cp_key needs a state with F2L and OLL solved"
        raise ValueError(msg)
    return _permutation_key(state, TOP_CORNER_SIDE_STICKERS)


def corner_pattern(state: CubeState) -> str:
    """Return the colours of the top corners' side stickers (no AUF folded in).

    Args:
        state: A cube state.

    Returns:
        An 8-character string.

    """
    facelets = state.facelets()
    return "".join(facelets[i] for i in TOP_CORNER_SIDE_STICKERS)


def eo_pattern(state: CubeState) -> str:
    """Return which top edges show the U colour on top, as four 0s and 1s.

    Args:
        state: A cube state.

    Returns:
        A 4-character string (UB, UL, UR, UF).

    """
    facelets = state.facelets()
    return "".join("1" if facelets[i] == "U" else "0" for i in _U_FACE_EDGES)


def edges_oriented(state: CubeState) -> bool:
    """Check that every top edge shows the U colour on top.

    Args:
        state: A cube state.

    Returns:
        True if the four top edges are oriented.

    """
    return eo_pattern(state) == "1111"


def eo_key(state: CubeState) -> str:
    """Return a key identifying an edge-orientation case regardless of the pre-AUF.

    Args:
        state: A cube state with F2L solved, in standard orientation.

    Returns:
        The smallest edge pattern over the four turns of the U layer.

    Raises:
        ValueError: If F2L isn't solved.

    """
    if not is_f2l_solved(state):
        msg = "eo_key needs a state with F2L solved"
        raise ValueError(msg)
    return min(
        eo_pattern(state.apply([Move("U", turns)]) if turns else state)
        for turns in range(4)
    )


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
    """Identify the case a state shows, for cases of the given kind.

    Args:
        kind: The kind of case to look for.
        state: A cube state in standard orientation.

    Returns:
        The case key, or None if the state can't be a case of that kind: F2L
        broken; the U face unsolved for PLL, CP and EP; the edges unoriented for CO.

    """
    if not is_f2l_solved(state):
        return None
    match kind:
        case CaseKind.OLL:
            return oll_key(state)
        case CaseKind.EO:
            return eo_key(state)
        case CaseKind.CO:
            return oll_key(state) if edges_oriented(state) else None
        case CaseKind.PLL | CaseKind.EP:
            return pll_key(state) if is_oll_solved(state) else None
        case CaseKind.CP:
            return cp_key(state) if is_oll_solved(state) else None
