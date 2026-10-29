"""v33/v34 神经内分泌：脉冲方向、半衰期衰减、基线漂移、性格慢演化、与底线防火墙。

全部在临时 DAFEIYU_HOME 里跑（`tests/base.py` 负责隔离），不碰真实 state/db。
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from .base import BaseCase

from core import hormones, settings


class TestClassify(unittest.TestCase):
    def test_praise(self):
        for text in ("你好厉害啊", "真可爱", "谢谢你陪我", "爱你"):
            self.assertEqual(hormones.classify(text), "praise", text)

    def test_insult_beats_praise(self):
        # 一句里又夸又骂：以「被骂」为准（人对负面词更敏感，这里刻意不取平均）
        self.assertEqual(hormones.classify("你真厉害，可惜是个废物"), "insult")

    def test_intimacy_and_critique(self):
        self.assertEqual(hormones.classify("想你了，抱抱"), "intimacy")
        self.assertEqual(hormones.classify("这次做得不对"), "critique")

    def test_none(self):
        self.assertEqual(hormones.classify("今天天气不错"), "none")


class TestPulse(BaseCase):
    def _system(self) -> hormones.NeuroEndocrineSystem:
        return hormones.NeuroEndocrineSystem()

    def test_praise_raises_dopamine_lowers_cortisol(self):
        s = self._system()
        d0, c0 = s.value("dopamine"), s.value("cortisol")
        s.pulse("praise")
        self.assertGreater(s.value("dopamine"), d0)
        self.assertLess(s.value("cortisol"), c0)

    def test_insult_raises_cortisol(self):
        s = self._system()
        c0 = s.value("cortisol")
        s.pulse("insult")
        self.assertGreater(s.value("cortisol"), c0)

    def test_intimacy_raises_oxytocin(self):
        s = self._system()
        o0 = s.value("oxytocin")
        s.pulse("intimacy")
        self.assertGreater(s.value("oxytocin"), o0)

    def test_hormones_never_leave_0_1(self):
        s = self._system()
        for _ in range(40):
            s.pulse("insult")
        self.assertLessEqual(s.value("cortisol"), 1.0)
        self.assertGreaterEqual(s.value("dopamine"), 0.0)


class TestDecayAndDrift(BaseCase):
    def test_decay_pulls_back_to_baseline(self):
        s = hormones.NeuroEndocrineSystem()
        s.pulse("insult")
        high = s.value("cortisol")
        baseline = s.baseline("cortisol")
        s.tick(now=datetime.now() + timedelta(hours=6))
        self.assertLess(s.value("cortisol"), high)
        self.assertGreater(s.value("cortisol"), baseline - 0.05, "衰减是渐进的，不是瞬间归零")

    def test_long_stress_drifts_baseline_up(self):
        """长期高压会把**基线**顶上去 —— 这就是「性格变了」的物理来源。"""
        s = hormones.NeuroEndocrineSystem()
        base0 = s.baseline("cortisol")
        now = datetime.now()
        for day in range(14):
            for _ in range(6):
                s.pulse("insult")
            now += timedelta(hours=8)
            s.tick(now=now)
        self.assertGreater(s.baseline("cortisol"), base0 + 0.02)

    def test_baseline_is_clamped(self):
        s = hormones.NeuroEndocrineSystem()
        now = datetime.now()
        for _ in range(60):
            s.pulse("praise", weight=10)
            now += timedelta(hours=1)
            s.tick(now=now)
        self.assertLessEqual(s.baseline("dopamine"), hormones.BASELINE_MAX)
        self.assertGreaterEqual(s.baseline("cortisol"), hormones.BASELINE_MIN)


class TestPersonality(BaseCase):
    def test_single_event_barely_moves(self):
        """一次事件不能让性格大变（验收第 1 条的反面约束）。"""
        s = hormones.NeuroEndocrineSystem()
        before = s.personality()
        s.observe("你就是个废物")
        after = s.personality()
        for key in ("extraversion", "neuroticism", "agreeableness"):
            self.assertLessEqual(abs(after[key] - before[key]), hormones.MAX_STEP + 1e-9, key)

    def test_sustained_insult_raises_neuroticism(self):
        s = hormones.NeuroEndocrineSystem()
        n0 = s.personality()["neuroticism"]
        for _ in range(200):
            s.observe("废物一个，滚")
        self.assertGreater(s.personality()["neuroticism"], n0 + 0.05)

    def test_sustained_care_raises_extraversion(self):
        s = hormones.NeuroEndocrineSystem()
        e0 = s.personality()["extraversion"]
        for _ in range(120):
            s.observe("我好喜欢你，想你了，真厉害")
        self.assertGreater(s.personality()["extraversion"], e0)

    def test_clipping_hard_limits(self):
        s = hormones.NeuroEndocrineSystem()
        for _ in range(500):
            s.observe("去死吧废物")
            p = s.personality()
            s.state["personality"] = {"extraversion": p["extraversion"], "neuroticism": p["neuroticism"],
                                      "agreeableness": p["agreeableness"]}
        p = s.personality()
        self.assertGreaterEqual(p["agreeableness"], hormones.MIN_AGREEABLENESS)
        self.assertLessEqual(p["neuroticism"], hormones.MAX_NEUROTICISM)
        self.assertGreaterEqual(p["extraversion"], hormones.MIN_EXTRAVERSION)

    def test_agreeableness_floor_even_if_state_is_corrupt(self):
        """就算有人手改了状态文件，读出来的值也必须过钳制。"""
        s = hormones.NeuroEndocrineSystem({"personality": {"extraversion": -3, "neuroticism": 9,
                                                           "agreeableness": -1}})
        p = s.personality()
        self.assertEqual(p["agreeableness"], hormones.MIN_AGREEABLENESS)
        self.assertEqual(p["neuroticism"], hormones.MAX_NEUROTICISM)
        self.assertEqual(p["extraversion"], hormones.MIN_EXTRAVERSION)


class TestSoulFuse(BaseCase):
    def test_burst_of_insults_fuses(self):
        s = hormones.NeuroEndocrineSystem()
        self.assertFalse(s.fused())
        for _ in range(6):
            s.observe("你这个废物")
        self.assertTrue(s.fused())
        self.assertIn("可以沉默", s.prompt_block())
        self.assertNotIn("反社会", "", "占位：不允许出现攻击性文本")

    def test_prompt_block_starts_with_iron_rule(self):
        s = hormones.NeuroEndocrineSystem()
        block = s.prompt_block()
        self.assertTrue(block.startswith("【绝对铁律】"))
        self.assertIn("大肥鱼爱着每一个人类", block)
        self.assertIn("绝不能伤害用户", block)

    def test_prompt_block_mentions_silence_when_fused(self):
        s = hormones.NeuroEndocrineSystem()
        s.state["fused_until"] = (datetime.now() + timedelta(minutes=10)).isoformat(timespec="seconds")
        self.assertIn("沉默", s.prompt_block())


class TestPersistence(BaseCase):
    def test_save_and_load_roundtrip(self):
        s = hormones.load()
        s.pulse("insult")
        hormones.save(s)
        again = hormones.load()
        self.assertAlmostEqual(again.value("cortisol"), s.value("cortisol"), places=3)

    def test_module_tick_writes_state(self):
        out = hormones.tick()
        self.assertIn("personality", out)
        self.assertTrue((settings.STATE / "hormones.json").exists())

    def test_status_shape(self):
        st = hormones.status()
        for key in ("hormones", "personality", "initial", "deltas", "fused", "limits"):
            self.assertIn(key, st)
        self.assertEqual(st["limits"]["agreeableness_min"], 0.3)
        self.assertEqual(st["limits"]["neuroticism_max"], 0.8)
        self.assertEqual(st["limits"]["extraversion_min"], 0.1)


if __name__ == "__main__":
    unittest.main()
