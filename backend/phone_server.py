import base64
import json
import logging
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import unquote, urlparse

from PySide6.QtCore import QObject, QUrl, Signal

from .data import DATA_DIR

logger = logging.getLogger(__name__)

HTTP_PORT = 18924
MAX_IMAGES = 40
MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_IMAGE_BYTES = 120 * 1024 * 1024
MAX_IMAGE_BASE64 = (MAX_IMAGE_BYTES * 4 // 3) + 8
MAX_REQUEST_BYTES = MAX_IMAGE_BASE64 + 4096
IMAGE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
RESOURCE_ROOT = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(__file__)))
APP_ICON_PATH = os.path.join(RESOURCE_ROOT, "assets", "icons", "baka.png")

PHONE_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<meta name="theme-color" content="#f3f5fa">
<link id="favicon" rel="icon" type="image/png">
<title>Lume 手机上传</title>
<style>
:root { color-scheme:light; --window:#f3f5fa; --card:#fff; --card-hover:#fbfcfe; --text:#101828; --secondary:#475467; --muted:#98a2b3; --border:#e4e7ec; --accent:#4f8ef7; --accent-hover:#3d7ce8; --accent-soft:#eaf1fe; --success:#12b76a; --success-soft:#e7f8f0; --danger:#f04438; --danger-soft:#feecea; --hover:#f2f4f7; }
* { box-sizing:border-box; }
body { margin:0; min-height:100vh; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei UI",sans-serif; color:var(--text); background:var(--window); }
main { width:min(100%,520px); margin:auto; padding:28px 18px 72px; }
.hero { display:flex; align-items:center; justify-content:center; gap:12px; margin:4px 0 24px; }
.logo { width:58px; height:58px; object-fit:contain; }
.hero-copy { text-align:left; }
.brand { font-size:28px; line-height:1.1; font-weight:750; letter-spacing:-.5px; color:var(--text); }
.subtitle { color:var(--secondary); margin-top:5px; }
.card { background:var(--card); border:1px solid var(--border); border-radius:14px; padding:18px; margin-bottom:12px; box-shadow:0 6px 18px rgba(15,23,42,.05); }
.status { display:flex; align-items:center; gap:10px; font-weight:650; }
.dot { width:10px; height:10px; border-radius:50%; background:#f79009; box-shadow:0 0 0 5px #fef3e2; }
.dot.ok { background:var(--success); box-shadow:0 0 0 5px var(--success-soft); }
.dot.error { background:var(--danger); box-shadow:0 0 0 5px var(--danger-soft); }
.hint { color:var(--muted); font-size:13px; line-height:1.55; margin:9px 0 0 20px; }
.actions { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
button { appearance:none; border:0; border-radius:13px; min-height:48px; padding:0 14px; font-size:15px; font-weight:700; cursor:pointer; transition:transform .14s ease,opacity .14s ease,box-shadow .14s ease; }
button:active { transform:scale(.975); } button:disabled { opacity:.42; cursor:not-allowed; }
.primary { color:#fff; background:var(--accent); box-shadow:0 5px 14px rgba(79,142,247,.2); }
.primary:hover { background:var(--accent-hover); }
.secondary { color:var(--accent); background:var(--accent-soft); } .submit { width:100%; margin-top:14px; } input { display:none; }
.section-title { display:flex; justify-content:space-between; align-items:center; font-weight:700; margin-bottom:12px; }
.count { color:var(--muted); font-size:13px; font-weight:500; } .grid { display:grid; grid-template-columns:repeat(3,1fr); gap:9px; }
.empty { color:var(--muted); text-align:center; padding:26px 8px; font-size:14px; }
.item { position:relative; aspect-ratio:3/4; overflow:hidden; border:1px solid var(--border); border-radius:12px; background:var(--hover); animation:appear .22s ease-out; }
.item img { width:100%; height:100%; object-fit:cover; display:block; } .item-controls { position:absolute; inset:auto 5px 5px; display:flex; gap:4px; }
.item-controls button { min-height:28px; padding:0; flex:1; border-radius:7px; color:#fff; background:rgba(14,18,30,.74); backdrop-filter:blur(5px); font-size:13px; }
.complete { text-align:center; padding:34px 18px; } .complete-mark { width:64px; height:64px; margin:0 auto 15px; display:grid; place-items:center; border-radius:50%; color:#fff; background:var(--success); font-size:32px; }
.hidden { display:none !important; } @keyframes appear { from { opacity:0; transform:translateY(5px) scale(.98); } }
@media (prefers-color-scheme:dark) { :root { color-scheme:dark; --window:#131519; --card:#1c2026; --card-hover:#212630; --text:#f2f4f7; --secondary:#b3bcc8; --muted:#7c8794; --border:#282d35; --accent:#6ba1ff; --accent-hover:#83b1ff; --accent-soft:#1c293d; --success:#3ddc97; --success-soft:#12301f; --danger:#ff7a70; --danger-soft:#3a1c1a; --hover:#22262e; } .card { box-shadow:0 6px 18px rgba(0,0,0,.18); } }
@media (prefers-reduced-motion:reduce) { * { animation:none !important; transition:none !important; } }
</style>
</head>
<body><main>
  <header class="hero"><img id="logo" class="logo" alt="Lume"><div class="hero-copy"><div class="brand">Lume</div><div class="subtitle">手机试卷上传</div></div></header>
  <section class="card"><div class="status"><span id="dot" class="dot"></span><span id="status">正在连接电脑</span></div><p id="hint" class="hint">请保持手机与电脑处于同一局域网</p></section>
  <div id="upload" class="hidden">
    <section class="card"><div class="actions"><button id="camera" class="primary">拍照上传</button><button id="gallery" class="secondary">从相册选择</button></div><input id="cameraInput" type="file" accept="image/*" capture="environment"><input id="galleryInput" type="file" accept="image/*" multiple></section>
    <section class="card"><div class="section-title"><span>已上传图片</span><span id="count" class="count">0 / 40</span></div><div id="grid" class="grid"></div><div id="empty" class="empty">拍照或从相册选择图片后，将自动上传到电脑</div></section>
    <button id="submit" class="primary submit" disabled>完成上传，进入下一步</button>
  </div>
  <section id="complete" class="card complete hidden"><div class="complete-mark">&#10003;</div><h2>已提交</h2><p class="subtitle">请返回电脑继续识别与导出</p></section>
</main>
<script>
const base = location.pathname.replace(/\/$/, '');
const localImages = new Map(); let orderedIds = []; let submitted = false; let polling = false;
const byId = (id) => document.getElementById(id); const dot = byId('dot'), statusText = byId('status'), hint = byId('hint');
const upload = byId('upload'), complete = byId('complete'), grid = byId('grid');
byId('logo').src = base + '/icon.png'; byId('favicon').href = base + '/icon.png';
function setStatus(text, type='', detail='') { statusText.textContent=text; hint.textContent=detail; dot.className='dot '+type; }
async function api(path, options={}) { const response=await fetch(base+path,{cache:'no-store',...options}); let data={}; try { data=await response.json(); } catch (_) {} if (!response.ok || data.ok===false) throw new Error(data.error || `请求失败 (${response.status})`); return data; }
function showSubmitted() { submitted=true; upload.classList.add('hidden'); complete.classList.remove('hidden'); setStatus('上传已完成','ok','请在电脑端继续操作'); }
function syncState(state) { orderedIds=state.images || []; for (const id of [...localImages.keys()]) if (!orderedIds.includes(id)) localImages.delete(id); if (state.submitted) showSubmitted(); else { upload.classList.remove('hidden'); complete.classList.add('hidden'); setStatus('上传服务已连接','ok','图片仅在当前局域网会话中传输'); } render(); }
async function refresh() { if (polling || submitted) return; polling=true; try { syncState(await api('/state')); } catch (error) { setStatus('连接暂时中断','error',error.message+'，正在重试'); } finally { polling=false; } }
function render() { grid.replaceChildren(); byId('count').textContent=`${orderedIds.length} / 40`; byId('empty').classList.toggle('hidden',orderedIds.length>0); byId('submit').disabled=orderedIds.length===0; orderedIds.forEach((id,index)=>{ const item=document.createElement('div'); item.className='item'; const image=document.createElement('img'); image.alt=`第 ${index+1} 张`; image.src=localImages.get(id) || `${base}/image/${encodeURIComponent(id)}`; item.appendChild(image); const controls=document.createElement('div'); controls.className='item-controls'; [['↑',index>0,()=>move(index,index-1)],['↓',index<orderedIds.length-1,()=>move(index,index+1)],['×',true,()=>remove(index)]].forEach(([label,enabled,handler])=>{ const button=document.createElement('button'); button.textContent=label; button.disabled=!enabled; button.onclick=handler; controls.appendChild(button); }); item.appendChild(controls); grid.appendChild(item); }); }
async function move(from,to) { try { syncState(await api('/move',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({from,to})})); } catch(error) { setStatus('调整顺序失败','error',error.message); } }
async function remove(index) { try { syncState(await api('/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({index})})); } catch(error) { setStatus('删除失败','error',error.message); } }
async function prepare(file) { if (orderedIds.length>=40) throw new Error('一次最多上传 40 张图片'); const source=await new Promise((resolve,reject)=>{ const reader=new FileReader(); reader.onload=()=>resolve(reader.result); reader.onerror=()=>reject(new Error('读取图片失败')); reader.readAsDataURL(file); }); const image=await new Promise((resolve,reject)=>{ const value=new Image(); value.onload=()=>resolve(value); value.onerror=()=>reject(new Error('无法解析图片')); value.src=source; }); const max=2500, scale=Math.min(1,max/Math.max(image.width,image.height)); const canvas=document.createElement('canvas'); canvas.width=Math.round(image.width*scale); canvas.height=Math.round(image.height*scale); const context=canvas.getContext('2d'); context.fillStyle='#fff'; context.fillRect(0,0,canvas.width,canvas.height); context.drawImage(image,0,0,canvas.width,canvas.height); const preview=canvas.toDataURL('image/jpeg',.9), id=`img_${Date.now()}_${Math.random().toString(36).slice(2,9)}`; const result=await api('/upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,data:preview.split(',')[1]})}); localImages.set(id,preview); syncState(result); }
async function uploadFiles(files) { setStatus('正在上传','','请不要关闭当前页面'); for (const file of files) { try { await prepare(file); } catch(error) { setStatus('部分图片上传失败','error',error.message); return; } } setStatus('上传服务已连接','ok','可以继续拍照，或调整图片顺序'); }
byId('camera').onclick=()=>byId('cameraInput').click(); byId('gallery').onclick=()=>byId('galleryInput').click(); for (const id of ['cameraInput','galleryInput']) byId(id).onchange=(event)=>{ uploadFiles([...event.target.files]); event.target.value=''; };
byId('submit').onclick=async()=>{ try { await api('/start',{method:'POST'}); showSubmitted(); } catch(error) { setStatus('提交失败','error',error.message); } }; refresh(); setInterval(refresh,1500);
</script></body></html>"""


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class PhoneHTTPRequestHandler(BaseHTTPRequestHandler):
    server_version = "LumeHTTP/1.0"
    timeout = 15

    def setup(self):
        super().setup()
        self.connection.settimeout(self.timeout)

    @property
    def phone_server(self):
        return self.server.phone_server

    def _route(self):
        parts = [unquote(part) for part in urlparse(self.path).path.split("/") if part]
        if not parts or not self.phone_server.matchesToken(parts[0]):
            return None
        return parts[1:]

    def _send_bytes(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status=200, **payload):
        self._send_bytes(
            status,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("无效的请求长度") from exc
        if length <= 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("请求内容为空或过大")
        try:
            return json.loads(self.rfile.read(length))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("无效的 JSON 数据") from exc

    def do_GET(self):
        route = self._route()
        if route is None:
            self.send_error(404)
        elif not route:
            self._send_bytes(200, PHONE_HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif route == ["state"]:
            self._send_json(ok=True, **self.phone_server.getHttpState())
        elif route == ["icon.png"]:
            icon = self.phone_server.getAppIconBytes()
            if icon is None:
                self.send_error(404)
            else:
                self._send_bytes(200, icon, "image/png")
        elif len(route) == 2 and route[0] == "image":
            image = self.phone_server.getImageBytes(route[1])
            if image is None:
                self.send_error(404)
            else:
                self._send_bytes(200, image, "image/jpeg")
        else:
            self.send_error(404)

    def do_POST(self):
        route = self._route()
        if route is None:
            self.send_error(404)
            return
        try:
            if route == ["upload"]:
                payload = self._read_json()
                self.phone_server.addImage(payload.get("id", ""), payload.get("data", ""))
            elif route == ["move"]:
                payload = self._read_json()
                self.phone_server.moveImage(payload.get("from", -1), payload.get("to", -1))
            elif route == ["delete"]:
                payload = self._read_json()
                self.phone_server.deleteImage(payload.get("index", -1))
            elif route == ["start"]:
                self.phone_server.requestStart()
            else:
                self.send_error(404)
                return
            self._send_json(ok=True, **self.phone_server.getHttpState())
        except ValueError as exc:
            self._send_json(400, ok=False, error=str(exc))
        except Exception:
            logger.exception("phone HTTP request failed")
            self._send_json(500, ok=False, error="服务器处理失败")

    def log_message(self, _message_format, *args):
        pass


class PhoneServer(QObject):
    """Token-protected LAN HTTP service for uploading phone photos."""

    imageReceived = Signal(str)
    imagesChanged = Signal()
    startRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._images = []
        self._lock = threading.RLock()
        self._tmp_dir = os.path.join(DATA_DIR, "tmp")
        os.makedirs(self._tmp_dir, exist_ok=True)
        self._running = False
        self._submitted = False
        self._http_server = None
        self._http_thread = None
        self._session_token = ""

    @staticmethod
    def _is_private_ip(ip):
        try:
            parts = [int(part) for part in ip.split(".")]
        except (TypeError, ValueError):
            return False
        if len(parts) != 4:
            return False
        return (
            parts[0] == 10
            or (parts[0] == 192 and parts[1] == 168)
            or (parts[0] == 172 and 16 <= parts[1] <= 31)
        )

    @staticmethod
    def getLanIp():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.settimeout(0.5)
                sock.connect(("8.8.8.8", 80))
                ip = sock.getsockname()[0]
                if PhoneServer._is_private_ip(ip):
                    return ip
        except OSError:
            pass
        candidates = []
        try:
            if sys.platform.startswith("win"):
                result = subprocess.run(
                    ["ipconfig", "/all"], capture_output=True, timeout=5, check=False
                )
                for line in result.stdout.decode("utf-8", errors="ignore").splitlines():
                    if "ipv4" in line.lower() and ":" in line:
                        candidates.append(
                            line.split(":", 1)[1].strip().split("(")[0].strip()
                        )
            elif sys.platform == "darwin":
                for interface in ("en0", "en1", "en2"):
                    result = subprocess.run(
                        ["ipconfig", "getifaddr", interface], capture_output=True,
                        timeout=3, check=False,
                    )
                    if ip := result.stdout.decode("utf-8", errors="ignore").strip():
                        candidates.append(ip)
            else:
                result = subprocess.run(["hostname", "-I"], capture_output=True, timeout=3, check=False)
                candidates.extend(result.stdout.decode("utf-8", errors="ignore").split())
        except (OSError, subprocess.SubprocessError):
            pass
        for ip in candidates:
            if PhoneServer._is_private_ip(ip):
                return ip
        if candidates:
            return candidates[0]
        try:
            ip = socket.gethostbyname(socket.gethostname())
            if ip and not ip.startswith("127."):
                return ip
        except OSError:
            pass
        return "127.0.0.1"

    @staticmethod
    def getNetworkName():
        try:
            if sys.platform.startswith("win"):
                result = subprocess.run(
                    ["netsh", "wlan", "show", "interfaces"],
                    capture_output=True, timeout=5, check=False,
                )
                for line in result.stdout.decode("utf-8", errors="ignore").splitlines():
                    if "SSID" in line and ":" in line and "BSSID" not in line:
                        return line.split(":", 1)[1].strip()
            elif sys.platform == "darwin":
                result = subprocess.run(
                    ["networksetup", "-getairportnetwork", "en0"],
                    capture_output=True, timeout=3, check=False,
                )
                text = result.stdout.decode("utf-8", errors="ignore")
                if ":" in text:
                    return text.split(":", 1)[1].strip()
            else:
                commands = (
                    ["iwgetid", "-r"],
                    ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
                )
                for command in commands:
                    try:
                        result = subprocess.run(
                            command, capture_output=True, timeout=3, check=False
                        )
                    except FileNotFoundError:
                        continue
                    text = result.stdout.decode("utf-8", errors="ignore").strip()
                    if command[0] == "nmcli":
                        for line in text.splitlines():
                            if line.startswith("yes:"):
                                return line.split(":", 1)[1]
                    elif text:
                        return text
        except (OSError, subprocess.SubprocessError):
            pass
        return ""

    def startServer(self):
        if self._running:
            return True
        self.clearImages()
        self._submitted = False
        self._session_token = secrets.token_urlsafe(12)
        try:
            self._http_server = ThreadedHTTPServer(
                ("0.0.0.0", HTTP_PORT), PhoneHTTPRequestHandler  # nosec B104
            )
            self._http_server.phone_server = self
            self._http_thread = threading.Thread(
                target=self._http_server.serve_forever,
                name="lume-phone-http",
                daemon=True,
            )
            self._http_thread.start()
        except OSError:
            logger.warning("could not start phone HTTP server", exc_info=True)
            self._http_server = None
            self._http_thread = None
            self._session_token = ""
            return False
        self._running = True
        return True

    def stopServer(self):
        if self._http_server:
            server, thread = self._http_server, self._http_thread
            self._http_server = None
            self._http_thread = None
            try:
                server.shutdown()
                server.server_close()
            except OSError:
                logger.debug("error while stopping phone server", exc_info=True)
            if thread and thread.is_alive():
                thread.join(timeout=2)
        self._running = False
        self._submitted = False
        self._session_token = ""
        self.clearImages()

    def matchesToken(self, token):
        return bool(self._session_token) and secrets.compare_digest(token, self._session_token)

    def _cleanup_temp_files(self):
        try:
            for name in os.listdir(self._tmp_dir):
                if name.startswith("phone_"):
                    try: os.remove(os.path.join(self._tmp_dir, name))
                    except OSError: pass
        except OSError:
            pass

    def getHttpState(self):
        with self._lock: return {"images":[image["id"] for image in self._images], "submitted":self._submitted}

    def addImage(self, image_id, b64_data):
        if not isinstance(image_id, str) or not IMAGE_ID_PATTERN.fullmatch(image_id): raise ValueError("无效的图片标识")
        if not isinstance(b64_data, str) or not b64_data or len(b64_data) > MAX_IMAGE_BASE64: raise ValueError("图片数据为空或过大")
        try: image_bytes = base64.b64decode(b64_data, validate=True)
        except (ValueError, TypeError) as exc: raise ValueError("图片数据无效") from exc
        if len(image_bytes) > MAX_IMAGE_BYTES or not image_bytes.startswith(b"\xff\xd8\xff"): raise ValueError("仅支持不超过 8 MB 的 JPEG 图片")
        with self._lock:
            if any(image["id"] == image_id for image in self._images): return
            if len(self._images) >= MAX_IMAGES: raise ValueError("一次最多上传 40 张图片")
            if sum(image["size"] for image in self._images) + len(image_bytes) > MAX_TOTAL_IMAGE_BYTES: raise ValueError("图片总大小超过 120 MB")
            file_path = os.path.join(self._tmp_dir, f"phone_{uuid.uuid4().hex}.jpg")
            try:
                with open(file_path, "wb") as image_file: image_file.write(image_bytes)
            except OSError as exc: raise ValueError("图片保存失败") from exc
            self._images.append({"id":image_id, "b64":b64_data, "path":file_path, "size":len(image_bytes)}); self._submitted = False
        self.imageReceived.emit(QUrl.fromLocalFile(file_path).toString())

    def getImageBytes(self, image_id):
        if not IMAGE_ID_PATTERN.fullmatch(image_id): return None
        with self._lock:
            image = next((item for item in self._images if item["id"] == image_id), None)
            if image is None: return None
            try:
                with open(image["path"], "rb") as image_file: return image_file.read()
            except OSError: return None

    @staticmethod
    def getAppIconBytes():
        try:
            with open(APP_ICON_PATH, "rb") as icon_file:
                return icon_file.read()
        except OSError:
            return None

    def requestStart(self):
        with self._lock:
            if not self._images: raise ValueError("请先上传至少一张图片")
            self._submitted = True
        self.startRequested.emit()

    def getImagesJson(self):
        with self._lock: return json.dumps([image["b64"] for image in self._images])

    def getImagePathsJson(self):
        with self._lock: return json.dumps([QUrl.fromLocalFile(image["path"]).toString() for image in self._images])

    def moveImage(self, from_index, to_index):
        if not isinstance(from_index, int) or not isinstance(to_index, int): raise ValueError("无效的图片位置")
        with self._lock:
            size = len(self._images)
            if not (0 <= from_index < size and 0 <= to_index < size): raise ValueError("图片位置超出范围")
            if from_index == to_index: return
            self._images.insert(to_index, self._images.pop(from_index)); self._submitted = False
        self.imagesChanged.emit()

    def deleteImage(self, index):
        if not isinstance(index, int): raise ValueError("无效的图片位置")
        with self._lock:
            if not 0 <= index < len(self._images): raise ValueError("图片位置超出范围")
            removed = self._images.pop(index); self._submitted = False
            try: os.remove(removed["path"])
            except OSError: pass
        self.imagesChanged.emit()

    def clearImages(self):
        with self._lock: self._images.clear(); self._submitted = False; self._cleanup_temp_files()
        self.imagesChanged.emit()

    def getConnectionUrl(self):
        if not self._session_token: return ""
        return f"http://{self.getLanIp()}:{HTTP_PORT}/{self._session_token}"
