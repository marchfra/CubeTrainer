"""cstimer-style side panel: session summary on top, list of solves below."""

import math
from typing import override

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
    Signal,
)
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGridLayout,
    QHeaderView,
    QLabel,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from cubetrainer import stats
from cubetrainer.formatting import format_solve, format_value
from cubetrainer.solves import SolveList

#: Averages shown in the summary and as table columns.
AVERAGE_SIZES: tuple[int, ...] = (5, 12)

#: Table column headers.
COLUMNS: tuple[str, ...] = ("#", "time", *(f"ao{n}" for n in AVERAGE_SIZES))

type _AnyIndex = QModelIndex | QPersistentModelIndex


class SolvesTableModel(QAbstractTableModel):
    """Table of solves, newest first, with the rolling averages ending at each one."""

    def __init__(self, solves: SolveList) -> None:
        """Create the model.

        Args:
            solves: The solve list to display (not copied; call ``refresh`` after
                changing it).

        """
        super().__init__()
        self._solves: SolveList = solves
        self._averages: dict[int, list[float | None]] = {}
        self.refresh()

    def refresh(self) -> None:
        """Recompute the rolling averages and redraw the whole table."""
        self.beginResetModel()
        values = self._solves.values()
        self._averages = {n: stats.rolling_averages(values, n) for n in AVERAGE_SIZES}
        self.endResetModel()

    def solve_index(self, row: int) -> int:
        """Convert a table row to a position in the solve list.

        Args:
            row: Table row (0 is the newest solve).

        Returns:
            The index into the solve list (0 is the oldest solve).

        """
        return len(self._solves) - 1 - row

    @override
    def rowCount(self, parent: _AnyIndex | None = None) -> int:
        """Return the number of rows.

        Args:
            parent: Unused; the table is flat.

        Returns:
            The number of solves (0 for any valid parent).

        """
        if parent is not None and parent.isValid():
            return 0
        return len(self._solves)

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
    ) -> str | Qt.AlignmentFlag | None:
        """Return the text (or alignment) of a cell.

        Args:
            index: The cell.
            role: The requested data role.

        Returns:
            The cell text for the display role, right alignment for the alignment
            role, None otherwise.

        """
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        i = self.solve_index(index.row())
        column = index.column()
        if column == 0:
            return str(i + 1)
        if column == 1:
            return format_solve(self._solves.solves[i])
        return format_value(self._averages[AVERAGE_SIZES[column - 2]][i])

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


class SummaryPanel(QWidget):
    """Grid of current / best single and averages, plus the session mean.

    Attributes:
        cells: Value labels keyed by ``(row name, "current" | "best")``, where the row
            name is ``"time"`` or ``"ao5"``, ``"ao12"``...
        mean_label: Shows the solve count and the session mean.

    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Create the grid with empty values.

        Args:
            parent: Optional parent widget.

        """
        super().__init__(parent)
        grid = QGridLayout(self)
        bold = QFont()
        bold.setBold(True)
        for col, title in enumerate(("current", "best"), start=1):
            header = QLabel(title)
            header.setFont(bold)
            header.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(header, 0, col)

        self.cells: dict[tuple[str, str], QLabel] = {}
        row_names = ["time", *(f"ao{n}" for n in AVERAGE_SIZES)]
        for row, name in enumerate(row_names, start=1):
            grid.addWidget(QLabel(name), row, 0)
            for col, kind in enumerate(("current", "best"), start=1):
                cell = QLabel()
                cell.setAlignment(Qt.AlignmentFlag.AlignRight)
                grid.addWidget(cell, row, col)
                self.cells[name, kind] = cell

        self.mean_label: QLabel = QLabel()
        grid.addWidget(self.mean_label, len(row_names) + 1, 0, 1, 3)

    def update_from(self, solves: SolveList) -> None:
        """Recompute and show the statistics of ``solves``.

        Args:
            solves: The session's solves.

        """
        values = solves.values()
        self.cells["time", "current"].setText(
            format_value(values[-1] if values else None),
        )
        self.cells["time", "best"].setText(format_value(stats.best_single(values)))
        for n in AVERAGE_SIZES:
            current = stats.current_average(values, n)
            self.cells[f"ao{n}", "current"].setText(format_value(current))
            best = stats.best_average(values, n)
            self.cells[f"ao{n}", "best"].setText(format_value(best))
        finished = sum(1 for v in values if math.isfinite(v))
        mean = format_value(stats.mean_excluding_dnf(values))
        self.mean_label.setText(f"solves: {finished}/{len(values)}    mean: {mean}")


class SolvesPanel(QWidget):
    """Summary plus solves table, as in cstimer's left column.

    Attributes:
        solve_activated: Emitted with a solve-list index when a row is clicked.
        summary: The statistics grid.
        model: The table model.
        table: The table view.

    """

    solve_activated = Signal(int)

    def __init__(self, solves: SolveList, parent: QWidget | None = None) -> None:
        """Create the panel.

        Args:
            solves: The session's solves.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self._solves: SolveList = solves
        self.summary: SummaryPanel = SummaryPanel()
        self.model: SolvesTableModel = SolvesTableModel(solves)

        self.table: QTableView = QTableView()
        self.table.setModel(self.model)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.clicked.connect(self._on_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.summary)
        layout.addWidget(self.table, stretch=1)
        self.refresh()

    def refresh(self) -> None:
        """Redraw the summary and the table after the solve list changed."""
        self.model.refresh()
        self.summary.update_from(self._solves)

    def _on_clicked(self, index: QModelIndex) -> None:
        """Forward a row click as a solve index.

        Args:
            index: The clicked cell.

        """
        self.solve_activated.emit(self.model.solve_index(index.row()))
