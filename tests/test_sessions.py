"""Tests for sessions: the stores and the session menu."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from cubetrainer.db import TIMER_KIND, Database, DbSessionStore
from cubetrainer.sessions import (
    MemorySessionStore,
    SessionInfo,
    SessionStore,
    next_session_name,
)
from cubetrainer.solves import Solve
from cubetrainer.ui.main_window import MainWindow
from cubetrainer.ui.timer_page import TimerPage
from tests.helpers import FakeClock, do_solve


@pytest.fixture(params=["memory", "database"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[SessionStore]:
    """Provide each kind of session store.

    Args:
        request: Which store to build.
        tmp_path: Directory for the database.

    Yields:
        The store.

    """
    if request.param == "memory":
        yield MemorySessionStore()
        return
    db = Database(tmp_path / "app.db")
    yield DbSessionStore(db, TIMER_KIND)
    db.close()


def test_store_starts_with_one_session(store: SessionStore) -> None:
    """There is always a first session, and it's current."""
    sessions = store.sessions()

    assert [s.name for s in sessions] == ["Session 1"]
    assert store.current() == sessions[0].id


def test_create_select_rename_delete(store: SessionStore) -> None:
    """Sessions can be added, chosen, renamed and deleted."""
    first = store.current()
    second = store.create("OH")
    store.select(second)
    store.rename(second, "One-handed")

    assert [s.name for s in store.sessions()] == ["Session 1", "One-handed"]
    assert store.current() == second

    store.delete(second)
    assert [s.id for s in store.sessions()] == [first]
    assert store.current() == first


def test_sessions_keep_their_own_solves(store: SessionStore) -> None:
    """Each session has its own solves; deleting a session drops them."""
    first = store.current()
    second = store.create("Other")
    store.solves(first).add(Solve(1_000, "a"))
    store.solves(second).add(Solve(2_000, "b"))

    assert [s.time_ms for s in store.solves(first).solves] == [1_000]
    assert [s.time_ms for s in store.solves(second).solves] == [2_000]


def test_database_store_remembers_current_and_cascades(tmp_path: Path) -> None:
    """The current session survives a reopen; deleting removes the solves too."""
    db = Database(tmp_path / "app.db")
    store = DbSessionStore(db, TIMER_KIND)
    other = store.create("Other")
    store.select(other)
    store.solves(other).add(Solve(1_000, ""))
    db.close()

    db = Database(tmp_path / "app.db")
    reopened = DbSessionStore(db, TIMER_KIND)
    assert reopened.current() == other
    reopened.delete(other)
    count = db._conn.execute("SELECT COUNT(*) FROM solves").fetchone()[0]
    assert count == 0
    assert DbSessionStore(db, "trainer:pll").sessions()[0].name == "Session 1"
    db.close()


def test_next_session_name_skips_used_names() -> None:
    """New sessions get the first free "Session N" name."""
    existing = [SessionInfo(1, "Session 1"), SessionInfo(2, "Session 3")]

    assert next_session_name([]) == "Session 1"
    assert next_session_name(existing) == "Session 4"
    assert next_session_name([SessionInfo(1, "Mine")]) == "Session 2"


@pytest.fixture
def page(qtbot: QtBot, clock: FakeClock) -> TimerPage:
    """Provide a visible full-timer page with in-memory sessions.

    Args:
        qtbot: pytest-qt helper.
        clock: The fake clock.

    Returns:
        The page.

    """
    widget = TimerPage(generate=lambda: "s", clock=clock)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def menu_texts(page: TimerPage) -> list[str]:
    """Return the session menu's entries, after it fills itself.

    Args:
        page: The page.

    Returns:
        The action texts (separators are empty strings).

    """
    page.session_menu.aboutToShow.emit()
    return [action.text() for action in page.session_menu.actions()]


def test_menu_lists_sessions_and_actions(page: TimerPage) -> None:
    """The menu shows the sessions, then New / Rename / Delete (off for one session)."""
    assert page.session_button.text() == "Session 1  ▾"
    assert menu_texts(page) == [
        "Session 1",
        "",
        "New session…",
        "Rename session…",
        "Delete session…",
    ]
    delete = page.session_menu.actions()[-1]
    assert not delete.isEnabled()


def test_new_session_switches_to_an_empty_list(
    qtbot: QtBot,
    page: TimerPage,
    clock: FakeClock,
) -> None:
    """A new session starts empty; switching back shows the old solves."""
    do_solve(qtbot, page, clock, 1_000)
    asked: list[tuple[str, str]] = []

    def answer(label: str, text: str) -> str | None:
        asked.append((label, text))
        return "Practice"

    page.ask_text = answer
    page.new_session()

    assert asked == [("Name of the new session:", "Session 2")]
    assert page.session_button.text() == "Practice  ▾"
    assert page.solves_panel.model.rowCount() == 0
    do_solve(qtbot, page, clock, 2_000)

    first = page.sessions.sessions()[0].id
    page.switch_session(first)
    assert [s.time_ms for s in page.solves.solves] == [1_000]
    assert page.solves_panel.model.rowCount() == 1


def test_cancelled_new_session_does_nothing(page: TimerPage) -> None:
    """Cancelling the name dialog creates nothing."""
    page.ask_text = lambda _label, _text: None

    page.new_session()

    assert len(page.sessions.sessions()) == 1


def test_rename_session(page: TimerPage) -> None:
    """Renaming updates the button and the menu."""
    page.ask_text = lambda _label, _text: "Warm-up"

    page.rename_session()

    assert page.session_button.text() == "Warm-up  ▾"
    assert menu_texts(page)[0] == "Warm-up"


@pytest.mark.parametrize("answer", [True, False])
def test_delete_session_asks_first(page: TimerPage, *, answer: bool) -> None:
    """Deleting asks for confirmation and then moves to the remaining session."""
    page.ask_text = lambda _label, _text: "Doomed"
    page.new_session()
    questions: list[str] = []

    def confirm(question: str) -> bool:
        questions.append(question)
        return answer

    page.confirm = confirm
    page.delete_session()

    assert questions == ["Delete the session 'Doomed' and its 0 solves?"]
    names = [s.name for s in page.sessions.sessions()]
    assert names == (["Session 1"] if answer else ["Session 1", "Doomed"])
    assert page.session_button.text() == ("Session 1  ▾" if answer else "Doomed  ▾")


def test_switching_from_the_menu(qtbot: QtBot, page: TimerPage) -> None:
    """Choosing a session in the menu switches to it."""
    page.ask_text = lambda _label, _text: "Other"
    page.new_session()

    menu_texts(page)
    page.session_menu.actions()[0].trigger()

    assert page.session_button.text() == "Session 1  ▾"
    qtbot.mouseClick(page.session_button, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(page.session_menu.isVisible)
    page.session_menu.hide()


def test_trainer_sessions_are_per_set(qtbot: QtBot, clock: FakeClock) -> None:
    """Each trainer has its own sessions; the per-case table follows the session."""
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    window.show()
    window.open_trainer("pll")
    trainer = window.trainer_pages["pll"]
    trainer.timer._clock = clock
    do_solve(qtbot, trainer, clock, 1_500)
    assert trainer.case_stats.model.rowCount() == 1

    trainer.ask_text = lambda _label, _text: "Fresh"
    trainer.new_session()

    assert trainer.case_stats.model.rowCount() == 0
    assert [s.name for s in window.timer_page.sessions.sessions()] == ["Session 1"]
    window.open_trainer("oll")
    assert [s.name for s in window.trainer_pages["oll"].sessions.sessions()] == [
        "Session 1",
    ]
