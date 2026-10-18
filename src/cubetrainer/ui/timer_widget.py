"""The big timer display, driven by the spacebar like cstimer."""

import time
from collections.abc import Callable
from typing import override

import shiboken6
from PySide6.QtCore import QEvent, QObject, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QPalette,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from cubetrainer.inspection import inspection_text, warnings_between
from cubetrainer.timing import TimerMachine, TimerState, format_ms
from cubetrainer.ui import theme
from cubetrainer.ui.icon_buttons import CogButton, KeyboardButton
from cubetrainer.ui.shortcuts import Shortcut
from cubetrainer.ui.theme import FontRole, set_theme_font

#: Display colour for each state; an empty string means the default text colour.
#: Text and icon colour on a timer card.
CARD_TEXT: str = "#ffffff"

#: Space between a timer card's edge and its corner buttons, in pixels.
CARD_INSET: int = 12


class TimeLabel(QLabel):
    """The big time, drawn in a colour of its own (the timer's state).

    It paints its text itself: a colour set through the palette or a per-widget
    style sheet would be undone when a theme switch restyles the app (Qt restores
    the palette, or font, a widget had earlier).

    Attributes:
        color: The colour of the time ("" for the app's text colour).

    """

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        """Create the label.

        Args:
            text: The first text.
            parent: Optional parent widget.

        """
        super().__init__(text, parent)
        self.color: str = ""

    def set_color(self, color: str) -> None:
        """Change the colour of the time.

        Args:
            color: A colour, or "" for the app's text colour.

        """
        if color != self.color:
            self.color = color
            self.update()

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the text in the label's colour, with its font and alignment.

        Args:
            event: The paint event (unused: the whole label is drawn).

        """
        del event
        painter = QPainter(self)
        try:
            ink = self.color or self.palette().color(QPalette.ColorRole.WindowText)
            painter.setPen(QColor(ink))
            painter.setFont(self.font())
            painter.drawText(self.contentsRect(), self.alignment(), self.text())
        finally:
            painter.end()


STATE_COLORS: dict[TimerState, str] = {
    TimerState.IDLE: "",
    TimerState.INSPECTING: "",
    TimerState.HOLDING: "#e5484d",
    TimerState.READY: "#30a46c",
    TimerState.RUNNING: "",
    TimerState.STOPPED: "",
}

#: Widgets that need the keyboard themselves; the timer must not steal their keys.
_TEXT_INPUTS: tuple[type[QWidget], ...] = (
    QLineEdit,
    QTextEdit,
    QPlainTextEdit,
    QAbstractSpinBox,
)

#: Modifier keys never stop a running solve, so e.g. Cmd+Tab doesn't end it.
MODIFIER_KEYS: frozenset[Qt.Key] = frozenset(
    {
        Qt.Key.Key_Shift,
        Qt.Key.Key_Control,
        Qt.Key.Key_Meta,
        Qt.Key.Key_Alt,
        Qt.Key.Key_AltGr,
        Qt.Key.Key_CapsLock,
    },
)

_REFRESH_INTERVAL_MS: int = 10

#: The keys the timer handles itself (in ``_handle_key``), for the shortcuts list.
TIMER_KEYS: tuple[Shortcut, ...] = (
    Shortcut("Space", "Hold until green, release to start (or to start inspection)"),
    Shortcut("Any key", "Stop the timer (modifier keys like ⌘ don't)"),
    Shortcut("Esc", "Cancel a hold or inspection"),
)

#: How-to text without inspection.
HINT_TEXT: str = "Hold space until green, release to start, press any key to stop"

#: How-to text when inspection also starts with a hold.
HOLD_INSPECTION_HINT_TEXT: str = (
    "Hold space until green to start inspection, then again to start the solve"
)

#: How-to text with inspection.
INSPECTION_HINT_TEXT: str = (
    "Press space to start inspection, then hold it until green and release to start"
)


class TimerWidget(QWidget):
    """Large time display controlled by the keyboard.

    Hold space until the display turns green, release to start, press any key to stop
    (modifier keys excepted).
    Keys are captured with an application-wide event filter, so the timer works
    regardless of which child widget has focus and space never activates a button.

    Attributes:
        solve_started: Emitted when the timer starts running.
        solve_finished: Emitted when a solve ends, with its time in milliseconds and
            the value of its inspection ``Penalty``.
        inspection_warning: Emitted with 8000 or 12000 when inspection reaches 8 or
            12 seconds.
        machine: The underlying state machine.
        display: The label showing the time.
        hint: How-to text under the time.
        shortcuts_button: Small button in the bottom-right corner; the page shows
            the shortcuts when it's clicked.
        options_button: Small button left of ``shortcuts_button``; the page shows
            its options menu when it's clicked.

    """

    solve_started = Signal()
    solve_finished = Signal(int, str)
    inspection_warning = Signal(int)

    def __init__(
        self,
        clock: Callable[[], int] = time.perf_counter_ns,
        parent: QWidget | None = None,
    ) -> None:
        """Create the widget and start listening for keys.

        Args:
            clock: Monotonic clock returning nanoseconds; injectable for tests.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self._clock: Callable[[], int] = clock
        self.machine: TimerMachine = TimerMachine()
        self._warned_up_to_ms: int = -1
        self._card_color: str = ""  # the timer card's colour now ("" until drawn)
        self._applying: bool = False  # setting up the card (see changeEvent)
        self._card_mode: bool | None = None  # the card trait it was set up for

        self.display: TimeLabel = TimeLabel(format_ms(0))
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Fixed-width digits keep the number from jittering while it runs; the
        # weight is the theme's (thin, light or bold).
        set_theme_font(self.display, FontRole.TIMER, 112)

        self.hint: QLabel = QLabel(HINT_TEXT)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setObjectName("muted")

        # In the bottom-right corner, outside the layout, so the time stays
        # centred (``resizeEvent`` keeps them in place): options, then shortcuts.
        self.shortcuts_button: KeyboardButton = KeyboardButton(self)
        self.options_button: CogButton = CogButton("Options", self)
        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.display)
        layout.addWidget(self.hint)
        layout.addStretch()

        self._refresh_timer: QTimer = QTimer(self)
        self._refresh_timer.setInterval(_REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self._apply_card_mode()  # for the theme in use; again on theme switches

    def set_inspection(self, *, enabled: bool, hold: bool = False) -> None:
        """Turn inspection on or off, updating the how-to text.

        Args:
            enabled: Whether a press first begins a 15 s inspection.
            hold: Whether starting inspection needs a hold until green too.

        """
        self.machine.inspection = enabled
        self.machine.hold_to_inspect = hold
        if not enabled:
            self.hint.setText(HINT_TEXT)
        else:
            self.hint.setText(
                HOLD_INSPECTION_HINT_TEXT if hold else INSPECTION_HINT_TEXT,
            )

    def refresh(self) -> None:
        """Advance the state machine and repaint the display."""
        now = self._clock()
        self.machine.update(now)
        state = self.machine.state
        inspected = self.machine.inspection_elapsed_ms(now)
        if inspected is not None:
            # Counting down, also while holding (red, then green), like cstimer.
            self.display.setText(inspection_text(inspected))
            for warning in warnings_between(self._warned_up_to_ms, inspected):
                self.inspection_warning.emit(warning)
            self._warned_up_to_ms = inspected
        elif self.machine.arming_inspection:
            # Holding to start inspection: show the full inspection time.
            self.display.setText(inspection_text(0))
        elif state is TimerState.HOLDING or state is TimerState.READY:
            # cstimer shows 0.00 while arming the timer.
            self.display.setText(format_ms(0))
        else:
            self.display.setText(format_ms(self.machine.elapsed_ms(now)))
        if inspected is None:
            self._warned_up_to_ms = -1
        self._paint_state(state)
        if state is TimerState.IDLE or state is TimerState.STOPPED:
            self._refresh_timer.stop()
        else:
            self._refresh_timer.start()

    def _paint_state(self, state: TimerState) -> None:
        """Show the state: the time's colour, or (timer card themes) the card's.

        Args:
            state: The timer's state.

        """
        if theme.CURRENT.timer_card:
            colors = theme.current_colors()
            card = {
                TimerState.HOLDING: colors.danger,
                TimerState.READY: colors.success,
            }.get(state, colors.timer_card)
            if card != self._card_color:
                self._card_color = card
                self.update()
            self.display.set_color(CARD_TEXT)
            return
        self.display.set_color(STATE_COLORS[state])

    def _apply_card_mode(self) -> None:
        """Set up (or undo) the timer card, for the theme in use.

        On a card, text and icons are white and the corner buttons sit inside its
        padding.
        """
        card = theme.CURRENT.timer_card
        self._card_mode = card
        self._card_color = ""
        # Style sheet rules colour it (#muted, or #onCard on a card), not a
        # per-widget sheet: re-applying one of those resets fonts to old ones.
        self.hint.setObjectName("onCard" if card else "muted")
        self.hint.style().unpolish(self.hint)
        self.hint.style().polish(self.hint)
        for button in (self.shortcuts_button, self.options_button):
            button.set_on_card(on_card=card)
        self._place_corner_buttons()
        self.refresh()
        self.update()

    @override
    def changeEvent(self, event: QEvent) -> None:
        """Follow theme switches (they change the app's style sheet).

        Args:
            event: The change event.

        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._card_color = ""  # light/dark switch: pick the card colour again
            self.update()
        if event.type() == QEvent.Type.StyleChange and not self._applying:
            self._applying = True
            try:
                self._apply_card_mode()
            finally:
                self._applying = False

    def _sync_card_mode(self) -> None:
        """Set the card up again if the theme's card trait changed meanwhile.

        A hidden timer (e.g. a trainer's, behind the full timer) may miss the
        restyle notice of a theme switch; it catches up when shown or painted.
        """
        if self._card_mode is not theme.CURRENT.timer_card and not self._applying:
            self._applying = True
            try:
                self._apply_card_mode()
            finally:
                self._applying = False

    @override
    def showEvent(self, event: QShowEvent) -> None:
        """Catch up with theme switches made while hidden.

        Args:
            event: The show event.

        """
        super().showEvent(event)
        self._sync_card_mode()

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Draw the timer card (timer card themes only).

        Args:
            event: The paint event.

        """
        super().paintEvent(event)
        self._sync_card_mode()
        if not theme.CURRENT.timer_card:
            return
        if not self._card_color:
            self._paint_state(self.machine.state)
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._card_color))
            radius = theme.CURRENT.radius + 10
            painter.drawRoundedRect(QRectF(self.rect()), radius, radius)
        finally:
            painter.end()

    def _should_capture(self) -> bool:
        """Decide whether keyboard events should go to the timer.

        Returns:
            True while a solve is running; otherwise only when the timer is visible,
            no dialog is open and no text field has focus.

        """
        if self.machine.state is TimerState.RUNNING:
            return True
        if not self.isVisible() or QApplication.activeModalWidget() is not None:
            return False
        return not isinstance(QApplication.focusWidget(), _TEXT_INPUTS)

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Intercept key events application-wide and feed them to the state machine.

        Args:
            watched: The object the event was sent to.
            event: The event being delivered.

        Returns:
            True if the event was consumed by the timer.

        """
        if not shiboken6.isValid(self):
            # A timer whose window is being destroyed may still be asked while its
            # filter is removed; it has nothing to say any more.
            return False
        if (
            isinstance(event, QKeyEvent)
            and event.type() in {QEvent.Type.KeyPress, QEvent.Type.KeyRelease}
            and event.key() not in MODIFIER_KEYS
            and self._should_capture()
        ):
            return self._handle_key(event)
        return super().eventFilter(watched, event)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep the options and shortcuts buttons in the bottom-right corner.

        Args:
            event: The resize event.

        """
        super().resizeEvent(event)
        self._place_corner_buttons()

    def _place_corner_buttons(self) -> None:
        """Put the options and shortcuts buttons in the bottom-right corner.

        On a timer card they sit inside its rounded corner.
        """
        inset = CARD_INSET if theme.CURRENT.timer_card else 0
        right = self.width() - inset
        for button in (self.shortcuts_button, self.options_button):
            size = button.sizeHint()
            right -= size.width()
            button.move(right, self.height() - size.height() - inset)

    def _handle_key(self, event: QKeyEvent) -> bool:
        """Apply a captured key press or release to the timer.

        Args:
            event: A key press or release that the timer may consume.

        Returns:
            True if the event was consumed; False lets it reach its target.

        """
        is_press = event.type() == QEvent.Type.KeyPress
        is_space = event.key() == Qt.Key.Key_Space
        state = self.machine.state
        if event.key() == Qt.Key.Key_Escape and state in {
            TimerState.INSPECTING,
            TimerState.HOLDING,
            TimerState.READY,
        }:
            if is_press:
                self.machine.cancel()
                self.refresh()
            return True
        if not is_space and state not in {TimerState.RUNNING, TimerState.STOPPED}:
            return False
        if event.isAutoRepeat():
            return True

        now = self._clock()
        if is_press:
            result = self.machine.key_down(now, is_start_key=is_space)
            if result is not None:
                self.solve_finished.emit(result, self.machine.last_penalty.value)
        else:
            self.machine.key_up(now, is_start_key=is_space)
            if self.machine.state is TimerState.RUNNING:
                self.solve_started.emit()
        self.refresh()
        return True
