"""In-memory story sessions and deterministic open-answer mapping."""
from __future__ import annotations

import copy
import re
import threading
import time
import uuid
from typing import Any, Dict, Mapping, Optional

from . import engine

SESSION_TTL_SECONDS = 2 * 60 * 60
OPEN_TEXT_MAX_LENGTH = 1200

_SENSITIVE_PATTERNS = (
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)1[3-9]\d(?:[\s-]?\d{4}){2}(?!\d)"),
    re.compile(r"(?<!\d)(?:\d{17}[\dXx]|\d{15})(?!\d)"),
    re.compile(r"(?<!\d)(?:\d[\s-]?){16,19}(?!\d)"),
)

_INTENT_RULES = {
    "N12": {
        "A": ("complete_official_report", ("完整说明", "说明完整", "把经过说清", "正规入口完整")),
        "B": ("brief_official_report", ("只说", "一句话", "简单说", "赠票出问题")),
        "C": ("unverified_help", ("陌生入口", "陌生消息", "快速解决", "快速处理")),
    },
    "N13": {
        "A": ("organized_redacted_evidence", ("按时间整理", "整理时间", "来源和操作", "遮蔽隐私", "脱敏")),
        "B": ("partial_screenshot", ("一张截图", "只留一张", "截图")),
        "C": ("discard_evidence", ("清空记录", "删除记录", "清空", "删除")),
    },
    "N14": {
        "A": ("accept_invitation", ("愿意去", "我愿意", "接受邀请", "一起去", "去赴约")),
        "B": ("defer_invitation", ("改天", "暂缓", "还没想好", "再考虑", "晚点回答", "不确定")),
        "C": ("decline_invitation", ("拒绝", "不愿意", "不喜欢", "没感觉", "不想赴约")),
    },
}


class StoryError(Exception):
    def __init__(self, status_code: int, message: str):
        Exception.__init__(self, message)
        self.status_code = status_code
        self.message = message


def _is_sensitive(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS)


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise StoryError(400, "缺少或无效字段：" + key)
    return value.strip()


def _map_open_intent(node_id: str, text: str) -> Dict[str, Any]:
    normalized = text.casefold()
    matches = []
    rules = _INTENT_RULES.get(node_id, {})
    for option_id, (intent, keywords) in rules.items():
        for keyword in keywords:
            if keyword.casefold() in normalized:
                matches.append((option_id, intent, keyword))
                break

    option_ids = set(item[0] for item in matches)
    if len(option_ids) == 1:
        option_id, intent, keyword = matches[0]
        return {
            "intent": intent,
            "suggested_option_id": option_id,
            "evidence_quote": keyword,
            "confidence": None,
            "confidence_status": "rule_match_not_calibrated",
            "need_confirm": True,
        }
    return {
        "intent": "unclear" if not matches else "mixed",
        "suggested_option_id": None,
        "evidence_quote": None,
        "confidence": None,
        "confidence_status": "uncertain",
        "need_confirm": True,
    }


