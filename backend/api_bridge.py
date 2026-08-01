import base64
import json
import os
import time
import uuid

import pymupdf
import requests
from PySide6.QtCore import QObject, Signal, Slot, QThread

from .chat import (
    build_chat_request, extract_json, image_content, iter_sse_deltas, validate_http_url,
)
from .data import DEFAULT_CONFIG, load_config, load_models, save_config, save_models
from .phone_server import PhoneServer


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
        self._response = None

    def abort(self):
        self._abort = True
        if self._response is not None:
            self._response.close()

    def run(self):
        try:
            resp = requests.post(
                self.url, json=self.payload, headers=self.headers,
                stream=True, timeout=600,
            )
            resp.raise_for_status()
            self._response = resp
        except Exception as e:
            self.error_signal.emit(str(e))
            return

        full_content = ""
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

        try:
            for reasoning, content in iter_sse_deltas(
                resp.iter_content(chunk_size=None), lambda: self._abort
            ):
                if reasoning:
                    pending_reasoning += reasoning
                if content:
                    full_content += content
                    pending_content += content
                if time.monotonic() - last_flush >= FLUSH_INTERVAL:
                    flush()
        except Exception as exc:
            if not self._abort:
                self.error_signal.emit(str(exc))
            return
        finally:
            resp.close()
            self._response = None

        if self._abort:
            return

        flush()
        self.finished_signal.emit(full_content)


class AsrWorker(QThread):
    progress = Signal(int, str)
    done = Signal(str)
    error = Signal(str)

    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            text = self._run_asr()
            if not self._abort:
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
            if self._abort:
                return ""
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
            if self._abort:
                return ""
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
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            pages = self._run_ocr()
            if not self._abort:
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
            if self._abort:
                return []
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
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            with open(self.filepath, "rb") as f:
                pdf_bytes = f.read()
            doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
            images = []
            for page in doc:
                if self._abort:
                    doc.close()
                    return
                pix = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
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

    def __init__(self, model, data, thinking_enabled, is_vision=False, parent=None):
        super().__init__(parent)
        self.model = model
        self.data = data
        self.thinking_enabled = thinking_enabled
        self.is_vision = is_vision
        self._abort = False
        self._response = None

    def abort(self):
        self._abort = True
        if self._response is not None:
            self._response.close()

    def _flush(self, state):
        if state["reasoning"]:
            self.chunk_received.emit(json.dumps({"reasoning": state["reasoning"]}))
            state["reasoning"] = ""
        if state["content"]:
            self.chunk_received.emit(json.dumps({"content": state["content"]}))
            state["content"] = ""

    def _stream_call(self, url, payload, headers):
        full = ""
        try:
            resp = requests.post(url, json=payload, headers=headers, stream=True, timeout=600)
            resp.raise_for_status()
            self._response = resp
        except Exception as e:
            self.error_signal.emit(str(e))
            return None, str(e)

        flush_state = {"reasoning": "", "content": "", "at": time.monotonic()}
        FLUSH_INTERVAL = 0.05

        try:
            for reasoning, content in iter_sse_deltas(
                resp.iter_content(chunk_size=None), lambda: self._abort
            ):
                if reasoning:
                    flush_state["reasoning"] += reasoning
                if content:
                    full += content
                    flush_state["content"] += content
                if time.monotonic() - flush_state["at"] >= FLUSH_INTERVAL:
                    self._flush(flush_state)
                    flush_state["at"] = time.monotonic()
        except Exception as exc:
            if not self._abort:
                self.error_signal.emit(str(exc))
            return None, str(exc)
        finally:
            resp.close()
            self._response = None

        if self._abort:
            return full, "aborted"
        self._flush(flush_state)
        return full, None

    def _call(self, messages):
        url, payload, headers = build_chat_request(
            self.model, messages, self.thinking_enabled, temperature=0.3
        )
        return self._stream_call(url, payload, headers)

    def run(self):
        from .prompts import PDF_SYSTEM_PROMPT, PDF_VISION_PROMPT

        if self.is_vision:
            # Batch mode: acknowledge the first batch, then send the rest.
            prompt = PDF_VISION_PROMPT
            first_batch = self.data[:9]
            remaining = self.data[9:]

            ack_content = image_content(
                first_batch,
                "请先识别这些试卷图片的内容，熟悉试卷结构和排版，只输出且仅输出OK，不要输出其他任何内容。",
            )
            p1_text, err = self._call([
                {"role": "system", "content": prompt},
                {"role": "user", "content": ack_content},
            ])
            if err or self._abort:
                return

            p2_text, err = self._call([
                {"role": "system", "content": prompt},
                {"role": "user", "content": ack_content},
                {"role": "assistant", "content": p1_text},
                {"role": "user", "content": image_content(
                    remaining,
                    "请继续识别剩余试卷图片内容。结合之前已经识别的内容，输出完整JSON。",
                )},
            ])
            if err or self._abort:
                return
            self.finished_signal.emit(p2_text)

        else:
            # Split mode: OCR text, two calls with a shared session.
            full_text = self.data
            base_messages = [
                {"role": "system", "content": PDF_SYSTEM_PROMPT},
                {"role": "user", "content": f"试卷内容：\n{full_text}\n\n请提取并返回 source、listening、reading、seven_choices 部分的JSON。只输出JSON，不要其他内容。"},
            ]

            p1_text, err = self._call(base_messages)
            if err or self._abort:
                return

            p2_text, err = self._call(base_messages + [
                {"role": "assistant", "content": p1_text},
                {"role": "user", "content": "请继续提取并返回 cloze、grammar、writing、continuation 部分的JSON。只输出JSON，不要其他内容。"},
            ])
            if err or self._abort:
                return

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


