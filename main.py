import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication

from RinUI import RinUIWindow

from backend.api_bridge import ApiBridge


class LumeWindow(RinUIWindow):
    def __init__(self):
        super().__init__()

        self.api = ApiBridge()
        self.engine.rootContext().setContextProperty("api", self.api)

        qml_path = Path(__file__).parent / "ui" / "main.qml"
        self.load(str(qml_path))

        icon_path = Path(__file__).parent / "baka.ico"
        if icon_path.exists():
            self.setIcon(str(icon_path))

        self.setProperty("title", "Lume @Irving Wu")


if __name__ == "__main__":
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Lume")
    app.setOrganizationName("Lume")

    icon_path = Path(__file__).parent / "baka.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = LumeWindow()
    sys.exit(app.exec())
