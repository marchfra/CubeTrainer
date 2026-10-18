"""The Timer tab: cstimer-like layout for full solves.

Solves list on the left; scramble bar and big timer on the right.
"""

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, override

import numpy as np
import shiboken6
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QFont, QKeySequence, QShortcut, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from cubetrainer.cube.scramble import random_state_scramble
from cubetrainer.formatting import format_solve
from cubetrainer.sessions import MemorySessionStore, SessionStore, next_session_name
from cubetrainer.settings import MemorySettings, Settings, get_flag, set_flag
from cubetrainer.solves import Penalty, Solve, SolveList
from cubetrainer.sound import InspectionAudio
from cubetrainer.ui.case_images import CaseInfo
from cubetrainer.ui.chart_style import GRAPH_HEIGHT
from cubetrainer.ui.dropdown import Dropdown
from cubetrainer.ui.icon_buttons import MoreButton
from cubetrainer.ui.scramble_bar import ScrambleBar
from cubetrainer.ui.shortcuts import Shortcut, ShortcutsDialog
from cubetrainer.ui.solve_dialog import SolveDialog
from cubetrainer.ui.solves_panel import TIMER_LAYOUT, PanelLayout, SolvesPanel
from cubetrainer.ui.timer_widget import TIMER_KEYS, TimerWidget

if TYPE_CHECKING:
    from cubetrainer.ui.icon_buttons import CogButton
    from cubetrainer.ui.time_graph import TimeGraph

#: Keyboard shortcut for each penalty on the last solve. "Ctrl" is Cmd on macOS.
PENALTY_SHORTCUTS: dict[Penalty, str] = {
    Penalty.OK: "Ctrl+1",
    Penalty.PLUS_TWO: "Ctrl+2",
    Penalty.DNF: "Ctrl+3",
}

#: How each penalty is named in the shortcuts list.
_PENALTY_NAMES: dict[Penalty, str] = {
    Penalty.OK: "OK",
    Penalty.PLUS_TWO: "+2",
    Penalty.DNF: "DNF",
}

#: Shortcut deleting the last solve. "Ctrl" is Cmd on macOS.
DELETE_LAST_SHORTCUT: str = "Ctrl+Z"

#: Width of the side columns: the solves on the left and, on pages that have
#: one, the right column. Equal widths keep the timer centred between them.
SIDE_COLUMN_WIDTH: int = 320


def default_scramble_generator() -> Callable[[], str]:
    """Build a generator of full-cube random-state scrambles.

    Returns:
        A function returning a new scramble each time it's called.

    """
    rng = np.random.default_rng()
    return lambda: random_state_scramble(rng)


def ask_text(parent: QWidget, label: str, text: str) -> str | None:
    """Ask for a line of text in a small dialog.

    Args:
        parent: Parent of the dialog.
        label: What to ask.
        text: The suggested answer.

    Returns:
        The answer with spaces trimmed, or None if cancelled or left empty.

    """
    answer, accepted = QInputDialog.getText(parent, "CubeTrainer", label, text=text)
    answer = answer.strip()
    return answer if accepted and answer else None


def ask_confirmation(parent: QWidget, question: str) -> bool:
    """Ask a yes/no question in a message box.

    Args:
        parent: Parent widget of the message box.
        question: The question text.

    Returns:
        True if the user answered yes.

    """
    answer = QMessageBox.question(parent, "Confirm", question)
    return answer == QMessageBox.StandardButton.Yes


