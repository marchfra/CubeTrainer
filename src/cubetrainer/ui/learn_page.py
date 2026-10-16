"""The Learn tab: jperm-style list of a set's cases with their learning status."""

from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QMouseEvent, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from cubetrainer import stats
from cubetrainer.cases.catalog import Case, CaseSet, CaseStatus, load_case_set
from cubetrainer.db import Database, trainer_session_kind
from cubetrainer.formatting import format_average, format_value
from cubetrainer.ui.case_images import case_pixmap

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

_COLUMN_TITLES: tuple[str, ...] = ("Case", "Name", "Algorithm", "Group", "Best", "Avg")


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
        self.setPixmap(case_pixmap(case, IMAGE_SIZE))
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
    """Grid of one set's cases: image, name, algorithm, group, best and mean time.

    The times come from the set's trainer solves, leaving out mistakes.

    Attributes:
        case_set: The set shown.
        statuses: Current status of every case, keyed by case id.
        images: The clickable image of every case, keyed by case id.
        best_labels: Best trainer time of every case, keyed by case id.
        mean_labels: Mean trainer time of every case, keyed by case id.

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
        self.best_labels: dict[str, QLabel] = {}
        self.mean_labels: dict[str, QLabel] = {}

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
            for col, labels in ((4, self.best_labels), (5, self.mean_labels)):
                label = QLabel()
                label.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                )
                grid.addWidget(label, row, col)
                labels[case.id] = label
        grid.setColumnStretch(2, 1)
        self.refresh_times()

    def refresh_times(self) -> None:
        """Reload the trainer solves and show each case's best and mean time."""
        session = self._db.get_or_create_session(trainer_session_kind(self.case_set.id))
        by_case = stats.case_stats(self._db.load_solves(session))
        for case in self.case_set.cases:
            case_stats = by_case.get(case.id)
            best = case_stats.best if case_stats else None
            mean = case_stats.mean if case_stats else None
            self.best_labels[case.id].setText(format_value(best))
            self.mean_labels[case.id].setText(format_average(mean))

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
    """Set picker and Train button above a scrollable case list.

    Attributes:
        train_requested: Emitted with a set id when the user wants to train it.
        set_picker: Button showing the current set; clicking it opens ``set_menu``.
        set_menu: Menu choosing which set to show.
        train_button: Starts the trainer for the selected set.
        case_list: The list for the selected set.

    """

    train_requested = Signal(str)

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        """Create the page showing the first available set.

        Args:
            db: The app database.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self._db: Database = db
        # A plain push button that pops up a menu, rather than a combo box or a
        # push button with an attached menu: macOS draws those 1-2 px higher than a
        # plain push button, so next to the Train button they look misaligned.
        self.set_picker: QPushButton = QPushButton()
        self.set_picker.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.set_menu: QMenu = QMenu(self.set_picker)
        for set_id in AVAILABLE_SETS:
            self.set_menu.addAction(
                load_case_set(set_id).name,
                lambda sid=set_id: self.select_set(sid),
            )
        self.set_picker.clicked.connect(self._pop_up_set_menu)
        self.train_button: QPushButton = QPushButton()
        self.train_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.train_button.clicked.connect(
            lambda: self.train_requested.emit(self.case_list.case_set.id),
        )

        self._scroll: QScrollArea = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        top = QHBoxLayout()
        top.addWidget(QLabel("Set:"))
        top.addWidget(self.set_picker)
        top.addWidget(self.train_button)
        top.addStretch()
        hint = QLabel("Click a case image to cycle unlearned → learning → finished")
        top.addWidget(hint)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self._scroll, stretch=1)

        self.case_list: CaseList = CaseList(load_case_set(AVAILABLE_SETS[0]), db)
        self._show_case_list(self.case_list)

    def _pop_up_set_menu(self) -> None:
        """Show the set menu just below the picker."""
        self.set_menu.popup(
            self.set_picker.mapToGlobal(self.set_picker.rect().bottomLeft()),
        )

    @override
    def showEvent(self, event: QShowEvent) -> None:
        """Refresh the trainer times each time the page is shown.

        Args:
            event: The show event.

        """
        super().showEvent(event)
        self.case_list.refresh_times()

    def select_set(self, set_id: str) -> None:
        """Show the cases of another set.

        Args:
            set_id: The set to show, e.g. ``"pll"``.

        """
        self._show_case_list(CaseList(load_case_set(set_id), self._db))

    def _show_case_list(self, case_list: CaseList) -> None:
        """Display a case list and label the picker and Train button for its set.

        Args:
            case_list: The list to show.

        """
        self.case_list = case_list
        self._scroll.setWidget(case_list)
        self.set_picker.setText(f"{case_list.case_set.name}  ▾")
        self.train_button.setText(f"Train {case_list.case_set.name}")
