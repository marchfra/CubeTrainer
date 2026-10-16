"""Trainer table with one row of statistics per case, sortable by any column."""

from collections.abc import Callable
from typing import override

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from cubetrainer import stats
from cubetrainer.cases.catalog import CaseSet
from cubetrainer.formatting import format_average, format_percent, format_value
from cubetrainer.solves import SolveList
from cubetrainer.stats import CASE_AVERAGE_SIZE, CaseStats

#: Column headers.
COLUMNS: tuple[str, ...] = (
    "case",
    "n",
    "best",
    "avg",
    f"ao{CASE_AVERAGE_SIZE}",
    "err%",
    "hint%",
)

#: Role holding the value a column sorts by (numbers, not their text).
SORT_ROLE: int = Qt.ItemDataRole.UserRole

type _AnyIndex = QModelIndex | QPersistentModelIndex
type _Cell = tuple[str, float]


def _time_cell(value: float | None, text: Callable[[float | None], str]) -> _Cell:
    """Build the text and sort key of a time cell; missing values sort last.

    Args:
        value: Milliseconds, ``math.inf`` for DNF, or None.
        text: Formats the value.

    Returns:
        The display text and the sort key.

    """
    return text(value), float("inf") if value is None else value


class CaseStatsModel(QAbstractTableModel):
    """One row per case that has solves, in the set's order."""

    def __init__(self, case_set: CaseSet, solves: SolveList) -> None:
        """Create the model.

        Args:
            case_set: The set being trained (gives case order and names).
            solves: The trainer session's solves (call ``refresh`` after changes).

        """
        super().__init__()
        self._case_set: CaseSet = case_set
        self._solves: SolveList = solves
        self._rows: list[tuple[_Cell, ...]] = []
        self.refresh()

    def refresh(self) -> None:
        """Recompute every case's statistics and redraw the table."""
        self.beginResetModel()
        by_case = stats.case_stats(self._solves.solves)
        self._rows = [
            self._row(position, case.name, by_case[case.id])
            for position, case in enumerate(self._case_set.cases)
            if case.id in by_case
        ]
        self.endResetModel()

    def set_solves(self, solves: SolveList) -> None:
        """Use another solve list.

        Args:
            solves: The new list.

        """
        self._solves = solves
        self.refresh()

    @staticmethod
    def _row(position: int, name: str, case: CaseStats) -> tuple[_Cell, ...]:
        """Build the cells of one case's row.

        Args:
            position: The case's position in its set (the case column sorts by it).
            name: The case name.
            case: The case's statistics.

        Returns:
            One (text, sort key) pair per column.

        """
        return (
            (name, float(position)),
            (str(case.count), float(case.count)),
            _time_cell(case.best, format_value),
            _time_cell(case.mean, format_average),
            _time_cell(case.current_average, format_average),
            (format_percent(case.mistake_rate), case.mistake_rate),
            (format_percent(case.hint_rate), case.hint_rate),
        )

    @override
    def rowCount(self, parent: _AnyIndex | None = None) -> int:
        """Return the number of rows.

        Args:
            parent: Unused; the table is flat.

        Returns:
            The number of cases with solves (0 for any valid parent).

        """
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    @override
    def columnCount(self, parent: _AnyIndex | None = None) -> int:
        """Return the number of columns.

        Args:
            parent: Unused; the table is flat.

        Returns:
            The number of columns (0 for any valid parent).

        """
        if parent is not None and parent.isValid():
            return 0
        return len(COLUMNS)

    @override
    def data(
        self,
        index: _AnyIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | float | Qt.AlignmentFlag | None:
        """Return a cell's text, sort key or alignment.

        Args:
            index: The cell.
            role: The requested data role.

        Returns:
            The text for the display role, the sort key for ``SORT_ROLE``, the
            alignment for the alignment role, None otherwise.

        """
        if not index.isValid():
            return None
        text, key = self._rows[index.row()][index.column()]
        if role == Qt.ItemDataRole.DisplayRole:
            return text
        if role == SORT_ROLE:
            return key
        if role == Qt.ItemDataRole.TextAlignmentRole:
            horizontal = (
                Qt.AlignmentFlag.AlignLeft
                if index.column() == 0
                else Qt.AlignmentFlag.AlignRight
            )
            return horizontal | Qt.AlignmentFlag.AlignVCenter
        return None

    @override
    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> str | None:
        """Return the column titles.

        Args:
            section: Column (or row) number.
            orientation: Header orientation.
            role: The requested data role.

        Returns:
            The column title for horizontal display-role requests, else None.

        """
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return COLUMNS[section]
        return None


class CaseStatsPanel(QWidget):
    """Title plus the sortable per-case table.

    Attributes:
        model: The per-case statistics.
        proxy: Sorts the model by the numeric sort keys.
        table: The table view.

    """

    def __init__(
        self,
        case_set: CaseSet,
        solves: SolveList,
        parent: QWidget | None = None,
    ) -> None:
        """Create the panel.

        Args:
            case_set: The set being trained.
            solves: The trainer session's solves.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.model: CaseStatsModel = CaseStatsModel(case_set, solves)
        self.proxy: QSortFilterProxyModel = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)

        self.table: QTableView = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        note = QLabel("Per case (best / avg / ao5 leave out mistakes)")
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(note)
        box.addWidget(self.table, stretch=1)

    def refresh(self) -> None:
        """Recompute the statistics after the solves changed."""
        self.model.refresh()

    def set_solves(self, solves: SolveList) -> None:
        """Show the statistics of another solve list (e.g. after switching session).

        Args:
            solves: The new list.

        """
        self.model.set_solves(solves)
