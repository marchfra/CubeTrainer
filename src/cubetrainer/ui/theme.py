"""The app's look: themes, light/dark mode, and the style sheet built from them.

A ``Theme`` is a small set of named values (two colour sets, light and dark, plus
fonts, a corner radius and two traits: flat panels, a coloured timer card); the
style sheet is generated from those values. Three themes ship (Calm, Clean, Bold);
the user picks one, and light, dark or the system's mode, in the Settings window.

Widgets with a special font (times, moves) register a font *role* with
``set_theme_font``, so switching themes gives them the new theme's fonts too.
"""

import tempfile
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from cubetrainer.settings import Settings

#: Where the bundled fonts are (SIL Open Font License, see the OFL files there).
FONTS_DIR: Path = Path(__file__).parent / "fonts"

#: Font family meaning "the system's interface font" (San Francisco on macOS).
SYSTEM_FONT: str = ""


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
        success: Positive state, e.g. the timer when it's ready to start.
        card: The timer card's colour (timer card themes), if not the accent: white
            text on it must stay readable.
        sidebar: Tint of the side columns, painted edge to edge ("" for none).
        toolbar: Tint of the header row ("" for none).
        hairline: Lines between the toolbar, the sidebars and the middle.

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
    success: str
    card: str = ""
    sidebar: str = ""
    toolbar: str = ""
    hairline: str = ""

    @property
    def timer_card(self) -> str:
        """The timer card's colour: ``card``, or the accent if it has none."""
        return self.card or self.accent


@dataclass(frozen=True, slots=True)
class Theme:
    """A named look: colours for light and dark mode, fonts, roundness and traits.

    Attributes:
        name: Shown to the user.
        description: One line about the look, for the Settings window.
        light: Colours in light mode.
        dark: Colours in dark mode.
        ui_font: Family of the interface text and times (``SYSTEM_FONT`` for the
            system's).
        mono_font: Family of scrambles and moves (must be fixed-width: hidden
            moves are masked with dots of the same width).
        mono_fallbacks: Families to try, in order, when ``mono_font`` isn't
            installed (e.g. system fonts of other systems); the bundled
            ``Geist Mono`` comes last.
        radius: Corner radius of panels, in pixels (controls use a smaller one).
        timer_weight: Weight of the big time.
        flat: Panels without boxes: tables and cards on the background, separated
            by hairlines.
        timer_card: The timer is a card in the accent colour that turns red while
            held and green when ready (instead of the time changing colour).

    """

    name: str
    description: str
    light: Colors
    dark: Colors
    ui_font: str
    mono_font: str
    radius: int
    timer_weight: QFont.Weight = QFont.Weight.Light
    flat: bool = False
    timer_card: bool = False
    mono_fallbacks: tuple[str, ...] = ()


#: Soft panels on a near-black (or light grey) ground, one violet accent.
CALM: Theme = Theme(
    name="Calm",
    description="Soft rounded panels, one violet accent",
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
        success="#30a46c",
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
        success="#3dd68c",
    ),
    ui_font="Geist",
    mono_font="Geist Mono",
    radius=14,
)

#: Like a Mac app: the system font, flat panels with hairlines, system blue.
CLEAN: Theme = Theme(
    name="Clean",
    description="Like a Mac app: sidebars, hairlines, the system font",
    light=Colors(
        background="#ffffff",
        surface="#ffffff",
        raised="#ffffff",
        raised_hover="#f5f5f7",
        border="#d2d2d7",
        border_strong="#c7c7cc",
        divider="#ececee",
        text="#1d1d1f",
        muted="#7a7a7f",
        faint="#c7c7cc",
        accent="#0071e3",
        accent_text="#ffffff",
        danger="#d70015",
        danger_soft="rgba(215, 0, 21, 0.06)",
        danger_border="rgba(215, 0, 21, 0.3)",
        selection="rgba(0, 113, 227, 0.12)",
        success="#248a3d",
        sidebar="#f6f6f7",
        toolbar="#fbfbfc",
        hairline="#e5e5e7",
    ),
    dark=Colors(
        background="#1e1e1e",
        surface="#1e1e1e",
        raised="#48484a",
        raised_hover="#545456",
        border="#48484a",
        border_strong="#636366",
        divider="#323234",
        text="#f5f5f7",
        muted="#98989d",
        faint="#545456",
        accent="#0a84ff",
        accent_text="#ffffff",
        danger="#ff6961",
        danger_soft="rgba(255, 105, 97, 0.14)",
        danger_border="rgba(255, 105, 97, 0.45)",
        selection="rgba(10, 132, 255, 0.25)",
        success="#30d158",
        sidebar="#252527",
        toolbar="#2a2a2c",
        hairline="#000000",
    ),
    ui_font=SYSTEM_FONT,
    mono_font="Menlo",
    # Menlo is macOS's: Windows and Linux have their own fixed-width fonts.
    mono_fallbacks=("Consolas", "DejaVu Sans Mono", "Liberation Mono"),
    radius=6,
    timer_weight=QFont.Weight.Thin,
    flat=True,
)

