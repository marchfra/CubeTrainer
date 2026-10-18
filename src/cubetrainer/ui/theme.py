"""The app's look: colours, fonts and the style sheet built from them.

A ``Theme`` is a small set of named values (two colour sets, light and dark, plus
fonts and a corner radius); the style sheet is generated from those values, so a
new look is a new ``Theme`` and nothing else. The app follows the system's light
or dark mode and re-applies the theme when it changes.
"""

import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

#: Where the bundled fonts are (SIL Open Font License, see OFL.txt there).
FONTS_DIR: Path = Path(__file__).parent / "fonts"


@dataclass(frozen=True, slots=True)
class Colors:
    """The colours of one appearance (light or dark) of a theme.

    Attributes:
        background: The window behind everything.
        surface: Panels: tables, cards, menus.
        raised: Buttons and other controls.
        raised_hover: Controls under the mouse.
        border: Outlines of panels and controls.
        border_strong: Scroll bar handles, pressed controls.
        divider: Lines between table rows.
        text: Main text.
        muted: Secondary text: labels, headers, units.
        faint: Hints and disabled text.
        accent: The one highlight colour (best times, default buttons, focus).
        accent_text: Text on the accent colour.
        danger: Mistakes and destructive actions.
        danger_soft: Background tint of the Mistake button.
        danger_border: Outline of the Mistake button.
        selection: Background of selected rows and menu items.

    """

    background: str
    surface: str
    raised: str
    raised_hover: str
    border: str
    border_strong: str
    divider: str
    text: str
    muted: str
    faint: str
    accent: str
    accent_text: str
    danger: str
    danger_soft: str
    danger_border: str
    selection: str


@dataclass(frozen=True, slots=True)
class Theme:
    """A named look: colours for light and dark mode, fonts and roundness.

    Attributes:
        name: Shown to the user.
        light: Colours in light mode.
        dark: Colours in dark mode.
        ui_font: Family of the interface text.
        mono_font: Family of times and moves (fixed-width digits).
        radius: Corner radius of panels, in pixels (controls use a smaller one).

    """

    name: str
    light: Colors
    dark: Colors
    ui_font: str
    mono_font: str
    radius: int


#: Soft panels on a near-black (or light grey) ground, one violet accent.
CALM: Theme = Theme(
    name="Calm",
    light=Colors(
        background="#f3f4f7",
        surface="#ffffff",
        raised="#ffffff",
        raised_hover="#f6f7fa",
        border="#e2e5eb",
        border_strong="#cfd3dc",
        divider="#eef0f4",
        text="#171a21",
        muted="#6a7184",
        faint="#b4b9c5",
        accent="#6b5cf0",
        accent_text="#ffffff",
        danger="#c4303f",
        danger_soft="rgba(212, 60, 76, 0.08)",
        danger_border="rgba(212, 60, 76, 0.35)",
        selection="rgba(107, 92, 240, 0.14)",
    ),
    dark=Colors(
        background="#0e1014",
        surface="#161920",
        raised="#1c2029",
        raised_hover="#232834",
        border="#252a35",
        border_strong="#343a48",
        divider="#1e222b",
        text="#e7e9ee",
        muted="#8b92a3",
        faint="#4a5060",
        accent="#8c7dff",
        accent_text="#0e1014",
        danger="#ff6b78",
        danger_soft="rgba(255, 92, 108, 0.12)",
        danger_border="rgba(255, 92, 108, 0.4)",
        selection="rgba(140, 125, 255, 0.22)",
    ),
    ui_font="Geist",
    mono_font="Geist Mono",
    radius=14,
)

#: The theme in use (a setting may choose another one later).
CURRENT: Theme = CALM


def is_dark() -> bool:
    """Return whether the system is in dark mode.

    Returns:
        True in dark mode.

    """
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def current_colors(theme: Theme = CURRENT) -> Colors:
    """Return a theme's colours for the system's current mode.

    Args:
        theme: The theme.

    Returns:
        Its dark colours in dark mode, else its light ones.

    """
    return theme.dark if is_dark() else theme.light


