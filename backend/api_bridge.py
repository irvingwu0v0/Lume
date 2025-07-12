import base64
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error

import fitz
import requests
from PySide6.QtCore import QObject, Signal, Slot, QThread

from .data import load_models, save_models, load_config, save_config
from .phone_server import PhoneServer


def extract_json(text):
    """Robustly extract a JSON dict from AI-generated text.
    Module-level so both SseWorker/SplitPdfWorker and ApiBridge can use it."""
    import re as _re
    if not text or not text.strip():
        return None, "empty content"
    t = text.strip()

    # 1) Direct parse
    try:
        result = json.loads(t)
        if isinstance(result, dict):
            return result, None
    except Exception:
        pass

    # 2) Search for JSON fences — prefer the LAST complete code block
    fences = ["```json\n", "```json", "```JSON\n", "```JSON", "```"]
    best = None
    for fence in fences:
        pos = 0
        while True:
            fence_start = t.find(fence, pos)
            if fence_start == -1:
                break
            inner_start = fence_start + len(fence)
            inner = t[inner_start:]
            fence_end = inner.find("```")
            if fence_end == -1:
                fence_end = len(inner)
            inner = inner[:fence_end].strip()
            if inner:
                try:
                    result = json.loads(inner)
                    if isinstance(result, dict):
                        best = result
                except Exception:
                    pass
            pos = inner_start + fence_end + 3

    if best is not None:
        return best, None

    # 3) String-aware balanced brace extraction
    start_pos = t.find("{")
    if start_pos == -1:
        return None, "no JSON object found"

    stack = []
    in_string = False
    escape_next = False
    i = start_pos
    while i < len(t):
        ch = t[i]
        if escape_next:
            escape_next = False
            i += 1
            continue
        if ch == '\\' and in_string:
            escape_next = True
            i += 1
            continue
        if ch == '"' and not escape_next:
            in_string = not in_string
            i += 1
            continue
        if in_string:
            i += 1
            continue
        if ch == '{':
            stack.append('{')
        elif ch == '}':
            if stack and stack[-1] == '{':
                stack.pop()
                if not stack:
                    candidate = t[start_pos:i+1]
                    try:
                        return json.loads(candidate), None
                    except Exception:
                        pass
        elif ch == '[':
            stack.append('[')
        elif ch == ']':
            if stack and stack[-1] == '[':
                stack.pop()
        i += 1

    # 4) Auto-close truncated JSON
    if stack and len(stack) <= 50:
        suffix = ""
        if in_string:
            suffix += '"'
        for opener in reversed(stack):
            suffix += '}' if opener == '{' else ']'
        candidate = t[start_pos:] + suffix
        try:
            return json.loads(candidate), None
        except Exception:
            pass

    return None, "could not extract valid JSON"


