"""尺度检测：陡增害羞，且只作用于 shyness。"""

from __future__ import annotations

import unittest

from .base import BaseCase

from core.emotion import detector_scale, vector


class TestScale(BaseCase):
    def test_levels_and_delta(self):
        one = detector_scale.detect("亲亲你")
        self.assertTrue(one["hit"])
        self.assertEqual(one["level"], 1)
        self.assertAlmostEqual(one["delta"]["shyness"], 20.0, places=1)

        two = detector_scale.detect("想跟你一起睡")
        self.assertEqual(two["level"], 2)
        self.assertAlmostEqual(two["delta"]["shyness"], 35.0, places=1)

        three = detector_scale.detect("太露骨了，做爱")
        self.assertEqual(three["level"], 3)
        self.assertLessEqual(three["delta"]["shyness"], 45.0)

    def test_normal_text_does_not_hit(self):
        self.assertFalse(detector_scale.detect("今天吃了碗面，还行")["hit"])
        # 抱抱属于亲密（奖励），不该算尺度
        self.assertFalse(detector_scale.detect("抱抱你")["hit"])

    def test_only_shyness_changes(self):
        vector.set_values({"joy": 60, "happiness": 60, "sadness": 10, "inferiority": 10})
        before = dict(vector.current().values)
        detector_scale.apply("想跟你一起睡")
        after = vector.current()
        for dim in ("joy", "happiness", "sadness", "inferiority"):
            self.assertAlmostEqual(after.get(dim), before[dim], places=1)
        self.assertGreater(after.get("shyness"), before["shyness"])

    def test_shy_behavior_mapping(self):
        vector.set_values({"shyness": 80})
        from core.emotion import policy

        loud = policy.build(vector.current(), curiosity=0.9)
        quiet = policy.build(vector.current(), curiosity=0.2)
        self.assertEqual(loud.tone, "shy_verbose")
        self.assertEqual(quiet.tone, "shy_short")
        self.assertGreater(loud.max_chars, quiet.max_chars)


if __name__ == "__main__":
    unittest.main()
