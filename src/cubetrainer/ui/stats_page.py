"""The Stats tab: a detailed summary of the solves of a chosen source.

A source is the full timer or one set's trainer; within it, one session or all of
them, and for trainers one case or all. Trainer statistics leave out solves marked
as mistakes, like the trainer's own tables.
"""

from dataclasses import dataclass
from typing import override

import shiboken6
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from cubetrainer import stats
from cubetrainer.cases.catalog import load_case_set
from cubetrainer.db import TIMER_KIND, Database, DbSessionStore, trainer_session_kind
from cubetrainer.formatting import format_average, format_percent, format_value
from cubetrainer.solves import Solve
from cubetrainer.ui.distribution_plots import HistogramPlot
from cubetrainer.ui.dropdown import Dropdown
from cubetrainer.ui.learn_page import AVAILABLE_SETS
from cubetrainer.ui.learning_plots import CaseCharts, LearningCurvePlot
from cubetrainer.ui.record_plots import RecordsPlot
from cubetrainer.ui.theme import FontRole, set_theme_font

#: Shown for an option that covers everything (sessions or cases).
ALL: str = "All"

#: Initial sub-X limit, in seconds.
DEFAULT_SUB_X: float = 20.0


@dataclass(frozen=True, slots=True)
class Source:
    """Where the Stats page takes its solves from.

    Attributes:
        kind: Session kind, e.g. ``"timer"`` or ``"trainer:pll"``.
        label: Display name, e.g. ``"Full timer"`` or ``"PLL trainer"``.
        set_id: The case set for trainers, None for the full timer.

    """

    kind: str
    label: str
    set_id: str | None = None


def all_sources() -> list[Source]:
    """List the full timer and every set's trainer.

    Returns:
        The sources, full timer first.

    """
    return [
        Source(TIMER_KIND, "Full timer"),
        *(
            Source(
                trainer_session_kind(set_id),
                f"{load_case_set(set_id).name} trainer",
                set_id,
            )
            for set_id in AVAILABLE_SETS
        ),
    ]


def load_solves(
    db: Database,
    source: Source,
    session_id: int | None,
    case_id: str | None,
    *,
    keep_mistakes: bool = False,
) -> list[Solve]:
    """Collect the solves a selection covers, oldest first.

    Args:
        db: The database.
        source: The full timer or a trainer.
        session_id: One session, or None for all of the source's sessions.
        case_id: For trainers, one case, or None for every case.
        keep_mistakes: Keep trainer solves marked as mistakes (for mistake rates).

    Returns:
        The solves (for trainers, without the ones marked as mistakes unless
        ``keep_mistakes``).

    """
    store = DbSessionStore(db, source.kind)
    ids = [s.id for s in store.sessions()] if session_id is None else [session_id]
    solves = [solve for sid in ids for solve in db.load_solves(sid)]
    solves.sort(key=lambda solve: solve.created_at)
    if source.set_id is not None:
        if not keep_mistakes:
            solves = [s for s in solves if not s.mistake]
        if case_id is not None:
            solves = [s for s in solves if s.case_id == case_id]
    return solves


#: Width a number field needs besides its text: padding, border and arrows.
_SPIN_EXTRA: int = 48

#: Item data meaning "all sessions" or "all cases" in a picker.
_ALL_DATA: str = ""

#: Characters a session or case picker is sized for (its items change, its width
#: doesn't).
_PICKER_CHARACTERS: int = 18

#: Characters the case picker is sized for (case names are short).
_CASE_CHARACTERS: int = 10


def _picker(tooltip: str) -> QComboBox:
    """Create a combo box that never takes keyboard focus (space times solves).

    Args:
        tooltip: Hover help text.

    Returns:
        The (empty) combo box.

    """
    picker = Dropdown()
    picker.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    picker.setToolTip(tooltip)
    return picker


def _refill(picker: QComboBox, items: list[tuple[str, str]], current: str) -> None:
    """Replace a picker's items and select one, without signalling a choice.

    Args:
        picker: The combo box.
        items: (text, data) for each item.
        current: Data of the item to select.

    """
    picker.blockSignals(True)  # noqa: FBT003 - Qt's positional flag
    picker.clear()
    for text, data in items:
        picker.addItem(text, data)
    picker.setCurrentIndex(max(picker.findData(current), 0))
    picker.blockSignals(False)  # noqa: FBT003 - Qt's positional flag


def _value_label() -> QLabel:
    """Create a right-aligned label for a number, with tabular digits.

    Returns:
        The label.

    """
    label = QLabel()
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    set_theme_font(label, FontRole.NUMBER, 13)
    return label


