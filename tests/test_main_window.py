"""Tests for the main window shell."""

from pathlib import Path

from pytestqt.qtbot import QtBot

from cubetrainer.db import Database
from cubetrainer.ui.main_window import TAB_TITLES, MainWindow
from tests.helpers import FakeClock, do_solve


def make_window(qtbot: QtBot, db: Database) -> MainWindow:
    """Create and show a main window backed by ``db``.

    Args:
        qtbot: pytest-qt helper.
        db: The database.

    Returns:
        The window.

    """
    window = MainWindow(db)
    qtbot.addWidget(window)
    window.show()
    return window


def test_window_has_expected_tabs(qtbot: QtBot) -> None:
    """The window exposes the Timer, Learn and Stats tabs in order."""
    window = make_window(qtbot, Database(":memory:"))

    titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]

    assert titles == list(TAB_TITLES)


def test_tabs_can_be_switched(qtbot: QtBot) -> None:
    """Selecting a tab makes it the current one."""
    window = make_window(qtbot, Database(":memory:"))

    window.tabs.setCurrentIndex(2)

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Stats"


def test_solves_survive_restart(qtbot: QtBot, tmp_path: Path, clock: FakeClock) -> None:
    """Solves done in one window are shown by a new window on the same database."""
    path = tmp_path / "app.db"
    db = Database(path)
    window = make_window(qtbot, db)
    window.timer_page.timer._clock = clock
    do_solve(qtbot, window.timer_page, clock, 9_876)
    window.close()
    db.close()

    reopened = make_window(qtbot, Database(path))

    solves = reopened.timer_page.solves.solves
    assert [s.time_ms for s in solves] == [9_876]
    assert reopened.timer_page.solves_panel.model.rowCount() == 1
