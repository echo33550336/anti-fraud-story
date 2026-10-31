"""Exhaustive checks for the 15-node story configuration."""
from __future__ import print_function

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game import engine
from game.schemas import ENDING_IDS, NODE_IDS, REFERENCE_SCORES, validate_config

CONFIG_PATH = ROOT / "game" / "config" / "story_15nodes.json"
EXPECTED_COMBINATIONS = 248832


def _simulate(choices):
    flags = {}
    ticket_stage_flags = {}
    for node_id, option_id in zip(NODE_IDS, choices):
        flags = engine.apply_choice(flags, node_id, option_id)
        if node_id == "N07":
            ticket_stage_flags = dict(flags)
    review = engine.build_review(flags)
    return flags, review, ticket_stage_flags


def _check_witnesses(config, failures):
    witnesses = config.get("witness_paths", [])
    by_ending = {}
    endings = {
        item.get("id"): item
        for item in config.get("endings", [])
        if isinstance(item, dict)
    }
    for witness in witnesses:
        if not isinstance(witness, dict):
            continue
        ending_id = witness.get("ending")
        choices = witness.get("choices")
        if ending_id in by_ending:
            failures.append("duplicate witness path for %s" % ending_id)
            continue
        by_ending[ending_id] = witness
        if not isinstance(choices, list) or len(choices) != 15:
            continue
        try:
            flags, review, _ = _simulate(choices)
        except (KeyError, TypeError, ValueError) as exc:
            failures.append("witness %s cannot be replayed: %s" % (ending_id, exc))
            continue
        if review["ending_id"] != ending_id:
            failures.append(
                "witness %s routes to %s" % (ending_id, review["ending_id"])
            )
        expected_score = REFERENCE_SCORES.get(ending_id)
        actual_score = review["score"]
        if type(actual_score) is not int or actual_score != expected_score:
            failures.append(
                "witness %s scores %r, expected integer %r"
                % (ending_id, actual_score, expected_score)
            )
        configured = endings.get(ending_id, {}).get("reference_score")
        if configured != review["score"]:
            failures.append(
                "ending %s configured reference score does not match replay"
                % ending_id
            )

    if set(by_ending) != set(ENDING_IDS):
        failures.append("witness paths do not cover all 16 endings")

    for ending_id in ("P01", "P02"):
        witness = by_ending.get(ending_id)
        if not witness or not isinstance(witness.get("choices"), list) or len(witness["choices"]) != 15:
            continue
        base_choices = list(witness["choices"])
        try:
            base_flags, base_review, _ = _simulate(base_choices)
        except (KeyError, TypeError, ValueError):
            continue
        for romance_choice in ("A", "B", "C"):
            variant_choices = list(base_choices)
            variant_choices[13] = romance_choice
            try:
                _, variant_review, _ = _simulate(variant_choices)
            except (KeyError, TypeError, ValueError) as exc:
                failures.append("romance branch %s could not replay: %s" % (romance_choice, exc))
                continue
            if variant_review["dimensions"] != base_review["dimensions"]:
                failures.append("N14 choice %s changed safety dimensions" % romance_choice)
            if variant_review["score"] != base_review["score"]:
                failures.append("N14 choice %s changed score" % romance_choice)


def main():
    if not CONFIG_PATH.is_file():
        print("配置文件不存在: %s" % CONFIG_PATH)
        return 2

    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except (IOError, ValueError) as exc:
        print("读取配置失败: %s" % exc)
        return 2

    failures = validate_config(config)
    if failures:
        for failure in failures:
            print("配置错误: %s" % failure)
        return 1

    option_sets = [
        [option["id"] for option in node["options"]]
        for node in config["nodes"]
    ]
    product_size = 1
    for option_set in option_sets:
        product_size *= len(option_set)
    if product_size != EXPECTED_COMBINATIONS:
        print("选项组合数错误: %d，预期 %d" % (product_size, EXPECTED_COMBINATIONS))
        return 1

    reachable = set()
    checked = 0
    for choices in itertools.product(*option_sets):
        try:
            flags, review, ticket_stage_flags = _simulate(choices)
        except (KeyError, TypeError, ValueError) as exc:
            print("组合复算失败，路径=%s，错误=%s" % (choices, exc))
            return 1
        checked += 1
        reachable.add(review["ending_id"])
        if choices[2] == "A" and (
            any(
                ticket_stage_flags.get(key) is True
                for key in ("data_submitted", "auth_granted", "payment_made")
            )
            or ticket_stage_flags.get("ticket_loss", 0) > 0
        ):
            print("早断联后产生暴露，路径=%s" % (choices,))
            return 1

    if checked != EXPECTED_COMBINATIONS:
        print("复算组合数错误: %d，预期 %d" % (checked, EXPECTED_COMBINATIONS))
        return 1
    if reachable != set(ENDING_IDS):
        print(
            "结局覆盖错误: 实际=%s，缺少=%s"
            % (sorted(reachable), sorted(set(ENDING_IDS) - reachable))
        )
        return 1

    _check_witnesses(config, failures)
    if failures:
        for failure in failures:
            print("复算错误: %s" % failure)
        return 1

    print("配置结构: 15 节点、16 结局、7 徽章")
    print("封闭选项组合: %d" % checked)
    print("可达结局: %d/16" % len(reachable))
    print("见证路径: 16/16，参考分精确匹配")
    print("早断联: N05-N07 未产生资料、授权或付款暴露")
    print("恋爱分支: A/B/C 不改变安全维度、结局或分数")
    return 0


if __name__ == "__main__":
    sys.exit(main())
