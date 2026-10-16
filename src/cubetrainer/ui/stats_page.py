"""The Stats tab: a detailed summary of the solves of a chosen source.

A source is the full timer or one set's trainer; within it, one session or all of
them, and for trainers one case or all. Trainer statistics leave out solves marked
as mistakes, like the trainer's own tables.
"""

from dataclasses import dataclass
from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QShowEvent
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from cubetrainer import stats
from cubetrainer.cases.catalog import load_case_set
from cubetrainer.db import TIMER_KIND, Database, DbSessionStore, trainer_session_kind
from cubetrainer.formatting import format_average, format_percent, format_value
from cubetrainer.solves import Solve
from cubetrainer.ui.learn_page import AVAILABLE_SETS
from cubetrainer.ui.sizing import reserve_width

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
) -> list[Solve]:
    """Collect the solves a selection covers, oldest first.

    Args:
        db: The database.
        source: The full timer or a trainer.
        session_id: One session, or None for all of the source's sessions.
        case_id: For trainers, one case, or None for every case.

    Returns:
        The solves (for trainers, without the ones marked as mistakes).

    """
    store = DbSessionStore(db, source.kind)
    ids = [s.id for s in store.sessions()] if session_id is None else [session_id]
    solves = [solve for sid in ids for solve in db.load_solves(sid)]
    solves.sort(key=lambda solve: solve.created_at)
    if source.set_id is not None:
        solves = [s for s in solves if not s.mistake]
        if case_id is not None:
            solves = [s for s in solves if s.case_id == case_id]
    return solves


def _picker(tooltip: str) -> tuple[QPushButton, QMenu]:
    """Create a button that pops up a menu, like the Learn tab's set picker.

    Args:
        tooltip: Hover help text.

    Returns:
        The button and its (empty) menu.

    """
    button = QPushButton()
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.setToolTip(tooltip)
    menu = QMenu(button)
    button.clicked.connect(
        lambda: menu.popup(button.mapToGlobal(button.rect().bottomLeft())),
    )
    return button, menu


def _value_label() -> QLabel:
    """Create a right-aligned label for a number, with tabular digits.

    Returns:
        The label.

    """
    label = QLabel()
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    font = QFont()
    font.setFeature(QFont.Tag("tnum"), 1)
    label.setFont(font)
    return label


class StatsPage(QWidget):
    """Summary statistics of the selected solves.

    Attributes:
        source: The selected source.
        session_id: The selected session, or None for all sessions.
        case_id: The selected case (trainers only), or None for all cases.
        source_button: Chooses the source.
        session_button: Chooses the session.
        case_button: Chooses the case (hidden for the full timer).
        sub_x: The limit for the sub-X rate, in seconds.
        overview: Value labels of the overview, keyed by row name.
        averages: Value labels of the averages, keyed by ``(n, "current" | "best")``.
        sub_x_label: The sub-X rate.

    """

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        """Create the page, showing the full timer's current session.

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

        self.source_button, self._source_menu = _picker("Full timer or a trainer")
        for source in self._sources:
            self._source_menu.addAction(
                source.label,
                lambda s=source: self.select_source(s),
            )
        reserve_width(self.source_button, *(f"{s.label}  ▾" for s in self._sources))
        self.session_button, self._session_menu = _picker("One session or all")
        self._session_menu.aboutToShow.connect(self._fill_session_menu)
        self.case_button, self._case_menu = _picker("One case or all")
        self._case_menu.aboutToShow.connect(self._fill_case_menu)

        self.sub_x: QDoubleSpinBox = QDoubleSpinBox()
        self.sub_x.setRange(0.5, 600)
        self.sub_x.setDecimals(2)
        self.sub_x.setSingleStep(1)
        self.sub_x.setSuffix(" s")
        self.sub_x.setValue(DEFAULT_SUB_X)
        self.sub_x.valueChanged.connect(self.refresh)

        top = QHBoxLayout()
        for text, button in (
            ("Source:", self.source_button),
            ("Session:", self.session_button),
            ("Case:", self.case_button),
        ):
            label = QLabel(text)
            top.addWidget(label)
            top.addWidget(button)
            if button is self.case_button:
                self._case_label = label
        top.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        boxes = QHBoxLayout()
        boxes.addWidget(self._build_overview())
        boxes.addWidget(self._build_averages())
        boxes.addWidget(self._build_sub_x())
        boxes.addStretch()
        layout.addLayout(boxes)
        layout.addStretch()
        self.refresh()

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
            header.setFont(bold)
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

    def _fill_session_menu(self) -> None:
        """List the source's sessions, plus "All"."""
        self._session_menu.clear()
        self._session_menu.addAction(ALL, lambda: self.select_session(None))
        for session in DbSessionStore(self._db, self.source.kind).sessions():
            self._session_menu.addAction(
                session.name,
                lambda sid=session.id: self.select_session(sid),
            )

    def _fill_case_menu(self) -> None:
        """List the trainer's cases, plus "All"."""
        self._case_menu.clear()
        self._case_menu.addAction(ALL, lambda: self.select_case(None))
        if self.source.set_id is None:
            return
        for case in load_case_set(self.source.set_id).cases:
            self._case_menu.addAction(
                case.name,
                lambda cid=case.id: self.select_case(cid),
            )

    def refresh(self) -> None:
        """Reload the selected solves and show their statistics."""
        self._update_pickers()
        solves = load_solves(self._db, self.source, self.session_id, self.case_id)
        values = [solve.value for solve in solves]
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
        rate = stats.sub_x_rate(values, self.sub_x.value() * 1000)
        if rate is None:
            self.sub_x_label.setText("-")
        else:
            under = round(rate * len(values))
            self.sub_x_label.setText(
                f"{format_percent(rate)}  ({under} of {len(values)})",
            )

    def _update_pickers(self) -> None:
        """Show the current selection on the picker buttons."""
        self.source_button.setText(f"{self.source.label}  ▾")
        sessions = DbSessionStore(self._db, self.source.kind).sessions()
        name = next((s.name for s in sessions if s.id == self.session_id), ALL)
        self.session_button.setText(f"{name}  ▾")
        trainer = self.source.set_id is not None
        self.case_button.setVisible(trainer)
        self._case_label.setVisible(trainer)
        if trainer and self.source.set_id is not None:
            cases = load_case_set(self.source.set_id).cases
            case = next((c.name for c in cases if c.id == self.case_id), ALL)
            self.case_button.setText(f"{case}  ▾")

    @override
    def showEvent(self, event: QShowEvent) -> None:
        """Refresh each time the tab is shown: solves may have changed elsewhere.

        Args:
            event: The show event.

        """
        super().showEvent(event)
        self.refresh()
