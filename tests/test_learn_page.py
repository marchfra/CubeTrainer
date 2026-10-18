"""Tests for the Learn tab."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QDialog, QLabel
from pytestqt.qtbot import QtBot

from cubetrainer.cases.catalog import CaseCustomization, CaseStatus
from cubetrainer.db import Database
from cubetrainer.ui.case_editor import CaseEditor
from cubetrainer.ui.learn_page import AVAILABLE_SETS, STATUS_COLORS, LearnPage


def make_page(qtbot: QtBot, db: Database) -> LearnPage:
    """Create and show a Learn page, showing the PLL set.

    Args:
        qtbot: pytest-qt helper.
        db: The database.

    Returns:
        The page.

    """
    page = LearnPage(db)
    qtbot.addWidget(page)
    page.show()
    page.select_set("pll")
    return page


def test_lists_all_pll_cases(qtbot: QtBot) -> None:
    """Every PLL case gets an image, and all start unlearned."""
    page = make_page(qtbot, Database(":memory:"))

    assert page.set_picker.currentText() == "PLL"
    assert [page.set_picker.itemText(i) for i in range(page.set_picker.count())] == [
        "2-Look OLL",
        "2-Look PLL",
        "OLL",
        "PLL",
    ]
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


def test_set_picker_is_a_combo_box(qtbot: QtBot) -> None:
    """The set picker is a combo box listing the sets, ids as item data."""
    page = make_page(qtbot, Database(":memory:"))

    assert isinstance(page.set_picker, QComboBox)
    assert page.set_picker.itemData(page.set_picker.currentIndex()) == "pll"


def test_selecting_a_set_relabels_buttons(qtbot: QtBot) -> None:
    """Choosing a set in the picker updates the list and the Train button."""
    page = make_page(qtbot, Database(":memory:"))

    page.set_picker.setCurrentIndex(page.set_picker.findData("oll"))

    assert page.set_picker.currentText() == "OLL"
    assert page.train_button.text() == "Train OLL"
    assert page.case_list.case_set.id == "oll"
    assert len(page.case_list.images) == 57


def test_times_are_vertically_centred(qtbot: QtBot) -> None:
    """Best and avg sit in the middle of their row, like the other columns."""
    page = make_page(qtbot, Database(":memory:"))

    for labels in (page.case_list.best_labels, page.case_list.mean_labels):
        assert labels["T"].alignment() & Qt.AlignmentFlag.AlignVCenter


def test_opens_on_pll(qtbot: QtBot) -> None:
    """The Learn tab starts on the PLL set."""
    page = LearnPage(Database(":memory:"))
    qtbot.addWidget(page)

    assert page.case_list.case_set.id == "pll"
    assert page.set_picker.currentText() == "PLL"


def test_layout_is_the_same_for_every_set(qtbot: QtBot) -> None:
    """Buttons and columns stay put when switching sets."""
    page = make_page(qtbot, Database(":memory:"))
    page.resize(1280, 700)
    headers = ("Name", "Algorithm", "Group", "Best", "Avg")
    layouts = []
    for set_id in AVAILABLE_SETS:
        page.select_set(set_id)
        qtbot.wait(1)  # let the new list lay out
        columns = {
            label.text(): label.mapTo(page, label.rect().topLeft()).x()
            for label in page.case_list.findChildren(QLabel)
            if label.text() in headers
        }
        layouts.append((page.set_picker.width(), page.train_button.x(), columns))

    assert all(layout == layouts[0] for layout in layouts)


def test_editing_a_case_updates_and_saves_it(qtbot: QtBot, tmp_path: Path) -> None:
    """An accepted edit changes the row and is stored; a cancelled one isn't."""
    db = Database(tmp_path / "app.db")
    page = make_page(qtbot, db)
    case_list = page.case_list
    new_alg = "R U R' U' R' F R2 U' R' U' R U R' F'"
    old_image = case_list.images["T"].pixmap().toImage()

    def accept(dialog: QDialog) -> int:
        assert isinstance(dialog, CaseEditor)
        dialog.alg_edit.setText(new_alg)
        dialog.rotate(1)
        return QDialog.DialogCode.Accepted

    case_list.run_dialog = accept
    qtbot.mouseClick(case_list.edit_buttons["T"], Qt.MouseButton.LeftButton)

    assert case_list.alg_labels["T"].text() == new_alg
    assert case_list.images["T"].pixmap().toImage() != old_image
    assert db.load_case_customizations("pll")["T"] == CaseCustomization(
        alg=new_alg,
        rotation=1,
    )

    def cancel(dialog: QDialog) -> int:
        assert isinstance(dialog, CaseEditor)
        dialog.alg_edit.setText("M2 U M U2 M' U M2")
        return QDialog.DialogCode.Rejected

    case_list.run_dialog = cancel
    case_list.edit_case("T")
    assert case_list.alg_labels["T"].text() == new_alg

    reopened = make_page(qtbot, Database(tmp_path / "app.db"))
    assert reopened.case_list.alg_labels["T"].text() == new_alg
