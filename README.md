<div align="center">

<img src="baka.ico" width="72" alt="Lume">

# Lume

**Light Up My English**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=fff)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-6.5+-41CD52?logo=qt&logoColor=fff)](https://doc.qt.io/qtforpython)
[![RinUI](https://img.shields.io/badge/UI-RinUI%20%2F%20Fluent-539dda)](https://github.com/RinUI)
[![docx](https://img.shields.io/badge/docx-1.0-2b579a?logo=microsoftword&logoColor=fff)](https://python-docx.readthedocs.io)
[![pptx](https://img.shields.io/badge/pptx-1.0-b7472a?logo=microsoftpowerpoint&logoColor=fff)](https://python-pptx.readthedocs.io)
[![Platform](https://img.shields.io/badge/platform-Windows-6c5ce7)]()

> **AI 一键生成英语教学材料 · 写作思路 · 听力文本 · 试卷导出 Word / PPT**

</div>

---

## 📖 这是什么

备英语课的时候，你是不是也经历过——

- 想出篇读后续写范文，AI 给了内容，但**排版调格式导出 Word** 又要花掉半小时
- 网上下载了听力 MP3，要手动切段落、逐题敲选项、调字体字号
- 扫描了一份纸质试卷，OCR 完还得**手工核对每道题的正文和选项**

**Lume 就是来解决这些麻烦事的。**

上传文件或拍张照，选一个 AI 模型，它会把材料整理成**贴近高考排版**的 Word 或评讲用 PPT，拿到就能直接打印。

它是基于 **PySide6 + RinUI（Fluent Design）** 的桌面应用，所有 AI 调用都走 **OpenAI 兼容接口**，所以 ChatGPT、DeepSeek、通义千问、豆包、硅基流动、Ollama、vLLM……只要能填 `Base URL + API Key + 模型名` 就能用。

---

## ✨ 功能速览

| 你只需 | Lume 自动完成 | 你能拿到 |
|---|---|---|
| 📄 选择 PDF 试卷（含扫描件） | Umi-OCR 识别 / 视觉大模型直读 → AI 整理 | 📄 16 开 Word 或 📊 评讲 PPT |
| 📱 手机拍试卷 | 局域网直连桌面端 → 视觉大模型识别 | 📄 Word / 📊 PPT |
| 🎵 选择 MP3 / WAV / M4A / FLAC | Bcut ASR 转写 → AI 整理成听力材料 | 📄 16 开 Word |
| 📝 粘贴作文题目或原文 | AI 生成写作思路、情节结构、高分表达、范文 | 📄 16 开 Word |

每个流程都可以**独立选择 AI 模型**，并单独开关「思考模式（推理）」与「视觉模型」。

---

## 🧭 界面与工作流

Lume 的主界面是一个 Fluent 风格的侧边导航窗口，包含五个页面：

| 页面 | 作用 |
|---|---|
| **首页** | 功能入口卡片，快速跳转到各工作流 |
| **试卷转换** | PDF / 手机拍照 → 识别 → 导出 Word / PPT |
| **听力材料生成** | 音频转写 → AI 整理成标准听力文本 |
| **作文思路生成** | 读后续写 / 应用文思路与范文生成 |
| **设置** | 管理 AI 模型、配置 Umi-OCR 服务 |

三个生成类工作流都采用相同的 **三步式交互**：`上传/输入 → 选择模型 → 结果导出`，并带有统一的步骤指示器、模型选择器和流式输出面板。

---

## 🚀 快速开始

> 便携版解压即用，无需在本机安装 Python。

### 环境要求

- **Python 3.10+**（推荐 3.10 ~ 3.12）
- Windows 10 / 11（打包版与手机连接功能以 Windows 为主）
- 如需 OCR 模式：本地运行 [Umi-OCR](https://github.com/hiroi-sora/Umi-OCR) 并开启 HTTP 服务（默认端口 `1224`）

### 方式一：下载打包版（推荐）

从 [Releases](https://github.com/irvingwu0v0/Lume/releases) 下载最新压缩包，解压后运行 `Lume.exe` 即可。

### 方式二：源码运行

```bash
# 克隆源代码
git clone https://github.com/irvingwu0v0/Lume.git && cd Lume

# 安装依赖
pip install -r requirements.txt

# 启动
python main.py
```

> 💡 **第一次使用？** 打开「设置」→「添加模型」，填入你的 AI 接口信息 → 回到首页随便试一个功能。

---

## ⚙️ 首次配置

### 1. 添加 AI 模型

进入「设置 → AI 模型列表 → 添加模型」，填写：

| 字段 | 说明 | 示例 |
|---|---|---|
| 模型代称 | 显示用的别名 | `DeepSeek V4 Pro` |
| Base URL | OpenAI 兼容接口根地址 | `https://api.deepseek.com` |
| 模型名称 | 接口使用的 model 名 | `deepseek-v4-pro` |
| API Key | 你的密钥 | `sk-...` |
| 思考模式 | 是否发送 `thinking: enabled`（推理模型） | 按模型选择 |
| 视觉模型 | 是否可用于图片识别（试卷拍照 / 视觉模式） | 按模型选择 |

保存后可以点「测试」验证连通性并查看延迟。模型配置保存在本地 `data/models.json`。

### 2. 配置 Umi-OCR（仅 OCR 模式需要）

1. 启动 Umi-OCR，在「设置 → 全局设置 → HTTP 服务」中开启服务，记下端口（默认 `1224`）。
2. 在 Lume「设置 → Umi OCR API」中填写主机与端口，点「保存」，再点「测试」确认连接成功。

> 视觉模式（让多模态大模型直接看图片）**不需要** Umi-OCR。

---

## 📘 使用指南

> 提示：所有工作流都在左侧导航中，首次使用请先到「设置」添加模型。

### 📄 试卷转换

**上传方式**

- **上传 PDF**：选择本地 PDF 试卷（支持扫描件）。
- **连接手机 Lume**：在同一 Wi-Fi 下，用手机浏览器打开桌面端显示的 IP（详见下方「手机端拍照上传」）。

**识别模式（步骤 2）**

| 模式 | 适用 | 说明 |
|---|---|---|
| **OCR 模式** | 清晰的文字型 PDF | 先用 Umi-OCR 提取文字，再由 AI 整理；可勾选「分两次进行」以缓解长上下文压力 |
| **视觉模型模式** | 扫描件、图片、手机拍照 | 多模态模型直读图片；超过 9 张可勾选「分批发送」 |

**导出**

- **Word**：16 开页面、页眉页脚页码、贴近高考排版的听力 / 阅读 / 七选五 / 完形 / 语法 / 写作结构。
- **PPT**：基于 `templates/ppt_template.pptx` 生成的评讲课件。

### 🎵 听力材料生成

1. 上传 `MP3 / WAV / M4A / FLAC` 音频，点击「开始转写」（使用 Bcut ASR 在线转写）。
2. 转写完成后，选择一个 AI 模型进行「AI 整理」——自动识别说话人、规范数字与时间格式、划分第一 / 第二节。
3. 导出标准听力材料 Word。

> ⚠️ 转写需要联网调用 Bcut 接口；音频会上传到第三方服务，请注意隐私。

### 📝 作文思路生成

1. 粘贴阅读原文（读后续写）或作文题目（应用文）。
2. 选择「读后续写 / 应用文」模式。
3. AI 按五个维度输出：题目解析、命题意图、写作思路 / 框架、高分表达、范文参考。
4. 导出 Word。

---

## 📱 手机端拍照上传

手机与电脑连到**同一个局域网**后：

1. 在桌面端「试卷转换 → 连接手机 Lume」，界面会显示形如 `192.168.x.x` 的 IP 地址。
2. 手机浏览器访问 `http://<该 IP>:18924/`，打开内置的拍照上传页面。
3. 拍完照可在手机上预览、排序、删除，点「下一步」后桌面端会自动进入选择模型步骤。

> 桌面端也支持手机 App 通过 WebSocket（端口 `18923`）连接；HTTP 页面（`18924`）是为方便任意手机浏览器使用的兜底方案。若端口被占用，请关闭其他 Lume 实例后重试。

---

## 🗂 数据与隐私

Lume 的所有本地数据都在程序目录下的 `data/` 文件夹（打包版位于 `Lume.exe` 同级目录）：

```
data/
├── models.json    # AI 模型配置（含 API Key）
├── config.json    # OCR 主机 / 端口等设置
└── tmp/           # 手机上传的临时图片
```

- API Key **以明文**保存在 `models.json` 中，请勿把 `data/` 目录分享给他人。
- 手机上传的临时图片会在断开连接 / 退出时清理。

---

## 🧱 项目结构

```
Lume/
├── main.py                  # 程序入口：初始化 QApplication 与 RinUI 窗口
├── build.py                 # PyInstaller 打包脚本（onedir）
├── requirements.txt
├── baka.ico
├── README.md
├── ui/                      # QML 界面
│   ├── main.qml             # FluentWindow + 侧边导航
│   ├── components/          # 可复用组件
│   │   ├── StepIndicator.qml    # 三步进度指示器
│   │   ├── ModelSelector.qml    # 模型下拉选择（读取后端模型列表）
│   │   ├── StreamResult.qml     # 流式输出 / 思考过程 / 自动滚动面板
│   │   └── FeatureCard.qml      # 首页功能卡片
│   └── pages/
│       ├── HomePage.qml
│       ├── PdfConvertPage.qml
│       ├── ListeningPage.qml
│       ├── WritingPage.qml
│       └── SettingsPage.qml
├── backend/
│   ├── chat.py              # OpenAI 兼容请求构造、SSE 流式解析、AI JSON 提取
│   ├── api_bridge.py        # QML ↔ Python 桥接（@Slot / Signal）+ 各类后台 Worker
│   ├── phone_server.py      # 手机端 WebSocket + HTTP 服务
│   ├── export.py            # Word（16 开）/ PPT 导出
│   ├── prompts.py           # 所有提示词模板（PDF 两套提示词共享同一 JSON Schema）
│   └── data.py              # 本地配置读写与默认值
└── templates/
    └── ppt_template.pptx    # PPT 评讲课件模板
```

**架构说明**

- 界面层（QML）只负责展示与交互；所有耗时任务（AI 流式请求、ASR、OCR、PDF 转图片）都跑在 `QThread` 后台线程里，通过 Qt Signal 把进度和结果回传给界面，界面不会卡死。
- `backend/chat.py` 统一封装了请求构造与 SSE 增量解析，`api_bridge.py` 与 `SplitPdfWorker` 共用同一套逻辑。
- 三个生成流程共用 `StepIndicator` / `ModelSelector` / `StreamResult` 组件，避免重复实现。

---

## 🛠 自己打包

```bash
# 安装打包工具
pip install pyinstaller

# 清理 + 构建（产物在 dist/Lume/）
python build.py

# 仅清理构建产物
python build.py clean
```

打包脚本会自动收集 `ui/`、`backend/`、`templates/` 与图标，并注入 `darkdetect`、`fitz`、`PySide6.QtWebSockets`、`PySide6.QtNetwork` 等隐藏依赖。

---

## ❓ 常见问题

**Q：支持哪些 AI 服务？**
任何 OpenAI 兼容的 `/chat/completions` 接口都可以。视觉模型需要在设置里勾选「视觉模型」。

**Q：视觉模式和 OCR 模式怎么选？**
文字清晰的电子版 PDF 用 OCR 模式更快更省 token；扫描件、照片、手写标注建议用视觉模式。

**Q：生成时提示 JSON 解析失败？**
模型偶尔会输出不完整或不规范的 JSON，Lume 已内置容错解析（代码围栏、括号配平、自动补全）。如果仍失败，换一个更强的模型或关闭思考模式重试。

**Q：手机连不上桌面端？**
确认两者在同一 Wi-Fi、桌面防火墙放行 `18923` / `18924` 端口，并关闭其他占用端口的 Lume 实例。

---

## 🙏 致谢

- **[Umi-OCR](https://github.com/hiroi-sora/Umi-OCR)** — 离线 OCR 引擎，用于 PDF 扫描件文字识别
- **Bcut ASR** — 必剪语音转写接口（来源 [VideoCaptioner](https://github.com/WEIFENG2333/VideoCaptioner)）
- **[RinUI](https://github.com/RinUI)** — Fluent Design 风格的 QML 组件库

---

## 📜 许可证

GPL-3.0（沿用项目原有许可证声明）。

<div align="center">
<sub>专治英语备课各种麻烦事 · Made with ❤️</sub>
</div>
