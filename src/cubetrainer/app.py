"""Application entry point."""

import sys

from PySide6.QtWidgets import QApplication

from cubetrainer.ui.main_window import MainWindow


def main() -> None:
    """Start the Qt application and show the main window.

    The process exits with the Qt event loop's return code.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("CubeTrainer")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
