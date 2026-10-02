"""Design tokens and the single Qt style sheet used by the whole app.

No third-party theme library is involved: colours live in two plain dicts, the
dark/light choice comes from Qt's own ``QStyleHints.colorScheme()``, and every
control is styled from the generated style sheet below.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette

ACCENT = "#4f8ef7"

_LIGHT = {
    "window": "#f3f5fa",
    "surface": "#ffffff",
    "sidebar": "#ffffff",
    "card": "#ffffff",
    "card_hover": "#fbfcfe",
    "text": "#101828",
    "text_secondary": "#475467",
    "text_muted": "#98a2b3",
    "border": "#e4e7ec",
    "border_strong": "#d0d5dd",
    "accent": ACCENT,
    "accent_hover": "#3d7ce8",
    "accent_pressed": "#3369cc",
    "accent_soft": "#eaf1fe",
    "accent_soft_hover": "#dbe8fd",
    "on_accent": "#ffffff",
    "success": "#12b76a",
    "success_soft": "#e7f8f0",
    "error": "#f04438",
    "error_soft": "#feecea",
    "warning": "#f79009",
    "warning_soft": "#fef3e2",
    "input_bg": "#ffffff",
    "hover": "#f2f4f7",
    "pressed": "#e9ecf2",
    "disabled_bg": "#eef0f4",
    "disabled_text": "#a9b1bd",
    "scrollbar": "#cdd5e0",
    "gradient_from": "#4f8ef7",
    "gradient_to": "#38bdf8",
}

_DARK = {
    "window": "#131519",
    "surface": "#16191e",
    "sidebar": "#16191e",
    "card": "#1c2026",
    "card_hover": "#212630",
    "text": "#f2f4f7",
    "text_secondary": "#b3bcc8",
    "text_muted": "#7c8794",
    "border": "#282d35",
    "border_strong": "#3a4048",
    "accent": "#6ba1ff",
    "accent_hover": "#83b1ff",
    "accent_pressed": "#5a92f0",
    "accent_soft": "#1c293d",
    "accent_soft_hover": "#22334b",
    "on_accent": "#0b1220",
    "success": "#3ddc97",
    "success_soft": "#12301f",
    "error": "#ff7a70",
    "error_soft": "#3a1c1a",
    "warning": "#ffc46b",
    "warning_soft": "#3a2a12",
    "input_bg": "#191d23",
    "hover": "#22262e",
    "pressed": "#2a2f38",
    "disabled_bg": "#22262e",
    "disabled_text": "#5c646f",
    "scrollbar": "#39414b",
    "gradient_from": "#5b93ff",
    "gradient_to": "#38bdf8",
}

_FONT_CANDIDATES = {
    "win32": ["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI Variable Text", "Segoe UI"],
    "darwin": ["PingFang SC", "SF Pro Text", "Helvetica Neue"],
    "linux": [
        "Noto Sans CJK SC", "Noto Sans SC", "Source Han Sans SC",
        "Noto Sans", "Sarasa Gothic SC", "DejaVu Sans",
    ],
}


def _pick_font():
    """Choose the nicest available UI font for the running platform."""
    import sys

    key = "win32" if sys.platform.startswith("win") else (
        "darwin" if sys.platform == "darwin" else "linux"
    )
    available = set(QFontDatabase.families())
    for name in _FONT_CANDIDATES.get(key, []):
        if name in available:
            return name
    for name in ["Noto Sans", "DejaVu Sans", "Arial", "Helvetica"]:
        if name in available:
            return name
    return QFont().family()


class Theme:
    """Holds the active colour tokens and applies them to the application."""

    colors = dict(_LIGHT)
    dark = False
    font_family = ""

    # ── detection / application ─────────────────────────────────
    @classmethod
    def _detect_dark(cls, app):
        scheme = app.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
        window = app.palette().color(QPalette.ColorRole.Window)
        return window.lightness() < 128

    @classmethod
    def apply(cls, app):
        cls.dark = cls._detect_dark(app)
        cls.colors = dict(_DARK if cls.dark else _LIGHT)
        cls.font_family = _pick_font()

        font = QFont(cls.font_family)
        font.setPixelSize(14)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        app.setFont(font)
        app.setStyleSheet(cls.stylesheet())

    # ── helpers ─────────────────────────────────────────────────
    @classmethod
    def color(cls, name):
        return QColor(cls.colors[name])

    @classmethod
    def shadow_color(cls, alpha=38):
        base = (0, 0, 0) if cls.dark else (15, 23, 42)
        return QColor(base[0], base[1], base[2], alpha)

    @classmethod
    def stylesheet(cls):
        c = cls.colors
        # NOTE: no ``* { font-family/size }`` rule here — a global font rule
        # would override the icon font that IconButton/IconLabel set per widget.
        return f"""
