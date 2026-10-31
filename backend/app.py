"""15 步反诈剧情 Demo 的标准库 HTTP 服务。

启动：python app.py
默认地址：http://127.0.0.1:5000

服务提供剧情 API 与前端静态文件；剧情状态与评分由引擎模块处理。

环境变量：PORT / HOST / STORY_ENGINE(contract|legacy) / FRONTEND_DIR / ALLOW_PUBLIC
"""

from __future__ import annotations

import json
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
# 剧情引擎：contract = 前端 one-ticket-v1 契约引擎（默认）；legacy = 旧 R/P 结局引擎
ENGINE = os.getenv("STORY_ENGINE", "contract").strip().lower()


def _story_handlers():
    """按 STORY_ENGINE 返回 (错误类, handle_get, handle_post)，避免启动时强依赖某个引擎。"""
    if ENGINE == "legacy":
        from game.sessions import StoryError, handle_get, handle_post
    else:
        from contract_story import ContractError as StoryError, handle_get, handle_post
    return StoryError, handle_get, handle_post


# 前端静态目录：MIX-V5 布局下默认为 <包根>/frontend；不存在则仅提供 API。
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR") or (Path(__file__).resolve().parent.parent / "frontend"))
_STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".mp3": "audio/mpeg",
    ".woff2": "font/woff2",
    ".md": "text/markdown; charset=utf-8",
}


def log(msg: str) -> None:
    print("[%s] %s" % (threading.current_thread().name, msg), flush=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "AntiScamCoach/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        log(fmt % args)

    # ---------- 工具 ----------
    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
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

    def _serve_static(self, path: str) -> bool:
        """返回前端静态文件；不存在返回 False，越界直接 403。"""
        root = FRONTEND_DIR
        if not root.is_dir():
            return False
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        try:
            root_resolved = root.resolve()
            candidate = (root_resolved / relative).resolve()
            candidate.relative_to(root_resolved)
        except (ValueError, OSError):
            self._json(403, {"error": "路径不合法"})
            return True
        if candidate.is_dir():
            candidate = candidate / "index.html"
        if not candidate.is_file():
            return False
        try:
            data = candidate.read_bytes()
        except OSError:
            return False
        self._send(200, data, _STATIC_TYPES.get(candidate.suffix.lower(), "application/octet-stream"))
        return True

    # ---------- 路由 ----------
    def do_GET(self) -> None:  # noqa: N802
        if not self._host_ok():
            self._json(403, {"error": "Local access only"})
            return
        path = self.path.split("?")[0]
        if path == "/api/health":
            self._json(200, {"ok": True, "service": "story-agent"})
        elif path.startswith("/api/"):
            if path in ("/api/story/state", "/api/story/review"):
                self._handle_story_get(path)
            else:
                self._json(404, {"error": "Not Found"})
        elif path == "/" and not FRONTEND_DIR.is_dir():
            self._json(200, {"ok": True, "service": "story-agent", "api": "/api/story"})
        elif self._serve_static(path):
            return
        elif path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
        else:
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

        StoryError, handle_get, _unused = _story_handlers()
        try:
            result = handle_get(path, parse_qs(urlsplit(self.path).query))
            self._json(200, result)
        except StoryError as exc:
            self._json(exc.status_code, {"error": exc.message})

    def _handle_story_post(self, path: str, payload: dict) -> None:
        StoryError, _unused, handle_post = _story_handlers()

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
    print("剧情引擎：%s" % ("legacy 旧版 R/P 结局" if ENGINE == "legacy" else "contract one-ticket-v1"))
    print("前端目录：%s" % (FRONTEND_DIR if FRONTEND_DIR.is_dir() else "未找到（仅 API 模式）"))
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
