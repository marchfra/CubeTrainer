"""Shared pytest configuration."""

import os

import pytest

from tests.helpers import FakeClock

# Run Qt headless unless told otherwise: no windows pop up during tests and keyboard
# focus doesn't depend on which app is in front. Set QT_QPA_PLATFORM to override.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def clock() -> FakeClock:
    """Provide a fresh fake clock starting at zero.

    Returns:
        The clock.

    """
    return FakeClock()
