"""好奇心：缺口→意图、学习反馈回写权重、可学习性过滤。"""

from __future__ import annotations

import unittest

from .base import BaseCase

from core.cognition import curiosity, metacognition
from core.entity import KnowledgeItem
from core.repo import learning as lr


class TestCuriosity(BaseCase):
    def _gap_knowledge(self, name: str = "边界感") -> KnowledgeItem:
        item = KnowledgeItem(
            name=name, domain="情绪", concepts=[name],
            slots={"应有": ["是什么", "怎么用", "例子", "边界"], "已填": {}},
            content="", source="test",
        )
        item.recompute()
        lr.knowledge_insert(item)
        return item

    def test_gap_becomes_intent(self):
        self._gap_knowledge()
        self.assertTrue(metacognition.gaps())
        made = metacognition.intents_from_gaps()
        self.assertTrue(any(i.target == "边界感" for i in made))
        self.assertIn("边界感", [i["target"] for i in curiosity.view()["queue"]])

    def test_unlearnable_gap_filtered(self):
        self.assertEqual(curiosity.learnability.__name__, "learnability")
        from core.entity import LearningIntent

        self.assertLess(curiosity._learnability("什么"), 0.25)
        self.assertGreater(curiosity._learnability("边界感"), 0.5)
        intent = LearningIntent(target="边界感", expected_learnability=0.8)
        self.assertGreater(curiosity.learnability(intent), 0.5)

    def test_feedback_updates_domain_weight(self):
        before = curiosity.weights().weight("害羞")
        out = curiosity.feedback("害羞", before_uncertainty=0.9, after_uncertainty=0.2)
        self.assertGreater(out["weight"], before)
        after = curiosity.weights().weight("害羞")
        self.assertGreater(after, before)
        self.assertGreater(curiosity.weights().tired("害羞"), 0.0)

    def test_fatigue_decays(self):
        curiosity.feedback("语言", 0.9, 0.1)
        before = curiosity.weights().tired("语言")
        curiosity.tick_fatigue()
        self.assertLess(curiosity.weights().tired("语言"), before)

    def test_signals_in_range(self):
        sig = curiosity.signals("我今天不太懂什么叫边界感")
        for key in ("gap", "pred_err", "progress", "competence", "social"):
            self.assertIn(key, sig)
            self.assertGreaterEqual(sig[key], 0.0)
            self.assertLessEqual(sig[key], 1.0)


if __name__ == "__main__":
    unittest.main()
