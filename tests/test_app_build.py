"""Tests for building and installing the standalone app (without building it)."""

import dataclasses
import os
import struct
from pathlib import Path, PurePosixPath, PureWindowsPath

import pytest
from PySide6.QtGui import QImage
from pytestqt.qtbot import QtBot

from app_bundle.build_app import install, uninstall
from app_bundle.launcher import keep_matplotlib_cache, matplotlib_cache_dir
from app_bundle.make_icon import PNG_SIZE, write_icon
from app_bundle.platforms import (
    InstallLayout,
    desktop_entry,
    install_layout,
    shortcut_script,
    system_name,
)
from cubetrainer.ui.theme import BUNDLED_MONO, CLEAN, load_fonts, mono_family

HOME_POSIX = PurePosixPath("/home/ana")
HOME_WINDOWS = PureWindowsPath(r"C:\Users\Ana")


def test_macos_installs_the_bundle_in_applications() -> None:
    """On macOS the .app goes to /Applications, with no separate launcher."""
    layout = install_layout("darwin", PurePosixPath("/Users/ana"), {})

    assert layout.app == PurePosixPath("/Applications/CubeTrainer.app")
    assert layout.executable == layout.app / "Contents/MacOS/CubeTrainer"
    assert layout.launcher is None
    assert layout.icon_format == "icns"
    assert layout.installed_paths() == [layout.app]


def test_windows_installs_per_user_with_a_start_menu_shortcut() -> None:
    """On Windows: a per-user Programs folder, plus a Start Menu shortcut."""
    menu = PureWindowsPath(
        r"C:\Users\Ana\AppData\Roaming\Microsoft\Windows\Start Menu\Programs",
    )
    env = {"LOCALAPPDATA": r"C:\Users\Ana\AppData\Local"}

    layout = install_layout("win32", HOME_WINDOWS, env, menu)

    assert layout.app == PureWindowsPath(
        r"C:\Users\Ana\AppData\Local\Programs\CubeTrainer",
    )
    assert layout.executable == layout.app / "CubeTrainer.exe"
    assert layout.launcher == menu / "CubeTrainer.lnk"
    assert layout.icon is None
    assert layout.icon_format == "ico"


def test_windows_without_localappdata_uses_the_home_folder() -> None:
    """A missing LOCALAPPDATA falls back to the usual place under the home folder."""
    layout = install_layout("win32", HOME_WINDOWS, {}, PureWindowsPath(r"C:\menu"))

    assert layout.app == HOME_WINDOWS / "AppData/Local/Programs/CubeTrainer"


@pytest.mark.parametrize(
    ("env", "data"),
    [({}, "/home/ana/.local/share"), ({"XDG_DATA_HOME": "/data/ana"}, "/data/ana")],
    ids=["default", "XDG_DATA_HOME"],
)
def test_linux_installs_in_the_data_folder_with_a_desktop_file(
    env: dict[str, str],
    data: str,
) -> None:
    """On Linux: the data folder, a .desktop launcher and a hicolor icon."""
    launchers = PurePosixPath("/home/ana/.local/share/applications")

    layout = install_layout("linux", HOME_POSIX, env, launchers)

    assert layout.app == PurePosixPath(data) / "cubetrainer"
    assert layout.executable == layout.app / "CubeTrainer"
    assert layout.launcher == launchers / "cubetrainer.desktop"
    assert (
        layout.icon
        == PurePosixPath(data) / "icons/hicolor/256x256/apps/cubetrainer.png"
    )
    assert layout.icon_format == "png"


def test_unsupported_systems_and_missing_launchers() -> None:
    """Only the three systems build; Windows and Linux need the launcher folder."""
    assert system_name("linux2") == "linux"
    with pytest.raises(ValueError, match="isn't supported"):
        system_name("freebsd14")
    with pytest.raises(ValueError, match="launcher folder"):
        install_layout("linux", HOME_POSIX, {})


def test_desktop_entry_runs_the_app_with_its_icon() -> None:
    """The Linux launcher names the app, runs it and shows its icon."""
    text = desktop_entry(PurePosixPath("/a b/CubeTrainer"), PurePosixPath("/i/c.png"))

    assert text.startswith("[Desktop Entry]\n")
    assert 'Exec="/a b/CubeTrainer"' in text
    assert "Icon=/i/c.png" in text
    assert "Name=CubeTrainer" in text
    assert "Terminal=false" in text


def test_shortcut_script_quotes_paths() -> None:
    """Paths go into PowerShell single quotes, with quotes inside doubled."""
    script = shortcut_script(
        PureWindowsPath(r"C:\Menu\CubeTrainer.lnk"),
        PureWindowsPath(r"C:\Ana's\CubeTrainer.exe"),
    )

    assert r"CreateShortcut('C:\Menu\CubeTrainer.lnk')" in script
    assert r"$s.TargetPath = 'C:\Ana''s\CubeTrainer.exe'" in script
    assert script.endswith("$s.Save()")


