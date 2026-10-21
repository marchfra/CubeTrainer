"""SQLite storage for sessions and solves.

The schema is versioned with SQLite's ``user_version`` pragma: each entry of
``MIGRATIONS`` upgrades the database by one version, so existing data survives schema
changes in later steps.
"""

import os
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import override

import platformdirs

from cubetrainer.cases.catalog import CaseCustomization, CaseStatus
from cubetrainer.cases.filters import CaseFilter
from cubetrainer.sessions import SESSION_STEM, SessionInfo
from cubetrainer.solves import Penalty, Solve, SolveList

#: Environment variable overriding where the database lives (useful for development).
DATA_DIR_ENV: str = "CUBETRAINER_DATA_DIR"

#: Name of the app's data directory.
APP_DIR_NAME: str = "CubeTrainer"

#: Directory, next to the database, holding uploaded case images.
IMAGES_DIR_NAME: str = "images"

#: Database file name inside the data directory.
DB_FILENAME: str = "cubetrainer.db"

#: Session kind used by the full-solve timer.
TIMER_KIND: str = "timer"

#: Name given to the session created automatically on first use.
DEFAULT_SESSION_NAME: str = f"{SESSION_STEM} 1"

#: Schema migrations; applying ``MIGRATIONS[i]`` moves the database to version i + 1.
MIGRATIONS: tuple[str, ...] = (
    """
    CREATE TABLE sessions (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        kind TEXT NOT NULL,
        created_at TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE solves (
        id INTEGER PRIMARY KEY,
        session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        time_ms INTEGER NOT NULL,
        penalty TEXT NOT NULL,
        scramble TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX solves_by_session ON solves(session_id, id);
    """,
    """
    CREATE TABLE case_progress (
        set_id TEXT NOT NULL,
        case_id TEXT NOT NULL,
        status TEXT NOT NULL,
        PRIMARY KEY (set_id, case_id)
    );
    """,
    """
    ALTER TABLE solves ADD COLUMN case_id TEXT;
    """,
    """
    ALTER TABLE solves ADD COLUMN hints INTEGER NOT NULL DEFAULT 0;
    """,
    """
    ALTER TABLE solves ADD COLUMN mistake INTEGER NOT NULL DEFAULT 0;
    """,
    """
    CREATE TABLE settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    """
    ALTER TABLE case_progress ADD COLUMN custom_alg TEXT;
    ALTER TABLE case_progress ADD COLUMN image_path TEXT;
    ALTER TABLE case_progress ADD COLUMN rotation INTEGER NOT NULL DEFAULT 0;
    """,
)


def trainer_session_kind(set_id: str) -> str:
    """Return the session kind used by the trainer of a case set.

    Args:
        set_id: The case set, e.g. ``"pll"``.

    Returns:
        e.g. ``"trainer:pll"``.

    """
    return f"trainer:{set_id}"


def default_db_path() -> Path:
    """Return where the database is stored.

    On macOS this is always ``~/Library/Application Support/CubeTrainer``: platformdirs
    would follow ``XDG_DATA_HOME`` when it's set, but that variable usually only exists
    in shells, so an app launched from Finder would look somewhere else and appear to
    have lost its data. Other platforms use platformdirs' user data directory.

    Returns:
        ``$CUBETRAINER_DATA_DIR/cubetrainer.db`` if the variable is set, otherwise the
        file in the platform's user data directory.

    """
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        directory = Path(override)
    elif sys.platform == "darwin":
        directory = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    else:
        directory = platformdirs.user_data_path(APP_DIR_NAME, appauthor=False)
    return directory / DB_FILENAME


class Database:
    """Connection to the app's SQLite database.

    Attributes:
        path: The database file, or ``":memory:"`` for a throwaway database.
        images_dir: Where uploaded case images are kept: next to the database (a
            temporary directory for a throwaway database).

    """

    def __init__(self, path: Path | str) -> None:
        """Open (creating if needed) the database and bring its schema up to date.

        Args:
            path: Database file, or ``":memory:"``.

        """
        self.path: Path | str = path
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.images_dir: Path = (
            path.parent / IMAGES_DIR_NAME
            if isinstance(path, Path)
            else Path(tempfile.gettempdir()) / "cubetrainer-images"
        )
        self._conn: sqlite3.Connection = sqlite3.connect(path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    @property
    def schema_version(self) -> int:
        """The schema version stored in the database."""
        return self._conn.execute("PRAGMA user_version").fetchone()[0]

    def _migrate(self) -> None:
        """Apply any migrations the database hasn't seen yet, one transaction each."""
        for version in range(self.schema_version, len(MIGRATIONS)):
            # executescript commits first, so wrap the migration in its own transaction.
            self._conn.executescript(
                f"BEGIN; {MIGRATIONS[version]} PRAGMA user_version = {version + 1}; "
                "COMMIT;",
            )

    def close(self) -> None:
        """Close the connection."""
        self._conn.close()

    def get_or_create_session(self, kind: str = TIMER_KIND) -> int:
        """Return the first session of a kind, creating a default one if none exist.

        Args:
            kind: Session kind, e.g. ``"timer"``.

        Returns:
            The session id.

        """
        row = self._conn.execute(
            "SELECT id FROM sessions WHERE kind = ? ORDER BY sort_order, id LIMIT 1",
            (kind,),
        ).fetchone()
        if row is not None:
            return row[0]
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO sessions (name, kind, created_at) VALUES (?, ?, ?)",
                (DEFAULT_SESSION_NAME, kind, datetime.now(UTC).isoformat()),
            )
        session_id = cursor.lastrowid
        assert session_id is not None  # noqa: S101 - always set after an INSERT
        return session_id

    def list_sessions(self, kind: str) -> list[SessionInfo]:
        """List the sessions of a kind, in display order.

        Args:
            kind: Session kind, e.g. ``"timer"``.

        Returns:
            The sessions (possibly none).

        """
        rows = self._conn.execute(
            "SELECT id, name FROM sessions WHERE kind = ? ORDER BY sort_order, id",
            (kind,),
        )
        return [SessionInfo(session_id, name) for session_id, name in rows]

    def create_session(self, kind: str, name: str) -> int:
        """Add a session at the end of a kind's list.

        Args:
            kind: Session kind.
            name: Its name.

        Returns:
            The new session's id.

        """
        with self._conn:
            (last,) = self._conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) FROM sessions WHERE kind = ?",
                (kind,),
            ).fetchone()
            cursor = self._conn.execute(
                "INSERT INTO sessions (name, kind, created_at, sort_order)"
                " VALUES (?, ?, ?, ?)",
                (name, kind, datetime.now(UTC).isoformat(), last + 1),
            )
        session_id = cursor.lastrowid
        assert session_id is not None  # noqa: S101 - always set after an INSERT
        return session_id

    def rename_session(self, session_id: int, name: str) -> None:
        """Rename a session.

        Args:
            session_id: The session.
            name: Its new name.

        """
        with self._conn:
            self._conn.execute(
                "UPDATE sessions SET name = ? WHERE id = ?",
                (name, session_id),
            )

    def delete_session(self, session_id: int) -> None:
        """Delete a session and (by cascade) its solves.

        Args:
            session_id: The session.

        """
        with self._conn:
            self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def load_solves(self, session_id: int) -> list[Solve]:
        """Load all solves of a session, oldest first.

        Args:
            session_id: The session.

        Returns:
            The solves, with their database ids set.

        """
        rows = self._conn.execute(
            "SELECT id, time_ms, penalty, scramble, created_at, case_id, hints,"
            " mistake FROM solves "
            "WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        return [
            Solve(
                time_ms=time_ms,
                scramble=scramble,
                penalty=Penalty(penalty),
                created_at=datetime.fromisoformat(created_at),
                id=solve_id,
                case_id=case_id,
                hints=hints,
                mistake=bool(mistake),
            )
            for (
                solve_id,
                time_ms,
                penalty,
                scramble,
                created_at,
                case_id,
                hints,
                mistake,
            ) in rows
        ]

    def add_solve(self, session_id: int, solve: Solve) -> int:
        """Insert a solve and record its new id on the object.

        Args:
            session_id: The session the solve belongs to.
            solve: The solve to store; its ``id`` is set.

        Returns:
            The new solve id.

        """
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO solves"
                " (session_id, time_ms, penalty, scramble, created_at, case_id, hints,"
                " mistake) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    solve.time_ms,
                    solve.penalty.value,
                    solve.scramble,
                    solve.created_at.isoformat(),
                    solve.case_id,
                    solve.hints,
                    int(solve.mistake),
                ),
            )
        solve.id = cursor.lastrowid
        assert solve.id is not None  # noqa: S101 - always set after an INSERT
        return solve.id

    def update_penalty(self, solve_id: int, penalty: Penalty) -> None:
        """Change a stored solve's penalty.

        Args:
            solve_id: The solve.
            penalty: The new penalty.

        """
        with self._conn:
            self._conn.execute(
                "UPDATE solves SET penalty = ? WHERE id = ?",
                (penalty.value, solve_id),
            )

    def update_mistake(self, solve_id: int, *, mistake: bool) -> None:
        """Change whether a stored solve is marked as a mistake.

        Args:
            solve_id: The solve.
            mistake: The new flag.

        """
        with self._conn:
            self._conn.execute(
                "UPDATE solves SET mistake = ? WHERE id = ?",
                (int(mistake), solve_id),
            )

    def delete_solve(self, solve_id: int) -> None:
        """Delete a stored solve.

        Args:
            solve_id: The solve.

        """
        with self._conn:
            self._conn.execute("DELETE FROM solves WHERE id = ?", (solve_id,))

    def load_case_statuses(self, set_id: str) -> dict[str, CaseStatus]:
        """Load the learning status of every case of a set that has one stored.

        Args:
            set_id: The case set, e.g. ``"pll"``.

        Returns:
            Statuses keyed by case id; cases never clicked are absent (unlearned).

        """
        rows = self._conn.execute(
            "SELECT case_id, status FROM case_progress WHERE set_id = ?",
            (set_id,),
        )
        return {case_id: CaseStatus(status) for case_id, status in rows}

    def load_case_customizations(self, set_id: str) -> dict[str, CaseCustomization]:
        """Load what the user changed about a set's cases in the case editor.

        Args:
            set_id: The case set.

        Returns:
            Customisations keyed by case id, for the cases that have any.

        """
        rows = self._conn.execute(
            "SELECT case_id, custom_alg, image_path, rotation FROM case_progress"
            " WHERE set_id = ? AND (custom_alg IS NOT NULL OR image_path IS NOT NULL"
            " OR rotation != 0)",
            (set_id,),
        )
        return {
            case_id: CaseCustomization(alg=alg, image_path=image, rotation=rotation)
            for case_id, alg, image, rotation in rows
        }

    def save_case_customization(
        self,
        set_id: str,
        case_id: str,
        customization: CaseCustomization,
    ) -> None:
        """Store what the user changed about a case (keeping its learning status).

        Args:
            set_id: The case set.
            case_id: The case.
            customization: The new customisation (all defaults to reset the case).

        """
        with self._conn:
            self._conn.execute(
                "INSERT INTO case_progress"
                " (set_id, case_id, status, custom_alg, image_path, rotation)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (set_id, case_id) DO UPDATE SET"
                " custom_alg = excluded.custom_alg, image_path = excluded.image_path,"
                " rotation = excluded.rotation",
                (
                    set_id,
                    case_id,
                    CaseStatus.UNLEARNED.value,
                    customization.alg,
                    customization.image_path,
                    customization.rotation,
                ),
            )

    def set_case_status(self, set_id: str, case_id: str, status: CaseStatus) -> None:
        """Store the learning status of a case.

        Args:
            set_id: The case set.
            case_id: The case.
            status: The new status.

        """
        with self._conn:
            self._conn.execute(
                "INSERT INTO case_progress (set_id, case_id, status) VALUES (?, ?, ?)"
                " ON CONFLICT (set_id, case_id) DO UPDATE SET status = excluded.status",
                (set_id, case_id, status.value),
            )

    def get_setting(self, key: str) -> str | None:
        """Read a stored setting.

        Args:
            key: The setting's name.

        Returns:
            Its value, or None if it was never set.

        """
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
        return None if row is None else row[0]

    def set_setting(self, key: str, value: str) -> None:
        """Store a setting, replacing any previous value.

        Args:
            key: The setting's name.
            value: Its new value.

        """
        with self._conn:
            self._conn.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)"
                " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


