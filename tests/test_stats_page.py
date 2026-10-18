"""Tests for the Stats tab."""

from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtWidgets import QComboBox
from pytestqt.qtbot import QtBot

from cubetrainer.db import TIMER_KIND, Database, DbSessionStore, trainer_session_kind
from cubetrainer.solves import Penalty, Solve
from cubetrainer.ui.stats_page import StatsPage, all_sources

START = datetime(2026, 10, 1, tzinfo=UTC)


def add(
    db: Database,
    session: int,
    *times: int,
    case_id: str | None = None,
    mistake: bool = False,
    penalty: Penalty = Penalty.OK,
) -> None:
    """Add solves to a session, a minute apart (after every solve so far).

    Args:
        db: The database.
        session: The session.
        *times: Solve times in milliseconds.
        case_id: The case, for trainer solves.
        mistake: Whether the solves are marked as mistakes.
        penalty: Their penalty.

    """
    count = db._conn.execute("SELECT COUNT(*) FROM solves").fetchone()[0]
    for i, ms in enumerate(times):
        moment = START + timedelta(minutes=count + i)
        solve = Solve(ms, "", penalty, moment, case_id=case_id, mistake=mistake)
        db.add_solve(session, solve)


def make_page(qtbot: QtBot, db: Database) -> StatsPage:
    """Create and show the Stats page.

    Args:
        qtbot: pytest-qt helper.
        db: The database.

    Returns:
        The page.

    """
    page = StatsPage(db)
    qtbot.addWidget(page)
    page.show()
    qtbot.waitUntil(lambda: page.overview["solves"].text() != "")  # deferred refresh
    return page


def test_shows_the_timers_current_session(qtbot: QtBot) -> None:
    """By default the page summarises the full timer's current session."""
    db = Database(":memory:")
    store = DbSessionStore(db, TIMER_KIND)
    add(db, store.current(), 10_000, 12_000, 14_000)
    page = make_page(qtbot, db)

    assert page.source_picker.currentText() == "Full timer"
    assert page.session_picker.currentText() == "Session 1"
    assert not page.case_picker.isVisible()
    assert page.overview["solves"].text() == "3"
    assert page.overview["mean"].text() == "12.00"
    assert page.overview["best"].text() == "10.00"
    assert page.averages[5, "current"].text() == "-"


def test_all_sessions_combine_in_time_order(qtbot: QtBot) -> None:
    """The All option covers every session of the source."""
    db = Database(":memory:")
    store = DbSessionStore(db, TIMER_KIND)
    add(db, store.current(), 10_000, 11_000)
    other = store.create("Other")
    add(db, other, 30_000, 31_000, 32_000)
    page = make_page(qtbot, db)

    page.select_session(None)

    assert page.session_picker.currentText() == "All"
    assert page.overview["solves"].text() == "5"
    assert page.averages[5, "current"].text() == "24.00"  # 11, 30, 31 after trimming


def test_trainer_source_filters_cases_and_mistakes(qtbot: QtBot) -> None:
    """Trainer statistics leave out mistakes and can focus on one case."""
    db = Database(":memory:")
    session = DbSessionStore(db, trainer_session_kind("pll")).current()
    add(db, session, 2_000, 3_000, case_id="T")
    add(db, session, 1_000, case_id="T", mistake=True)
    add(db, session, 5_000, case_id="Ua")
    page = make_page(qtbot, db)
    pll = next(s for s in all_sources() if s.set_id == "pll")

    page.select_source(pll)
    assert page.case_picker.isVisible()
    assert page.case_picker.currentText() == "All"
    assert page.overview["solves"].text() == "3"  # the mistake is left out
    assert page.overview["best"].text() == "2.00"

    page.select_case("T")
    assert page.case_picker.currentText() == "T"
    assert page.overview["mean"].text() == "2.50"


def test_sub_x_follows_the_limit(qtbot: QtBot) -> None:
    """Changing the limit updates the sub-X rate."""
    db = Database(":memory:")
    add(db, DbSessionStore(db, TIMER_KIND).current(), 9_000, 15_000, 25_000, 35_000)
    page = make_page(qtbot, db)

    assert page.sub_x_label.text() == "50%  (2 of 4)"
    page.sub_x.setValue(10)
    assert page.sub_x_label.text() == "25%  (1 of 4)"


def test_empty_source_shows_dashes(qtbot: QtBot) -> None:
    """With no solves everything shows a dash."""
    page = make_page(qtbot, Database(":memory:"))

    assert page.overview["solves"].text() == "0"
    assert page.overview["mean"].text() == "-"
    assert page.overview["variation (CV)"].text() == "-"
    assert page.sub_x_label.text() == "-"
    assert page.fit_labels["τ"].text() == "-"


def test_menus_list_sources_sessions_and_cases(qtbot: QtBot) -> None:
    """The pickers offer every source, the source's sessions and its cases."""
    db = Database(":memory:")
    page = make_page(qtbot, db)

    def items(picker: QComboBox) -> list[str]:
        return [picker.itemText(i) for i in range(picker.count())]

    assert items(page.source_picker) == [s.label for s in all_sources()]
    assert items(page.session_picker) == ["All", "Session 1"]

    page.select_source(next(s for s in all_sources() if s.set_id == "pll2"))
    assert items(page.case_picker)[:3] == ["All", "Headlights", "Diagonal"]


