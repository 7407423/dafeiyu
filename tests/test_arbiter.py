"""仲裁打分：价值×紧迫×预期−中断成本、类型上限、能否打断。"""

from __future__ import annotations

import unittest

from . import base  # noqa: F401  （先设 DAFEIYU_HOME，再碰 core）
from core.cognition import arbiter
from core.entity import ArbiterCandidate


class TestArbiter(unittest.TestCase):
    def test_formula(self):
        cand = ArbiterCandidate(kind="chitchat", value=1.0, urgency=1.0, expectancy=1.0,
                                interrupt_cost=0.2)
        self.assertAlmostEqual(cand.score(), 0.8, places=6)

    def test_fatigue_shrinks_value(self):
        cands = [
            arbiter.make("learn", "a", value=0.8, fatigue=0.0),
            arbiter.make("learn", "b", value=0.8, fatigue=0.8),
        ]
        out = arbiter.pick(cands)
        self.assertEqual(out["picked"][0]["ref_id"], "a")

    def test_dialogue_beats_chitchat(self):
        cands = [arbiter.make("dialogue", "d1"), arbiter.make("chitchat", "c1")]
        out = arbiter.pick(cands)
        self.assertEqual(out["winner"]["kind"], "dialogue")

    def test_type_cap(self):
        cands = [arbiter.make("learn", "a", value=0.9), arbiter.make("learn", "b", value=0.85),
                 arbiter.make("open_thought", "t", value=0.5)]
        out = arbiter.pick(cands)
        self.assertEqual([e["kind"] for e in out["picked"]].count("learn"), 1)
        self.assertEqual(len(out["picked"]), 2)   # learn 上限 1 + open_thought 上限 2

    def test_interruption_flag(self):
        out = arbiter.pick([arbiter.make("dialogue", "d")], busy_kind="chitchat")
        self.assertTrue(out["interrupted"])
        out2 = arbiter.pick([arbiter.make("chitchat", "c")], busy_kind="chitchat")
        self.assertFalse(out2["interrupted"])

    def test_empty(self):
        out = arbiter.pick([])
        self.assertIsNone(out["winner"])


if __name__ == "__main__":
    unittest.main()
