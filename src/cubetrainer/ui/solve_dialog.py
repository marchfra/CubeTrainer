"""Dialog showing one solve's details, with penalty buttons and delete."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from cubetrainer.formatting import format_solve_detailed
from cubetrainer.solves import Penalty, Solve

#: Radio button label for each penalty.
PENALTY_LABELS: dict[Penalty, str] = {
    Penalty.OK: "OK",
    Penalty.PLUS_TWO: "+2",
    Penalty.DNF: "DNF",
}


class SolveDialog(QDialog):
    """Shows a solve; lets the user change its penalty or delete it.

    Penalty changes are written to the solve immediately, so the caller only needs to
    refresh its views once the dialog closes. The dialog's result is
    ``SolveDialog.DELETED`` if the solve should be deleted.

    Attributes:
        DELETED: Dialog result code meaning "delete this solve".
        time_label: Shows the time, including any penalty.
        penalty_buttons: Radio buttons keyed by penalty.
        delete_button: Closes the dialog asking for deletion.

    """

    DELETED: int = 2

    def __init__(
        self,
        solve: Solve,
        number: int,
        parent: QWidget | None = None,
    ) -> None:
        """Create the dialog.

        Args:
            solve: The solve to show (its penalty is updated in place).
            number: The solve's 1-based number in the session, for the title.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self._solve: Solve = solve
        self.setWindowTitle(f"Solve #{number}")

        self.time_label: QLabel = QLabel()
        font = QFont()
        font.setPointSize(28)
        self.time_label.setFont(font)

        local_time = solve.created_at.astimezone()
        date_label = QLabel(local_time.strftime("%Y-%m-%d %H:%M:%S"))
        scramble_label = QLabel(solve.scramble)
        scramble_label.setWordWrap(True)
        scramble_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )

        penalty_row = QHBoxLayout()
        group = QButtonGroup(self)
        self.penalty_buttons: dict[Penalty, QRadioButton] = {}
        for penalty, label in PENALTY_LABELS.items():
            button = QRadioButton(label)
            button.setChecked(penalty is solve.penalty)
            button.toggled.connect(
                lambda checked, p=penalty: self._on_penalty_toggled(p, checked=checked),
            )
            group.addButton(button)
            penalty_row.addWidget(button)
            self.penalty_buttons[penalty] = button
        penalty_row.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.delete_button: QPushButton = buttons.addButton(
            "Delete",
            QDialogButtonBox.ButtonRole.DestructiveRole,
        )
        self.delete_button.clicked.connect(lambda: self.done(self.DELETED))
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.time_label)
        layout.addWidget(date_label)
        layout.addWidget(scramble_label)
        layout.addLayout(penalty_row)
        layout.addWidget(buttons)
        self._update_time()

    def _on_penalty_toggled(self, penalty: Penalty, *, checked: bool) -> None:
        """Apply a penalty when its radio button becomes checked.

        Args:
            penalty: The penalty of the toggled button.
            checked: Whether the button is now checked.

        """
        if checked:
            self._solve.penalty = penalty
            self._update_time()

    def _update_time(self) -> None:
        """Show the solve's time with its current penalty."""
        self.time_label.setText(format_solve_detailed(self._solve))
