"""Base class for Lume pages: a header plus a centred, scrollable column."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)

CONTENT_MAX_WIDTH = 940


class Page(QWidget):
    """Scrollable page with an optional title/subtitle and a width-capped column."""

    def __init__(self, api, title="", subtitle="", parent=None):
        super().__init__(parent)
        self.api = api

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(scroll)
        self.scroll = scroll

        holder = QWidget()
        holder.setObjectName("PageSurface")
        scroll.setWidget(holder)

        centering = QHBoxLayout(holder)
        centering.setContentsMargins(34, 30, 34, 34)
        centering.setSpacing(0)
        centering.addStretch(1)

        column = QWidget()
        column.setObjectName("Transparent")
        column.setMaximumWidth(CONTENT_MAX_WIDTH)
        centering.addWidget(column, 10)
        centering.addStretch(1)

        self.content = QVBoxLayout(column)
        self.content.setContentsMargins(0, 0, 0, 0)
        self.content.setSpacing(16)

        if title:
            heading = QLabel(title)
            heading.setObjectName("PageTitle")
            self.content.addWidget(heading)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("PageSubtitle")
            self.content.addWidget(sub)
        if title or subtitle:
            self.content.addSpacing(4)

    def add(self, widget):
        self.content.addWidget(widget)
        return widget

    def add_layout(self, layout):
        self.content.addLayout(layout)
        return layout

    def add_stretch(self):
        self.content.addStretch(1)

    def toast(self, text, level="info"):
        window = self.window()
        if hasattr(window, "show_toast"):
            window.show_toast(text, level)
