"""Helpers that keep widgets from resizing when their text changes."""

from PySide6.QtWidgets import QPushButton


def reserve_width(button: QPushButton, *texts: str) -> None:
    """Fix a button's width to fit its widest label, so changing text doesn't resize it.

    Args:
        button: The button, already showing its initial text.
        *texts: Other labels the button may show later.

    """
    original = button.text()
    widths = [button.sizeHint().width()]
    for text in texts:
        button.setText(text)
        widths.append(button.sizeHint().width())
    button.setText(original)
    button.setFixedWidth(max(widths))
