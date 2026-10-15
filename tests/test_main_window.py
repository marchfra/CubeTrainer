"""Tests for the main window shell."""

from pytestqt.qtbot import QtBot

from cubetrainer.ui.main_window import TAB_TITLES, MainWindow


def test_window_has_expected_tabs(qtbot: QtBot) -> None:
    """The window exposes the Timer, Learn and Stats tabs in order."""
    window = MainWindow()
    qtbot.addWidget(window)

    titles = [window.tabs.tabText(i) for i in range(window.tabs.count())]

    assert titles == list(TAB_TITLES)


def test_tabs_can_be_switched(qtbot: QtBot) -> None:
    """Selecting a tab makes it the current one."""
    window = MainWindow()
    qtbot.addWidget(window)

    window.tabs.setCurrentIndex(2)

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Stats"