class StoredTrainerPrefs:
    """Trainer preferences of one case set, kept in the database.

    Statuses are the ones set in the Learn tab; the filter is a setting.

    Attributes:
        db: The database.
        set_id: The case set.

    """

    def __init__(self, db: Database, set_id: str) -> None:
        """Create the preferences of a set.

        Args:
            db: The database.
            set_id: The case set, e.g. ``"pll"``.

        """
        self.db: Database = db
        self.set_id: str = set_id

    @property
    def _filter_key(self) -> str:
        """The setting holding this set's filter."""
        return f"trainer_filter:{self.set_id}"

    def statuses(self) -> dict[str, CaseStatus]:
        """Return the learning statuses set in the Learn tab.

        Returns:
            Statuses keyed by case id; missing cases are unlearned.

        """
        return self.db.load_case_statuses(self.set_id)

    def get_setting(self, key: str) -> str | None:
        """Read a setting (shared by every set's trainer).

        Args:
            key: The setting's name.

        Returns:
            Its value, or None if it was never set.

        """
        return self.db.get_setting(key)

    def set_setting(self, key: str, value: str) -> None:
        """Store a setting (shared by every set's trainer).

        Args:
            key: The setting's name.
            value: Its new value.

        """
        self.db.set_setting(key, value)

    def customizations(self) -> dict[str, CaseCustomization]:
        """Return what the user changed about the set's cases.

        Returns:
            Customisations keyed by case id.

        """
        return self.db.load_case_customizations(self.set_id)

    def load_filter(self) -> CaseFilter:
        """Return the saved filter, or the default one (every case, equally).

        Returns:
            The filter.

        """
        text = self.db.get_setting(self._filter_key)
        return CaseFilter() if text is None else CaseFilter.from_json(text)

    def save_filter(self, case_filter: CaseFilter) -> None:
        """Save the filter.

        Args:
            case_filter: The filter to keep.

        """
        self.db.set_setting(self._filter_key, case_filter.to_json())


