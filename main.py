"""Lume — AI-powered English teaching material generator.

Pure PySide6 (QtWidgets) desktop app, no third-party theme/component library.
Runs on Windows, macOS and Linux.
"""

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from backend.api_bridge import ApiBridge
from ui import icons
from ui.appicon import app_icon
from ui.main_window import MainWindow
from ui.theme import Theme

APP_NAME = "Lume"


def _fix_console_encoding():
    """Avoid UnicodeEncodeError when logging Chinese text on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def main():
    _fix_console_encoding()
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setStyle("Fusion")  # consistent base style on Windows/macOS/Linux
    app.setWindowIcon(app_icon())

    icons.load()  # register the bundled icon font before any widget paints
    Theme.apply(app)
    try:
        app.styleHints().colorSchemeChanged.connect(lambda _scheme: Theme.apply(app))
    except AttributeError:
        pass

    api = ApiBridge()
    window = MainWindow(api)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
