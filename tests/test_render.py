"""Tests for the last-layer image renderer."""

import pytest
from PySide6.QtGui import QColor

from cubetrainer.cases.catalog import Case, load_case_set
from cubetrainer.cube.model import SOLVED, parse_alg, state_solved_by
from cubetrainer.cube.render import (
    COLOR_SCHEME,
    IGNORED_COLOR,
    Arrow,
    RenderStyle,
    piece_arrows,
    render_last_layer,
)

T_PERM = "R U R' U' R' F R2 U' R' U' R U R' F'"


def test_solved_cube_has_no_arrows() -> None:
    """Nothing moves on a solved cube."""
    assert piece_arrows(SOLVED) == []


def test_t_perm_arrows() -> None:
    """T swaps the UL/UR edges and the UBR/UFR corners."""
    arrows = piece_arrows(state_solved_by(parse_alg(T_PERM)))

    assert sorted(arrows, key=lambda a: a.start) == [
        Arrow(start=(0, 1), end=(2, 1), both_ways=True),  # UL <-> UR
        Arrow(start=(2, 0), end=(2, 2), both_ways=True),  # UBR <-> UFR
    ]


def test_u_perm_arrows_form_a_cycle() -> None:
    """A U perm shows three one-way arrows around the edges."""
    arrows = piece_arrows(state_solved_by(parse_alg("M2 U M U2 M' U M2")))

    assert len(arrows) == 3
    assert not any(a.both_ways for a in arrows)
    assert {a.start for a in arrows} == {a.end for a in arrows}


def test_arrows_ignore_final_auf() -> None:
    """An algorithm ending a U turn away from solved still shows only its swaps."""
    state = state_solved_by(parse_alg(T_PERM + " U"))

    assert len(piece_arrows(state)) == 2


#: (corners moving, edges moving, two-piece swaps) in each PLL diagram.
PLL_STRUCTURE: dict[str, tuple[int, int, int]] = {
    **dict.fromkeys(["Aa", "Ab"], (3, 0, 0)),
    **dict.fromkeys(["Ga", "Gb", "Gc", "Gd"], (3, 3, 0)),
    **dict.fromkeys(["Ua", "Ub"], (0, 3, 0)),
    **dict.fromkeys(["H", "Z"], (0, 4, 2)),
    "E": (4, 0, 2),
    **dict.fromkeys(
        ["F", "Ja", "Jb", "Ra", "Rb", "T", "Na", "Nb", "V", "Y"],
        (2, 2, 2),
    ),
}


@pytest.mark.parametrize("case", load_case_set("pll").cases, ids=lambda c: c.id)
def test_pll_diagram_structure(case: Case) -> None:
    """Each PLL shows the usual cycles, e.g. G perms a corner and an edge 3-cycle."""
    arrows = piece_arrows(case.state())

    def moving(*, corners: bool) -> int:
        return sum(
            2 if a.both_ways else 1
            for a in arrows
            if (a.start[0] != 1 and a.start[1] != 1) == corners
        )

    swaps = sum(a.both_ways for a in arrows)
    assert (moving(corners=True), moving(corners=False), swaps) == PLL_STRUCTURE[
        case.id
    ]


