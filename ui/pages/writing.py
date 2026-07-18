"""Writing-ideas workflow: input -> model -> streaming result."""

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)

from ..controls import IconButton, SegmentedControl
from ..page import Page
from ..widgets import (
    ModelSelector, StepIndicator, StreamResultPanel, make_card, top_aligned,
)


class WritingPage(Page):
    def __init__(self, api, parent=None):
        super().__init__(
            api, title="作文思路生成",
            subtitle="粘贴原文或题目，AI 输出写作思路、结构框架与高分表达。",
            parent=parent,
        )
        self.write_mode = "continuation"

        self.indicator = StepIndicator()
        self.indicator.set_steps(["输入题目", "选择模型", "结果导出"])
        self.add(self.indicator)

        self.stack = QStackedWidget()
        self.add(self.stack)
        self.stack.addWidget(top_aligned(self._build_step1()))
        self.stack.addWidget(top_aligned(self._build_step2()))
        self.stack.addWidget(self._build_step3())

        self.api.writingChunk.connect(self.result_panel.append_chunk)
        self.api.writingDone.connect(self.result_panel.finish)
        self.api.writingError.connect(self._on_error)

        self.goto_step(1)
        self.add_stretch()

    # ── steps ───────────────────────────────────────────────────
    def _build_step1(self):
        card, layout = make_card()
        layout.addWidget(self._bold("输入作文题目"))

        self.mode_control = SegmentedControl([
            ("pen-nib", "读后续写"),
            ("file-lines", "应用文"),
        ])
        self.mode_control.changed.connect(self._on_mode_changed)
        layout.addWidget(self.mode_control)

        hint = QLabel("读后续写模式 — 分析原文并生成续写思路")
        hint.setObjectName("Muted")
        layout.addWidget(hint)
        self._mode_hint = hint

        self.input_edit = QTextEdit()
        self.input_edit.setPlaceholderText("在此粘贴阅读理解原文及续写提示句...")
        self.input_edit.setMinimumHeight(220)
        self.input_edit.textChanged.connect(self._on_input_changed)
        layout.addWidget(self.input_edit)

        footer = QHBoxLayout()
        self.counter = QLabel("0 字")
        self.counter.setObjectName("Hint")
        footer.addWidget(self.counter)
        footer.addStretch(1)
        self.next_button = IconButton("下一步：选择模型", "arrow-right", "primary",
                                      height=40, icon_size=14)
        self.next_button.setEnabled(False)
        self.next_button.clicked.connect(self._go_step2)
        footer.addWidget(self.next_button)
        layout.addLayout(footer)
        return card

    def _build_step2(self):
        card, layout = make_card()
        layout.addWidget(self._bold("选择 AI 模型"))
        subtitle = QLabel("选择用于生成写作思路的 AI 模型")
        subtitle.setObjectName("Muted")
        layout.addWidget(subtitle)

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
        self.start_button = IconButton("确认，开始生成", "wand-sparkles", "primary",
                                       height=40, icon_size=15)
        self.start_button.clicked.connect(self._start_generation)
        buttons.addWidget(self.start_button)
        layout.addLayout(buttons)
        return card

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

    def _on_input_changed(self):
        text = self.input_edit.toPlainText()
        self.next_button.setEnabled(bool(text.strip()))
        self.counter.setText(f"{len(text)} 字")

    def _on_mode_changed(self, index):
        self.write_mode = "continuation" if index == 0 else "practical"
        if self.write_mode == "continuation":
            self._mode_hint.setText("读后续写模式 — 分析原文并生成续写思路")
            self.input_edit.setPlaceholderText("在此粘贴阅读理解原文及续写提示句...")
        else:
            self._mode_hint.setText("应用文模式 — 分析题目并生成写作框架")
            self.input_edit.setPlaceholderText("在此粘贴应用文写作题目...")

    def _go_step2(self):
        self.goto_step(2)

    def _start_generation(self):
        if self.model_selector.model_count == 0:
            self.goto_step(2)
            self.toast("请先在「设置」中添加可用的 AI 模型", "error")
            return
        self.goto_step(3)
        self.result_panel.begin("正在等待 AI 响应...")
        self.api.startWritingGeneration(
            self.input_edit.toPlainText(),
            self.model_selector.selected_model_id,
            self.model_selector.selected_model_thinking,
            self.write_mode,
        )

    def _stop(self):
        self.api.cancelGeneration()
        self.result_panel.set_generating(False)

    def _export(self):
        import json
        reply = json.loads(self.api.saveWritingDocx(self.result_panel.content, self.write_mode))
        if reply.get("ok"):
            self.toast("Word 文档已保存", "success")
        elif not reply.get("cancelled"):
            self.toast(reply.get("error", "导出失败"), "error")

    def _on_error(self, err):
        self.result_panel.fail(err)
        self.toast(err, "error")
