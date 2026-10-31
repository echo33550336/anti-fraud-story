"""Deterministic domain rules for the 15-node story backend."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .config_loader import load_config
from .scoring import (
    compute_dimension_score,
    compute_frontend_score,
    total_paid,
)

DIMENSION_ORDER = (
    "funds",
    "authorization",
    "privacy",
    "stop_contact",
    "official_help",
    "source_verification",
    "evidence",
)

REFERENCE_SCORES = {
    "R01": 88, "R02": 91,
    "R03": 76, "R04": 80,
    "R05": 64, "R06": 80,
    "R07": 59, "R08": 74,
    "R09": 56, "R10": 68,
    "R11": 70, "R12": 88,
    "R13": 88, "R14": 91,
    "P01": 98, "P02": 100,
}

LOSS_COUNTER_KEYS = frozenset(("ticket_loss", "shop_loss", "recovery_loss"))
FRONTEND_GRAPH_PATH = Path(__file__).resolve().parent / "config" / "story_frontend_graph.json"
FRONTEND_GRAPH_MODEL = "frontend_graph_v1"


def load_frontend_graph_config() -> Dict[str, Any]:
    """Load the additive graph config without changing the legacy default."""
    config = load_config(str(FRONTEND_GRAPH_PATH))
    if config.get("meta", {}).get("model") != FRONTEND_GRAPH_MODEL:
        raise ValueError("frontend graph config has an unexpected model")
    return config


def resolve_graph_node(
    node_id: str, config: Mapping[str, Any]
) -> Dict[str, Any]:
    node = next((item for item in config.get("nodes", []) if item.get("id") == node_id), None)
    if node is None:
        raise ValueError("unknown node: %s" % node_id)
    resolved = dict(node)
    resolved["variant_id"] = "default"
    return resolved


def _graph_condition_matches(condition: Mapping[str, Any], flags: Mapping[str, Any]) -> bool:
    for key, expected in condition.items():
        if key.endswith("_gt"):
            field = key[:-3]
            actual = flags.get(field, 0)
            if isinstance(actual, bool) or not isinstance(actual, int) or actual <= expected:
                return False
        elif flags.get(key, False) != expected:
            return False
    return True


def _graph_option_target(option: Mapping[str, Any], flags: Mapping[str, Any]) -> str:
    for conditional in option.get("conditional_targets", []):
        if _graph_condition_matches(conditional.get("when", {}), flags):
            return conditional["target"]
    return option["target"]


def apply_graph_choice(
    flags: Mapping[str, Any], node_id: str, option_id: str,
    config: Mapping[str, Any],
) -> Dict[str, Any]:
    node = resolve_graph_node(node_id, config)
    if node.get("free"):
        raise ValueError("node requires a free answer")
    option = next((item for item in node["options"] if item.get("id") == option_id), None)
    if option is None:
        raise ValueError("invalid option for %s: %s" % (node_id, option_id))
    updated = dict(flags)
    updated[node_id.lower()] = option_id
    for key, value in option.get("flags", {}).items():
        updated[key] = value
    for key, amount in option.get("increments", {}).items():
        current = updated.get(key, 0)
        if isinstance(current, bool) or not isinstance(current, int) or current < 0:
            raise ValueError("%s must be a non-negative integer" % key)
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("configured increment %s must be a non-negative integer" % key)
        updated[key] = current + amount
    return {
        "flags": updated,
        "target": _graph_option_target(option, updated),
        "response": option.get("response", ""),
    }


def apply_graph_free_answer(
    flags: Mapping[str, Any], node_id: str, text: str,
    config: Mapping[str, Any],
) -> Optional[Dict[str, Any]]:
    node = resolve_graph_node(node_id, config)
    if not node.get("free"):
        raise ValueError("node does not accept a free answer")
    spec = node.get("free_answer", {})
    if len(text.strip()) < spec.get("min_length", 1):
        return None
    normalized = text.casefold()
    for route in spec.get("routes", []):
        any_words = route.get("any_keywords", [])
        all_words = route.get("all_keywords", [])
        none_words = route.get("none_keywords", [])
        if any_words and not any(word.casefold() in normalized for word in any_words):
            continue
        if all_words and not all(word.casefold() in normalized for word in all_words):
            continue
        if any(word.casefold() in normalized for word in none_words):
            continue
        updated = dict(flags)
        updated.update(route.get("set_flags", {}))
        updated[node_id.lower()] = route["target"]
        return {"flags": updated, "target": route["target"], "route": route}
    return None


def build_frontend_review(
    flags: Mapping[str, Any], ending_id: str, history: List[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> Dict[str, Any]:
    ending = next((item for item in config["endings"] if item["id"] == ending_id), None)
    if ending is None:
        raise ValueError("unknown frontend ending: %s" % ending_id)
    scoring_spec = config["scoring"]
    paid = total_paid(flags, scoring_spec["payment_fields"])
    score = compute_frontend_score(flags, ending_id, scoring_spec)

    badges = []
    for badge in scoring_spec["badges"]:
        earned = any(flags.get(key, False) for key in badge.get("any_flags", []))
        earned = earned or ending_id in badge.get("any_endings", [])
        earned = earned or any(flags.get(key, 0) > 0 for key in badge.get("any_paid_fields", []))
        if earned:
            badges.append(badge["name"])
    return {
        "ending_id": ending_id,
        "title": ending["title"],
        "rating": ending["rating"],
        "narration": ending["narration"],
        "note": ending["note"],
        "score": score,
        "badges": badges,
        "paid": {key: flags.get(key, 0) for key in scoring_spec["payment_fields"]},
        "total_paid": paid,
        "history": [dict(item) for item in history],
    }


def _index_config(config: Mapping[str, Any]):
    nodes = {node["id"]: node for node in config["nodes"]}
    variants = {}
    for variant in config["variants"]:
        variants.setdefault(variant["node"], []).append(variant)
    return nodes, variants


_CONFIG = load_config()
_NODES_BY_ID, _VARIANTS_BY_NODE = _index_config(_CONFIG)


def reload_story_config() -> Dict[str, Any]:
    """Reload config explicitly after an operator changes the JSON file."""
    global _CONFIG, _NODES_BY_ID, _VARIANTS_BY_NODE
    _CONFIG = load_config(force_reload=True)
    _NODES_BY_ID, _VARIANTS_BY_NODE = _index_config(_CONFIG)
    return _CONFIG


def _get_config(config: Optional[Mapping[str, Any]] = None) -> Mapping[str, Any]:
    return _CONFIG if config is None else config


def _bool_flag(flags: Mapping[str, Any], key: str) -> bool:
    value = flags.get(key, False)
    if not isinstance(value, bool):
        raise ValueError("%s must be a server-owned boolean" % key)
    return value


def _loss_counter(flags: Mapping[str, Any], key: str) -> int:
    if key not in LOSS_COUNTER_KEYS:
        raise ValueError("unsupported loss counter: %s" % key)
    value = flags.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("%s must be a non-negative integer" % key)
    return value


def _variant_key(node_id: str, variant: Mapping[str, Any]) -> str:
    when = variant.get("when") or {}
    suffix = ",".join(
        "%s=%s" % (key, json.dumps(when[key], ensure_ascii=False, sort_keys=True))
        for key in sorted(when)
    )
    return node_id + ":" + suffix


def resolve_variant(
    node_id: str,
    flags: Mapping[str, Any],
    config: Optional[Mapping[str, Any]] = None,
) -> Optional[Mapping[str, Any]]:
    """Select the unique configured variant whose conditions match server state."""
    current = _get_config(config)
    if config is None:
        candidates = _VARIANTS_BY_NODE.get(node_id, [])
    else:
        candidates = [
            variant for variant in current.get("variants", [])
            if variant.get("node") == node_id
        ]

    matches = [
        variant for variant in candidates
        if all(
            (_loss_counter(flags, key) if key in LOSS_COUNTER_KEYS else flags.get(key)) == value
            for key, value in variant.get("when", {}).items()
        )
    ]
    if len(matches) > 1:
        raise ValueError("ambiguous variants for %s" % node_id)
    return matches[0] if matches else None


def resolve_node(
    node_id: str,
    flags: Mapping[str, Any],
    config: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a node with its matching option and line variant applied."""
    current = _get_config(config)
    if config is None:
        node = _NODES_BY_ID.get(node_id)
    else:
        node = next(
            (item for item in current.get("nodes", []) if item.get("id") == node_id),
            None,
        )
    if node is None:
        raise ValueError("unknown node: %s" % node_id)

    resolved = dict(node)
    variant = resolve_variant(node_id, flags, config)
    if variant is None:
        resolved["variant_id"] = "default"
        return resolved

    for field in ("scene", "lines", "prompt", "options", "ui_option_order"):
        if field in variant:
            resolved[field] = variant[field]
    resolved["variant_id"] = variant.get("id") or _variant_key(node_id, variant)
    return resolved


