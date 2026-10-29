"""检索：双路召回、命中刷新、2 号情绪门控。"""

from __future__ import annotations

import unittest

from .base import BaseCase, make_memory

from core.emotion import vector
from core.entity import EmotionVector
from core.memory import retrieval


class TestRetrieval(BaseCase):
    def test_keyword_and_semantic_recall(self):
        item = make_memory(layer="long2", subtype="summary",
                           content="老大抱了我一下，我说想赖着不动。",
                           concepts=["老大", "抱抱"], emotion_tag="开心", salience=0.8)
        out = retrieval.recall("老大抱抱", top_k=5)
        self.assertTrue(out["items"])
        self.assertEqual(out["items"][0]["id"], item.id)

    def test_hit_refreshes_strength(self):
        item = make_memory(layer="short", subtype="diary", content="老大今天夸我厉害了",
                           concepts=["老大", "夸奖"], strength=0.2, salience=0.6)
        from core.repo import memory as mr

        retrieval.recall("老大夸我", top_k=3)
        back = mr.get(item.id)
        self.assertGreaterEqual(back.strength, 0.9)
        self.assertGreaterEqual(back.access_count, 1)

    def test_lt2_needs_concept_or_emotion(self):
        make_memory(layer="long2", subtype="summary", content="那次被撩到脸红了。",
                    concepts=["害羞", "脸红"], emotion_tag="害羞", salience=0.7)

        low = EmotionVector.from_config({"initial": {}, "baseline": {}})
        self.assertEqual(retrieval.lt2_recall("今天的天气如何", vec=low), [])

        # 概念命中 2 个 → 读
        hits = retrieval.lt2_recall("害羞 脸红", vec=low)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["category"], "害羞")

        # 情绪对得上 → 也读
        warm = EmotionVector.from_config({"initial": {"shyness": 80},
                                          "baseline": {"shyness": 5}})
        hits2 = retrieval.lt2_recall("今天的天气如何", vec=warm)
        self.assertTrue(hits2)
        self.assertIn("情绪", hits2[0]["reason"])

    def test_mood_congruent_boost(self):
        sad_item = make_memory(layer="long2", subtype="summary", content="他走了，我一个人坐着",
                               concepts=["离开", "一个人"], emotion_tag="难过", salience=0.6)
        plain_item = make_memory(layer="long2", subtype="summary", content="今天吃了碗面，还行",
                                 concepts=["吃饭", "日常"], emotion_tag="平静", salience=0.6)
        vec = EmotionVector.from_config({"initial": {"sadness": 80}, "baseline": {"sadness": 5}})
        quiet = EmotionVector.from_config({"initial": {"sadness": 0}, "baseline": {"sadness": 0}})
        self.assertGreater(retrieval.mood_bonus(sad_item, vec), 1.0)
        self.assertEqual(retrieval.mood_bonus(sad_item, quiet), 1.0)
        self.assertGreaterEqual(retrieval.mood_bonus(plain_item, vec), 1.0)


if __name__ == "__main__":
    unittest.main()
