r"""Where a built CubeTrainer goes on each system, and how it's launched.

PyInstaller builds a ``CubeTrainer.app`` bundle on macOS and a ``CubeTrainer``
folder elsewhere. Installing puts it where the system expects programs, plus a
launcher entry where needed:

- macOS: ``/Applications/CubeTrainer.app`` (Spotlight, Launchpad and the Dock find
  app bundles by themselves);
- Windows: ``%LOCALAPPDATA%\Programs\CubeTrainer`` (the per-user programs folder),
  plus a Start Menu shortcut;
- Linux: ``~/.local/share/cubetrainer`` (or under ``$XDG_DATA_HOME``), plus a
  ``.desktop`` launcher and an icon.

The launcher folders on Windows and Linux are platformdirs'
``user_applications_dir()``. On macOS that function follows XDG variables when
they're set, so the macOS folder is fixed instead. Everything here is pure (paths
in, paths out), so all three systems can be tested anywhere.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

#: The app's name: the bundle, the executable and the launcher entries.
APP_NAME: str = "CubeTrainer"

#: Lower-case name for Linux files (data folder, launcher, icon).
LINUX_NAME: str = "cubetrainer"


@dataclass(frozen=True, slots=True)
class InstallLayout:
    """Where the app, its launcher and its icon go on one system.

    Attributes:
        system: ``"darwin"``, ``"win32"`` or ``"linux"`` (like ``sys.platform``).
        built: What PyInstaller builds, relative to its output folder.
        app: Where the built app is copied.
        executable: The program to run, inside the installed app.
        launcher: The Start Menu shortcut or ``.desktop`` file, if the system needs
            one.
        icon: Where the launcher's icon is copied, if it needs its own file.
        icon_format: The icon file format the build needs (``"icns"``, ``"ico"``
            or ``"png"``).

    """

    system: str
    built: PurePath
    app: PurePath
    executable: PurePath
    launcher: PurePath | None
    icon: PurePath | None
    icon_format: str

    def installed_paths(self) -> list[PurePath]:
        """Return everything an install creates (what an uninstall removes).

        Returns:
            The app, then the launcher and icon if there are any.

        """
        return [p for p in (self.app, self.launcher, self.icon) if p is not None]


def system_name(platform: str) -> str:
    """Reduce ``sys.platform`` to the three systems the build knows.

    Args:
        platform: A ``sys.platform`` value, e.g. ``"darwin"`` or ``"linux2"``.

    Returns:
        ``"darwin"``, ``"win32"`` or ``"linux"``.

    Raises:
        ValueError: For any other system.

    """
    for name in ("darwin", "win32", "linux"):
        if platform.startswith(name):
            return name
    msg = f"building the app isn't supported on {platform!r}"
    raise ValueError(msg)


def install_layout(
    platform: str,
    home: PurePath,
    env: Mapping[str, str],
    launchers: PurePath | None = None,
) -> InstallLayout:
    """Work out where things go on a system.

    Args:
        platform: The system, as ``sys.platform`` names it.
        home: The user's home folder.
        env: Environment variables (``LOCALAPPDATA``, ``XDG_DATA_HOME``).
        launchers: The launcher folder (platformdirs' ``user_applications_dir()``);
            needed on Windows and Linux.

    Returns:
        The layout.

    Raises:
        ValueError: If the system isn't supported, or ``launchers`` is missing
            where it's needed.

    """
    system = system_name(platform)
    if system == "darwin":
        app = PurePosixPath("/Applications") / f"{APP_NAME}.app"
        return InstallLayout(
            system=system,
            built=PurePosixPath(f"{APP_NAME}.app"),
            app=app,
            executable=app / "Contents" / "MacOS" / APP_NAME,
            launcher=None,
            icon=None,
            icon_format="icns",
        )
    if launchers is None:
        msg = "the launcher folder is needed on Windows and Linux"
        raise ValueError(msg)
    if system == "win32":
        local = PureWindowsPath(
            env.get("LOCALAPPDATA") or PureWindowsPath(home) / "AppData" / "Local",
        )
        app = local / "Programs" / APP_NAME
        return InstallLayout(
            system=system,
            built=PureWindowsPath(APP_NAME),
            app=app,
            executable=app / f"{APP_NAME}.exe",
            launcher=PureWindowsPath(launchers) / f"{APP_NAME}.lnk",
            icon=None,  # the shortcut uses the icon inside the .exe
            icon_format="ico",
        )
    data = PurePosixPath(
        env.get("XDG_DATA_HOME") or PurePosixPath(home) / ".local/share",
    )
    app = data / LINUX_NAME
    return InstallLayout(
        system=system,
        built=PurePosixPath(APP_NAME),
        app=app,
        executable=app / APP_NAME,
        launcher=PurePosixPath(launchers) / f"{LINUX_NAME}.desktop",
        icon=data / "icons" / "hicolor" / "256x256" / "apps" / f"{LINUX_NAME}.png",
        icon_format="png",
    )


def desktop_entry(executable: PurePath, icon: PurePath) -> str:
    """Write the Linux launcher (a freedesktop ``.desktop`` file).

    Args:
        executable: The program to run.
        icon: Its icon file.

    Returns:
        The file's text.

    """
    return "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={APP_NAME}",
            "Comment=Rubik's cube timer and OLL/PLL trainer",
            f'Exec="{executable}"',
            f"Icon={icon}",
            "Terminal=false",
            "Categories=Game;Utility;",
            f"StartupWMClass={APP_NAME}",
            "",
        ],
    )


def shortcut_script(shortcut: PurePath, target: PurePath) -> str:
    """Write the PowerShell commands that create a Windows Start Menu shortcut.

    Uses Windows' own shortcut maker (``WScript.Shell``), so nothing needs
    installing.

    Args:
        shortcut: The ``.lnk`` file to create.
        target: The program it starts.

    Returns:
        The PowerShell commands.

    """

    def quoted(path: PurePath) -> str:
        return "'" + str(path).replace("'", "''") + "'"

    make = "(New-Object -ComObject WScript.Shell).CreateShortcut"
    return (
        f"$s = {make}({quoted(shortcut)});"
        f" $s.TargetPath = {quoted(target)};"
        f" $s.WorkingDirectory = {quoted(target.parent)};"
        " $s.Save()"
    )


def home_layout(platform: str, home: Path, env: Mapping[str, str]) -> InstallLayout:
    """Work out this machine's layout (with platformdirs' launcher folder).

    Args:
        platform: ``sys.platform``.
        home: The user's home folder.
        env: The environment.

    Returns:
        The layout.

    """
    launchers = None
    if system_name(platform) != "darwin":
        import platformdirs  # noqa: PLC0415 - only where launchers are needed

        launchers = Path(platformdirs.user_applications_dir())
    return install_layout(platform, home, env, launchers)
