"""Main application window with the Timer, Learn and Stats tabs."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMainWindow, QTabWidget, QWidget

#: Titles of the top-level tabs, in display order.
TAB_TITLES: tuple[str, ...] = ("Timer", "Learn", "Stats")


def _placeholder(text: str) -> QWidget:
    """Build a centred label used for tabs that are not implemented yet.

    Args:
        text: Message shown in the middle of the tab.

    Returns:
        The placeholder widget.

    """
    label = QLabel(text)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label


class MainWindow(QMainWindow):
    """Top-level window hosting one tab per app section.

    Attributes:
        tabs: The tab widget holding the Timer, Learn and Stats pages.

    """

    def __init__(self) -> None:
        """Create the window and its (for now, placeholder) tabs."""
        super().__init__()
        self.setWindowTitle("CubeTrainer")
        self.resize(1100, 720)

        self.tabs: QTabWidget = QTabWidget()
        for title in TAB_TITLES:
            self.tabs.addTab(_placeholder(f"{title} — coming soon"), title)
        self.setCentralWidget(self.tabs)
