"""A tiny fake NTULearn: a login page that sets the sessionStorage token, plus the REST endpoints we use."""
import base64
import html
import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API = "/learn/api/public/v1/"


def fake_jwt(exp: int) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{enc({'alg': 'none'})}.{enc({'exp': exp, 'sub': 'u1'})}.sig"


class MockNTULearn:
    def __init__(self, login_delay_ms: int = 800):
        self.token = fake_jwt(int(time.time()) + 3600)
        self.login_delay_ms = login_delay_ms
        self.hits = []
        self.failed_once = set()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.base = f"http://127.0.0.1:{self.httpd.server_port}"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()

    def routes(self):
        body = ('<p>The midterm is on 21 Sep and is worth 20%.</p>'
                f'<a href="#" data-bbfile="{html.escape(json.dumps({"linkName": "Embedded.pdf", "resourceUrl": self.base + "/signed/embedded.pdf?sig=abc"}), quote=True)}">x</a>')
        return {
            "users/me": {"id": "u1", "userName": "demo", "name": {"given": "Demo"}},
            "courses/_1_1/users/u1": {"userId": "u1"},
            "courses/_1_1/contents": {"results": [{"id": "f1", "title": "Week 1", "hasChildren": True, "contentHandler": {"id": "resource/x-bb-folder"}}]},
            "courses/_1_1/contents/f1/children": {"results": [
                {"id": "file1", "title": "Slides", "contentHandler": {"id": "resource/x-bb-file"}},
                {"id": "doc1", "title": "Course Info", "hasChildren": True, "contentHandler": {"id": "resource/x-bb-document"}}]},
            "courses/_1_1/contents/file1/attachments": {"results": [{"id": "att1", "fileName": "Lecture 1.pdf"}]},
            "courses/_1_1/contents/doc1": {"id": "doc1"},
            "courses/_1_1/contents/doc1/attachments": {"results": []},
            "courses/_1_1/contents/doc1/children": {"results": [{"id": "body1", "title": "ultraDocumentBody", "contentHandler": {"id": "resource/x-bb-document"}}]},
            "courses/_1_1/contents/body1": {"id": "body1", "body": body},
            "courses/_1_1/gradebook/columns": {"results": [{"id": "q1", "name": "Quiz 1", "grading": {"due": "2026-09-20T15:59:00.000Z"}, "score": {"possible": 100}}]},
            "courses/_1_1/gradebook/users/u1": {"results": [{"columnId": "q1", "status": "NeedsGrading"}]},
            "courses/_1_1/announcements": {"results": [{"id": "an1", "title": "Welcome", "created": "2026-08-01T01:00:00.000Z", "body": "<p>Hello</p>"}]},
        }

    def _handler(self):
        mock = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status, payload, ctype="application/json", headers=None):
                data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                url = urllib.parse.urlparse(self.path)
                query = urllib.parse.parse_qs(url.query)
                auth = self.headers.get("Authorization")
                mock.hits.append((url.path, auth is not None))
                if url.path == "/ultra/course":
                    storage = base64.b64encode(json.dumps({"accessToken": mock.token}).encode()).decode()
                    page = (f"<!doctype html><title>Mock NTULearn</title><p>signing in...</p><script>setTimeout(function(){{"
                            f"sessionStorage.setItem('fnds.token.normal', '{storage}');document.body.textContent='ok';}}, {mock.login_delay_ms});</script>")
                    return self._send(200, page.encode(), "text/html; charset=utf-8")
                if url.path == "/signed/embedded.pdf":
                    return self._send(200, b"%PDF-1.4 embedded", "application/pdf")
                if url.path == "/bbcswebdav/xid-1":
                    if auth != f"Bearer {mock.token}":
                        return self._send(401, {"message": "no auth on redirect"})
                    return self._send(200, b"%PDF-1.4 lecture", "application/pdf")
                if not url.path.startswith(API):
                    return self._send(404, {"message": "not found"})
                if auth != f"Bearer {mock.token}":
                    return self._send(401, {"status": 401, "message": "Bearer token is invalid"})
                rest = url.path[len(API):]
                if rest == "courses/_1_1/announcements" and rest not in mock.failed_once:
                    mock.failed_once.add(rest)
                    return self._send(503, {"message": "try again"})
                if rest == "users/u1/courses":
                    if query.get("offset") == ["1"]:
                        return self._send(200, {"results": [{"course": {"id": "_2_1", "courseId": "26S1-ZX2002-LEC", "name": "ZX2002-DROPPED Main"}}]})
                    return self._send(200, {"results": [{"course": {"id": "_1_1", "courseId": "26S1-ZX1001-LEC", "name": "ZX1001-MOCK COURSE AY26/27 Sem 1 Main"}}],
                                            "paging": {"nextPage": API + "users/u1/courses?offset=1&limit=200&expand=course"}})
                if rest == "courses/_1_1/contents/file1/attachments/att1/download":
                    return self._send(302, b"", "text/plain", {"Location": "/bbcswebdav/xid-1"})
                table = mock.routes()
                if rest in table:
                    return self._send(200, table[rest])
                return self._send(404, {"status": 404, "message": "Membership item not found"})

        return Handler
