"""Exam conversion: PDF or phone photos -> OCR / vision -> Word / PPT."""

from io import BytesIO
import json
import os

import qrcode
from PySide6.QtCore import QRectF, Qt, QUrl
from PySide6.QtGui import QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QScrollArea, QStackedWidget,
    QVBoxLayout, QWidget,
)

from .. import icons
from ..controls import IconBadge, IconButton, RadioButton, SegmentedControl, ToggleSwitch
from ..page import Page
from ..theme import Theme
from ..widgets import (
    Card, DropZone, ModelSelector, StepIndicator, StreamResultPanel, make_card, top_aligned,
)

THUMB_W, THUMB_H = 104, 132


def _local_path(url_or_path):
    if url_or_path.startswith("file:"):
        return QUrl(url_or_path).toLocalFile()
    return url_or_path


def _rounded_thumb(path, width, height, radius=8):
    pixmap = QPixmap(_local_path(path))
    if pixmap.isNull():
        return pixmap
    scaled = pixmap.scaled(
        width, height,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    x = max(0, (scaled.width() - width) // 2)
    y = max(0, (scaled.height() - height) // 2)
    cropped = scaled.copy(x, y, width, height)

    rounded = QPixmap(width, height)
    rounded.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, width, height), radius, radius)
    painter.setClipPath(clip)
    painter.drawPixmap(0, 0, cropped)
    painter.end()
    return rounded


class Thumbnail(QWidget):
    def __init__(self, path, index, count, on_move, on_delete, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        holder = QLabel()
        holder.setFixedSize(THUMB_W, THUMB_H)
        holder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        holder.setStyleSheet(
            f"border: 1px solid {Theme.colors['border']}; border-radius: 8px;"
            f" background: {Theme.colors['hover']};"
        )
        pixmap = _rounded_thumb(path, THUMB_W, THUMB_H)
        if not pixmap.isNull():
            holder.setPixmap(pixmap)
        else:
            holder.setFont(icons.font(28))
            holder.setStyleSheet(
                holder.styleSheet() + f" color: {Theme.colors['text_muted']};"
            )
            holder.setText(icons.text("image"))
        layout.addWidget(holder)

        controls = QHBoxLayout()
        controls.setSpacing(2)
        index_label = QLabel(f"{index + 1}")
        index_label.setObjectName("Hint")
        index_label.setFixedWidth(16)
        controls.addWidget(index_label)

        def small(icon_name, enabled, slot, tooltip):
            button = IconButton("", icon_name, "ghost", height=24, padding=4,
                                icon_size=11, radius=6, tooltip=tooltip)
            button.setFixedSize(24, 24)
            button.setEnabled(enabled)
            button.clicked.connect(slot)
            return button

        controls.addWidget(small("arrow-up", index > 0,
                                 lambda: on_move(index, index - 1), "上移"))
        controls.addWidget(small("arrow-down", index < count - 1,
                                 lambda: on_move(index, index + 1), "下移"))
        controls.addWidget(small("trash", True, lambda: on_delete(index), "删除"))
        controls.addStretch(1)
        layout.addLayout(controls)


class PdfConvertPage(Page):
    def __init__(self, api, parent=None):
        super().__init__(
            api, title="试卷转换",
            subtitle="上传 PDF 或手机拍照，AI 识别整理后导出 Word / PPT。",
            parent=parent,
        )
        self.upload_mode = "pdf"
        self.pdf_file = ""
        self.pdf_mode = "ocr"
        self.phone_image_count = 0
        self._phone_paths = []
        self._phone_url = ""

        self.indicator = StepIndicator()
        self.indicator.set_steps(["上传试卷", "识别设置", "结果导出"])
        self.add(self.indicator)

        self.stack = QStackedWidget()
        self.add(self.stack)
        self.stack.addWidget(top_aligned(self._build_step1()))
        self.stack.addWidget(top_aligned(self._build_step2()))
        self.stack.addWidget(self._build_step3())

        self.api.ocrProgress.connect(self._on_ocr_progress)
        self.api.ocrDone.connect(self._on_ocr_done)
        self.api.ocrError.connect(self._on_ocr_error)
        self.api.pdfToImagesDone.connect(self._on_images_done)
        self.api.pdfToImagesError.connect(self._on_images_error)
        self.api.pdfChunk.connect(self.result_panel.append_chunk)
        self.api.pdfDone.connect(self._on_pdf_done)
        self.api.pdfError.connect(self._on_pdf_error)
        self.api.phoneImageReceived.connect(self._on_phone_image_received)
        self.api.phoneImagesChanged.connect(self._on_phone_images_changed)
        self.api.phoneStartRequested.connect(self._on_phone_start_requested)

        self.goto_step(1)
        self.add_stretch()

    # ── step 1 ──────────────────────────────────────────────────
    def _build_step1(self):
        card, layout = make_card()
        layout.addWidget(self._bold("上传试卷"))

        self.mode_control = SegmentedControl([
            ("file-pdf", "上传 PDF 文件"),
            ("mobile-screen", "手机浏览器上传"),
        ])
        self.mode_control.changed.connect(self._on_upload_mode_changed)
        layout.addWidget(self.mode_control)

        self.upload_stack = QStackedWidget()
        self.upload_stack.addWidget(self._build_pdf_panel())
        self.upload_stack.addWidget(self._build_phone_panel())
        layout.addWidget(self.upload_stack)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.next_button = IconButton("下一步：识别设置", "arrow-right", "primary",
                                      height=40, icon_size=14)
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self._go_step2)
        footer.addWidget(self.next_button)
        layout.addLayout(footer)
        return card

    def _build_pdf_panel(self):
        panel = QWidget()
        panel.setObjectName("Transparent")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.pdf_drop = DropZone("file-pdf", "点击选择 PDF 试卷",
                                 "支持文字版与扫描件，最大程度保留排版", min_height=160)
        self.pdf_drop.clicked.connect(self._pick_pdf)
        layout.addWidget(self.pdf_drop)

        self.pdf_card = Card(padding=14, spacing=10)
        self.pdf_card.setVisible(False)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(IconBadge("file-pdf", 42, "error", radius=12))
        info = QVBoxLayout()
        info.setSpacing(2)
        self.pdf_name = QLabel("")
        self.pdf_name.setStyleSheet("font-weight: 600; background: transparent;")
        self.pdf_info = QLabel("")
        self.pdf_info.setObjectName("Hint")
        info.addWidget(self.pdf_name)
        info.addWidget(self.pdf_info)
        row.addLayout(info, 1)
        replace = IconButton("重新选择", "rotate-right", "ghost", height=34, icon_size=13)
        replace.clicked.connect(self._pick_pdf)
        row.addWidget(replace)
        self.pdf_card.body.addLayout(row)
        layout.addWidget(self.pdf_card)
        return panel

    def _build_phone_panel(self):
        panel = QWidget()
        panel.setObjectName("Transparent")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        connection_card = Card(padding=20, spacing=14)
        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(IconBadge("qrcode", 40, "accent", radius=11))
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        header_text.addWidget(self._bold("扫码打开上传页面"))
        subtitle = QLabel("无需安装 App，仅通过局域网 HTTP 上传")
        subtitle.setObjectName("Hint")
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)
        connection_card.body.addLayout(header)

        connection = QHBoxLayout()
        connection.setSpacing(20)
        self.qr_label = QLabel()
        self.qr_label.setFixedSize(184, 184)
        self.qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.qr_label.setStyleSheet(
            f"background: white; border: 1px solid {Theme.colors['border']};"
            " border-radius: 14px; padding: 10px;"
        )
        connection.addWidget(self.qr_label)

        details = QVBoxLayout()
        details.setSpacing(9)
        details.addWidget(self._bold("手机和电脑需连接同一网络"))
        guide = QLabel(
            "1. 用手机相机扫描左侧二维码\n"
            "2. 在网页中拍照或选择图片\n"
            "3. 上传完成后进入识别设置"
        )
        guide.setObjectName("Hint")
        guide.setWordWrap(True)
        details.addWidget(guide)
        details.addStretch(1)

        self.ip_label = QLabel("正在启动上传服务...")
        self.ip_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.ip_label.setWordWrap(True)
        self.ip_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {Theme.colors['accent']};"
            f" background: {Theme.colors['hover']}; border-radius: 8px; padding: 9px;"
        )
        details.addWidget(self.ip_label)

        copy_button = IconButton("复制上传地址", "copy", "secondary", height=34, icon_size=13)
        copy_button.clicked.connect(self._copy_phone_url)
        details.addWidget(copy_button, 0, Qt.AlignmentFlag.AlignLeft)

        self.network_label = QLabel("网络：未知网络")
        self.network_label.setObjectName("Hint")
        details.addWidget(self.network_label)
        connection.addLayout(details, 1)
        connection_card.body.addLayout(connection)
        layout.addWidget(connection_card)

        uploaded_card = Card(padding=18, spacing=12)
        uploaded_header = QHBoxLayout()
        uploaded_header.setSpacing(9)
        uploaded_header.addWidget(IconBadge("images", 34, "success", radius=9))
        uploaded_header.addWidget(self._bold("已上传图片"))
        uploaded_header.addStretch(1)
        self.count_label = QLabel("0 张已上传")
        self.count_label.setObjectName("Muted")
        uploaded_header.addWidget(self.count_label)
        uploaded_card.body.addLayout(uploaded_header)

        self.phone_hint = QLabel("手机网页上传后会自动显示，可在任一端调整顺序或删除")
        self.phone_hint.setObjectName("Hint")
        uploaded_card.body.addWidget(self.phone_hint)

        self.thumbs_scroll = QScrollArea()
        self.thumbs_scroll.setWidgetResizable(True)
        self.thumbs_scroll.setFixedHeight(190)
        self.thumbs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.thumbs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.thumbs_scroll.viewport().setAutoFillBackground(False)
        self.thumbs_holder = QWidget()
        self.thumbs_holder.setObjectName("Transparent")
        self.thumbs_layout = QHBoxLayout(self.thumbs_holder)
        self.thumbs_layout.setContentsMargins(0, 0, 0, 0)
        self.thumbs_layout.setSpacing(10)
        self.thumbs_layout.addStretch(1)
        self.thumbs_scroll.setWidget(self.thumbs_holder)
        uploaded_card.body.addWidget(self.thumbs_scroll)

        self.phone_empty = QLabel("暂无图片，请在手机端拍照上传")
        self.phone_empty.setObjectName("Hint")
        self.phone_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phone_empty.setMinimumHeight(54)
        uploaded_card.body.addWidget(self.phone_empty)
        layout.addWidget(uploaded_card)
        return panel

    # ── step 2 ──────────────────────────────────────────────────
    def _build_step2(self):
        card, layout = make_card()
        layout.addWidget(self._bold("识别方式与模型"))

        self.phone_tip = QLabel("手机拍照建议使用视觉模型，识别效果更好")
        self.phone_tip.setObjectName("Hint")
        self.phone_tip.setVisible(False)
        layout.addWidget(self.phone_tip)

        self.vision_radio = RadioButton("视觉模型模式 — 多模态模型直接读图")
        self.ocr_radio = RadioButton("OCR 模式 — Umi-OCR 提取文字后再整理")
        self.ocr_radio.setChecked(True)
        # Both must be connected: only the newly-checked one should switch modes.
        self.vision_radio.toggled.connect(self._on_pdf_mode_changed)
        self.ocr_radio.toggled.connect(self._on_pdf_mode_changed)
        layout.addWidget(self.vision_radio)
        layout.addWidget(self.ocr_radio)

        self.batch_row, self.batch_check = self._toggle_row(
            "分批发送", "图片超过 9 张时按批处理，避免超出上下文")
        self.split_row, self.split_check = self._toggle_row(
            "分两次进行", "先梳理结构再生成内容，缓解长文本压力")
        self.batch_row.setVisible(False)
        layout.addWidget(self.batch_row)
        layout.addWidget(self.split_row)

        layout.addSpacing(6)
        layout.addWidget(self._bold("选择 AI 模型"))
        self.model_selector = ModelSelector(self.api)
        layout.addWidget(self.model_selector)

        self.empty_hint = QLabel("暂未配置模型，请先在「设置」页面添加 AI 模型")
        self.empty_hint.setObjectName("Error")
        self.empty_hint.setVisible(False)
        layout.addWidget(self.empty_hint)

        buttons = QHBoxLayout()
        back = IconButton("上一步", "arrow-left", "ghost", height=40, icon_size=14)
        back.clicked.connect(lambda: self.goto_step(1))
        buttons.addWidget(back)
        buttons.addStretch(1)
        self.start_button = IconButton("确认，开始识别", "wand-sparkles", "primary",
                                       height=40, icon_size=15)
        self.start_button.clicked.connect(self._start_generation)
        buttons.addWidget(self.start_button)
        layout.addLayout(buttons)
        return card

    def _toggle_row(self, title, description):
        row = QWidget()
        row.setObjectName("Transparent")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(12)

        text = QVBoxLayout()
        text.setSpacing(2)
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600; background: transparent;")
        hint = QLabel(description)
        hint.setObjectName("Hint")
        text.addWidget(label)
        text.addWidget(hint)
        layout.addLayout(text, 1)

        switch = ToggleSwitch()
        layout.addWidget(switch)
        return row, switch

    # ── step 3 ──────────────────────────────────────────────────
    def _build_step3(self):
        card = QWidget()
        card.setObjectName("Transparent")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.result_panel = StreamResultPanel("生成结果")
        self.result_panel.stop_requested.connect(self._stop)
        layout.addWidget(self.result_panel)

        actions = QHBoxLayout()
        back = IconButton("上一步", "arrow-left", "ghost", height=40, icon_size=14)
        back.clicked.connect(lambda: (self._stop(), self.goto_step(2)))
        actions.addWidget(back)
        actions.addStretch(1)
        self.word_button = IconButton("导出 Word", "file-word", "primary",
                                      height=40, icon_size=15)
        self.word_button.clicked.connect(self._export_word)
        actions.addWidget(self.word_button)
        self.ppt_button = IconButton("导出 PPT", "file-powerpoint", "secondary",
                                     height=40, icon_size=15)
        self.ppt_button.clicked.connect(self._export_ppt)
        actions.addWidget(self.ppt_button)
        layout.addLayout(actions)
        layout.addStretch(1)
        return card

    # ── navigation / mode ───────────────────────────────────────
    def goto_step(self, step):
        self.stack.setCurrentIndex(step - 1)
        self.indicator.set_current(step)
        show_actions = step == 3
        self.word_button.setVisible(show_actions)
        self.ppt_button.setVisible(show_actions)
        if step == 2:
            self.model_selector.filter_vision = (self.pdf_mode == "vision")
            self.model_selector.reload()
            self.empty_hint.setVisible(self.model_selector.model_count == 0)
        self._update_next_enabled()

    def _bold(self, text):
        label = QLabel(text)
        label.setObjectName("CardTitle")
        return label

    def _on_upload_mode_changed(self, index):
        self.upload_mode = "pdf" if index == 0 else "phone"
        if self.upload_mode == "phone":
            self.upload_stack.setCurrentIndex(1)
            self._start_phone_connection()
            self._set_pdf_mode("vision")
        else:
            self.upload_stack.setCurrentIndex(0)
            self._stop_phone_connection()
            self._set_pdf_mode("ocr")
        self.phone_tip.setVisible(self.upload_mode == "phone")
        self.ocr_radio.setVisible(self.upload_mode == "pdf")
        self._update_next_enabled()

    def _on_pdf_mode_changed(self, checked):
        if not checked:
            return
        self._set_pdf_mode("vision" if self.vision_radio.isChecked() else "ocr")

    def _set_pdf_mode(self, mode):
        self.pdf_mode = mode
        if mode == "vision":
            self.vision_radio.setChecked(True)
        else:
            self.ocr_radio.setChecked(True)
        self.batch_row.setVisible(mode == "vision")
        self.split_row.setVisible(mode == "ocr")
        if self.stack.currentIndex() == 1:
            self.model_selector.filter_vision = (mode == "vision")
            self.model_selector.reload()

    def _update_next_enabled(self):
        if self.upload_mode == "pdf":
            self.next_button.setEnabled(bool(self.pdf_file))
        else:
            self.next_button.setEnabled(self.phone_image_count > 0)

    # ── step 1 actions ──────────────────────────────────────────
    def _pick_pdf(self):
        path = self.api.openFileDialog("PDF 文件 (*.pdf)")
        if not path:
            return
        self.pdf_file = path
        self.pdf_name.setText(os.path.basename(path))
        try:
            size = os.path.getsize(path) / 1024 / 1024
            self.pdf_info.setText(f"{size:.1f} MB")
        except OSError:
            self.pdf_info.setText("")
        self.pdf_drop.set_content("已选择 PDF 文件", "点击此处可重新选择", "circle-check")
        self.pdf_card.setVisible(True)
        self._update_next_enabled()

    def _go_step2(self):
        self.goto_step(2)

    def _start_phone_connection(self):
        self._phone_paths = []
        self.phone_image_count = 0
        self._phone_url = ""
        network = self.api.getPhoneNetworkName()
        self.network_label.setText("网络：" + (network or "未知网络"))
        if not self.api.startPhoneServer():
            self.toast("HTTP 端口 18924 可能被占用，请关闭其他 Lume 实例后重试", "error")
            self.ip_label.setText("上传服务启动失败")
            self.qr_label.clear()
        else:
            self._phone_url = self.api.getPhoneConnectionUrl()
            self.ip_label.setText(self._phone_url)
            self._set_qr_code(self._phone_url)
        self._update_phone_panel()

    def _stop_phone_connection(self):
        self.api.stopPhoneServer()
        self.phone_image_count = 0
        self._phone_paths = []
        self._phone_url = ""
        self.qr_label.clear()
        self._update_phone_panel()

    def _set_qr_code(self, url):
        qr = qrcode.QRCode(version=None, box_size=8, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        image = qr.make_image(fill_color="#172033", back_color="white")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue(), "PNG")
        self.qr_label.setPixmap(pixmap.scaled(
            164, 164, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def _copy_phone_url(self):
        if not self._phone_url:
            self.toast("上传服务尚未启动", "error")
            return
        QApplication.clipboard().setText(self._phone_url)
        self.toast("上传地址已复制", "success")

    def _update_phone_panel(self):
        self.thumbs_scroll.setVisible(self.phone_image_count > 0)
        self.phone_empty.setVisible(self.phone_image_count == 0)
        self.count_label.setText(f"{self.phone_image_count} 张已上传")

    def _rebuild_thumbnails(self):
        while self.thumbs_layout.count() > 0:
            item = self.thumbs_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index, path in enumerate(self._phone_paths):
            self.thumbs_layout.addWidget(Thumbnail(
                path, index, len(self._phone_paths),
                self.api.movePhoneImage, self.api.deletePhoneImage,
            ))
        self.thumbs_layout.addStretch(1)
        self.phone_image_count = len(self._phone_paths)
        self._update_phone_panel()
        self._update_next_enabled()

    # ── step 2 / 3 actions ──────────────────────────────────────
    def _start_generation(self):
        if self.model_selector.model_count == 0:
            self.goto_step(2)
            self.toast("请先在「设置」中添加可用的 AI 模型", "error")
            return
        self.goto_step(3)
        self.result_panel.begin("正在处理...")
        model_id = self.model_selector.selected_model_id
        thinking = self.model_selector.selected_model_thinking
        if self.upload_mode == "phone":
            self.api.startVisionGeneration(
                self.api.getPhoneImagesJson(), model_id, thinking, self.batch_check.isChecked()
            )
        elif self.pdf_mode == "ocr":
            self.api.startPdfOcr(self.pdf_file)
        else:
            self.api.startPdfToImages(self.pdf_file)

    def _stop(self):
        self.api.cancelGeneration()
        self.result_panel.set_generating(False)

    def _export_word(self):
        reply = json.loads(self.api.savePdfDocx(self.result_panel.content))
        if reply.get("ok"):
            self.toast("Word 文档已保存", "success")
        elif not reply.get("cancelled"):
            self.toast(reply.get("error", "导出失败"), "error")

    def _export_ppt(self):
        reply = json.loads(self.api.savePdfPptx(self.result_panel.content))
        if reply.get("ok"):
            self.toast("PPT 文档已保存", "success")
        elif not reply.get("cancelled"):
            self.toast(reply.get("error", "导出失败"), "error")

    # ── signal handlers ─────────────────────────────────────────
    def _on_ocr_progress(self, pct, status):
        self.result_panel.set_status(f"{status}  {int(pct)}%" if 0 < pct < 100 else status)

    def _on_ocr_done(self, pages):
        self.result_panel.set_status("OCR 完成，正在调用 AI...")
        self.api.startPdfGeneration(
            json.dumps(pages),
            self.model_selector.selected_model_id,
            self.model_selector.selected_model_thinking,
            self.split_check.isChecked(),
        )

    def _on_ocr_error(self, err):
        self.result_panel.set_generating(False)
        self.result_panel.set_status("OCR 失败")
        self.toast(err, "error")

    def _on_images_done(self, images):
        self.result_panel.set_status("图片转换完成，正在调用 AI...")
        self.api.startVisionGeneration(
            json.dumps(images),
            self.model_selector.selected_model_id,
            self.model_selector.selected_model_thinking,
            self.batch_check.isChecked(),
        )

    def _on_images_error(self, err):
        self.result_panel.set_generating(False)
        self.result_panel.set_status("转换失败")
        self.toast(err, "error")

    def _on_pdf_done(self, content):
        self.result_panel.finish(content)

    def _on_pdf_error(self, err):
        self.result_panel.fail(err)
        self.toast(err, "error")

    def _on_phone_image_received(self, file_path):
        self._phone_paths.append(file_path)
        self._rebuild_thumbnails()

    def _on_phone_images_changed(self):
        try:
            self._phone_paths = list(json.loads(self.api.getPhoneImagePathsJson()))
        except Exception:
            self._phone_paths = []
        self._rebuild_thumbnails()

    def _on_phone_start_requested(self):
        if self.stack.currentIndex() == 0 and self.upload_mode == "phone":
            self.goto_step(2)
