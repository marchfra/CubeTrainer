"""Build CubeTrainer.app with PyInstaller, and optionally install it.

    uv run python app_bundle/build_app.py            # builds dist/CubeTrainer.app
    uv run python app_bundle/build_app.py --install  # ...and puts it in /Applications

The app keeps its data where ``uv run cubetrainer`` does, so both see the same
solves and settings. Rebuild after changing the code: the bundle holds a copy.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

#: The project's root folder.
ROOT: Path = Path(__file__).resolve().parent.parent

#: Where the app is built, and where PyInstaller keeps its working files.
DIST: Path = ROOT / "dist"
WORK: Path = ROOT / "build"

#: The built app.
APP: Path = DIST / "CubeTrainer.app"

#: Where ``--install`` puts it: the Mac's Applications folder, next to the other
#: apps (Spotlight, Launchpad and the Dock find it there).
INSTALLED: Path = Path("/Applications") / "CubeTrainer.app"


def folder_size(path: Path) -> int:
    """Return the total size of the files in a folder, counting each file once.

    App bundles link many files between folders; links aren't counted again.

    Args:
        path: The folder.

    Returns:
        Its size in bytes.

    """
    return sum(
        file.stat().st_size
        for file in path.rglob("*")
        if file.is_file() and not file.is_symlink()
    )


def build() -> Path:
    """Build the app (making the icon first, if it's missing).

    Returns:
        The app's path.

    """
    icon = ROOT / "app_bundle" / "CubeTrainer.icns"
    if not icon.exists():
        subprocess.run(  # noqa: S603 - this project's own script
            [sys.executable, str(ROOT / "app_bundle" / "make_icon.py")],
            check=True,
        )
    subprocess.run(  # noqa: S603 - PyInstaller from this environment
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--distpath",
            str(DIST),
            "--workpath",
            str(WORK),
            str(ROOT / "app_bundle" / "CubeTrainer.spec"),
        ],
        check=True,
    )
    # The bundle's plain folder copy is a by-product: only the .app is wanted.
    shutil.rmtree(DIST / "CubeTrainer", ignore_errors=True)
    return APP


def install(app: Path) -> Path:
    """Copy the app to /Applications, replacing an older copy.

    Args:
        app: The built app.

    Returns:
        Where it was installed.

    """
    INSTALLED.parent.mkdir(exist_ok=True)
    if INSTALLED.exists():
        shutil.rmtree(INSTALLED)
    shutil.copytree(app, INSTALLED, symlinks=True)
    return INSTALLED


def main() -> None:
    """Build the app, and install it if asked."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--install",
        action="store_true",
        help=f"also copy the app to {INSTALLED.parent}",
    )
    args = parser.parse_args()
    app = build()
    print(f"Built {app} ({folder_size(app) / 1e6:.0f} MB)")
    if args.install:
        print(f"Installed {install(app)}")


if __name__ == "__main__":
    main()
