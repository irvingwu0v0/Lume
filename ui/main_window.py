"""Main application window: sidebar navigation, animated page transitions, toasts."""

from PySide6.QtCore import QPoint, QRect, QTimer, QVariantAnimation
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QStackedWidget, QVBoxLayout, QWidget,
)

from .anim import OUT, fade_in
from .appicon import app_icon
from .controls import IconButton
from .pages.home import HomePage
from .pages.listening import ListeningPage
from .pages.pdf_convert import PdfConvertPage
from .pages.settings import SettingsPage
from .pages.writing import WritingPage
from .widgets import LogoMark, Toast

SIDEBAR_WIDTH = 244


class MainWindow(QMainWindow):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.setWindowTitle("Lume")
        self.setWindowIcon(app_icon())
        self.resize(1280, 840)
        self.setMinimumSize(1040, 700)

        central = QWidget()
        central.setObjectName("Transparent")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(18, 24, 18, 18)
        side_layout.setSpacing(4)
        self.sidebar = sidebar

        # ── brand ───────────────────────────────────────────────
        brand_row = QHBoxLayout()
        brand_row.setSpacing(11)
        brand_row.setContentsMargins(4, 0, 0, 0)
        mark = LogoMark(40, radius=12)
        brand_row.addWidget(mark)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        name = QLabel("Lume")
        name.setObjectName("Brand")
        tag = QLabel("Light Up My English")
        tag.setObjectName("BrandTag")
        brand_text.addWidget(name)
        brand_text.addWidget(tag)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        side_layout.addLayout(brand_row)
        side_layout.addSpacing(22)

        # ── pages / navigation ──────────────────────────────────
        self.stack = QStackedWidget()
        self._buttons = []

        def add_page(text, icon_name, page):
            button = IconButton(
                text, icon_name, "nav", checkable=True, align="left",
                height=44, padding=13, radius=10, icon_size=17,
            )
            index = self.stack.addWidget(page)
            button.clicked.connect(lambda _=False, i=index: self.go_to(i))
            self._buttons.append(button)
            side_layout.addWidget(button)
            return button

        for text, icon_name, page in [
            ("首页", "home", HomePage(api, navigate=self.go_to)),
            ("试卷转换", "file-lines", PdfConvertPage(api)),
            ("听力材料生成", "headphones", ListeningPage(api)),
            ("作文思路生成", "pen-nib", WritingPage(api)),
        ]:
            add_page(text, icon_name, page)

        side_layout.addStretch(1)
        side_layout.addWidget(self._settings_separator())
        add_page("设置", "gear", SettingsPage(api))

        # sliding active-item indicator
        self._indicator = QFrame(sidebar)
        self._indicator.setObjectName("NavIndicator")
        self._indicator.setFixedSize(3, 22)
        self._indicator.raise_()
        self._indicator_anim = None

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)

        self._buttons[0].setChecked(True)
        self._indicator.setGeometry(QRect(6, 0, 3, 22))

        self.toast = Toast(central)
        self.api.toastMessage.connect(self._on_toast)
        self._place_toast()

    def _settings_separator(self):
        line = QFrame()
        line.setObjectName("Divider")
        line.setFixedHeight(1)
        wrapper = QWidget()
        wrapper.setObjectName("Transparent")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(6, 6, 6, 10)
        layout.addWidget(line)
        return wrapper

    # ── navigation ──────────────────────────────────────────────
    def go_to(self, index):
        if not 0 <= index < len(self._buttons):
            return
        changed = index != self.stack.currentIndex()
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self._buttons):
            button.setChecked(i == index)
        self._move_indicator(index)
        if changed:
            fade_in(self.stack.currentWidget(), duration=220)

    def _move_indicator(self, index):
        button = self._buttons[index]
        top = button.mapTo(self.sidebar, button.rect().topLeft()).y()
        target = QRect(6, top + (button.height() - 22) // 2, 3, 22)
        anim = QVariantAnimation(self)
        anim.setDuration(260)
        anim.setEasingCurve(OUT)
        anim.setStartValue(self._indicator.geometry())
        anim.setEndValue(target)
        anim.valueChanged.connect(lambda value: self._indicator.setGeometry(value))
        anim.start()
        self._indicator_anim = anim

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self._after_show)

    def _after_show(self):
        self._move_indicator_instant(self.stack.currentIndex())
        self.stack.currentWidget().setFocus()

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        self._place_toast()
        if self._buttons:
            self._move_indicator_instant(self.stack.currentIndex())

    def _move_indicator_instant(self, index):
        button = self._buttons[index]
        top = button.mapTo(self.sidebar, button.rect().topLeft()).y()
        self._indicator.setGeometry(QRect(6, top + (button.height() - 22) // 2, 3, 22))

    # ── toasts ──────────────────────────────────────────────────
    def show_toast(self, text, level="info"):
        self.toast.show_message(text, level, self._toast_home)

    def _toast_home(self, width):
        left = self.sidebar.width()
        available = max(1, self.width() - left)
        return QPoint(left + max(16, (available - width) // 2), 22)

    def _on_toast(self, text, kind):
        self.show_toast(text, "success" if kind == "success" else "error")

    def _place_toast(self):
        if self.toast.isVisible() and self.toast._home is not None:
            home = self._toast_home(self.toast.width() or 300)
            self.toast._home = home
            self.toast.move(home)

    def closeEvent(self, event):  # noqa: N802
        try:
            self.api.shutdown()
        except Exception:
            pass
        super().closeEvent(event)