def test_image_colours() -> None:
    """The image is square and transparent, with yellow U stickers."""
    size = 195  # 50 px per U-face cell
    image = render_last_layer(SOLVED, size)

    assert (image.width(), image.height()) == (size, size)
    assert image.pixelColor(0, 0).alpha() == 0
    centre = image.pixelColor(size // 2, size // 2)
    assert centre.name() == QColor(COLOR_SCHEME["U"]).name()
    front_strip = image.pixelColor(size // 2, size - 5)
    assert front_strip.name() == QColor(COLOR_SCHEME["F"]).name()


def test_arrows_are_drawn_on_request() -> None:
    """With arrows on, the U face gets dark pixels; with arrows off it doesn't."""
    state = state_solved_by(parse_alg(T_PERM))
    size = 195
    # Middle of the UL-UR swap arrow, crossing the centre cell.
    point = (size // 2, size // 2)

    with_arrows = render_last_layer(state, size).pixelColor(*point)
    without = render_last_layer(state, size, RenderStyle(arrows=False)).pixelColor(
        *point,
    )

    assert with_arrows.lightness() < 60
    assert without.name() == QColor(COLOR_SCHEME["U"]).name()


#: Cell (column, row) of each top-layer position; row 0 is the back.
CELLS: dict[str, tuple[int, int]] = {
    "UBL": (0, 0),
    "UB": (1, 0),
    "UBR": (2, 0),
    "UL": (0, 1),
    "UR": (2, 1),
    "UFL": (0, 2),
    "UF": (1, 2),
    "UFR": (2, 2),
}

#: G perm diagrams as confirmed by hand (green in front): piece -> where it goes.
G_PERM_MOVES: dict[str, dict[str, str]] = {
    "Ga": {
        "UBL": "UBR",
        "UB": "UL",
        "UBR": "UFL",
        "UL": "UR",
        "UR": "UB",
        "UFL": "UBL",
    },
    "Gb": {
        "UBL": "UFL",
        "UB": "UF",
        "UL": "UB",
        "UFL": "UFR",
        "UF": "UL",
        "UFR": "UBL",
    },
    "Gc": {
        "UBL": "UFL",
        "UL": "UR",
        "UR": "UF",
        "UFL": "UFR",
        "UF": "UL",
        "UFR": "UBL",
    },
    "Gd": {
        "UBL": "UBR",
        "UB": "UL",
        "UBR": "UFL",
        "UL": "UF",
        "UFL": "UBL",
        "UF": "UB",
    },
}


@pytest.mark.parametrize("case_id", sorted(G_PERM_MOVES))
def test_g_perm_arrows_match_confirmed_diagrams(case_id: str) -> None:
    """Each G perm shows the hand-checked cycles, keeping its block in place."""
    case = next(c for c in load_case_set("pll").cases if c.id == case_id)

    arrows = piece_arrows(case.state())

    expected = {CELLS[a]: CELLS[b] for a, b in G_PERM_MOVES[case_id].items()}
    assert {a.start: a.end for a in arrows} == expected


def test_orientation_only_shows_yellow_and_grey() -> None:
    """OLL images: U-coloured stickers yellow, the others grey, no arrows."""
    sune = next(c for c in load_case_set("oll").cases if c.id == "27")
    size = 195
    image = render_last_layer(
        sune.state(),
        size,
        RenderStyle(arrows=False, orientation_only=True),
    )

    colours = {
        image.pixelColor(x, y).name()
        for x in range(5, size, 10)
        for y in range(5, size, 10)
        if image.pixelColor(x, y).alpha() == 255
    }
    assert QColor(COLOR_SCHEME["U"]).name() in colours
    assert QColor(IGNORED_COLOR).name() in colours
    assert QColor(COLOR_SCHEME["F"]).name() not in colours


@pytest.mark.parametrize(
    ("hide_corners", "hide_edges", "corner_grey", "edge_grey"),
    [(True, False, True, False), (False, True, False, True)],
)
def test_hiding_corners_or_edges(
    *,
    hide_corners: bool,
    hide_edges: bool,
    corner_grey: bool,
    edge_grey: bool,
) -> None:
    """Hidden pieces are drawn grey, including their U-face sticker."""
    size = 195  # 50 px per U-face cell; the U face starts at 0.45 cells
    image = render_last_layer(
        SOLVED,
        size,
        RenderStyle(hide_corners=hide_corners, hide_edges=hide_edges),
    )
    grey = QColor(IGNORED_COLOR).name()
    corner_pixel = image.pixelColor(int(size * 1.0 / 3.9), int(size * 1.0 / 3.9)).name()
    edge_pixel = image.pixelColor(size // 2, int(size * 1.0 / 3.9)).name()

    assert (corner_pixel == grey) == corner_grey
    assert (edge_pixel == grey) == edge_grey


def test_corner_only_arrows_ignore_edges() -> None:
    """A T perm with edges ignored shows just the corner swap."""
    arrows = piece_arrows(state_solved_by(parse_alg(T_PERM)), corners_only=True)

    assert arrows == [Arrow(start=(2, 0), end=(2, 2), both_ways=True)]