class StatsPage(QWidget):
    """Summary statistics of the selected solves.

    Attributes:
        source: The selected source.
        session_id: The selected session, or None for all sessions.
        case_id: The selected case (trainers only), or None for all cases.
        source_picker: Chooses the source.
        session_picker: Chooses the session, or all.
        case_picker: Chooses the case, or all (hidden for the full timer).
        sub_x: The limit for the sub-X rate, in seconds.
        overview: Value labels of the overview, keyed by row name.
        averages: Value labels of the averages, keyed by ``(n, "current" | "best")``.
        sub_x_label: The sub-X rate.
        histogram: Histogram of the times with the ex-Gaussian fit.
        fit_labels: Values of the ex-Gaussian fit, keyed by μ, σ, τ and D.
        records_plot: Personal-best progression.
        learning_curve: Times by solve number with the fitted trend and plateau.
        case_charts: For trainers, the slowest cases' times, mistakes and hints.

    """

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        """Create the page for the full timer's current session (drawn when shown).

        Args:
            db: The app database.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self._db: Database = db
        self._sources: list[Source] = all_sources()
        self.source: Source = self._sources[0]
        self.session_id: int | None = DbSessionStore(db, self.source.kind).current()
        self.case_id: str | None = None
        self._shown: tuple[object, ...] | None = None
        self._values: list[float] = []

        # Only the user's choices (``activated``) load anything: refilling the
        # pickers in code doesn't.
        self.source_picker: QComboBox = _picker("Full timer or a trainer")
        for source in self._sources:
            self.source_picker.addItem(source.label)
        self.source_picker.activated.connect(
            lambda index: self.select_source(self._sources[index]),
        )
        self.session_picker: QComboBox = _picker("One session or all")
        self.case_picker: QComboBox = _picker("One case or all")
        for picker, characters in (
            (self.session_picker, _PICKER_CHARACTERS),
            (self.case_picker, _CASE_CHARACTERS),
        ):
            picker.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon,
            )
            picker.setMinimumContentsLength(characters)
        self.session_picker.activated.connect(
            lambda index: self.select_session(
                int(data) if (data := self.session_picker.itemData(index)) else None,
            ),
        )
        self.case_picker.activated.connect(
            lambda index: self.select_case(self.case_picker.itemData(index) or None),
        )

        self.sub_x: QDoubleSpinBox = QDoubleSpinBox()
        self.sub_x.setRange(0.5, 600)
        self.sub_x.setDecimals(2)
        self.sub_x.setSingleStep(1)
        self.sub_x.setSuffix(" s")
        self.sub_x.setAlignment(Qt.AlignmentFlag.AlignRight)  # like the numbers
        # Room for "0000.00 s" plus the arrows, and no more.
        self.sub_x.setFixedWidth(
            self.sub_x.fontMetrics().horizontalAdvance("0000.00 s") + _SPIN_EXTRA,
        )
        self.sub_x.setValue(DEFAULT_SUB_X)
        self.sub_x.valueChanged.connect(self._update_sub_x)

        top = QHBoxLayout()
        for text, picker in (
            ("Source:", self.source_picker),
            ("Session:", self.session_picker),
            ("Case:", self.case_picker),
        ):
            label = QLabel(text)
            top.addWidget(label)
            top.addWidget(picker)
            if picker is self.case_picker:
                self._case_label = label
        top.addStretch()

        # Everything below the pickers scrolls: the page is taller than the window.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self._build_content())
        page = QVBoxLayout(self)
        page.addLayout(top)
        page.addWidget(scroll, stretch=1)
        # No refresh yet: the page fills in when it's first shown (see showEvent),
        # so the app doesn't compute and draw statistics for a tab nobody opened.

    def _build_content(self) -> QWidget:
        """Create everything below the pickers: the summary boxes, then the plots.

        Returns:
            The content widget.

        """
        content = QWidget()
        layout = QVBoxLayout(content)
        boxes = QHBoxLayout()
        boxes.addWidget(self._build_overview())
        boxes.addWidget(self._build_averages())
        boxes.addWidget(self._build_sub_x())
        boxes.addWidget(self._build_fit())
        boxes.addStretch()
        layout.addLayout(boxes)
        row = QHBoxLayout()
        self.histogram: HistogramPlot = HistogramPlot()
        row.addWidget(self.histogram)
        self.records_plot: RecordsPlot = RecordsPlot()
        row.addWidget(self.records_plot)
        layout.addLayout(row)
        self.learning_curve: LearningCurvePlot = LearningCurvePlot()
        layout.addWidget(self.learning_curve)
        self.case_charts: CaseCharts = CaseCharts()
        layout.addWidget(self.case_charts)
        layout.addStretch()
        return content

    def _build_overview(self) -> QGroupBox:
        """Create the overview box: counts, best, worst, mean, spread, percentiles.

        Returns:
            The box.

        """
        box = QGroupBox("Overview")
        grid = QGridLayout(box)
        self.overview: dict[str, QLabel] = {}
        rows = [
            "solves",
            "DNFs",
            "best",
            "worst",
            "mean",
            "median",
            "std dev",
            "variation (CV)",
            "10th percentile",
            "90th percentile",
        ]
        for row, name in enumerate(rows):
            grid.addWidget(QLabel(name), row, 0)
            self.overview[name] = _value_label()
            grid.addWidget(self.overview[name], row, 1)
        grid.setColumnMinimumWidth(1, 80)
        return box

    def _build_averages(self) -> QGroupBox:
        """Create the averages box: current and best ao5, ao12, ao50, ao100.

        Returns:
            The box.

        """
        box = QGroupBox("Averages")
        grid = QGridLayout(box)
        bold = QFont()
        bold.setBold(True)
        for col, title in enumerate(("current", "best"), start=1):
            header = QLabel(title)
            set_theme_font(header, FontRole.UI, 13, QFont.Weight.Bold)
            header.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(header, 0, col)
            grid.setColumnMinimumWidth(col, 80)
        self.averages: dict[tuple[int, str], QLabel] = {}
        for row, n in enumerate(stats.SUMMARY_AVERAGES, start=1):
            grid.addWidget(QLabel(f"ao{n}"), row, 0)
            for col, kind in enumerate(("current", "best"), start=1):
                label = _value_label()
                grid.addWidget(label, row, col)
                self.averages[n, kind] = label
        grid.setRowStretch(len(stats.SUMMARY_AVERAGES) + 1, 1)
        return box

    def _build_sub_x(self) -> QGroupBox:
        """Create the sub-X box: how many solves beat a chosen time.

        Returns:
            The box.

        """
        box = QGroupBox("Sub-X")
        grid = QGridLayout(box)
        grid.addWidget(QLabel("under"), 0, 0)
        grid.addWidget(self.sub_x, 0, 1)
        self.sub_x_label: QLabel = _value_label()
        grid.addWidget(self.sub_x_label, 1, 0, 1, 2)
        grid.setRowStretch(2, 1)
        return box

    def _build_fit(self) -> QGroupBox:
        """Create the fit box: the ex-Gaussian's parameters, explained.

        Returns:
            The box.

        """
        box = QGroupBox("Ex-Gaussian fit")
        grid = QGridLayout(box)
        self.fit_labels: dict[str, QLabel] = {}
        rows = [
            ("μ", "typical clean solve"),
            ("σ", "consistency of clean solves"),
            ("τ", "tail of bad solves"),
            ("D", "fit quality (smaller is better)"),
        ]
        for row, (symbol, meaning) in enumerate(rows):
            grid.addWidget(QLabel(symbol), row, 0)
            grid.addWidget(QLabel(meaning), row, 1)
            self.fit_labels[symbol] = _value_label()
            grid.addWidget(self.fit_labels[symbol], row, 2)
        grid.setColumnMinimumWidth(2, 60)
        grid.setRowStretch(len(rows), 1)
        box.setToolTip(
            "Solve times are modelled as a normal distribution (μ, σ) plus an "
            "exponential tail (τ). A high τ means occasional disasters cost you "
            "most; a high σ means every solve varies.",
        )
        return box

    def _show_case_charts(self) -> None:
        """Show which cases to drill, for a trainer source covering every case."""
        set_id = self.source.set_id
        shown = set_id is not None and self.case_id is None
        self.case_charts.setVisible(shown)
        if not shown or set_id is None:
            return
        names = {case.id: case.name for case in load_case_set(set_id).cases}
        solves = load_solves(
            self._db,
            self.source,
            self.session_id,
            None,
            keep_mistakes=True,
        )
        self.case_charts.set_solves(solves, lambda cid: names.get(cid, cid))

    def _show_fit(self) -> None:
        """Show the ex-Gaussian parameters of the plotted times."""
        fit = self.histogram.fit
        texts = (
            {"μ": "-", "σ": "-", "τ": "-", "D": "-"}
            if fit is None
            else {
                "μ": f"{fit.mu:.2f}",
                "σ": f"{fit.sigma:.2f}",
                "τ": f"{fit.tau:.2f}",
                "D": f"{fit.ks:.2f}",
            }
        )
        for symbol, text in texts.items():
            self.fit_labels[symbol].setText(text)

    def select_source(self, source: Source) -> None:
        """Show another source, starting from its current session and all cases.

        Args:
            source: The full timer or a trainer.

        """
        self.source = source
        self.session_id = DbSessionStore(self._db, source.kind).current()
        self.case_id = None
        self.refresh()

    def select_session(self, session_id: int | None) -> None:
        """Show one session of the source, or all of them.

        Args:
            session_id: The session, or None for all.

        """
        self.session_id = session_id
        self.refresh()

    def select_case(self, case_id: str | None) -> None:
        """Show one case of a trainer, or all of them.

        Args:
            case_id: The case, or None for all.

        """
        self.case_id = case_id
        self.refresh()

    def _refresh_if_open(self) -> None:
        """Refresh, unless the page was hidden or closed before this deferred call.

        A hidden page refreshes the next time it's shown anyway, and a closed one
        may be in the middle of being deleted.
        """
        if not shiboken6.isValid(self):
            return
        # Holding the window keeps it (and this page) from being garbage-collected
        # mid-refresh when nothing else refers to it any more.
        window = self.window()
        if window.isVisible() and self.isVisible():
            self.refresh()

    def refresh(self) -> None:
        """Reload the selected solves and show their statistics.

        Nothing is recomputed or redrawn when the selection and its solves are the
        same as last time, so reopening the tab after no changes is instant.
        """
        self._update_pickers()
        everything = load_solves(
            self._db,
            self.source,
            self.session_id,
            self.case_id,
            keep_mistakes=True,
        )
        key = (
            self.source,
            self.session_id,
            self.case_id,
            tuple((s.id, s.value, s.mistake) for s in everything),
        )
        if key != self._shown:
            self._shown = key
            trainer = self.source.set_id is not None
            solves = [s for s in everything if not (trainer and s.mistake)]
            self._show(solves)
        self._update_sub_x()

    def _show(self, solves: list[Solve]) -> None:
        """Compute and draw every statistic of some solves.

        Args:
            solves: The selected solves (for trainers, without mistakes).

        """
        values = [solve.value for solve in solves]
        self._values = values
        summary = stats.summarize(values)
        texts = {
            "solves": str(summary.count),
            "DNFs": str(summary.dnfs),
            "best": format_value(summary.best),
            "worst": format_value(summary.worst),
            "mean": format_average(summary.mean),
            "median": format_average(summary.median),
            "std dev": format_average(summary.std),
            "variation (CV)": format_percent(summary.cv) if summary.cv else "-",
            "10th percentile": format_average(summary.percentiles[10]),
            "90th percentile": format_average(summary.percentiles[90]),
        }
        for name, text in texts.items():
            self.overview[name].setText(text)
        for n, (current, best) in summary.averages.items():
            self.averages[n, "current"].setText(format_average(current))
            self.averages[n, "best"].setText(format_average(best))
        self.histogram.set_values(values)
        self.records_plot.set_solves(solves)
        self.learning_curve.set_values(values)
        self._show_case_charts()
        self._show_fit()

    def _update_sub_x(self) -> None:
        """Show the share of solves under the sub-X limit."""
        values = self._values
        rate = stats.sub_x_rate(values, self.sub_x.value() * 1000)
        if rate is None:
            self.sub_x_label.setText("-")
        else:
            under = round(rate * len(values))
            self.sub_x_label.setText(
                f"{format_percent(rate)}  ({under} of {len(values)})",
            )

    def _update_pickers(self) -> None:
        """Fill the pickers for the source and show the current selection."""
        self.source_picker.setCurrentIndex(self._sources.index(self.source))
        sessions = DbSessionStore(self._db, self.source.kind).sessions()
        _refill(
            self.session_picker,
            [(ALL, _ALL_DATA), *((s.name, str(s.id)) for s in sessions)],
            _ALL_DATA if self.session_id is None else str(self.session_id),
        )
        trainer = self.source.set_id is not None
        self.case_picker.setVisible(trainer)
        self._case_label.setVisible(trainer)
        if trainer and self.source.set_id is not None:
            cases = load_case_set(self.source.set_id).cases
            _refill(
                self.case_picker,
                [(ALL, _ALL_DATA), *((c.name, c.id) for c in cases)],
                self.case_id or _ALL_DATA,
            )

    @override
    def showEvent(self, event: QShowEvent) -> None:
        """Refresh each time the tab is shown: solves may have changed elsewhere.

        The refresh runs just after the tab appears, so switching to it never waits
        for the plots to be drawn.

        Args:
            event: The show event.

        """
        super().showEvent(event)
        QTimer.singleShot(0, self, self._refresh_if_open)