def _built_folder(root: Path) -> Path:
    """Make a fake build output: a folder with a program and a data file.

    Args:
        root: Where to make it.

    Returns:
        The folder.

    """
    built = root / "dist" / "CubeTrainer"
    (built / "_internal").mkdir(parents=True)
    (built / "CubeTrainer").write_text("program")
    (built / "_internal" / "data.json").write_text("{}")
    return built


def test_linux_install_and_uninstall_round_trip(tmp_path: Path) -> None:
    """Install copies the app, launcher and icon; uninstall removes exactly those."""
    data = tmp_path / "share"
    layout = install_layout(
        "linux",
        HOME_POSIX,
        {"XDG_DATA_HOME": str(data)},
        data / "applications",
    )
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"png")

    warmed: list[Path] = []
    created = install(layout, _built_folder(tmp_path), icon, warm_up=warmed.append)

    assert (data / "cubetrainer" / "_internal" / "data.json").exists()
    desktop = data / "applications" / "cubetrainer.desktop"
    assert f'Exec="{data / "cubetrainer" / "CubeTrainer"}"' in desktop.read_text()
    assert Path(layout.icon or "").read_bytes() == b"png"
    assert set(created) == {Path(p) for p in layout.installed_paths()}

    assert warmed == [Path(layout.executable)]  # the installed app ran once
    install(layout, _built_folder(tmp_path / "again"), icon, warm_up=warmed.append)
    cache = matplotlib_cache_dir(str(layout.executable), tmp_path / "cache")
    cache.mkdir(parents=True)  # as the warm-up would
    assert uninstall(layout, tmp_path / "cache") == [*created, cache]
    assert not any(Path(p).exists() for p in layout.installed_paths())
    assert uninstall(layout, tmp_path / "cache") == []  # nothing left to remove


def test_windows_install_makes_the_shortcut(tmp_path: Path) -> None:
    """On Windows the shortcut maker is asked for the Start Menu entry."""
    layout = InstallLayout(
        system="win32",
        built=PurePosixPath("CubeTrainer"),
        app=tmp_path / "Programs" / "CubeTrainer",
        executable=tmp_path / "Programs" / "CubeTrainer" / "CubeTrainer.exe",
        launcher=tmp_path / "Start Menu" / "CubeTrainer.lnk",
        icon=None,
        icon_format="ico",
    )
    made: list[tuple[Path, Path]] = []

    def make_shortcut(shortcut: Path, target: Path) -> None:
        made.append((shortcut, target))
        shortcut.write_text("lnk")

    install(
        layout,
        _built_folder(tmp_path),
        tmp_path / "unused.ico",
        make_shortcut,
        warm_up=lambda _program: None,
    )

    assert made == [(Path(layout.launcher or ""), Path(layout.executable))]
    assert len(uninstall(layout, tmp_path / "cache")) == 2


def test_ico_holds_several_sizes(qtbot: QtBot, tmp_path: Path) -> None:
    """The Windows icon has seven sizes, and Qt can read it back."""
    del qtbot
    path = write_icon("ico", tmp_path)

    reserved, kind, count = struct.unpack("<HHH", path.read_bytes()[:6])
    assert (reserved, kind, count) == (0, 1, 7)
    assert not QImage(str(path)).isNull()


def test_png_icon_for_linux(qtbot: QtBot, tmp_path: Path) -> None:
    """The Linux icon is a 256-pixel PNG; unknown formats are refused."""
    del qtbot
    image = QImage(str(write_icon("png", tmp_path)))

    assert image.size().toTuple() == (PNG_SIZE, PNG_SIZE)
    with pytest.raises(ValueError, match="unknown icon format"):
        write_icon("gif", tmp_path)


def test_fixed_width_font_falls_back(qtbot: QtBot) -> None:
    """A theme's missing fixed-width font is replaced by a fallback, then Geist Mono."""
    del qtbot
    load_fonts()
    missing = dataclasses.replace(CLEAN, mono_font="No Such Mono", mono_fallbacks=())
    assert mono_family(missing) == BUNDLED_MONO

    fallback = dataclasses.replace(missing, mono_fallbacks=("Nor This", "Geist Mono"))
    assert mono_family(fallback) == "Geist Mono"


def test_matplotlib_cache_is_kept_per_install_location(tmp_path: Path) -> None:
    """Each install location gets its own lasting cache folder, the same each time."""
    applications = matplotlib_cache_dir("/Applications/CubeTrainer.app/x", tmp_path)

    assert applications == matplotlib_cache_dir(
        "/Applications/CubeTrainer.app/x",
        tmp_path,
    )
    assert applications != matplotlib_cache_dir("/dist/CubeTrainer.app/x", tmp_path)
    assert applications.parent == tmp_path
    assert applications.name.startswith("matplotlib-")


def test_launcher_points_matplotlib_at_a_lasting_folder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The launcher overrides the temporary folder PyInstaller's hook sets."""
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "temporary"))
    monkeypatch.setattr(
        "platformdirs.user_cache_dir",
        lambda *_args, **_kwargs: str(tmp_path / "cache"),
    )

    folder = keep_matplotlib_cache()

    assert folder.parent == tmp_path / "cache"
    assert folder.is_dir()
    assert os.environ["MPLCONFIGDIR"] == str(folder)
