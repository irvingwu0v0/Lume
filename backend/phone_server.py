import base64
import json
import os
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtNetwork import QHostAddress
from PySide6.QtWebSockets import QWebSocketServer

# Default ports used by both desktop and phone app.
# WS_PORT is used for the real-time WebSocket channel.
# HTTP_PORT serves a mobile web page as a convenience fallback.
WS_PORT = 18923
HTTP_PORT = 18924

# Mobile web interface served on HTTP_PORT.  It is self-contained so any phone
# browser can open it by visiting http://<desktop-ip>:<http-port>/ .
PHONE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Lume 试卷转换</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  background: #f7f7fb;
  color: #1f1f1f;
  max-width: 480px;
  margin: 0 auto;
  padding: 24px 20px 80px;
}
.header { text-align: center; margin-bottom: 24px; }
.header h1 {
  font-size: 36px;
  font-weight: 700;
  background: linear-gradient(90deg, #539dda, #53bcd9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.header p { color: #666; margin-top: 4px; }
.card {
  background: white;
  border-radius: 16px;
  padding: 18px;
  box-shadow: 0 2px 8px rgba(96, 94, 210, 0.08);
  margin-bottom: 16px;
}
.status-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-weight: 600;
}
.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #ffc107;
  animation: pulse 1.5s infinite;
}
.status-dot.connected { background: #28a745; animation: none; }
.status-dot.error { background: #dc3545; animation: none; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
.help-text { color: #666; font-size: 14px; text-align: center; margin-top: 8px; line-height: 1.5; }
.btn {
  width: 100%;
  padding: 14px;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: transform .05s;
  margin-top: 12px;
}
.btn:active { transform: scale(0.98); }
.btn-primary { background: #539dda; color: white; }
.btn-primary:disabled { background: #ccc; }
.btn-secondary { background: #f0f0ff; color: #539dda; }
.camera-btn {
  background: linear-gradient(135deg, #539dda, #53bcd9);
  color: white;
  font-size: 18px;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}
.preview-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-top: 12px;
}
.preview-item {
  aspect-ratio: 3/4;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,.1);
  background: #eee;
}
.preview-item img { width: 100%; height: 100%; object-fit: cover; }
.hidden { display: none !important; }
.complete-screen { text-align: center; padding: 60px 20px; }
.complete-icon {
  width: 80px;
  height: 80px;
  line-height: 80px;
  border-radius: 50%;
  background: #28a745;
  color: white;
  font-size: 40px;
  margin: 0 auto 20px;
}
</style>
</head>
<body>
  <div id="app">
    <div class="header">
      <h1>Lume</h1>
      <p>手机试卷上传</p>
    </div>

    <div class="card">
      <div class="status-row">
        <span class="status-dot" id="status-dot"></span>
        <span id="status-text">连接中...</span>
      </div>
      <p class="help-text" id="status-help">正在连接电脑端...</p>
    </div>

    <div id="camera-section" class="hidden">
      <div class="card">
        <button class="btn camera-btn" id="camera-btn">
          <span>拍照上传</span>
        </button>
        <button class="btn btn-secondary" id="gallery-btn">从相册选择</button>
        <input type="file" accept="image/*" capture="environment" id="camera-input" class="hidden">
        <input type="file" accept="image/*" id="gallery-input" class="hidden" multiple>
      </div>

      <div class="card">
        <div style="font-weight:600; margin-bottom:8px;">已上传预览</div>
        <div class="preview-grid" id="preview-grid"></div>
      </div>

      <button class="btn btn-primary" id="start-btn" disabled>下一步 — 开始处理</button>
    </div>

    <div id="complete-section" class="hidden">
      <div class="card complete-screen">
        <div class="complete-icon">&#10003;</div>
        <h2>已提交</h2>
        <p style="color:#666; margin-top:12px;">请在电脑端继续操作</p>
        <p style="color:#999; font-size:13px; margin-top:8px;">您可以关闭此页面</p>
      </div>
    </div>
  </div>

  <script>
    const WS_PORT = 18923;
    const ip = location.hostname;
    let ws = null;
    let connected = false;
    const images = [];

    const statusDot = document.getElementById('status-dot');
    const statusText = document.getElementById('status-text');
    const statusHelp = document.getElementById('status-help');
    const cameraSection = document.getElementById('camera-section');
    const completeSection = document.getElementById('complete-section');
    const previewGrid = document.getElementById('preview-grid');
    const startBtn = document.getElementById('start-btn');

    function setStatus(text, type, help) {
      statusText.textContent = text;
      statusHelp.textContent = help || '';
      statusDot.classList.remove('connected', 'error');
      if (type) statusDot.classList.add(type);
    }

    function connect() {
      if (ws) { try { ws.close(); } catch (e) {} }
      ws = new WebSocket(`ws://${ip}:${WS_PORT}`);
      ws.onopen = () => {
        connected = true;
        setStatus('连接成功', 'connected', '手机与电脑已建立连接');
        cameraSection.classList.remove('hidden');
      };
      ws.onclose = () => {
        connected = false;
        cameraSection.classList.add('hidden');
        setStatus('连接已断开', 'error', '请检查是否在同一局域网，正在重试...');
        setTimeout(connect, 2000);
      };
      ws.onerror = () => {
        setStatus('连接失败', 'error', '无法连接到电脑，请确认 IP 地址正确');
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'connected') {
            // confirmed by server
          } else if (data.type === 'image_ack') {
            // desktop received the image
          } else if (data.type === 'proceed' || data.type === 'processing_started') {
            showComplete();
          }
        } catch (e) {}
      };
    }

    function showComplete() {
      cameraSection.classList.add('hidden');
      completeSection.classList.remove('hidden');
      setStatus('已提交', 'connected', '请在电脑端继续操作');
    }

    function resizeAndUpload(file) {
      const reader = new FileReader();
      reader.onload = (e) => {
        const img = new Image();
        img.onload = () => {
          const canvas = document.createElement('canvas');
          const MAX = 2500;
          let w = img.width, h = img.height;
          if (w > MAX || h > MAX) {
            if (w > h) { h = Math.round(h * MAX / w); w = MAX; }
            else { w = Math.round(w * MAX / h); h = MAX; }
          }
          canvas.width = w;
          canvas.height = h;
          const ctx = canvas.getContext('2d');
          ctx.fillStyle = '#fff';
          ctx.fillRect(0, 0, w, h);
          ctx.drawImage(img, 0, 0, w, h);
          const dataUrl = canvas.toDataURL('image/jpeg', 0.92);
          const base64 = dataUrl.split(',')[1];
          const id = 'img_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);

          // local preview
          const div = document.createElement('div');
          div.className = 'preview-item';
          const preview = document.createElement('img');
          preview.src = dataUrl;
          div.appendChild(preview);
          previewGrid.appendChild(div);
          images.push({ id, data: base64 });

          startBtn.disabled = false;

          if (connected && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'image', id, data: base64 }));
          }
        };
        img.src = e.target.result;
      };
      reader.readAsDataURL(file);
    }

    document.getElementById('camera-btn').addEventListener('click', () => {
      document.getElementById('camera-input').click();
    });
    document.getElementById('gallery-btn').addEventListener('click', () => {
      document.getElementById('gallery-input').click();
    });
    document.getElementById('camera-input').addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) resizeAndUpload(e.target.files[0]);
      e.target.value = '';
    });
    document.getElementById('gallery-input').addEventListener('change', (e) => {
      if (e.target.files) {
        Array.from(e.target.files).forEach(resizeAndUpload);
      }
      e.target.value = '';
    });
    startBtn.addEventListener('click', () => {
      if (connected && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'start' }));
      }
      showComplete();
    });

    connect();
  </script>
