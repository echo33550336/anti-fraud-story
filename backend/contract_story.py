"""one-ticket-v1 剧情服务（契约引擎）。

数据源：contract/story-one-ticket-v1.json（前端导出，唯一数据依据）。
对前端 src/api.js 暴露 5 个端点，返回字段严格按前端 API_CONTRACT.md：
  POST /api/story/start     {story_id} -> {story_id, session_id, node, status}
  POST /api/story/answer    {session_id,node_id,option_id} -> {story_id,response,next_node|ending_id}
  POST /api/story/open      {session_id,node_id,text} -> {story_id,intent,suggested_option_id,need_confirm,message}
  POST /api/story/confirm   {session_id,node_id,option_id,open_text} -> 同 answer
  GET  /api/story/review?session_id=... -> {story_id,ending_id,title,rating,narration,next_step,score,badges}

旧剧情引擎 game/ 原样保留，由 app.py 的 STORY_ENGINE 环境变量切换。
本模块不调用任何外部模型；LLM 意图增强在 P2-b 阶段以可选方式接入。
"""
from __future__ import annotations

import copy
import json
import os
import re
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

STORY_ID = "one-ticket-v1"
SESSION_TTL_SECONDS = 2 * 60 * 60
OPEN_TEXT_MAX_LENGTH = 1200
DEFAULT_CONTRACT_PATH = Path(__file__).resolve().parent / "contract" / "story-one-ticket-v1.json"

_SENSITIVE_PATTERNS = (
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
    re.compile(r"(?<!\d)1[3-9]\d(?:[\s-]?\d{4}){2}(?!\d)"),
    re.compile(r"(?<!\d)(?:\d{17}[\dXx]|\d{15})(?!\d)"),
    re.compile(r"(?<!\d)(?:\d[\s-]?){16,19}(?!\d)"),
)

# 与前端 src/engine.js classify() 完全同序：先匹配者胜。
_INTENT_RULES: Dict[str, List[Tuple[str, "re.Pattern[str]"]]] = {
    "N03": [
        ("CONTINUE", re.compile(r"继续|解释|添加|加微信|听听|联系对方")),
        ("STOP", re.compile(r"官方|总机|剧院|核实|不转|拒绝|拉黑|举报|不加|停止|不信")),
    ],
    "N15": [
        ("DELETE", re.compile(r"删除|删掉|清空|不处理|不想面对")),
        ("SHARE", re.compile(r"分享|提醒朋友|告诉朋友|传播")),
        ("REPORT", re.compile(r"举报|报案|银行|支付平台|止付|保存证据|保留证据")),
        ("VERIFY", re.compile(r"官方|剧院|总机|核实|联系小岚|确认身份")),
    ],
}

_BADGES_VERIFIED = ("E01", "E02", "E05", "E11")
_BADGES_STOPPED = ("E04", "E07", "E08", "E09", "E12", "E14", "E15")
_BADGES_EVIDENCE = ("E12", "E14")
_SCORE_HIGH = ("E01", "E02", "E05", "E11", "E12", "E14")


class ContractError(Exception):
    """HTTP 层可识别的业务错误。"""

    def __init__(self, status_code: int, message: str):
        Exception.__init__(self, message)
        self.status_code = status_code
        self.message = message


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(400, "缺少或无效字段：" + key)
    return value.strip()


def _node_number(node_id: str) -> Optional[int]:
    if isinstance(node_id, str) and len(node_id) == 3 and node_id[0] == "N":
        try:
            return int(node_id[1:])
        except ValueError:
            return None
    return None


def _check_open_text(text: Any) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ContractError(400, "开放回答不能为空")
    text = text.strip()
    if len(text) > OPEN_TEXT_MAX_LENGTH:
        raise ContractError(400, "开放回答过长，请控制在1200字以内")
    if any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS):
        raise ContractError(422, "请删除手机号、身份证号或银行卡号后再提交")
    return text


def _round_half_up(value: float) -> int:
    """对齐 JS Math.round（正数四舍五入）。"""
    return int(value + 0.5)