def test_choosing_in_the_pickers_selects(qtbot: QtBot) -> None:
    """Choosing a source, session or case in a picker shows it."""
    db = Database(":memory:")
    session = DbSessionStore(db, trainer_session_kind("pll")).current()
    add(db, session, 2_000, 3_000, case_id="T")
    add(db, session, 5_000, case_id="Ua")
    page = make_page(qtbot, db)
    index = next(i for i, s in enumerate(all_sources()) if s.set_id == "pll")

    page.source_picker.activated.emit(index)
    assert page.source.set_id == "pll"
    assert page.overview["solves"].text() == "3"

    page.case_picker.activated.emit(page.case_picker.findData("T"))
    assert page.case_id == "T"
    assert page.overview["solves"].text() == "2"

    page.session_picker.activated.emit(page.session_picker.findData(""))
    assert page.session_id is None
    assert page.case_picker.currentText() == "T"  # the case stays chosen


def test_refreshes_when_shown(qtbot: QtBot) -> None:
    """Solves added elsewhere show up the next time the tab is shown."""
    db = Database(":memory:")
    page = make_page(qtbot, db)
    add(db, DbSessionStore(db, TIMER_KIND).current(), 10_000, 20_000)

    page.hide()
    page.show()

    qtbot.waitUntil(lambda: page.overview["solves"].text() == "2")
    assert page.overview["median"].text() == "15.00"


def test_plus_two_counts_in_times(qtbot: QtBot) -> None:
    """Penalties apply: a +2 solve counts two seconds slower."""
    db = Database(":memory:")
    add(db, DbSessionStore(db, TIMER_KIND).current(), 10_000, penalty=Penalty.PLUS_TWO)

    page = make_page(qtbot, db)

    assert page.overview["best"].text() == "12.00"


def test_distribution_plots_follow_the_selection(qtbot: QtBot) -> None:
    """The plots show the selected solves (trainer mistakes left out)."""
    db = Database(":memory:")
    session = DbSessionStore(db, trainer_session_kind("pll")).current()
    add(db, session, *range(2_000, 4_400, 200), case_id="T")
    add(db, session, 30_000, case_id="T", mistake=True)
    page = make_page(qtbot, db)
    assert page.histogram.seconds == []

    page.select_source(next(s for s in all_sources() if s.set_id == "pll"))

    assert len(page.histogram.seconds) == 12
    assert max(page.histogram.seconds) < 30
    assert page.histogram.fit is not None
    assert page.fit_labels["μ"].text() == f"{page.histogram.fit.mu:.2f}"
    assert page.fit_labels["D"].text() != "-"


def test_record_plots_follow_the_selection(qtbot: QtBot) -> None:
    """The records plot gets the same solves as the summary."""
    db = Database(":memory:")
    add(db, DbSessionStore(db, TIMER_KIND).current(), *range(10_000, 22_000, 1_000))
    page = make_page(qtbot, db)

    assert page.records_plot.records["single"][0][1] == 10_000


def test_case_charts_only_for_trainers_on_all_cases(qtbot: QtBot) -> None:
    """The case charts show for a trainer covering every case, with mistakes."""
    db = Database(":memory:")
    session = DbSessionStore(db, trainer_session_kind("pll")).current()
    add(db, session, 2_000, 3_000, case_id="T")
    add(db, session, 9_000, case_id="T", mistake=True)
    page = make_page(qtbot, db)
    assert not page.case_charts.isVisible()

    page.select_source(next(s for s in all_sources() if s.set_id == "pll"))
    assert page.case_charts.isVisible()
    assert page.case_charts.rows[0].stats.mistake_rate == 1 / 3

    page.select_case("T")
    assert not page.case_charts.isVisible()


def test_learning_curve_gets_the_selected_times(qtbot: QtBot) -> None:
    """The learning curve shows the same solves as the summary."""
    db = Database(":memory:")
    add(db, DbSessionStore(db, TIMER_KIND).current(), *range(30_000, 10_000, -500))
    page = make_page(qtbot, db)

    assert len(page.learning_curve.seconds) == 40
    assert page.learning_curve.curve is not None


def test_unchanged_data_is_not_redrawn(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reopening the tab with the same solves skips recomputing and redrawing."""
    db = Database(":memory:")
    add(db, DbSessionStore(db, TIMER_KIND).current(), *range(10_000, 22_000, 1_000))
    page = make_page(qtbot, db)
    calls: list[int] = []
    monkeypatch.setattr(page.histogram, "set_values", lambda v: calls.append(len(v)))

    page.refresh()
    assert calls == []

    add(db, DbSessionStore(db, TIMER_KIND).current(), 9_000)
    page.refresh()
    assert calls == [13]


def test_sub_x_changes_do_not_redraw_plots(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Changing the sub-X limit only updates the sub-X box."""
    db = Database(":memory:")
    add(db, DbSessionStore(db, TIMER_KIND).current(), 9_000, 15_000)
    page = make_page(qtbot, db)
    calls: list[int] = []
    monkeypatch.setattr(page.histogram, "set_values", lambda v: calls.append(len(v)))

    page.sub_x.setValue(10)

    assert calls == []
    assert page.sub_x_label.text() == "50%  (1 of 2)"
