"""Scramble display with previous / next / copy icon buttons."""

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from cubetrainer.scramble_history import ScrambleHistory
from cubetrainer.ui.icon_buttons import ChevronButton, CopyButton
from cubetrainer.ui.theme import mono_font

_COPIED_FEEDBACK_MS: int = 1200


class ScrambleBar(QWidget):
    """Shows the current scramble and lets the user browse or copy it.

    Attributes:
        history: The scramble history being displayed.
        label: The label showing the scramble text.
        prev_button: Goes back to the previous scramble.
        next_button: Goes forward, generating a new scramble at the end.
        copy_button: Copies the scramble to the clipboard.
        scramble_changed: Emitted with the scramble each time one is shown, new or
            browsed to.

    """

    scramble_changed = Signal(str)

    def __init__(
        self,
        generate: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        """Create the bar and generate the first scramble.

        Args:
            generate: Function returning a new scramble each time it's called.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.history: ScrambleHistory = ScrambleHistory(generate)

        self.label: QLabel = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.label.setFont(mono_font(16))

        # Small borderless icons (like the timer's cog), leaving the scramble room
        # to stay on one line.
        self.prev_button: ChevronButton = ChevronButton("Previous scramble", left=True)
        self.next_button: ChevronButton = ChevronButton("Next scramble", left=False)
        self.copy_button: CopyButton = CopyButton("Copy scramble to clipboard")
        self.prev_button.clicked.connect(self.show_previous)
        self.next_button.clicked.connect(self.show_next)
        self.copy_button.clicked.connect(self.copy)

        layout = QHBoxLayout(self)
        # No margins, so the buttons line up with the header row the bar sits in.
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.prev_button)
        layout.addWidget(self.label, stretch=1)
        layout.addWidget(self.next_button)
        layout.addWidget(self.copy_button)

        self._update()

    @property
    def scramble(self) -> str:
        """The scramble currently shown."""
        return self.history.current

    def show_previous(self) -> None:
        """Go back to the previous scramble."""
        self.history.previous()
        self._update()

    def show_next(self) -> None:
        """Go to the next scramble, generating one if needed."""
        self.history.next()
        self._update()

    def show_new(self) -> None:
        """Jump to a freshly generated scramble (called after each solve)."""
        self.history.new()
        self._update()

    def copy(self) -> None:
        """Copy the current scramble to the clipboard and briefly confirm it."""
        QGuiApplication.clipboard().setText(self.scramble)
        self.copy_button.set_copied(copied=True)
        # Using the button as context cancels the reset if the button is deleted first.
        QTimer.singleShot(
            _COPIED_FEEDBACK_MS,
            self.copy_button,
            lambda: self.copy_button.set_copied(copied=False),
        )

    def _update(self) -> None:
        """Refresh the label and button states from the history."""
        self.label.setText(self.scramble)
        self.prev_button.setEnabled(self.history.can_go_back)
        # Emitted even if the text is the same: two consecutive trainer scrambles can
        # be identical, and listeners (e.g. hints) still need to reset.
        self.scramble_changed.emit(self.scramble)