QWidget {{ color: {c['text']}; }}
QWidget:focus {{ outline: none; }}

QMainWindow, QDialog, QMessageBox {{ background: {c['window']}; }}
QWidget#PageSurface, QScrollArea > QWidget > QWidget#PageSurface {{ background: {c['window']}; }}
QWidget#Transparent {{ background: transparent; }}

QLabel {{ background: transparent; }}
QLabel#Brand {{ font-size: 21px; font-weight: 700; }}
QLabel#BrandTag {{ color: {c['text_muted']}; font-size: 11px; }}
QLabel#PageTitle {{ font-size: 26px; font-weight: 700; }}
QLabel#PageSubtitle {{ color: {c['text_secondary']}; font-size: 14px; }}
QLabel#CardTitle {{ font-size: 16px; font-weight: 600; }}
QLabel#SectionTitle {{ font-size: 15px; font-weight: 600; }}
QLabel#Muted {{ color: {c['text_secondary']}; }}
QLabel#Hint {{ color: {c['text_muted']}; font-size: 12px; }}
QLabel#Success {{ color: {c['success']}; }}
QLabel#Error {{ color: {c['error']}; }}
QLabel#Accent {{ color: {c['accent']}; }}
QFrame#Sidebar {{
    background: {c['sidebar']};
    border-right: 1px solid {c['border']};
}}
QFrame#Card, QFrame#CardHover {{
    background: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 14px;
}}
QFrame#CardHover:hover {{
    background: {c['card_hover']};
    border: 1px solid {c['border_strong']};
}}
QFrame#ToastHost {{ background: transparent; border: none; }}
QFrame#Inset {{
    background: {c['hover']};
    border: 1px solid {c['border']};
    border-radius: 12px;
}}
QFrame#Divider {{ background: {c['border']}; max-height: 1px; border: none; }}
QFrame#NavIndicator {{ background: {c['accent']}; border-radius: 2px; }}
QFrame#Toast {{
    background: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 12px;
}}

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox {{
    background: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 8px 12px;
    color: {c['text']};
    selection-background-color: {c['accent']};
    selection-color: {c['on_accent']};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover {{ border-color: {c['border_strong']}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus {{
    border: 1px solid {c['accent']};
    background: {c['input_bg']};
}}
QLineEdit:disabled, QTextEdit:disabled {{ color: {c['disabled_text']}; }}

QComboBox {{
    background: {c['input_bg']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 9px 36px 9px 40px;
    color: {c['text']};
}}
QComboBox:hover {{ border-color: {c['border_strong']}; }}
QComboBox:focus {{ border: 1px solid {c['accent']}; }}
QComboBox::drop-down {{ border: none; width: 34px; }}
QComboBox::down-arrow {{ image: none; width: 0; height: 0; }}
QComboBox QAbstractItemView {{
    background: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 6px;
    outline: none;
    selection-background-color: {c['accent_soft']};
    selection-color: {c['text']};
}}
QComboBox QAbstractItemView::item {{ min-height: 30px; padding: 4px 8px; border-radius: 6px; }}

QProgressBar {{
    border: none;
    border-radius: 6px;
    background: {c['border']};
    min-height: 9px;
    max-height: 9px;
}}
QProgressBar::chunk {{ border-radius: 6px; background: {c['accent']}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 3px 2px; }}
QScrollBar::handle:vertical {{
    background: {c['scrollbar']}; border-radius: 4px; min-height: 36px;
}}
QScrollBar::handle:vertical:hover {{ background: {c['border_strong']}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px 3px; }}
QScrollBar::handle:horizontal {{
    background: {c['scrollbar']}; border-radius: 4px; min-width: 36px;
}}
QScrollBar::handle:horizontal:hover {{ background: {c['border_strong']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{
    background: {c['card']};
    color: {c['text']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 5px 8px;
}}
QMenu {{
    background: {c['card']};
    border: 1px solid {c['border']};
    border-radius: 10px;
    padding: 6px;
}}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {c['accent_soft']}; }}

QCheckBox, QRadioButton {{ spacing: 8px; background: transparent; }}
QMessageBox {{ background: {c['window']}; }}
"""