class NetworkProbe(QThread):
    """Run a blocking network check off the GUI thread."""

    result = Signal(str)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func

    def run(self):
        try:
            self.result.emit(self._func())
        except Exception as exc:  # defensive: never let a probe thread die silently
            self.result.emit(json.dumps({"ok": False, "detail": str(exc)[:300]}))


class ApiBridge(QObject):
    toastMessage = Signal(str, str)
    modelsChanged = Signal()
    ocrConfigChanged = Signal()

    modelTested = Signal(str, str)  # model_id, JSON result
    ocrTested = Signal(str)         # JSON result

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

    phoneImageReceived = Signal(str)
    phoneImagesChanged = Signal()
    phoneStartRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._probes = []
        self._sse_worker = None
        self._asr_worker = None
        self._ocr_worker = None
        self._pdf_img_worker = None
        self._phone_server = PhoneServer(self)
        self._phone_server.imageReceived.connect(self.phoneImageReceived.emit)
        self._phone_server.imagesChanged.connect(self.phoneImagesChanged.emit)
        self._phone_server.startRequested.connect(self.phoneStartRequested.emit)

    @staticmethod
    def _stop_worker(worker, timeout_ms=5000):
        if not worker or not worker.isRunning():
            return True
        abort = getattr(worker, "abort", None)
        if abort:
            abort()
        return worker.wait(timeout_ms)

    def shutdown(self):
        self._phone_server.stopServer()
        for worker in (
            self._sse_worker, self._asr_worker, self._ocr_worker, self._pdf_img_worker,
            *self._probes,
        ):
            if worker and not self._stop_worker(worker, timeout_ms=1500):
                worker.terminate()
                worker.wait(1000)

    @Slot(result=str)
    def getModelsJson(self):
        return json.dumps(load_models())

    @Slot(str, str, str, str, bool, bool, result=str)
    def addModel(self, alias, base_url, model_name, api_key, thinking_enabled, vision_enabled):
        models = load_models()
        new_model = {
            "id": uuid.uuid4().hex,
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

    @Slot(str)
    def testModel(self, model_id):
        """Probe a model's endpoint in the background; result via ``modelTested``."""
        models = load_models()
        model = next((m for m in models if m["id"] == model_id), None)
        if not model:
            self.modelTested.emit(model_id, json.dumps({"ok": False, "detail": "模型不存在"}))
            return

        def probe():
            base_url = validate_http_url(model["base_url"])
            url = f"{base_url}/chat/completions"
            payload = {
                "model": model["model_name"],
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            }
            try:
                start = time.time()
                resp = requests.post(
                    url, json=payload,
                    headers={"Authorization": f"Bearer {model['api_key']}"},
                    timeout=15,
                )
                elapsed = round((time.time() - start) * 1000)
                resp.raise_for_status()
                body = resp.json()
                return json.dumps({
                    "ok": True, "elapsed_ms": elapsed, "model": body.get("model", ""),
                })
            except requests.HTTPError as exc:
                response = exc.response
                return json.dumps({
                    "ok": False,
                    "status": response.status_code if response is not None else 0,
                    "detail": response.text[:300] if response is not None else str(exc)[:300],
                })
            except Exception as e:
                return json.dumps({"ok": False, "detail": str(e)[:300]})

        self._run_probe(probe, lambda payload: self.modelTested.emit(model_id, payload))

    def _run_probe(self, func, on_result):
        worker = NetworkProbe(func, self)
        worker.result.connect(on_result)
        worker.finished.connect(lambda: self._probes.remove(worker) if worker in self._probes else None)
        self._probes.append(worker)
        worker.start()

    @Slot(result=str)
    def getOcrConfig(self):
        return json.dumps(load_config())

    @Slot(str, str)
    def saveOcrConfig(self, host, port):
        config = load_config()
        config["ocr_host"] = host or DEFAULT_CONFIG["ocr_host"]
        config["ocr_port"] = port or DEFAULT_CONFIG["ocr_port"]
        save_config(config)
        self.ocrConfigChanged.emit()
        self.toastMessage.emit("OCR 配置已保存", "success")

    @Slot(str)
    def testOcrConnection(self, url):
        """Probe the OCR service in the background; result via ``ocrTested``."""
        def probe():
            try:
                safe_url = validate_http_url(url)
                resp = requests.get(safe_url, timeout=8)
                resp.raise_for_status()
                text = resp.text.strip()[:100]
                return json.dumps({"ok": True, "text": text})
            except Exception as e:
                return json.dumps({"ok": False, "detail": str(e)[:200]})

        self._run_probe(probe, self.ocrTested.emit)

    @Slot(str, str, bool, str)
    def startWritingGeneration(self, passage, model_id, thinking_enabled, mode):
        models = load_models()
        model = next((m for m in models if m["id"] == model_id), None)
        if not model:
            self.writingError.emit("模型未找到")
            return

        from .prompts import WRITING_CONTINUATION_PROMPT, WRITING_PRACTICAL_PROMPT
        prompt = WRITING_PRACTICAL_PROMPT if mode == "practical" else WRITING_CONTINUATION_PROMPT

        url, payload, headers = build_chat_request(
            model,
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": passage},
            ],
            thinking_enabled,
        )
        self._start_stream(
            SseWorker(url, payload, headers),
            self.writingChunk, self.writingDone, self.writingError,
        )

    @Slot()
    def cancelGeneration(self):
        self._stop_worker(self._sse_worker)

    def _start_stream(self, worker, chunk_signal, done_signal, error_signal):
        """Abort any in-flight stream, wire up signals, and start *worker*."""
        if not self._stop_worker(self._sse_worker):
            error_signal.emit("上一项 AI 任务仍在停止，请稍后重试")
            return
        worker.chunk_received.connect(chunk_signal.emit)
        worker.finished_signal.connect(done_signal.emit)
        worker.error_signal.connect(error_signal.emit)
        self._sse_worker = worker
        worker.start()

    def _pick_save_path(self, default_name, filter_str, ext):
        """Ask for a save path and make sure it carries *ext*. None if cancelled."""
        filepath = self._ask_save_path(default_name, filter_str)
        if not filepath:
            return None
        if not filepath.endswith(ext):
            filepath += ext
        return filepath

    @Slot(str, str, result=str)
    def saveWritingDocx(self, content, mode):
        from .export import build_writing_docx
        default_name = "应用文写作思路.docx" if mode == "practical" else "读后续写思路.docx"
        filepath = self._pick_save_path(default_name, "Word 文档 (*.docx)", ".docx")
        if not filepath:
            return json.dumps({"ok": False, "cancelled": True})
        try:
            build_writing_docx(content, filepath)
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(str, str)
    def startListenAsr(self, filepath, filename):
        if not self._stop_worker(self._asr_worker):
            self.asrError.emit("上一项转写任务仍在停止，请稍后重试")
            return

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

        from .prompts import LISTENING_SYSTEM_PROMPT
        url, payload, headers = build_chat_request(
            model,
            [
                {"role": "system", "content": LISTENING_SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            thinking_enabled,
            temperature=0.3,
        )
        self._start_stream(
            SseWorker(url, payload, headers),
            self.listeningChunk, self.listeningDone, self.listeningError,
        )

    @Slot(str, str, result=str)
    def saveListeningDocx(self, content, filename):
        from .export import build_listening_docx
        data, err = extract_json(content)
        if err:
            return json.dumps({"ok": False, "error": err})

        save_filename = filename if filename else "听力材料.docx"
        if not save_filename.endswith(".docx"):
            save_filename = save_filename.rsplit(".", 1)[0] + ".docx"

        filepath = self._pick_save_path(save_filename, "Word 文档 (*.docx)", ".docx")
        if not filepath:
            return json.dumps({"ok": False, "cancelled": True})
        try:
            build_listening_docx(data, filepath)
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})

    @Slot(str, result=str)
    def startPdfOcr(self, filepath):
        config = load_config()
        host = config["ocr_host"]
        port = config["ocr_port"]

        if not self._stop_worker(self._ocr_worker):
            self.ocrError.emit("上一项 OCR 任务仍在停止，请稍后重试")
            return json.dumps({"ok": False})

        self._ocr_worker = OcrWorker(filepath, host, port)
        self._ocr_worker.progress.connect(self.ocrProgress.emit)
        self._ocr_worker.done.connect(self.ocrDone.emit)
        self._ocr_worker.error.connect(self.ocrError.emit)
        self._ocr_worker.start()
        return json.dumps({"ok": True})

    @Slot(str, result=str)
    def startPdfToImages(self, filepath):
        if not self._stop_worker(self._pdf_img_worker):
            self.pdfToImagesError.emit("上一项 PDF 转换任务仍在停止，请稍后重试")
            return json.dumps({"ok": False})

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

        pages = json.loads(pages_json)
        full_text = "\n\n".join(pages)

        from .prompts import PDF_SYSTEM_PROMPT

        if split_mode:
            worker = SplitPdfWorker(model, full_text, thinking_enabled, is_vision=False)
        else:
            url, payload, headers = build_chat_request(
                model,
                [
                    {"role": "system", "content": PDF_SYSTEM_PROMPT},
                    {"role": "user", "content": f"试卷内容：\n{full_text}\n\n请一次性输出完整JSON。"},
                ],
                thinking_enabled,
                temperature=0.3,
            )
            worker = SseWorker(url, payload, headers)

        self._start_stream(worker, self.pdfChunk, self.pdfDone, self.pdfError)

    @Slot(str, str, bool, bool)
    def startVisionGeneration(self, images_json, model_id, thinking_enabled, batch_mode):
        models = load_models()
        model = next((m for m in models if m["id"] == model_id), None)
        if not model:
            self.pdfError.emit("模型未找到")
            return

        images = json.loads(images_json)
        from .prompts import PDF_VISION_PROMPT

        if batch_mode and len(images) > 9:
            worker = SplitPdfWorker(model, images, thinking_enabled, is_vision=True)
        else:
            url, payload, headers = build_chat_request(
                model,
                [
                    {"role": "system", "content": PDF_VISION_PROMPT},
                    {"role": "user", "content": image_content(
                        images, "请识别以上试卷图片内容，一次性输出完整JSON。"
                    )},
                ],
                thinking_enabled,
                temperature=0.3,
            )
            worker = SseWorker(url, payload, headers)

        self._start_stream(worker, self.pdfChunk, self.pdfDone, self.pdfError)

    @Slot(str, result=str)
    def savePdfDocx(self, content):
        from .export import build_pdf_docx
        data, err = extract_json(content)
        if err:
            return json.dumps({"ok": False, "error": err})

        source = data.get("source", "")
        save_filename = (source + "英语.docx") if source else "英语试卷.docx"
        filepath = self._pick_save_path(save_filename, "Word 文档 (*.docx)", ".docx")
        if not filepath:
            return json.dumps({"ok": False, "cancelled": True})
        try:
            build_pdf_docx(data, filepath)
            return json.dumps({"ok": True})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)[:300]})

    @Slot(str, result=str)
    def savePdfPptx(self, content):
        from .export import build_pdf_pptx
        data, err = extract_json(content)
        if err:
            return json.dumps({"ok": False, "error": err})

        source = data.get("source", "")
        save_filename = (source + "英语.pptx") if source else "英语试卷.pptx"
        filepath = self._pick_save_path(save_filename, "PPT 文档 (*.pptx)", ".pptx")
        if not filepath:
            return json.dumps({"ok": False, "cancelled": True})
        try:
            build_pdf_pptx(data, filepath)
            return json.dumps({"ok": True})
        except IndexError as e:
            return json.dumps({"ok": False, "error": "PPT模板错误: " + str(e)})
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)[:300]})


    @Slot(result=bool)
    def startPhoneServer(self):
        """Start the phone HTTP upload server."""
        return self._phone_server.startServer()

    @Slot()
    def stopPhoneServer(self):
        """Stop the phone HTTP upload server."""
        self._phone_server.stopServer()

    @Slot(result=str)
    def getPhoneConnectionUrl(self):
        """Return the token-protected phone upload URL."""
        return self._phone_server.getConnectionUrl()

    @Slot(result=str)
    def getPhoneNetworkName(self):
        """Return the name of the connected Wi-Fi network."""
        return self._phone_server.getNetworkName()

    @Slot(result=str)
    def getPhoneImagesJson(self):
        """Return uploaded phone images as a JSON array of base64 strings."""
        return self._phone_server.getImagesJson()

    @Slot(result=str)
    def getPhoneImagePathsJson(self):
        """Return current temp file paths as a JSON array."""
        return self._phone_server.getImagePathsJson()

    @Slot(int)
    def deletePhoneImage(self, index):
        self._phone_server.deleteImage(index)

    @Slot(int, int)
    def movePhoneImage(self, from_index, to_index):
        self._phone_server.moveImage(from_index, to_index)

    @staticmethod
    def _dialog_parent():
        """Return the active window so native dialogs stay attached to it."""
        from PySide6.QtWidgets import QApplication
        return QApplication.activeWindow()

    @Slot(str, result=str)
    def openFileDialog(self, filter_str):
        """Open a file picker and return the selected path, or empty string if cancelled."""
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self._dialog_parent(), "选择文件", "", filter_str
        )
        return path if path else ""

    def _ask_save_path(self, default_name, filter_str):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self._dialog_parent(), "保存文件", default_name, filter_str
        )
        return path if path else ""