#: Space Grotesk, soft borderless panels, and the timer as a coloured card.
BOLD: Theme = Theme(
    name="Bold",
    description="The timer is a big coloured card",
    light=Colors(
        background="#eceef2",
        surface="#ffffff",
        raised="#ffffff",
        raised_hover="#f4f5f8",
        border="#e3e6ec",
        border_strong="#cfd3dc",
        divider="#f0f1f4",
        text="#12131a",
        muted="#646a78",
        faint="#a3a8b5",
        accent="#2f4bff",
        accent_text="#ffffff",
        danger="#c8283a",
        danger_soft="rgba(200, 40, 58, 0.08)",
        danger_border="rgba(200, 40, 58, 0.4)",
        selection="rgba(47, 75, 255, 0.12)",
        success="#16a34a",
    ),
    dark=Colors(
        background="#0b0c10",
        surface="#16181f",
        raised="#1f222b",
        raised_hover="#272b36",
        border="#23262f",
        border_strong="#343845",
        divider="#1f222b",
        text="#eef0f5",
        muted="#8a90a0",
        faint="#4b505d",
        accent="#5b74ff",
        accent_text="#ffffff",
        danger="#ff7d8a",
        danger_soft="rgba(255, 92, 108, 0.12)",
        danger_border="rgba(255, 92, 108, 0.4)",
        selection="rgba(91, 116, 255, 0.22)",
        success="#22c55e",
        card="#3d5afe",  # the accent is lighter, for blue text on the dark ground
    ),
    ui_font="Space Grotesk",
    mono_font="Space Mono",
    radius=18,
    timer_weight=QFont.Weight.DemiBold,
    timer_card=True,
)

#: Every theme, by name, in the order the Settings window lists them.
THEMES: dict[str, Theme] = {theme.name: theme for theme in (CALM, CLEAN, BOLD)}


class Appearance(StrEnum):
    """Light or dark mode: the system's, or always one of them."""

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


#: Setting names for the user's choices.
THEME_SETTING: str = "app.theme"
APPEARANCE_SETTING: str = "app.appearance"

#: The theme in use (changed by ``use_theme``).
CURRENT: Theme = CALM

#: The light/dark choice in use (changed by ``use_theme``).
APPEARANCE: Appearance = Appearance.SYSTEM


def is_dark() -> bool:
    """Return whether the app is in dark mode (forced by the user, or the system's).

    Returns:
        True in dark mode.

    """
    if APPEARANCE is not Appearance.SYSTEM:
        return APPEARANCE is Appearance.DARK
    return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark


def current_colors(theme: Theme | None = None) -> Colors:
    """Return a theme's colours for the current mode.

    Args:
        theme: The theme; the one in use if omitted.

    Returns:
        Its dark colours in dark mode, else its light ones.

    """
    theme = theme or CURRENT
    return theme.dark if is_dark() else theme.light


def _family(name: str) -> str:
    """Resolve a theme's font family (``SYSTEM_FONT`` means the system's).

    Args:
        name: A family, or ``SYSTEM_FONT``.

    Returns:
        A family Qt knows.

    """
    if name == SYSTEM_FONT:
        return QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
    return name


