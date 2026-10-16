"""Key-value settings, kept in the database or (for tests) in memory."""

from dataclasses import dataclass, field
from typing import Protocol


class Settings(Protocol):
    """Somewhere to keep simple settings (``Database`` is one)."""

    def get_setting(self, key: str) -> str | None:
        """Read a setting.

        Args:
            key: The setting's name.

        Returns:
            Its value, or None if it was never set.

        """
        ...

    def set_setting(self, key: str, value: str) -> None:
        """Store a setting.

        Args:
            key: The setting's name.
            value: Its new value.

        """
        ...


@dataclass(slots=True)
class MemorySettings:
    """Settings kept in a dictionary (nothing is saved).

    Attributes:
        values: The settings, by name.

    """

    values: dict[str, str] = field(default_factory=dict)

    def get_setting(self, key: str) -> str | None:
        """Read a setting.

        Args:
            key: The setting's name.

        Returns:
            Its value, or None if it was never set.

        """
        return self.values.get(key)

    def set_setting(self, key: str, value: str) -> None:
        """Store a setting.

        Args:
            key: The setting's name.
            value: Its new value.

        """
        self.values[key] = value


def get_flag(settings: Settings, key: str, *, default: bool) -> bool:
    """Read an on/off setting.

    Args:
        settings: Where settings are kept.
        key: The setting's name.
        default: The value when it was never set.

    Returns:
        The flag.

    """
    value = settings.get_setting(key)
    return default if value is None else value == "1"


def set_flag(settings: Settings, key: str, *, value: bool) -> None:
    """Store an on/off setting.

    Args:
        settings: Where settings are kept.
        key: The setting's name.
        value: The flag.

    """
    settings.set_setting(key, "1" if value else "0")
