"""Browsable history of generated scrambles (backs the ◀ / ▶ buttons)."""

from collections.abc import Callable


class ScrambleHistory:
    """A list of scrambles with a cursor, generating new ones on demand.

    Attributes:
        scrambles: Every scramble generated so far, oldest first.
        index: Position of the current scramble in ``scrambles``.

    """

    def __init__(self, generate: Callable[[], str]) -> None:
        """Create the history with one freshly generated scramble.

        Args:
            generate: Function returning a new scramble each time it's called.

        """
        self._generate: Callable[[], str] = generate
        self.scrambles: list[str] = [generate()]
        self.index: int = 0

    @property
    def current(self) -> str:
        """The scramble currently shown."""
        return self.scrambles[self.index]

    @property
    def can_go_back(self) -> bool:
        """Whether there is an earlier scramble to go back to."""
        return self.index > 0

    def previous(self) -> str:
        """Move to the previous scramble (stays put at the first one).

        Returns:
            The new current scramble.

        """
        self.index = max(self.index - 1, 0)
        return self.current

    def next(self) -> str:
        """Move to the next scramble, generating one if at the end of the list.

        Returns:
            The new current scramble.

        """
        if self.index == len(self.scrambles) - 1:
            self.scrambles.append(self._generate())
        self.index += 1
        return self.current

    def new(self) -> str:
        """Jump to a brand-new scramble at the end of the list (used after a solve).

        Returns:
            The new current scramble.

        """
        self.scrambles.append(self._generate())
        self.index = len(self.scrambles) - 1
        return self.current
