"""cstimer-style sessions: named groups of solves, one of which is current.

Each page (the full timer, each set's trainer) has its own sessions. A store always
has at least one session, so there's always somewhere to put a solve.
"""

from dataclasses import dataclass, field
from typing import Protocol

from cubetrainer.solves import SolveList

#: Name of the first session, and the stem of new sessions' default names.
SESSION_STEM: str = "Session"


@dataclass(frozen=True, slots=True)
class SessionInfo:
    """A session as listed in the session menu.

    Attributes:
        id: Identifier.
        name: Display name.

    """

    id: int
    name: str


def next_session_name(existing: list[SessionInfo]) -> str:
    """Suggest a name for a new session: ``"Session N"`` with N not yet used.

    Args:
        existing: The current sessions.

    Returns:
        e.g. ``"Session 3"``.

    """
    names = {session.name for session in existing}
    number = len(existing) + 1
    while f"{SESSION_STEM} {number}" in names:
        number += 1
    return f"{SESSION_STEM} {number}"


class SessionStore(Protocol):
    """The sessions of one page, and which one is current."""

    def sessions(self) -> list[SessionInfo]:
        """List the sessions in display order (creating a first one if none exist).

        Returns:
            The sessions.

        """
        ...

    def current(self) -> int:
        """Return the id of the current session.

        Returns:
            The id.

        """
        ...

    def select(self, session_id: int) -> None:
        """Make a session the current one.

        Args:
            session_id: The session.

        """
        ...

    def create(self, name: str) -> int:
        """Add a session at the end of the list.

        Args:
            name: Its name.

        Returns:
            The new session's id.

        """
        ...

    def rename(self, session_id: int, name: str) -> None:
        """Rename a session.

        Args:
            session_id: The session.
            name: Its new name.

        """
        ...

    def delete(self, session_id: int) -> None:
        """Delete a session and its solves.

        If it was current, the first remaining session becomes current.

        Args:
            session_id: The session (never the only one).

        """
        ...

    def solves(self, session_id: int) -> SolveList:
        """Return a session's solves.

        Args:
            session_id: The session.

        Returns:
            Its solve list (changes to it are kept).

        """
        ...


@dataclass(slots=True)
class MemorySessionStore:
    """Sessions kept in memory (nothing is saved).

    Attributes:
        names: Session names by id, in display order.
        lists: Session solves by id.
        current_id: The current session.

    """

    names: dict[int, str] = field(default_factory=lambda: {1: f"{SESSION_STEM} 1"})
    lists: dict[int, SolveList] = field(default_factory=dict)
    current_id: int = 1

    def sessions(self) -> list[SessionInfo]:
        """List the sessions in display order.

        Returns:
            The sessions.

        """
        return [SessionInfo(sid, name) for sid, name in self.names.items()]

    def current(self) -> int:
        """Return the id of the current session.

        Returns:
            The id.

        """
        return self.current_id

    def select(self, session_id: int) -> None:
        """Make a session the current one.

        Args:
            session_id: The session.

        """
        self.current_id = session_id

    def create(self, name: str) -> int:
        """Add a session at the end of the list.

        Args:
            name: Its name.

        Returns:
            The new session's id.

        """
        session_id = max(self.names, default=0) + 1
        self.names[session_id] = name
        return session_id

    def rename(self, session_id: int, name: str) -> None:
        """Rename a session.

        Args:
            session_id: The session.
            name: Its new name.

        """
        self.names[session_id] = name

    def delete(self, session_id: int) -> None:
        """Delete a session; if it was current, the first remaining one becomes so.

        Args:
            session_id: The session (never the only one).

        """
        del self.names[session_id]
        self.lists.pop(session_id, None)
        if self.current_id == session_id:
            self.current_id = next(iter(self.names))

    def solves(self, session_id: int) -> SolveList:
        """Return a session's solves.

        Args:
            session_id: The session.

        Returns:
            Its solve list.

        """
        return self.lists.setdefault(session_id, SolveList())
