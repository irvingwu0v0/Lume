<div align="center">

<img src="assets/icons/baka.png" width="72" alt="Lume">

# Lume

**Light Up My English**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=fff)](https://python.org)
[![PySide6](https://img.shields.io/badge/PySide6-6.5+-41CD52?logo=qt&logoColor=fff)](https://doc.qt.io/qtforpython)
[![UI](https://img.shields.io/badge/UI-Pure%20PySide6-539dda)]()
[![Icons](https://img.shields.io/badge/icons-Font%20Awesome%206%20(OFL)-528dd7)]()
[![docx](https://img.shields.io/badge/docx-1.0-2b579a?logo=microsoftword&logoColor=fff)](https://python-docx.readthedocs.io)
[![pptx](https://img.shields.io/badge/pptx-1.0-b7472a?logo=microsoftpowerpoint&logoColor=fff)](https://python-pptx.readthedocs.io)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-6c5ce7)]()
[![License](https://img.shields.io/badge/license-GPL--3.0-2ea44f?logo=gnu&logoColor=fff)](LICENSE)

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

界面完全基于 **PySide6（QtWidgets）** 手写，**不依赖任何第三方主题库或 QML 组件库**，因此可以干净地运行在 **Windows / macOS / Linux** 三大平台。所有 AI 调用都走 **OpenAI 兼容接口**，所以 ChatGPT、DeepSeek、通义千问、豆包、硅基流动、Ollama、vLLM……只要能填 `Base URL + API Key + 模型名` 就能用。

---

## ✨ 功能速览

| 你只需 | Lume 自动完成 | 你能拿到 |
|---|---|---|
| 📄 选择 PDF 试卷（含扫描件） | Umi-OCR 识别 / 视觉大模型直读 → AI 整理 | 📄 16 开 Word 或 📊 评讲 PPT |
| 📱 手机拍试卷 | 浏览器通过局域网 HTTP 上传 → 视觉大模型识别 | 📄 Word / 📊 PPT |
| 🎵 选择 MP3 / WAV / M4A / FLAC | Bcut ASR 转写 → AI 整理成听力材料 | 📄 16 开 Word |
| 📝 粘贴作文题目或原文 | AI 生成写作思路、情节结构、高分表达、范文 | 📄 16 开 Word |

每个流程都可以**独立选择 AI 模型**，并单独开关「思考模式（推理）」与「视觉模型」。

---

## 🧭 界面与工作流

Lume 的主界面是一个自绘的侧边导航窗口，包含五个页面：

| 页面 | 作用 |
|---|---|
| **首页** | 功能入口卡片，快速跳转到各工作流 |
| **试卷转换** | PDF / 手机拍照 → 识别 → 导出 Word / PPT |
| **听力材料生成** | 音频转写 → AI 整理成标准听力文本 |
| **作文思路生成** | 读后续写 / 应用文思路与范文生成 |
| **设置** | 管理 AI 模型、配置 Umi-OCR 服务 |

三个生成类工作流都采用相同的 **三步式交互**：`上传/输入 → 选择模型 → 结果导出`，并共用统一的 `StepIndicator` / `ModelSelector` / `StreamResultPanel` / `DropZone` 组件（见 `ui/widgets.py`）。

**视觉与动效**

- **图标字体**：界面不使用 emoji，所有图标都来自随程序打包的 Font Awesome 6 Free Solid 字体（`assets/fonts/`，SIL OFL 1.1），因此三平台观感完全一致、任意 DPI 下都清晰，并且颜色跟随主题变化。
- **应用图标**：主图是 `assets/icons/baka.png`（2000×2000、带透明通道）；`scripts/make_icons.py` 由它派生 Windows 的 `.ico` 与 macOS 的 `.icns`（见下文「应用图标」）。侧边栏左上角的品牌标直接绘制这张原图，不套底板、不加边框、不做裁切。
- **自绘控件**：按钮、开关、复选框、单选、分段选择器、步骤条、Toast 等都由 `QPainter` 绘制（`ui/controls.py`），而不是套第三方主题库，因此悬停 / 按下 / 选中状态都能做平滑过渡。
- **过渡动画**：页面切换淡入、侧边栏高亮滑动、卡片悬停浮起、Toast 滑入滑出、步骤条进度与对勾生长、开关滑块、分段控件滑块、流式等待指示器与平滑滚动，均使用 Qt 自带的 `QPropertyAnimation` / `QVariantAnimation` 实现（`ui/anim.py`），不引入额外依赖。
- **主题**：通过 Qt 自带的 `QStyleHints.colorScheme()` 自动跟随系统浅色 / 深色模式，并回退到调色板亮度判断；样式集中定义在 `ui/theme.py` 的单份 Qt Style Sheet 中，切换主题无需重启。

---

## 🚀 快速开始

### 环境要求

- **Python 3.10+**（推荐 3.10 ~ 3.13）
- Windows 10 / 11、macOS 12+ 或主流 Linux 发行版（均支持）
- 如需 OCR 模式：本地运行 [Umi-OCR](https://github.com/hiroi-sora/Umi-OCR) 并开启 HTTP 服务（默认端口 `1224`）

### 方式一：下载打包版（推荐）

从 [Releases](https://github.com/irvingwu0v0/Lume/releases) 下载对应平台的最新压缩包：

- Windows：解压后运行 `Lume.exe`
- macOS：解压后打开 `Lume.app`
- Linux：解压后运行 `Lume/Lume`

### 方式二：源码运行（使用项目内虚拟环境）

```bash
# 1. 克隆源代码
git clone https://github.com/irvingwu0v0/Lume.git
cd Lume

# 2. 在项目目录下创建虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (CMD)
.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate

# 4. 安装依赖（默认走中科大 PyPI 镜像，国内更快）
pip install -i https://pypi.mirrors.ustc.edu.cn/simple -r requirements.txt

# 5. 启动
python main.py
```

> 💡 也可以不激活虚拟环境，直接用 `.venv/bin/python main.py`（Windows 为 `.venv\Scripts\python.exe main.py`）。
>
> 想永久使用中科大源，可执行：
> `pip config set global.index-url https://pypi.mirrors.ustc.edu.cn/simple`

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

保存后可以点「测试」验证连通性并查看延迟。测试在后台线程执行，不会卡住界面。模型配置保存在本地 `data/models.json`。

### 2. 配置 Umi-OCR（仅 OCR 模式需要）

1. 启动 Umi-OCR，在「设置 → 全局设置 → HTTP 服务」中开启服务，记下端口（默认 `1224`）。
2. 在 Lume「设置 → Umi OCR API」中填写主机与端口，点「保存」，再点「测试」确认连接成功。

> 视觉模式（让多模态大模型直接看图片）**不需要** Umi-OCR。

---

## 📘 使用指南

### 📄 试卷转换

**上传方式**

- **上传 PDF**：选择本地 PDF 试卷（支持扫描件）。
- **手机浏览器上传**：在同一 Wi-Fi 下扫描桌面端二维码，或在手机浏览器打开完整上传地址（详见下方「手机端拍照上传」）。

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

1. 在桌面端进入「试卷转换 → 手机浏览器上传」，Lume 会启动局域网 HTTP 上传服务。
2. 用手机相机扫描界面中的二维码；也可以复制完整地址后在手机浏览器打开。
3. 在网页中拍照或从相册选图，可预览、排序、删除；点「完成上传」后桌面端会自动进入识别设置。

> 手机上传仅使用 HTTP 端口 `18924`，不需要安装手机 App，也没有 WebSocket 配对流程。每次启动上传服务都会生成新的随机会话令牌；只有拿到完整链接的局域网设备才能访问本次上传页面。若端口被占用，请关闭其他 Lume 实例后重试。
>
> 局域网 IP 与 Wi-Fi 名称的获取已针对三平台分别实现：Windows 使用 `ipconfig` / `netsh`，macOS 使用 `ipconfig getifaddr` / `networksetup`，Linux 使用 `hostname -I` / `iwgetid` / `nmcli`。

---

## 🗂 数据与隐私

Lume 的所有本地数据默认都在程序目录下的 `data/` 文件夹（Windows / Linux 打包版位于可执行文件同级目录，macOS 便携版位于 `Lume.app` 同级目录）：

```
data/
├── models.json    # AI 模型配置（含 API Key）
├── config.json    # OCR 主机 / 端口等设置
└── tmp/           # 手机上传的临时图片
```

- 若便携目录不可写（例如 macOS 的 `.app` 位于 `/Applications`），会自动改用系统应用数据目录（macOS 为 `~/Library/Application Support/Lume`，Linux 为 `~/.local/share/Lume`，Windows 为 `%LOCALAPPDATA%\Lume`）。
- API Key **以明文**保存在 `models.json` 中，请勿把 `data/` 目录分享给他人。
- 手机上传通过局域网明文 HTTP 传输，请只在可信网络中使用，不要将端口映射到公网。
- 手机上传的临时图片会在重新启动上传服务、切回 PDF 模式或退出程序时清理。

---

## 🧱 项目结构

```
Lume/
├── main.py                     # 程序入口：QApplication、主题、主窗口
├── build.py                    # PyInstaller 跨平台打包脚本（onedir）
├── scripts/
│   ├── make_icons.py           # 由主图 baka.png 生成 ICO / ICNS 应用图标
│   └── package_release.py      # 把构建产物打成 Lume_<平台>_<日期>.zip
├── .github/workflows/
│   └── build.yml               # GitHub Actions：三平台自动打包 / 发版
├── requirements.txt
├── README.md
├── assets/
│   ├── fonts/                  # 内置图标字体（Font Awesome 6 Free Solid + OFL 许可）
│   └── icons/                  # 应用图标：baka.png（主图）+ 派生的 baka.ico / baka.icns
├── ui/                         # 纯 PySide6 界面层（QtWidgets，无 QML / 第三方组件库）
│   ├── theme.py                # 浅色 / 深色配色令牌 + 全部 Qt Style Sheet
│   ├── icons.py                # 图标字体加载与字形渲染（按名称取图标）
│   ├── anim.py                 # 动画基元：淡入、滑动、投影、旋转指示器、脉冲点
│   ├── controls.py             # 自绘动画控件：按钮 / 开关 / 复选 / 单选 / 分段控件 / 徽标
│   ├── widgets.py              # 组合组件：卡片、步骤指示器、模型选择器、流式面板、Toast、上传区
│   ├── resources.py            # 源码 / 打包两种模式下的资源定位
│   ├── appicon.py              # 按平台挑选应用图标（ico / png / icns）
│   ├── page.py                 # 页面基类（标题 + 居中限宽的滚动画布）
│   ├── main_window.py          # 侧边导航 + 动画指示条 + 页面淡入 + 全局 Toast
│   └── pages/
│       ├── home.py             # 首页功能卡片
│       ├── pdf_convert.py      # 试卷转换（PDF / 手机拍照）
│       ├── listening.py        # 听力材料生成
│       ├── writing.py          # 作文思路生成
│       └── settings.py         # AI 模型管理 + Umi-OCR 配置
├── backend/
│   ├── chat.py                 # OpenAI 兼容请求构造、SSE 流式解析、AI JSON 提取
│   ├── api_bridge.py           # 界面 ↔ Python 桥接（@Slot / Signal）+ 各类后台 Worker
│   ├── phone_server.py         # 带随机令牌的局域网 HTTP 上传服务
│   ├── export.py               # Word（16 开）/ PPT 导出
│   ├── prompts.py              # 所有提示词模板（PDF 两套提示词共享同一 JSON Schema）
│   └── data.py                 # 本地配置读写、可写目录探测与默认值
└── templates/
    └── ppt_template.pptx       # PPT 评讲课件模板
```

**架构说明**

- 界面层（QtWidgets）只负责展示与交互；所有耗时任务（AI 流式请求、ASR、OCR、PDF 转图片、模型 / OCR 连通性测试）都跑在 `QThread` 后台线程里，通过 Qt Signal 把进度和结果回传给界面，界面不会卡死。
- `backend/chat.py` 统一封装了请求构造与 SSE 增量解析，`api_bridge.py` 与 `SplitPdfWorker` 共用同一套逻辑。
- 三个生成流程共用 `StepIndicator` / `ModelSelector` / `StreamResultPanel` 组件，避免重复实现。
- 主题和界面组件不依赖第三方 UI 库：颜色来自 Qt 系统配色，图标来自随包分发的字体文件；二维码由轻量的 `qrcode` 在本地生成。

---

## 🛠 自己打包

```bash
# 确保已激活 .venv
pip install -i https://pypi.mirrors.ustc.edu.cn/simple pyinstaller

# 清理 + 构建
python build.py

# 仅清理构建产物
python build.py clean

# 打成便携压缩包（自动带上平台与日期）
python scripts/package_release.py
# → release/Lume_Linux_20261002.zip
```

打包产物（`--onedir`）：

| 平台 | 产物 | 启动方式 |
|---|---|---|
| Windows | `dist/Lume/Lume.exe` | 双击运行 |
| macOS | `dist/Lume.app` | `open dist/Lume.app` |
| Linux | `dist/Lume/Lume` | `./dist/Lume/Lume` |

打包脚本会自动收集 `assets/`（图标字体与应用图标）与 `templates/`（PPT 模板），Python 包由 PyInstaller 自行分析，并显式注入 `pymupdf` 隐藏依赖（`winreg` 仅在 Windows 上注入）。

构建前会自动检查 `.ico` / `.icns` 是否缺失或比主图 `assets/icons/baka.png` 更旧，必要时调用 `scripts/make_icons.py` 重新生成。`--icon` 参数按平台自动选择：Windows 用 `.ico`，macOS 应用包用 `.icns`，Linux 不需要（窗口图标由运行时加载的 `baka.png` 提供）。

> ⚠️ 请在目标平台上分别打包：PyInstaller 不支持跨平台交叉编译。

### 应用图标

主图只有一份：`assets/icons/baka.png`。Windows 的 `.ico` 与 macOS 应用包的 `.icns` 都由它派生（已随仓库提交，改动主图后重新运行即可）：

```bash
python scripts/make_icons.py
# → assets/icons/baka.ico   多尺寸 Windows 图标（16/24/32/48/64/128/256）
# → assets/icons/baka.icns  macOS 应用包图标（32/64/128/256/512）
```

脚本不依赖任何第三方图像库：`ico` / `icns` 都是套在 PNG 外面的简单容器，由标准库 `struct` 直接写出，主图的透明通道会完整保留。运行时由 `ui/appicon.py` 选择格式：Windows 用 `baka.ico`，Linux / macOS 直接渲染 `baka.png`，文件缺失时自动回退。窗口标题固定为 `Lume`，窗口与任务栏图标就是这张主图（不带底板、不裁切）。

### 便携包命名

`scripts/package_release.py` 会把构建产物打包成 `Lume_<平台>_<日期>.zip`，压缩包内保留顶层目录（`Lume/` 或 `Lume.app`），解压即用：

| 平台 | 产物 | 启动方式 |
|---|---|---|
| Windows | `Lume_Windows_20261002.zip` | 解压后双击 `Lume\Lume.exe` |
| Linux | `Lume_Linux_20261002.zip` | 解压后 `./Lume/Lume` |
| macOS | `Lume_macOS_20261002.zip` | 解压后 `open Lume.app` |

---

## 🤖 自动打包与发布

仓库内置 GitHub Actions 工作流 [`.github/workflows/build.yml`](.github/workflows/build.yml)：

- **触发方式**：推送 `v*` 标签（如 `git tag v1.0.0 && git push origin v1.0.0`），或在 Actions 页面手动 `Run workflow`。
- **构建矩阵**：`windows-latest`、`ubuntu-22.04`（降低 glibc 依赖）、`macos-latest`，由 GitHub Runner 在各目标系统原生构建。
- **产物**：每个平台生成一个便携 zip，既作为 Actions artifact 保留 14 天，也会在打标签时自动附加到对应的 GitHub Release。
- CI 中使用官方 PyPI（GitHub Runner 在境外，官方源更稳定）；本地开发仍推荐中科大镜像。

```bash
git tag v1.0.0
git push origin v1.0.0     # 触发三平台构建并创建 Release
```

> macOS 产物未做代码签名，首次打开如被 Gatekeeper 拦截，可执行
> `xattr -dr com.apple.quarantine Lume.app` 后再打开。

---

## ❓ 常见问题

**Q：支持哪些 AI 服务？**
任何 OpenAI 兼容的 `/chat/completions` 接口都可以。视觉模型需要在设置里勾选「视觉模型」。

**Q：视觉模式和 OCR 模式怎么选？**
文字清晰的电子版 PDF 用 OCR 模式更快更省 token；扫描件、照片、手写标注建议用视觉模式。

**Q：生成时提示 JSON 解析失败？**
模型偶尔会输出不完整或不规范的 JSON，Lume 已内置容错解析（代码围栏、括号配平、自动补全）。如果仍失败，换一个更强的模型或关闭思考模式重试。

**Q：手机连不上桌面端？**
确认两者在同一 Wi-Fi、桌面防火墙放行 TCP `18924` 端口，并关闭其他占用该端口的 Lume 实例。若二维码指向 `127.0.0.1`，说明系统没有检测到可用的局域网地址，请先连接局域网再重新进入手机上传页。

**Q：Linux / macOS 上界面很丑或字体不对？**
Lume 统一使用 `Fusion` 基础样式 + 自带样式表，正常情况下三平台外观一致。Linux 若缺少中文字体，可安装 `fonts-noto-cjk`（Debian/Ubuntu）或 `noto-fonts-cjk`（Arch）。

---

## 🙏 致谢

- **[Umi-OCR](https://github.com/hiroi-sora/Umi-OCR)** — 离线 OCR 引擎，用于 PDF 扫描件文字识别
- **Bcut ASR** — 必剪语音转写接口（来源 [VideoCaptioner](https://github.com/WEIFENG2333/VideoCaptioner)）
- **[Qt for Python (PySide6)](https://doc.qt.io/qtforpython)** — 跨平台界面框架
- **[Font Awesome 6 Free](https://fontawesome.com)** — 界面图标字体（SIL OFL 1.1，许可证见 `assets/fonts/LICENSE-FontAwesome.txt`）
- **baka.png** — Lume 应用图标原图（`assets/icons/`），`.ico` / `.icns` 由 `scripts/make_icons.py` 派生

---

## 📜 许可证

本项目以 **GNU General Public License v3.0** 发布，完整条款见 [LICENSE](LICENSE)。

你可以自由使用、修改与再分发本项目；任何基于本项目的衍生作品也必须同样以 GPL-3.0 开源，并保留版权与许可声明。本项目按「原样」提供，不含任何形式的担保。

内置 Font Awesome 字体仍按 `assets/fonts/LICENSE-FontAwesome.txt` 中的 SIL OFL 1.1 授权。

<div align="center">
<sub>专治英语备课各种麻烦事 · Made with ❤️</sub>
</div>
