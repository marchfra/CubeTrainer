"""Tests for the Learn tab."""

from pathlib import Path

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from cubetrainer.cases.catalog import CaseStatus
from cubetrainer.db import Database
from cubetrainer.ui.learn_page import STATUS_COLORS, LearnPage


def make_page(qtbot: QtBot, db: Database) -> LearnPage:
    """Create and show a Learn page.

    Args:
        qtbot: pytest-qt helper.
        db: The database.

    Returns:
        The page.

    """
    page = LearnPage(db)
    qtbot.addWidget(page)
    page.show()
    return page


def test_lists_all_pll_cases(qtbot: QtBot) -> None:
    """Every PLL case gets an image, and all start unlearned."""
    page = make_page(qtbot, Database(":memory:"))

    assert page.set_picker.text() == "PLL  ▾"
    assert [a.text() for a in page.set_menu.actions()] == ["PLL"]
    assert len(page.case_list.images) == 21
    assert set(page.case_list.statuses.values()) == {CaseStatus.UNLEARNED}


def test_clicking_image_cycles_status(qtbot: QtBot) -> None:
    """Each click advances the status, and the image colour and tooltip follow."""
    page = make_page(qtbot, Database(":memory:"))
    image = page.case_list.images["T"]

    qtbot.mouseClick(image, Qt.MouseButton.LeftButton)
    assert page.case_list.statuses["T"] is CaseStatus.LEARNING
    assert STATUS_COLORS[CaseStatus.LEARNING] in image.styleSheet()
    assert image.toolTip() == "Status: learning (click to change)"

    qtbot.mouseClick(image, Qt.MouseButton.LeftButton)
    assert page.case_list.statuses["T"] is CaseStatus.FINISHED

    qtbot.mouseClick(image, Qt.MouseButton.LeftButton)
    assert page.case_list.statuses["T"] is CaseStatus.UNLEARNED
    assert image.styleSheet() == ""


def test_status_colour_does_not_reach_tooltip(qtbot: QtBot) -> None:
    """The status style only targets the image itself, so tooltips keep the default."""
    page = make_page(qtbot, Database(":memory:"))
    image = page.case_list.images["T"]

    qtbot.mouseClick(image, Qt.MouseButton.LeftButton)

    style = image.styleSheet()
    assert style.startswith(f"#{image.objectName()} {{")
    assert "QToolTip" not in style


def test_right_click_does_nothing(qtbot: QtBot) -> None:
    """Only the left button changes the status."""
    page = make_page(qtbot, Database(":memory:"))

    qtbot.mouseClick(page.case_list.images["T"], Qt.MouseButton.RightButton)

    assert page.case_list.statuses["T"] is CaseStatus.UNLEARNED


def test_statuses_survive_restart(qtbot: QtBot, tmp_path: Path) -> None:
    """Statuses are saved and shown again by a new page on the same database."""
    path = tmp_path / "app.db"
    db = Database(path)
    page = make_page(qtbot, db)
    qtbot.mouseClick(page.case_list.images["Ua"], Qt.MouseButton.LeftButton)
    for _ in range(2):
        qtbot.mouseClick(page.case_list.images["Jb"], Qt.MouseButton.LeftButton)
    db.close()

    reopened = make_page(qtbot, Database(path))

    statuses = reopened.case_list.statuses
    assert statuses["Ua"] is CaseStatus.LEARNING
    assert statuses["Jb"] is CaseStatus.FINISHED
    assert statuses["T"] is CaseStatus.UNLEARNED
    assert "finished" in reopened.case_list.images["Jb"].toolTip()


def test_set_picker_opens_menu(qtbot: QtBot) -> None:
    """Clicking the set picker pops up the set menu below it."""
    page = make_page(qtbot, Database(":memory:"))

    qtbot.mouseClick(page.set_picker, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(page.set_menu.isVisible)
    picker_bottom = page.set_picker.mapToGlobal(page.set_picker.rect().bottomLeft())
    assert page.set_menu.pos().y() >= picker_bottom.y() - 1
    page.set_menu.hide()


def test_selecting_a_set_relabels_buttons(qtbot: QtBot) -> None:
    """Choosing a set from the menu updates the picker and the Train button."""
    page = make_page(qtbot, Database(":memory:"))

    page.set_menu.actions()[0].trigger()

    assert page.set_picker.text() == "PLL  ▾"
    assert page.train_button.text() == "Train PLL"
    assert page.case_list.case_set.id == "pll"


def test_times_are_vertically_centred(qtbot: QtBot) -> None:
    """Best and avg sit in the middle of their row, like the other columns."""
    page = make_page(qtbot, Database(":memory:"))

    for labels in (page.case_list.best_labels, page.case_list.mean_labels):
        assert labels["T"].alignment() & Qt.AlignmentFlag.AlignVCenter
