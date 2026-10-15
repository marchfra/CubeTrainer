"""The big timer display, driven by the spacebar like cstimer."""

import time
from collections.abc import Callable
from typing import override

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QKeyEvent
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

from cubetrainer.timing import TimerMachine, TimerState, format_ms

#: Display colour for each state; an empty string means the default text colour.
STATE_COLORS: dict[TimerState, str] = {
    TimerState.IDLE: "",
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


class TimerWidget(QWidget):
    """Large time display controlled by the keyboard.

    Hold space until the display turns green, release to start, press any key to stop
    (modifier keys excepted).
    Keys are captured with an application-wide event filter, so the timer works
    regardless of which child widget has focus and space never activates a button.

    Attributes:
        solve_started: Emitted when the timer starts running.
        solve_finished: Emitted with the solve time in milliseconds when a solve ends.
        machine: The underlying state machine.
        display: The label showing the time.

    """

    solve_started = Signal()
    solve_finished = Signal(int)

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

        self.display: QLabel = QLabel(format_ms(0))
        self.display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(96)
        # Tabular (fixed-width) digits keep the number from jittering while it runs.
        font.setFeature(QFont.Tag("tnum"), 1)
        self.display.setFont(font)

        hint = QLabel("Hold space until green, release to start, press any key to stop")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.display)
        layout.addWidget(hint)
        layout.addStretch()

        self._refresh_timer: QTimer = QTimer(self)
        self._refresh_timer.setInterval(_REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self.refresh)

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def refresh(self) -> None:
        """Advance the state machine and repaint the display."""
        now = self._clock()
        self.machine.update(now)
        state = self.machine.state
        if state is TimerState.HOLDING or state is TimerState.READY:
            # cstimer shows 0.00 while arming the timer.
            self.display.setText(format_ms(0))
        else:
            self.display.setText(format_ms(self.machine.elapsed_ms(now)))
        color = STATE_COLORS[state]
        self.display.setStyleSheet(f"color: {color};" if color else "")
        if state in {TimerState.HOLDING, TimerState.READY, TimerState.RUNNING}:
            self._refresh_timer.start()
        else:
            self._refresh_timer.stop()

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
        if (
            isinstance(event, QKeyEvent)
            and event.type() in {QEvent.Type.KeyPress, QEvent.Type.KeyRelease}
            and event.key() not in MODIFIER_KEYS
            and self._should_capture()
        ):
            return self._handle_key(event)
        return super().eventFilter(watched, event)

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
                self.solve_finished.emit(result)
        else:
            self.machine.key_up(now, is_start_key=is_space)
            if self.machine.state is TimerState.RUNNING:
                self.solve_started.emit()
        self.refresh()
        return True
