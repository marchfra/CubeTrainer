"""The Learn tab: jperm-style list of a set's cases with their learning status."""

from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from cubetrainer.cases.catalog import Case, CaseSet, CaseStatus, load_case_set
from cubetrainer.cube.render import render_last_layer
from cubetrainer.db import Database

#: Case sets offered in the set picker, by id.
AVAILABLE_SETS: tuple[str, ...] = ("pll",)

#: Background colour behind a case image for each status ("" means none).
STATUS_COLORS: dict[CaseStatus, str] = {
    CaseStatus.UNLEARNED: "",
    CaseStatus.LEARNING: "#e8a33d",
    CaseStatus.FINISHED: "#3fa45b",
}

#: Displayed size of case images, in logical pixels.
IMAGE_SIZE: int = 96

#: Images are rendered at this multiple of their size so they stay sharp on Retina.
_RENDER_SCALE: int = 2

_COLUMN_TITLES: tuple[str, ...] = ("Case", "Name", "Algorithm", "Group")


class CaseImage(QLabel):
    """A case's image that cycles the case's status when clicked.

    The status shows as the background colour, and is named in the tooltip.

    Attributes:
        clicked: Emitted when the image is clicked with the left button.

    """

    clicked = Signal()

    def __init__(self, case: Case, status: CaseStatus) -> None:
        """Render the image and show the initial status.

        Args:
            case: The case to draw.
            status: Its current status.

        """
        super().__init__()
        image = render_last_layer(case.state(), IMAGE_SIZE * _RENDER_SCALE)
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(_RENDER_SCALE)
        self.setPixmap(pixmap)
        self.setFixedSize(IMAGE_SIZE + 12, IMAGE_SIZE + 12)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName(f"caseImage_{case.id}")
        self.show_status(status)

    def show_status(self, status: CaseStatus) -> None:
        """Colour the background and update the tooltip for a status.

        Args:
            status: The status to show.

        """
        color = STATUS_COLORS[status]
        # Scope the rule to this widget by object name: an unscoped style sheet would
        # also colour the tooltip, which inherits the widget's style.
        self.setStyleSheet(
            f"#{self.objectName()} {{ background-color: {color}; border-radius: 8px; }}"
            if color
            else "",
        )
        self.setToolTip(f"Status: {status.value} (click to change)")

    @override
    def mousePressEvent(self, ev: QMouseEvent) -> None:
        """Emit ``clicked`` on a left click.

        Args:
            ev: The mouse event.

        """
        if ev.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        else:
            super().mousePressEvent(ev)


class CaseList(QWidget):
    """Grid of one set's cases: image (with status), name, algorithm and group.

    Attributes:
        case_set: The set shown.
        statuses: Current status of every case, keyed by case id.
        images: The clickable image of every case, keyed by case id.

    """

    def __init__(self, case_set: CaseSet, db: Database) -> None:
        """Build the grid.

        Args:
            case_set: The set to show.
            db: Database holding the cases' statuses.

        """
        super().__init__()
        self.case_set: CaseSet = case_set
        self._db: Database = db
        stored = db.load_case_statuses(case_set.id)
        self.statuses: dict[str, CaseStatus] = {
            case.id: stored.get(case.id, CaseStatus.UNLEARNED)
            for case in case_set.cases
        }
        self.images: dict[str, CaseImage] = {}

        grid = QGridLayout(self)
        grid.setHorizontalSpacing(24)
        bold = QFont()
        bold.setBold(True)
        for col, title in enumerate(_COLUMN_TITLES):
            header = QLabel(title)
            header.setFont(bold)
            grid.addWidget(header, 0, col)

        alg_font = QFont()
        alg_font.setPointSize(15)
        for row, case in enumerate(case_set.cases, start=1):
            image = CaseImage(case, self.statuses[case.id])
            image.clicked.connect(lambda cid=case.id: self.cycle_status(cid))
            self.images[case.id] = image
            grid.addWidget(image, row, 0)

            name = QLabel(case.name)
            name.setFont(bold)
            grid.addWidget(name, row, 1)
            alg = QLabel(case.alg)
            alg.setFont(alg_font)
            alg.setWordWrap(True)
            alg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(alg, row, 2)
            grid.addWidget(QLabel(case.group), row, 3)
        grid.setColumnStretch(2, 1)

    def cycle_status(self, case_id: str) -> None:
        """Advance a case to its next status, show it and save it.

        Args:
            case_id: The clicked case.

        """
        status = self.statuses[case_id].next()
        self.statuses[case_id] = status
        self.images[case_id].show_status(status)
        self._db.set_case_status(self.case_set.id, case_id, status)


class LearnPage(QWidget):
    """Set picker above a scrollable case list.

    Attributes:
        set_picker: Chooses which case set to show.
        case_list: The list for the selected set.

    """

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        """Create the page showing the first available set.

        Args:
            db: The app database.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self._db: Database = db
        self.set_picker: QComboBox = QComboBox()
        for set_id in AVAILABLE_SETS:
            self.set_picker.addItem(load_case_set(set_id).name, set_id)
        self.set_picker.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.set_picker.currentIndexChanged.connect(self._show_selected_set)

        self._scroll: QScrollArea = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        top = QHBoxLayout()
        top.addWidget(QLabel("Set:"))
        top.addWidget(self.set_picker)
        top.addStretch()
        hint = QLabel("Click a case image to cycle unlearned → learning → finished")
        top.addWidget(hint)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self._scroll, stretch=1)

        self.case_list: CaseList = CaseList(load_case_set(AVAILABLE_SETS[0]), db)
        self._scroll.setWidget(self.case_list)

    def _show_selected_set(self, index: int) -> None:
        """Replace the case list with the set chosen in the picker.

        Args:
            index: Index of the chosen set in the picker.

        """
        self.case_list = CaseList(
            load_case_set(self.set_picker.itemData(index)),
            self._db,
        )
        self._scroll.setWidget(self.case_list)
