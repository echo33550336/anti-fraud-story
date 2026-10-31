"""反诈剧情演练的标准库 HTTP 服务。

启动：python app.py
默认地址：http://127.0.0.1:5000

同一个进程同时提供剧情 API 和 frontend/ 静态页面，部署时只需要一个服务。
"""

from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))
# 公网部署（Docker / Render / 隧道）时 HOST 为 0.0.0.0，此时放开 Host 校验
PUBLIC = HOST not in ("127.0.0.1", "localhost") or os.getenv("ALLOW_PUBLIC") == "1"
FRONTEND_ROOT = (Path(__file__).resolve().parents[1] / "frontend").resolve()


def log(msg: str) -> None:
    print("[%s] %s" % (threading.current_thread().name, msg), flush=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "AntiScamCoach/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        log(fmt % args)

    # ---------- 工具 ----------
    def _cors_headers(self) -> None:
        """Allow browser clients served from a local development origin."""
        from urllib.parse import urlsplit

        origin = self.headers.get("Origin")
        self.send_header("Vary", "Origin")
        if not origin:
            return
        try:
            parsed = urlsplit(origin)
            allowed = parsed.scheme in ("http", "https") and parsed.hostname in (
                "localhost", "127.0.0.1", "::1"
            )
        except ValueError:
            allowed = False
        if allowed:
            self.send_header("Access-Control-Allow-Origin", origin)

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors_headers()
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, code: int, data: dict) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        if PUBLIC:
            return True
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return host in ("127.0.0.1", "localhost", "")

    def _handle_frontend(self, path: str) -> bool:
        """Serve a file from ``frontend/``; return False when it is not found."""
        from urllib.parse import unquote

        relative = "index.html" if path in ("", "/") else unquote(path.lstrip("/"))
        try:
            target = (FRONTEND_ROOT / relative).resolve()
            if target != FRONTEND_ROOT and FRONTEND_ROOT not in target.parents:
                return False
            if not target.is_file():
                return False
            content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            if content_type.startswith("text/") or content_type in (
                "application/javascript", "application/json", "image/svg+xml"
            ):
                content_type += "; charset=utf-8"
            self._send(200, target.read_bytes(), content_type)
            return True
        except (OSError, ValueError):
            return False

    # ---------- 路由 ----------
    def do_OPTIONS(self) -> None:  # noqa: N802
        if not self._host_ok():
            self._json(403, {"error": "Local access only"})
            return
        self.send_response(204)
        self._cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if not self._host_ok():
            self._json(403, {"error": "Local access only"})
            return
        path = self.path.split("?")[0]
        if path == "/api/health":
            self._json(200, {"ok": True, "service": "story-agent"})
        elif path in ("/api/story/state", "/api/story/review"):
            self._handle_story_get(path)
        elif path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
        elif path.startswith("/api/"):
            self._json(404, {"error": "Not Found"})
        elif not self._handle_frontend(path):
            self._json(404, {"error": "Not Found"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._host_ok():
            self._json(403, {"error": "Local access only"})
            return
        path = self.path.split("?")[0]
        try:
            length = int(self.headers.get("Content-Length") or 0)
            if length > 100_000:
                self._json(413, {"error": "请求体过大"})
                return
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            self._json(400, {"error": "请求格式错误"})
            return

        try:
            if path.startswith("/api/story/"):
                self._handle_story_post(path, payload)
            else:
                self._json(404, {"error": "Not Found"})
        except Exception:
            log("处理异常:\n" + traceback.format_exc())
            self._json(500, {"error": "处理失败，请稍后重试"})

    # ---------- 业务处理 ----------
    def _handle_story_get(self, path: str) -> None:
        from urllib.parse import parse_qs, urlsplit
        from game.sessions import StoryError, handle_get

        try:
            result = handle_get(path, parse_qs(urlsplit(self.path).query))
            self._json(200, result)
        except StoryError as exc:
            self._json(exc.status_code, {"error": exc.message})

    def _handle_story_post(self, path: str, payload: dict) -> None:
        from game.sessions import StoryError, handle_post

        try:
            result = handle_post(path, payload)
            self._json(200, result)
        except StoryError as exc:
            self._json(exc.status_code, {"error": exc.message})

def main() -> None:
    print("=" * 56)
    print("反诈陪练 · Anti-Scam Coach")
    print("=" * 56)
    print("访问地址：http://%s:%d" % (HOST, PORT))
    if PUBLIC:
        print("Host 校验已放开（部署用）")
    print("按 Ctrl+C 停止")
    print("=" * 56)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except OSError as e:
        print("启动失败：%s（端口 %d 可能被占用，可设置 PORT=5001）" % (e, PORT))
        sys.exit(1)
