"""Small animation helpers built on Qt's own animation framework.

Everything here is optional sugar: widgets must look correct when an animation
is skipped, so the helpers never own business state.
"""

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPropertyAnimation, QRectF, QTimer, Qt,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QWidget,
)

OUT = QEasingCurve.Type.OutCubic
IN_OUT = QEasingCurve.Type.InOutCubic


def _keep(widget, animation):
    """Prevent the animation from being garbage-collected mid-flight."""
    widget._animations = getattr(widget, "_animations", [])
    widget._animations.append(animation)
    animation.finished.connect(lambda: widget._animations.remove(animation)
                               if animation in widget._animations else None)
    return animation


def fade_in(widget, duration=200, delay=0, keep_effect=False):
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(OUT)
    if not keep_effect:
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    _keep(widget, anim)
    if delay:
        QTimer.singleShot(delay, anim.start)
    else:
        anim.start()
    return anim


def fade_out(widget, duration=150, hide=True):
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(1.0)
    anim.setEndValue(0.0)
    anim.setEasingCurve(IN_OUT)
    if hide:
        anim.finished.connect(widget.hide)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    _keep(widget, anim)
    anim.start()
    return anim


def slide_fade_in(widget, dy=14, dx=0, duration=240):
    """Fade in while drifting into place. Safe for layout-managed widgets."""
    original = widget.pos()
    widget.move(original.x() + dx, original.y() + dy)

    move = QPropertyAnimation(widget, b"pos", widget)
    move.setDuration(duration)
    move.setStartValue(QPoint(original.x() + dx, original.y() + dy))
    move.setEndValue(original)
    move.setEasingCurve(OUT)
    _keep(widget, move)
    move.start()

    fade_in(widget, duration=duration)
    return move


def animate_property(target, prop, end, duration=200, easing=OUT, on_finished=None):
    anim = QPropertyAnimation(target, prop, target)
    anim.setDuration(duration)
    anim.setStartValue(target.property(prop))
    anim.setEndValue(end)
    anim.setEasingCurve(easing)
    if on_finished:
        anim.finished.connect(on_finished)
    _keep(target, anim)
    anim.start()
    return anim


def smooth_scroll(scrollbar, value, duration=220):
    anim = QPropertyAnimation(scrollbar, b"value", scrollbar)
    anim.setDuration(duration)
    anim.setStartValue(scrollbar.value())
    anim.setEndValue(int(value))
    anim.setEasingCurve(OUT)
    _keep(scrollbar, anim)
    anim.start()
    return anim


def drop_shadow(widget, blur=26, offset_y=7, alpha=38):
    from .theme import Theme

    effect = QGraphicsDropShadowEffect(widget)
    effect.setColor(Theme.shadow_color(alpha))
    effect.setBlurRadius(blur)
    effect.setOffset(0, offset_y)
    widget.setGraphicsEffect(effect)
    return effect


def animate_shadow(effect, blur, offset_y=None, duration=180):
    if effect is None:
        return None
    blur_anim = QPropertyAnimation(effect, b"blurRadius", effect)
    blur_anim.setDuration(duration)
    blur_anim.setStartValue(effect.blurRadius())
    blur_anim.setEndValue(float(blur))
    blur_anim.setEasingCurve(OUT)
    _keep(effect, blur_anim)
    blur_anim.start()
    if offset_y is not None:
        offset_anim = QPropertyAnimation(effect, b"offset", effect)
        offset_anim.setDuration(duration)
        offset_anim.setStartValue(effect.offset())
        offset_anim.setEndValue(effect.offset().__class__(0, offset_y))
        offset_anim.setEasingCurve(OUT)
        _keep(effect, offset_anim)
        offset_anim.start()
    return blur_anim


class BusyIndicator(QWidget):
    """Rotating arc spinner used for indeterminate progress."""

    def __init__(self, diameter=20, thickness=2.5, parent=None):
        super().__init__(parent)
        self._diameter = diameter
        self._thickness = thickness
        self._angle = 0
        self.setFixedSize(diameter, diameter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def start(self):
        self.show()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()

    def is_running(self):
        return self._timer.isActive()

    def _tick(self):
        self._angle = (self._angle + 9) % 360
        self.update()

    def paintEvent(self, event):  # noqa: N802 (Qt naming)
        from .theme import Theme

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = self._thickness / 2.0
        rect = QRectF(
            inset, inset,
            self._diameter - self._thickness,
            self._diameter - self._thickness,
        )
        pen = QPen(Theme.color("border"), self._thickness)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(rect, 0, 360 * 16)

        pen.setColor(Theme.color("accent"))
        painter.setPen(pen)
        painter.drawArc(rect, int(-self._angle * 16), int(110 * 16))


class PulseDots(QWidget):
    """Three softly pulsing dots, used for 'waiting' states."""

    def __init__(self, diameter=7, spacing=6, parent=None):
        super().__init__(parent)
        self._d = diameter
        self._spacing = spacing
        self._phase = 0.0
        self.setFixedSize(diameter * 3 + spacing * 2, diameter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def start(self):
        self.show()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self):
        self._timer.stop()
        self.hide()

    def is_running(self):
        return self._timer.isActive()

    def _tick(self):
        self._phase = (self._phase + 0.12) % 1.0
        self.update()

    def paintEvent(self, event):  # noqa: N802
        import math

        from .theme import Theme

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = Theme.color("accent")
        for i in range(3):
            wave = 0.45 + 0.55 * (0.5 + 0.5 * math.sin((self._phase + i * 0.18) * 2 * math.pi))
            size = self._d * wave
            x = i * (self._d + self._spacing) + (self._d - size) / 2
            y = (self._d - size) / 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), int(255 * wave)))
            painter.drawEllipse(QRectF(x, y, size, size))
