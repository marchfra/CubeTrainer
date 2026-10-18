"""Shared pytest configuration."""

import gc
import os
from collections.abc import Iterator

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

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


@pytest.fixture(autouse=True)
def _destroy_leftover_widgets(qapp: QApplication) -> Iterator[None]:
    """Destroy each test's windows before the next test starts.

    pytest-qt only holds a test's windows weakly once it returns, so they would be
    destroyed whenever the garbage collector next runs: possibly in the middle of a
    later test, while Qt is walking through every widget (e.g. restyling after a
    theme switch), which crashes. Collecting now, and letting Qt finish the
    deletions, keeps that from happening. Set up first, so it runs after
    pytest-qt has closed the windows. Objects alive after a cleanup are frozen
    (never collected again in this test session), which keeps it fast.

    Args:
        qapp: The application.

    Yields:
        Nothing.

    """
    yield
    if not qapp.topLevelWidgets():
        return  # nothing to destroy: skip the (slow) full collection
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    # What's left is long-lived (modules, caches): set it aside, so the next
    # collection only looks at what later tests create, and stays quick.
    gc.freeze()