class Contract:
    """契约剧情配置：加载、索引、校验。"""

    def __init__(self, path: Optional[str] = None):
        source = Path(path or os.getenv("STORY_CONTRACT") or DEFAULT_CONTRACT_PATH)
        if not source.is_file():
            raise RuntimeError("找不到剧情契约文件：%s" % source)
        with source.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        self.story_id: str = data.get("story_id") or ""
        self.nodes: List[Dict[str, Any]] = data.get("nodes") or []
        self.endings: List[Dict[str, Any]] = data.get("endings") or []
        self.free_answers: Dict[str, Dict[str, str]] = data.get("free_answers") or {}
        self.by_id: Dict[str, Dict[str, Any]] = {node["id"]: node for node in self.nodes}
        self.order: Dict[str, int] = {node["id"]: index + 1 for index, node in enumerate(self.nodes)}
        self.ending_by_id: Dict[str, Dict[str, Any]] = {item["id"]: item for item in self.endings}
        self._validate(source)

    def _validate(self, source: Path) -> None:
        if self.story_id != STORY_ID:
            raise RuntimeError("%s 的 story_id=%r，期望 %r" % (source, self.story_id, STORY_ID))
        if len(self.nodes) != 15:
            raise RuntimeError("%s 节点数=%d，期望 15" % (source, len(self.nodes)))
        if len(self.endings) != 16:
            raise RuntimeError("%s 结局数=%d，期望 16" % (source, len(self.endings)))
        for node in self.nodes:
            node_id = node["id"]
            free = bool(node.get("free"))
            if free:
                if node_id not in self.free_answers:
                    raise RuntimeError("自由回答节点 %s 缺少 free_answers 映射" % node_id)
                continue
            for option in node.get("options") or []:
                target = option.get("next")
                if target in self.by_id or target in self.ending_by_id:
                    continue
                raise RuntimeError("节点 %s 选项 %s 指向未知目标 %r" % (node_id, option.get("id"), target))
        for node_id, mapping in self.free_answers.items():
            for option_id, target in mapping.items():
                if target not in self.by_id and target not in self.ending_by_id:
                    raise RuntimeError("free_answers %s/%s 指向未知目标 %r" % (node_id, option_id, target))

    # ---------- 公开视图 ----------
    def public_node(self, node_id: str) -> Dict[str, Any]:
        node = self.by_id.get(node_id)
        if node is None:
            raise ContractError(404, "未知节点：" + node_id)
        beats = node.get("beats") or []
        first = beats[0] if beats else {}
        lines = [{
            "speaker": first.get("who") or node.get("speaker") or "旁白",
            "text": first.get("text") or node.get("scene") or "",
        }]
        return {
            "id": node["id"],
            "act": node.get("act"),
            "act_name": node.get("act_name"),
            "title": node.get("title"),
            "time": node.get("time"),
            "scene": node.get("scene"),
            "lines": lines,
            "prompt": node.get("prompt"),
            "free": bool(node.get("free")),
            "options": [{"id": item.get("id"), "text": item.get("text")} for item in node.get("options") or []],
            "beats": copy.deepcopy(beats),
            "presentation": copy.deepcopy(node.get("presentation") or {}),
            "progress": {"current": self.order.get(node_id, 1), "total": len(self.nodes)},
        }

    def translate_target(self, node_id: str, option_id: str) -> str:
        """把选项解析为下一节点 ID 或结局 ID（非法选项抛 400）。"""
        node = self.by_id.get(node_id)
        if node is None:
            raise ContractError(400, "未知节点：" + node_id)
        if bool(node.get("free")):
            raise ContractError(400, "该节点需要自由回答，请先提交 /open 再 /confirm")
        for option in node.get("options") or []:
            if option.get("id") == option_id:
                return str(option.get("next"))
        raise ContractError(400, "该节点没有此选项")

    def translate_free(self, node_id: str, option_id: str) -> str:
        mapping = self.free_answers.get(node_id)
        if not mapping:
            raise ContractError(400, "当前节点不接受自由回答")
        target = mapping.get(option_id)
        if target is None:
            raise ContractError(400, "自由回答没有该确认选项：" + option_id)
        return target

    def ending(self, ending_id: str) -> Dict[str, Any]:
        item = self.ending_by_id.get(ending_id)
        if item is None:
            raise ContractError(404, "未知结局：" + ending_id)
        return item