class DbSessionStore:
    """The sessions of one kind (one page), kept in the database.

    The current session is remembered in a setting.

    Attributes:
        db: The database.
        kind: Session kind, e.g. ``"timer"`` or ``"trainer:pll"``.

    """

    def __init__(self, db: Database, kind: str) -> None:
        """Create the store.

        Args:
            db: The database.
            kind: Session kind.

        """
        self.db: Database = db
        self.kind: str = kind

    @property
    def _current_key(self) -> str:
        """The setting holding the current session's id."""
        return f"session.current:{self.kind}"

    def sessions(self) -> list[SessionInfo]:
        """List the sessions, creating a first one if there are none.

        Returns:
            The sessions in display order.

        """
        sessions = self.db.list_sessions(self.kind)
        if not sessions:
            self.db.get_or_create_session(self.kind)
            sessions = self.db.list_sessions(self.kind)
        return sessions

    def current(self) -> int:
        """Return the current session (the first one if none was chosen).

        Returns:
            The session id.

        """
        ids = [session.id for session in self.sessions()]
        stored = self.db.get_setting(self._current_key)
        if stored is not None and int(stored) in ids:
            return int(stored)
        return ids[0]

    def select(self, session_id: int) -> None:
        """Make a session the current one.

        Args:
            session_id: The session.

        """
        self.db.set_setting(self._current_key, str(session_id))

    def create(self, name: str) -> int:
        """Add a session at the end of the list.

        Args:
            name: Its name.

        Returns:
            The new session's id.

        """
        return self.db.create_session(self.kind, name)

    def rename(self, session_id: int, name: str) -> None:
        """Rename a session.

        Args:
            session_id: The session.
            name: Its new name.

        """
        self.db.rename_session(session_id, name)

    def delete(self, session_id: int) -> None:
        """Delete a session and its solves; the current one moves if needed.

        Args:
            session_id: The session (never the only one).

        """
        was_current = self.current() == session_id
        self.db.delete_session(session_id)
        if was_current:
            self.select(self.sessions()[0].id)

    def solves(self, session_id: int) -> SolveList:
        """Return a session's solves, saving every change.

        Args:
            session_id: The session.

        Returns:
            The stored solve list.

        """
        return StoredSolveList(self.db, session_id)


