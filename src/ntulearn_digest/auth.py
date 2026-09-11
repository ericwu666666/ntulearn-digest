"""Getting, checking and storing the Blackboard bearer token.

NTULearn keeps a short-lived (about 1 hour) OAuth access token in the browser's
sessionStorage under ``fnds.token.normal``. We never see or store your password:
you copy the token from your own logged-in tab and hand it to this tool.
"""
from __future__ import annotations

import base64
import getpass
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ENV_VAR = "NTULEARN_TOKEN"
STORAGE_KEY = "fnds.token.normal"


class AuthError(RuntimeError):
    pass


def _b64(s: str, urlsafe: bool) -> bytes:
    s = s.strip()
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s) if urlsafe else base64.b64decode(s)


def normalize_token(raw: Optional[str]) -> str:
    """Accept the JWT itself, ``Bearer <jwt>``, a JSON blob, or the raw base64 sessionStorage value."""
    s = (raw or "").strip().strip('"').strip("'")
    if s.lower().startswith("bearer "):
        s = s[7:].strip()
    if s.startswith("eyJ") and s.count(".") == 2:
        return s
    candidates = [s]
    for urlsafe in (False, True):
        try:
            candidates.append(_b64(s, urlsafe).decode("utf-8"))
        except Exception:
            pass
    for c in candidates:
        try:
            data = json.loads(c)
        except Exception:
            continue
        if isinstance(data, dict):
            tok = data.get("accessToken") or data.get("access_token")
            if isinstance(tok, str) and tok:
                return normalize_token(tok)
    raise AuthError(
        "无法识别这段 token。请粘贴 accessToken（以 eyJ 开头），"
        f"或 sessionStorage['{STORAGE_KEY}'] 的原始值。"
    )


def jwt_expiry(token: str) -> Optional[datetime]:
    try:
        payload = json.loads(_b64(token.split(".")[1], urlsafe=True))
        exp = payload.get("exp")
        return datetime.fromtimestamp(int(exp), tz=timezone.utc) if exp else None
    except Exception:
        return None


def minutes_left(token: str, now: Optional[datetime] = None) -> Optional[int]:
    exp = jwt_expiry(token)
    if exp is None:
        return None
    now = now or datetime.now(timezone.utc)
    return int((exp - now).total_seconds() // 60)


def default_token_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home())
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return base / "ntulearn-digest" / "token"


def save_token(token: str, path: Optional[Path] = None) -> Path:
    path = path or default_token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def load_token(explicit: Optional[str] = None, path: Optional[Path] = None) -> str:
    raw = explicit or os.environ.get(ENV_VAR)
    if not raw:
        p = path or default_token_path()
        if p.exists():
            raw = p.read_text(encoding="utf-8")
    if not raw:
        raise AuthError("还没有 token。先运行 `ntulearn auth`，步骤见 README。")
    return normalize_token(raw)


def read_clipboard() -> str:
    commands = []
    if shutil.which("pbpaste"):
        commands.append(["pbpaste"])
    if os.name == "nt":
        commands.append(["powershell", "-NoProfile", "-Command", "Get-Clipboard"])
    if shutil.which("wl-paste"):
        commands.append(["wl-paste", "--no-newline"])
    if shutil.which("xclip"):
        commands.append(["xclip", "-selection", "clipboard", "-o"])
    for cmd in commands:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=True).stdout
            if out.strip():
                return out.strip()
        except Exception:
            continue
    raise AuthError("读不到剪贴板。请改用 `ntulearn auth`，在提示处粘贴 token。")


def prompt_token() -> str:
    return getpass.getpass("粘贴 NTULearn token（输入不会显示），回车确认：")
