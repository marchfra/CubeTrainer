"""Entry point of the built app: starts CubeTrainer like the ``cubetrainer`` command.

Before starting, it gives matplotlib a lasting cache folder. PyInstaller's
matplotlib hook points it at a new temporary folder on every launch (needed for
one-file builds, which unpack somewhere new each time), so matplotlib would scan
every installed font again (about 20 s) each time the app starts. This app is a
folder in a fixed place, so its cache can be kept: one folder per install
location, so a copy elsewhere never reuses font paths that don't exist there.

With ``CUBETRAINER_WARM_UP`` set, it only builds that cache and exits: the build
script does this once when installing, so even the first launch is quick.
"""

import hashlib
import os
import sys
from pathlib import Path

#: Environment variable asking for the cache to be built, without starting the app.
WARM_UP: str = "CUBETRAINER_WARM_UP"


def matplotlib_cache_dir(executable: str, cache_root: Path) -> Path:
    """Return the lasting matplotlib folder for an install location.

    Args:
        executable: The app's program (``sys.executable`` in the built app).
        cache_root: The app's cache folder.

    Returns:
        A folder named after the location, e.g. ``matplotlib-3f2a…``.

    """
    place = hashlib.sha256(executable.encode()).hexdigest()[:12]
    return cache_root / f"matplotlib-{place}"


def keep_matplotlib_cache() -> Path:
    """Point matplotlib at this install's lasting cache folder.

    Returns:
        The folder.

    """
    import platformdirs  # noqa: PLC0415 - before matplotlib, in the launcher only

    folder = matplotlib_cache_dir(
        sys.executable,
        Path(platformdirs.user_cache_dir("CubeTrainer", appauthor=False)),
    )
    folder.mkdir(parents=True, exist_ok=True)
    os.environ["MPLCONFIGDIR"] = str(folder)
    return folder


def run() -> None:
    """Start the app, or only build matplotlib's font cache if asked to."""
    keep_matplotlib_cache()
    if os.environ.get(WARM_UP):
        import matplotlib.font_manager  # noqa: F401, PLC0415 - builds the cache

        return
    from cubetrainer.app import main  # noqa: PLC0415 - after the cache is set

    main()


if __name__ == "__main__":
    run()
