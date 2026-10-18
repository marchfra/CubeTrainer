"""Main application window with the Timer, Learn and Stats tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from cubetrainer.cases.catalog import load_case_set
from cubetrainer.db import (
    TIMER_KIND,
    Database,
    DbSessionStore,
    StoredTrainerPrefs,
    trainer_session_kind,
)
from cubetrainer.ui.timer_page import TimerPage
from cubetrainer.ui.trainer_page import TrainerPage

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtGui import QShowEvent

    from cubetrainer.ui.learn_page import LearnPage
    from cubetrainer.ui.stats_page import StatsPage

#: Titles of the top-level tabs, in display order.
TAB_TITLES: tuple[str, ...] = ("Timer", "Learn", "Stats")


class LazyPage[PageT: QWidget](QWidget):
    """A tab's page that is only built when first shown, or first asked for.

    Pages the user doesn't see at startup cost nothing until they do: the window
    opens sooner.
    """

    def __init__(self, build: Callable[[], PageT]) -> None:
        """Create the empty holder.

        Args:
            build: Creates the page.

        """
        super().__init__()
        self._build: Callable[[], PageT] = build
        self._page: PageT | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

    @property
    def page(self) -> PageT:
        """The page, built now if it wasn't yet."""
        if self._page is None:
            self._page = self._build()
            layout = self.layout()
            if layout is not None:
                layout.addWidget(self._page)
        return self._page

    @property
    def built(self) -> bool:
        """Whether the page has been built."""
        return self._page is not None

    @override
    def showEvent(self, event: QShowEvent) -> None:
        """Build the page when its tab is first shown.

        Args:
            event: The show event.

        """
        self.page  # noqa: B018 - builds it
        super().showEvent(event)


class MainWindow(QMainWindow):
    """Top-level window hosting one tab per app section.

    Attributes:
        tabs: The tab widget holding the Timer, Learn and Stats pages.
        timer_stack: The Timer tab: the full timer or one of the trainers.
        timer_page: The full-solve timer page.
        trainer_pages: Trainer pages created so far, keyed by set id.
        learn_page: The case list shown in the Learn tab (built when first needed).
        stats_page: The statistics shown in the Stats tab (built when first
            needed).

    """

    def __init__(self, db: Database) -> None:
        """Create the window and its tabs.

        Args:
            db: The app database.

        """
        super().__init__()
        self._db: Database = db
        self.setWindowTitle("CubeTrainer")
        self.resize(1280, 760)

        self.tabs: QTabWidget = QTabWidget()
        self.timer_page: TimerPage = TimerPage(
            sessions=DbSessionStore(db, TIMER_KIND),
            settings=db,
        )
        self.trainer_pages: dict[str, TrainerPage] = {}
        self.timer_stack: QStackedWidget = QStackedWidget()
        self.timer_stack.addWidget(self.timer_page)
        self.tabs.addTab(self.timer_stack, TAB_TITLES[0])
        # Learn and Stats aren't visible at startup: built when first opened.
        self._learn: LazyPage[LearnPage] = LazyPage(self._make_learn_page)
        self.tabs.addTab(self._learn, TAB_TITLES[1])
        self._stats: LazyPage[StatsPage] = LazyPage(self._make_stats_page)
        self.tabs.addTab(self._stats, TAB_TITLES[2])
        self.setCentralWidget(self.tabs)

    @property
    def learn_page(self) -> LearnPage:
        """The Learn tab's page (built now if it wasn't yet)."""
        return self._learn.page

    @property
    def stats_page(self) -> StatsPage:
        """The Stats tab's page (built now if it wasn't yet)."""
        return self._stats.page

    def _make_learn_page(self) -> LearnPage:
        """Build the Learn tab's page.

        Returns:
            The page, wired to open trainers.

        """
        # Imported here, like the Stats page: the window opens without them.
        from cubetrainer.ui.learn_page import LearnPage  # noqa: PLC0415

        page = LearnPage(self._db)
        page.train_requested.connect(self.open_trainer)
        return page

    def _make_stats_page(self) -> StatsPage:
        """Build the Stats tab's page.

        Returns:
            The page.

        """
        # Imported here: its plots need matplotlib and scipy, slow to load.
        from cubetrainer.ui.stats_page import StatsPage  # noqa: PLC0415

        return StatsPage(self._db)

    def open_trainer(self, set_id: str) -> None:
        """Show the trainer of a case set in the Timer tab, creating it if needed.

        Args:
            set_id: The case set to train, e.g. ``"pll"``.

        """
        page = self.trainer_pages.get(set_id)
        if page is None:
            page = TrainerPage(
                load_case_set(set_id),
                sessions=DbSessionStore(self._db, trainer_session_kind(set_id)),
                prefs=StoredTrainerPrefs(self._db, set_id),
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
