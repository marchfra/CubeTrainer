"""Tests for the Timer tab: scramble bar wiring and buttons."""

from itertools import count

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QPushButton
from pytestqt.qtbot import QtBot

from cubetrainer.db import TIMER_KIND, Database, DbSessionStore
from cubetrainer.settings import MemorySettings
from cubetrainer.solves import Penalty
from cubetrainer.ui.sizing import reserve_width
from cubetrainer.ui.solve_dialog import SolveDialog
from cubetrainer.ui.timer_page import TimerPage
from cubetrainer.ui.timer_widget import HINT_TEXT, INSPECTION_HINT_TEXT
from tests.helpers import FakeClock, do_solve


@pytest.fixture
def page(qtbot: QtBot, clock: FakeClock) -> TimerPage:
    """Provide a visible timer page with predictable scrambles "s0", "s1", ...

    Args:
        qtbot: pytest-qt helper.
        clock: The fake clock.

    Returns:
        The page.

    """
    counter = count()
    widget = TimerPage(generate=lambda: f"s{next(counter)}", clock=clock)
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_shows_first_scramble_with_back_disabled(page: TimerPage) -> None:
    """The page opens on a scramble and there is nothing to go back to."""
    assert page.scramble_bar.label.text() == "s0"
    assert not page.scramble_bar.prev_button.isEnabled()


