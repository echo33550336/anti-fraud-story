"""LLM 开放回答「点评 + 评分」客户端（单次调用，无重试）。

设计边界（重要）：
- 每次 /api/story/open 最多发起 1 次模型请求，**不重试、不循环**；超时/失败/解析失败一律返回 None，由后端退回规则模式。
- 发送内容：节点问题、玩家开放回答文本、评分体系；手机号/身份证/银行卡在入口处已被拦截。
- 配置来源优先级：环境变量 > 同目录 config.json > 内置默认值；评分体系写在 config.json 的 rubric 段，改配置不用改代码。
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
DEFAULT_BASE_URL = "https://api.openai-next.com/v1"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_RUBRIC: Dict[str, Any] = {
    "total": 100,
    "dimensions": [
        {"name": "风险识别", "max": 40, "hint": "是否指出未核实身份、提前转账、陌生链接、脱离平台等风险"},
        {"name": "行动正确性", "max": 30, "hint": "是否采取核实官方渠道、停止联系、保全证据、举报求助等正确动作"},
        {"name": "具体可执行", "max": 20, "hint": "是否给出可落地步骤，而不是空泛表态"},
        {"name": "表达清晰", "max": 10, "hint": "是否说清做什么、为什么"},
    ],
    "instruction": "按维度打分后求和，总分 0-100 的整数；点评不超过 60 个字，先指出优点再给一条改进建议；不评价人格，不预测真实受骗概率。",
}


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() not in ("0", "false", "no", "off", "")


def load_config() -> Dict[str, Any]:
    """读取并合并配置（环境变量优先）。"""
    file_data: Dict[str, Any] = {}
    if CONFIG_PATH.is_file():
        try:
            parsed = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                file_data = parsed
        except (OSError, json.JSONDecodeError) as exc:
            print("[llm] config.json 读取失败：%s" % exc, file=sys.stderr)
    llm_cfg = file_data.get("llm") if isinstance(file_data.get("llm"), dict) else {}
    rubric = file_data.get("rubric") if isinstance(file_data.get("rubric"), dict) else {}
    if not rubric or not rubric.get("dimensions"):
        rubric = DEFAULT_RUBRIC
    base_url = os.getenv("LLM_BASE_URL") or llm_cfg.get("base_url") or DEFAULT_BASE_URL
    model = os.getenv("LLM_MODEL") or llm_cfg.get("model") or DEFAULT_MODEL
    api_key = os.getenv("LLM_API_KEY") or llm_cfg.get("api_key") or ""
    try:
        timeout = float(os.getenv("LLM_TIMEOUT") or llm_cfg.get("timeout_seconds") or 30)
    except (TypeError, ValueError):
        timeout = 30.0
    try:
        max_tokens = int(llm_cfg.get("max_tokens") or 512)
    except (TypeError, ValueError):
        max_tokens = 512
    return {
        "enabled": _truthy(os.getenv("LLM_ENABLED", llm_cfg.get("enabled", True))),
        "base_url": str(base_url).strip().rstrip("/"),
        "model": str(model).strip(),
        "api_key": str(api_key).strip(),
        "timeout_seconds": timeout,
        "max_tokens": max_tokens,
        "temperature": llm_cfg.get("temperature", 0),
        "rubric": rubric,
    }


def _rubric_text(rubric: Dict[str, Any]) -> str:
    lines = []
    for item in rubric.get("dimensions") or []:
        lines.append("- %s（%s 分）：%s" % (item.get("name"), item.get("max"), item.get("hint")))
    return "\n".join(lines)


def _build_messages(node_id: str, prompt: str, text: str, rubric: Dict[str, Any]) -> List[Dict[str, str]]:
    system = (
        "你是反诈演练的开放回答评分员。请严格按给定评分体系评价玩家的行动描述。\n"
        "评分体系（总分 %s）：\n%s\n补充要求：%s\n"
        "只输出一个 JSON 对象，不要 markdown、不要解释。格式："
        '{"score": 整数0-100, "comment": "不超过60字的点评"}'
        % (rubric.get("total", 100), _rubric_text(rubric), rubric.get("instruction", ""))
    )
    user = "节点：%s\n节点问题：%s\n玩家回答：%s" % (node_id, prompt or "（无）", text)
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _extract_json(content: str) -> Optional[Dict[str, Any]]:
    """从模型输出里提取第一个完整 JSON 对象（容忍 markdown 代码块/前后缀）。"""
    text = (content or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def evaluate_open_answer(node_id: str, prompt: str, text: str) -> Optional[Dict[str, Any]]:
    """单次点评+评分调用；任何失败返回 None（调用方退回规则模式）。"""
    cfg = load_config()
    if not cfg["enabled"]:
        return None
    if not cfg["api_key"]:
        print("[llm] 未配置 api_key，跳过模型调用", file=sys.stderr)
        return None
    url = cfg["base_url"] + "/chat/completions"
    payload: Dict[str, Any] = {
        "model": cfg["model"],
        "messages": _build_messages(node_id, prompt, text, cfg["rubric"]),
        "temperature": cfg["temperature"],
        "max_tokens": cfg["max_tokens"],
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            # Cloudflare 会按浏览器签名拦截（error 1010），需带常规 UA
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Authorization": "Bearer " + cfg["api_key"],
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=cfg["timeout_seconds"]) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        print("[llm] HTTP %s 调用失败：%s" % (exc.code, detail), file=sys.stderr)
        return None
    except Exception as exc:  # 超时、DNS、连接重置等：不重试
        print("[llm] 调用异常（%.1fs）：%s" % (time.monotonic() - started, exc), file=sys.stderr)
        return None
    elapsed = time.monotonic() - started
    try:
        data = json.loads(body)
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    except (json.JSONDecodeError, IndexError, AttributeError, TypeError) as exc:
        print("[llm] 响应解析失败：%s" % exc, file=sys.stderr)
        return None
    parsed = _extract_json(content)
    if not parsed:
        print("[llm] %s 未能解析 JSON（%.1fs，原文 %r）" % (node_id, elapsed, str(content)[:200]), file=sys.stderr)
        return None
    try:
        score = int(round(float(parsed.get("score"))))
    except (TypeError, ValueError):
        print("[llm] %s 分数无效：%r" % (node_id, parsed.get("score")), file=sys.stderr)
        return None
    score = max(0, min(100, score))
    comment = str(parsed.get("comment") or "").strip()
    if not comment:
        print("[llm] %s 缺少点评文本" % node_id, file=sys.stderr)
        return None
    print("[llm] %s -> %s 分，%.1fs" % (node_id, score, elapsed), file=sys.stderr)
    return {"score": score, "comment": comment[:200], "model": cfg["model"]}


if __name__ == "__main__":
    config = load_config()
    key_hint = (config["api_key"][:6] + "..." + config["api_key"][-4:]) if config["api_key"] else "缺失"
    print("enabled=%s model=%s base=%s key=%s timeout=%.0fs max_tokens=%d"
          % (config["enabled"], config["model"], config["base_url"], key_hint,
             config["timeout_seconds"], config["max_tokens"]))
    print("评分体系：", " / ".join("%s%s" % (d.get("name"), d.get("max")) for d in config["rubric"].get("dimensions", [])))
    print("单次真实调用验证（不重试）...")
    result = evaluate_open_answer(
        "N03",
        "对方让你不要挂电话，先转 2000 元保证金，你会怎么做？",
        "我先挂断，打剧院官方总机核实票务，不转账也不点链接，把通话记录和号码保存下来。",
    )
    print("点评结果：", json.dumps(result, ensure_ascii=False))
