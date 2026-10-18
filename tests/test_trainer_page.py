"""Tests for trainer mode: the trainer page and how the app switches to it."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetricsF, QPixmap
from PySide6.QtWidgets import QDialog, QLabel, QWidget
from pytestqt.qtbot import QtBot

from cubetrainer.cases.catalog import CaseCustomization, CaseStatus, load_case_set
from cubetrainer.cases.filters import CaseFilter, MemoryTrainerPrefs, Odds
from cubetrainer.cube.model import alg_pieces, parse_alg
from cubetrainer.db import Database
from cubetrainer.sessions import MemorySessionStore
from cubetrainer.solves import Solve
from cubetrainer.timing import TimerState
from cubetrainer.ui.case_images import case_pixmap
from cubetrainer.ui.filter_dialog import FilterDialog
from cubetrainer.ui.main_window import MainWindow
from cubetrainer.ui.solve_dialog import SolveDialog
from cubetrainer.ui.trainer_page import (
    DIALOG_IMAGE_SIZE,
    HINT_PROMPT,
    TrainerPage,
    breakable_spaces,
    wrap_pieces,
)
from tests.helpers import FakeClock, do_solve

PLL = load_case_set("pll")
T_CASE = next(c for c in PLL.cases if c.id == "T")


@pytest.fixture
def page(qtbot: QtBot, clock: FakeClock) -> TrainerPage:
    """Provide a visible PLL trainer whose scrambles are always a T perm.

    T is the only case marked as learning, and the filter keeps learning cases only.

    Args:
        qtbot: pytest-qt helper.
        clock: The fake clock.

    Returns:
        The page.

    """
    prefs = MemoryTrainerPrefs(
        case_statuses={"T": CaseStatus.LEARNING},
        case_filter=CaseFilter(statuses=frozenset({CaseStatus.LEARNING})),
    )
    widget = TrainerPage(PLL, prefs=prefs, clock=clock)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_solve_records_its_case(
    qtbot: QtBot,
    page: TrainerPage,
    clock: FakeClock,
) -> None:
    """A trainer solve stores the case of its scramble, shown in the case column."""
    do_solve(qtbot, page, clock, 1_500)

    solve = page.solves.solves[0]
    assert solve.case_id == "T"
    model = page.solves_panel.model
    assert model.columnCount() == 4
    assert model.data(model.index(0, 2)) == "T"


def test_solve_dialog_names_the_case(
    qtbot: QtBot,
    page: TrainerPage,
    clock: FakeClock,
) -> None:
    """The details dialog of a trainer solve names and shows the case."""
    do_solve(qtbot, page, clock, 1_500)
    labels: list[QLabel] = []

    def run_dialog(dialog: QDialog) -> int:
        assert isinstance(dialog, SolveDialog)
        labels.extend(dialog.findChildren(QLabel))
        return 0

    page.run_dialog = run_dialog
    page.show_solve(0)

    assert "Case: T" in [label.text() for label in labels]
    images = [label.pixmap() for label in labels if not label.pixmap().isNull()]
    assert len(images) == 1
    assert images[0].deviceIndependentSize().width() == DIALOG_IMAGE_SIZE


def test_full_solve_dialog_has_no_case(
    qtbot: QtBot,
    clock: FakeClock,
) -> None:
    """Full-timer solves show neither a case name nor an image."""
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    window.show()
    window.timer_page.timer._clock = clock
    do_solve(qtbot, window.timer_page, clock, 9_000)
    labels: list[QLabel] = []

    def run_dialog(dialog: QDialog) -> int:
        labels.extend(dialog.findChildren(QLabel))
        return 0

    window.timer_page.run_dialog = run_dialog
    window.timer_page.show_solve(0)

    assert not any(label.text().startswith("Case:") for label in labels)
    assert all(label.pixmap().isNull() for label in labels)


def test_header_and_back_button(qtbot: QtBot, page: TrainerPage) -> None:
    """The header names the set; the back button asks to leave the trainer."""
    assert page.title.text() == "PLL trainer"

    with qtbot.waitSignal(page.back_requested):
        qtbot.mouseClick(page.back_button, Qt.MouseButton.LeftButton)


def test_train_button_opens_trainer_and_back_returns(qtbot: QtBot) -> None:
    """Learn → Train switches the Timer tab to the trainer; back shows the timer."""
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    window.show()
    window.tabs.setCurrentWidget(window.learn_page)
    window.learn_page.select_set("pll")

    assert window.learn_page.train_button.text() == "Train PLL"
    qtbot.mouseClick(window.learn_page.train_button, Qt.MouseButton.LeftButton)

    trainer = window.trainer_pages["pll"]
    assert window.tabs.currentWidget() is window.timer_stack
    assert window.timer_stack.currentWidget() is trainer
    assert window.tabs.tabText(window.tabs.currentIndex()) == "Timer"

    qtbot.mouseClick(trainer.back_button, Qt.MouseButton.LeftButton)
    assert window.timer_stack.currentWidget() is window.timer_page

    window.open_trainer("pll")
    assert window.trainer_pages["pll"] is trainer  # reused, not recreated


def test_trainer_solves_are_kept_apart(qtbot: QtBot, clock: FakeClock) -> None:
    """Trainer solves go to their own session, not the full timer's list."""
    db = Database(":memory:")
    window = MainWindow(db)
    qtbot.addWidget(window)
    window.show()
    window.open_trainer("pll")
    trainer = window.trainer_pages["pll"]
    trainer.timer._clock = clock

    do_solve(qtbot, trainer, clock, 2_000)

    assert len(trainer.solves) == 1
    assert len(window.timer_page.solves) == 0
    stored = db.load_solves(db.get_or_create_session("trainer:pll"))
    assert [(s.time_ms, s.case_id is not None) for s in stored] == [(2_000, True)]


