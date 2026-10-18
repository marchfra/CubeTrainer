"""Draw the app icon and write it as a macOS icon file (CubeTrainer.icns).

The icon is the solved cube, drawn like the Notation pictures, on a dark rounded
tile in the Calm theme's colours. macOS wants every size from 16 to 1024 pixels;
they are drawn here and packed with Apple's ``iconutil``.

Run it with ``uv run python app_bundle/make_icon.py`` (the build script runs it when
the icon file is missing).
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication

from cubetrainer.cube.move_render import render_solved_cube

#: Where the icon file is written.
ICON_PATH: Path = Path(__file__).parent / "CubeTrainer.icns"

#: The tile's gradient, top to bottom (Calm's dark surfaces).
_TILE_TOP: str = "#232834"
_TILE_BOTTOM: str = "#0e1014"

#: Apple's icon grid, as fractions of the canvas: the tile's inset and corner radius.
_TILE_INSET: float = 100 / 1024
_TILE_RADIUS: float = 185 / 1024

#: The cube's size, as a fraction of the canvas (bigger when the icon is tiny).
_CUBE: float = 0.62
_SMALL_CUBE: float = 0.7

#: Up to this many pixels the faces are solid blocks (stickers would be a blur of
#: dark lines); up to _THIN_LINES the stickers get thinner lines.
_SOLID_FACES: int = 32
_THIN_LINES: int = 128

#: Icon sizes (points) and the scales macOS wants for each.
_SIZES: tuple[int, ...] = (16, 32, 128, 256, 512)


def draw_icon(size: int) -> QImage:
    """Draw the icon at a size.

    Args:
        size: Width and height in pixels.

    Returns:
        The icon, on a transparent background.

    """
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = size * _TILE_INSET
        tile = QRectF(inset, inset, size - 2 * inset, size - 2 * inset)
        gradient = QLinearGradient(tile.topLeft(), tile.bottomLeft())
        gradient.setColorAt(0, QColor(_TILE_TOP))
        gradient.setColorAt(1, QColor(_TILE_BOTTOM))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        radius = size * _TILE_RADIUS
        painter.drawRoundedRect(tile, radius, radius)
        small = size <= _SOLID_FACES
        cube_size = round(size * (_SMALL_CUBE if small else _CUBE))
        cube = render_solved_cube(
            cube_size,
            stickers=not small,
            line=0.5 if size <= _THIN_LINES else 1.0,
        )
        offset = (size - cube_size) / 2
        painter.drawImage(QRectF(offset, offset, cube_size, cube_size), cube)
    finally:
        painter.end()
    return image


def write_icns(path: Path = ICON_PATH) -> Path:
    """Draw every icon size and pack them into a macOS icon file.

    Args:
        path: Where to write the ``.icns`` file.

    Returns:
        The path written.

    Raises:
        RuntimeError: If Apple's ``iconutil`` isn't available (it's part of macOS).

    """
    iconutil = shutil.which("iconutil")
    if iconutil is None:
        msg = "iconutil not found: the icon can only be made on macOS"
        raise RuntimeError(msg)
    with tempfile.TemporaryDirectory() as folder:
        iconset = Path(folder) / "CubeTrainer.iconset"
        iconset.mkdir()
        for points in _SIZES:
            for scale in (1, 2):
                name = f"icon_{points}x{points}{'@2x' if scale == 2 else ''}.png"  # noqa: PLR2004
                draw_icon(points * scale).save(str(iconset / name))
        subprocess.run(  # noqa: S603 - a fixed command on files made here
            [iconutil, "--convert", "icns", "--output", str(path), str(iconset)],
            check=True,
        )
    return path


def main() -> None:
    """Write the icon file and say where it went."""
    # Drawing needs a QApplication; it must stay alive until the icon is written.
    app = QApplication.instance() or QApplication(sys.argv)
    path = write_icns()
    app.quit()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
