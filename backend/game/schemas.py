"""Structural and semantic validation for the story configuration."""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

NODE_IDS = tuple("N%02d" % i for i in range(1, 16))
ENDING_IDS = tuple(
    ["R%02d" % i for i in range(1, 15)] + ["P01", "P02"]
)
GRAPH_MODEL = "frontend_graph_v1"
FRONTEND_ENDING_IDS = tuple("E%02d" % i for i in range(1, 17))
BADGE_IDS = (
    "independent_check",
    "authorization_guardian",
    "timely_brake",
    "regain_control",
    "evidence_keeper",
    "tender_and_firm",
    "safe_carrier",
)
DIMENSION_WEIGHTS = {
    "funds": 21,
    "authorization": 19,
    "privacy": 17,
    "stop_contact": 15,
    "official_help": 13,
    "source_verification": 11,
    "evidence": 9,
}
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
ALLOWED_STATE_FLAGS = {
    "identity_confirmed", "contact_closed", "data_submitted",
    "auth_granted", "payment_made", "source_result", "n04",
    "n04_scope", "n05", "n06", "n07", "n08", "n09", "n10",
    "n11", "n11_seen", "n12", "n13", "n14", "n15",
    "ticket_loss", "shop_loss", "recovery_loss",
}
ALLOWED_INCREMENT_KEYS = {"ticket_loss", "shop_loss", "recovery_loss"}
ALLOWED_VARIANT_CONDITIONS = ALLOWED_STATE_FLAGS
ALLOWED_ENDING_CONDITION_KEYS = {"all", "any", "default"}
ENDING_CONDITION_FIELDS = {
    "ticket_loss", "shop_loss", "recovery_loss", "total_loss",
    "all_dimensions", "data_submitted", "auth_granted",
    "identity_confirmed", "contact_closed", "n04", "n05", "n12",
    "n14", "n15",
}
ENDING_CONDITION_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte"}
NUMERIC_ENDING_FIELDS = {
    "ticket_loss", "shop_loss", "recovery_loss", "total_loss",
}
BOOLEAN_ENDING_FIELDS = {
    "all_dimensions", "data_submitted", "auth_granted",
    "identity_confirmed", "contact_closed",
}
CHOICE_ENDING_VALUES = {
    "n04": {"A", "B", "C"},
    "n05": {"A", "B"},
    "n12": {"A", "B", "C"},
    "n14": {"A", "B", "C"},
    "n15": {"A", "B"},
}
EXPOSURE_FLAGS = {
    "N05": "data_submitted",
    "N06": "auth_granted",
    "N07": "payment_made",
}


def _is_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _option_effect(option: Mapping[str, Any], key: str) -> Any:
    effects = option.get("effects")
    if not isinstance(effects, dict):
        return None
    flags = effects.get("flags")
    if not isinstance(flags, dict):
        return None
    return flags.get(key)


def _path_text(path: str, message: str) -> str:
    return "%s: %s" % (path, message)


def _validate_ending_condition(condition: Any, path: str, errors: List[str]) -> None:
    if not isinstance(condition, dict) or not condition:
        errors.append("%s: expected a non-empty condition object" % path)
        return

    if set(condition) == {"default"}:
        if condition.get("default") is not True:
            errors.append("%s.default: expected true" % path)
        return

    if set(condition) & ALLOWED_ENDING_CONDITION_KEYS:
        if set(condition) - {"all", "any"}:
            errors.append("%s: combinators cannot be mixed with other keys" % path)
        for key in ("all", "any"):
            if key not in condition:
                continue
            children = condition[key]
            if not isinstance(children, list) or not children:
                errors.append("%s.%s: expected a non-empty list" % (path, key))
                continue
            for index, child in enumerate(children):
                _validate_ending_condition(child, "%s.%s[%d]" % (path, key, index), errors)
        return

    if set(condition) != {"field", "op", "value"}:
        errors.append("%s: expected field/op/value or all/any" % path)
        return

    field = condition.get("field")
    op = condition.get("op")
    value = condition.get("value")
    if field not in ENDING_CONDITION_FIELDS:
        errors.append("%s.field: unknown ending condition field %r" % (path, field))
        return
    if op not in ENDING_CONDITION_OPERATORS:
        errors.append("%s.op: unknown comparison operator %r" % (path, op))
        return
    if field in NUMERIC_ENDING_FIELDS:
        if not _is_integer(value) or value < 0:
            errors.append("%s.value: expected a non-negative integer" % path)
        if op not in {"eq", "ne", "gt", "gte", "lt", "lte"}:
            errors.append("%s.op: invalid numeric comparison" % path)
    elif field in BOOLEAN_ENDING_FIELDS:
        if type(value) is not bool or op not in {"eq", "ne"}:
            errors.append("%s: boolean fields require eq/ne and a boolean value" % path)
    elif field in CHOICE_ENDING_VALUES:
        if value not in CHOICE_ENDING_VALUES[field] or op not in {"eq", "ne"}:
            errors.append("%s: invalid choice comparison for %s" % (path, field))


