"""Tests for the dropdown (a combo box whose list opens below it)."""

from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from cubetrainer.ui.dropdown import Dropdown


def test_list_opens_below_the_box(qtbot: QtBot) -> None:
    """The list starts under the box, at least as wide, and the box keeps no focus."""
    box = Dropdown()
    qtbot.addWidget(box)
    for name in ("Session 1", "Synthetic", "Synthetic slowest first"):
        box.addItem(name)
    box.setCurrentIndex(2)  # macOS would put this item over the box
    box.move(100, 100)
    box.show()
    qtbot.waitExposed(box)

    box.showPopup()
    popup = box.view().window()
    qtbot.waitUntil(popup.isVisible)

    bottom = box.mapToGlobal(QPoint(0, box.height())).y()
    assert popup.geometry().top() >= bottom
    assert popup.width() >= box.width()
    assert box.focusPolicy() == Qt.FocusPolicy.NoFocus
    box.hidePopup()


def test_list_window_is_see_through_for_its_rounded_panel(qtbot: QtBot) -> None:
    """The list's window is translucent and frameless; its panel is painted round."""
    box = Dropdown()
    qtbot.addWidget(box)
    container = box.view().window()

    assert container.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert container.windowFlags() & Qt.WindowType.FramelessWindowHint
    box.addItem("one")
    box.show()
    box.showPopup()
    qtbot.waitUntil(container.isVisible)
    assert not container.grab().isNull()  # paints the panel without errors
    box.hidePopup()
