"""Reusable, mostly custom-painted widgets shared by the Lume pages."""

import json

from PySide6.QtCore import (
    QEasingCurve, QPoint, QRectF, Qt, QTimer, QVariantAnimation, Signal,
)
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap, QTextCursor,
)
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QSizePolicy, QTextEdit,
    QVBoxLayout, QWidget,
)

from . import icons
from .anim import OUT, PulseDots, animate_shadow, drop_shadow, smooth_scroll
from .controls import IconButton
from .theme import Theme


class Card(QFrame):
    """Rounded surface container with an optional hover elevation."""

    def __init__(self, parent=None, hover=False, padding=20, spacing=13):
        super().__init__(parent)
        self.setObjectName("CardHover" if hover else "Card")
        self._hover = hover
        self._shadow = None
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)
        if hover:
            self._shadow = drop_shadow(self, blur=18, offset_y=4, alpha=26)

    def add(self, widget):
        self.body.addWidget(widget)
        return widget

    def add_layout(self, layout):
        self.body.addLayout(layout)
        return layout

    def enterEvent(self, event):  # noqa: N802
        super().enterEvent(event)
        if self._hover and self._shadow is not None:
            animate_shadow(self._shadow, blur=38, offset_y=11, duration=200)

    def leaveEvent(self, event):  # noqa: N802
        super().leaveEvent(event)
        if self._hover and self._shadow is not None:
            animate_shadow(self._shadow, blur=18, offset_y=4, duration=200)


def make_card(parent=None, padding=20, spacing=13):
    """Backwards-compatible helper returning ``(frame, layout)``."""
    card = Card(parent, padding=padding, spacing=spacing)
    return card, card.body


def top_aligned(widget):
    """Wrap *widget* so a QStackedWidget page keeps it at its natural height."""
    container = QWidget()
    container.setObjectName("Transparent")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(widget)
    layout.addStretch(1)
    return container


def hline(parent=None):
    line = QFrame(parent)
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


def section_title(text):
    label = QLabel(text)
    label.setObjectName("CardTitle")
    return label


def muted(text):
    label = QLabel(text)
    label.setObjectName("Muted")
    return label