def activate(qtbot: QtBot, page: TrainerPage) -> None:
    """Make the page's window active, so its shortcuts fire.

    Args:
        qtbot: pytest-qt helper.
        page: The page.

    """
    page.activateWindow()
    qtbot.waitUntil(page.isActiveWindow)


def test_hints_reveal_one_move_at_a_time(qtbot: QtBot, page: TrainerPage) -> None:
    """→ shows the case image and the algorithm's first move, then one more per press.

    The moves are the algorithm as written (no U turn added in front), with its
    brackets: T is "(R U R' U') (R' F R2 U') (R' U' R U) (R' F')".
    """
    activate(qtbot, page)
    total = len(parse_alg(T_CASE.alg))
    assert page.hint_panel.moves.text() == HINT_PROMPT
    assert page.hint_panel.image.pixmap().isNull()
    height = page.hint_panel.height()
    card = page.hint_panel.card.size()

    qtbot.keyClick(page, Qt.Key.Key_Right)
    assert page.hints_shown == 1
    assert not page.hint_panel.image.pixmap().isNull()
    assert page.hint_panel.height() == height
    assert page.hint_panel.shown_text == "(R"
    assert page.hint_panel.hidden_moves == total - 1
    assert page.hint_panel.card.size() == card  # the card never changes size

    for _ in range(3):
        qtbot.keyClick(page, Qt.Key.Key_Right)
    # Four moves: the first group is complete, closing bracket included.
    assert page.hint_panel.shown_text == "(R U R' U')"
    assert page.hint_panel.hidden_moves == total - 4

    qtbot.keyClick(page, Qt.Key.Key_Right)
    assert page.hint_panel.shown_text == "(R U R' U') (R'"

    for _ in range(total + 3):
        qtbot.keyClick(page, Qt.Key.Key_Right)
    assert page.hints_shown == total
    assert page.hint_panel.shown_text == T_CASE.alg
    assert page.hint_panel.hidden_moves == 0
    assert page.hint_panel.card.size() == card


def test_hint_does_not_stop_running_solve(
    qtbot: QtBot,
    page: TrainerPage,
    clock: FakeClock,
) -> None:
    """→ during a solve shows a hint and leaves the timer running."""
    activate(qtbot, page)
    qtbot.keyPress(page, Qt.Key.Key_Space)
    clock.advance_ms(300)
    qtbot.keyRelease(page, Qt.Key.Key_Space)

    qtbot.keyClick(page, Qt.Key.Key_Right)

    assert page.timer.machine.state is TimerState.RUNNING
    assert page.hints_shown == 1


def test_solve_records_hints_and_new_scramble_resets_them(
    qtbot: QtBot,
    page: TrainerPage,
    clock: FakeClock,
) -> None:
    """The hint count is saved with the solve; the next scramble starts fresh."""
    activate(qtbot, page)
    for _ in range(3):
        qtbot.keyClick(page, Qt.Key.Key_Right)

    do_solve(qtbot, page, clock, 2_500)

    assert page.solves.solves[-1].hints == 3
    assert page.hints_shown == 0
    assert page.hint_panel.moves.text() == HINT_PROMPT

    do_solve(qtbot, page, clock, 2_000)
    assert page.solves.solves[-1].hints == 0


