"""Tests for the trainer's filter dialog."""

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from cubetrainer.cases.catalog import CaseStatus, load_case_set
from cubetrainer.cases.filters import CaseFilter
from cubetrainer.ui.filter_dialog import FilterDialog

PLL = load_case_set("pll")


def make_dialog(
    qtbot: QtBot,
    case_filter: CaseFilter,
    statuses: dict[str, CaseStatus] | None = None,
) -> FilterDialog:
    """Create and show a filter dialog for PLL.

    Args:
        qtbot: pytest-qt helper.
        case_filter: The filter to start from.
        statuses: Learning statuses (all unlearned if omitted).

    Returns:
        The dialog.

    """
    dialog = FilterDialog(PLL, statuses or {}, case_filter)
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def test_starts_from_the_given_filter(qtbot: QtBot) -> None:
    """Checkboxes and radio buttons reflect the filter."""
    dialog = make_dialog(
        qtbot,
        CaseFilter(
            groups=frozenset({"Edges Only"}),
            statuses=frozenset({CaseStatus.LEARNING}),
            realistic=True,
        ),
        {"H": CaseStatus.LEARNING},
    )

    assert [b.isChecked() for b in dialog.group_boxes.values()] == [False, False, True]
    assert dialog.status_boxes[CaseStatus.LEARNING].isChecked()
    assert not dialog.status_boxes[CaseStatus.UNLEARNED].isChecked()
    assert dialog.realistic_button.isChecked()
    assert dialog.count_label.text() == "1 of 21 cases selected"


def test_all_groups_means_no_group_restriction(qtbot: QtBot) -> None:
    """With every group ticked, the filter keeps groups=None."""
    dialog = make_dialog(qtbot, CaseFilter())

    assert dialog.case_filter() == CaseFilter()
    assert dialog.count_label.text() == "21 of 21 cases selected"


def test_ok_is_disabled_when_nothing_matches(qtbot: QtBot) -> None:
    """Unticking every status selects nothing, so OK can't be pressed."""
    dialog = make_dialog(qtbot, CaseFilter())

    for box in dialog.status_boxes.values():
        box.setChecked(False)

    assert dialog.count_label.text() == "0 of 21 cases selected"
    assert not dialog.ok_button.isEnabled()


def test_none_and_all_group_buttons(qtbot: QtBot) -> None:
    """The None button unticks every group and the All button ticks them again."""
    dialog = make_dialog(qtbot, CaseFilter())
    buttons = {b.text(): b for b in dialog.findChildren(type(dialog.ok_button))}

    qtbot.mouseClick(buttons["None"], Qt.MouseButton.LeftButton)
    assert not any(b.isChecked() for b in dialog.group_boxes.values())
    assert dialog.case_filter().groups == frozenset()

    qtbot.mouseClick(buttons["All"], Qt.MouseButton.LeftButton)
    assert all(b.isChecked() for b in dialog.group_boxes.values())


def test_reads_back_a_new_filter(qtbot: QtBot) -> None:
    """Changing controls produces the matching filter."""
    dialog = make_dialog(qtbot, CaseFilter())

    dialog.group_boxes["Adjacent Corner Swap"].setChecked(False)
    dialog.status_boxes[CaseStatus.FINISHED].setChecked(False)
    dialog.realistic_button.setChecked(True)

    assert dialog.case_filter() == CaseFilter(
        groups=frozenset({"Diagonal Corner Swap", "Edges Only"}),
        statuses=frozenset({CaseStatus.UNLEARNED, CaseStatus.LEARNING}),
        realistic=True,
    )
    assert dialog.count_label.text() == "9 of 21 cases selected"
