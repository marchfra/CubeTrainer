"""Tests for the app icon drawing (the app bundle itself is built by a script)."""

from pytestqt.qtbot import QtBot

from app_bundle.make_icon import draw_icon
from cubetrainer.cube.model import STICKERS
from cubetrainer.cube.move_render import STILL_COLOR, render_solved_cube
from cubetrainer.cube.render import COLOR_SCHEME


def test_solved_cube_has_every_visible_face_in_colour(qtbot: QtBot) -> None:
    """The icon's cube shows yellow, green and orange faces, nothing greyed out."""
    del qtbot  # painting needs the QApplication
    image = render_solved_cube(240)
    colours = {
        image.pixelColor(x, y).name()
        for x in range(0, 240, 4)
        for y in range(0, 240, 4)
        if image.pixelColor(x, y).alpha() == 255
    }

    assert {COLOR_SCHEME["U"], COLOR_SCHEME["F"], COLOR_SCHEME["R"]} <= colours
    assert STILL_COLOR not in colours
    assert len(STICKERS) == 54


def test_icon_is_a_tile_with_transparent_corners(qtbot: QtBot) -> None:
    """Every size draws; the corners outside the rounded tile stay transparent."""
    del qtbot
    for size in (16, 64, 512, 1024):
        icon = draw_icon(size)
        assert icon.size().toTuple() == (size, size)
        assert icon.pixelColor(0, 0).alpha() == 0
        assert icon.pixelColor(size // 2, size // 8).alpha() == 255  # the tile