def test_browsing_scrambles_resets_hints(qtbot: QtBot, page: TrainerPage) -> None:
    """Moving to another scramble with ▶ forgets the hints."""
    activate(qtbot, page)
    qtbot.keyClick(page, Qt.Key.Key_Right)

    page.scramble_bar.show_next()

    assert page.hints_shown == 0
    assert page.hint_panel.image.pixmap().isNull()


def test_right_arrow_still_stops_the_full_timer(qtbot: QtBot, clock: FakeClock) -> None:
    """Hints are a trainer feature: in the full timer → is just 'any key'."""
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    window.show()
    timer_page = window.timer_page
    timer_page.timer._clock = clock
    timer_page.inspection_action.setChecked(False)
    qtbot.keyPress(timer_page, Qt.Key.Key_Space)
    clock.advance_ms(300)
    qtbot.keyRelease(timer_page, Qt.Key.Key_Space)

    qtbot.keyClick(timer_page, Qt.Key.Key_Right)

    assert timer_page.timer.machine.state is not TimerState.RUNNING
    assert len(timer_page.solves) == 1


def test_m_flags_the_last_solve(
    qtbot: QtBot,
    page: TrainerPage,
    clock: FakeClock,
) -> None:
    """After a solve, M toggles its mistake flag; the button and stats follow."""
    activate(qtbot, page)
    do_solve(qtbot, page, clock, 1_500)
    assert not page.mistake_button.isChecked()

    qtbot.keyClick(page, Qt.Key.Key_M)
    assert page.solves.solves[-1].mistake
    assert page.mistake_button.isChecked()
    model = page.solves_panel.model
    assert model.data(model.index(0, 3)) == "✗"
    case_row = page.case_stats.proxy
    assert case_row.data(case_row.index(0, 4)) == "100%"

    qtbot.keyClick(page, Qt.Key.Key_M)
    assert not page.solves.solves[-1].mistake
    assert not page.mistake_button.isChecked()


def test_m_during_a_solve_flags_it_without_stopping(
    qtbot: QtBot,
    page: TrainerPage,
    clock: FakeClock,
) -> None:
    """M mid-solve keeps the timer running and flags the solve when it ends."""
    activate(qtbot, page)
    do_solve(qtbot, page, clock, 1_000)  # an earlier, clean solve
    qtbot.keyPress(page, Qt.Key.Key_Space)
    clock.advance_ms(300)
    qtbot.keyRelease(page, Qt.Key.Key_Space)

    qtbot.keyClick(page, Qt.Key.Key_M)

    assert page.timer.machine.state is TimerState.RUNNING
    assert page.mistake_button.isChecked()
    assert not page.solves.solves[-1].mistake  # the earlier solve is untouched

    clock.advance_ms(2_000)
    qtbot.keyPress(page, Qt.Key.Key_Space)
    qtbot.keyRelease(page, Qt.Key.Key_Space)
    assert [s.mistake for s in page.solves.solves] == [False, True]

    do_solve(qtbot, page, clock, 1_000)  # the flag doesn't carry over
    assert page.solves.solves[-1].mistake is False


def test_mistake_button_matches_m(
    qtbot: QtBot,
    page: TrainerPage,
    clock: FakeClock,
) -> None:
    """Clicking the button does what M does."""
    do_solve(qtbot, page, clock, 1_500)

    qtbot.mouseClick(page.mistake_button, Qt.MouseButton.LeftButton)

    assert page.solves.solves[-1].mistake
    assert page.mistake_button.isChecked()


def test_mistake_without_solves_does_nothing(page: TrainerPage) -> None:
    """With no solves yet, marking a mistake is harmless."""
    page.toggle_mistake()

    assert not page.mistake_button.isChecked()