class Scoring:
    """前端 src/engine.js demoScore/demoBadges/advance 状态规则的 Python 移植。"""

    @staticmethod
    def initial() -> Dict[str, Any]:
        return {
            "ticket_paid": 0,
            "second_paid": 0,
            "small_paid": 0,
            "invest_paid": 0,
            "verified_official": False,
            "stopped": False,
        }

    @staticmethod
    def apply(state: Dict[str, Any], node_no: int, target: str) -> str:
        """按前端 advance() 的顺序更新状态，返回最终目标（可能被改写为 E15/E16）。"""
        numeric = _node_number(target) if isinstance(target, str) and target[:1] == "N" else None
        if node_no == 3 and numeric == 4:
            state["verified_official"] = True
        if node_no == 4 and numeric == 5:
            state["ticket_paid"] += 900
        if node_no == 5 and numeric == 6:
            state["second_paid"] += 900
        if node_no == 6 and target == "E03":
            state["second_paid"] = 3000 - state["ticket_paid"]
        if node_no == 9 and numeric == 10:
            state["small_paid"] += 128
        if node_no == 10 and numeric == 11:
            state["small_paid"] += 188
        if node_no == 12 and numeric == 13:
            state["invest_paid"] += 3000
        if node_no == 13 and numeric == 14:
            state["invest_paid"] += 500
        if node_no == 14 and target == "E10":
            paid = state["ticket_paid"] + state["second_paid"] + state["small_paid"] + state["invest_paid"]
            state["invest_paid"] += max(0, 5000 - paid)
        if node_no in (13, 14) and numeric == 15:
            state["stopped"] = True

        if node_no == 5 and numeric == 7 and state["verified_official"]:
            target = "E15"
        if node_no == 7 and target == "E04" and state["verified_official"] and state["ticket_paid"]:
            target = "E15"
        if node_no == 14 and target == "E10" and state["second_paid"] >= 900:
            target = "E16"
        return target

    @staticmethod
    def score(ending_id: str, state: Mapping[str, Any]) -> int:
        paid = state["ticket_paid"] + state["second_paid"] + state["small_paid"] + state["invest_paid"]
        score = 100 - min(50, _round_half_up(paid / 100))
        if ending_id in ("E03", "E10", "E16"):
            score -= 18
        if ending_id == "E13":
            score -= 15
        if ending_id in _SCORE_HIGH:
            score = max(score, 82)
        return max(10, min(100, score))

    @staticmethod
    def badges(ending_id: str, state: Mapping[str, Any]) -> List[str]:
        badges: List[str] = []
        if state["verified_official"] or ending_id in _BADGES_VERIFIED:
            badges.append("独立核验")
        if state["stopped"] or ending_id in _BADGES_STOPPED:
            badges.append("及时刹车")
        if state["ticket_paid"] or state["small_paid"] or state["invest_paid"]:
            badges.append("识别代价")
        if ending_id in _BADGES_EVIDENCE:
            badges.append("线索保管员")
        if ending_id == "E14":
            badges.append("安全传递者")
        return badges


