"""The big timer display, driven by the spacebar like cstimer."""

import time
from collections.abc import Callable
from typing import override

import shiboken6
from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent, QResizeEvent
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
from cubetrainer.ui.icon_buttons import CogButton, KeyboardButton
from cubetrainer.ui.shortcuts import Shortcut
from cubetrainer.ui.theme import number_font

#: Display colour for each state; an empty string means the default text colour.
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

        self.display: QLabel = QLabel(format_ms(0))
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Fixed-width digits keep the number from jittering while it runs.
        self.display.setFont(number_font(112, QFont.Weight.Light))

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
        color = STATE_COLORS[state]
        self.display.setStyleSheet(f"color: {color};" if color else "")
        if state is TimerState.IDLE or state is TimerState.STOPPED:
            self._refresh_timer.stop()
        else:
            self._refresh_timer.start()

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
        right = self.width()
        for button in (self.shortcuts_button, self.options_button):
            size = button.sizeHint()
            right -= size.width()
            button.move(right, self.height() - size.height())

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
