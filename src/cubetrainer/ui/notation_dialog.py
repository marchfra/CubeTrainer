"""Dialog showing the move notation: every move with a picture, and the suffixes."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from cubetrainer.cube.move_render import render_move
from cubetrainer.cube.notation import MoveGroup, notation_entries, suffix_notes

#: Side of a move picture, in logical pixels.
PICTURE_SIZE: int = 84

#: Moves per row in each section.
COLUMNS: int = 3


def _heading(text: str) -> QLabel:
    """Create a section heading.

    Args:
        text: The heading.

    Returns:
        A bold label.

    """
    label = QLabel(text)
    font = QFont()
    font.setBold(True)
    font.setPointSize(15)
    label.setFont(font)
    return label


class NotationDialog(QDialog):
    """Every move the app understands, grouped by kind, with a picture of each.

    Attributes:
        moves: The move names shown, in order.
        pictures: The picture label of each move.

    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the dialog.

        Args:
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.setWindowTitle("Notation")
        self.moves: list[str] = []
        self.pictures: dict[str, QLabel] = {}

        content = QWidget()
        box = QVBoxLayout(content)
        box.addWidget(_heading("Writing moves"))
        suffixes = QGridLayout()
        suffixes.setHorizontalSpacing(24)
        for row, (example, meaning) in enumerate(suffix_notes()):
            suffixes.addWidget(QLabel(example), row, 0)
            suffixes.addWidget(QLabel(meaning), row, 1)
        suffixes.setColumnStretch(1, 1)
        box.addLayout(suffixes)
        box.addWidget(
            QLabel(
                "Pictures show the cube with yellow on top and green in front;"
                " the coloured layers turn, the arrows show which way.",
            ),
        )

        entries = notation_entries()
        for group in MoveGroup:
            box.addSpacing(10)
            box.addWidget(_heading(group.value))
            grid = QGridLayout()
            grid.setHorizontalSpacing(18)
            members = [entry for entry in entries if entry.group is group]
            for i, entry in enumerate(members):
                grid.addWidget(
                    self._move_cell(entry.base, entry.description),
                    i // COLUMNS,
                    i % COLUMNS,
                )
            box.addLayout(grid)
        box.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        # Wide enough for the content: it only scrolls vertically.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(
            content.sizeHint().width()
            + scroll.verticalScrollBar().sizeHint().width()
            + 2 * scroll.frameWidth(),
        )
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addWidget(buttons)
        self.resize(self.sizeHint().width(), 720)

    def _move_cell(self, base: str, description: str) -> QWidget:
        """Create one move's cell: picture, name and description.

        Args:
            base: The move.
            description: What it does.

        Returns:
            The cell.

        """
        ratio = self.devicePixelRatioF()
        image = render_move(base, round(PICTURE_SIZE * ratio))
        image.setDevicePixelRatio(ratio)  # sharp on high-density screens
        picture = QLabel()
        picture.setPixmap(QPixmap.fromImage(image))
        picture.setFixedSize(PICTURE_SIZE, PICTURE_SIZE)
        name = QLabel(base)
        font = QFont()
        font.setBold(True)
        font.setPointSize(20)
        name.setFont(font)
        text = QLabel(description)
        text.setWordWrap(True)
        text.setFixedWidth(170)
        words = QVBoxLayout()
        words.addWidget(name)
        words.addWidget(text)
        words.addStretch()
        cell = QWidget()
        row = QHBoxLayout(cell)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(picture)
        row.addLayout(words)
        self.moves.append(base)
        self.pictures[base] = picture
        return cell