def test_buttons_browse_scrambles(qtbot: QtBot, page: TimerPage) -> None:
    """▶ goes forward (generating), ◀ goes back."""
    bar = page.scramble_bar
    qtbot.mouseClick(bar.next_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(bar.next_button, Qt.MouseButton.LeftButton)
    assert bar.label.text() == "s2"
    assert bar.prev_button.isEnabled()

    qtbot.mouseClick(bar.prev_button, Qt.MouseButton.LeftButton)
    assert bar.label.text() == "s1"


def test_copy_puts_scramble_on_clipboard(qtbot: QtBot, page: TimerPage) -> None:
    """Copy places the current scramble on the clipboard and confirms it."""
    qtbot.mouseClick(page.scramble_bar.copy_button, Qt.MouseButton.LeftButton)

    assert QGuiApplication.clipboard().text() == "s0"
    assert page.scramble_bar.copy_button.copied  # shows a tick
    qtbot.waitUntil(lambda: not page.scramble_bar.copy_button.copied, timeout=3000)


def test_scramble_buttons_are_fixed_size_icons(page: TimerPage) -> None:
    """Previous, next and copy are small fixed-size icons, whatever they show."""
    bar = page.scramble_bar
    for button in (bar.prev_button, bar.next_button, bar.copy_button):
        assert button.minimumSize() == button.maximumSize()


def test_reserve_width_fits_longest_label(qtbot: QtBot) -> None:
    """A button sized for a long label doesn't resize when it shows that label."""
    button = QPushButton("Copy")
    qtbot.addWidget(button)
    long_text = "Copied to the clipboard, all good"

    reserve_width(button, long_text)
    width = button.width()
    button.setText(long_text)

    assert button.text() == long_text
    assert button.minimumWidth() == button.maximumWidth() == width
    assert button.sizeHint().width() <= width


def test_solve_moves_to_new_scramble(
    qtbot: QtBot,
    page: TimerPage,
    clock: FakeClock,
) -> None:
    """Finishing a solve shows a freshly generated scramble."""
    page.scramble_bar.show_next()
    page.scramble_bar.show_previous()

    do_solve(qtbot, page, clock, 5_000)

    assert page.scramble_bar.label.text() == "s2"


def test_buttons_do_not_take_focus(page: TimerPage) -> None:
    """Buttons can't be focused, so space never triggers them."""
    bar = page.scramble_bar
    for button in (bar.prev_button, bar.next_button, bar.copy_button):
        assert button.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_solve_is_recorded_with_its_scramble(
    qtbot: QtBot,
    page: TimerPage,
    clock: FakeClock,
) -> None:
    """A finished solve lands in the table with the scramble shown at its start."""
    do_solve(qtbot, page, clock, 8_765)

    assert len(page.solves) == 1
    assert page.solves.solves[0].time_ms == 8_765
    assert page.solves.solves[0].scramble == "s0"
    assert page.solves_panel.model.rowCount() == 1


def press_shortcut(qtbot: QtBot, page: TimerPage, key: Qt.Key) -> None:
    """Press Cmd+key (Qt's ControlModifier is Cmd on macOS).

    Args:
        qtbot: pytest-qt helper.
        page: The page (its window must be active for shortcuts to fire).
        key: The key pressed together with Cmd.

    """
    qtbot.keyClick(page, key, Qt.KeyboardModifier.ControlModifier)


@pytest.mark.parametrize(
    ("key", "penalty"),
    [
        (Qt.Key.Key_2, Penalty.PLUS_TWO),
        (Qt.Key.Key_3, Penalty.DNF),
    ],
)
def test_penalty_shortcuts_apply_to_last_solve(
    qtbot: QtBot,
    page: TimerPage,
    clock: FakeClock,
    key: Qt.Key,
    penalty: Penalty,
) -> None:
    """Cmd+2 / Cmd+3 set +2 / DNF on the last solve, and Cmd+1 clears it."""
    do_solve(qtbot, page, clock, 1_000)
    do_solve(qtbot, page, clock, 2_000)
    page.activateWindow()
    qtbot.waitUntil(page.isActiveWindow)

    press_shortcut(qtbot, page, key)
    assert page.solves.solves[-1].penalty is penalty
    assert page.solves.solves[0].penalty is Penalty.OK

    press_shortcut(qtbot, page, Qt.Key.Key_1)
    assert page.solves.solves[-1].penalty is Penalty.OK


@pytest.mark.parametrize("answer", [True, False])
def test_cmd_z_deletes_last_solve_after_confirmation(
    qtbot: QtBot,
    page: TimerPage,
    clock: FakeClock,
    *,
    answer: bool,
) -> None:
    """Cmd+Z asks first and only deletes when confirmed."""
    questions: list[str] = []

    def confirm(question: str) -> bool:
        questions.append(question)
        return answer

    page.confirm = confirm
    do_solve(qtbot, page, clock, 1_000)
    do_solve(qtbot, page, clock, 2_000)
    page.activateWindow()
    qtbot.waitUntil(page.isActiveWindow)

    press_shortcut(qtbot, page, Qt.Key.Key_Z)

    assert questions == ["Delete the last solve (2.00)?"]
    assert len(page.solves) == (1 if answer else 2)


def test_shortcuts_without_solves_do_nothing(page: TimerPage) -> None:
    """Penalty and delete shortcuts are harmless on an empty session."""
    page.confirm = lambda _q: pytest.fail("should not ask")

    page.set_last_penalty(Penalty.DNF)
    page.delete_last()

    assert len(page.solves) == 0


@pytest.mark.parametrize(("result", "remaining"), [(SolveDialog.DELETED, 1), (0, 2)])
def test_solve_dialog_result_is_applied(
    qtbot: QtBot,
    page: TimerPage,
    clock: FakeClock,
    result: int,
    remaining: int,
) -> None:
    """Closing the dialog with Delete removes the solve; closing normally keeps it."""
    do_solve(qtbot, page, clock, 1_000)
    do_solve(qtbot, page, clock, 2_000)
    shown: list[SolveDialog] = []

    def run_dialog(dialog: QDialog) -> int:
        assert isinstance(dialog, SolveDialog)
        shown.append(dialog)
        return result

    page.run_dialog = run_dialog
    page.show_solve(0)

    assert shown[0].windowTitle() == "Solve #1"
    assert len(page.solves) == remaining
    assert page.solves_panel.model.rowCount() == remaining


def test_dialog_penalty_change_is_saved(qtbot: QtBot, clock: FakeClock) -> None:
    """A penalty chosen in the solve dialog is written to the database."""
    db = Database(":memory:")
    session = db.get_or_create_session()
    page = TimerPage(
        sessions=DbSessionStore(db, TIMER_KIND),
        generate=lambda: "s",
        clock=clock,
    )
    qtbot.addWidget(page)
    page.show()
    do_solve(qtbot, page, clock, 1_000)

    def run_dialog(dialog: QDialog) -> int:
        assert isinstance(dialog, SolveDialog)
        dialog.penalty_buttons[Penalty.DNF].setChecked(True)
        return 0

    page.run_dialog = run_dialog
    page.show_solve(0)

    assert [s.penalty for s in db.load_solves(session)] == [Penalty.DNF]


def test_inspection_options_default_and_persist(qtbot: QtBot) -> None:
    """The full timer starts with inspection and beeps on; changes are saved."""
    settings = MemorySettings()
    page = TimerPage(generate=lambda: "s", settings=settings)
    qtbot.addWidget(page)

    assert page.inspection_action.isChecked()
    assert page.audio_action.isChecked()
    assert page.timer.machine.inspection

    assert page.timer.hint.text() == INSPECTION_HINT_TEXT

    page.inspection_action.setChecked(False)
    assert not page.timer.machine.inspection
    assert page.timer.hint.text() == HINT_TEXT
    assert not page.audio_action.isEnabled()  # beeps need inspection
    assert settings.values["timer.inspection"] == "0"

    again = TimerPage(generate=lambda: "s", settings=settings)
    qtbot.addWidget(again)
    assert not again.inspection_action.isChecked()


@pytest.mark.parametrize("audio", [True, False])
def test_warnings_beep_only_when_enabled(qtbot: QtBot, *, audio: bool) -> None:
    """Warnings play a sound only with beeps turned on."""
    page = TimerPage(generate=lambda: "s")
    qtbot.addWidget(page)
    played: list[int] = []
    page.play_warning = played.append
    page.audio_action.setChecked(audio)

    page.timer.inspection_warning.emit(8_000)

    assert played == ([8_000] if audio else [])


def test_late_start_is_recorded_as_plus_two(
    qtbot: QtBot,
    page: TimerPage,
    clock: FakeClock,
) -> None:
    """A solve started after 15 s of inspection is saved with +2."""
    page.inspection_action.setChecked(True)
    qtbot.keyPress(page, Qt.Key.Key_Space)
    qtbot.keyRelease(page, Qt.Key.Key_Space)
    clock.advance_ms(15_500)
    qtbot.keyPress(page, Qt.Key.Key_Space)
    clock.advance_ms(300)
    qtbot.keyRelease(page, Qt.Key.Key_Space)
    clock.advance_ms(10_000)
    qtbot.keyPress(page, Qt.Key.Key_Space)

    assert page.solves.solves[-1].penalty is Penalty.PLUS_TWO
    assert page.solves_panel.model.data(page.solves_panel.model.index(0, 1)) == "12.00+"


def test_hold_to_inspect_option(qtbot: QtBot) -> None:
    """Holding to start inspection is off by default, saved, and needs inspection."""
    settings = MemorySettings()
    page = TimerPage(generate=lambda: "s", settings=settings)
    qtbot.addWidget(page)
    assert not page.hold_action.isChecked()
    assert not page.timer.machine.hold_to_inspect

    page.hold_action.setChecked(True)
    assert page.timer.machine.hold_to_inspect
    assert settings.values["timer.inspection_hold"] == "1"

    page.inspection_action.setChecked(False)
    assert not page.hold_action.isEnabled()
