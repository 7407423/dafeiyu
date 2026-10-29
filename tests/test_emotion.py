"""情绪动力学：自然回归、阈值保护窗口、主导情绪重算。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from .base import BaseCase

from core.emotion import vector


class TestEmotionDynamics(BaseCase):
    def test_decays_toward_baseline(self):
        vector.set_values({"joy": 95})
        before = vector.current().get("joy")
        vector.tick(datetime.now() + timedelta(hours=2))
        after = vector.current().get("joy")
        self.assertLess(after, before)
        self.assertGreater(after, 55)      # 不会一路掉到基线
        # 再走 12 小时，应该明显靠近基线
        vector.tick(datetime.now() + timedelta(hours=14))
        self.assertLess(vector.current().get("joy"), after)

    def test_negative_decays_slower_than_shyness(self):
        vector.set_values({"sadness": 90, "shyness": 90})
        vector.tick(datetime.now() + timedelta(hours=2))
        vec = vector.current()
        # 2 小时：害羞（半衰期 2h）掉一半，难过（半衰期 2.5h）掉得少
        shy_drop = 90 - vec.get("shyness")
        sad_drop = 90 - vec.get("sadness")
        self.assertGreater(shy_drop, sad_drop)

    def test_protection_window_blocks_decay(self):
        vector.set_values({"joy": 55})
        vector.apply({"joy": 15})
        peak = vector.current().get("joy")
        self.assertGreaterEqual(peak, 60)
        self.assertIn("joy", vector.protected_dims())
        vector.tick(datetime.now() + timedelta(minutes=3))
        self.assertAlmostEqual(vector.current().get("joy"), peak, places=1)

    def test_dominant_from_deviation(self):
        vector.set_values({"shyness": 88})
        self.assertEqual(vector.current().dominant, "shyness")
        vector.set_values({"shyness": 5, "sadness": 70})
        self.assertEqual(vector.current().dominant, "sadness")

    def test_mood_factor(self):
        vector.set_values({"joy": 90, "happiness": 90, "sadness": 0, "inferiority": 0})
        happy = vector.current().mood_factor()
        vector.set_values({"sadness": 90, "inferiority": 90, "joy": 0, "happiness": 0})
        sad = vector.current().mood_factor()
        self.assertGreater(happy, sad)


if __name__ == "__main__":
    unittest.main()
