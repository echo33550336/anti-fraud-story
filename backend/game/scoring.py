"""Integer scoring functions for the story backend.

Every score is produced by a plain function that returns an ``int``.  This
module deliberately uses integer arithmetic only: no floats, no decimal
places, and no display-time rounding.

Two standards live here because the repository keeps the legacy model around:

* :func:`compute_frontend_score` - the current frontend-aligned story
  (10-100, payment deductions + ending penalties + good-ending floors).
* :func:`compute_dimension_score` - the archived seven-dimension model
  (50-100, weighted protection levels + optional sharing bonus).
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

PAYMENT_UNIT = 100


def _non_negative_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("%s must be a non-negative integer" % name)
    return int(value)


def total_paid(flags: Mapping[str, Any], payment_fields: Sequence[str]) -> int:
    """Return the sum of the simulated payments as an integer."""
    return sum(_non_negative_int(flags.get(key, 0), key) for key in payment_fields)


def compute_frontend_score(
    flags: Mapping[str, Any],
    ending_id: str,
    scoring: Mapping[str, Any],
) -> int:
    """Return the integer score (10-100) for a finished frontend-path run.

    ``paid // PAYMENT_UNIT`` is integer division, so the result never depends
    on decimal places or floating-point rounding.
    """
    if not isinstance(ending_id, str) or not ending_id:
        raise ValueError("ending_id must be a non-empty string")

    paid = total_paid(flags, scoring["payment_fields"])
    deduction = min(int(scoring["max_payment_deduction"]), paid // PAYMENT_UNIT)
    score = 100 - deduction
    score -= int(scoring["ending_penalties"].get(ending_id, 0))
    score = max(
        score,
        int(scoring["minimum_score_by_ending"].get(ending_id, scoring["score_min"])),
    )
    return max(int(scoring["score_min"]), min(int(scoring["score_max"]), score))


def compute_dimension_score(
    dimensions: Mapping[str, int],
    n15: str,
    score_spec: Mapping[str, Any],
    dimension_order: Sequence[str],
) -> int:
    """Return the legacy seven-dimension score as an integer from 50 to 100."""
    if n15 not in ("A", "B"):
        raise ValueError("completed story requires an N15 choice")
    if set(dimensions.keys()) != set(dimension_order):
        raise ValueError("dimensions must contain exactly the seven 08 dimensions")

    weights = score_spec["weights"]
    weighted_sum = 0
    for name in dimension_order:
        level = dimensions[name]
        if isinstance(level, bool) or not isinstance(level, int) or level not in (0, 1, 2):
            raise ValueError("dimension levels must be integer values from 0 to 2")
        weighted_sum += int(weights[name]) * level

    denominator = int(score_spec["denominator"])
    if denominator <= 0:
        raise ValueError("score denominator must be positive")

    raw_numerator = int(score_spec["base"]) * weighted_sum
    all_protected = all(dimensions[name] == 2 for name in dimension_order)
    if all_protected and n15 == "B":
        raw_numerator += int(score_spec["share_bonus"]) * denominator

    # final = round_half_up(50 + raw_score / 2), using integer arithmetic only.
    return 50 + (raw_numerator + denominator) // (2 * denominator)