def _validate_frontend_graph(config: Mapping[str, Any]) -> List[str]:
    """Validate the additive graph format that mirrors the bundled frontend."""
    errors: List[str] = []
    meta = config.get("meta")
    if not isinstance(meta, dict):
        return ["meta: expected an object"]
    if not isinstance(meta.get("title"), str) or not meta.get("title"):
        errors.append("meta.title: expected a non-empty string")

    nodes = config.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != 15:
        return errors + ["nodes: expected 15 graph nodes"]
    node_map: Dict[str, Dict[str, Any]] = {}
    for index, node in enumerate(nodes):
        path = "nodes[%d]" % index
        expected_id = "N%02d" % (index + 1)
        if not isinstance(node, dict):
            errors.append("%s: expected an object" % path)
            continue
        node_id = node.get("id")
        if node_id != expected_id:
            errors.append("%s.id: expected %s in fixed order" % (path, expected_id))
        if isinstance(node_id, str) and node_id in node_map:
            errors.append("%s.id: duplicate %s" % (path, node_id))
        if isinstance(node_id, str):
            node_map[node_id] = node
        for field in ("title", "time", "speaker", "text", "prompt"):
            if not isinstance(node.get(field), str) or not node.get(field):
                errors.append("%s.%s: expected a non-empty string" % (path, field))
        if not isinstance(node.get("free"), bool):
            errors.append("%s.free: expected a boolean" % path)
        for field in ("phone",):
            value = node.get(field, [])
            if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                errors.append("%s.%s: expected a list of strings" % (path, field))
        if node.get("prop") is not None and not isinstance(node.get("prop"), str):
            errors.append("%s.prop: expected a string or null" % path)

        options = node.get("options")
        if not isinstance(options, list):
            errors.append("%s.options: expected a list" % path)
            options = []
        is_free = node.get("free") is True
        if is_free and options:
            errors.append("%s.options: free-answer nodes must not define fixed options" % path)
        if not is_free and len(options) not in (2, 3):
            errors.append("%s.options: expected 2 or 3 options" % path)
        option_ids: Set[str] = set()
        for option_index, option in enumerate(options):
            opath = "%s.options[%d]" % (path, option_index)
            if not isinstance(option, dict):
                errors.append("%s: expected an object" % opath)
                continue
            option_id = option.get("id")
            if option_id not in ("A", "B", "C"):
                errors.append("%s.id: expected A, B, or C" % opath)
            elif option_id in option_ids:
                errors.append("%s.id: duplicate %s" % (opath, option_id))
            else:
                option_ids.add(option_id)
            for field in ("text", "target"):
                if not isinstance(option.get(field), str) or not option.get(field):
                    errors.append("%s.%s: expected a non-empty string" % (opath, field))
            if "response" in option and not isinstance(option.get("response"), str):
                errors.append("%s.response: expected a string" % opath)
            conditional = option.get("conditional_targets", [])
            if not isinstance(conditional, list):
                errors.append("%s.conditional_targets: expected a list" % opath)
                conditional = []
            for target in [option.get("target")] + [
                item.get("target") for item in conditional if isinstance(item, dict)
            ]:
                if isinstance(target, str) and not (
                    target in {"N%02d" % i for i in range(1, 16)}
                    or target in FRONTEND_ENDING_IDS
                ):
                    errors.append("%s: unknown target %r" % (opath, target))
            for cond_index, item in enumerate(conditional):
                cpath = "%s.conditional_targets[%d]" % (opath, cond_index)
                if not isinstance(item, dict) or not isinstance(item.get("when"), dict):
                    errors.append("%s: expected an object with when and target" % cpath)
                elif not item.get("when"):
                    errors.append("%s.when: expected a non-empty object" % cpath)
                if not isinstance(item, dict) or not isinstance(item.get("target"), str):
                    errors.append("%s.target: expected a string" % cpath)
            increments = option.get("increments", {})
            if not isinstance(increments, dict):
                errors.append("%s.increments: expected an object" % opath)
            else:
                for key, amount in increments.items():
                    if key not in {"ticket_paid", "second_paid", "small_paid", "invest_paid"}:
                        errors.append("%s.increments: unknown payment field %s" % (opath, key))
                    if not _is_integer(amount) or amount < 0:
                        errors.append("%s.increments.%s: expected a non-negative integer" % (opath, key))
        order = node.get("ui_option_order")
        if order is not None and (not isinstance(order, list) or order != [o.get("id") for o in options if isinstance(o, dict)]):
            errors.append("%s.ui_option_order: must match option IDs in display order" % path)

        free_answer = node.get("free_answer")
        if is_free:
            if not isinstance(free_answer, dict) or not isinstance(free_answer.get("routes"), list) or not free_answer["routes"]:
                errors.append("%s.free_answer.routes: expected a non-empty list" % path)
            else:
                for route_index, route in enumerate(free_answer["routes"]):
                    rpath = "%s.free_answer.routes[%d]" % (path, route_index)
                    if not isinstance(route, dict):
                        errors.append("%s: expected an object" % rpath)
                        continue
                    if not isinstance(route.get("target"), str) or route.get("target") not in set(FRONTEND_ENDING_IDS) | {"N%02d" % i for i in range(1, 16)}:
                        errors.append("%s.target: unknown graph target" % rpath)
                    for field in ("any_keywords", "all_keywords", "none_keywords"):
                        if field in route and (not isinstance(route[field], list) or any(not isinstance(x, str) or not x for x in route[field])):
                            errors.append("%s.%s: expected a list of non-empty strings" % (rpath, field))
        elif free_answer is not None:
            errors.append("%s.free_answer: only free-answer nodes may define routes" % path)

    endings = config.get("endings")
    if not isinstance(endings, list) or len(endings) != 16:
        errors.append("endings: expected 16 frontend endings")
        endings = []
    ending_ids: List[str] = []
    for index, ending in enumerate(endings):
        path = "endings[%d]" % index
        if not isinstance(ending, dict):
            errors.append("%s: expected an object" % path)
            continue
        ending_id = ending.get("id")
        if isinstance(ending_id, str):
            ending_ids.append(ending_id)
        if ending_id != "E%02d" % (index + 1):
            errors.append("%s.id: expected E%02d in fixed order" % (path, index + 1))
        for field in ("title", "rating", "narration", "note"):
            if not isinstance(ending.get(field), str) or not ending.get(field):
                errors.append("%s.%s: expected a non-empty string" % (path, field))
    if set(ending_ids) != set(FRONTEND_ENDING_IDS):
        errors.append("endings: IDs must cover E01 through E16 exactly once")
    return errors


