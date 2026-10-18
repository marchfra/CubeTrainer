"""cstimer-style side panel: session summary on top, list of solves below."""

import math
from collections.abc import Callable
from dataclasses import dataclass
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
from cubetrainer.formatting import (
    format_average,
    format_flags,
    format_solve,
    format_value,
)
from cubetrainer.solves import SolveList
from cubetrainer.ui.theme import FontRole, set_theme_font


@dataclass(frozen=True, slots=True)
class PanelLayout:
    """What the solves panel shows.

    Attributes:
        average_sizes: Averages shown in the summary and as table columns.
        trainer: Whether this is a trainer table: adds case and flag columns, and
            leaves mistakes out of the summary's best and mean.

    """

    average_sizes: tuple[int, ...] = (5, 12)
    trainer: bool = False

    @property
    def columns(self) -> tuple[str, ...]:
        """The table column headers, in order."""
        extra = ("case", "flags") if self.trainer else ()
        return ("#", "time", *extra, *(f"ao{n}" for n in self.average_sizes))


#: Layout of the full-solve timer: ao5 and ao12.
TIMER_LAYOUT: PanelLayout = PanelLayout()

#: Layout of the trainer: case and flags columns; averages across different cases mean
#: little.
TRAINER_LAYOUT: PanelLayout = PanelLayout(average_sizes=(), trainer=True)

type _AnyIndex = QModelIndex | QPersistentModelIndex


class SolvesTableModel(QAbstractTableModel):
    """Table of solves, newest first, with the rolling averages ending at each one."""

    def __init__(
        self,
        solves: SolveList,
        layout: PanelLayout = TIMER_LAYOUT,
        case_name: Callable[[str], str] = str,
    ) -> None:
        """Create the model.

        Args:
            solves: The solve list to display (not copied; call ``refresh`` after
                changing it).
            layout: Which columns to show.
            case_name: Display name of a case id, for the case column.

        """
        super().__init__()
        self._solves: SolveList = solves
        self._layout: PanelLayout = layout
        self._case_name: Callable[[str], str] = case_name
        self._averages: dict[int, list[float | None]] = {}
        self.refresh()

    def refresh(self) -> None:
        """Recompute the rolling averages and redraw the whole table."""
        self.beginResetModel()
        values = self._solves.values()
        self._averages = {
            n: stats.rolling_averages(values, n) for n in self._layout.average_sizes
        }
        self.endResetModel()

    def set_solves(self, solves: SolveList) -> None:
        """Show another solve list (e.g. after switching session).

        Args:
            solves: The new list.

        """
        self._solves = solves
        self.refresh()

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
        return len(self._layout.columns)

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
        return self._cell_text(index.row(), self._layout.columns[index.column()])

    def _cell_text(self, row: int, header: str) -> str:
        """Return the text of one cell.

        Args:
            row: Table row (0 is the newest solve).
            header: The cell's column header.

        Returns:
            The text to display.

        """
        i = self.solve_index(row)
        solve = self._solves.solves[i]
        texts: dict[str, Callable[[], str]] = {
            "#": lambda: str(i + 1),
            "time": lambda: format_solve(solve),
            "case": lambda: self._case_name(solve.case_id) if solve.case_id else "",
            "flags": lambda: format_flags(solve),
        }
        if header in texts:
            return texts[header]()
        return format_average(self._averages[int(header.removeprefix("ao"))][i])

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
            return self._layout.columns[section]
        return None