def test_dialog_mistake_box_is_saved(qtbot: QtBot, clock: FakeClock) -> None:
    """The solve dialog's mistake box changes and stores the flag."""
    db = Database(":memory:")
    window = MainWindow(db)
    qtbot.addWidget(window)
    window.show()
    window.open_trainer("pll")
    trainer = window.trainer_pages["pll"]
    trainer.timer._clock = clock
    do_solve(qtbot, trainer, clock, 1_500)

    def run_dialog(dialog: QDialog) -> int:
        assert isinstance(dialog, SolveDialog)
        assert dialog.mistake_box is not None
        dialog.mistake_box.setChecked(True)
        return 0

    trainer.run_dialog = run_dialog
    trainer.show_solve(0)

    stored = db.load_solves(db.get_or_create_session("trainer:pll"))
    assert [s.mistake for s in stored] == [True]
    assert trainer.mistake_button.isChecked()


def test_full_solves_have_no_mistake_box(qtbot: QtBot) -> None:
    """The full timer's dialog has no mistake box."""
    dialog = SolveDialog(Solve(1_000, ""), 1)
    qtbot.addWidget(dialog)

    assert dialog.mistake_box is None


def test_learn_page_shows_trainer_times(qtbot: QtBot, clock: FakeClock) -> None:
    """The Learn cards show each case's best and mean, updated when shown again."""
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    window.show()
    window.open_trainer("pll")
    trainer = window.trainer_pages["pll"]
    trainer.timer._clock = clock
    case = trainer._recognizer.recognize(trainer.scramble_bar.scramble)
    assert case is not None
    do_solve(qtbot, trainer, clock, 1_500)
    do_solve(qtbot, trainer, clock, 9_000)
    trainer.toggle_mistake()  # the 9.00 is a mistake: left out

    window.learn_page.select_set("pll")
    window.tabs.setCurrentWidget(window.learn_page)

    cards = window.learn_page.case_list
    assert cards.best_labels[case.id].text() == "1.50"
    assert cards.mean_labels[case.id].text() == "1.50"


def test_filter_button_describes_the_filter(page: TrainerPage) -> None:
    """The fixture's filter keeps only T, picked with equal probability."""
    assert page.filter_button.text() == "1 case · equal"


def test_accepting_the_filter_saves_it_and_rescrambles(page: TrainerPage) -> None:
    """Accepting the dialog stores the filter and shows a matching scramble."""
    first = page.scramble_bar.history.index

    def run_dialog(dialog: QDialog) -> int:
        assert isinstance(dialog, FilterDialog)
        dialog.status_boxes[CaseStatus.UNLEARNED].setChecked(True)
        dialog.odds_buttons[Odds.REALISTIC].setChecked(True)
        return QDialog.DialogCode.Accepted

    page.run_dialog = run_dialog
    page.edit_filter()

    assert page.prefs.load_filter().odds is Odds.REALISTIC
    assert CaseStatus.UNLEARNED in page.prefs.load_filter().statuses
    assert page.filter_button.text() == "21 cases · realistic"
    assert page.scramble_bar.history.index == first + 1


def test_cancelling_the_filter_changes_nothing(page: TrainerPage) -> None:
    """A cancelled dialog leaves the filter and the scramble alone."""
    before = page.prefs.load_filter()
    scramble = page.scramble_bar.scramble

    def run_dialog(dialog: QDialog) -> int:
        assert isinstance(dialog, FilterDialog)
        dialog.odds_buttons[Odds.REALISTIC].setChecked(True)
        return QDialog.DialogCode.Rejected

    page.run_dialog = run_dialog
    page.edit_filter()

    assert page.prefs.load_filter() == before
    assert page.scramble_bar.scramble == scramble


def test_filter_button_warns_when_nothing_matches(qtbot: QtBot) -> None:
    """If statuses change so nothing matches, the button says all cases are used."""
    prefs = MemoryTrainerPrefs(
        case_statuses={"T": CaseStatus.LEARNING},
        case_filter=CaseFilter(statuses=frozenset({CaseStatus.LEARNING})),
    )
    page = TrainerPage(PLL, prefs=prefs)
    qtbot.addWidget(page)
    page.show()

    prefs.case_statuses["T"] = CaseStatus.FINISHED  # as if changed in Learn
    page.hide()
    page.show()  # showing the page again refreshes the button

    assert page.filter_button.text() == "⚠ all 21 · equal"
    assert page.filter_button.toolTip().startswith("No case matches the filter")


