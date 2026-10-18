"""A combo box whose list drops down below it, in a rounded panel."""

from typing import override

from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox, QWidget

from cubetrainer.ui.theme import CURRENT, current_colors


class Dropdown(QComboBox):
    """A combo box that opens its list just below itself, like a web dropdown.

    macOS places the list so the selected item covers the box; that hides the box
    and the items above it jump around. Here the list always starts below the box
    (or ends above it, when there's no room below), as wide as the box at least,
    in a rounded panel like the theme's menus. It never takes keyboard focus, so
    the space bar always reaches the timer.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the (empty) dropdown.

        Args:
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # The list's window is see-through and its rounded panel is painted here
        # (``eventFilter``): Qt draws that window itself, square, and ignores style
        # sheet backgrounds on it.
        container = self.view().window()
        container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        container.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        container.setWindowFlag(Qt.WindowType.NoDropShadowWindowHint)
        container.installEventFilter(self)

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Paint the list's rounded panel before the list draws over it.

        Args:
            watched: The object the event is for.
            event: The event.

        Returns:
            False: the list still paints itself on top.

        """
        if event.type() == QEvent.Type.Paint and isinstance(watched, QWidget):
            colors = current_colors()
            painter = QPainter(watched)
            try:
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                painter.setPen(QPen(QColor(colors.border), 1))
                painter.setBrush(QColor(colors.surface))
                radius = max(CURRENT.radius - 6, 4)
                rect = QRectF(watched.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
                painter.drawRoundedRect(rect, radius, radius)
            finally:
                painter.end()
        return super().eventFilter(watched, event)

    @override
    def showPopup(self) -> None:
        """Open the list, then move it below the box (or above, if it won't fit)."""
        super().showPopup()
        popup = self.view().window()
        below = self.mapToGlobal(QPoint(0, self.height() + 2))
        top = below.y()
        screen = self.screen().availableGeometry()
        if top + popup.height() > screen.bottom():
            top = self.mapToGlobal(QPoint(0, -2)).y() - popup.height()
        popup.setMinimumWidth(self.width())
        popup.move(below.x(), max(top, screen.top()))