class LogoMark(QWidget):
    """The master Lume artwork (``assets/icons/baka.png``) drawn as-is.

    The artwork already has a transparent background, so it is painted without
    a tile, border or rounded clip; only a glyph badge is used as a fallback
    when no icon file could be loaded.
    """

    _FALLBACK_GLYPH = "wand-sparkles"

    def __init__(self, size=40, radius=12, parent=None):
        super().__init__(parent)
        self._radius = radius
        self._pixmap = self._load_pixmap()
        self.setFixedSize(size, size)

    @staticmethod
    def _load_pixmap():
        from .appicon import icon_files

        for path in icon_files():
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                return pixmap
        return QPixmap()

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        rect = QRectF(self.rect())

        if self._pixmap.isNull():
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            clip = QPainterPath()
            clip.addRoundedRect(rect, self._radius, self._radius)
            painter.setClipPath(clip)
            painter.fillRect(self.rect(), Theme.color("accent_soft"))
            painter.setPen(Theme.color("accent"))
            painter.setFont(icons.font(self.width() * 0.42))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                             icons.text(self._FALLBACK_GLYPH))
            return

        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        side = min(self.width(), self.height())
        target = QRectF(0, 0, side, side)
        target.moveCenter(rect.center())

        ratio = self.devicePixelRatioF()
        scaled = self._pixmap.scaled(
            max(1, int(side * ratio)), max(1, int(side * ratio)),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(ratio)
        painter.drawPixmap(target.toRect(), scaled)


class StepIndicator(QFrame):
    """Animated horizontal step header drawn with QPainter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFixedHeight(96)
        self._labels = []
        self._current = 1
        self._progress = 0.0
        self._pop = 1.0

    def set_steps(self, labels):
        self._labels = list(labels)
        self.update()

    def set_current(self, step):
        self._current = step
        previous = self._progress
        target = float(step - 1)
        anim = QVariantAnimation(self)
        anim.setDuration(300)
        anim.setEasingCurve(OUT)
        anim.setStartValue(previous)
        anim.setEndValue(target)
        anim.valueChanged.connect(self._set_progress)
        anim.start()
        self._progress_anim = anim

        bump = QVariantAnimation(self)
        bump.setDuration(380)
        bump.setEasingCurve(QEasingCurve.Type.OutCubic)
        bump.setStartValue(1.0)
        bump.setKeyValueAt(0.35, 1.14)
        bump.setEndValue(1.0)
        bump.valueChanged.connect(self._set_pop)
        bump.start()
        self._pop_anim = bump
        self.update()

    def _set_progress(self, value):
        self._progress = float(value)
        self.update()

    def _set_pop(self, value):
        self._pop = float(value)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        if not self._labels:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        count = len(self._labels)
        width = self.width()
        margin = 46.0
        cy = 32.0
        radius = 15.0
        if count > 1:
            xs = [margin + i * (width - 2 * margin) / (count - 1) for i in range(count)]
        else:
            xs = [width / 2]

        # connectors
        for i in range(count - 1):
            ratio = max(0.0, min(1.0, self._progress - i))
            left, right = xs[i] + radius + 8, xs[i + 1] - radius - 8
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(Theme.color("border"))
            painter.drawRoundedRect(QRectF(left, cy - 2, right - left, 4), 2, 2)
            if ratio > 0:
                painter.setBrush(Theme.color("accent"))
                painter.drawRoundedRect(QRectF(left, cy - 2, (right - left) * ratio, 4), 2, 2)

        for i, x in enumerate(xs):
            step = i + 1
            active = step == self._current
            center = QPoint(int(x), int(cy))
            scale = self._pop if active else 1.0

            if active:
                halo = Theme.color("accent")
                halo.setAlpha(38)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(halo)
                painter.drawEllipse(center, radius * 1.55 * scale, radius * 1.55 * scale)

            if step < self._current:
                fill = Theme.color("success")
            elif active:
                fill = Theme.color("accent")
            else:
                fill = Theme.color("border")

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawEllipse(center, radius * scale, radius * scale)

            painter.setPen(QColor(Theme.colors["on_accent"]) if (active or step < self._current)
                          else Theme.color("text_muted"))
            if step < self._current:
                painter.setFont(icons.font(radius * 1.05))
                painter.drawText(QRectF(x - radius, cy - radius, radius * 2, radius * 2),
                                 Qt.AlignmentFlag.AlignCenter, icons.text("check"))
            else:
                font = QFont(Theme.font_family)
                font.setPixelSize(int(13 * scale))
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(QRectF(x - radius, cy - radius, radius * 2, radius * 2),
                                 Qt.AlignmentFlag.AlignCenter, str(step))

            label_color = (Theme.color("accent") if active
                           else Theme.color("success") if step < self._current
                           else Theme.color("text_muted"))
            painter.setPen(label_color)
            label_font = QFont(Theme.font_family)
            label_font.setPixelSize(12)
            painter.setFont(label_font)
            painter.drawText(QRectF(x - 90, cy + 22, 180, 20),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                             self._labels[i])


class ModelSelector(QComboBox):
    """Model drop-down that reads the configured models from the backend."""

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self.api = api
        self.filter_vision = False
        self._models = []
        self._rotation = 0.0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(42)

    def reload(self):
        self.clear()
        self._models = []
        try:
            models = json.loads(self.api.getModelsJson())
        except Exception:
            models = []
        for model in models:
            if self.filter_vision and not model.get("vision_enabled"):
                continue
            label = model.get("alias", "")
            markers = []
            if model.get("thinking_enabled"):
                markers.append("思考")
            if model.get("vision_enabled"):
                markers.append("视觉")
            if markers:
                label += "  ·  " + " / ".join(markers)
            self.addItem(label, model)
            self._models.append(model)

        if self._models:
            self.setCurrentIndex(0)
            self.setEnabled(True)
        else:
            self.addItem("暂无可用的 AI 模型", None)
            self.setCurrentIndex(0)
            self.setEnabled(False)

    @property
    def model_count(self):
        return len(self._models)

    def _current(self):
        return self.currentData()

    @property
    def selected_model_id(self):
        model = self._current()
        return model.get("id", "") if model else ""

    @property
    def selected_model_thinking(self):
        model = self._current()
        return bool(model.get("thinking_enabled")) if model else False

    # ── animated chevron ────────────────────────────────────────
    def showPopup(self):  # noqa: N802
        super().showPopup()
        self._rotate(180)

    def hidePopup(self):  # noqa: N802
        super().hidePopup()
        self._rotate(0)

    def _rotate(self, target):
        anim = QVariantAnimation(self)
        anim.setDuration(180)
        anim.setEasingCurve(OUT)
        anim.setStartValue(self._rotation)
        anim.setEndValue(float(target))
        anim.valueChanged.connect(self._set_rotation)
        anim.start()
        self._rotate_anim = anim

    def _set_rotation(self, value):
        self._rotation = float(value)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(Theme.colors["accent"] if self.hasFocus() else
                       Theme.colors["text_secondary"] if self.isEnabled() else
                       Theme.colors["disabled_text"])
        painter.setPen(color)
        painter.setFont(icons.font(15))
        painter.drawText(QRectF(14, 0, 20, self.height()),
                         Qt.AlignmentFlag.AlignCenter, icons.text("layer-group"))

        painter.save()
        painter.translate(self.width() - 22, self.height() / 2.0)
        painter.rotate(self._rotation)
        painter.setFont(icons.font(13))
        painter.drawText(QRectF(-9, -9, 18, 18), Qt.AlignmentFlag.AlignCenter,
                         icons.text("chevron-down"))
        painter.restore()


class StreamResultPanel(QFrame):
    """Streaming AI output: status, collapsible reasoning, auto-scrolling text."""

    stop_requested = Signal()

    def __init__(self, title="生成结果", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._content = ""
        self._thinking = ""
        self._content_buffer = ""
        self._thinking_buffer = ""
        self._thinking_open = False

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(10)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")
        header.addWidget(self.title_label)

        self.busy = PulseDots()
        header.addWidget(self.busy)

        self.status_label = QLabel("")
        self.status_label.setObjectName("Muted")
        header.addWidget(self.status_label)
        header.addStretch(1)

        self.stop_button = IconButton("停止", "stop", "danger", height=32, padding=12,
                                      icon_size=13, radius=8)
        self.stop_button.setVisible(False)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        header.addWidget(self.stop_button)
        root.addLayout(header)

        # ── collapsible reasoning ───────────────────────────────
        self.think_frame = QFrame()
        self.think_frame.setObjectName("Inset")
        think_layout = QVBoxLayout(self.think_frame)
        think_layout.setContentsMargins(12, 10, 12, 12)
        think_layout.setSpacing(8)

        think_header = QHBoxLayout()
        think_header.setSpacing(8)
        think_icon = QLabel()
        think_icon.setFont(icons.font(13))
        think_icon.setText(icons.text("lightbulb"))
        think_icon.setStyleSheet(f"color: {Theme.colors['warning']}; background: transparent;")
        think_header.addWidget(think_icon)
        think_title = QLabel("思考过程")
        think_title.setStyleSheet(f"color: {Theme.colors['accent']}; font-weight: 600;")
        think_header.addWidget(think_title)
        think_header.addStretch(1)
        self.think_toggle = IconButton("", "chevron-down", "ghost", height=28, padding=6,
                                       icon_size=12, radius=7)
        self.think_toggle.setToolTip("展开 / 收起思考过程")
        self.think_toggle.clicked.connect(self._toggle_thinking)
        think_header.addWidget(self.think_toggle)
        think_layout.addLayout(think_header)

        self.think_edit = QTextEdit()
        self.think_edit.setReadOnly(True)
        self.think_edit.setMinimumHeight(0)
        self.think_edit.setMaximumHeight(0)
        self.think_edit.setStyleSheet(
            f"QTextEdit {{ background: transparent; border: none; padding: 0;"
            f" color: {Theme.colors['text_secondary']}; font-size: 13px; }}"
        )
        think_layout.addWidget(self.think_edit)

        self.think_frame.setVisible(False)
        root.addWidget(self.think_frame)

        self.content_edit = QTextEdit()
        self.content_edit.setReadOnly(True)
        self.content_edit.setMinimumHeight(320)
        root.addWidget(self.content_edit, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(80)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._flush)

        self._think_anim = None

    # ── public API ──────────────────────────────────────────────
    @property
    def content(self):
        return self._content

    @property
    def thinking(self):
        return self._thinking

    def reset(self):
        self._timer.stop()
        self._content = ""
        self._thinking = ""
        self._content_buffer = ""
        self._thinking_buffer = ""
        self.content_edit.clear()
        self.think_edit.clear()
        self._thinking_open = False
        self._apply_thinking_height(animate=False)
        self.think_frame.setVisible(False)
        self.status_label.setText("")
        self.busy.stop()
        self.stop_button.setVisible(False)

    def begin(self, pending_text="正在等待 AI 响应..."):
        self.reset()
        self.status_label.setText(pending_text)
        self.busy.start()
        self.stop_button.setVisible(True)

    def append_chunk(self, chunk):
        try:
            obj = json.loads(chunk)
        except Exception:
            return
        if obj.get("reasoning"):
            self._thinking_buffer += obj["reasoning"]
            self.status_label.setText("AI 正在思考...")
        if obj.get("content"):
            self._content_buffer += obj["content"]
            self.status_label.setText("AI 正在生成...")
        if not self._timer.isActive():
            self._timer.start()

    def finish(self, full_text):
        self._timer.stop()
        self._flush()
        self._content = full_text
        self.content_edit.setPlainText(full_text)
        self._scroll_to_end()
        self.status_label.setText("生成完成")
        self._set_idle()

    def fail(self, message=""):
        self._timer.stop()
        self._flush()
        self.status_label.setText("生成出错" if not message else f"生成出错：{message}")
        self.status_label.setObjectName("Error")
        self._restyle(self.status_label)
        self._set_idle()

    def set_status(self, text):
        self.status_label.setObjectName("Muted")
        self._restyle(self.status_label)
        self.status_label.setText(text)

    def set_generating(self, generating):
        self.busy.setVisible(generating)
        self.stop_button.setVisible(generating)
        if generating:
            self.busy.start()
        else:
            self.busy.stop()

    @staticmethod
    def _restyle(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def _set_idle(self):
        self.busy.stop()
        self.stop_button.setVisible(False)

    # ── thinking panel ──────────────────────────────────────────
    def _toggle_thinking(self):
        self._thinking_open = not self._thinking_open
        self.think_toggle.setIconName("chevron-up" if self._thinking_open else "chevron-down")
        self._apply_thinking_height(animate=True)

    def _apply_thinking_height(self, animate):
        if self._thinking_open:
            doc_height = self.think_edit.document().size().height()
            target = int(max(58, min(220, doc_height + 22)))
        else:
            target = 0
        if animate:
            anim = QVariantAnimation(self)
            anim.setDuration(220)
            anim.setEasingCurve(OUT)
            anim.setStartValue(float(self.think_edit.maximumHeight()))
            anim.setEndValue(float(target))
            anim.valueChanged.connect(lambda v: self.think_edit.setMaximumHeight(int(v)))
            anim.start()
            self._think_anim = anim
        else:
            self.think_edit.setMaximumHeight(target)

    # ── streaming helpers ───────────────────────────────────────
    def _scroll_to_end(self):
        bar = self.content_edit.verticalScrollBar()
        smooth_scroll(bar, bar.maximum())

    def _flush(self):
        if self._content_buffer:
            self._content += self._content_buffer
            self._content_buffer = ""
            self.content_edit.setPlainText(self._content)
            self._scroll_to_end()
        if self._thinking_buffer:
            self._thinking += self._thinking_buffer
            self._thinking_buffer = ""
            self.think_edit.setPlainText(self._thinking)
            self.think_frame.setVisible(True)
            self.think_edit.moveCursor(QTextCursor.MoveOperation.End)
            if self._thinking_open:
                self._apply_thinking_height(animate=False)


class Toast(QFrame):
    """Auto-hiding notification with a slide-down + fade transition."""

    ICONS = {
        "success": ("circle-check", "success"),
        "error": ("circle-xmark", "error"),
        "warning": ("triangle-exclamation", "warning"),
        "info": ("circle-info", "accent"),
    }

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("ToastHost")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._body = QFrame()
        self._body.setObjectName("Toast")
        self._body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer.addWidget(self._body)

        layout = QHBoxLayout(self._body)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(10)

        self.icon = QLabel()
        self.icon.setFont(icons.font(16))
        self.icon.setStyleSheet("background: transparent;")
        layout.addWidget(self.icon)

        self.label = QLabel("")
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)

        # NOTE: only one graphics effect per widget is allowed and nested
        # effects do not survive QWidget.grab(), so the toast slides rather
        # than fades, keeping its soft drop shadow.
        self._shadow = drop_shadow(self._body, blur=24, offset_y=8, alpha=46)

        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dismiss)
        self._anim = None
        self._home = None

    def show_message(self, text, level="info", home_provider=None):
        icon_name, tone = self.ICONS.get(level, self.ICONS["info"])
        color = Theme.colors[tone]
        self.icon.setText(icons.text(icon_name))
        self.icon.setStyleSheet(f"color: {color}; background: transparent;")
        self.label.setText(text)
        self._body.setStyleSheet(
            f"QFrame#Toast {{ background: {Theme.colors['card']};"
            f" border: 1px solid {Theme.colors['border']};"
            f" border-left: 3px solid {color}; border-radius: 12px; }}"
        )

        self.adjustSize()
        self.setFixedWidth(min(max(self.sizeHint().width(), 260), 460))
        self.show()
        self.raise_()

        target = (home_provider(self.width()) if home_provider else self.pos())
        self._home = target
        self.move(target.x(), target.y() - 18)

        anim = QVariantAnimation(self)
        anim.setDuration(240)
        anim.setEasingCurve(OUT)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)

        def step(value):
            value = float(value)
            self.move(target.x(), int(target.y() - 18 * (1.0 - value)))

        anim.valueChanged.connect(step)
        anim.start()
        self._anim = anim
        self._timer.start(3400)

    def _dismiss(self):
        start = self.pos()
        anim = QVariantAnimation(self)
        anim.setDuration(180)
        anim.setEasingCurve(QEasingCurve.Type.InCubic)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)

        def step(value):
            value = float(value)
            self.move(start.x(), int(start.y() - 12 * value))

        anim.valueChanged.connect(step)
        anim.finished.connect(self._after_hide)
        anim.start()
        self._anim = anim

    def _after_hide(self):
        self.hide()


class DropZone(QWidget):
    """Dashed upload target with a hover animation and an icon-font glyph."""

    clicked = Signal()

    def __init__(self, icon_name="cloud-arrow-up", title="点击选择文件",
                 hint="", parent=None, min_height=150):
        super().__init__(parent)
        self._icon_name = icon_name
        self._title = title
        self._hint = hint
        self._hover = 0.0
        self.setMinimumHeight(min_height)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_content(self, title=None, hint=None, icon_name=None):
        if title is not None:
            self._title = title
        if hint is not None:
            self._hint = hint
        if icon_name is not None:
            self._icon_name = icon_name
        self.update()

    def enterEvent(self, event):  # noqa: N802
        super().enterEvent(event)
        self._animate(1.0)

    def leaveEvent(self, event):  # noqa: N802
        super().leaveEvent(event)
        self._animate(0.0)

    def _animate(self, target):
        anim = QVariantAnimation(self)
        anim.setDuration(160)
        anim.setEasingCurve(OUT)
        anim.setStartValue(self._hover)
        anim.setEndValue(float(target))
        anim.valueChanged.connect(self._set_hover)
        anim.start()
        self._hover_anim = anim

    def _set_hover(self, value):
        self._hover = float(value)
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):  # noqa: N802
        from .controls import mix

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)

        border = mix(Theme.color("border"), Theme.color("accent"), self._hover)
        background = mix(QColor(0, 0, 0, 0), QColor(Theme.colors["accent_soft"]),
                         self._hover * 0.75)
        pen = QPen(border, 1.6, Qt.PenStyle.DashLine)
        pen.setDashPattern([5, 4])
        painter.setPen(pen)
        painter.setBrush(background)
        painter.drawRoundedRect(rect, 14, 14)

        icon_size = 30
        title_font = QFont(Theme.font_family)
        title_font.setPixelSize(15)
        title_font.setBold(True)
        hint_font = QFont(Theme.font_family)
        hint_font.setPixelSize(12)

        fm_title = QFontMetrics(title_font)
        fm_hint = QFontMetrics(hint_font)
        block = icon_size + 10 + fm_title.height() + (6 + fm_hint.height() if self._hint else 0)
        top = (self.height() - block) / 2.0

        painter.setPen(Theme.color("accent"))
        painter.setFont(icons.font(icon_size))
        painter.drawText(QRectF(0, top, self.width(), icon_size),
                         Qt.AlignmentFlag.AlignCenter, icons.text(self._icon_name))
        y = top + icon_size + 10

        painter.setPen(Theme.color("text"))
        painter.setFont(title_font)
        painter.drawText(QRectF(0, y, self.width(), fm_title.height()),
                         Qt.AlignmentFlag.AlignCenter, self._title)
        y += fm_title.height()

        if self._hint:
            y += 6
            painter.setPen(Theme.color("text_muted"))
            painter.setFont(hint_font)
            painter.drawText(QRectF(0, y, self.width(), fm_hint.height()),
                             Qt.AlignmentFlag.AlignCenter, self._hint)