def mono_font(point_size: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Return the theme's fixed-width font, for times and moves.

    Args:
        point_size: Size in points.
        weight: Weight.

    Returns:
        The font.

    """
    font = QFont(CURRENT.mono_font)
    font.setPointSizeF(point_size)
    font.setWeight(weight)
    return font


def number_font(
    point_size: float,
    weight: QFont.Weight = QFont.Weight.Normal,
) -> QFont:
    """Return the theme's font for times: the UI font with fixed-width digits.

    The fixed-width font would do too, but its zero is slashed, which reads badly
    in a large time.

    Args:
        point_size: Size in points.
        weight: Weight.

    Returns:
        The font, with tabular figures so a running time doesn't jitter.

    """
    font = QFont(CURRENT.ui_font)
    font.setPointSizeF(point_size)
    font.setWeight(weight)
    font.setFeature(QFont.Tag("tnum"), 1)
    return font


def load_fonts() -> list[str]:
    """Register the bundled fonts with Qt (once is enough; repeats are harmless).

    Returns:
        The families registered.

    """
    families: set[str] = set()
    for path in sorted(FONTS_DIR.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        families.update(QFontDatabase.applicationFontFamilies(font_id))
    return sorted(families)


def palette_for(colors: Colors) -> QPalette:
    """Build a Qt palette from a theme's colours (for widgets the style sheet skips).

    Args:
        colors: The colours.

    Returns:
        The palette.

    """
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: colors.background,
        QPalette.ColorRole.WindowText: colors.text,
        QPalette.ColorRole.Base: colors.surface,
        QPalette.ColorRole.AlternateBase: colors.raised,
        QPalette.ColorRole.Text: colors.text,
        QPalette.ColorRole.Button: colors.raised,
        QPalette.ColorRole.ButtonText: colors.text,
        QPalette.ColorRole.ToolTipBase: colors.raised,
        QPalette.ColorRole.ToolTipText: colors.text,
        QPalette.ColorRole.PlaceholderText: colors.faint,
        QPalette.ColorRole.Highlight: colors.accent,
        QPalette.ColorRole.HighlightedText: colors.accent_text,
        QPalette.ColorRole.Accent: colors.accent,
        QPalette.ColorRole.Link: colors.accent,
        QPalette.ColorRole.Mid: colors.border,
        QPalette.ColorRole.Midlight: colors.border,
        QPalette.ColorRole.Dark: colors.border_strong,
    }
    for role, color in roles.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors.faint))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(colors.faint),
    )
    return palette


#: Small drawings the style sheet needs as files (a tick, chevrons), as SVG with a
#: ``{color}`` slot: style sheets can only show images, not draw them.
_ICONS: dict[str, str] = {
    "check": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
        '<path d="M3.5 8.5l3 3 6-7" fill="none" stroke="{color}" stroke-width="2.2"'
        ' stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "up": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">'
        '<path d="M3 7.5l3-3 3 3" fill="none" stroke="{color}" stroke-width="1.6"'
        ' stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
    "down": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">'
        '<path d="M3 4.5l3 3 3-3" fill="none" stroke="{color}" stroke-width="1.6"'
        ' stroke-linecap="round" stroke-linejoin="round"/></svg>'
    ),
}


@cache
def _icon_dir() -> Path:
    """Return a folder for this run's generated icons (made once).

    Returns:
        The folder.

    """
    return Path(tempfile.mkdtemp(prefix="cubetrainer-icons-"))


def icon_path(name: str, color: str) -> str:
    """Write one of the style sheet's icons in a colour, and return its path.

    Args:
        name: ``"check"``, ``"up"`` or ``"down"``.
        color: Its colour, e.g. ``"#6b5cf0"``.

    Returns:
        The SVG file's path, with forward slashes, for ``url(...)`` in a style sheet.

    """
    path = _icon_dir() / f"{name}-{color.lstrip('#')}.svg"
    if not path.exists():
        path.write_text(_ICONS[name].format(color=color), encoding="utf-8")
    return path.as_posix()


def style_sheet(colors: Colors, theme: Theme = CURRENT) -> str:
    """Build the app's style sheet from a theme's colours.

    Args:
        colors: The colours (light or dark).
        theme: The theme (for the radius).

    Returns:
        The style sheet.

    """
    c = colors
    r = theme.radius
    small = max(r - 6, 4)
    check = icon_path("check", c.accent_text)
    up, down = icon_path("up", c.muted), icon_path("down", c.muted)
    return f"""
QToolTip {{
    background: {c.raised}; color: {c.text};
    border: 1px solid {c.border}; border-radius: 6px; padding: 4px 8px;
}}
QPushButton {{
    background: {c.raised}; color: {c.text};
    border: 1px solid {c.border}; border-radius: {small}px;
    padding: 6px 12px; min-height: 18px;
}}
QPushButton:hover {{ background: {c.raised_hover}; border-color: {c.border_strong}; }}
QPushButton:pressed, QPushButton:checked {{ background: {c.border}; }}
QPushButton:disabled {{
    background: transparent; color: {c.faint}; border-color: {c.divider};
}}
QPushButton:default {{
    background: {c.accent}; color: {c.accent_text}; border-color: {c.accent};
}}
QPushButton[pill="true"] {{ border-radius: 14px; padding: 6px 14px; }}
QPushButton#dangerButton {{
    color: {c.danger}; background: {c.danger_soft}; border-color: {c.danger_border};
}}
QPushButton#dangerButton:hover {{ border-color: {c.danger}; }}
QPushButton#mistakeButton {{
    color: {c.danger}; background: {c.danger_soft};
    border-color: {c.danger_border}; font-weight: 600;
}}
QPushButton#mistakeButton:hover {{ border-color: {c.danger}; }}
QPushButton#mistakeButton:checked {{
    color: #ffffff; background: {c.danger}; border-color: {c.danger};
}}
QTabWidget::pane {{ border: none; }}
QTabWidget::tab-bar {{ alignment: center; }}
QTabBar::tab {{
    background: transparent; color: {c.muted};
    padding: 6px 18px; margin: 6px 2px; border-radius: {small}px;
}}
QTabBar::tab:hover {{ color: {c.text}; }}
QTabBar::tab:selected {{ background: {c.raised}; color: {c.text}; }}
QTableView {{
    background: {c.surface}; color: {c.text};
    border: 1px solid {c.border}; border-radius: {r}px;
    gridline-color: {c.divider};
    selection-background-color: {c.selection}; selection-color: {c.text};
    outline: none;
}}
QTableView::item {{ border-bottom: 1px solid {c.divider}; padding: 0 6px; }}
QTableView::item:selected {{ background: {c.selection}; color: {c.text}; }}
QHeaderView {{ background: transparent; border: none; }}
QHeaderView::section {{
    background: {c.surface}; color: {c.muted};
    border: none; border-bottom: 1px solid {c.border};
    padding: 7px 6px; font-size: 11px;
}}
QTableCornerButton::section {{ background: {c.surface}; border: none; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 6px 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px 6px; }}
QScrollBar::handle {{ background: {c.border_strong}; border-radius: 3px; }}
QScrollBar::handle:vertical {{ min-height: 30px; }}
QScrollBar::handle:horizontal {{ min-width: 30px; }}
QScrollBar::handle:hover {{ background: {c.muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QMenu {{
    background: {c.surface}; color: {c.text};
    border: 1px solid {c.border}; border-radius: {small}px; padding: 5px;
}}
QMenu::item {{ padding: 6px 22px 6px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c.selection}; }}
QMenu::item:disabled {{ color: {c.faint}; }}
QMenu::separator {{ height: 1px; background: {c.border}; margin: 5px 8px; }}
QLineEdit, QPlainTextEdit, QTextEdit {{
    background: {c.surface}; color: {c.text};
    border: 1px solid {c.border}; border-radius: {small}px; padding: 4px 8px;
    selection-background-color: {c.selection}; selection-color: {c.text};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border-color: {c.accent};
}}
QCheckBox, QRadioButton {{ spacing: 8px; color: {c.text}; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {c.faint}; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px; height: 14px;
    border: 1.5px solid {c.border_strong}; background: {c.surface};
}}
QCheckBox::indicator {{ border-radius: 5px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border-color: {c.accent};
}}
QCheckBox::indicator:checked {{
    background: {c.accent}; border-color: {c.accent}; image: url({check});
}}
QRadioButton::indicator:checked {{
    background: {c.accent_text}; border: 5px solid {c.accent};
    width: 7px; height: 7px;
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    border-color: {c.divider}; background: transparent;
}}
QComboBox {{ combobox-popup: 0; }}
QAbstractSpinBox, QComboBox {{
    background: {c.surface}; color: {c.text};
    border: 1px solid {c.border}; border-radius: {small}px;
    padding: 6px 24px 6px 10px; min-height: 18px;
    selection-background-color: {c.selection}; selection-color: {c.text};
}}
QAbstractSpinBox:hover, QComboBox:hover {{ border-color: {c.border_strong}; }}
QAbstractSpinBox:focus, QComboBox:focus {{ border-color: {c.accent}; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 18px; border: none; background: transparent;
}}
QAbstractSpinBox::up-button {{
    subcontrol-position: top right; margin: 3px 4px 0 0; border-radius: 4px;
}}
QAbstractSpinBox::down-button {{
    subcontrol-position: bottom right; margin: 0 4px 3px 0; border-radius: 4px;
}}
QAbstractSpinBox::up-button:hover, QAbstractSpinBox::down-button:hover {{
    background: {c.raised_hover};
}}
QAbstractSpinBox::up-arrow {{ image: url({up}); width: 10px; height: 10px; }}
QAbstractSpinBox::down-arrow {{ image: url({down}); width: 10px; height: 10px; }}
QComboBox::drop-down {{
    subcontrol-origin: border; subcontrol-position: center right;
    width: 20px; border: none;
}}
QComboBox::down-arrow {{ image: url({down}); width: 10px; height: 10px; }}
QComboBox QAbstractItemView {{
    background: transparent; color: {c.text}; border: none; margin: 1px;
    selection-background-color: {c.selection}; selection-color: {c.text};
    outline: none; padding: 4px;
}}
QComboBox QAbstractItemView::item {{
    padding: 5px 8px; min-height: 20px; border-radius: 6px;
}}
QGroupBox {{
    background: {c.surface}; border: 1px solid {c.border}; border-radius: {r}px;
    margin-top: 22px; padding: 12px 10px 10px 10px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; subcontrol-position: top left;
    left: 4px; padding: 0 2px; color: {c.muted};
}}
QWidget#card {{
    background: {c.surface}; border: 1px solid {c.border}; border-radius: {r}px;
}}
QLabel#muted {{ color: {c.muted}; }}
QLabel#best {{ color: {c.accent}; }}
"""


def apply_theme(
    app: QApplication,
    theme: Theme = CURRENT,
    *,
    dark: bool | None = None,
) -> None:
    """Give the whole app a theme's look, in light or dark mode.

    Args:
        app: The application.
        theme: The theme.
        dark: Dark mode or not; None follows the system.

    """
    load_fonts()
    colors = theme.dark if (is_dark() if dark is None else dark) else theme.light
    font = QFont(theme.ui_font)
    font.setPointSizeF(13)
    app.setFont(font)
    app.setPalette(palette_for(colors))
    app.setStyleSheet(style_sheet(colors, theme))


def follow_system_mode(app: QApplication, theme: Theme = CURRENT) -> None:
    """Apply a theme now and again whenever the system switches light/dark mode.

    Args:
        app: The application.
        theme: The theme.

    """
    apply_theme(app, theme)
    QGuiApplication.styleHints().colorSchemeChanged.connect(
        lambda _scheme: apply_theme(app, theme),
    )