def validate_config(config: Any) -> List[str]:
    """Return all detectable config errors without mutating the input."""
    errors = []
    if not isinstance(config, dict):
        return ["root: expected a JSON object"]

    meta = config.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta: expected an object")
        meta = {}
    elif meta.get("model") == GRAPH_MODEL:
        return _validate_frontend_graph(config)

    score = meta.get("score")
    if not isinstance(score, dict):
        errors.append("meta.score: expected an object")
        score = {}
    for key, expected in (("base", 96), ("share_bonus", 4), ("denominator", 210)):
        if score.get(key) != expected:
            errors.append("meta.score.%s: expected %s" % (key, expected))

    weights = score.get("weights", meta.get("weights"))
    if not isinstance(weights, dict):
        errors.append("meta.score.weights: expected the seven dimension weights")
    elif weights != DIMENSION_WEIGHTS:
        errors.append("meta.score.weights: values do not match 08")

    acts = config.get("acts")
    if not isinstance(acts, list):
        errors.append("acts: expected a list")
        act_ids = set()
    else:
        if len(acts) != 5:
            errors.append("acts: expected 5 acts")
        act_ids = set()
        for index, act in enumerate(acts):
            if not isinstance(act, dict):
                errors.append("acts[%d]: expected an object" % index)
                continue
            act_id = act.get("id")
            if not isinstance(act_id, str) or not act_id:
                errors.append("acts[%d].id: expected a non-empty string" % index)
            elif act_id in act_ids:
                errors.append("acts[%d].id: duplicate %s" % (index, act_id))
            else:
                act_ids.add(act_id)

    raw_nodes = config.get("nodes")
    nodes_by_id: Dict[str, Dict[str, Any]] = {}
    if not isinstance(raw_nodes, list):
        errors.append("nodes: expected a list")
        raw_nodes = []
    if len(raw_nodes) != 15:
        errors.append("nodes: expected 15 nodes")

    for index, node in enumerate(raw_nodes):
        path = "nodes[%d]" % index
        if not isinstance(node, dict):
            errors.append("%s: expected an object" % path)
            continue
        node_id = node.get("id")
        expected_id = NODE_IDS[index] if index < len(NODE_IDS) else None
        if node_id != expected_id:
            errors.append("%s.id: expected %s in fixed order" % (path, expected_id))
        if not isinstance(node_id, str):
            continue
        if node_id in nodes_by_id:
            errors.append("%s.id: duplicate %s" % (path, node_id))
        nodes_by_id[node_id] = node

        for field in ("act", "time", "scene"):
            if not isinstance(node.get(field), str) or not node.get(field):
                errors.append("%s.%s: expected a non-empty string" % (path, field))
        if node.get("act") not in act_ids:
            errors.append("%s.act: unknown act %r" % (path, node.get("act")))
        if "prompt" not in node or (
            node.get("prompt") is not None and not isinstance(node.get("prompt"), str)
        ):
            errors.append("%s.prompt: expected a string or null" % path)

        lines = node.get("lines")
        if not isinstance(lines, list):
            errors.append("%s.lines: expected a list" % path)
        else:
            for line_index, line in enumerate(lines):
                if not isinstance(line, dict):
                    errors.append("%s.lines[%d]: expected an object" % (path, line_index))
                    continue
                if not isinstance(line.get("speaker"), str) or not isinstance(line.get("text"), str):
                    errors.append("%s.lines[%d]: speaker and text must be strings" % (path, line_index))

        options = node.get("options")
        if not isinstance(options, list):
            errors.append("%s.options: expected a list" % path)
            options = []
        if len(options) not in (2, 3):
            errors.append("%s.options: expected 2 or 3 options" % path)

        option_ids = []
        for option_index, option in enumerate(options):
            option_path = "%s.options[%d]" % (path, option_index)
            if not isinstance(option, dict):
                errors.append("%s: expected an object" % option_path)
                continue
            option_id = option.get("id")
            if option_id not in ("A", "B", "C"):
                errors.append("%s.id: expected A, B, or C" % option_path)
            else:
                option_ids.append(option_id)
            for field in ("text", "response"):
                if not isinstance(option.get(field), str) or not option.get(field):
                    errors.append("%s.%s: expected a non-empty string" % (option_path, field))
            effects = option.get("effects")
            if not isinstance(effects, dict) or not isinstance(effects.get("flags"), dict):
                errors.append("%s.effects.flags: expected an object" % option_path)
            else:
                unknown = set(effects["flags"]) - ALLOWED_STATE_FLAGS
                if unknown:
                    errors.append("%s.effects.flags: unknown keys %s" % (option_path, sorted(unknown)))
            if isinstance(effects, dict) and "increments" in effects:
                increments = effects["increments"]
                if not isinstance(increments, dict):
                    errors.append("%s.effects.increments: expected an object" % option_path)
                else:
                    for key, delta in increments.items():
                        if key not in ALLOWED_INCREMENT_KEYS:
                            errors.append("%s.effects.increments: unknown key %s" % (option_path, key))
                        if not _is_integer(delta) or delta < 0:
                            errors.append("%s.effects.increments.%s: expected a non-negative integer" % (option_path, key))

        if len(option_ids) != len(set(option_ids)):
            errors.append("%s.options: duplicate option IDs" % path)
        order = node.get("ui_option_order")
        if not isinstance(order, list) or order != option_ids:
            errors.append("%s.ui_option_order: must match option IDs in display order" % path)

        expected_next = NODE_IDS[index + 1] if index + 1 < len(NODE_IDS) else "REVIEW"
        if node.get("next") != expected_next:
            errors.append("%s.next: expected %s" % (path, expected_next))

    if set(nodes_by_id) != set(NODE_IDS):
        errors.append("nodes: IDs must be exactly N01 through N15")

    option_counts = [len(n.get("options", [])) for n in raw_nodes if isinstance(n, dict) and isinstance(n.get("options"), list)]
    if option_counts.count(2) != 10 or option_counts.count(3) != 5:
        errors.append("nodes.options: expected ten 2-option nodes and five 3-option nodes")

    raw_variants = config.get("variants")
    if not isinstance(raw_variants, list):
        errors.append("variants: expected a list")
        raw_variants = []
    for index, variant in enumerate(raw_variants):
        path = "variants[%d]" % index
        if not isinstance(variant, dict):
            errors.append("%s: expected an object" % path)
            continue
        node_id = variant.get("node")
        node = nodes_by_id.get(node_id)
        if node is None:
            errors.append("%s.node: unknown node %r" % (path, node_id))
            continue
        when = variant.get("when")
        if not isinstance(when, dict) or not when:
            errors.append("%s.when: expected a non-empty condition object" % path)
        elif set(when) - ALLOWED_VARIANT_CONDITIONS:
            errors.append("%s.when: unknown condition keys %s" % (path, sorted(set(when) - ALLOWED_VARIANT_CONDITIONS)))
        variant_options = variant.get("options")
        if variant_options is not None:
            if not isinstance(variant_options, list):
                errors.append("%s.options: expected a list" % path)
            else:
                base_ids = [o.get("id") for o in node.get("options", []) if isinstance(o, dict)]
                variant_ids = [o.get("id") for o in variant_options if isinstance(o, dict)]
                if variant_ids != base_ids:
                    errors.append("%s.options: IDs and order must match the base node" % path)
                for option_index, option in enumerate(variant_options):
                    if not isinstance(option, dict):
                        continue
                    effects = option.get("effects")
                    if not isinstance(effects, dict) or not isinstance(effects.get("flags"), dict):
                        errors.append("%s.options[%d].effects.flags: expected an object" % (path, option_index))
                    elif "increments" in effects:
                        increments = effects["increments"]
                        if not isinstance(increments, dict):
                            errors.append("%s.options[%d].effects.increments: expected an object" % (path, option_index))
                        else:
                            for key, delta in increments.items():
                                if key not in ALLOWED_INCREMENT_KEYS:
                                    errors.append("%s.options[%d].effects.increments: unknown key %s" % (path, option_index, key))
                                if not _is_integer(delta) or delta < 0:
                                    errors.append("%s.options[%d].effects.increments.%s: expected a non-negative integer" % (path, option_index, key))
        if when.get("contact_closed") is True and node_id in EXPOSURE_FLAGS:
            exposure_key = EXPOSURE_FLAGS[node_id]
            for option_index, option in enumerate(variant_options or []):
                if isinstance(option, dict) and _option_effect(option, exposure_key) is True:
                    errors.append("%s.options[%d]: early-disconnect variant creates %s" % (path, option_index, exposure_key))

    for node_id, flag in EXPOSURE_FLAGS.items():
        node = nodes_by_id.get(node_id)
        if not node:
            continue
        options = {o.get("id"): o for o in node.get("options", []) if isinstance(o, dict)}
        if _option_effect(options.get("B", {}), flag) is not True:
            errors.append("%s option B must record %s=true in the active scene" % (node_id, flag))
        if _option_effect(options.get("A", {}), flag) is not False:
            errors.append("%s option A must record %s=false in the active scene" % (node_id, flag))

    raw_endings = config.get("endings")
    if not isinstance(raw_endings, list):
        errors.append("endings: expected a list")
        raw_endings = []
    if len(raw_endings) != 16:
        errors.append("endings: expected 16 endings")
    ending_map = {}
    ending_priorities = []
    for index, ending in enumerate(raw_endings):
        path = "endings[%d]" % index
        if not isinstance(ending, dict):
            errors.append("%s: expected an object" % path)
            continue
        ending_id = ending.get("id")
        if ending_id not in ENDING_IDS:
            errors.append("%s.id: unknown ending %r" % (path, ending_id))
        elif ending_id in ending_map:
            errors.append("%s.id: duplicate %s" % (path, ending_id))
        else:
            ending_map[ending_id] = ending
        for field in ("title", "narration", "next_step"):
            if not isinstance(ending.get(field), str) or not ending.get(field):
                errors.append("%s.%s: expected a non-empty string" % (path, field))
        when = ending.get("when")
        _validate_ending_condition(when, "%s.when" % path, errors)
        priority = ending.get("priority")
        if not _is_integer(priority) or priority < 0:
            errors.append("%s.priority: expected a non-negative integer" % path)
        else:
            ending_priorities.append(priority)
        reference_score = ending.get("reference_score")
        expected_score = REFERENCE_SCORES.get(ending_id)
        if not _is_integer(reference_score) or reference_score != expected_score:
            errors.append("%s.reference_score: expected %s" % (path, expected_score))
    if set(ending_map) != set(ENDING_IDS):
        errors.append("endings: IDs must cover R01-R14, P01, and P02")
    if len(ending_priorities) != len(raw_endings) or len(ending_priorities) != len(set(ending_priorities)):
        errors.append("endings.priority: values must be unique for all endings")

    raw_badges = config.get("badges")
    if not isinstance(raw_badges, list):
        errors.append("badges: expected a list")
        raw_badges = []
    if len(raw_badges) != 7:
        errors.append("badges: expected 7 badges")
    badge_ids = []
    for index, badge in enumerate(raw_badges):
        path = "badges[%d]" % index
        if not isinstance(badge, dict):
            errors.append("%s: expected an object" % path)
            continue
        badge_id = badge.get("id")
        badge_ids.append(badge_id)
        if not isinstance(badge_id, str) or not badge_id:
            errors.append("%s.id: expected a non-empty string" % path)
        if not isinstance(badge.get("name"), str) or not badge.get("name"):
            errors.append("%s.name: expected a non-empty string" % path)
        if not isinstance(badge.get("when"), dict):
            errors.append("%s.when: expected an object" % path)
    if set(badge_ids) != set(BADGE_IDS):
        errors.append("badges: IDs must match the seven 08 actions")

    raw_witnesses = config.get("witness_paths")
    if not isinstance(raw_witnesses, list):
        errors.append("witness_paths: expected a list")
        raw_witnesses = []
    if len(raw_witnesses) != 16:
        errors.append("witness_paths: expected 16 paths")
    witness_ids = []
    for index, witness in enumerate(raw_witnesses):
        path = "witness_paths[%d]" % index
        if not isinstance(witness, dict):
            errors.append("%s: expected an object" % path)
            continue
        ending_id = witness.get("ending")
        witness_ids.append(ending_id)
        if ending_id not in ENDING_IDS:
            errors.append("%s.ending: unknown ending %r" % (path, ending_id))
        choices = witness.get("choices")
        if not isinstance(choices, list) or len(choices) != 15:
            errors.append("%s.choices: expected 15 option IDs" % path)
            continue
        for node_index, option_id in enumerate(choices):
            node_id = NODE_IDS[node_index]
            node = nodes_by_id.get(node_id, {})
            allowed = [
                option.get("id")
                for option in node.get("options", [])
                if isinstance(option, dict)
            ]
            if option_id not in allowed:
                errors.append("%s.choices[%d]: invalid option %r for %s" % (path, node_index, option_id, node_id))
    if set(witness_ids) != set(ENDING_IDS):
        errors.append("witness_paths: require one path for every ending")

    return errors
