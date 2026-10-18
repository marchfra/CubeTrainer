"""Small borderless buttons showing a drawn icon (a keyboard, a cog).

The icons are painted rather than taken from a font, so they stay crisp at this
size. They're drawn in a faint text colour and turn the system accent colour on
hover, darker while pressed; both follow light and dark mode.
"""

import math
from typing import override

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QCursor,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QAbstractButton, QWidget

#: How often a highlighted button checks whether the pointer has left, in ms.
_HOVER_RECHECK_MS: int = 150


class IconButton(QAbstractButton):
    """A borderless button whose icon subclasses draw in ``draw_icon``."""

    #: Size of the button, in logical pixels.
    SIZE: QSize = QSize(30, 22)

    def __init__(self, tooltip: str, parent: QWidget | None = None) -> None:
        """Create the button.

        Args:
            tooltip: What the button does.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.setFixedSize(self.SIZE)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)  # repaint on enter/leave
        self.setToolTip(tooltip)
        self._on_card: bool = False

    def set_on_card(self, *, on_card: bool) -> None:
        """Draw in white, for a button on a coloured card (e.g. Bold's timer).

        On a card in the accent colour, the accent hover colour wouldn't show.

        Args:
            on_card: Whether the button sits on a coloured card.

        """
        self._on_card = on_card
        self.update()

    @override
    def sizeHint(self) -> QSize:
        """Return the fixed size.

        Returns:
            ``SIZE``.

        """
        return self.SIZE

    def ink(self, *, hovered: bool, pressed: bool, enabled: bool = True) -> QColor:
        """Return the colour to draw the icon in.

        Args:
            hovered: Whether the mouse is over the button.
            pressed: Whether the button is held down.
            enabled: Whether the button can be clicked.

        Returns:
            A faint text colour (fainter when disabled), or the accent colour
            (darker when pressed); on a card, white in the same strengths.

        """
        if self._on_card:
            white = QColor("#ffffff")
            alpha = (
                0.25 if not enabled else 0.8 if pressed else 1.0 if hovered else 0.55
            )
            white.setAlphaF(alpha)
            return white
        palette = self.palette()
        if not enabled:
            faint = QColor(palette.windowText().color())
            faint.setAlphaF(0.15)
            return faint
        if not hovered and not pressed:
            muted = QColor(palette.windowText().color())
            muted.setAlphaF(0.4)  # visible, but quieter than any text
            return muted
        accent = palette.accent().color()  # the system accent, e.g. macOS blue
        return accent.darker(130) if pressed else accent

    def draw_icon(self, painter: QPainter, color: QColor) -> None:
        """Draw the icon centred in the button (subclasses implement this).

        Args:
            painter: An antialiased painter on the button.
            color: The colour to draw in.

        """

    @override
    def paintEvent(self, e: QPaintEvent) -> None:
        """Draw the icon in the colour for the current state.

        Args:
            e: The paint event (unused: the whole button is drawn).

        """
        del e
        hovered = self.pointer_inside()
        if hovered:
            # A menu or dialog opened by a click takes the mouse, so the button
            # never hears that the pointer left; check again until it has.
            QTimer.singleShot(_HOVER_RECHECK_MS, self, self.update)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.draw_icon(
                painter,
                self.ink(
                    hovered=hovered,
                    pressed=self.isDown(),
                    enabled=self.isEnabled(),
                ),
            )
        finally:
            painter.end()  # even if drawing fails, or Qt complains about it

    def pointer_inside(self) -> bool:
        """Return whether the mouse pointer is over the button right now.

        Asked of the pointer's position rather than of hover events, which stop
        while a menu or dialog the button opened has the mouse.

        Returns:
            True if the pointer is inside the button.

        """
        return self.isVisible() and self.rect().contains(
            self.mapFromGlobal(QCursor.pos()),
        )


class KeyboardButton(IconButton):
    """Shows a keyboard: an outline, two rows of keys and a space bar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the button.

        Args:
            parent: Optional parent widget.

        """
        super().__init__("Keyboard shortcuts", parent)

    @override
    def draw_icon(self, painter: QPainter, color: QColor) -> None:
        """Draw the keyboard.

        Args:
            painter: An antialiased painter on the button.
            color: The colour to draw in.

        """
        width, height = 24.0, 15.0
        left = (self.width() - width) / 2
        top = (self.height() - height) / 2
        painter.setPen(QPen(color, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(left, top, width, height), 3, 3)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        key = 2.4
        for row, (count, shift) in enumerate(((5, 0.0), (4, 1.8))):
            y = top + 3.2 + row * 3.6
            for i in range(count):
                x = left + 3.4 + shift + i * 3.8
                painter.drawRoundedRect(QRectF(x, y, key, key), 0.6, 0.6)
        painter.drawRoundedRect(QRectF(left + 7, top + 10.4, width - 14, 2), 0.8, 0.8)


class CogButton(IconButton):
    """Shows a cog: the outline of a toothed wheel, with a ring in the middle."""

    #: Number of teeth.
    TEETH: int = 8

    def __init__(self, tooltip: str = "Options", parent: QWidget | None = None) -> None:
        """Create the button.

        Args:
            tooltip: What the button does.
            parent: Optional parent widget.

        """
        super().__init__(tooltip, parent)

    @override
    def draw_icon(self, painter: QPainter, color: QColor) -> None:
        """Draw the cog.

        Args:
            painter: An antialiased painter on the button.
            color: The colour to draw in.

        """
        centre = QPointF(self.width() / 2, self.height() / 2)
        outer, root, hole = 7.6, 5.4, 2.2
        tooth = 2 * math.pi / self.TEETH
        # The outline alternates between the tips of the teeth and their roots;
        # each tooth is a little narrower at the tip than at the root.
        outline: list[QPointF] = []
        for i in range(self.TEETH):
            middle = i * tooth
            for angle, radius in (
                (middle - 0.32 * tooth, root),
                (middle - 0.2 * tooth, outer),
                (middle + 0.2 * tooth, outer),
                (middle + 0.32 * tooth, root),
            ):
                outline.append(
                    centre
                    + QPointF(radius * math.cos(angle), radius * math.sin(angle)),
                )
        wheel = QPainterPath()
        wheel.addPolygon(QPolygonF(outline))
        wheel.closeSubpath()
        # Outlined, with the same line as the keyboard, so the icons match.
        pen = QPen(color, 1.4)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(wheel)
        painter.drawEllipse(centre, hole, hole)


class ChevronButton(IconButton):
    """Shows a chevron pointing left or right (previous / next)."""

    def __init__(
        self,
        tooltip: str,
        *,
        left: bool,
        parent: QWidget | None = None,
    ) -> None:
        """Create the button.

        Args:
            tooltip: What the button does.
            left: Point left (else right).
            parent: Optional parent widget.

        """
        super().__init__(tooltip, parent)
        self.left: bool = left

    @override
    def draw_icon(self, painter: QPainter, color: QColor) -> None:
        """Draw the chevron.

        Args:
            painter: An antialiased painter on the button.
            color: The colour to draw in.

        """
        x, y = self.width() / 2, self.height() / 2
        reach = -3.5 if self.left else 3.5
        pen = QPen(color, 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(x - reach, y - 7),
                    QPointF(x + reach, y),
                    QPointF(x - reach, y + 7),
                ],
            ),
        )


class CopyButton(IconButton):
    """Shows two overlapping sheets (copy), or a tick right after copying.

    Attributes:
        copied: Whether the tick is shown.

    """

    def __init__(self, tooltip: str, parent: QWidget | None = None) -> None:
        """Create the button.

        Args:
            tooltip: What the button does.
            parent: Optional parent widget.

        """
        super().__init__(tooltip, parent)
        self.copied: bool = False

    def set_copied(self, *, copied: bool) -> None:
        """Show the tick (just copied) or the copy icon.

        Args:
            copied: Show the tick.

        """
        self.copied = copied
        self.update()

    @override
    def draw_icon(self, painter: QPainter, color: QColor) -> None:
        """Draw the sheets, or the tick in the accent colour.

        Args:
            painter: An antialiased painter on the button.
            color: The colour to draw in.

        """
        x, y = self.width() / 2, self.height() / 2
        pen = QPen(color, 1.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.copied:
            pen.setColor(self.palette().accent().color())
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.drawPolyline(
                QPolygonF(
                    [QPointF(x - 6, y), QPointF(x - 2, y + 4), QPointF(x + 6, y - 5)],
                ),
            )
            return
        painter.setPen(pen)
        painter.drawRoundedRect(QRectF(x - 3, y - 7, 10, 12), 2.5, 2.5)
        # The back sheet shows only where the front one doesn't cover it.
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(x - 5, y - 4),
                    QPointF(x - 7, y - 4),
                    QPointF(x - 7, y + 8),
                    QPointF(x + 2, y + 8),
                    QPointF(x + 2, y + 6),
                ],
            ),
        )


class MoreButton(IconButton):
    """Shows three dots in a row (more actions)."""

    @override
    def draw_icon(self, painter: QPainter, color: QColor) -> None:
        """Draw the dots.

        Args:
            painter: An antialiased painter on the button.
            color: The colour to draw in.

        """
        x, y = self.width() / 2, self.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        for dx in (-6.0, 0.0, 6.0):
            painter.drawEllipse(QPointF(x + dx, y), 1.7, 1.7)
