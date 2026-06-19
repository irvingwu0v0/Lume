"""Custom-painted, animated controls built directly on QtWidgets.

Painting (instead of style sheets) keeps hover/press/selection transitions
smooth and lets icons come from the bundled icon font with a theme-aware colour.
"""

from PySide6.QtCore import (
    QEasingCurve, QRectF, QSize, Qt, QVariantAnimation, Signal,
)
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QLabel, QSizePolicy, QWidget

from . import icons
from .theme import Theme

OUT = QEasingCurve.Type.OutCubic


def mix(a, b, t):
    """Linear interpolation between two QColors."""
    t = max(0.0, min(1.0, float(t)))
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )


def animate_to(widget, key, start, end, setter, duration=150, easing=OUT):
    """Animate a float attribute, cancelling any previous animation of *key*."""
    previous = getattr(widget, "_anim_" + key, None)
    if previous is not None:
        previous.stop()
    anim = QVariantAnimation(widget)
    anim.setDuration(duration)
    anim.setEasingCurve(easing)
    anim.setStartValue(float(start))
    anim.setEndValue(float(end))
    anim.valueChanged.connect(lambda value: setter(float(value)))
    setattr(widget, "_anim_" + key, anim)
    anim.start()
    return anim


class IconButton(QAbstractButton):
    """Rounded button with an optional icon glyph, text and hover animation."""

    VARIANTS = {"primary", "secondary", "ghost", "soft", "danger", "nav"}

    def __init__(
        self, text="", icon_name="", variant="secondary", parent=None,
        icon_size=17, height=38, padding=16, radius=10, align="center",
        checkable=False, tooltip="",
    ):
        super().__init__(parent)
        self._icon_name = icon_name
        self._variant = variant if variant in self.VARIANTS else "secondary"
        self._icon_size = icon_size
        self._height = height
        self._pad = padding
        self._radius = radius
        self._align = align
        self._hover = 0.0
        self._press = 0.0
        self._select = 0.0
        self.setCheckable(checkable)
        self.setText(text)
        if tooltip:
            self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        if checkable:
            self.setChecked(False)
            self.toggled.connect(self._on_toggled)

    # ── public API ──────────────────────────────────────────────
    def setIconName(self, name):
        self._icon_name = name
        self.update()

    def iconName(self):
        return self._icon_name

    def setVariant(self, variant):
        if variant in self.VARIANTS:
            self._variant = variant
            self.update()

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        width = self._pad * 2
        if self._icon_name:
            width += self._icon_size
        if self._icon_name and self.text():
            width += 8
        if self.text():
            width += fm.horizontalAdvance(self.text())
        return QSize(max(width, 32), self._height)

    def minimumSizeHint(self):
        return self.sizeHint()

    # ── animation state ─────────────────────────────────────────
    def _on_toggled(self, checked):
        animate_to(self, "select", self._select, 1.0 if checked else 0.0,
                   self._set_select, 180)

    def _set_select(self, value):
        self._select = value
        self.update()

    def enterEvent(self, event):  # noqa: N802
        super().enterEvent(event)
        animate_to(self, "hover", self._hover, 1.0, self._set_hover, 130)

    def leaveEvent(self, event):  # noqa: N802
        super().leaveEvent(event)
        animate_to(self, "hover", self._hover, 0.0, self._set_hover, 130)

    def _set_hover(self, value):
        self._hover = value
        self.update()

    def _set_press(self, value):
        self._press = value
        self.update()

    def mousePressEvent(self, event):  # noqa: N802
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            animate_to(self, "press", self._press, 1.0, self._set_press, 90)

    def mouseReleaseEvent(self, event):  # noqa: N802
        super().mouseReleaseEvent(event)
        animate_to(self, "press", self._press, 0.0, self._set_press, 160)

    # ── painting ────────────────────────────────────────────────
    def _triple(self, checked):
        c = Theme.colors
        clear = QColor(0, 0, 0, 0)
        variant = self._variant
        if variant == "primary":
            return (
                (QColor(c["accent"]), QColor(c["on_accent"]), clear),
                (QColor(c["accent_hover"]), QColor(c["on_accent"]), clear),
                (QColor(c["accent_pressed"]), QColor(c["on_accent"]), clear),
            )
        if variant == "soft":
            return (
                (QColor(c["accent_soft"]), QColor(c["accent"]), clear),
                (QColor(c["accent_soft_hover"]), QColor(c["accent"]), clear),
                (QColor(c["accent_soft_hover"]), QColor(c["accent"]), clear),
            )
        if variant == "danger":
            return (
                (clear, QColor(c["error"]), clear),
                (QColor(c["error_soft"]), QColor(c["error"]), clear),
                (QColor(c["error_soft"]), QColor(c["error"]), clear),
            )
        if variant == "nav":
            if checked:
                return (
                    (QColor(c["accent_soft"]), QColor(c["accent"]), clear),
                    (QColor(c["accent_soft_hover"]), QColor(c["accent"]), clear),
                    (QColor(c["accent_soft_hover"]), QColor(c["accent"]), clear),
                )
            return (
                (clear, QColor(c["text_secondary"]), clear),
                (QColor(c["hover"]), QColor(c["text"]), clear),
                (QColor(c["pressed"]), QColor(c["text"]), clear),
            )
        if variant == "ghost":
            return (
                (clear, QColor(c["text_secondary"]), clear),
                (QColor(c["hover"]), QColor(c["text"]), clear),
                (QColor(c["pressed"]), QColor(c["text"]), clear),
            )
        # secondary (default)
        return (
            (QColor(c["card"]), QColor(c["text"]), QColor(c["border"])),
            (QColor(c["hover"]), QColor(c["text"]), QColor(c["border_strong"])),
            (QColor(c["pressed"]), QColor(c["text"]), QColor(c["border_strong"])),
        )

    def _state_colors(self):
        c = Theme.colors
        off = self._triple(False)
        on = self._triple(True)
        t = self._select if self.isCheckable() else 0.0

        def blend(index):
            return tuple(mix(off[index][i], on[index][i], t) for i in range(3))

        normal, hover, press = blend(0), blend(1), blend(2)
        if not self.isEnabled():
            disabled = QColor(c["disabled_bg"]) if self._variant in (
                "primary", "secondary", "soft") else QColor(0, 0, 0, 0)
            faded = QColor(c["disabled_text"])
            normal = hover = press = (disabled, faded, QColor(0, 0, 0, 0))

        bg = mix(normal[0], hover[0], self._hover)
        bg = mix(bg, press[0], self._press)
        fg = mix(normal[1], hover[1], self._hover)
        fg = mix(fg, press[1], self._press)
        border = mix(normal[2], hover[2], self._hover)
        border = mix(border, press[2], self._press)
        return bg, fg, border

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg, fg, border = self._state_colors()

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if bg.alpha() > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(rect, self._radius, self._radius)
        if border.alpha() > 0:
            painter.setPen(QPen(border, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, self._radius, self._radius)
        if self.hasFocus() and self.isEnabled() and self._variant not in ("primary", "nav"):
            focus = QColor(Theme.colors["accent"])
            focus.setAlpha(150)
            painter.setPen(QPen(focus, 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, self._radius, self._radius)

        icon_w = self._icon_size if self._icon_name else 0
        text = self.text()
        fm = QFontMetrics(self.font())
        gap = 8 if (icon_w and text) else 0
        content_w = icon_w + gap + (fm.horizontalAdvance(text) if text else 0)

        if self._align == "left":
            x = float(self._pad)
        else:
            x = max(float(self._pad), (self.width() - content_w) / 2.0)

        if icon_w:
            painter.setFont(icons.font(self._icon_size))
            painter.setPen(fg)
            painter.drawText(
                QRectF(x, 0, icon_w, self.height()),
                Qt.AlignmentFlag.AlignCenter, icons.text(self._icon_name),
            )
            x += icon_w + gap
        if text:
            painter.setFont(self.font())
            painter.setPen(fg)
            painter.drawText(
                QRectF(x, 0, self.width() - x - 4, self.height()),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text,
            )


class ToggleSwitch(QAbstractButton):
    """Animated iOS-style switch."""

    def __init__(self, parent=None, width=42, height=24):
        super().__init__(parent)
        self._w = width
        self._h = height
        self._pos = 0.0
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(width, height)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked):
        animate_to(self, "pos", self._pos, 1.0 if checked else 0.0,
                   self._set_pos, 180)

    def _set_pos(self, value):
        self._pos = value
        self.update()

    def paintEvent(self, event):  # noqa: N802
        c = Theme.colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        off = QColor(c["border_strong"])
        on = QColor(c["accent"])
        if not self.isEnabled():
            off = QColor(c["disabled_bg"])
            on = QColor(c["disabled_text"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(mix(off, on, self._pos))
        painter.drawRoundedRect(QRectF(0, 0, self._w, self._h), self._h / 2, self._h / 2)

        knob = self._h - 6
        x = 3 + self._pos * (self._w - knob - 6)
        painter.setBrush(QColor("#ffffff"))
        painter.drawEllipse(QRectF(x, 3, knob, knob))


class CheckBox(QAbstractButton):
    """Animated check box with a check glyph from the icon font."""

    def __init__(self, text="", parent=None, box=18):
        super().__init__(parent)
        self._box = box
        self._t = 0.0
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked):
        animate_to(self, "t", self._t, 1.0 if checked else 0.0, self._set_t, 160)

    def _set_t(self, value):
        self._t = value
        self.update()

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(self._box + 8 + fm.horizontalAdvance(self.text()), max(self._box + 4, 24))

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):  # noqa: N802
        from PySide6.QtCore import QRectF as _Rect

        c = Theme.colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = self._box
        top = (self.height() - side) / 2.0
        box_rect = _Rect(0.5, top + 0.5, side - 1, side - 1)

        on = QColor(c["accent"])
        off = QColor(0, 0, 0, 0)
        border = mix(QColor(c["border_strong"]), on, self._t)
        painter.setBrush(mix(off, on, self._t))
        painter.setPen(QPen(border, 1.4))
        painter.drawRoundedRect(box_rect, 5, 5)

        if self._t > 0.02:
            glyph = QColor(c["on_accent"])
            glyph.setAlphaF(self._t)
            painter.setPen(glyph)
            painter.setFont(icons.font(side - 5))
            painter.drawText(box_rect, Qt.AlignmentFlag.AlignCenter, icons.text("check"))

        painter.setPen(QColor(c["text"] if self.isEnabled() else c["disabled_text"]))
        painter.setFont(self.font())
        fm = QFontMetrics(self.font())
        painter.drawText(
            QRectF(side + 8, 0, self.width() - side - 8, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            fm.elidedText(self.text(), Qt.TextElideMode.ElideRight,
                          max(0, self.width() - side - 8)),
        )


class RadioButton(QAbstractButton):
    """Animated radio button drawn as a ring plus growing dot."""

    def __init__(self, text="", parent=None, box=18):
        super().__init__(parent)
        self._box = box
        self._t = 0.0
        self.setText(text)
        self.setCheckable(True)
        self.setAutoExclusive(True)  # QAbstractButton does not do this for us
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked):
        animate_to(self, "t", self._t, 1.0 if checked else 0.0, self._set_t, 160)

    def _set_t(self, value):
        self._t = value
        self.update()

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(self._box + 8 + fm.horizontalAdvance(self.text()), max(self._box + 4, 24))

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):  # noqa: N802
        c = Theme.colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        side = self._box
        top = (self.height() - side) / 2.0
        rect = QRectF(0.8, top + 0.8, side - 1.6, side - 1.6)

        border = mix(QColor(c["border_strong"]), QColor(c["accent"]), self._t)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border, 1.5))
        painter.drawEllipse(rect)

        if self._t > 0.01:
            dot = (side / 2 - 4.5) * self._t
            center = rect.center()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(c["accent"]))
            painter.drawEllipse(center, dot, dot)

        painter.setPen(QColor(c["text"] if self.isEnabled() else c["disabled_text"]))
        painter.setFont(self.font())
        fm = QFontMetrics(self.font())
        painter.drawText(
            QRectF(side + 8, 0, self.width() - side - 8, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            fm.elidedText(self.text(), Qt.TextElideMode.ElideRight,
                          max(0, self.width() - side - 8)),
        )


class SegmentedControl(QWidget):
    """Segmented switcher with an animated sliding pill."""

    changed = Signal(int)

    def __init__(self, options, parent=None, height=40, radius=11):
        super().__init__(parent)
        self._options = list(options)  # [(icon_name, text), ...]
        self._index = 0
        self._pos = 0.0
        self._hover_index = -1
        self._height = height
        self._radius = radius
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(height)

    # ── API ─────────────────────────────────────────────────────
    def current_index(self):
        return self._index

    def set_current_index(self, index, animate=True):
        index = max(0, min(len(self._options) - 1, int(index)))
        if index == self._index and animate:
            return
        previous = self._index
        self._index = index
        if animate:
            animate_to(self, "pos", self._pos, float(index), self._set_pos, 220)
        else:
            self._pos = float(index)
        self.update()
        if index != previous:
            self.changed.emit(index)

    def _set_pos(self, value):
        self._pos = value
        self.update()

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        width = 0
        for icon_name, text in self._options:
            width += (18 if icon_name else 0) + (6 if icon_name and text else 0)
            width += fm.horizontalAdvance(text)
        width += 56 * len(self._options)
        return QSize(max(width, 240), self._height)

    # ── geometry ────────────────────────────────────────────────
    def _seg_width(self):
        return self.width() / max(1, len(self._options))

    def _seg_rect(self, index):
        width = self._seg_width()
        return QRectF(index * width + 3, 3, width - 6, self.height() - 6)

    def _index_at(self, x):
        if not self._options:
            return -1
        return max(0, min(len(self._options) - 1, int(x // max(1.0, self._seg_width()))))

    # ── events ──────────────────────────────────────────────────
    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            index = self._index_at(event.position().x())
            if index >= 0:
                self.set_current_index(index)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        index = self._index_at(event.position().x())
        if index != self._hover_index:
            self._hover_index = index
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # noqa: N802
        self._hover_index = -1
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):  # noqa: N802
        if not self._options:
            return
        c = Theme.colors
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(c["hover"]))
        painter.drawRoundedRect(QRectF(self.rect()), self._radius, self._radius)

        low = int(self._pos)
        high = min(low + 1, len(self._options) - 1)
        frac = self._pos - low
        a, b = self._seg_rect(low), self._seg_rect(high)
        pill = QRectF(
            a.x() + (b.x() - a.x()) * frac,
            a.y() + (b.y() - a.y()) * frac,
            a.width() + (b.width() - a.width()) * frac,
            a.height() + (b.height() - a.height()) * frac,
        )
        painter.setBrush(QColor(c["card"]))
        painter.setPen(QPen(QColor(c["border"]), 1))
        painter.drawRoundedRect(pill, self._radius - 3, self._radius - 3)

        for i, (icon_name, text) in enumerate(self._options):
            rect = self._seg_rect(i)
            if i == self._index:
                color = QColor(c["accent"])
            elif i == self._hover_index:
                color = QColor(c["text"])
            else:
                color = QColor(c["text_secondary"])

            fm = QFontMetrics(self.font())
            icon_w = 17 if icon_name else 0
            gap = 6 if (icon_w and text) else 0
            content = icon_w + gap + (fm.horizontalAdvance(text) if text else 0)
            x = rect.center().x() - content / 2.0

            if icon_w:
                painter.setPen(color)
                painter.setFont(icons.font(icon_w))
                painter.drawText(
                    QRectF(x, rect.y(), icon_w, rect.height()),
                    Qt.AlignmentFlag.AlignCenter, icons.text(icon_name),
                )
                x += icon_w + gap
            if text:
                painter.setPen(color)
                painter.setFont(self.font())
                painter.drawText(
                    QRectF(x, rect.y(), fm.horizontalAdvance(text) + 4, rect.height()),
                    Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text,
                )


class IconBadge(QWidget):
    """Rounded square/circle badge with a soft tinted background and a glyph."""

    def __init__(self, icon_name="", size=46, tone="accent", parent=None, radius=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._size = size
        self._tone = tone
        self._radius = radius if radius is not None else size // 2
        self.setFixedSize(size, size)

    def setIconName(self, name):
        self._icon_name = name
        self.update()

    def setTone(self, tone):
        self._tone = tone
        self.update()

    def _colors(self):
        c = Theme.colors
        tones = {
            "accent": (c["accent_soft"], c["accent"]),
            "success": (c["success_soft"], c["success"]),
            "warning": (c["warning_soft"], c["warning"]),
            "error": (c["error_soft"], c["error"]),
            "neutral": (c["hover"], c["text_secondary"]),
        }
        return tones.get(self._tone, tones["accent"])

    def paintEvent(self, event):  # noqa: N802
        background, foreground = self._colors()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(QRectF(self.rect()), self._radius, self._radius)

        painter.setPen(QColor(foreground))
        painter.setFont(icons.font(self._size * 0.42))
        painter.drawText(QRectF(self.rect()), Qt.AlignmentFlag.AlignCenter,
                         icons.text(self._icon_name))


class Tag(QLabel):
    """Small soft pill label, e.g. the '思考' / '视觉' markers."""

    def __init__(self, text="", tone="accent", parent=None):
        super().__init__(text, parent)
        self._tone = tone
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._apply_style()

    def setTone(self, tone):
        self._tone = tone
        self._apply_style()

    def _apply_style(self):
        c = Theme.colors
        tones = {
            "accent": (c["accent_soft"], c["accent"]),
            "success": (c["success_soft"], c["success"]),
            "warning": (c["warning_soft"], c["warning"]),
            "error": (c["error_soft"], c["error"]),
            "neutral": (c["hover"], c["text_secondary"]),
        }
        background, foreground = tones.get(self._tone, tones["accent"])
        self.setStyleSheet(
            f"QLabel {{ background: {background}; color: {foreground};"
            " border-radius: 6px; padding: 2px 8px; font-size: 11px; font-weight: 600; }"
        )


class IconLabel(QLabel):
    """A bare glyph that follows the style sheet colour."""

    def __init__(self, icon_name, size=18, parent=None):
        super().__init__(parent)
        self.setFont(icons.font(size))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText(icons.text(icon_name))
        self.setFixedSize(size + 6, size + 6)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
