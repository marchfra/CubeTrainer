"""Draw the app icon, and write it in each system's format.

The icon is the solved cube, drawn like the Notation pictures, on a dark rounded
tile in the Calm theme's colours (simplified at small sizes, so it stays readable).
Each system wants its own file:

- macOS: ``.icns``, every size from 16 to 1024 pixels, packed with Apple's
  ``iconutil``;
- Windows: ``.ico``, several sizes (written here: PNG images in an ICO wrapper);
- Linux: a 256-pixel ``.png``.

The build script makes the one it needs; ``python -m app_bundle.make_icon`` (from
the project folder) writes this system's icon into ``build/icons`` to look at.
"""

import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QImageWriter, QLinearGradient, QPainter
from PySide6.QtWidgets import QApplication

from app_bundle.platforms import home_layout
from cubetrainer.cube.move_render import render_solved_cube

#: Where ``main`` writes the icon.
ICON_FOLDER: Path = Path(__file__).resolve().parent.parent / "build" / "icons"

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

#: Sizes in a Windows icon (Windows picks the one it needs).
_ICO_SIZES: tuple[int, ...] = (16, 24, 32, 48, 64, 128, 256)

#: Size of the Linux icon.
PNG_SIZE: int = 256


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


def _png_bytes(size: int) -> bytes:
    """Draw the icon at a size and encode it as PNG.

    Args:
        size: Width and height in pixels.

    Returns:
        The PNG file's bytes.

    """
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    # QImageWriter, not QImage.save: PySide's save wants a str format at run time
    # but its type stubs say bytes; the writer takes bytes in both.
    QImageWriter(buffer, QByteArray(b"PNG")).write(draw_icon(size))
    buffer.close()
    return bytes(data.data())


def write_ico(path: Path) -> Path:
    """Write a Windows icon file with several sizes.

    An ICO file is a small header, one directory entry per image, then the images;
    since Windows Vista each image can simply be a PNG.

    Args:
        path: Where to write the ``.ico`` file.

    Returns:
        The path written.

    """
    images = [(size, _png_bytes(size)) for size in _ICO_SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))  # reserved, icon, count
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        side = 0 if size >= 256 else size  # noqa: PLR2004 - in ICO, 0 means 256
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    path.write_bytes(header + entries + blobs)
    return path


def write_png(path: Path, size: int = PNG_SIZE) -> Path:
    """Write the icon as a PNG (for Linux launchers).

    Args:
        path: Where to write it.
        size: Width and height in pixels.

    Returns:
        The path written.

    """
    path.write_bytes(_png_bytes(size))
    return path


def write_icon(icon_format: str, folder: Path) -> Path:
    """Write the icon in a system's format.

    Args:
        icon_format: ``"icns"``, ``"ico"`` or ``"png"``.
        folder: Where to write ``CubeTrainer.<format>``.

    Returns:
        The path written.

    Raises:
        ValueError: For an unknown format.

    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"CubeTrainer.{icon_format}"
    writers = {"icns": write_icns, "ico": write_ico, "png": write_png}
    if icon_format not in writers:
        msg = f"unknown icon format {icon_format!r}"
        raise ValueError(msg)
    return writers[icon_format](path)


def write_icns(path: Path) -> Path:
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
    """Write this system's icon into ``build/icons`` and say where it went."""
    # Drawing needs a QApplication; it must stay alive until the icon is written.
    app = QApplication.instance() or QApplication(sys.argv)
    path = write_icon(
        home_layout(sys.platform, Path.home(), {}).icon_format,
        ICON_FOLDER,
    )
    app.quit()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