class SseWorker(QThread):
    chunk_received = Signal(str)
    finished_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, url, payload, headers, parent=None):
        super().__init__(parent)
        self.url = url
        self.payload = payload
        self.headers = headers
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            resp = requests.post(
                self.url, json=self.payload, headers=self.headers,
                stream=True, timeout=600,
            )
            resp.raise_for_status()
        except Exception as e:
            self.error_signal.emit(str(e))
            return

        full_content = ""
        buf = ""
        pending_reasoning = ""
        pending_content = ""
        last_flush = time.monotonic()
        FLUSH_INTERVAL = 0.05

        def flush():
            nonlocal pending_reasoning, pending_content, last_flush
            if pending_reasoning:
                self.chunk_received.emit(json.dumps({"reasoning": pending_reasoning}))
                pending_reasoning = ""
            if pending_content:
                self.chunk_received.emit(json.dumps({"content": pending_content}))
                pending_content = ""
            last_flush = time.monotonic()

        for chunk in resp.iter_content(chunk_size=None):
            if self._abort:
                return
            if not chunk:
                continue
            buf += chunk.decode("utf-8", errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    flush()
                    self.finished_signal.emit(full_content)
                    return
                try:
                    obj = json.loads(data_str)
                    choices = obj.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        reasoning = delta.get("reasoning_content", "")
                        content = delta.get("content", "")
                        if reasoning:
                            pending_reasoning += reasoning
                        if content:
                            full_content += content
                            pending_content += content
                        if time.monotonic() - last_flush >= FLUSH_INTERVAL:
                            flush()
                except json.JSONDecodeError:
                    pass
        flush()
        self.finished_signal.emit(full_content)


class AsrWorker(QThread):
    progress = Signal(int, str)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath

    def run(self):
        try:
            text = self._run_asr()
            self.done.emit(text)
        except Exception as e:
            self.error.emit(str(e))

    def _run_asr(self):
        BCUT_API = "https://member.bilibili.com/x/bcut/rubick-interface"
        BCUT_HEADERS = {
            "User-Agent": "Bilibili/1.0.0 (https://www.bilibili.com)",
            "Content-Type": "application/json",
        }

        with open(self.filepath, "rb") as f:
            file_data = f.read()
        file_size = len(file_data)

        self.progress.emit(20, "正在上传音频...")

        resp = requests.post(
            BCUT_API + "/resource/create",
            data=json.dumps({
                "type": 2, "name": "audio.mp3", "size": file_size,
                "ResourceFileType": "mp3", "model_id": "8",
            }),
            headers=BCUT_HEADERS, timeout=30,
        )
        resp.raise_for_status()
        res = resp.json()["data"]
        in_boss_key = res["in_boss_key"]
        resource_id = res["resource_id"]
        upload_id = res["upload_id"]
        upload_urls = res["upload_urls"]
        per_size = res["per_size"]

        etags = []
        for clip in range(len(upload_urls)):
            start = clip * per_size
            end = (clip + 1) * per_size
            r = requests.put(
                upload_urls[clip], data=file_data[start:end],
                headers={"Content-Type": "application/octet-stream"}, timeout=120,
            )
            r.raise_for_status()
            etags.append(r.headers.get("Etag", ""))

        self.progress.emit(40, "正在提交上传...")

        resp = requests.post(
            BCUT_API + "/resource/create/complete",
            data=json.dumps({
                "InBossKey": in_boss_key, "ResourceId": resource_id,
                "Etags": ",".join(etags), "UploadId": upload_id, "model_id": "8",
            }),
            headers=BCUT_HEADERS, timeout=30,
        )
        resp.raise_for_status()
        download_url = resp.json()["data"]["download_url"]

        self.progress.emit(50, "正在创建转录任务...")

        resp = requests.post(
            BCUT_API + "/task",
            json={"resource": download_url, "model_id": "8"},
            headers=BCUT_HEADERS, timeout=30,
        )
        resp.raise_for_status()
        task_id = resp.json()["data"]["task_id"]

        self.progress.emit(60, "正在转写，请稍候...")

        for _ in range(500):
            resp = requests.get(
                BCUT_API + "/task/result",
                params={"model_id": 8, "task_id": task_id},
                headers=BCUT_HEADERS, timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            state = data.get("state", 0)
            if state == 4:
                utterances = json.loads(data["result"])["utterances"]
                lines = []
                for u in utterances:
                    t = u.get("transcript", "").strip()
                    if t:
                        lines.append(t)
                self.progress.emit(100, "转写完成")
                return "\n".join(lines)
            if state < 0:
                raise RuntimeError(f"ASR task failed, state={state}")
            time.sleep(1)
        raise TimeoutError("ASR task timed out")


class OcrWorker(QThread):
    progress = Signal(int, str)
    done = Signal(list)
    error = Signal(str)

    def __init__(self, filepath, host, port, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self.host = host
        self.port = port

    def run(self):
        try:
            pages = self._run_ocr()
            self.done.emit(pages)
        except Exception as e:
            self.error.emit(str(e))

    def _run_ocr(self):
        base = f"http://{self.host}:{self.port}"
        options = json.dumps({"doc.extractionMode": "mixed", "tbpu.parser": "none"})

        self.progress.emit(5, "正在上传 PDF...")

        with open(self.filepath, "rb") as f:
            file_data = f.read()

        resp = requests.post(
            f"{base}/api/doc/upload",
            files={"file": (os.path.basename(self.filepath), file_data)},
            data={"json": options}, timeout=60,
        )
        resp_data = resp.json()

        if resp_data.get("code") == 101:
            resp = requests.post(
                f"{base}/api/doc/upload",
                files={"file": ("temp.pdf", file_data)},
                data={"json": options}, timeout=60,
            )
            resp_data = resp.json()

        if resp_data.get("code") != 100:
            raise RuntimeError(f"OCR upload failed: {resp_data}")

        task_id = resp_data["data"]
        self.progress.emit(10, "正在识别文字...")

        ocr_results = []
        total_pages = 1

        while True:
            resp = requests.post(
                f"{base}/api/doc/result",
                json={"id": task_id, "is_data": True, "format": "text", "is_unread": True},
                timeout=30,
            )
            res_data = resp.json()
            if res_data.get("code") != 100:
                raise RuntimeError(f"OCR poll failed: {res_data}")

            total_pages = max(res_data.get("pages_count", 1), 1)
            processed = res_data.get("processed_count", 0)
            page_text = res_data.get("data", "")

            if page_text:
                ocr_results.append(page_text)

            pct = min(10 + int(85 * processed / total_pages), 95)
            self.progress.emit(pct, f"正在识别第 {processed}/{total_pages} 页...")

            if res_data.get("is_done"):
                if res_data.get("state") != "success":
                    raise RuntimeError(f"OCR failed: {res_data.get('message', 'unknown')}")
                break
            time.sleep(1)

        while len(ocr_results) < total_pages:
            ocr_results.append("")

        try:
            requests.get(f"{base}/api/doc/clear/{task_id}", timeout=5)
        except Exception:
            pass

        self.progress.emit(100, "识别完成")
        return ocr_results


class PdfToImagesWorker(QThread):
    done = Signal(list)
    error = Signal(str)

    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath

    def run(self):
        try:
            with open(self.filepath, "rb") as f:
                pdf_bytes = f.read()
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            images = []
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                img_bytes = pix.tobytes("jpeg")
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                images.append(b64)
            doc.close()
            self.done.emit(images)
        except Exception as e:
            self.error.emit(str(e))


class SplitPdfWorker(QThread):
    """Two-pass AI generation worker for split_mode (OCR) and batch_mode (Vision)."""
    chunk_received = Signal(str)
    finished_signal = Signal(str)
    error_signal = Signal(str)

    def __init__(self, base_url, model, data, thinking_enabled, is_vision=False, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.model = model
        self.data = data
        self.thinking_enabled = thinking_enabled
        self.is_vision = is_vision
        self._abort = False

    def abort(self):
        self._abort = True

    def _stream_call(self, url, payload, headers):
        full = ""
        try:
            resp = requests.post(url, json=payload, headers=headers, stream=True, timeout=600)
            resp.raise_for_status()
        except Exception as e:
            self.error_signal.emit(str(e))
            return None, str(e)

        pending_reasoning = ""
        pending_content = ""
        last_flush = time.monotonic()
        FLUSH_INTERVAL = 0.05

        for chunk in resp.iter_content(chunk_size=None):
            if self._abort:
                return full, "aborted"
            if not chunk:
                continue
            for line in chunk.decode("utf-8", errors="replace").split("\n"):
                if not line.startswith("data: "):
                    continue
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    if pending_reasoning:
                        self.chunk_received.emit(json.dumps({"reasoning": pending_reasoning}))
                    if pending_content:
                        self.chunk_received.emit(json.dumps({"content": pending_content}))
                    return full, None
                try:
                    obj = json.loads(data_str)
                    choices = obj.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        reasoning = delta.get("reasoning_content", "")
                        content = delta.get("content", "")
                        if reasoning:
                            pending_reasoning += reasoning
                        if content:
                            full += content
                            pending_content += content
                        if time.monotonic() - last_flush >= FLUSH_INTERVAL:
                            if pending_reasoning:
                                self.chunk_received.emit(json.dumps({"reasoning": pending_reasoning}))
                                pending_reasoning = ""
                            if pending_content:
                                self.chunk_received.emit(json.dumps({"content": pending_content}))
                                pending_content = ""
                            last_flush = time.monotonic()
                except json.JSONDecodeError:
                    pass
        if pending_reasoning:
            self.chunk_received.emit(json.dumps({"reasoning": pending_reasoning}))
        if pending_content:
            self.chunk_received.emit(json.dumps({"content": pending_content}))
        return full, None

    def run(self):
        from .prompts import PDF_SYSTEM_PROMPT, PDF_VISION_PROMPT
        thinking_kv = {"type": "enabled"} if self.thinking_enabled else {"type": "disabled"}
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.model['api_key']}",
        }

        if self.is_vision:
            # Batch mode: split images, two calls
            images = self.data
            batch_size = 9
            prompt = PDF_VISION_PROMPT

            first_batch = images[:batch_size]
            remaining = images[batch_size:]

            # Call 1: send first batch, ask to acknowledge
            img_content_1 = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}} for b64 in first_batch]
            img_content_1.append({"type": "text", "text": "请先识别这些试卷图片的内容，熟悉试卷结构和排版，只输出且仅输出OK，不要输出其他任何内容。"})

            p1_payload = {
                "model": self.model["model_name"],
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": img_content_1},
                ],
                "temperature": 0.3,
                "stream": True,
            }
            p1_payload["thinking"] = thinking_kv

            p1_text, err = self._stream_call(url, p1_payload, headers)
            if err or self._abort:
                return

            # Call 2: remaining images + final prompt
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": img_content_1},
                {"role": "assistant", "content": p1_text},
            ]
            img_content_2 = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}} for b64 in remaining]
            img_content_2.append({"type": "text", "text": "请继续识别剩余试卷图片内容。结合之前已经识别的内容，输出完整JSON。"})

            messages.append({"role": "user", "content": img_content_2})
            p2_payload = {
                "model": self.model["model_name"],
                "messages": messages,
                "temperature": 0.3,
                "stream": True,
            }
            p2_payload["thinking"] = thinking_kv

            p2_text, err = self._stream_call(url, p2_payload, headers)
            if err or self._abort:
                return
            self.finished_signal.emit(p2_text)

        else:
            # Split mode: OCR text, two calls with shared session
            prompt = PDF_SYSTEM_PROMPT
            full_text = self.data  # this is the OCR text string

            # Call 1: source + listening + reading + seven_choices
            p1_messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"试卷内容：\n{full_text}\n\n请提取并返回 source、listening、reading、seven_choices 部分的JSON。只输出JSON，不要其他内容。"},
            ]
            p1_payload = {
                "model": self.model["model_name"],
                "messages": p1_messages,
                "temperature": 0.3,
                "stream": True,
            }
            p1_payload["thinking"] = thinking_kv

            p1_text, err = self._stream_call(url, p1_payload, headers)
            if err or self._abort:
                return

            # Call 2: cloze + grammar + writing + continuation
            p2_messages = p1_messages + [
                {"role": "assistant", "content": p1_text},
                {"role": "user", "content": "请继续提取并返回 cloze、grammar、writing、continuation 部分的JSON。只输出JSON，不要其他内容。"},
            ]
            p2_payload = {
                "model": self.model["model_name"],
                "messages": p2_messages,
                "temperature": 0.3,
                "stream": True,
            }
            p2_payload["thinking"] = thinking_kv

            p2_text, err = self._stream_call(url, p2_payload, headers)
            if err or self._abort:
                return

            # Merge both parts using the robust extract_json
            part1, err1 = extract_json(p1_text)
            if err1:
                self.error_signal.emit("第一批 JSON 解析失败: " + err1)
                return
            part2, err2 = extract_json(p2_text)
            if err2:
                self.error_signal.emit("第二批 JSON 解析失败: " + err2)
                return
            combined = {}
            combined.update(part1)
            combined.update(part2)
            self.finished_signal.emit(json.dumps(combined, ensure_ascii=False))


