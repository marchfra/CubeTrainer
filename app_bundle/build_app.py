"""Build CubeTrainer as a standalone app with PyInstaller, and install it.

    python -m app_bundle.build_app              # builds it, into dist/
    python -m app_bundle.build_app --install    # ...and installs it
    python -m app_bundle.build_app --uninstall  # removes what --install added

Run it from the project folder. It needs PyInstaller: ``pip install ".[app]"``
(or prefix the commands with ``uv run`` in a uv checkout).
Each system builds its own app: CubeTrainer.app on macOS, a CubeTrainer folder on
Windows and Linux (see ``platforms.py`` for where they're installed). The app keeps
its data where ``cubetrainer`` does, so both see the same solves and settings.
Rebuild after changing the code: the app holds a copy.
"""

import argparse
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path, PurePath

import platformdirs

from app_bundle.launcher import WARM_UP, matplotlib_cache_dir
from app_bundle.platforms import (
    InstallLayout,
    desktop_entry,
    home_layout,
    shortcut_script,
)

#: The project's root folder.
ROOT: Path = Path(__file__).resolve().parent.parent

#: Where the app is built, and where PyInstaller keeps its working files.
DIST: Path = ROOT / "dist"
WORK: Path = ROOT / "build"

#: Makes a Windows shortcut: (shortcut file, program it starts).
type ShortcutMaker = Callable[[Path, Path], None]

#: Runs the installed app once to build its font cache: (the app's program).
type WarmUp = Callable[[Path], None]


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


def make_icon(layout: InstallLayout) -> Path:
    """Draw the icon in this system's format, into the build folder.

    Args:
        layout: This system's layout (it says which format).

    Returns:
        The icon file.

    """
    # Drawing needs Qt, but not a screen (e.g. a Linux machine without one).
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415 - only for drawing

    from app_bundle.make_icon import write_icon  # noqa: PLC0415

    app = QApplication.instance() or QApplication(sys.argv)
    path = write_icon(layout.icon_format, WORK / "icons")
    app.quit()
    return path


def build(layout: InstallLayout) -> tuple[Path, Path]:
    """Build the app with PyInstaller.

    Args:
        layout: This system's layout.

    Returns:
        The built app, and its icon file.

    """
    icon = make_icon(layout)
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
        env={**os.environ, "CUBETRAINER_ICON": str(icon)},
    )
    built = DIST / layout.built
    if layout.system == "darwin":
        # The plain folder PyInstaller also leaves is a by-product of the .app.
        shutil.rmtree(DIST / "CubeTrainer", ignore_errors=True)
    return built, icon


def make_windows_shortcut(shortcut: Path, target: Path) -> None:
    """Create a Windows shortcut with Windows' own shortcut maker (PowerShell).

    Args:
        shortcut: The ``.lnk`` file to create.
        target: The program it starts.

    """
    subprocess.run(  # noqa: S603 - PowerShell with a script built from paths
        [  # noqa: S607 - PowerShell is found on PATH on every Windows
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            shortcut_script(shortcut, target),
        ],
        check=True,
    )


def _remove(path: Path) -> None:
    """Delete a file or folder, if it's there.

    Args:
        path: What to delete.

    """
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def install(
    layout: InstallLayout,
    built: Path,
    icon: Path,
    make_shortcut: ShortcutMaker = make_windows_shortcut,
    warm_up: WarmUp | None = None,
) -> list[Path]:
    """Copy the built app into place and add its launcher, replacing older ones.

    Then the installed app is run once to build matplotlib's font cache, so its
    first launch doesn't stall while that happens (see ``launcher.py``).

    Args:
        layout: Where things go.
        built: The built app.
        icon: The icon file (copied for the Linux launcher).
        make_shortcut: Creates the Windows Start Menu shortcut.
        warm_up: Runs the installed app to build its cache; ``warm_up_cache``
            if omitted.

    Returns:
        What was created.

    """
    app = Path(layout.app)
    _remove(app)
    app.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(built, app, symlinks=True)
    if layout.icon is not None:
        target = Path(layout.icon)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(icon, target)
    if layout.launcher is not None:
        launcher = Path(layout.launcher)
        launcher.parent.mkdir(parents=True, exist_ok=True)
        _remove(launcher)
        if layout.system == "linux" and layout.icon is not None:
            launcher.write_text(
                desktop_entry(layout.executable, layout.icon),
                encoding="utf-8",
            )
        elif layout.system == "win32":
            make_shortcut(launcher, Path(layout.executable))
    (warm_up or warm_up_cache)(Path(layout.executable))
    return [Path(p) for p in layout.installed_paths()]


def warm_up_cache(executable: Path) -> None:
    """Run the installed app once, only to build its font cache (then it exits).

    Args:
        executable: The installed app's program.

    """
    print("Preparing the app's font cache (once; this can take a while)...")
    subprocess.run(  # noqa: S603 - the app just installed
        [str(executable)],
        check=True,
        env={**os.environ, WARM_UP: "1"},
    )


def uninstall(layout: InstallLayout, cache_root: Path | None = None) -> list[Path]:
    """Remove what ``install`` added, and the installed app's font cache.

    Args:
        layout: Where things went.
        cache_root: The app's cache folder (platformdirs' ``user_cache_dir``) if
            omitted.

    Returns:
        What was removed (things already missing are skipped).

    """
    if cache_root is None:
        cache_root = Path(platformdirs.user_cache_dir("CubeTrainer", appauthor=False))
    cache = matplotlib_cache_dir(str(layout.executable), cache_root)
    removed = []
    for path in [*map(Path, layout.installed_paths()), cache]:
        if path.exists() or path.is_symlink():
            _remove(path)
            removed.append(path)
    return removed


def _show(path: PurePath) -> str:
    """Write a path with the home folder as ``~``, for messages.

    Args:
        path: The path.

    Returns:
        It, shortened.

    """
    home = str(Path.home())
    text = str(path)
    return "~" + text[len(home) :] if text.startswith(home) else text


def main() -> None:
    """Build the app, and install it if asked; or uninstall it."""
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--install", action="store_true", help="also install the app")
    group.add_argument(
        "--uninstall",
        action="store_true",
        help="remove what --install added (without building)",
    )
    args = parser.parse_args()
    layout = home_layout(sys.platform, Path.home(), os.environ)
    if args.uninstall:
        removed = uninstall(layout)
        print("\n".join(f"Removed {_show(p)}" for p in removed) or "Nothing to remove")
        return
    built, icon = build(layout)
    print(f"Built {_show(built)} ({folder_size(built) / 1e6:.0f} MB)")
    if args.install:
        for path in install(layout, built, icon):
            print(f"Installed {_show(path)}")


if __name__ == "__main__":
    main()
