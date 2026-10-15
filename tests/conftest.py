"""Shared pytest configuration."""

import os

# Run Qt headless unless told otherwise: no windows pop up during tests and keyboard
# focus doesn't depend on which app is in front. Set QT_QPA_PLATFORM to override.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
