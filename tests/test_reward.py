"""奖罚：delta 生效、RPE 递减、显著性回填。"""

from __future__ import annotations

import unittest

from .base import BaseCase, make_memory

from core.emotion import reward, vector


class TestReward(BaseCase):
    def test_praise_raises_positive(self):
        before = vector.current().get("joy")
        ev = reward.apply_trigger("praise", "老大说我很棒")
        self.assertEqual(ev.type, "reward")
        self.assertGreater(vector.current().get("joy"), before)

    def test_rpe_decays_on_repeat(self):
        first = reward.apply_trigger("praise", "真棒")
        second = reward.apply_trigger("praise", "真厉害")
        third = reward.apply_trigger("praise", "真好")
        self.assertEqual(first.rpe_weight, 1.0)
        self.assertLess(second.rpe_weight, first.rpe_weight)
        self.assertLess(third.rpe_weight, second.rpe_weight)
        self.assertGreater(third.rpe_weight, 0.19)

    def test_insult_raises_negative(self):
        before = vector.current().get("sadness")
        reward.apply_trigger("insult", "你怎么这么没用")
        self.assertGreater(vector.current().get("sadness"), before)
        self.assertGreater(vector.current().get("inferiority"), 0)

    def test_ignored_is_punishment(self):
        ev = reward.apply_trigger("ignored", "被晾着 90 分钟")
        self.assertEqual(ev.type, "punishment")
        self.assertGreater(ev.delta.get("sadness", 0), 0)

    def test_salience_boost_near_event(self):
        item = make_memory(layer="instant", subtype="chat", content="老大夸我了", salience=0.2)
        reward.apply_trigger("intimacy", "抱抱你")
        from core.repo import memory as mr

        self.assertGreater(mr.get(item.id).salience, 0.2)

    def test_stats_shape_matches_bridge(self):
        reward.apply_trigger("praise", "好")
        reward.apply_trigger("insult", "滚")
        stats = reward.stats()
        self.assertEqual(set(stats), {"rewards", "punishments", "shame", "ignored", "care"})
        self.assertEqual(stats["rewards"], 1)
        self.assertEqual(stats["punishments"], 1)


if __name__ == "__main__":
    unittest.main()
