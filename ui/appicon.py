"""Platform-appropriate application icon.

The master artwork is ``assets/icons/baka.png``; ``scripts/make_icons.py``
derives a multi-size ``.ico`` (Windows) and an ``.icns`` (macOS bundles) from
it.  Windows loads the ``.ico``, Linux and macOS render the PNG directly.
"""

import sys
from PySide6.QtGui import QIcon

from .resources import resource_path

_ICON_DIR = ("assets", "icons")
# Ordered candidates per platform; the first file that exists wins.
_WINDOWS = [_ICON_DIR + ("baka.ico",), _ICON_DIR + ("baka.png",)]
_OTHER = [_ICON_DIR + ("baka.png",), _ICON_DIR + ("baka.ico",)]


def icon_files():
    """Existing icon files to load, best match first."""
    candidates = _WINDOWS if sys.platform == "win32" else _OTHER
    return [resource_path(*parts) for parts in candidates
            if resource_path(*parts).is_file()]


def app_icon():
    """Build a :class:`QIcon` from every available size/format."""
    icon = QIcon()
    for path in icon_files():
        icon.addFile(str(path))
    return icon