</body>
</html>"""


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class PhoneHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            body = PHONE_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        # Suppress noisy access logs.
        pass


class PhoneServer(QObject):
    """WebSocket server that lets a phone upload photos to the desktop.

    Signals are emitted from the Qt event loop so QML can consume them safely.
    """

    phoneConnected = Signal()
    phoneDisconnected = Signal()
    imageReceived = Signal(str)  # QML-friendly forward-slash file path
    imagesChanged = Signal()     # emitted after move / delete / clear
    startRequested = Signal()    # phone clicked "下一步"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ws_server = None
        self._client = None
        self._images_base64 = []  # base64 strings passed to the vision pipeline
        self._image_files = []     # parallel list of temp file paths
        self._tmp_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "data", "tmp"
        )
        os.makedirs(self._tmp_dir, exist_ok=True)
        self._running = False
        self._http_server = None
        self._http_thread = None

    @staticmethod
    def getLanIp():
        """Return the machine's LAN IP address, preferring private LAN ranges.

        The common socket trick may return a proxy/VPN address (e.g. 198.18.x.x),
        so we fall back to parsing ipconfig and pick a real private IPv4 address.
        """

        def _is_private(ip):
            try:
                parts = [int(p) for p in ip.split(".")]
                if len(parts) != 4:
                    return False
                if parts[0] == 10:
                    return True
                if parts[0] == 172 and 16 <= parts[1] <= 31:
                    return True
                if parts[0] == 192 and parts[1] == 168:
                    return True
            except Exception:
                return False
            return False

        # First try the routing trick.
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if _is_private(ip):
                return ip
        except Exception:
            pass

        # Fallback: parse ipconfig and prefer private addresses.
        try:
            result = subprocess.run(["ipconfig", "/all"], capture_output=True, timeout=5)
            output = result.stdout.decode("utf-8", errors="ignore")
            candidates = []
            for line in output.splitlines():
                lower = line.lower()
                if "ipv4" in lower and ":" in line:
                    raw = line.split(":", 1)[1].strip()
                    # Remove the interface priority marker like "(首选)" if present.
                    raw = raw.split("(")[0].strip()
                    # ipconfig may append the default gateway after the IP; keep only the first token.
                    ip = raw.split()[0]
                    candidates.append(ip)

            # Prefer the first private address.
            for ip in candidates:
                if _is_private(ip):
                    return ip
            if candidates:
                return candidates[0]
        except Exception:
            pass

        return "127.0.0.1"

    @staticmethod
    def getNetworkName():
        """Return the name of the connected Wi-Fi network."""
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True, timeout=5
            )
            output = result.stdout.decode("utf-8", errors="ignore")
            for line in output.split("\n"):
                if "SSID" in line and ":" in line and "BSSID" not in line:
                    return line.split(":", 1)[1].strip()
        except Exception:
            pass
        return ""


    def startServer(self):
        """Start both the WebSocket server and the convenience HTTP server.

        Returns True if the WebSocket server started successfully.
        The HTTP server is optional and will not block on failure.
        """
        # Always clear leftover images from a previous session.
        self.clearImages()

        if self._running:
            return True

        self._ws_server = QWebSocketServer("Lume", QWebSocketServer.NonSecureMode)
        if not self._ws_server.listen(QHostAddress.Any, WS_PORT):
            self._ws_server.deleteLater()
            self._ws_server = None
            return False

        self._ws_server.newConnection.connect(self._on_new_connection)

        # Start HTTP server on a separate thread so the Qt event loop is free.
        try:
            self._http_server = ThreadedHTTPServer(("0.0.0.0", HTTP_PORT), PhoneHTTPRequestHandler)
            self._http_thread = threading.Thread(target=self._http_server.serve_forever, daemon=True)
            self._http_thread.start()
        except Exception:
            self._http_server = None
            self._http_thread = None

        self._running = True
        return True

    def stopServer(self):
        """Stop accepting connections and clean up stored images."""
        if self._client:
            try:
                self._send_to_phone({"type": "disconnect"})
                self._client.close()
            except Exception:
                pass
            self._client = None

        if self._ws_server:
            self._ws_server.close()
            self._ws_server.deleteLater()
            self._ws_server = None

        if self._http_server:
            try:
                self._http_server.shutdown()
            except Exception:
                pass
            self._http_server = None
            self._http_thread = None

        self._running = False
        self._images_base64.clear()
        self._image_files.clear()
        self._cleanup_temp_files()

    def _cleanup_temp_files(self):
        try:
            for name in os.listdir(self._tmp_dir):
                if name.startswith("phone_"):
                    try:
                        os.remove(os.path.join(self._tmp_dir, name))
                    except Exception:
                        pass
        except Exception:
            pass

    def _on_new_connection(self):
        if self._client:
            # Only one phone at a time.
            extra = self._ws_server.nextPendingConnection()
            if extra:
                extra.close()
                extra.deleteLater()
            return

        # New phone session — wipe any leftover images.
        self.clearImages()

        self._client = self._ws_server.nextPendingConnection()
        self._client.textMessageReceived.connect(self._on_text_message)
        self._client.disconnected.connect(self._on_disconnected)
        self._send_to_phone({"type": "connected"})
        self.phoneConnected.emit()

    def _on_disconnected(self):
        sender = self.sender()
        if sender:
            sender.deleteLater()
        self._client = None
        self.phoneDisconnected.emit()

    def _on_text_message(self, message):
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "image":
                image_id = data.get("id", "")
                b64_data = data.get("data", "")
                if not image_id or not b64_data:
                    return

                self._images_base64.append(b64_data)

                # Save a temporary JPEG for QML preview.
                file_name = f"phone_{image_id}.jpg"
                file_path = os.path.join(self._tmp_dir, file_name)
                try:
                    with open(file_path, "wb") as f:
                        f.write(base64.b64decode(b64_data))
                    # Use a proper file:// URL for QML Image sources.
                    qml_url = QUrl.fromLocalFile(file_path).toString()
                    self._image_files.append(file_path)
                    self._send_to_phone({"type": "image_ack", "id": image_id})
                    self.imageReceived.emit(qml_url)
                except Exception:
                    pass

            elif msg_type == "start":
                self.startRequested.emit()

            elif msg_type == "delete":
                # Phone‑initiated delete — do NOT echo back to phone.
                self.deleteImage(data.get("index", -1), sync_to_phone=False)

            elif msg_type == "reorder":
                # Phone‑initiated reorder — do NOT echo back.
                self.moveImage(
                    data.get("from", -1),
                    data.get("to", -1),
                    sync_to_phone=False,
                )

        except Exception as e:
            print(f"PhoneServer: error handling message: {e}")

    def _send_to_phone(self, data):
        if self._client and self._client.isValid():
            try:
                self._client.sendTextMessage(json.dumps(data))
            except Exception:
                pass

    def notifyProceed(self):
        """Tell the phone to move to the completion screen."""
        self._send_to_phone({"type": "proceed"})

    def notifyProcessingStarted(self):
        """Tell the phone that AI generation has started on the desktop."""
        self._send_to_phone({"type": "processing_started"})

    def notifyProcessingComplete(self):
        """Tell the phone that AI generation is finished."""
        self._send_to_phone({"type": "processing_complete"})

    def getImagesJson(self):
        """Return stored images as a JSON array of base64 strings."""
        return json.dumps(self._images_base64)

    def getImagePathsJson(self):
        """Return current temp‑file paths as a JSON array."""
        paths = [QUrl.fromLocalFile(f).toString() for f in self._image_files]
        return json.dumps(paths)

    def getImageCount(self):
        return len(self._images_base64)

    def moveImage(self, from_index: int, to_index: int, sync_to_phone: bool = False):
        """Reorder images.  When *sync_to_phone* is True the phone is notified."""
        size = len(self._images_base64)
        if 0 <= from_index < size and 0 <= to_index < size and from_index != to_index:
            self._images_base64.insert(to_index, self._images_base64.pop(from_index))
            # Only track files if they match in length
            if len(self._image_files) == size:
                self._image_files.insert(to_index, self._image_files.pop(from_index))
            if sync_to_phone:
                self._send_to_phone({"type": "reorder", "from": from_index, "to": to_index})
            self.imagesChanged.emit()

    def deleteImage(self, index: int, sync_to_phone: bool = False):
        """Remove one image by index.  When *sync_to_phone* is True the phone is notified."""
        size = len(self._images_base64)
        if 0 <= index < size:
            self._images_base64.pop(index)
            if index < len(self._image_files):
                old = self._image_files.pop(index)
                try:
                    os.remove(old)
                except Exception:
                    pass
            if sync_to_phone:
                self._send_to_phone({"type": "delete", "index": index})
            self.imagesChanged.emit()

    def clearImages(self):
        self._images_base64.clear()
        self._cleanup_temp_files()
        self._image_files.clear()
        self.imagesChanged.emit()

    def isPhoneConnected(self):
        return self._client is not None and self._client.isValid()

    def isServerRunning(self):
        return self._running

    @property
    def port(self):
        return WS_PORT
