"""Main application window with the Timer, Learn and Stats tabs."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QStackedWidget,
    QTabWidget,
    QWidget,
)

from cubetrainer.cases.catalog import load_case_set
from cubetrainer.db import Database, StoredSolveList, trainer_session_kind
from cubetrainer.ui.learn_page import LearnPage
from cubetrainer.ui.timer_page import TimerPage
from cubetrainer.ui.trainer_page import TrainerPage

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
        timer_stack: The Timer tab: the full timer or one of the trainers.
        timer_page: The full-solve timer page.
        trainer_pages: Trainer pages created so far, keyed by set id.
        learn_page: The case list shown in the Learn tab.

    """

    def __init__(self, db: Database) -> None:
        """Create the window and its tabs (Stats is a placeholder for now).

        Args:
            db: The app database.

        """
        super().__init__()
        self._db: Database = db
        self.setWindowTitle("CubeTrainer")
        self.resize(1280, 760)

        self.tabs: QTabWidget = QTabWidget()
        timer_solves = StoredSolveList(db, db.get_or_create_session())
        self.timer_page: TimerPage = TimerPage(solves=timer_solves)
        self.trainer_pages: dict[str, TrainerPage] = {}
        self.timer_stack: QStackedWidget = QStackedWidget()
        self.timer_stack.addWidget(self.timer_page)
        self.tabs.addTab(self.timer_stack, TAB_TITLES[0])
        self.learn_page: LearnPage = LearnPage(db)
        self.learn_page.train_requested.connect(self.open_trainer)
        self.tabs.addTab(self.learn_page, TAB_TITLES[1])
        self.tabs.addTab(_placeholder(f"{TAB_TITLES[2]} — coming soon"), TAB_TITLES[2])
        self.setCentralWidget(self.tabs)

    def open_trainer(self, set_id: str) -> None:
        """Show the trainer of a case set in the Timer tab, creating it if needed.

        Args:
            set_id: The case set to train, e.g. ``"pll"``.

        """
        page = self.trainer_pages.get(set_id)
        if page is None:
            session = self._db.get_or_create_session(trainer_session_kind(set_id))
            page = TrainerPage(
                load_case_set(set_id),
                solves=StoredSolveList(self._db, session),
            )
            page.back_requested.connect(self.open_timer)
            self.trainer_pages[set_id] = page
            self.timer_stack.addWidget(page)
        self.timer_stack.setCurrentWidget(page)
        self.tabs.setCurrentWidget(self.timer_stack)

    def open_timer(self) -> None:
        """Show the full-solve timer in the Timer tab."""
        self.timer_stack.setCurrentWidget(self.timer_page)
        self.tabs.setCurrentWidget(self.timer_stack)
