"""Tests for the SQLite storage layer."""

import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import platformdirs
import pytest

from cubetrainer.cases.catalog import CaseStatus
from cubetrainer.db import (
    DATA_DIR_ENV,
    DB_FILENAME,
    MIGRATIONS,
    Database,
    StoredSolveList,
    default_db_path,
)
from cubetrainer.solves import Penalty, Solve


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide a database path inside a not-yet-existing directory.

    Args:
        tmp_path: pytest's temporary directory.

    Returns:
        The path.

    """
    return tmp_path / "nested" / "test.db"


@pytest.fixture
def db(db_path: Path) -> Iterator[Database]:
    """Provide an open database, closed after the test.

    Args:
        db_path: Where to create it.

    Yields:
        The database.

    """
    database = Database(db_path)
    yield database
    database.close()


def test_new_database_is_at_latest_schema(db: Database, db_path: Path) -> None:
    """Opening creates the file (and its directory) and applies all migrations."""
    assert db_path.exists()
    assert db.schema_version == len(MIGRATIONS)


def test_reopening_does_not_rerun_migrations(db_path: Path) -> None:
    """A second open on the same file keeps the data and the version."""
    first = Database(db_path)
    session = first.get_or_create_session()
    first.close()

    second = Database(db_path)

    assert second.schema_version == len(MIGRATIONS)
    assert second.get_or_create_session() == session
    second.close()


def test_get_or_create_session_is_idempotent_per_kind(db: Database) -> None:
    """The same kind returns the same session; another kind gets its own."""
    timer = db.get_or_create_session()

    assert db.get_or_create_session() == timer
    assert db.get_or_create_session("trainer:pll") != timer


def test_solve_round_trip(db: Database) -> None:
    """Every field of a solve survives storing and loading."""
    session = db.get_or_create_session()
    created = datetime(2026, 10, 15, 12, 30, 45, 123456, tzinfo=UTC)
    solve = Solve(12_345, "R U R' U'", Penalty.PLUS_TWO, created)

    solve_id = db.add_solve(session, solve)

    assert solve.id == solve_id
    assert db.load_solves(session) == [solve]


def test_solves_load_oldest_first_per_session(db: Database) -> None:
    """Solves come back in insertion order and only for their own session."""
    timer = db.get_or_create_session()
    other = db.get_or_create_session("trainer:pll")
    for ms in (3_000, 1_000, 2_000):
        db.add_solve(timer, Solve(ms, ""))
    db.add_solve(other, Solve(9_999, ""))

    assert [s.time_ms for s in db.load_solves(timer)] == [3_000, 1_000, 2_000]


def test_update_and_delete(db: Database) -> None:
    """Penalties can be changed and solves deleted."""
    session = db.get_or_create_session()
    keep = Solve(1_000, "")
    drop = Solve(2_000, "")
    db.add_solve(session, keep)
    db.add_solve(session, drop)
    assert keep.id is not None
    assert drop.id is not None

    db.update_penalty(keep.id, Penalty.DNF)
    db.delete_solve(drop.id)

    loaded = db.load_solves(session)
    assert [(s.time_ms, s.penalty) for s in loaded] == [(1_000, Penalty.DNF)]


def test_deleting_session_cascades_to_solves(db: Database) -> None:
    """Foreign keys are enforced, so a session's solves go with it."""
    session = db.get_or_create_session()
    db.add_solve(session, Solve(1_000, ""))

    with db._conn:
        db._conn.execute("DELETE FROM sessions WHERE id = ?", (session,))

    count = db._conn.execute("SELECT COUNT(*) FROM solves").fetchone()[0]
    assert count == 0


def test_stored_solve_list_writes_through(db_path: Path) -> None:
    """Adds, penalties and deletes made through the list are on disk after reopening."""
    db = Database(db_path)
    solves = StoredSolveList(db, db.get_or_create_session())
    for ms in (1_000, 2_000, 3_000):
        solves.add(Solve(ms, f"scramble {ms}"))
    solves.set_penalty(-1, Penalty.PLUS_TWO)
    solves.delete(0)
    db.close()

    reopened = Database(db_path)
    loaded = StoredSolveList(reopened, reopened.get_or_create_session())

    assert [(s.time_ms, s.penalty) for s in loaded.solves] == [
        (2_000, Penalty.OK),
        (3_000, Penalty.PLUS_TWO),
    ]
    reopened.close()


def test_default_path_uses_env_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """CUBETRAINER_DATA_DIR redirects the database."""
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))

    assert default_db_path() == tmp_path / DB_FILENAME


def test_macos_path_ignores_xdg(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """On macOS the database is in Application Support even if XDG_DATA_HOME is set."""
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setattr(sys, "platform", "darwin")

    expected = Path.home() / "Library/Application Support/CubeTrainer" / DB_FILENAME
    assert default_db_path() == expected


def test_other_platforms_use_platformdirs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Elsewhere the platform's user data directory is used (here, via XDG)."""
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        platformdirs,
        "user_data_path",
        lambda name: tmp_path / "share" / name,
    )

    assert default_db_path() == tmp_path / "share" / "CubeTrainer" / DB_FILENAME


def test_case_statuses_round_trip(db: Database) -> None:
    """Statuses are stored per set and case, and can be overwritten."""
    assert db.load_case_statuses("pll") == {}

    db.set_case_status("pll", "T", CaseStatus.LEARNING)
    db.set_case_status("pll", "T", CaseStatus.FINISHED)
    db.set_case_status("pll", "Ua", CaseStatus.LEARNING)
    db.set_case_status("oll", "T", CaseStatus.LEARNING)

    assert db.load_case_statuses("pll") == {
        "T": CaseStatus.FINISHED,
        "Ua": CaseStatus.LEARNING,
    }
