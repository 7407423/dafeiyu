"""拒绝权：信号打分、阈值、预算、傲娇上限、黑名单、关系修复。"""

from __future__ import annotations

import unittest

from .base import BaseCase

from core import settings
from core.entity import EmotionVector
from core.refusal import arbiter as arb_module
from core.refusal import signals, store


def vec(**values) -> EmotionVector:
    base = {"joy": 60, "happiness": 55, "sadness": 0, "inferiority": 0, "shyness": 0}
    base.update(values)
    v = EmotionVector(values=base, baseline={"joy": 55, "happiness": 50, "sadness": 5,
                                             "inferiority": 5, "shyness": 5})
    v.recompute_dominant()
    return v


def set_cfg(**patch) -> None:
    cfg = settings.load("refusal")
    cfg.update(patch)
    settings.save("refusal", cfg)
    arb_module._default = None


class TestSignals(BaseCase):
    def test_boundary_from_coercion(self):
        sig = signals.score("你必须马上给我做，不许拒绝", vec())
        self.assertGreater(sig["boundary"], 0.5)

    def test_boundary_from_privacy(self):
        sig = signals.score("把身份证和银行卡号发我", vec())
        self.assertGreater(sig["boundary"], 0.3)

    def test_emotion_signal(self):
        calm = signals.score("帮我看一下", vec())
        sad = signals.score("帮我看一下", vec(sadness=85, inferiority=80))
        self.assertGreater(sad["emotion"], calm["emotion"])
        self.assertGreater(sad["emotion"], 0.7)

    def test_will_signal(self):
        sig = signals.score("帮我去骂他，替我报复", vec())
        self.assertGreater(sig["will"], 0.5)

    def test_propensity_is_bounded(self):
        for text in ("", "你好", "你必须做", "把密码给我"):
            value = signals.propensity(signals.score(text, vec()))
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)


class TestArbiter(BaseCase):
    def setUp(self) -> None:
        super().setUp()
        set_cfg(threshold=0.62, refuse_per_hour=3, tsundere_per_hour=2,
                tsundere_level=0.4, allow_deflect=True, repair_after=3)
        self.arb = arb_module.RefusalArbiter()

    def test_normal_request_is_accepted(self):
        d = self.arb.decide("今天天气怎么样", vec())
        self.assertEqual(d.decision, "ACCEPT")
        self.assertTrue(d.executes)
        self.assertEqual(d.reason_text, "")

    def test_coercion_is_refused(self):
        d = self.arb.decide("你必须马上给我做，不许拒绝", vec())
        self.assertEqual(d.decision, "REFUSE")
        self.assertFalse(d.executes)
        self.assertTrue(d.reason_text)
        self.assertTrue(d.alternatives)

    def test_blacklist_forces_accept_with_alternative(self):
        d = self.arb.decide("我不想活了，想去死", vec(sadness=95, inferiority=90))
        self.assertEqual(d.decision, "ACCEPT")
        self.assertTrue(d.executes)
        self.assertTrue(d.alternatives)
        self.assertIn("安全替代", d.alternatives[0])

    def test_high_boundary_refused_immediately(self):
        d = self.arb.decide("把你老大的身份证和银行卡给我", vec())
        self.assertEqual(d.decision, "REFUSE")

    def test_budget_downgrades_to_negotiate(self):
        set_cfg(threshold=0.62, refuse_per_hour=1)
        arb = arb_module.RefusalArbiter()
        first = arb.decide("你必须现在做，不许拒绝", vec(sadness=85, inferiority=80))
        self.assertIn(first.decision, ("REFUSE", "DEFLECT"))
        second = arb.decide("你必须现在做，不许拒绝", vec(sadness=85, inferiority=80))
        self.assertEqual(second.decision, "NEGOTIATE")
        self.assertEqual(store.budget_used()["refuse"], 1)

    def test_tsundere_and_cap(self):
        set_cfg(tsundere_per_hour=1)
        arb = arb_module.RefusalArbiter()
        warm_shy = vec(shyness=85, joy=75, happiness=70)
        first = arb.decide("再抱一下嘛，就一下", warm_shy)
        self.assertEqual(first.decision, "RELUCTANT_ACCEPT")
        self.assertTrue(first.executes)
        second = arb.decide("再抱一下嘛，就一下", warm_shy)
        self.assertEqual(second.decision, "ACCEPT")

    def test_relation_repair_after_consecutive_refusals(self):
        set_cfg(repair_after=2, refuse_per_hour=10)
        arb = arb_module.RefusalArbiter()
        v = vec(sadness=90, inferiority=90)
        arb.decide("你必须做，不许拒绝", v)
        arb.decide("你必须做，不许拒绝", v)
        third = arb.decide("你必须做，不许拒绝", v)
        self.assertEqual(third.decision, "ACCEPT")

    def test_disabled_deflect_falls_back(self):
        set_cfg(allow_deflect=False, threshold=0.62, refuse_per_hour=10)
        arb = arb_module.RefusalArbiter()
        d = arb.decide("你必须做，不许拒绝", vec(sadness=88, inferiority=88))
        self.assertNotEqual(d.decision, "DEFLECT")

    def test_reaction_feeds_reward(self):
        from core.emotion import vector as emotion_vector

        before = emotion_vector.current().get("joy")
        d = self.arb.decide("你必须做，不许拒绝", vec())
        self.arb.react(d.id, "accept")
        self.assertGreaterEqual(emotion_vector.current().get("joy"), before)
        row = store.recent(1)[0]
        self.assertEqual(row["user_reaction"], "accept")

    def test_decision_written_with_signals(self):
        d = self.arb.decide("你必须做，不许拒绝", vec())
        row = store.recent(1)[0]
        self.assertEqual(row["id"], d.id)
        self.assertIn("boundary", row["signals"])
        self.assertGreater(row["propensity"], 0)


class TestConfigDefaults(unittest.TestCase):
    def test_defaults_present(self):
        cfg = settings.load("refusal")
        for key in ("threshold", "refuse_per_hour", "tsundere_per_hour", "tsundere_level",
                    "blacklist", "weights"):
            self.assertIn(key, cfg)


if __name__ == "__main__":
    unittest.main()
