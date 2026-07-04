"""Home page: gradient hero and the three feature entry cards."""

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import icons
from ..controls import IconBadge
from ..page import Page
from ..theme import Theme
from ..widgets import Card


class HeroCard(QFrame):
    """Gradient banner painted by hand so it works in light and dark themes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(168)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(34, 30, 34, 30)
        layout.setSpacing(20)

        text = QVBoxLayout()
        text.setSpacing(8)
        eyebrow = QLabel("LUME ·  AI 教学材料生成")
        eyebrow.setStyleSheet("color: rgba(255,255,255,0.78); font-size: 12px; font-weight: 600;")
        time_title = QLabel("让英语备课，快一点")
        time_title.setStyleSheet("color: #ffffff; font-size: 30px; font-weight: 700;")
        subtitle = QLabel("上传试卷、音频或题目，选一个模型，剩下的排版与整理交给 Lume。")
        subtitle.setStyleSheet("color: rgba(255,255,255,0.88); font-size: 14px;")
        subtitle.setWordWrap(True)
        text.addWidget(eyebrow)
        text.addWidget(time_title)
        text.addWidget(subtitle)
        text.addStretch(1)
        layout.addLayout(text, 1)

        mark = QLabel()
        mark.setFont(icons.font(62))
        mark.setText(icons.text("wand-sparkles"))
        mark.setStyleSheet("color: rgba(255,255,255,0.92); background: transparent;")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignVCenter)

    def paintEvent(self, event):  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())

        gradient = Theme.colors
        from PySide6.QtGui import QLinearGradient

        g = QLinearGradient(rect.topLeft(), rect.bottomRight())
        g.setColorAt(0.0, QColor(gradient["gradient_from"]))
        g.setColorAt(1.0, QColor(gradient["gradient_to"]))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(g)
        painter.drawRoundedRect(rect, 18, 18)

        glow = QColor(255, 255, 255, 26)
        painter.setBrush(glow)
        painter.drawEllipse(QRectF(rect.width() - 190, -70, 230, 230))
        painter.setBrush(QColor(255, 255, 255, 18))
        painter.drawEllipse(QRectF(rect.width() - 90, 40, 150, 150))


class FeatureCard(Card):
    clicked = Signal()

    def __init__(self, icon_name, tone, title, description, parent=None):
        super().__init__(parent, hover=True, padding=22, spacing=12)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        badge = IconBadge(icon_name, 46, tone, radius=14)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(badge)
        row.addStretch(1)
        arrow = QLabel()
        arrow.setFont(icons.font(15))
        arrow.setText(icons.text("arrow-right"))
        arrow.setStyleSheet(f"color: {Theme.colors['text_muted']}; background: transparent;")
        row.addWidget(arrow)
        self.body.addLayout(row)

        heading = QLabel(title)
        heading.setObjectName("CardTitle")
        self.body.addWidget(heading)

        desc = QLabel(description)
        desc.setObjectName("Muted")
        desc.setWordWrap(True)
        self.body.addWidget(desc)
        self.body.addStretch(1)

    def mouseReleaseEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class HomePage(Page):
    def __init__(self, api, navigate, parent=None):
        super().__init__(api, parent=parent)
        self.navigate = navigate

        self.add(HeroCard())
        self.content.addSpacing(6)

        caption = QLabel("选择一项开始")
        caption.setObjectName("SectionTitle")
        self.add(caption)

        cards = QWidget()
        cards.setObjectName("Transparent")
        cards_layout = QHBoxLayout(cards)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(18)

        specs = [
            ("file-lines", "accent", "试卷转换",
             "上传 PDF 或手机拍照，AI 识别整理为标准化文档，导出 Word 与 PPT。", 1),
            ("headphones", "success", "听力材料生成",
             "上传音频自动转写，AI 整理成听力练习材料，一键导出。", 2),
            ("pen-nib", "warning", "作文思路生成",
             "输入阅读原文或题目，生成写作思路、情节结构与高分表达。", 3),
        ]
        for icon_name, tone, title, desc, index in specs:
            card = FeatureCard(icon_name, tone, title, desc)
            card.clicked.connect(lambda i=index: self.navigate(i))
            cards_layout.addWidget(card, 1)

        self.add(cards)
        self.content.addSpacing(10)

        tips = Card(padding=20, spacing=12)
        tips_header = QHBoxLayout()
        tips_header.setSpacing(9)
        bulb = QLabel()
        bulb.setFont(icons.font(14))
        bulb.setText(icons.text("lightbulb"))
        bulb.setStyleSheet(f"color: {Theme.colors['warning']}; background: transparent;")
        tips_header.addWidget(bulb)
        tips_title = QLabel("第一次使用？")
        tips_title.setObjectName("SectionTitle")
        tips_header.addWidget(tips_title)
        tips_header.addStretch(1)
        tips.body.addLayout(tips_header)

        tip = QLabel("先到「设置 → AI 模型列表」添加一个 OpenAI 兼容接口（Base URL / API Key / 模型名），"
                     "即可开始使用全部功能。OCR 模式还需要本地运行 Umi-OCR 服务。")
        tip.setObjectName("Muted")
        tip.setWordWrap(True)
        tips.body.addWidget(tip)
        self.add(tips)

        self.add_stretch()
