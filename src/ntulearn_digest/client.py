"""A tiny Blackboard Learn REST client: standard library only, with retries, paging and downloads."""
from __future__ import annotations

import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__

API = "/learn/api/public/v1"
USER_AGENT = f"ntulearn-digest/{__version__} (+https://github.com/ericwu666666/ntulearn-digest)"


class ApiError(RuntimeError):
    def __init__(self, status: int, url: str, body: str = ""):
        short = url.split("?")[0]
        super().__init__(f"HTTP {status} {short} {body[:160]}".strip())
        self.status = status
        self.url = url
        self.body = body


class Blackboard:
    """Read-only access to ``/learn/api/public/v1`` with a user's bearer token."""

    def __init__(self, base_url: str, token: str, timeout: float = 60, retries: int = 4, backoff: float = 1.5):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.requests = 0

    # ---- low level -------------------------------------------------------
    def url(self, path: str, params: Optional[Dict[str, Any]] = None) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            full = path
        else:
            if not path.startswith("/learn/"):
                path = API + "/" + path.lstrip("/")
            full = self.base_url + path
        if params:
            full += ("&" if "?" in full else "?") + urllib.parse.urlencode(params)
        return full

    def _open(self, url: str, auth: bool = True, timeout: Optional[float] = None):
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json, */*"}
        if auth:
            headers["Authorization"] = "Bearer " + self.token
        last: Exception = ApiError(0, url, "no attempt")
        for attempt in range(self.retries):
            self.requests += 1
            try:
                return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout or self.timeout)
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", "replace")
                except Exception:
                    pass
                finally:
                    e.close()
                if e.code == 429 or e.code >= 500:
                    last = ApiError(e.code, url, body)
                    wait = e.headers.get("Retry-After") if e.headers else None
                    time.sleep(float(wait) if wait and wait.isdigit() else self.backoff * (2 ** attempt))
                    continue
                raise ApiError(e.code, url, body) from None
            except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as e:
                last = e
                time.sleep(self.backoff * (2 ** attempt))
        if isinstance(last, ApiError):
            raise last
        raise ApiError(0, url, str(last))

    # ---- JSON --------------------------------------------------------------
    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        with self._open(self.url(path, params)) as r:
            return json.loads(r.read().decode("utf-8"))

    def get_or_none(self, path: str, params: Optional[Dict[str, Any]] = None, missing=(403, 404)) -> Any:
        try:
            return self.get(path, params)
        except ApiError as e:
            if e.status in missing:
                return None
            raise

    def paged(self, path: str, params: Optional[Dict[str, Any]] = None, missing=(403, 404)) -> List[dict]:
        out: List[dict] = []
        url: Optional[str] = self.url(path, params)
        while url:
            try:
                with self._open(url) as r:
                    data = json.loads(r.read().decode("utf-8"))
            except ApiError as e:
                if e.status in missing and not out:
                    return []
                raise
            out.extend(data.get("results") or [])
            nxt = (data.get("paging") or {}).get("nextPage")
            url = self.url(nxt) if nxt else None
        return out

    # ---- files -------------------------------------------------------------
    def download(self, url: str, dest: Path, auth: bool = True) -> int:
        """Stream a file to ``dest`` via a .part file. Returns the byte count."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        last: Exception = ApiError(0, url, "no attempt")
        for attempt in range(3):
            try:
                n = 0
                with self._open(self.url(url), auth=auth, timeout=300) as r, open(tmp, "wb") as f:
                    while True:
                        chunk = r.read(1 << 16)
                        if not chunk:
                            break
                        f.write(chunk)
                        n += len(chunk)
                if n == 0:
                    raise ApiError(0, url, "empty file")
                os.replace(tmp, dest)
                return n
            except ApiError as e:
                last = e
                if 400 <= e.status < 500:
                    break
            except (OSError, http.client.HTTPException) as e:
                last = e
            time.sleep(self.backoff * (attempt + 1))
        try:
            tmp.unlink()
        except OSError:
            pass
        raise last if isinstance(last, ApiError) else ApiError(0, url, str(last))