class StorySessions:
    def __init__(self, ttl_seconds: int = SESSION_TTL_SECONDS):
        self._ttl_seconds = ttl_seconds
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def _purge_expired(self, now: float) -> None:
        expired = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session["last_touch"] > self._ttl_seconds
        ]
        for session_id in expired:
            del self._sessions[session_id]

    def _get_session(self, session_id: str) -> Dict[str, Any]:
        if not isinstance(session_id, str) or not session_id:
            raise StoryError(400, "缺少 session_id")
        now = time.monotonic()
        self._purge_expired(now)
        session = self._sessions.get(session_id)
        if session is None:
            raise StoryError(404, "会话不存在或已过期")
        session["last_touch"] = now
        return session

    @staticmethod
    def _progress(session: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "completed": len(session["log"]),
            "total": 15,
            "current_node": session["current_node"],
        }

    @staticmethod
    def _public_node(session: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        node_id = session.get("current_node")
        if node_id is None:
            return None
        node = engine.resolve_node(node_id, session["flags"])
        return {
            "id": node["id"],
            "act": node["act"],
            "time": node["time"],
            "scene": node["scene"],
            "lines": node.get("lines", []),
            "prompt": node.get("prompt"),
            "ui_option_order": node["ui_option_order"],
            "options": [
                {"id": option["id"], "text": option["text"], "response": option["response"]}
                for option in node["options"]
            ],
            "variant_id": node["variant_id"],
        }

    def start(self) -> Dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            self._purge_expired(now)
            session_id = uuid.uuid4().hex
            session = {
                "session_id": session_id,
                "current_node": "N01",
                "flags": {},
                "log": [],
                "status": "ongoing",
                "last_touch": now,
                "responses": {},
                "pending_open": None,
                "stop_review": None,
                "final_review": None,
            }
            self._sessions[session_id] = session
            return {
                "session_id": session_id,
                "node": self._public_node(session),
                "progress": self._progress(session),
                "status": "ongoing",
            }

    def _answer_locked(
        self,
        session: Dict[str, Any],
        node_id: str,
        option_id: str,
        source: str = "closed",
        intent: Optional[str] = None,
    ) -> Dict[str, Any]:
        previous = session["responses"].get(node_id)
        if previous is not None:
            if previous["option_id"] == option_id:
                return copy.deepcopy(previous["result"])
            raise StoryError(409, "该节点已作答")

        if session["status"] != "ongoing":
            raise StoryError(409, "会话已结束")
        if session["current_node"] != node_id:
            raise StoryError(409, "节点不匹配；请读取当前会话状态")

        node = engine.resolve_node(node_id, session["flags"])
        option = next(
            (item for item in node["options"] if item.get("id") == option_id),
            None,
        )
        if option is None:
            raise StoryError(400, "该节点没有此选项")

        new_flags = engine.apply_choice(session["flags"], node_id, option_id)
        session["flags"] = new_flags
        session["log"].append({
            "node": node_id,
            "variant": node["variant_id"],
            "option": option_id,
            "source": source,
            "intent": intent,
        })
        session["pending_open"] = None

        next_id = node.get("next")
        if next_id == "REVIEW":
            session["current_node"] = None
            session["status"] = "finished"
            session["final_review"] = engine.build_review(new_flags)
            event = "finished"
        else:
            session["current_node"] = next_id
            event = "choice_recorded"

        result = {
            "session_id": session["session_id"],
            "response": option["response"],
            "next_node": self._public_node(session),
            "progress": self._progress(session),
            "status": session["status"],
            "event": event,
        }
        session["responses"][node_id] = {
            "option_id": option_id,
            "result": copy.deepcopy(result),
        }
        return result

    def answer(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        session_id = _required_string(payload, "session_id")
        node_id = _required_string(payload, "node_id")
        option_id = _required_string(payload, "option_id")
        with self._lock:
            session = self._get_session(session_id)
            return self._answer_locked(session, node_id, option_id)

    def open_answer(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        session_id = _required_string(payload, "session_id")
        node_id = _required_string(payload, "node_id")
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise StoryError(400, "开放回答不能为空")
        text = text.strip()
        if len(text) > OPEN_TEXT_MAX_LENGTH:
            raise StoryError(400, "开放回答过长，请控制在1200字以内")
        if _is_sensitive(text):
            raise StoryError(422, "请删除手机号、身份证号或银行卡号后再提交")

        with self._lock:
            session = self._get_session(session_id)
            if session["status"] != "ongoing" or session["current_node"] != node_id:
                raise StoryError(409, "节点不匹配；请读取当前会话状态")
            node = engine.resolve_node(node_id, session["flags"])
            open_spec = node.get("open_answer") or {}
            if not open_spec.get("enabled"):
                raise StoryError(400, "当前节点不接受开放回答")

            mapped = _map_open_intent(node_id, text)
            session["pending_open"] = {
                "node_id": node_id,
                "intent": mapped["intent"],
                "suggested_option_id": mapped["suggested_option_id"],
                "evidence_quote": mapped["evidence_quote"],
                "confidence_status": mapped["confidence_status"],
            }
            result = dict(mapped)
            result["session_id"] = session_id
            result["node_id"] = node_id
            return result

    def confirm(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        session_id = _required_string(payload, "session_id")
        node_id = _required_string(payload, "node_id")
        option_id = _required_string(payload, "option_id")
        open_text = payload.get("open_text")
        if open_text is not None:
            if not isinstance(open_text, str):
                raise StoryError(400, "open_text 必须是字符串")
            if len(open_text) > OPEN_TEXT_MAX_LENGTH:
                raise StoryError(400, "开放回答过长，请控制在1200字以内")
            if _is_sensitive(open_text):
                raise StoryError(422, "请删除手机号、身份证号或银行卡号后再提交")

        with self._lock:
            session = self._get_session(session_id)
            previous = session["responses"].get(node_id)
            if previous is not None:
                if previous["option_id"] == option_id:
                    return copy.deepcopy(previous["result"])
                raise StoryError(409, "该节点已作答")

            pending = session.get("pending_open")
            if pending is None or pending.get("node_id") != node_id:
                raise StoryError(409, "请先提交当前节点的开放回答")
            if session["current_node"] != node_id:
                raise StoryError(409, "节点不匹配；请读取当前会话状态")
            intent = pending.get("intent")
            if pending.get("suggested_option_id") != option_id:
                intent = "player_selected_alternative"
            return self._answer_locked(
                session,
                node_id,
                option_id,
                source="open",
                intent=intent,
            )

    def state(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._get_session(session_id)
            return {
                "session_id": session_id,
                "status": session["status"],
                "node": self._public_node(session),
                "progress": self._progress(session),
            }

    def stop(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        session_id = _required_string(payload, "session_id")
        with self._lock:
            session = self._get_session(session_id)
            if session["status"] == "finished":
                return {"review": copy.deepcopy(session["final_review"])}
            if session["status"] == "stopped":
                return {"review": copy.deepcopy(session["stop_review"])}

            session["status"] = "stopped"
            session["current_node"] = None
            session["pending_open"] = None
            session["stop_review"] = {
                "status": "stopped",
                "completed": len(session["log"]),
                "total": 15,
                "message": "演练未走完15步；以下只复盘已发生的选择。",
                "choices": copy.deepcopy(session["log"]),
            }
            return {"review": copy.deepcopy(session["stop_review"])}

    def review(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._get_session(session_id)
            if session["status"] == "finished":
                result = copy.deepcopy(session["final_review"])
                result["status"] = "finished"
                return result
            if session["status"] == "stopped":
                return copy.deepcopy(session["stop_review"])
            raise StoryError(409, "演练尚未结束")


_STORE = StorySessions()


def handle_post(path: str, payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise StoryError(400, "请求体必须是JSON对象")
    if path == "/api/story/start":
        return _STORE.start()
    if path == "/api/story/answer":
        return _STORE.answer(payload)
    if path == "/api/story/open":
        return _STORE.open_answer(payload)
    if path == "/api/story/confirm":
        return _STORE.confirm(payload)
    if path == "/api/story/stop":
        return _STORE.stop(payload)
    raise StoryError(404, "Not Found")


def handle_get(path: str, query: Mapping[str, Any]) -> Dict[str, Any]:
    values = query.get("session_id")
    if isinstance(values, list):
        session_id = values[0] if values else ""
    else:
        session_id = values
    if path == "/api/story/state":
        return _STORE.state(session_id)
    if path == "/api/story/review":
        return _STORE.review(session_id)
    raise StoryError(404, "Not Found")
