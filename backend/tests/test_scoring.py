"""Unit tests for the integer scoring functions."""
from __future__ import annotations

import unittest

from game import engine
from game.scoring import compute_dimension_score, compute_frontend_score, total_paid

DIMENSION_ORDER = engine.DIMENSION_ORDER


class FrontendScoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = engine.load_frontend_graph_config()["scoring"]

    def score(self, ending_id, **payments):
        return compute_frontend_score(payments, ending_id, self.spec)

    def test_returns_plain_int(self):
        for ending_id in ("E01", "E03", "E12", "E13", "E16"):
            for paid in (0, 137, 900, 1028, 1216, 1800, 3000, 4216, 5116):
                result = self.score(ending_id, ticket_paid=paid)
                self.assertIs(type(result), int)
                self.assertGreaterEqual(result, 10)
                self.assertLessEqual(result, 100)

    def test_zero_payment(self):
        self.assertEqual(self.score("E01"), 100)
        self.assertEqual(self.score("E02"), 100)

    def test_payment_deduction_is_integer_division(self):
        # 900 // 100 = 9 -> 91
        self.assertEqual(self.score("E04", ticket_paid=900), 91)
        # 1800 // 100 = 18 -> 82
        self.assertEqual(self.score("E04", ticket_paid=1800), 82)

    def test_ending_penalties(self):
        self.assertEqual(self.score("E03", ticket_paid=1800, second_paid=1200), 52)
        self.assertEqual(self.score("E13", ticket_paid=900, small_paid=316, invest_paid=3000), 43)
        self.assertEqual(self.score("E16", ticket_paid=900, second_paid=900, small_paid=316, invest_paid=3000), 32)

    def test_good_ending_floor(self):
        # 4216 // 100 = 42 -> 58, floored to 82 for E12
        self.assertEqual(self.score("E12", ticket_paid=900, second_paid=900, small_paid=316, invest_paid=3000), 82)

    def test_payment_deduction_cap(self):
        self.assertEqual(self.score("E16", invest_paid=6000), 32)  # 50 cap + 18 penalty

    def test_total_paid(self):
        flags = {"ticket_paid": 900, "second_paid": 900, "small_paid": 316, "invest_paid": 3000}
        self.assertEqual(total_paid(flags, self.spec["payment_fields"]), 5116)
        self.assertIs(type(total_paid(flags, self.spec["payment_fields"])), int)

    def test_rejects_negative_payment(self):
        with self.assertRaises(ValueError):
            self.score("E04", ticket_paid=-1)


class DimensionScoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = engine._CONFIG["meta"]["score"]

    def test_returns_plain_int(self):
        dimensions = {name: 2 for name in DIMENSION_ORDER}
        self.assertIs(type(compute_dimension_score(dimensions, "A", self.spec, DIMENSION_ORDER)), int)

    def test_all_protected(self):
        dimensions = {name: 2 for name in DIMENSION_ORDER}
        self.assertEqual(compute_dimension_score(dimensions, "A", self.spec, DIMENSION_ORDER), 98)
        self.assertEqual(compute_dimension_score(dimensions, "B", self.spec, DIMENSION_ORDER), 100)

    def test_all_zero(self):
        dimensions = {name: 0 for name in DIMENSION_ORDER}
        self.assertEqual(compute_dimension_score(dimensions, "A", self.spec, DIMENSION_ORDER), 50)

    def test_single_gap(self):
        dimensions = {name: 2 for name in DIMENSION_ORDER}
        dimensions["funds"] = 1
        self.assertEqual(compute_dimension_score(dimensions, "A", self.spec, DIMENSION_ORDER), 93)

    def test_engine_wrapper_matches(self):
        dimensions = {name: 2 for name in DIMENSION_ORDER}
        self.assertEqual(engine.compute_score(dimensions, "A"), 98)
        self.assertIs(type(engine.compute_score(dimensions, "A")), int)


if __name__ == "__main__":
    unittest.main()
