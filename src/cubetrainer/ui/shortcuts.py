"""The keyboard shortcuts reference: what each key does, and a dialog listing them.

The list isn't written by hand: pages record each shortcut as they register it
(see ``TimerPage._add_shortcut``) and the timer lists the keys it handles itself
(``TIMER_KEYS``), so the dialog always shows exactly what the app does.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True, slots=True)
class Shortcut:
    """A key and what it does.

    Attributes:
        keys: The key sequence in portable text form (e.g. ``"Ctrl+1"``), or a
            description of keys that isn't one (e.g. ``"Any key"``).
        action: What pressing it does.

    """

    keys: str
    action: str


#: Names shown instead of the platform's symbol, which is less familiar.
_KEY_NAMES: dict[str, str] = {"Esc": "Esc"}


def key_label(keys: str) -> str:
    """Show keys the way the platform writes them, e.g. ``"Ctrl+1"`` as ``"⌘1"``.

    Args:
        keys: Portable key sequence text, or a description like ``"Any key"``.

    Returns:
        The label: the platform's text for a key sequence, else ``keys`` itself.

    """
    if keys in _KEY_NAMES:
        return _KEY_NAMES[keys]
    native = QKeySequence(keys).toString(QKeySequence.SequenceFormat.NativeText)
    return native or keys


class ShortcutsDialog(QDialog):
    """Lists keyboard shortcuts in titled sections.

    Attributes:
        rows: The (key label, action) pairs shown, by section title.

    """

    def __init__(
        self,
        sections: Sequence[tuple[str, Sequence[Shortcut]]],
        parent: QWidget | None = None,
    ) -> None:
        """Create the dialog.

        Args:
            sections: (title, shortcuts) for each section, in order.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.setWindowTitle("Keyboard shortcuts")
        self.rows: dict[str, list[tuple[str, str]]] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        bold = QFont()
        bold.setBold(True)
        row = 0
        for title, shortcuts in sections:
            if row:
                grid.setRowMinimumHeight(row, 12)  # space between sections
                row += 1
            heading = QLabel(title)
            heading.setFont(bold)
            grid.addWidget(heading, row, 0, 1, 2)
            row += 1
            self.rows[title] = []
            for shortcut in shortcuts:
                label = key_label(shortcut.keys)
                self.rows[title].append((label, shortcut.action))
                key = QLabel(label)
                key.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                )
                grid.addWidget(key, row, 0)
                grid.addWidget(QLabel(shortcut.action), row, 1)
                row += 1
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        box = QVBoxLayout(self)
        box.addLayout(grid)
        box.addWidget(buttons)
