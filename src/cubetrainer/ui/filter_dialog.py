"""Dialog choosing which cases the trainer picks, and how likely each one is."""

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from cubetrainer.cases.catalog import CaseSet, CaseStatus
from cubetrainer.cases.filters import RECENT_SOLVES, CaseFilter, Odds

_PROBABILITY_HELP: str = (
    "Realistic: each case comes up as often as in real solves (in PLL, H, Na and Nb"
    " are 4 times rarer than most cases, E and Z twice as rare).\n"
    "Slowest first: slow cases come up more often, by the square of their mean time"
    f" over their last {RECENT_SOLVES} solves, more if you often mark them as"
    " mistakes; cases with fewer than 3 timed solves count as the slowest."
)


class FilterDialog(QDialog):
    """Edits a ``CaseFilter``, showing how many cases it selects.

    Attributes:
        group_boxes: A checkbox per group of the set, keyed by group.
        status_boxes: A checkbox per learning status.
        odds_buttons: A radio button per way of weighting the cases.
        count_label: Says how many cases the filter selects.
        ok_button: Accepts the filter (disabled while it selects nothing).

    """

    def __init__(
        self,
        case_set: CaseSet,
        statuses: dict[str, CaseStatus],
        case_filter: CaseFilter,
        parent: QWidget | None = None,
    ) -> None:
        """Create the dialog showing an existing filter.

        Args:
            case_set: The set being trained.
            statuses: Learning status by case id, to count the matching cases.
            case_filter: The filter to start from.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.setWindowTitle(f"{case_set.name} cases to train")
        self._case_set: CaseSet = case_set
        self._statuses: dict[str, CaseStatus] = statuses

        groups_box = QGroupBox("Groups")
        groups_layout = QVBoxLayout(groups_box)
        self.group_boxes: dict[str, QCheckBox] = {}
        for group in case_set.groups:
            box = QCheckBox(group)
            box.setChecked(case_filter.groups is None or group in case_filter.groups)
            box.toggled.connect(self._update_count)
            groups_layout.addWidget(box)
            self.group_boxes[group] = box
        select_row = QHBoxLayout()
        for label, checked in (("All", True), ("None", False)):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, c=checked: self._set_groups(c))
            select_row.addWidget(button)
        select_row.addStretch()
        groups_layout.addLayout(select_row)

        status_box = QGroupBox("Status")
        status_layout = QHBoxLayout(status_box)
        self.status_boxes: dict[CaseStatus, QCheckBox] = {}
        for status in CaseStatus:
            box = QCheckBox(status.value)
            box.setChecked(status in case_filter.statuses)
            box.toggled.connect(self._update_count)
            status_layout.addWidget(box)
            self.status_boxes[status] = box

        probability_box = QGroupBox("Probability")
        probability_box.setToolTip(_PROBABILITY_HELP)
        probability_layout = QHBoxLayout(probability_box)
        self.odds_buttons: dict[Odds, QRadioButton] = {}
        for odds in Odds:
            button = QRadioButton(odds.value.capitalize())
            button.setChecked(odds is case_filter.odds)
            probability_layout.addWidget(button)
            self.odds_buttons[odds] = button
        probability_layout.addStretch()

        self.count_label: QLabel = QLabel()
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok_button is not None  # noqa: S101 - requested just above
        self.ok_button: QPushButton = ok_button
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(groups_box)
        layout.addWidget(status_box)
        layout.addWidget(probability_box)
        layout.addWidget(self.count_label)
        layout.addWidget(buttons)
        self._update_count()

    def case_filter(self) -> CaseFilter:
        """Return the filter currently described by the controls.

        Returns:
            The filter; ``groups`` is None when every group is ticked.

        """
        groups = frozenset(g for g, box in self.group_boxes.items() if box.isChecked())
        return CaseFilter(
            groups=None if len(groups) == len(self.group_boxes) else groups,
            statuses=frozenset(
                s for s, box in self.status_boxes.items() if box.isChecked()
            ),
            odds=next(o for o, b in self.odds_buttons.items() if b.isChecked()),
        )

    def _set_groups(self, checked: bool) -> None:  # noqa: FBT001
        """Tick or untick every group.

        Args:
            checked: Whether to tick them (passed positionally by the buttons).

        """
        for box in self.group_boxes.values():
            box.setChecked(checked)

    def _update_count(self) -> None:
        """Show how many cases the filter selects; forbid selecting none."""
        count = len(self.case_filter().matching(self._case_set, self._statuses))
        total = len(self._case_set.cases)
        self.count_label.setText(f"{count} of {total} cases selected")
        self.ok_button.setEnabled(count > 0)
