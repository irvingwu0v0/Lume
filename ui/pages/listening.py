"""Listening-material workflow: audio upload -> ASR -> model -> result."""

import json
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QProgressBar, QStackedWidget, QVBoxLayout, QWidget,
)

from ..anim import BusyIndicator, animate_property
from ..controls import IconBadge, IconButton
from ..page import Page
from ..theme import Theme
from ..widgets import (
    Card, DropZone, ModelSelector, StepIndicator, StreamResultPanel, make_card, top_aligned,
)


class ListeningPage(Page):
    def __init__(self, api, parent=None):
        super().__init__(
            api, title="听力材料生成",
            subtitle="上传音频自动转写，AI 整理成可直接打印的听力练习材料。",
            parent=parent,
        )
        self.audio_file = ""
        self.transcript = ""

        self.indicator = StepIndicator()
        self.indicator.set_steps(["上传音频", "语音转写", "结果导出"])
        self.add(self.indicator)

        self.stack = QStackedWidget()
        self.add(self.stack)
        self.stack.addWidget(top_aligned(self._build_step1()))
        self.stack.addWidget(top_aligned(self._build_step2()))
        self.stack.addWidget(self._build_step3())

        self.api.asrProgress.connect(self._on_asr_progress)
        self.api.asrDone.connect(self._on_asr_done)
        self.api.asrError.connect(self._on_asr_error)
        self.api.listeningChunk.connect(self.result_panel.append_chunk)
        self.api.listeningDone.connect(self.result_panel.finish)
        self.api.listeningError.connect(self._on_error)

        self.goto_step(1)
        self.add_stretch()

    # ── step 1 ──────────────────────────────────────────────────
    def _build_step1(self):
        card, layout = make_card()
        layout.addWidget(self._bold("上传音频文件"))

        self.drop = DropZone(
            "music", "点击选择音频文件", "支持 MP3 / WAV / M4A / FLAC", min_height=170,
        )
        self.drop.clicked.connect(self._pick_audio)
        layout.addWidget(self.drop)

        self.file_card = Card(padding=14, spacing=10)
        self.file_card.setVisible(False)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(IconBadge("file-audio", 42, "success", radius=12))

        info = QVBoxLayout()
        info.setSpacing(2)
        self.file_name = QLabel("")
        self.file_name.setStyleSheet("font-weight: 600; background: transparent;")
        self.file_size = QLabel("")
        self.file_size.setObjectName("Hint")
        info.addWidget(self.file_name)
        info.addWidget(self.file_size)
        row.addLayout(info, 1)

        replace = IconButton("重新选择", "rotate-right", "ghost", height=34, icon_size=13)
        replace.clicked.connect(self._pick_audio)
        row.addWidget(replace)
        self.file_card.body.addLayout(row)
        layout.addWidget(self.file_card)

        self.asr_start_button = IconButton("开始转写", "microphone", "primary",
                                           height=40, icon_size=15)
        self.asr_start_button.setEnabled(False)
        self.asr_start_button.clicked.connect(self._start_asr)
        layout.addWidget(self.asr_start_button, 0, Qt.AlignmentFlag.AlignLeft)
        return card

    # ── step 2 ──────────────────────────────────────────────────
    def _build_step2(self):
        card, layout = make_card()

        status_row = QHBoxLayout()
        status_row.setSpacing(10)
        self.asr_spinner = BusyIndicator(18, 2.4)
        status_row.addWidget(self.asr_spinner)
        self.asr_status = QLabel("准备开始转写...")
        self.asr_status.setObjectName("Muted")
        status_row.addWidget(self.asr_status)
        status_row.addStretch(1)
        self.asr_percent = QLabel("0%")
        self.asr_percent.setObjectName("Accent")
        self.asr_percent.setStyleSheet(
            f"color: {Theme.colors['accent']}; font-weight: 600; background: transparent;"
        )
        status_row.addWidget(self.asr_percent)
        layout.addLayout(status_row)

        self.asr_bar = QProgressBar()
        self.asr_bar.setRange(0, 100)
        self.asr_bar.setTextVisible(False)
        layout.addWidget(self.asr_bar)

        layout.addSpacing(8)
        layout.addWidget(self._bold("选择 AI 整理模型"))
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
        self.start_button = IconButton("开始 AI 整理", "wand-sparkles", "primary",
                                       height=40, icon_size=15)
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._start_generation)
        buttons.addWidget(self.start_button)
        layout.addLayout(buttons)
        return card

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
        self.export_button = IconButton("导出 Word", "file-word", "primary",
                                        height=40, icon_size=15)
        self.export_button.clicked.connect(self._export)
        actions.addWidget(self.export_button)
        layout.addLayout(actions)
        layout.addStretch(1)
        return card

    # ── behaviour ───────────────────────────────────────────────
    def goto_step(self, step):
        self.stack.setCurrentIndex(step - 1)
        self.indicator.set_current(step)
        self.export_button.setVisible(step == 3)
        if step == 2:
            self.model_selector.reload()
            self.empty_hint.setVisible(self.model_selector.model_count == 0)

    def _bold(self, text):
        label = QLabel(text)
        label.setObjectName("CardTitle")
        return label

    def _pick_audio(self):
        path = self.api.openFileDialog("音频文件 (*.mp3 *.wav *.m4a *.flac)")
        if not path:
            return
        self.audio_file = path
        self.file_name.setText(os.path.basename(path))
        try:
            size = os.path.getsize(path) / 1024 / 1024
            self.file_size.setText(f"{size:.1f} MB")
        except OSError:
            self.file_size.setText("")
        self.drop.set_content("已选择音频文件", "点击此处可重新选择", "circle-check")
        self.file_card.setVisible(True)
        self.asr_start_button.setEnabled(True)

    def _start_asr(self):
        self.goto_step(2)
        self.asr_bar.setValue(0)
        self.asr_percent.setText("0%")
        self.asr_status.setText("准备开始转写...")
        self.start_button.setEnabled(False)
        self.asr_spinner.start()
        self.api.startListenAsr(self.audio_file, os.path.basename(self.audio_file))

    def _start_generation(self):
        if not self.transcript or self.model_selector.model_count == 0:
            self.goto_step(2)
            self.toast("请先完成转写并选择可用的 AI 模型", "error")
            return
        self.goto_step(3)
        self.result_panel.begin("正在等待 AI 响应...")
        self.api.startListeningGeneration(
            self.transcript,
            self.model_selector.selected_model_id,
            self.model_selector.selected_model_thinking,
        )

    def _stop(self):
        self.api.cancelGeneration()
        self.result_panel.set_generating(False)

    def _export(self):
        reply = json.loads(self.api.saveListeningDocx(
            self.result_panel.content, os.path.basename(self.audio_file)
        ))
        if reply.get("ok"):
            self.toast("Word 文档已保存", "success")
        elif not reply.get("cancelled"):
            self.toast(reply.get("error", "导出失败"), "error")

    # ── signal handlers ─────────────────────────────────────────
    def _on_asr_progress(self, pct, status):
        animate_property(self.asr_bar, b"value", int(pct), duration=260)
        self.asr_percent.setText(f"{int(pct)}%")
        self.asr_status.setText(status)

    def _on_asr_done(self, text):
        self.transcript = text
        self.asr_spinner.stop()
        self.asr_bar.setValue(100)
        self.asr_percent.setText("100%")
        self.asr_status.setObjectName("Success")
        self._restyle(self.asr_status)
        self.asr_status.setText("转写完成")
        self.start_button.setEnabled(True)

    def _on_asr_error(self, err):
        self.asr_spinner.stop()
        self.asr_status.setText("转写失败：" + err)
        self.toast(err, "error")

    def _on_error(self, err):
        self.result_panel.fail(err)
        self.toast(err, "error")

    @staticmethod
    def _restyle(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)
