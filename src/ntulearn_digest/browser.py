"""One-click login: open a dedicated Chrome/Edge window, let the user sign in, read the token locally.

We start the user's installed Chromium-based browser with its own profile folder and a
DevTools port bound to 127.0.0.1, wait until NTULearn has put its access token into
sessionStorage, read it over the Chrome DevTools Protocol and close the window.
The password is typed by the user into Microsoft's own login page; we never see it.
Because the profile folder is kept, later runs usually log in without any typing.
"""
from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .auth import default_token_path

TOKEN_JS = (
    "(() => { try { if (location.origin !== %s) return null;"
    " const raw = sessionStorage.getItem('fnds.token.normal'); if (!raw) return null;"
    " const t = JSON.parse(atob(raw)).accessToken; return typeof t === 'string' ? t : null;"
    " } catch (e) { return null; } })()"
)


class BrowserError(RuntimeError):
    pass


def default_profile_dir() -> Path:
    return default_token_path().parent / "browser-profile"


def find_browser(explicit: Optional[str] = None) -> Optional[str]:
    candidates: List[str] = [c for c in (explicit, os.environ.get("NTULEARN_BROWSER")) if c]
    if sys.platform == "darwin":
        for app in ("Google Chrome", "Microsoft Edge", "Chromium", "Brave Browser"):
            for root in ("/Applications", str(Path.home() / "Applications")):
                candidates.append(f"{root}/{app}.app/Contents/MacOS/{app}")
    elif os.name == "nt":
        roots = [os.environ.get(k) for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
        for root in filter(None, roots):
            candidates += [os.path.join(root, "Google", "Chrome", "Application", "chrome.exe"),
                           os.path.join(root, "Microsoft", "Edge", "Application", "msedge.exe"),
                           os.path.join(root, "BraveSoftware", "Brave-Browser", "Application", "brave.exe")]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                 "microsoft-edge", "microsoft-edge-stable", "brave-browser"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


class WebSocket:
    """Just enough RFC 6455 to talk to Chrome DevTools on localhost."""

    def __init__(self, url: str, timeout: float = 10):
        u = urllib.parse.urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f"GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n")
        self.sock.sendall(request.encode())
        head = b""
        while not head.endswith(b"\r\n\r\n"):
            chunk = self.sock.recv(1)
            if not chunk:
                raise ConnectionError("DevTools closed the connection")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError(head.split(b"\r\n", 1)[0].decode("latin-1"))
        self.next_id = 0

    def _read(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("DevTools closed the connection")
            buf += chunk
        return buf

    def _send(self, opcode: int, payload: bytes) -> None:
        header = bytearray([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += n.to_bytes(2, "big")
        else:
            header.append(0x80 | 127)
            header += n.to_bytes(8, "big")
        mask = os.urandom(4)
        self.sock.sendall(bytes(header) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def recv(self) -> str:
        parts: List[bytes] = []
        while True:
            b1, b2 = self._read(2)
            n = b2 & 0x7F
            if n == 126:
                n = int.from_bytes(self._read(2), "big")
            elif n == 127:
                n = int.from_bytes(self._read(8), "big")
            mask = self._read(4) if b2 & 0x80 else None
            data = self._read(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            opcode = b1 & 0x0F
            if opcode == 0x9:
                self._send(0xA, data)
                continue
            if opcode == 0x8:
                raise ConnectionError("DevTools closed the connection")
            if opcode in (0x1, 0x2, 0x0):
                parts.append(data)
                if b1 & 0x80:
                    return b"".join(parts).decode("utf-8")

    def call(self, method: str, params: Optional[dict] = None) -> dict:
        self.next_id += 1
        self._send(0x1, json.dumps({"id": self.next_id, "method": method, "params": params or {}}).encode())
        while True:
            msg = json.loads(self.recv())
            if msg.get("id") == self.next_id:
                return msg

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


def _get_json(url: str, timeout: float = 2) -> object:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class BrowserSession:
    def __init__(self, executable: str, profile: Path, url: str, headless: bool = False):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        profile.mkdir(parents=True, exist_ok=True)
        args = [executable, f"--remote-debugging-port={self.port}", f"--user-data-dir={profile}",
                "--no-first-run", "--no-default-browser-check", "--disable-default-apps", "--new-window"]
        if headless:
            args.append("--headless=new")
        args += shlex.split(os.environ.get("NTULEARN_BROWSER_ARGS", ""))
        args.append(url)
        self.devtools = f"http://127.0.0.1:{self.port}"
        self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def wait_ready(self, timeout: float = 40) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                _get_json(self.devtools + "/json/version")
                return
            except Exception:
                if self.proc.poll() is not None:
                    raise BrowserError("浏览器启动后马上退出了。如果之前的 ntulearn 登录窗口还开着，先把它关掉再试。")
                time.sleep(0.25)
        raise BrowserError("浏览器没有响应。可以用 --browser 指定 Chrome 或 Edge 的路径。")

    def pages(self) -> List[dict]:
        return [t for t in _get_json(self.devtools + "/json/list") if t.get("type") == "page"]  # type: ignore[union-attr]

    def close(self) -> None:
        try:
            info = _get_json(self.devtools + "/json/version")
            ws = WebSocket(info["webSocketDebuggerUrl"], timeout=3)  # type: ignore[index]
            try:
                ws.call("Browser.close")
            finally:
                ws.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()


def capture_token(base_url: str, browser: Optional[str] = None, profile: Optional[Path] = None,
                  headless: bool = False, timeout: float = 300, log: Callable[[str], None] = print) -> str:
    executable = find_browser(browser)
    if not executable:
        raise BrowserError("没找到 Chrome、Edge 或 Chromium。请安装 Chrome，或者改用 `ntulearn auth` 手动粘贴 token。")
    u = urllib.parse.urlparse(base_url)
    origin = f"{u.scheme}://{u.netloc}"
    session = BrowserSession(executable, profile or default_profile_dir(), base_url.rstrip("/") + "/ultra/course", headless)
    sockets: Dict[str, WebSocket] = {}
    try:
        session.wait_ready()
        if not headless:
            log("已打开一个浏览器窗口。第一次使用请在里面正常登录 NTULearn，登录成功后窗口会自动关闭。")
        expression = TOKEN_JS % json.dumps(origin)
        deadline = time.time() + timeout
        last_host = None
        while time.time() < deadline:
            if session.proc.poll() is not None:
                raise BrowserError("浏览器窗口被关掉了，登录没有完成。")
            try:
                pages = session.pages()
            except Exception:
                pages = []
            host = urllib.parse.urlparse(pages[0].get("url", "")).hostname if pages else None
            if host and host != last_host:
                log(f"等待登录，当前页面：{host}")
                last_host = host
            for page in pages:
                pid, ws_url = page.get("id"), page.get("webSocketDebuggerUrl")
                if not pid or not ws_url:
                    continue
                try:
                    ws = sockets.get(pid) or WebSocket(ws_url)
                    sockets[pid] = ws
                    reply = ws.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
                    value = ((reply.get("result") or {}).get("result") or {}).get("value")
                    if isinstance(value, str) and value.count(".") == 2:
                        return value
                except Exception:
                    stale = sockets.pop(pid, None)
                    if stale:
                        stale.close()
            time.sleep(1.5)
        raise BrowserError(f"{int(timeout)} 秒内没有完成登录。重新运行就行。")
    finally:
        for ws in sockets.values():
            ws.close()
        session.close()