class StorySessions:
    def __init__(self, contract: Contract, ttl_seconds: int = SESSION_TTL_SECONDS):
        self._contract = contract
        self._ttl = ttl_seconds
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    # ---------- 内部 ----------
    def _purge(self, now: float) -> None:
        expired = [key for key, item in self._sessions.items() if now - item["last_touch"] > self._ttl]
        for key in expired:
            del self._sessions[key]

    def _get(self, session_id: str) -> Dict[str, Any]:
        if not isinstance(session_id, str) or not session_id:
            raise ContractError(400, "缺少 session_id")
        now = time.monotonic()
        self._purge(now)
        session = self._sessions.get(session_id)
        if session is None:
            raise ContractError(404, "会话不存在或已过期")
        session["last_touch"] = now
        return session

    def _progress(self, session: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            "current": len(session["log"]) + (0 if session["status"] != "ongoing" else 1),
            "total": len(self._contract.nodes),
        }

    def _record(self, session: Dict[str, Any], node_id: str, option_id: str, source: str, intent: Optional[str]) -> str:
        node_no = _node_number(node_id)
        if node_no is None:
            raise ContractError(400, "无效节点：" + node_id)
        if source == "open":
            target = self._contract.translate_free(node_id, option_id)
        else:
            target = self._contract.translate_target(node_id, option_id)
        target = Scoring.apply(session["state"], node_no, target)
        session["log"].append({"node_id": node_id, "option_id": option_id, "source": source, "intent": intent})
        session["pending_open"] = None
        if target in self._contract.ending_by_id:
            session["current"] = None
            session["status"] = "finished"
            session["ending_id"] = target
            return target
        session["current"] = target
        return target

    def _result(self, session: Mapping[str, Any], target: str) -> Dict[str, Any]:
        if session["status"] == "finished":
            return {
                "story_id": STORY_ID,
                "response": "",
                "ending_id": session["ending_id"],
                "status": "finished",
            }
        return {
            "story_id": STORY_ID,
            "response": "",
            "next_node": self._contract.public_node(target),
            "status": "ongoing",
        }

    # ---------- 接口 ----------
    def start(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        requested = payload.get("story_id")
        if requested is not None and requested != STORY_ID:
            raise ContractError(409, "剧情版本不匹配：期望 %s，收到 %r" % (STORY_ID, requested))
        with self._lock:
            now = time.monotonic()
            self._purge(now)
            session_id = uuid.uuid4().hex
            first = self._contract.nodes[0]["id"]
            session: Dict[str, Any] = {
                "session_id": session_id,
                "current": first,
                "status": "ongoing",
                "ending_id": None,
                "log": [],
                "state": Scoring.initial(),
                "open_scores": {},
                "pending_open": None,
                "responses": {},
                "last_touch": now,
            }
            self._sessions[session_id] = session
            return {
                "story_id": STORY_ID,
                "session_id": session_id,
                "node": self._contract.public_node(first),
                "progress": self._progress(session),
                "status": "ongoing",
            }

    def answer(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        session_id = _required_string(payload, "session_id")
        node_id = _required_string(payload, "node_id")
        option_id = _required_string(payload, "option_id")
        with self._lock:
            session = self._get(session_id)
            previous = session["responses"].get(node_id)
            if previous is not None:
                if previous["option_id"] == option_id:
                    return copy.deepcopy(previous["result"])
                raise ContractError(409, "该节点已作答")
            if session["status"] != "ongoing":
                raise ContractError(409, "会话已结束")
            if session["current"] != node_id:
                raise ContractError(409, "节点不匹配；请读取当前会话状态")
            target = self._record(session, node_id, option_id, "closed", None)
            result = self._result(session, target)
            session["responses"][node_id] = {"option_id": option_id, "result": copy.deepcopy(result)}
            return result

    def open_answer(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        session_id = _required_string(payload, "session_id")
        node_id = _required_string(payload, "node_id")
        text = _check_open_text(payload.get("text"))
        with self._lock:
            session = self._get(session_id)
            if session["status"] != "ongoing" or session["current"] != node_id:
                raise ContractError(409, "节点不匹配；请读取当前会话状态")
            node = self._contract.by_id.get(node_id)
            if not node or not node.get("free"):
                raise ContractError(400, "当前节点不接受开放回答")
            suggested = classify_intent(node_id, text)
            evaluation = _evaluate_open(node_id, node.get("prompt") or "", text)
            session["pending_open"] = {"node_id": node_id, "text": text, "suggested_option_id": suggested}
            if evaluation:
                session["open_scores"][node_id] = evaluation
                message = "点评（%d 分）：%s" % (evaluation["score"], evaluation["comment"])
            else:
                session["open_scores"].pop(node_id, None)
                message = "请确认系统理解的行动" if suggested else "意图不清楚，请补充具体行动"
            result = {
                "story_id": STORY_ID,
                "session_id": session_id,
                "node_id": node_id,
                "intent": suggested or "unclear",
                "suggested_option_id": suggested,
                "need_confirm": True,
                "message": message,
            }
            if evaluation:
                result["open_score"] = evaluation["score"]
                result["open_comment"] = evaluation["comment"]
            return result

    def confirm(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        session_id = _required_string(payload, "session_id")
        node_id = _required_string(payload, "node_id")
        option_id = _required_string(payload, "option_id")
        open_text = payload.get("open_text")
        if open_text is not None:
            _check_open_text(open_text)
        with self._lock:
            session = self._get(session_id)
            previous = session["responses"].get(node_id)
            if previous is not None:
                if previous["option_id"] == option_id:
                    return copy.deepcopy(previous["result"])
                raise ContractError(409, "该节点已作答")
            if session["status"] != "ongoing":
                raise ContractError(409, "会话已结束")
            pending = session.get("pending_open")
            if not pending or pending.get("node_id") != node_id:
                raise ContractError(409, "请先提交当前节点的开放回答")
            if session["current"] != node_id:
                raise ContractError(409, "节点不匹配；请读取当前会话状态")
            intent = pending.get("suggested_option_id")
            if intent != option_id:
                intent = "player_selected_alternative"
            target = self._record(session, node_id, option_id, "open", intent)
            result = self._result(session, target)
            session["responses"][node_id] = {"option_id": option_id, "result": copy.deepcopy(result)}
            return result

    def state(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._get(session_id)
            node = self._contract.public_node(session["current"]) if session["current"] else None
            return {
                "story_id": STORY_ID,
                "session_id": session_id,
                "status": session["status"],
                "node": node,
                "progress": self._progress(session),
                "ending_id": session["ending_id"],
                "history": copy.deepcopy(session["log"]),
            }

    def review(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            session = self._get(session_id)
            if session["status"] != "finished" or not session["ending_id"]:
                raise ContractError(409, "演练尚未结束")
            ending_id = session["ending_id"]
            ending = self._contract.ending(ending_id)
            route_score = Scoring.score(ending_id, session["state"])
            open_items = [
                {"node_id": node_id, "score": int(item["score"]), "comment": item["comment"]}
                for node_id, item in session.get("open_scores", {}).items()
            ]
            if open_items:
                average = sum(item["score"] for item in open_items) / len(open_items)
                final_score = _round_half_up(route_score * 0.7 + average * 0.3)
            else:
                final_score = route_score
            narration = ending.get("narration") or ""
            if open_items:
                lines = ["%s：%d 分，%s" % (item["node_id"], item["score"], item["comment"]) for item in open_items]
                narration = (narration + "\n\n【开放回答点评】\n" + "\n".join(lines)).strip()
            return {
                "story_id": STORY_ID,
                "ending_id": ending_id,
                "title": ending.get("title"),
                "rating": ending.get("rating"),
                "narration": narration,
                "next_step": ending.get("next_step"),
                "score": final_score,
                "route_score": route_score,
                "open_average": _round_half_up(
                    sum(item["score"] for item in open_items) / len(open_items)
                ) if open_items else None,
                "open_answers": open_items,
                "badges": Scoring.badges(ending_id, session["state"]),
                "history": copy.deepcopy(session["log"]),
            }


def classify_intent(node_id: str, text: str) -> Optional[str]:
    """规则意图识别（与前端 classify 同序），决定确认按钮的候选行动。"""
    rules = _INTENT_RULES.get(node_id)
    if not rules:
        return None
    for option_id, pattern in rules:
        if pattern.search(text):
            return option_id
    return None


def _evaluate_open(node_id: str, prompt: str, text: str) -> Optional[Dict[str, Any]]:
    """调用 LLM 点评+评分；模块缺失/未启用/任何异常都返回 None（规则模式继续可用）。"""
    try:
        from llm_intent import evaluate_open_answer
    except Exception as exc:  # 缺少模块或依赖：不影响主线
        print("[story] LLM 模块不可用：%s" % exc, file=sys.stderr)
        return None
    try:
        return evaluate_open_answer(node_id, prompt, text)
    except Exception as exc:  # 客户端内部已兜底，这里再保一层
        print("[story] LLM 点评异常：%s" % exc, file=sys.stderr)
        return None


_CONTRACT: Optional[Contract] = None
_SESSIONS: Optional[StorySessions] = None
_INIT_LOCK = threading.Lock()


def _sessions() -> StorySessions:
    global _CONTRACT, _SESSIONS
    if _SESSIONS is None:
        with _INIT_LOCK:
            if _SESSIONS is None:
                _CONTRACT = Contract()
                _SESSIONS = StorySessions(_CONTRACT)
    return _SESSIONS


def handle_post(path: str, payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ContractError(400, "请求体必须是JSON对象")
    store = _sessions()
    if path == "/api/story/start":
        return store.start(payload)
    if path == "/api/story/answer":
        return store.answer(payload)
    if path == "/api/story/open":
        return store.open_answer(payload)
    if path == "/api/story/confirm":
        return store.confirm(payload)
    raise ContractError(404, "Not Found")


def handle_get(path: str, query: Mapping[str, Any]) -> Dict[str, Any]:
    values = query.get("session_id")
    session_id = values[0] if isinstance(values, list) and values else ("" if values is None else str(values))
    store = _sessions()
    if path == "/api/story/state":
        return store.state(session_id)
    if path == "/api/story/review":
        return store.review(session_id)
    raise ContractError(404, "Not Found")


# ---------------- 离线自测（不启动服务、不联网） ----------------
def _self_test() -> None:
    # 离线自测：强制关闭 LLM，避免测试触发真实网络调用与额度消耗
    os.environ["LLM_ENABLED"] = "0"
    contract = Contract()
    store = StorySessions(contract)

    started = store.start({"story_id": STORY_ID})
    assert started["story_id"] == STORY_ID and started["session_id"]
    node = started["node"]
    assert node["id"] == "N01" and node["progress"] == {"current": 1, "total": 15}
    assert node["presentation"] and node["options"], "节点缺少 presentation/options"
    print("[1] start ->", node["id"], node["title"], node["progress"])

    session_id = started["session_id"]
    step = store.answer({"session_id": session_id, "node_id": "N01", "option_id": "A"})
    assert step["next_node"]["id"] == "N02", step
    print("[2] N01 A ->", step["next_node"]["id"])

    step = store.answer({"session_id": session_id, "node_id": "N02", "option_id": "B"})
    assert step["next_node"]["id"] == "N03" and step["next_node"]["free"] is True, step
    print("[3] N02 B ->", step["next_node"]["id"], "free=", step["next_node"]["free"])

    opened = store.open_answer({"session_id": session_id, "node_id": "N03", "text": "我先打剧院官方总机核实一下票务"})
    assert opened["suggested_option_id"] == "STOP", opened
    print("[4] /open ->", opened["intent"], opened["message"])

    ended = store.confirm({"session_id": session_id, "node_id": "N03", "option_id": "STOP", "open_text": "打剧院总机核实"})
    assert ended["ending_id"] == "E01", ended
    print("[5] /confirm ->", ended["ending_id"])

    review = store.review(session_id)
    for field in ("story_id", "ending_id", "title", "rating", "narration", "next_step", "score", "badges"):
        assert field in review, "review 缺少字段：" + field
    assert 10 <= review["score"] <= 100, review
    print("[6] /review ->", review["ending_id"], review["score"], review["badges"], "|", review["title"])

    # 另一条：N02 继续 -> N04 -> N05 转账 -> N06 追加 -> E03（校验分值/状态）
    second = store.start({"story_id": STORY_ID})
    sid = second["session_id"]
    for node_id, option_id, expect in (
        ("N01", "A", "N02"),
        ("N02", "A", "N04"),
        ("N04", "A", "N05"),
        ("N05", "A", "N06"),
    ):
        result = store.answer({"session_id": sid, "node_id": node_id, "option_id": option_id})
        assert result["next_node"]["id"] == expect, (node_id, result)
    ended = store.answer({"session_id": sid, "node_id": "N06", "option_id": "A"})
    assert ended["ending_id"] == "E03", ended
    review2 = store.review(sid)
    print("[7] 转账路径 ->", review2["ending_id"], review2["score"], review2["badges"])

    # 16 个结局的评分/徽章函数必须在合法区间
    for ending_id in contract.ending_by_id:
        score = Scoring.score(ending_id, Scoring.initial())
        assert 10 <= score <= 100, (ending_id, score)
    print("[8] 16 个结局评分计算全部通过")
    print("自测通过：契约加载、节点推进、自由回答、结局、评分、徽章一致")


if __name__ == "__main__":
    _self_test()
