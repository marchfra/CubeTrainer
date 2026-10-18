"""Application entry point."""

import sys

from PySide6.QtWidgets import QApplication

from cubetrainer.db import Database, default_db_path
from cubetrainer.sound import quiet_audio_warnings
from cubetrainer.ui.main_window import MainWindow
from cubetrainer.ui.theme import follow_system_mode


def main() -> None:
    """Start the Qt application and show the main window.

    The process exits with the Qt event loop's return code.
    """
    quiet_audio_warnings()
    app = QApplication(sys.argv)
    app.setApplicationName("CubeTrainer")
    db = Database(default_db_path())
    follow_system_mode(app, db)  # the saved theme and light/dark choice
    app.aboutToQuit.connect(db.close)
    window = MainWindow(db)
    window.show()
    sys.exit(app.exec())
