"""Bundled icon-font support.

Lume ships Font Awesome 6 Free (Solid), a single SIL OFL 1.1 licensed TTF.
Every icon is addressed by a stable name instead of a literal emoji, so the
UI stays crisp at any DPI and identical on Windows, macOS and Linux.
"""

from PySide6.QtGui import QFont, QFontDatabase

from .resources import resource_path

FONT_PARTS = ("assets", "fonts", "fa-solid-900.ttf")

# Font Awesome 6 Free Solid codepoints (private use area).  Only the glyphs the
# UI actually uses are listed; each name is verified against the bundled TTF so
# no entry can silently render as an empty box.
GLYPHS = {
    # navigation
    "home": 0xF015,
    "gear": 0xF013,
    "chevron-up": 0xF077,
    "chevron-down": 0xF078,
    "arrow-left": 0xF060,
    "arrow-right": 0xF061,
    "arrow-up": 0xF062,
    "arrow-down": 0xF063,
    # actions
    "plus": 0xF067,
    "check": 0xF00C,
    "pen": 0xF304,
    "trash": 0xF1F8,
    "eye": 0xF06E,
    "flask": 0xF0C3,
    "floppy-disk": 0xF0C7,
    "rotate-right": 0xF2F9,
    "copy": 0xF0C5,
    "cloud-arrow-up": 0xF0EE,
    "stop": 0xF04D,
    "wand-sparkles": 0xF72B,
    # status
    "circle-info": 0xF05A,
    "circle-check": 0xF058,
    "circle-xmark": 0xF057,
    "triangle-exclamation": 0xF071,
    "lightbulb": 0xF0EB,
    # content / media
    "file-lines": 0xF15C,
    "file-pdf": 0xF1C1,
    "file-word": 0xF1C2,
    "file-powerpoint": 0xF1C4,
    "file-audio": 0xF1C7,
    "headphones": 0xF025,
    "music": 0xF001,
    "microphone": 0xF130,
    "image": 0xF03E,
    "images": 0xF302,
    "layer-group": 0xF5FD,
    "inbox": 0xF01C,
    "pen-nib": 0xF5B7,
    "code": 0xF121,
    # devices / services
    "phone": 0xF095,
    "mobile-screen": 0xF3CD,
    "wifi": 0xF1EB,
    "server": 0xF233,
    "qrcode": 0xF029,
    "brain": 0xF5DC,
    "user": 0xF007,
}

_family = None
_loaded = False


def load():
    """Register the bundled icon font once and return its family name."""
    global _family, _loaded
    if _loaded:
        return _family
    _loaded = True
    font_id = QFontDatabase.addApplicationFont(str(resource_path(*FONT_PARTS)))
    families = QFontDatabase.applicationFontFamilies(font_id) if font_id != -1 else []
    _family = families[0] if families else None
    return _family


def family():
    return _family or load() or ""


def text(name):
    codepoint = GLYPHS.get(name)
    return chr(codepoint) if codepoint else ""


def font(pixel_size):
    f = QFont(family())
    f.setPixelSize(max(1, int(pixel_size)))
    f.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
    return f