class TimerPage(QWidget):
    """Full-solve timer page; also the base of the trainer page.

    Attributes:
        sessions: The page's sessions.
        solves: The solves of the current session.
        session_picker: Chooses the current session.
        session_actions_button: Opens ``session_menu`` (new, rename, delete).
        delete_session_action: The menu's delete action (off for the last session).
        session_menu: Adds, renames or deletes sessions.
        ask_text: Asks for a line of text; replaceable in tests.
        solves_panel: Summary and table of solves.
        scramble_bar: Shows the scramble to apply before the solve.
        timer: The spacebar-driven timer.
        title: The page's name, at the start of the header.
        grid: The page's layout. Row 0 is the header: ``header_left``, the scramble
            bar, ``header_right``. Under it, column 0 holds the session button, the
            statistics and the solves table (rows 1-3); column 1 the timer column;
            column 2 an optional right column (see ``add_right_column``), whose
            room the timer column takes when there is none.
        header_left: Start of the header, over the solves: the title.
        header_right: End of the header (empty on the full timer).
        shortcut_help: Every shortcut the page registered, with what it does.
        center_column: Layout holding the timer (and the time graph).
        settings: Where the options are kept.
        options_button: The cog in the timer's corner; opens ``options_menu``.
        options_menu: The inspection options.
        inspection_action: Turns inspection on or off.
        hold_action: Makes inspection start with a hold until green, like a solve.
        audio_action: Turns the 8 s / 12 s beeps on or off.
        play_warning: Plays an inspection warning; replaceable in tests.
        shortcuts: The keyboard shortcuts, keyed by key sequence string.
        confirm: Asks a yes/no question; replaceable in tests.
        run_dialog: Runs a dialog and returns its result; replaceable in tests.
        PANEL_LAYOUT: Statistics and columns of the solves panel.
        SETTINGS_PREFIX: Start of this page's setting names.
        INSPECTION_DEFAULT: Whether inspection is on until the user changes it.
        SHOW_GRAPH: Whether the page has a time graph under the timer.
        time_graph: The time graph; None on pages without one, and until the page
            is first shown (it's built just after, so the window opens sooner).

    """

    PANEL_LAYOUT: PanelLayout = TIMER_LAYOUT
    SETTINGS_PREFIX: str = "timer"
    INSPECTION_DEFAULT: bool = True
    SHOW_GRAPH: bool = True

    def __init__(
        self,
        sessions: SessionStore | None = None,
        generate: Callable[[], str] | None = None,
        clock: Callable[[], int] = time.perf_counter_ns,
        settings: Settings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Create the page, showing the current session.

        Args:
            sessions: The page's sessions; in memory if omitted.
            generate: Scramble generator; defaults to random-state full-cube scrambles.
            clock: Monotonic clock in nanoseconds, passed to the timer.
            settings: Where the options are kept; in memory if omitted.
            parent: Optional parent widget.

        """
        super().__init__(parent)
        self.settings: Settings = settings if settings is not None else MemorySettings()
        self.sessions: SessionStore = (
            sessions if sessions is not None else MemorySessionStore()
        )
        self.solves: SolveList = self.sessions.solves(self.sessions.current())
        self.confirm: Callable[[str], bool] = lambda q: ask_confirmation(self, q)
        self.ask_text: Callable[[str, str], str | None] = lambda label, text: ask_text(
            self,
            label,
            text,
        )
        self.run_dialog: Callable[[QDialog], int] = lambda d: d.exec()
        self._solve_scramble: str = ""

        self.solves_panel: SolvesPanel = SolvesPanel(
            self.solves,
            self.PANEL_LAYOUT,
            # A bound method is looked up per call, so subclasses' attributes exist.
            self.case_name,
            embed=False,  # placed in the body grid, to line up with a right column
        )
        self.solves_panel.solve_activated.connect(self.show_solve)
        self.scramble_bar: ScrambleBar = ScrambleBar(
            generate or default_scramble_generator(),
        )
        self.timer: TimerWidget = TimerWidget(clock=clock)
        self.timer.solve_started.connect(self._on_solve_started)
        self.timer.solve_finished.connect(self._on_solve_finished)

        self.title: QLabel = QLabel("Full timer")
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        self.title.setFont(font)
        self.header_left: QHBoxLayout = QHBoxLayout()
        self.header_left.addWidget(self.title)
        self.header_left.addStretch()
        self.header_right: QHBoxLayout = QHBoxLayout()
        self.header_right.addStretch()
        self._build_options()
        # In the timer's corner: the header (in the trainer, its right column) has
        # no room for another button.
        self.timer.shortcuts_button.clicked.connect(self.show_shortcuts)
        self.center_column: QVBoxLayout = QVBoxLayout()
        self.center_column.addWidget(self.timer, stretch=1)
        # The graph is built just after the page first appears (see showEvent):
        # it needs matplotlib, which takes a while to load, and the window
        # shouldn't wait for it. Its space is kept meanwhile, so nothing moves.
        self.time_graph: TimeGraph | None = None
        self._graph_slot: QWidget | None = None
        if self.SHOW_GRAPH:
            self._graph_slot = QWidget(self)
            self._graph_slot.setFixedHeight(GRAPH_HEIGHT)
            slot_layout = QVBoxLayout(self._graph_slot)
            slot_layout.setContentsMargins(0, 0, 0, 0)
            self.center_column.addWidget(self._graph_slot)
        self.grid: QGridLayout = QGridLayout(self)
        # The top row is the header: the scramble in the middle, over the timer.
        self.grid.addLayout(self.header_left, 0, 0)
        self.grid.addWidget(self.scramble_bar, 0, 1)
        self.grid.addLayout(self.header_right, 0, 2)
        self._build_left_column()
        # Without a right column the timer column also takes the right one's room.
        self.grid.addLayout(self.center_column, 1, 1, 3, 2)
        self.grid.setColumnStretch(1, 1)
        self.grid.setRowStretch(3, 1)

        self.shortcuts: dict[str, QShortcut] = {}
        self.shortcut_help: list[Shortcut] = []
        for penalty, keys in PENALTY_SHORTCUTS.items():
            self._add_shortcut(
                keys,
                lambda p=penalty: self.set_last_penalty(p),
                f"Mark the last solve {_PENALTY_NAMES[penalty]}",
            )
        self._add_shortcut(
            DELETE_LAST_SHORTCUT,
            self.delete_last,
            "Delete the last solve (asks first)",
        )

    @override
    def showEvent(self, event: QShowEvent) -> None:
        """Build the time graph just after the page first appears.

        Args:
            event: The show event.

        """
        super().showEvent(event)
        if self._graph_slot is not None and self.time_graph is None:
            QTimer.singleShot(0, self, self._build_time_graph_if_open)

    def _build_time_graph_if_open(self) -> None:
        """Build the graph, unless the page was hidden or closed meanwhile.

        A hidden page builds it the next time it's shown, and a closed one may be
        in the middle of being deleted.
        """
        if not shiboken6.isValid(self):
            return
        # Holding the window keeps it (and this page) from being garbage-collected
        # mid-build when nothing else refers to it any more.
        window = self.window()
        if window.isVisible() and self.isVisible():
            self.build_time_graph()

    def build_time_graph(self) -> None:
        """Create the time graph in its reserved space (once).

        Does nothing if the page was closed (and its space deleted) meanwhile.
        """
        if self._graph_slot is None or self.time_graph is not None:
            return
        # Imported here: matplotlib is slow to load (see showEvent). Loading it can
        # let Qt run pending events, the page's deletion included, so the space is
        # checked only afterwards.
        from cubetrainer.ui.time_graph import TimeGraph  # noqa: PLC0415

        slot = self._graph_slot
        if not (shiboken6.isValid(self) and shiboken6.isValid(slot)):
            return
        graph = TimeGraph(self.solves, slot)
        layout = slot.layout()
        if not shiboken6.isValid(slot) or layout is None:
            return  # closed while the graph was being made
        self.time_graph = graph
        layout.addWidget(graph)

    def _build_left_column(self) -> None:
        """Fill the body's left column: session button, statistics, solves table."""
        # A combo box chooses the session; the actions (new, rename, delete) are
        # in a menu behind the "more" button beside it, not among the choices.
        self.session_picker: QComboBox = Dropdown()
        self.session_picker.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.session_picker.setToolTip("Switch session")
        self.session_picker.activated.connect(
            lambda index: self.switch_session(self.session_picker.itemData(index)),
        )
        self.session_menu: QMenu = QMenu(self)
        self.session_menu.addAction("New session…", self.new_session)
        self.session_menu.addAction("Rename session…", self.rename_session)
        self.delete_session_action: QAction = self.session_menu.addAction(
            "Delete session…",
            self.delete_session,
        )
        self.session_actions_button: MoreButton = MoreButton(
            "New, rename or delete sessions",
        )
        self.session_actions_button.clicked.connect(
            lambda: self.session_menu.popup(
                self.session_actions_button.mapToGlobal(
                    self.session_actions_button.rect().bottomLeft(),
                ),
            ),
        )
        session_row = QWidget()
        row_layout = QHBoxLayout(session_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        row_layout.addWidget(self.session_picker, stretch=1)
        row_layout.addWidget(self.session_actions_button)
        self._update_session_picker()

        for row, widget in enumerate(
            (session_row, self.solves_panel.summary, self.solves_panel.table),
        ):
            widget.setFixedWidth(SIDE_COLUMN_WIDTH)
            self.grid.addWidget(widget, row + 1, 0)

    def add_right_column(self, title: QWidget, table: QWidget) -> None:
        """Add a column to the right of the timer, as wide as the solves column.

        The title sits level with the session button and the table fills the rest
        of the column; the timer column is then centred in the page.

        Args:
            title: Goes at the top, under the header.
            table: Goes under the title.

        """
        self.grid.removeItem(self.center_column)
        self.grid.addLayout(self.center_column, 1, 1, 3, 1)
        table.setFixedWidth(SIDE_COLUMN_WIDTH)
        self.grid.addWidget(title, 1, 2)
        self.grid.addWidget(table, 2, 2, 2, 1)

    def _update_session_picker(self) -> None:
        """List the sessions in the picker, the current one selected."""
        sessions = self.sessions.sessions()
        picker = self.session_picker
        picker.blockSignals(True)  # noqa: FBT003 - Qt's positional flag
        picker.clear()
        for session in sessions:
            picker.addItem(session.name, session.id)
        picker.setCurrentIndex(max(picker.findData(self.sessions.current()), 0))
        picker.blockSignals(False)  # noqa: FBT003 - Qt's positional flag
        # The last session can't be deleted.
        self.delete_session_action.setEnabled(len(sessions) > 1)

    def switch_session(self, session_id: int) -> None:
        """Make a session current and show its solves.

        Args:
            session_id: The session.

        """
        self.sessions.select(session_id)
        self.solves = self.sessions.solves(session_id)
        self.show_session_solves()
        self._update_session_picker()

    def show_session_solves(self) -> None:
        """Point every view at ``solves`` after the session changed (subclasses add)."""
        self.solves_panel.set_solves(self.solves)
        if self.time_graph is not None:
            self.time_graph.set_solves(self.solves)

    def new_session(self) -> None:
        """Ask for a name, then create a session and switch to it."""
        name = self.ask_text(
            "Name of the new session:",
            next_session_name(self.sessions.sessions()),
        )
        if name:
            self.switch_session(self.sessions.create(name))

    def rename_session(self) -> None:
        """Ask for a new name for the current session."""
        current = self.sessions.current()
        old = next(s.name for s in self.sessions.sessions() if s.id == current)
        name = self.ask_text("New name of the session:", old)
        if name:
            self.sessions.rename(current, name)
            self._update_session_picker()

    def delete_session(self) -> None:
        """Delete the current session and its solves, after asking (never the last)."""
        sessions = self.sessions.sessions()
        if len(sessions) < 2:  # noqa: PLR2004 - one session must always remain
            return
        current = self.sessions.current()
        name = next(s.name for s in sessions if s.id == current)
        count = len(self.solves)
        if self.confirm(f"Delete the session {name!r} and its {count} solves?"):
            self.sessions.delete(current)
            self.switch_session(self.sessions.current())

    def _build_options(self) -> None:
        """Create the options menu, set from the saved settings, on the timer's cog."""
        audio = InspectionAudio()
        self.play_warning: Callable[[int], None] = audio.play
        self.timer.inspection_warning.connect(self._on_inspection_warning)

        self.options_menu: QMenu = QMenu(self)
        self.inspection_action: QAction = self.options_menu.addAction(
            "Inspection (15 s)",
        )
        self.inspection_action.setCheckable(True)
        self.inspection_action.setChecked(
            get_flag(
                self.settings,
                self._key("inspection"),
                default=self.INSPECTION_DEFAULT,
            ),
        )
        self.hold_action: QAction = self.options_menu.addAction(
            "Hold space to start inspection",
        )
        self.hold_action.setCheckable(True)
        self.hold_action.setChecked(
            get_flag(self.settings, self._key("inspection_hold"), default=False),
        )
        self.audio_action: QAction = self.options_menu.addAction(
            "Beep at 8 s and 12 s of inspection",
        )
        self.audio_action.setCheckable(True)
        self.audio_action.setChecked(
            get_flag(self.settings, self._key("inspection_audio"), default=True),
        )
        for action in (self.inspection_action, self.hold_action, self.audio_action):
            action.toggled.connect(self._on_options_changed)
        self._on_options_changed()

        # The cog in the timer's corner: the options are all about the timer.
        self.options_button: CogButton = self.timer.options_button
        self.options_button.clicked.connect(self._show_options)

    def _show_options(self) -> None:
        """Pop the options menu up above the cog (it sits at the bottom)."""
        corner = self.options_button.mapToGlobal(self.options_button.rect().topLeft())
        self.options_menu.popup(
            corner - QPoint(0, self.options_menu.sizeHint().height()),
        )

    def _key(self, name: str) -> str:
        """Return the full name of one of this page's settings.

        Args:
            name: The short name, e.g. ``"inspection"``.

        Returns:
            e.g. ``"timer.inspection"``.

        """
        return f"{self.SETTINGS_PREFIX}.{name}"

    def _on_options_changed(self) -> None:
        """Apply and save the options; the other two only make sense with inspection."""
        inspection = self.inspection_action.isChecked()
        hold = self.hold_action.isChecked()
        self.timer.set_inspection(enabled=inspection, hold=hold)
        self.hold_action.setEnabled(inspection)
        self.audio_action.setEnabled(inspection)
        set_flag(self.settings, self._key("inspection"), value=inspection)
        set_flag(self.settings, self._key("inspection_hold"), value=hold)
        set_flag(
            self.settings,
            self._key("inspection_audio"),
            value=self.audio_action.isChecked(),
        )

    def _on_inspection_warning(self, warning_ms: int) -> None:
        """Beep for an 8 s or 12 s warning, if beeps are on.

        Args:
            warning_ms: The warning (8000 or 12000).

        """
        if self.audio_action.isChecked():
            self.play_warning(warning_ms)

    def _add_shortcut(
        self,
        keys: str,
        handler: Callable[[], None],
        action: str,
    ) -> None:
        """Register a window-wide shortcut that only works while this page is shown.

        The shortcut is also recorded, with its description, for the shortcuts
        list: registering is the only way to add one, so the list can't drift.

        Args:
            keys: Key sequence in portable text form, e.g. ``"Ctrl+1"``.
            handler: Function called when the shortcut fires.
            action: What it does, for the shortcuts list.

        """
        shortcut = QShortcut(QKeySequence(keys), self)
        shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        shortcut.activated.connect(handler)
        self.shortcuts[keys] = shortcut
        self.shortcut_help.append(Shortcut(keys, action))

    def show_shortcuts(self) -> None:
        """Show every keyboard shortcut: the timer's keys, then this page's."""
        sections = [("Timer", TIMER_KEYS), (self.title.text(), self.shortcut_help)]
        self.run_dialog(ShortcutsDialog(sections, self))

    def set_last_penalty(self, penalty: Penalty) -> None:
        """Set the penalty of the most recent solve (no-op without solves).

        Args:
            penalty: The new penalty.

        """
        if self.solves:
            self.solves.set_penalty(-1, penalty)
            self.refresh_solves()

    def delete_last(self) -> None:
        """Delete the most recent solve, after asking for confirmation."""
        if not self.solves:
            return
        last = format_solve(self.solves.solves[-1])
        if self.confirm(f"Delete the last solve ({last})?"):
            self.solves.delete(-1)
            self.refresh_solves()

    def show_solve(self, index: int) -> None:
        """Open the details dialog of a solve and apply what the user did there.

        Args:
            index: Position of the solve in the list (0 is the oldest).

        """
        solve = self.solves.solves[index]
        case = self.case_info(solve.case_id) if solve.case_id else None
        dialog = SolveDialog(solve, index + 1, case=case, parent=self)
        if self.run_dialog(dialog) == SolveDialog.DELETED:
            self.solves.delete(index)
        else:
            # The dialog edits the solve in place; go through the list so it's saved.
            self.solves.set_penalty(index, solve.penalty)
            self.solves.set_mistake(index, mistake=solve.mistake)
        self.refresh_solves()

    def refresh_solves(self) -> None:
        """Redraw everything showing the solves (subclasses add their own views)."""
        self.solves_panel.refresh()
        if self.time_graph is not None:
            self.time_graph.refresh()

    def case_name(self, case_id: str) -> str:
        """Return the display name of a case (subclasses with cases override this).

        Args:
            case_id: The case id.

        Returns:
            The name to show.

        """
        return case_id

    def case_info(self, case_id: str) -> CaseInfo | None:  # noqa: ARG002
        """Return what the solve dialog shows about a case (trainers override this).

        Args:
            case_id: The case id.

        Returns:
            None: full solves have no case.

        """
        return None

    def make_solve(self, time_ms: int, scramble: str, penalty: Penalty) -> Solve:
        """Build the record of a finished solve (subclasses add details).

        Args:
            time_ms: The solve time in milliseconds.
            scramble: The scramble shown when the solve started.
            penalty: The inspection penalty (OK without inspection).

        Returns:
            The new solve.

        """
        return Solve(time_ms=time_ms, scramble=scramble, penalty=penalty)

    def _on_solve_started(self) -> None:
        """Remember the scramble shown when the solve started."""
        self._solve_scramble = self.scramble_bar.scramble

    def _on_solve_finished(self, time_ms: int, penalty: str) -> None:
        """Record the solve and move on to a new scramble.

        Args:
            time_ms: The solve time in milliseconds.
            penalty: The value of its inspection ``Penalty``.

        """
        self.solves.add(
            self.make_solve(time_ms, self._solve_scramble, Penalty(penalty)),
        )
        self.refresh_solves()
        self.scramble_bar.show_new()
