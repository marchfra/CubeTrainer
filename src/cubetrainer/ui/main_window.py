"""Main application window with the Timer, Learn and Stats tabs."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QWidget

from cubetrainer.db import Database, StoredSolveList
from cubetrainer.ui.timer_page import TimerPage

#: Titles of the top-level tabs, in display order.
TAB_TITLES: tuple[str, ...] = ("Timer", "Learn", "Stats")


def _placeholder(text: str) -> QWidget:
    """Build a centred label used for tabs that are not implemented yet.

    Args:
        text: Message shown in the middle of the tab.

    Returns:
        The placeholder widget.

    """
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class MainWindow(QMainWindow):
    """Top-level window hosting one tab per app section.

    Attributes:
        tabs: The tab widget holding the Timer, Learn and Stats pages.
        timer_page: The full-solve timer page shown in the Timer tab.

    """

    def __init__(self, db: Database) -> None:
        """Create the window and its tabs (Learn and Stats are placeholders for now).

        Args:
            db: The app database.

        """
        super().__init__()
        self.setWindowTitle("CubeTrainer")
        self.resize(1100, 720)

        self.tabs: QTabWidget = QTabWidget()
        timer_solves = StoredSolveList(db, db.get_or_create_session())
        self.timer_page: TimerPage = TimerPage(solves=timer_solves)
        self.tabs.addTab(self.timer_page, TAB_TITLES[0])
        for title in TAB_TITLES[1:]:
            self.tabs.addTab(_placeholder(f"{title} — coming soon"), title)
        self.setCentralWidget(self.tabs)
