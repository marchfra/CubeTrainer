"""Main application window with the Timer, Learn and Stats tabs."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QWidget

from cubetrainer.db import Database, StoredSolveList
from cubetrainer.ui.learn_page import LearnPage
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
        learn_page: The case list shown in the Learn tab.

    """

    def __init__(self, db: Database) -> None:
        """Create the window and its tabs (Stats is a placeholder for now).

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
        self.learn_page: LearnPage = LearnPage(db)
        self.tabs.addTab(self.learn_page, TAB_TITLES[1])
        self.tabs.addTab(_placeholder(f"{TAB_TITLES[2]} — coming soon"), TAB_TITLES[2])
        self.setCentralWidget(self.tabs)