def test_oll_trainer_recognises_and_hints(qtbot: QtBot, clock: FakeClock) -> None:
    """The OLL trainer records the case of its scrambles and shows its hints."""
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    window.show()
    window.learn_page.select_set("oll")
    assert window.learn_page.train_button.text() == "Train OLL"

    qtbot.mouseClick(window.learn_page.train_button, Qt.MouseButton.LeftButton)

    trainer = window.trainer_pages["oll"]
    assert trainer.title.text() == "OLL trainer"
    assert trainer.filter_button.text() == "57 cases · equal"
    trainer.timer._clock = clock
    trainer.show_next_hint()
    assert trainer.hints_shown == 1
    do_solve(qtbot, trainer, clock, 2_000)
    assert trainer.solves.solves[-1].case_id is not None


@pytest.mark.parametrize(("set_id", "count"), [("oll2", 10), ("pll2", 6)])
def test_two_look_trainers(
    qtbot: QtBot,
    clock: FakeClock,
    set_id: str,
    count: int,
) -> None:
    """2-look trainers open, filter by look and record their cases."""
    window = MainWindow(Database(":memory:"))
    qtbot.addWidget(window)
    window.show()
    window.open_trainer(set_id)
    trainer = window.trainer_pages[set_id]
    trainer.timer._clock = clock

    assert trainer.filter_button.text() == f"{count} cases · equal"
    do_solve(qtbot, trainer, clock, 1_000)
    assert trainer.solves.solves[-1].case_id is not None


def test_trainer_uses_the_users_alg(qtbot: QtBot, clock: FakeClock) -> None:
    """Hints show the user's algorithm, and its scrambles are still recognised."""
    own_alg = "y (R U R' U') (R' F R2 U') (R' U' R U) (R' F') y'"
    prefs = MemoryTrainerPrefs(
        case_statuses={"T": CaseStatus.LEARNING},
        case_filter=CaseFilter(statuses=frozenset({CaseStatus.LEARNING})),
        case_customizations={"T": CaseCustomization(alg=own_alg)},
    )
    page = TrainerPage(PLL, prefs=prefs, clock=clock)
    qtbot.addWidget(page)
    page.show()

    for _ in range(100):
        page.show_next_hint()
    assert page.hint_panel.shown_text == own_alg

    do_solve(qtbot, page, clock, 1_000)
    assert page.solves.solves[-1].case_id == "T"
    info = page.case_info("T")
    assert info is not None
    assert (
        info.image.toImage()
        == case_pixmap(
            CaseCustomization(alg=own_alg).apply_to(T_CASE),
            DIALOG_IMAGE_SIZE,
        ).toImage()
    )


def test_trainer_inspection_is_off_by_default_and_separate(qtbot: QtBot) -> None:
    """The trainer's inspection is off until turned on, independently of the timer."""
    db = Database(":memory:")
    window = MainWindow(db)
    qtbot.addWidget(window)
    window.open_trainer("pll")
    trainer = window.trainer_pages["pll"]

    assert window.timer_page.inspection_action.isChecked()
    assert not trainer.inspection_action.isChecked()
    assert not trainer.timer.machine.inspection

    trainer.inspection_action.setChecked(True)
    window.timer_page.inspection_action.setChecked(False)

    assert db.get_setting("trainer.inspection") == "1"
    assert db.get_setting("timer.inspection") == "0"
    header = trainer.header_right
    items = [header.itemAt(i) for i in range(header.count())]
    widgets = [item.widget() for item in items if item is not None]
    assert widgets.index(trainer.mistake_button) < widgets.index(trainer.back_button)
    assert trainer.options_button.parent() is trainer.timer  # the cog in its corner


def test_set_history_spans_every_session(qtbot: QtBot, clock: FakeClock) -> None:
    """Slowest first rates cases on the solves of all the set's sessions."""
    sessions = MemorySessionStore()
    page = TrainerPage(PLL, sessions=sessions, clock=clock)
    qtbot.addWidget(page)
    page.show()
    do_solve(qtbot, page, clock, 1_500)
    page.switch_session(sessions.create("Second"))
    do_solve(qtbot, page, clock, 2_500)

    assert [s.time_ms for s in page.set_history()] == [1_500, 2_500]


def test_filter_button_names_slowest_first(qtbot: QtBot) -> None:
    """The filter button shows the odds of the saved filter."""
    prefs = MemoryTrainerPrefs(case_filter=CaseFilter(odds=Odds.SLOWEST))
    page = TrainerPage(PLL, prefs=prefs)
    qtbot.addWidget(page)

    assert page.filter_button.text() == "21 cases · slowest"