#: The fixed-width font that ships with the app, the last resort.
BUNDLED_MONO: str = "Geist Mono"


def mono_family(theme: Theme | None = None) -> str:
    """Return the first of a theme's fixed-width fonts that is installed.

    Args:
        theme: The theme; the one in use if omitted.

    Returns:
        The family: ``mono_font``, else the first installed fallback, else the
        bundled ``Geist Mono``.

    """
    theme = theme or CURRENT
    installed = set(QFontDatabase.families())
    for family in (theme.mono_font, *theme.mono_fallbacks):
        if family in installed:
            return family
    return BUNDLED_MONO


class FontRole(StrEnum):
    """What a font is for; each theme says which family and weight that means."""

    UI = "ui"  # interface text
    NUMBER = "number"  # times and statistics: the UI font with fixed-width digits
    TIMER = "timer"  # the big time: like NUMBER, in the theme's timer weight
    MONO = "mono"  # scrambles and moves: fixed-width


def theme_font(
    role: FontRole,
    point_size: float,
    weight: QFont.Weight = QFont.Weight.Normal,
) -> QFont:
    """Return the current theme's font for a role.

    Args:
        role: What the font is for.
        point_size: Size in points.
        weight: Weight (ignored for ``TIMER``, which uses the theme's).

    Returns:
        The font. Times get tabular figures, so a running time doesn't jitter.

    """
    family = mono_family() if role is FontRole.MONO else _family(CURRENT.ui_font)
    font = QFont(family)
    font.setPointSizeF(point_size)
    font.setWeight(CURRENT.timer_weight if role is FontRole.TIMER else weight)
    if role in {FontRole.NUMBER, FontRole.TIMER}:
        font.setFeature(QFont.Tag("tnum"), 1)
    return font


#: Property holding a widget's font role, size and weight (see set_theme_font).
_FONT_PROPERTY: str = "themeFont"


def set_theme_font(
    widget: QWidget,
    role: FontRole,
    point_size: float,
    weight: QFont.Weight = QFont.Weight.Normal,
) -> None:
    """Give a widget the theme's font for a role, now and after theme switches.

    Args:
        widget: The widget.
        role: What its font is for.
        point_size: Size in points.
        weight: Weight.

    """
    widget.setProperty(_FONT_PROPERTY, f"{role.value}:{point_size}:{weight.value}")
    widget.setFont(theme_font(role, point_size, weight))


def _refresh_theme_fonts(app: QApplication) -> None:
    """Re-apply the registered font roles after a theme switch.

    Args:
        app: The application.

    """
    for widget in app.allWidgets():
        spec = widget.property(_FONT_PROPERTY)
        if isinstance(spec, str):
            role, size, weight = spec.split(":")
            widget.setFont(
                theme_font(FontRole(role), float(size), QFont.Weight(int(weight))),
            )


