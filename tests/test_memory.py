"""衰减函数、分级压缩、蒸馏后墓碑仍可检索。"""

from __future__ import annotations

import unittest

from .base import BaseCase, make_memory

from core.emotion.dynamics import decay_toward
from core.memory import forget


class TestDecayMath(unittest.TestCase):
    def test_exponential_half_life(self):
        self.assertAlmostEqual(decay_toward(100, 0, 60, 60), 50.0, places=4)
        self.assertAlmostEqual(decay_toward(0, 100, 60, 60), 50.0, places=4)
        self.assertEqual(decay_toward(70, 0, 0, 60), 70.0)
        self.assertEqual(decay_toward(70, 0, 120, 0), 70.0)

    def test_tau_grows_with_salience_and_open(self):
        low = forget.tau_hours("thought", 0.1, "resolved", 0)
        high = forget.tau_hours("thought", 0.9, "resolved", 0)
        open_tau = forget.tau_hours("thought", 0.9, "open", 0)
        self.assertGreater(high, low)
        self.assertGreater(open_tau, high)

    def test_level_thresholds(self):
        self.assertEqual(forget.next_level(0.7, 0), 0)
        self.assertEqual(forget.next_level(0.5, 0), 1)
        self.assertEqual(forget.next_level(0.2, 1), 2)
        self.assertEqual(forget.next_level(0.1, 2), 3)


class TestForgetDistill(BaseCase):
    def test_level3_distills_before_deleting(self):
        item = make_memory(layer="short", subtype="pending",
                           content="老大说下次别再熬夜了，我记住了。",
                           summary="别再熬夜", concepts=["熬夜", "老大"], emotion_tag="难过",
                           salience=0.9, strength=0.02)
        stats = forget.decay_pass()
        self.assertGreaterEqual(stats["distilled"], 1)

        from core.repo import learning as lr, memory as mr

        tomb = mr.get(item.id)
        self.assertEqual(tomb.tombstone, 1)
        self.assertEqual(tomb.content, "")       # 正文删了
        self.assertTrue(tomb.concepts)           # 概念留着 → 还能被检索到

        conclusions = [i for i in mr.list_layer(layer="long2", limit=50) if i.subtype == "conclusion"]
        self.assertTrue(conclusions, "结论应该进长期记忆")
        self.assertTrue(lr.knowledge_list(limit=10), "教训应该进技能栏")

    def test_access_refreshes_strength(self):
        item = make_memory(layer="short", subtype="diary", content="今天很平常",
                           salience=0.3, strength=0.2)
        from core.repo import memory as mr

        mr.touch(item.id)
        back = mr.get(item.id)
        self.assertGreaterEqual(back.strength, 0.9)
        self.assertEqual(back.access_count, 1)


if __name__ == "__main__":
    unittest.main()