class SummaryPanel(QWidget):
    """Grid of current / best single and averages, plus the session mean.

    Attributes:
        cells: Value labels keyed by ``(row name, "current" | "best")``, where the row
            name is ``"time"`` or ``"ao5"``, ``"ao12"``...
        mean_label: Shows the solve count and the session mean.

    """

    def __init__(
        self,
        layout: PanelLayout = TIMER_LAYOUT,
        parent: QWidget | None = None,
    ) -> None:
        """Create the grid with empty values.

        Args:
            layout: Which averages to show (a row each, below the single time), and
                whether to leave mistakes out (trainer).
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self._average_sizes: tuple[int, ...] = layout.average_sizes
        self._trainer: bool = layout.trainer
        # A card (see the theme): muted labels, times in the fixed-width font, the
        # best ones in the accent colour.
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        grid = QGridLayout(self)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setVerticalSpacing(6)
        for col, title in enumerate(("current", "best"), start=1):
            header = QLabel(title)
            header.setObjectName("muted")
            header.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(header, 0, col)

        self.cells: dict[tuple[str, str], QLabel] = {}
        row_names = ["time", *(f"ao{n}" for n in self._average_sizes)]
        for row, name in enumerate(row_names, start=1):
            label = QLabel(name)
            label.setObjectName("muted")
            grid.addWidget(label, row, 0)
            for col, kind in enumerate(("current", "best"), start=1):
                cell = QLabel()
                cell.setAlignment(Qt.AlignmentFlag.AlignRight)
                set_theme_font(cell, FontRole.NUMBER, 16, QFont.Weight.Medium)
                cell.setObjectName("best" if kind == "best" else "")
                grid.addWidget(cell, row, col)
                self.cells[name, kind] = cell

        self.mean_label: QLabel = QLabel()
        self.mean_label.setObjectName("muted")
        grid.addWidget(self.mean_label, len(row_names) + 1, 0, 1, 3)

    def update_from(self, solves: SolveList) -> None:
        """Recompute and show the statistics of ``solves``.

        Args:
            solves: The session's solves.

        """
        all_values = solves.values()
        self.cells["time", "current"].setText(
            format_value(all_values[-1] if all_values else None),
        )
        values = stats.clean_values(solves.solves) if self._trainer else all_values
        self.cells["time", "best"].setText(format_value(stats.best_single(values)))
        for n in self._average_sizes:
            current = stats.current_average(values, n)
            self.cells[f"ao{n}", "current"].setText(format_average(current))
            best = stats.best_average(values, n)
            self.cells[f"ao{n}", "best"].setText(format_average(best))
        finished = sum(1 for v in all_values if math.isfinite(v))
        mean = format_average(stats.mean_excluding_dnf(values))
        text = f"solves: {finished}/{len(all_values)}    mean: {mean}"
        if self._trainer:
            mistakes = sum(s.mistake for s in solves.solves)
            text += f"    mistakes: {mistakes}"
        self.mean_label.setText(text)


class SolvesPanel(QWidget):
    """Summary plus solves table, as in cstimer's left column.

    Attributes:
        solve_activated: Emitted with a solve-list index when a row is clicked.
        summary: The statistics grid.
        model: The table model.
        table: The table view.

    """

    solve_activated = Signal(int)

    def __init__(
        self,
        solves: SolveList,
        layout: PanelLayout = TIMER_LAYOUT,
        case_name: Callable[[str], str] = str,
        parent: QWidget | None = None,
        *,
        embed: bool = True,
    ) -> None:
        """Create the panel.

        Args:
            solves: The session's solves.
            layout: Which statistics and columns to show.
            case_name: Display name of a case id, for the case column.
            parent: Optional parent widget.
            embed: Lay the summary and table out in the panel. False leaves them
                for the caller to place (e.g. in a grid that lines the table up
                with another one); the panel then still updates them.

        """
        super().__init__(parent)
        self._solves: SolveList = solves
        self.summary: SummaryPanel = SummaryPanel(layout)
        self.model: SolvesTableModel = SolvesTableModel(solves, layout, case_name)

        self.table: QTableView = QTableView()
        self.table.setShowGrid(False)  # row dividers come from the theme
        self.table.setModel(self.model)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch,
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.clicked.connect(self._on_clicked)

        if embed:
            box = QVBoxLayout(self)
            box.setContentsMargins(0, 0, 0, 0)
            box.addWidget(self.summary)
            box.addWidget(self.table, stretch=1)
        self.refresh()

    def refresh(self) -> None:
        """Redraw the summary and the table after the solve list changed."""
        self.model.refresh()
        self.summary.update_from(self._solves)

    def set_solves(self, solves: SolveList) -> None:
        """Show another solve list (e.g. after switching session).

        Args:
            solves: The new list.

        """
        self._solves = solves
        self.model.set_solves(solves)
        self.summary.update_from(solves)

    def _on_clicked(self, index: QModelIndex) -> None:
        """Forward a row click as a solve index.

        Args:
            index: The clicked cell.

        """
        self.solve_activated.emit(self.model.solve_index(index.row()))
