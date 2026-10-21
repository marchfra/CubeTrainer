# PyInstaller recipe for CubeTrainer (run through app_bundle/build_app.py).
#
# Bundles the app with its data (case lists, fonts), kociemba's pruning tables and
# Python itself, so it runs without Python or uv installed. On macOS the result is
# CubeTrainer.app; on Windows and Linux it's a CubeTrainer folder holding the
# program. The build script makes the icon first and passes its path in
# CUBETRAINER_ICON.

import os
import sys
from importlib.metadata import version
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH).parent  # noqa: F821 - defined by PyInstaller
VERSION = version("cubetrainer")
ICON = os.environ.get("CUBETRAINER_ICON")

analysis = Analysis(  # noqa: F821
    [str(ROOT / "app_bundle" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=collect_data_files("cubetrainer") + collect_data_files("kociemba"),
    # Not used, and only pulled in by optional imports of the libraries.
    excludes=["tkinter", "PyQt5", "PyQt6", "IPython", "pytest", "PIL.ImageTk"],
)
python = PYZ(analysis.pure)  # noqa: F821
program = EXE(  # noqa: F821
    python,
    analysis.scripts,
    exclude_binaries=True,
    name="CubeTrainer",
    console=False,
    # Windows shows the program's own icon (Explorer, taskbar, Start Menu).
    icon=ICON if sys.platform == "win32" else None,
)
files = COLLECT(  # noqa: F821
    program,
    analysis.binaries,
    analysis.datas,
    name="CubeTrainer",
)
if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        files,
        name="CubeTrainer.app",
        icon=ICON,
        bundle_identifier="local.cubetrainer",
        version=VERSION,
        info_plist={
            "CFBundleDisplayName": "CubeTrainer",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            # Follow the system's light/dark mode (the app can also force one).
            "NSRequiresAquaSystemAppearance": False,
            "LSMinimumSystemVersion": "12.0",
        },
    )