class StoredSolveList(SolveList):
    """A solve list that loads from and writes every change through to the database.

    Attributes:
        db: The database.
        session_id: The session whose solves this list holds.

    """

    def __init__(self, db: Database, session_id: int) -> None:
        """Load a session's solves.

        Args:
            db: The database.
            session_id: The session to load.

        """
        super().__init__()
        self.db: Database = db
        self.session_id: int = session_id
        self.solves = db.load_solves(session_id)

    @override
    def add(self, solve: Solve) -> None:
        """Append and store a newly finished solve.

        Args:
            solve: The solve to add; its ``id`` is set.

        """
        self.db.add_solve(self.session_id, solve)
        super().add(solve)

    @override
    def delete(self, index: int) -> Solve:
        """Remove a solve from the list and the database.

        Args:
            index: Position of the solve (0 is the oldest; -1 is the newest).

        Returns:
            The removed solve.

        """
        solve = super().delete(index)
        if solve.id is not None:
            self.db.delete_solve(solve.id)
        return solve

    @override
    def set_penalty(self, index: int, penalty: Penalty) -> None:
        """Change and store the penalty of a solve.

        Args:
            index: Position of the solve (0 is the oldest; -1 is the newest).
            penalty: The new penalty.

        """
        super().set_penalty(index, penalty)
        solve_id = self.solves[index].id
        if solve_id is not None:
            self.db.update_penalty(solve_id, penalty)

    @override
    def set_mistake(self, index: int, *, mistake: bool) -> None:
        """Mark or unmark a solve as messed up, and store the change.

        Args:
            index: Position of the solve (0 is the oldest; -1 is the newest).
            mistake: Whether the solve was a mistake.

        """
        super().set_mistake(index, mistake=mistake)
        solve_id = self.solves[index].id
        if solve_id is not None:
            self.db.update_mistake(solve_id, mistake=mistake)