class ApiBridge(QObject):
    toastMessage = Signal(str, str)
    modelsChanged = Signal()
    ocrConfigChanged = Signal()

    writingChunk = Signal(str)
    writingDone = Signal(str)
    writingError = Signal(str)

    asrProgress = Signal(int, str)
    asrDone = Signal(str)
    asrError = Signal(str)

    listeningChunk = Signal(str)
    listeningDone = Signal(str)
    listeningError = Signal(str)

    ocrProgress = Signal(int, str)
    ocrDone = Signal(list)
    ocrError = Signal(str)

    pdfToImagesDone = Signal(list)
    pdfToImagesError = Signal(str)

    pdfChunk = Signal(str)
    pdfDone = Signal(str)
    pdfError = Signal(str)

    phoneConnected = Signal()
    phoneDisconnected = Signal()
    phoneImageReceived = Signal(str)
    phoneImagesChanged = Signal()
    phoneStartRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sse_worker = None
        self._asr_worker = None
        self._ocr_worker = None
        self._pdf_img_worker = None
        self._last_pdf_result = {}
        self._tmp_files = {}
        self._phone_server = PhoneServer(self)
        self._phone_server.phoneConnected.connect(self.phoneConnected.emit)
        self._phone_server.phoneDisconnected.connect(self.phoneDisconnected.emit)
        self._phone_server.imageReceived.connect(self.phoneImageReceived.emit)
        self._phone_server.imagesChanged.connect(self.phoneImagesChanged.emit)
        self._phone_server.startRequested.connect(self.phoneStartRequested.emit)

    @Slot(result=str)
    def getModelsJson(self):
        return json.dumps(load_models())

    @Slot(str, str, str, str, bool, bool, result=str)
    def addModel(self, alias, base_url, model_name, api_key, thinking_enabled, vision_enabled):
        models = load_models()
        new_model = {
            "id": str(int(time.time() * 1000)),
            "alias": alias.strip(),
            "base_url": base_url.strip(),
            "model_name": model_name.strip(),
            "api_key": api_key.strip(),
            "thinking_enabled": thinking_enabled,
            "vision_enabled": vision_enabled,
        }
        models.append(new_model)
        save_models(models)
        self.modelsChanged.emit()
        return json.dumps(new_model)

    @Slot(str, str, str, str, str, bool, bool, result=str)
    def updateModel(self, model_id, alias, base_url, model_name, api_key, thinking_enabled, vision_enabled):
        models = load_models()
        for m in models:
            if m["id"] == model_id:
                m["alias"] = alias.strip()
                m["base_url"] = base_url.strip()
                m["model_name"] = model_name.strip()
                m["api_key"] = api_key.strip()
                m["thinking_enabled"] = thinking_enabled
                m["vision_enabled"] = vision_enabled
                save_models(models)
                self.modelsChanged.emit()
                return json.dumps(m)
        return json.dumps({"error": "not found"})

    @Slot(str, result=bool)
    def deleteModel(self, model_id):
        models = load_models()
        models = [m for m in models if m["id"] != model_id]
        save_models(models)
        self.modelsChanged.emit()
        return True

    @Slot(str, result=str)
    def testModel(self, model_id):
        models = load_models()
        model = next((m for m in models if m["id"] == model_id), None)
        if not model:
            return json.dumps({"ok": False, "detail": "not found"})

        base_url = model["base_url"].rstrip("/")
        url = f"{base_url}/chat/completions"
        payload = json.dumps({
            "model": model["model_name"],
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5,
        }).encode("utf-8")

        req = urllib.request.Request(
            url, data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {model['api_key']}",
            },
            method="POST",
        )

        try:
            start = time.time()
            resp = urllib.request.urlopen(req, timeout=15)
            elapsed = round((time.time() - start) * 1000)
            body = json.loads(resp.read().decode("utf-8"))
            return json.dumps({"ok": True, "elapsed_ms": elapsed, "model": body.get("model", "")})
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")[:300]
            except Exception:
                pass
            return json.dumps({"ok": False, "status": e.code, "detail": err_body})
        except Exception as e:
            return json.dumps({"ok": False, "detail": str(e)[:300]})

    @Slot(result=str)
    def getOcrConfig(self):
        return json.dumps(load_config())

    @Slot(str, str)
    def saveOcrConfig(self, host, port):
        config = load_config()
        config["ocr_host"] = host or "127.0.0.1"
        config["ocr_port"] = port or "1224"
        save_config(config)
        self.ocrConfigChanged.emit()
        self.toastMessage.emit("OCR 配置已保存", "success")

    @Slot(str, result=str)
    def testOcrConnection(self, url):
        try:
            resp = urllib.request.urlopen(url, timeout=8)
            text = resp.read().decode("utf-8").strip()[:100]
            return json.dumps({"ok": True, "text": text})
        except Exception as e:
            return json.dumps({"ok": False, "detail": str(e)[:200]})

    @Slot(str, str, bool, str)
    def startWritingGeneration(self, passage, model_id, thinking_enabled, mode):
        models = load_models()
        model = next((m for m in models if m["id"] == model_id), None)
        if not model:
            self.writingError.emit("模型未找到")
            return

        if self._sse_worker and self._sse_worker.isRunning():
            self._sse_worker.abort()
            self._sse_worker.wait(2000)

        from .prompts import WRITING_CONTINUATION_PROMPT, WRITING_PRACTICAL_PROMPT
        prompt = WRITING_PRACTICAL_PROMPT if mode == "practical" else WRITING_CONTINUATION_PROMPT

        base_url = model["base_url"].rstrip("/")
        url = f"{base_url}/chat/completions"
        payload = {
            "model": model["model_name"],
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": passage},
            ],
            "stream": True,
        }
        payload["thinking"] = {"type": "enabled"} if thinking_enabled else {"type": "disabled"}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model['api_key']}",
        }

        self._sse_worker = SseWorker(url, payload, headers)
        self._sse_worker.chunk_received.connect(self.writingChunk.emit)
        self._sse_worker.finished_signal.connect(self.writingDone.emit)
        self._sse_worker.error_signal.connect(self.writingError.emit)
        self._sse_worker.start()

    @Slot()
    def cancelGeneration(self):
        if self._sse_worker and self._sse_worker.isRunning():
            self._sse_worker.abort()
            self._sse_worker.wait(2000)

    @Slot(str, str, result=str)
    def saveWritingDocx(self, content, mode):
        from .export import build_writing_docx
        default_name = "应用文写作思路.docx" if mode == "practical" else "读后续写思路.docx"
        filepath = self._ask_save_path(default_name, "Word 文档 (*.docx)")
        if not filepath:
            return json.dumps({"ok": False, "cancelled": True})
        if not filepath.endswith(".docx"):
            filepath += ".docx"
        try:
            build_writing_docx(content, filepath)
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(str, str)
    def startListenAsr(self, filepath, filename):
        if self._asr_worker and self._asr_worker.isRunning():
            self._asr_worker.wait(2000)

        self._asr_worker = AsrWorker(filepath)
        self._asr_worker.progress.connect(self.asrProgress.emit)
        self._asr_worker.done.connect(self.asrDone.emit)
        self._asr_worker.error.connect(self.asrError.emit)
        self._asr_worker.start()

    @Slot(str, str, bool)
    def startListeningGeneration(self, transcript, model_id, thinking_enabled):
        models = load_models()
        model = next((m for m in models if m["id"] == model_id), None)
        if not model:
            self.listeningError.emit("模型未找到")
            return

        if self._sse_worker and self._sse_worker.isRunning():
            self._sse_worker.abort()
            self._sse_worker.wait(2000)

        from .prompts import LISTENING_SYSTEM_PROMPT
        base_url = model["base_url"].rstrip("/")
        url = f"{base_url}/chat/completions"
        payload = {
            "model": model["model_name"],
            "messages": [
                {"role": "system", "content": LISTENING_SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            "temperature": 0.3,
            "stream": True,
        }
        payload["thinking"] = {"type": "enabled"} if thinking_enabled else {"type": "disabled"}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {model['api_key']}",
        }

        self._sse_worker = SseWorker(url, payload, headers)
        self._sse_worker.chunk_received.connect(self.listeningChunk.emit)
        self._sse_worker.finished_signal.connect(self.listeningDone.emit)
        self._sse_worker.error_signal.connect(self.listeningError.emit)
        self._sse_worker.start()

    @Slot(str, str, result=str)
    def saveListeningDocx(self, json_str, filename):
        from .export import build_listening_docx
        data, err = self._extract_json(json_str)
        if err:
            return json.dumps({"ok": False, "error": err})

        save_filename = filename if filename else "听力材料.docx"
        if not save_filename.endswith(".docx"):
            save_filename = save_filename.rsplit(".", 1)[0] + ".docx"

        filepath = self._ask_save_path(save_filename, "Word 文档 (*.docx)")
        if not filepath:
            return json.dumps({"ok": False, "cancelled": True})
        if not filepath.endswith(".docx"):
            filepath += ".docx"
        try:
            build_listening_docx(data, filepath)
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(str, result=str)
    def startPdfOcr(self, filepath):
        config = load_config()
        host = config.get("ocr_host", "127.0.0.1")
        port = config.get("ocr_port", "1224")

        if self._ocr_worker and self._ocr_worker.isRunning():
            self._ocr_worker.wait(2000)

        self._ocr_worker = OcrWorker(filepath, host, port)
        self._ocr_worker.progress.connect(self.ocrProgress.emit)
        self._ocr_worker.done.connect(self.ocrDone.emit)
        self._ocr_worker.error.connect(self.ocrError.emit)
        self._ocr_worker.start()
        return json.dumps({"ok": True})

    @Slot(str, result=str)
    def startPdfToImages(self, filepath):
        if self._pdf_img_worker and self._pdf_img_worker.isRunning():
            self._pdf_img_worker.wait(2000)

        self._pdf_img_worker = PdfToImagesWorker(filepath)
        self._pdf_img_worker.done.connect(self.pdfToImagesDone.emit)
        self._pdf_img_worker.error.connect(self.pdfToImagesError.emit)
        self._pdf_img_worker.start()
        return json.dumps({"ok": True})

    @Slot(str, str, bool, bool)
    def startPdfGeneration(self, pages_json, model_id, thinking_enabled, split_mode):
        models = load_models()
        model = next((m for m in models if m["id"] == model_id), None)
        if not model:
            self.pdfError.emit("模型未找到")
            return

        if self._sse_worker and self._sse_worker.isRunning():
            self._sse_worker.abort()
            self._sse_worker.wait(2000)

        pages = json.loads(pages_json)
        full_text = "\n\n".join(pages)

        from .prompts import PDF_SYSTEM_PROMPT
        base_url = model["base_url"].rstrip("/")

        if split_mode:
            self._sse_worker = SplitPdfWorker(base_url, model, full_text, thinking_enabled, is_vision=False)
        else:
            url = f"{base_url}/chat/completions"
            thinking_kv = {"type": "enabled"} if thinking_enabled else {"type": "disabled"}
            payload = {
                "model": model["model_name"],
                "messages": [
                    {"role": "system", "content": PDF_SYSTEM_PROMPT},
                    {"role": "user", "content": f"试卷内容：\n{full_text}\n\n请一次性输出完整JSON。"},
                ],
                "temperature": 0.3,
                "stream": True,
            }
            payload["thinking"] = thinking_kv
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {model['api_key']}",
            }
            self._sse_worker = SseWorker(url, payload, headers)

        self._sse_worker.chunk_received.connect(self.pdfChunk.emit)
        self._sse_worker.finished_signal.connect(self.pdfDone.emit)
        self._sse_worker.error_signal.connect(self.pdfError.emit)
        self._sse_worker.start()

    @Slot(str, str, bool, bool)
    def startVisionGeneration(self, images_json, model_id, thinking_enabled, batch_mode):
        models = load_models()
        model = next((m for m in models if m["id"] == model_id), None)
        if not model:
            self.pdfError.emit("模型未找到")
            return

        if self._sse_worker and self._sse_worker.isRunning():
            self._sse_worker.abort()
            self._sse_worker.wait(2000)

        images = json.loads(images_json)
        from .prompts import PDF_VISION_PROMPT
        base_url = model["base_url"].rstrip("/")

        if batch_mode and len(images) > 9:
            self._sse_worker = SplitPdfWorker(base_url, model, images, thinking_enabled, is_vision=True)
        else:
            url = f"{base_url}/chat/completions"
            content = []
            for b64 in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })
            content.append({"type": "text", "text": "请识别以上试卷图片内容，一次性输出完整JSON。"})

            payload = {
                "model": model["model_name"],
                "messages": [
                    {"role": "system", "content": PDF_VISION_PROMPT},
                    {"role": "user", "content": content},
                ],
                "temperature": 0.3,
                "stream": True,
            }
            payload["thinking"] = {"type": "enabled"} if thinking_enabled else {"type": "disabled"}
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {model['api_key']}",
            }
            self._sse_worker = SseWorker(url, payload, headers)

        self._sse_worker.chunk_received.connect(self.pdfChunk.emit)
        self._sse_worker.finished_signal.connect(self.pdfDone.emit)
        self._sse_worker.error_signal.connect(self.pdfError.emit)
        self._sse_worker.start()

    def _extract_json(self, text):
        return extract_json(text)

    @Slot(str, result=str)
    def savePdfDocx(self, json_str):
        from .export import build_pdf_docx
        data, err = self._extract_json(json_str)
        if err:
            return json.dumps({"ok": False, "error": err})

        source = data.get("source", "")
        save_filename = (source + "英语.docx") if source else "英语试卷.docx"

        filepath = self._ask_save_path(save_filename, "Word 文档 (*.docx)")
        if not filepath:
            return json.dumps({"ok": False, "cancelled": True})
        if not filepath.endswith(".docx"):
            filepath += ".docx"
        try:
            build_pdf_docx(data, filepath)
            return json.dumps({"ok": True})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return json.dumps({"ok": False, "error": str(e)[:300]})

    @Slot(str, result=str)
    @Slot(str, result=str)
    def savePdfPptx(self, json_str):
        from .export import build_pdf_pptx
        print(f"[PPT DEBUG] Raw input (first 500 chars): {json_str[:500] if json_str else 'EMPTY'}")
        data, err = self._extract_json(json_str)
        if err:
            return json.dumps({"ok": False, "error": err})

        source = data.get("source", "")
        save_filename = (source + "英语.pptx") if source else "英语试卷.pptx"

        filepath = self._ask_save_path(save_filename, "PPT 文档 (*.pptx)")
        if not filepath:
            return json.dumps({"ok": False, "cancelled": True})
        if not filepath.endswith(".pptx"):
            filepath += ".pptx"
        print(f"[PPT DEBUG] data keys: {list(data.keys())}, output={filepath}")
        try:
            build_pdf_pptx(data, filepath)
            return json.dumps({"ok": True})
        except IndexError as e:
            import traceback
            print(f"[PPT DEBUG] IndexError traceback:")
            traceback.print_exc()
            return json.dumps({"ok": False, "error": "PPT模板错误: " + str(e) })
        except Exception as e:
            import traceback
            print(f"[PPT DEBUG] Exception traceback:")
            traceback.print_exc()
            return json.dumps({"ok": False, "error": str(e)[:300]})


    @Slot(result=bool)
    def startPhoneServer(self):
        """Start the phone connection server."""
        return self._phone_server.startServer()

    @Slot()
    def stopPhoneServer(self):
        """Stop the phone connection server."""
        self._phone_server.stopServer()

    @Slot(result=str)
    def getPhoneLanIp(self):
        """Return the desktop LAN IP for the phone to connect to."""
        return self._phone_server.getLanIp()

    @Slot(result=str)
    def getPhoneNetworkName(self):
        """Return the name of the connected Wi-Fi network."""
        return self._phone_server.getNetworkName()

    @Slot(result=bool)
    def isPhoneConnected(self):
        """Return whether a phone is currently connected."""
        return self._phone_server.isPhoneConnected()

    @Slot(result=str)
    def getPhoneImagesJson(self):
        """Return uploaded phone images as a JSON array of base64 strings."""
        return self._phone_server.getImagesJson()

    @Slot(result=str)
    def getPhoneImagePathsJson(self):
        """Return current temp file paths as a JSON array."""
        return self._phone_server.getImagePathsJson()

    @Slot(result=int)
    def getPhoneImageCount(self):
        """Return the number of phone-uploaded images."""
        return self._phone_server.getImageCount()

    @Slot(int)
    def deletePhoneImage(self, index):
        self._phone_server.deleteImage(index, sync_to_phone=True)

    @Slot(int, int)
    def movePhoneImage(self, from_index, to_index):
        self._phone_server.moveImage(from_index, to_index, sync_to_phone=True)

    @Slot()
    def proceedOnPhone(self):
        """Tell the connected phone to move to the completion screen."""
        self._phone_server.notifyProceed()

    @Slot()
    def notifyPhoneProcessingStarted(self):
        """Notify the phone that AI processing has started."""
        self._phone_server.notifyProcessingStarted()

    @Slot()
    def notifyPhoneProcessingComplete(self):
        """Notify the phone that AI processing has finished."""
        self._phone_server.notifyProcessingComplete()

    @Slot(str, result=str)
    def openFileDialog(self, filter_str):
        """Open a file picker and return the selected path, or empty string if cancelled."""
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(None, "选择文件", "", filter_str)
        return path if path else ""

    @Slot(str, result=str)
    def saveTempFile(self, data_b64):
        tmpdir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tmp")
        os.makedirs(tmpdir, exist_ok=True)
        task_id = hashlib.md5(f"tmp{time.time()}".encode()).hexdigest()[:12]
        filepath = os.path.join(tmpdir, f"{task_id}.tmp")
        import base64 as b64
        with open(filepath, "wb") as f:
            f.write(b64.b64decode(data_b64))
        self._tmp_files[task_id] = filepath
        return filepath

    @Slot(str)
    def cleanupTempFile(self, filepath):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except Exception:
            pass

    def _ask_save_path(self, default_name, filter_str):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(None, "保存文件", default_name, filter_str)
        return path if path else ""