def apply_choice(
    flags: Mapping[str, Any],
    node_id: str,
    option_id: str,
    config: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Apply the selected option's configured effects to server-owned state.

    Node order and replay protection belong to the session/API layer.
    """
    resolved = resolve_node(node_id, flags, config)
    option = next(
        (item for item in resolved.get("options", []) if item.get("id") == option_id),
        None,
    )
    if option is None:
        raise ValueError("invalid option for %s: %s" % (node_id, option_id))

    effects = option.get("effects") or {}
    effect_flags = effects.get("flags") or {}
    if not isinstance(effect_flags, dict):
        raise ValueError("configured effects.flags must be an object")
    increments = effects.get("increments") or {}
    if not isinstance(increments, dict):
        raise ValueError("configured effects.increments must be an object")

    updated = dict(flags)
    updated[node_id.lower()] = option_id
    for key, value in effect_flags.items():
        if key == "payment_made":
            if not isinstance(value, bool):
                raise ValueError("configured payment_made must be a boolean")
            updated[key] = _bool_flag(updated, key) or value
        else:
            updated[key] = value
    for key, delta in increments.items():
        if key not in LOSS_COUNTER_KEYS:
            raise ValueError("unsupported configured increment: %s" % key)
        if isinstance(delta, bool) or not isinstance(delta, int) or delta < 0:
            raise ValueError("configured increment %s must be a non-negative integer" % key)
        current = updated.get(key, 0)
        if isinstance(current, bool) or not isinstance(current, int) or current < 0:
            raise ValueError("state counter %s must be a non-negative integer" % key)
        updated[key] = current + delta
        if delta:
            updated["payment_made"] = True
    if node_id == "N04" and "n04_scope" in effect_flags:
        updated["source_result"] = effect_flags["n04_scope"]
    if node_id == "N11":
        updated["n11_seen"] = True
    return updated


def compute_dimensions(flags: Mapping[str, Any]) -> Dict[str, int]:
    """Calculate the seven completion dimensions from recorded choices."""
    data_submitted = _bool_flag(flags, "data_submitted")
    auth_granted = _bool_flag(flags, "auth_granted")
    payment_made = _bool_flag(flags, "payment_made")

    if payment_made:
        if flags.get("n11") not in ("A", "B"):
            raise ValueError("payment exposure requires an N11 handling choice")
        funds = 1 if flags["n11"] == "A" else 0
    else:
        funds = 2

    if auth_granted:
        if flags.get("n10") not in ("A", "B"):
            raise ValueError("authorization exposure requires an N10 handling choice")
        authorization = 1 if flags["n10"] == "A" else 0
    else:
        authorization = 2

    if data_submitted:
        if flags.get("n09") not in ("A", "B"):
            raise ValueError("data exposure requires an N09 handling choice")
        privacy = 1 if flags["n09"] == "A" else 0
    else:
        privacy = 2

    n08 = flags.get("n08")
    if n08 not in ("A", "B", "C"):
        raise ValueError("completed story requires an N08 choice")
    stop_contact = {"A": 2, "B": 1, "C": 0}[n08]

    n12 = flags.get("n12")
    if n12 not in ("A", "B", "C"):
        raise ValueError("completed story requires an N12 choice")
    official_help = {"A": 2, "B": 1, "C": 0}[n12]

    n04 = flags.get("n04")
    if n04 not in ("A", "B", "C"):
        raise ValueError("completed story requires an N04 choice")
    source_verification = {"A": 2, "B": 1, "C": 0}[n04]

    n13 = flags.get("n13")
    if n13 not in ("A", "B", "C"):
        raise ValueError("completed story requires an N13 choice")
    evidence = {"A": 2, "B": 1, "C": 0}[n13]

    return {
        "funds": funds,
        "authorization": authorization,
        "privacy": privacy,
        "stop_contact": stop_contact,
        "official_help": official_help,
        "source_verification": source_verification,
        "evidence": evidence,
    }


def compute_score(
    dimensions: Mapping[str, int],
    n15: str,
    config: Optional[Mapping[str, Any]] = None,
) -> int:
    """Return the weighted completion score mapped to an integer from 50 to 100."""
    current = _get_config(config)
    return compute_dimension_score(
        dimensions, n15, current["meta"]["score"], DIMENSION_ORDER
    )


def _ending_condition_value(
    field: str,
    dimensions: Mapping[str, int],
    n15: str,
    flags: Mapping[str, Any],
) -> Any:
    if field in LOSS_COUNTER_KEYS:
        return _loss_counter(flags, field)
    if field == "total_loss":
        return sum(_loss_counter(flags, key) for key in LOSS_COUNTER_KEYS)
    if field == "all_dimensions":
        return all(value == 2 for value in dimensions.values())
    if field == "n15":
        return n15
    if field in {"data_submitted", "auth_granted", "contact_closed", "identity_confirmed"}:
        return _bool_flag(flags, field)
    return flags.get(field)


def _matches_ending_condition(
    condition: Mapping[str, Any],
    dimensions: Mapping[str, int],
    n15: str,
    flags: Mapping[str, Any],
) -> bool:
    if "default" in condition:
        return condition.get("default") is True
    if "all" in condition:
        return all(
            _matches_ending_condition(child, dimensions, n15, flags)
            for child in condition["all"]
        )
    if "any" in condition:
        return any(
            _matches_ending_condition(child, dimensions, n15, flags)
            for child in condition["any"]
        )

    left = _ending_condition_value(condition["field"], dimensions, n15, flags)
    right = condition["value"]
    operator = condition["op"]
    if operator == "eq":
        return left == right
    if operator == "ne":
        return left != right
    if operator == "gt":
        return left > right
    if operator == "gte":
        return left >= right
    if operator == "lt":
        return left < right
    if operator == "lte":
        return left <= right
    raise ValueError("unknown ending comparison operator: %s" % operator)


def route_ending(
    dimensions: Mapping[str, int],
    n15: str,
    config: Optional[Mapping[str, Any]] = None,
    flags: Optional[Mapping[str, Any]] = None,
) -> str:
    """Route a completed story to its primary ending without changing its score."""
    current = _get_config(config)
    order = tuple(current["meta"].get("dimensions", DIMENSION_ORDER))
    if set(dimensions.keys()) != set(order):
        raise ValueError("dimensions must match the seven configured dimensions")
    if n15 not in ("A", "B"):
        raise ValueError("completed story requires an N15 choice")

    if flags is not None:
        endings = sorted(current.get("endings", []), key=lambda item: item.get("priority", 0))
        for ending in endings:
            if _matches_ending_condition(ending.get("when", {}), dimensions, n15, flags):
                return ending["id"]
        raise ValueError("no ending condition matched the completed story")

    # Compatibility for callers that only provide the seven dimensions.
    if all(dimensions[name] == 2 for name in order):
        return "P02" if n15 == "B" else "P01"

    lowest = min(dimensions[name] for name in order)
    if lowest not in (0, 1):
        raise ValueError("dimension levels must be from 0 to 2")
    gap = next(name for name in order if dimensions[name] == lowest)
    index = order.index(gap) * 2 + lowest + 1
    return "R%02d" % index


def collect_badges(
    flags: Mapping[str, Any],
    config: Optional[Mapping[str, Any]] = None,
) -> List[str]:
    """Return configured badges earned by actions; badges never change scoring."""
    current = _get_config(config)
    data_submitted = _bool_flag(flags, "data_submitted")
    auth_granted = _bool_flag(flags, "auth_granted")
    payment_made = _bool_flag(flags, "payment_made")
    earned = {
        "independent_check": flags.get("n04") == "A" and flags.get("n11_seen") is True,
        "authorization_guardian": not auth_granted,
        "timely_brake": flags.get("n08") == "A",
        "regain_control": (
            (data_submitted and flags.get("n09") == "A")
            or (auth_granted and flags.get("n10") == "A")
            or (payment_made and flags.get("n11") == "A")
        ),
        "evidence_keeper": flags.get("n13") == "A",
        "tender_and_firm": flags.get("n14") in ("A", "B", "C", "UNDECIDED"),
        "safe_carrier": flags.get("n15") == "B",
    }
    return [
        badge["id"]
        for badge in current.get("badges", [])
        if earned.get(badge.get("id"), False)
    ]


def build_review(
    flags: Mapping[str, Any],
    config: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Build final results after all 15 nodes have been completed."""
    current = _get_config(config)
    if flags.get("n11_seen") is not True:
        raise ValueError("final review requires the N11 result")
    dimensions = compute_dimensions(flags)
    n15 = flags.get("n15")
    ending = route_ending(dimensions, n15, current, flags=flags)
    return {
        "ending_id": ending,
        "score": compute_score(dimensions, n15, current),
        "dimensions": dimensions,
        "badges": collect_badges(flags, current),
        "romance_choice": flags.get("n14"),
        "witness_path": [
            flags.get("n%02d" % node_id)
            for node_id in range(1, 16)
        ],
    }