def test_filter_button_keeps_its_width(page: TrainerPage) -> None:
    """Changing the filter never resizes the button (nor shifts the header)."""
    width = page.filter_button.width()
    assert page.filter_button.minimumWidth() == page.filter_button.maximumWidth()

    for odds in Odds:
        page.prefs.save_filter(CaseFilter(odds=odds))
        page.update_filter_button()
        assert page.filter_button.width() == width
        assert page.filter_button.sizeHint().width() <= width


def test_hint_prompt_is_centred_over_the_timer(page: TrainerPage) -> None:
    """Before the first hint only the prompt shows: no empty image beside it."""
    assert page.hint_panel.image.isHidden()
    assert page.hint_panel.moves.alignment() & Qt.AlignmentFlag.AlignHCenter


def test_timer_is_centred_between_the_tables(qtbot: QtBot) -> None:
    """Timer and scramble sit in the middle; the per-case table uses its height."""
    page = TrainerPage(PLL)
    qtbot.addWidget(page)
    page.resize(1280, 700)
    page.show()
    qtbot.waitExposed(page)

    def top_and_bottom(widget: QWidget) -> tuple[int, int]:
        top = widget.mapTo(page, widget.rect().topLeft()).y()
        return top, top + widget.height()

    for widget in (page.timer, page.scramble_bar):
        centre = widget.mapTo(page, widget.rect().center()).x()
        assert abs(centre - page.width() / 2) <= 2
    solves_top, solves_bottom = top_and_bottom(page.solves_panel.table)
    cases_top, cases_bottom = top_and_bottom(page.case_stats.table)
    assert cases_bottom == solves_bottom
    assert cases_top < solves_top  # starts just under its title, not lower
    # The scramble is part of the header row, level with the title.
    scramble_top, scramble_bottom = top_and_bottom(page.scramble_bar)
    title_top, title_bottom = top_and_bottom(page.title)
    assert scramble_top <= title_bottom
    assert title_top <= scramble_bottom


ALG = "(R U R' U') (R' F R2 U') (R' U' R U) (R' F')"


def test_lines_break_between_bracket_groups() -> None:
    """Only the space before a new group (or a move outside groups) may break."""
    pieces = alg_pieces(ALG + " U", 3)
    breaks = breakable_spaces(pieces, 24)

    breakable = [piece for (piece, _), ok in zip(pieces, breaks, strict=True) if ok]
    assert breakable == ["(", " (", " (", " (", " U"]


def test_a_group_longer_than_a_line_may_break() -> None:
    """A group that can't fit on one line breaks like plain moves."""
    pieces = alg_pieces("(R U R' U' R U R' U')", 0)

    assert all(breakable_spaces(pieces, 10))


def test_hint_keeps_groups_together_in_the_label(page: TrainerPage) -> None:
    """Spaces inside groups are non-breaking in the shown and the masked text."""
    panel = page.hint_panel
    panel.show_hint(QPixmap(8, 8), ALG, 5)
    rows = panel.moves.text().split("<br>")

    expected = wrap_pieces(alg_pieces(ALG, 5), panel.line_length())
    assert len(rows) == len(expected)
    assert all('<span style="color:' in row or "·" not in row for row in rows)
    width = panel.moves.width()
    panel.show_hint(QPixmap(8, 8), ALG, 14)
    assert panel.moves.width() == width  # revealing moves never resizes the text


def test_wrap_keeps_groups_whole() -> None:
    """Lines end between groups, and a new line drops the space before it."""
    lines = wrap_pieces(alg_pieces(ALG, 0), 24)

    texts = ["".join(text for text, _ in line) for line in lines]
    assert texts == ["(R U R' U') (R' F R2 U')", "(R' U' R U) (R' F')"]


def test_hint_text_is_wide_enough_for_its_lines(page: TrainerPage) -> None:
    """The text box fits its longest line (Ra's last bracket used to be cut off)."""
    ra = "(R U R' F') (R U2 R' U2) (R' F) (R U R U2) (R' U')"
    panel = page.hint_panel
    panel.show_hint(QPixmap(8, 8), ra, 0)
    metrics = QFontMetricsF(panel.moves.font())

    for line in wrap_pieces(alg_pieces(ra, 99), panel.line_length()):
        text = "".join(piece for piece, _ in line)
        assert metrics.horizontalAdvance(text) <= panel.moves.width()
    assert panel.moves.width() <= panel.card.width()