def mono_font(point_size: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    """Return the current theme's fixed-width font, for scrambles and moves.

    Args:
        point_size: Size in points.
        weight: Weight.

    Returns:
        The font.

    """
    return theme_font(FontRole.MONO, point_size, weight)


def number_font(
    point_size: float,
    weight: QFont.Weight = QFont.Weight.Normal,
) -> QFont:
    """Return the current theme's font for times: the UI font with fixed-width digits.

    Args:
        point_size: Size in points.
        weight: Weight.

    Returns:
        The font, with tabular figures so a running time doesn't jitter.

    """
    return theme_font(FontRole.NUMBER, point_size, weight)


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


def style_sheet(colors: Colors, theme: Theme | None = None) -> str:
    """Build the app's style sheet from a theme's colours.

    Args:
        colors: The colours (light or dark).
        theme: The theme (radius, traits); the one in use if omitted.

    Returns:
        The style sheet.

    """
    theme = theme or CURRENT
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
/* Indicators are 16 px whether checked or not, in whole pixels (a fractional
   border rounds differently per state and nudges the label sideways). */
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px; height: 14px;
    border: 1px solid {c.border_strong}; background: {c.surface};
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
    width: 6px; height: 6px;
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
QLabel#onCard {{ color: rgba(255, 255, 255, 0.8); }}
QLabel#best {{ color: {c.accent}; }}
""" + (_flat_rules(c) if theme.flat else "")


def _flat_rules(c: Colors) -> str:
    """Return the rules that flatten panels (the ``flat`` trait).

    Tables, cards and group boxes lose their boxes and sit on the background;
    hairlines separate them instead.

    Args:
        c: The colours.

    Returns:
        Style sheet rules, applied after (and so over) the boxed ones.

    """
    return f"""
QTableView {{
    background: transparent; border: none; border-radius: 0;
    border-top: 1px solid {c.border}; border-bottom: 1px solid {c.border};
}}
QHeaderView::section {{ background: transparent; }}
QTableCornerButton::section {{ background: transparent; }}
QWidget#card {{
    background: transparent; border: none; border-radius: 0;
    border-bottom: 1px solid {c.divider};
}}
QGroupBox {{
    background: transparent; border: none; border-radius: 0;
    border-top: 1px solid {c.border};
}}
"""


def apply_theme(
    app: QApplication,
    theme: Theme | None = None,
    *,
    dark: bool | None = None,
) -> None:
    """Give the whole app a theme's look, in light or dark mode.

    Args:
        app: The application.
        theme: The theme; the one in use if omitted (else it becomes the one in
            use).
        dark: Dark mode or not; None follows the current mode.

    """
    global CURRENT  # noqa: PLW0603 - the app has one theme at a time
    load_fonts()
    if theme is not None:
        CURRENT = theme
    theme = CURRENT
    colors = theme.dark if (is_dark() if dark is None else dark) else theme.light
    font = QFont(_family(theme.ui_font))
    font.setPointSizeF(13)
    app.setFont(font)
    app.setPalette(palette_for(colors))
    app.setStyleSheet(style_sheet(colors, theme))
    _refresh_theme_fonts(app)


#: Qt colour scheme for each appearance (Unknown: the system's).
_SCHEMES: dict[Appearance, Qt.ColorScheme] = {
    Appearance.SYSTEM: Qt.ColorScheme.Unknown,
    Appearance.LIGHT: Qt.ColorScheme.Light,
    Appearance.DARK: Qt.ColorScheme.Dark,
}


def use_theme(app: QApplication, theme: Theme, appearance: Appearance) -> None:
    """Switch the app to a theme and a light/dark choice.

    The choice also goes to Qt, so native parts (title bar, dialogs) follow it.

    Args:
        app: The application.
        theme: The theme.
        appearance: Light, dark, or the system's mode.

    """
    global APPEARANCE  # noqa: PLW0603 - the app has one appearance at a time
    APPEARANCE = appearance
    app.styleHints().setColorScheme(_SCHEMES[appearance])
    apply_theme(app, theme)


def saved_choice(settings: Settings) -> tuple[Theme, Appearance]:
    """Return the theme and light/dark choice saved in the settings.

    Args:
        settings: Where they're kept.

    Returns:
        The theme and appearance (Calm and the system's mode if never chosen, or
        if what's saved is unknown).

    """
    theme = THEMES.get(settings.get_setting(THEME_SETTING) or "", CALM)
    try:
        appearance = Appearance(settings.get_setting(APPEARANCE_SETTING) or "")
    except ValueError:
        appearance = Appearance.SYSTEM
    return theme, appearance


def save_choice(settings: Settings, theme: Theme, appearance: Appearance) -> None:
    """Remember the theme and light/dark choice.

    Args:
        settings: Where to keep them.
        theme: The theme.
        appearance: The appearance.

    """
    settings.set_setting(THEME_SETTING, theme.name)
    settings.set_setting(APPEARANCE_SETTING, appearance.value)


def follow_system_mode(app: QApplication, settings: Settings | None = None) -> None:
    """Apply the saved theme now, and again whenever light/dark mode changes.

    Args:
        app: The application.
        settings: Where the user's choice is saved; Calm and the system's mode if
            omitted.

    """
    if settings is None:
        use_theme(app, CALM, Appearance.SYSTEM)
    else:
        use_theme(app, *saved_choice(settings))
    QGuiApplication.styleHints().colorSchemeChanged.connect(
        lambda _scheme: apply_theme(app),
    )
