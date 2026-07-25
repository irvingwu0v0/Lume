"""Settings page: OCR service config and AI model management."""

import json
from urllib.parse import urlsplit

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QVBoxLayout, QWidget,
)

from .. import icons
from ..controls import IconBadge, IconButton, Tag, ToggleSwitch
from ..page import Page
from ..theme import Theme
from ..widgets import Card, hline, make_card


class ModelDialog(QDialog):
    def __init__(self, parent=None, model=None):
        super().__init__(parent)
        self.setWindowTitle("编辑 AI 模型" if model else "添加 AI 模型")
        self.setMinimumWidth(460)
        self.model = model or {}
        self.values = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(IconBadge("brain", 42, "accent", radius=12))
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        title = QLabel("编辑模型配置" if model else "添加模型配置")
        title.setObjectName("CardTitle")
        subtitle = QLabel("任何 OpenAI 兼容的 /chat/completions 接口都可以")
        subtitle.setObjectName("Hint")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text)
        header.addStretch(1)
        layout.addLayout(header)

        form = QFormLayout()
        form.setSpacing(11)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.alias = QLineEdit(self.model.get("alias", ""))
        self.alias.setPlaceholderText("如：DeepSeek V4 Pro")
        self.base_url = QLineEdit(self.model.get("base_url", ""))
        self.base_url.setPlaceholderText("如：https://api.deepseek.com")
        self.model_name = QLineEdit(self.model.get("model_name", ""))
        self.model_name.setPlaceholderText("如：deepseek-v4-pro")

        self.api_key = QLineEdit(self.model.get("api_key", ""))
        self.api_key.setPlaceholderText("sk-...")
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.reveal = IconButton("", "eye", "ghost", height=34, padding=6,
                                 icon_size=14, radius=8, tooltip="显示 / 隐藏密钥")
        self.reveal.setCheckable(True)
        self.reveal.toggled.connect(self._toggle_reveal)
        key_row = QWidget()
        key_row.setObjectName("Transparent")
        key_layout = QHBoxLayout(key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(6)
        key_layout.addWidget(self.api_key, 1)
        key_layout.addWidget(self.reveal)

        form.addRow("模型代称", self.alias)
        form.addRow("Base URL", self.base_url)
        form.addRow("模型名称", self.model_name)
        form.addRow("API Key", key_row)
        layout.addLayout(form)

        options = Card(padding=14, spacing=10)
        options.body.addWidget(self._switch_row(
            "思考模式", "对推理模型发送 thinking 参数",
            bool(self.model.get("thinking_enabled")), "thinking",
        ))
        options.body.addWidget(hline())
        options.body.addWidget(self._switch_row(
            "视觉模型", "可用于试卷拍照 / 视觉识别模式",
            bool(self.model.get("vision_enabled")), "vision",
        ))
        layout.addWidget(options)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = IconButton("取消", "", "ghost", height=38)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = IconButton("保存", "floppy-disk", "primary", height=38, icon_size=14)
        save.clicked.connect(self._on_save)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def _switch_row(self, title, description, checked, attribute):
        row = QWidget()
        row.setObjectName("Transparent")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        text = QVBoxLayout()
        text.setSpacing(1)
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600; background: transparent;")
        hint = QLabel(description)
        hint.setObjectName("Hint")
        text.addWidget(label)
        text.addWidget(hint)
        layout.addLayout(text, 1)
        switch = ToggleSwitch()
        switch.setChecked(checked)
        layout.addWidget(switch)
        setattr(self, attribute, switch)
        return row

    def _toggle_reveal(self, shown):
        self.api_key.setEchoMode(
            QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
        )

    def _on_save(self):
        if not all([
            self.alias.text().strip(), self.base_url.text().strip(),
            self.model_name.text().strip(), self.api_key.text().strip(),
        ]):
            QMessageBox.warning(self, "提示", "请填写所有字段")
            return
        parsed_url = urlsplit(self.base_url.text().strip())
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            QMessageBox.warning(self, "提示", "Base URL 必须是有效的 http:// 或 https:// 地址")
            return
        self.values = {
            "alias": self.alias.text().strip(),
            "base_url": self.base_url.text().strip(),
            "model_name": self.model_name.text().strip(),
            "api_key": self.api_key.text().strip(),
            "thinking_enabled": self.thinking.isChecked(),
            "vision_enabled": self.vision.isChecked(),
        }
        self.accept()


class SettingsPage(Page):
    def __init__(self, api, parent=None):
        super().__init__(
            api, title="设置",
            subtitle="管理 AI 模型与 OCR 服务，配置保存在本地 data/ 目录。",
            parent=parent,
        )
        self._build_ocr_card()

        self.list_container = QWidget()
        self.list_container.setObjectName("Transparent")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(10)
        self.add(self.list_container)

        self.empty_card = Card(padding=26, spacing=8)
        self.empty_card.body.addWidget(
            self._centered("inbox", 30, Theme.colors["text_muted"])
        )
        empty_text = QLabel("还没有任何模型")
        empty_text.setObjectName("SectionTitle")
        empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_card.body.addWidget(empty_text)
        empty_hint = QLabel("点击上方「添加模型」，填入 OpenAI 兼容接口信息即可开始")
        empty_hint.setObjectName("Hint")
        empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_card.body.addWidget(empty_hint)
        self.add(self.empty_card)

        self.add_stretch()

        self.api.modelsChanged.connect(self.load_models)
        self.api.modelTested.connect(self._on_model_tested)
        self.api.ocrTested.connect(self._on_ocr_tested)
        self.load_ocr_config()
        self.load_models()

    def _centered(self, icon_name, size, color):
        label = QLabel()
        label.setFont(icons.font(size))
        label.setText(icons.text(icon_name))
        label.setStyleSheet(f"color: {color}; background: transparent;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    # ── OCR ─────────────────────────────────────────────────────
    def _build_ocr_card(self):
        card, layout = make_card()

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(IconBadge("server", 42, "accent", radius=12))
        header_text = QVBoxLayout()
        header_text.setSpacing(2)
        title = QLabel("Umi OCR API")
        title.setObjectName("CardTitle")
        desc = QLabel("用于 PDF 扫描件的文字识别服务，默认端口 1224")
        desc.setObjectName("Hint")
        header_text.addWidget(title)
        header_text.addWidget(desc)
        header.addLayout(header_text)
        header.addStretch(1)
        layout.addLayout(header)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.ocr_host = QLineEdit()
        self.ocr_host.setPlaceholderText("主机，如 127.0.0.1")
        self.ocr_port = QLineEdit()
        self.ocr_port.setPlaceholderText("端口，如 1224")
        self.ocr_port.setFixedWidth(150)
        row.addWidget(self.ocr_host, 1)
        row.addWidget(self.ocr_port)
        row.addStretch(1)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        test = IconButton("测试连接", "flask", "secondary", height=38, icon_size=14)
        test.clicked.connect(self._test_ocr)
        buttons.addWidget(test)
        save = IconButton("保存", "floppy-disk", "primary", height=38, icon_size=14)
        save.clicked.connect(
            lambda: self.api.saveOcrConfig(self.ocr_host.text(), self.ocr_port.text())
        )
        buttons.addWidget(save)
        layout.addLayout(buttons)
        self.add(card)

        self.add(hline())

        models_header = QHBoxLayout()
        models_header.setSpacing(12)
        models_header.addWidget(self._centered("layer-group", 20, Theme.colors["accent"]))
        models_title = QLabel("AI 模型列表")
        models_title.setObjectName("CardTitle")
        models_header.addWidget(models_title)
        models_header.addStretch(1)
        add = IconButton("添加模型", "plus", "primary", height=38, icon_size=13)
        add.clicked.connect(self._add_model)
        models_header.addWidget(add)
        self.add_layout(models_header)

    def load_ocr_config(self):
        try:
            config = json.loads(self.api.getOcrConfig())
        except Exception:
            return
        self.ocr_host.setText(config.get("ocr_host", ""))
        self.ocr_port.setText(config.get("ocr_port", ""))

    def _test_ocr(self):
        url = f"http://{self.ocr_host.text()}:{self.ocr_port.text()}/"
        self.toast("正在测试 OCR 连接...", "info")
        self.api.testOcrConnection(url)

    def _on_ocr_tested(self, payload):
        try:
            reply = json.loads(payload)
        except Exception:
            reply = {"ok": False}
        if reply.get("ok"):
            self.toast("OCR 连接成功，Umi OCR 服务正常", "success")
        else:
            self.toast(reply.get("detail", "无法连接到 OCR 服务"), "error")

    # ── models ──────────────────────────────────────────────────
    def load_models(self):
        while self.list_layout.count() > 0:
            item = self.list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        try:
            models = json.loads(self.api.getModelsJson())
        except Exception:
            models = []
        for model in models:
            self.list_layout.addWidget(self._model_card(model))
        self.empty_card.setVisible(not models)

    def _model_card(self, model):
        card = Card(padding=16, spacing=10)
        row = QHBoxLayout()
        row.setSpacing(14)

        tone = "accent"
        icon_name = "brain"
        if model.get("vision_enabled"):
            icon_name = "eye"
            tone = "success"
        row.addWidget(IconBadge(icon_name, 44, tone, radius=13))

        info = QVBoxLayout()
        info.setSpacing(5)
        name_row = QHBoxLayout()
        name_row.setSpacing(7)
        alias = QLabel(model.get("alias", ""))
        alias.setStyleSheet("font-weight: 600; font-size: 15px; background: transparent;")
        name_row.addWidget(alias)
        if model.get("thinking_enabled"):
            name_row.addWidget(Tag("思考", "warning"))
        if model.get("vision_enabled"):
            name_row.addWidget(Tag("视觉", "success"))
        name_row.addStretch(1)
        info.addLayout(name_row)

        detail = QLabel(f"{model.get('model_name', '')}   ·   {model.get('base_url', '')}")
        detail.setObjectName("Hint")
        info.addWidget(detail)
        row.addLayout(info, 1)

        actions = QHBoxLayout()
        actions.setSpacing(2)
        edit = IconButton("", "pen", "ghost", height=34, padding=8, icon_size=14,
                          radius=8, tooltip="编辑")
        edit.clicked.connect(lambda: self._edit_model(model))
        actions.addWidget(edit)
        test = IconButton("", "flask", "ghost", height=34, padding=8, icon_size=14,
                          radius=8, tooltip="测试连接")
        test.clicked.connect(lambda: self._test_model(model))
        actions.addWidget(test)
        delete = IconButton("", "trash", "danger", height=34, padding=8, icon_size=14,
                            radius=8, tooltip="删除")
        delete.clicked.connect(lambda: self._delete_model(model))
        actions.addWidget(delete)
        row.addLayout(actions)
        card.body.addLayout(row)
        return card

    def _add_model(self):
        dialog = ModelDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.values:
            values = dialog.values
            self.api.addModel(
                values["alias"], values["base_url"], values["model_name"],
                values["api_key"], values["thinking_enabled"], values["vision_enabled"],
            )

    def _edit_model(self, model):
        dialog = ModelDialog(self, model)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.values:
            values = dialog.values
            self.api.updateModel(
                model["id"], values["alias"], values["base_url"], values["model_name"],
                values["api_key"], values["thinking_enabled"], values["vision_enabled"],
            )

    def _test_model(self, model):
        self.toast(f"正在测试「{model.get('alias', '')}」...", "info")
        self.api.testModel(model["id"])

    def _on_model_tested(self, _model_id, payload):
        try:
            reply = json.loads(payload)
        except Exception:
            reply = {"ok": False}
        if reply.get("ok"):
            self.toast(f"连接成功，延迟 {reply.get('elapsed_ms')}ms", "success")
        else:
            detail = reply.get("detail") or reply.get("status") or "未知错误"
            self.toast(str(detail), "error")

    def _delete_model(self, model):
        confirm = QMessageBox.question(
            self, "确认删除", "确定要删除此模型吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.api.deleteModel(model["id"])
