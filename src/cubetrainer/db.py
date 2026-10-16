"""SQLite storage for sessions and solves.

The schema is versioned with SQLite's ``user_version`` pragma: each entry of
``MIGRATIONS`` upgrades the database by one version, so existing data survives schema
changes in later steps.
"""

import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import override

import platformdirs

from cubetrainer.cases.catalog import CaseStatus
from cubetrainer.solves import Penalty, Solve, SolveList

#: Environment variable overriding where the database lives (useful for development).
DATA_DIR_ENV: str = "CUBETRAINER_DATA_DIR"

#: Name of the app's data directory.
APP_DIR_NAME: str = "CubeTrainer"

#: Database file name inside the data directory.
DB_FILENAME: str = "cubetrainer.db"

#: Session kind used by the full-solve timer.
TIMER_KIND: str = "timer"

#: Name given to the session created automatically on first use.
DEFAULT_SESSION_NAME: str = "Session 1"

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
)


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
        directory = platformdirs.user_data_path(APP_DIR_NAME)
    return directory / DB_FILENAME


class Database:
    """Connection to the app's SQLite database.

    Attributes:
        path: The database file, or ``":memory:"`` for a throwaway database.

    """

    def __init__(self, path: Path | str) -> None:
        """Open (creating if needed) the database and bring its schema up to date.

        Args:
            path: Database file, or ``":memory:"``.

        """
        self.path: Path | str = path
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
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

    def load_solves(self, session_id: int) -> list[Solve]:
        """Load all solves of a session, oldest first.

        Args:
            session_id: The session.

        Returns:
            The solves, with their database ids set.

        """
        rows = self._conn.execute(
            "SELECT id, time_ms, penalty, scramble, created_at, case_id, hints"
            " FROM solves "
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
            )
            for solve_id, time_ms, penalty, scramble, created_at, case_id, hints in rows
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
                " (session_id, time_ms, penalty, scramble, created_at, case_id, hints)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    solve.time_ms,
                    solve.penalty.value,
                    solve.scramble,
                    solve.created_at.isoformat(),
                    solve.case_id,
                    solve.hints,
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
