"""v13 好奇心引擎 + v14 冷存储/费用开关 + v12 节律/受挫/指纹/叙事。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from .base import BaseCase

from core import circadian, cost, curiosity_engine, db, frustration, relationship, self_narrative
from core.language import fingerprint
from core.memory import coldstore
from core.repo import learning as lr


class TestCuriosityEngine(BaseCase):
    def test_urgency_range_and_order(self):
        now = datetime.now()
        fresh = {"specific_gap_score": 0.9, "last_explored_at": "", "explore_count": 0,
                 "progress": 0.5, "boredom": 0.0}
        stale = {"specific_gap_score": 0.0, "last_explored_at": now.isoformat(timespec="seconds"),
                 "explore_count": 10, "progress": 0.0, "boredom": 0.9}
        a = curiosity_engine.calculate_urgency(fresh, now)
        b = curiosity_engine.calculate_urgency(stale, now)
        self.assertGreater(a, b)
        for value in (a, b):
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)

    def test_boredom_accumulates_when_stalled(self):
        domain = {"progress": 0.0, "boredom": 0.1, "explore_count": 0}
        curiosity_engine.update_boredom(domain, hours=2)
        self.assertGreater(domain["boredom"], 0.1)
        domain2 = {"progress": 0.5, "boredom": 0.4, "explore_count": 0}
        curiosity_engine.update_boredom(domain2, hours=2)
        self.assertLess(domain2["boredom"], 0.4)

    def test_picks_high_gap_domain(self):
        curiosity_engine.set_config(threshold=0.3)
        data = curiosity_engine.ensure_domains()
        name = next(iter(data["domains"]))
        curiosity_engine.bump_gap(name, 1.0)
        pick = curiosity_engine.get_next_learning_target()
        self.assertIsNotNone(pick)
        self.assertEqual(pick["domain"], name)

    def test_tick_creates_autonomous_intent(self):
        curiosity_engine.set_config(threshold=0.2, enabled=True)
        data = curiosity_engine.ensure_domains()
        for domain in data["domains"].values():
            domain["specific_gap_score"] = 0.9
        settings_save = __import__("core.settings", fromlist=["write_state"])
        settings_save.write_state("curiosity_engine.json", data)
        before = lr.intent_queue(limit=50)
        out = curiosity_engine.tick()
        self.assertTrue(out.get("target"), out)
        after = lr.intent_queue(limit=50)
        self.assertGreater(len(after), len(before))
        self.assertEqual(after[-1].source, "autonomous")

    def test_disabled_skips(self):
        curiosity_engine.set_config(enabled=False)
        out = curiosity_engine.tick()
        self.assertIn("关闭", out.get("skipped", ""))

    def test_budget_blocks(self):
        curiosity_engine.set_config(enabled=True, budget_limit_per_day=0.01)
        cost.record_event("curiosity_autonomous", task="learning", actual=0.5, source="engine")
        blocked, why = curiosity_engine.budget_blocked()
        self.assertTrue(blocked)
        out = curiosity_engine.tick()
        self.assertIn("额度", out.get("skipped", ""))

    def test_record_outcome_updates(self):
        curiosity_engine.bump_gap("语言风格", 0.5)
        curiosity_engine.record_outcome("语言风格", error_before=0.8, error_after=0.2, note="学到边界感")
        st = {d["name"]: d for d in curiosity_engine.status()["domains"]}
        item = st["语言风格"]
        self.assertGreater(item["progress"], 0)
        self.assertEqual(item["explored"], 1)
        self.assertLess(item["gap"], 0.5)


class TestCostCuriosity(BaseCase):
    def test_tag_and_stats(self):
        cost.record_event("curiosity_autonomous", task="learning", actual=0.2, source="engine")
        cost.record_event("curiosity_autonomous", task="learning", actual=0.3, source="engine")
        stats = cost.curiosity_stats()
        self.assertAlmostEqual(stats["total"], 0.5, places=3)
        self.assertEqual(stats["calls"], 2)
        data = cost.attribute()
        names = {item["tag"]: item["name"] for item in data["by_tag"]}
        self.assertEqual(names.get("curiosity_autonomous"), "自主好奇心学习")

    def test_recall_tag_present(self):
        cost.record_event("memory_recall", task="recall", actual=0.0)
        data = cost.attribute()
        tags = {item["tag"] for item in data["by_tag"]}
        self.assertIn("memory_recall", tags)


class TestColdStore(BaseCase):
    def test_recall_trigger(self):
        self.assertTrue(coldstore.is_recall_question("我三个小时前说我想吃什么来着？"))
        self.assertTrue(coldstore.is_recall_question("你还记得我之前说的那个吗"))
        self.assertFalse(coldstore.is_recall_question("今天天气不错"))
        self.assertFalse(coldstore.is_recall_question("帮我写个函数"))

    def test_remember_search_format(self):
        coldstore.remember("user", "我晚上想吃红苹果", conv="private:owner", is_owner=True)
        coldstore.remember("assistant", "好呀，那我记着了", conv="private:owner")
        rows = coldstore.search(["红苹果"], conv="private:owner")
        self.assertTrue(rows)
        block = coldstore.format_block(rows)
        self.assertIn("过去18小时", block)
        self.assertIn("红苹果", block)

    def test_18h_boundary(self):
        old = (datetime.now() - timedelta(hours=20)).isoformat(timespec="seconds")
        coldstore.remember("user", "昨天说的事", ts=old)
        coldstore.remember("user", "刚才说的事")
        self.assertEqual(len(coldstore.recent()), 1)
        self.assertEqual(coldstore.purge(), 1)

    def test_no_trigger_no_context(self):
        coldstore.remember("user", "五小时前我说想吃火锅")
        self.assertFalse(coldstore.is_recall_question("在干嘛"))


class TestCircadian(BaseCase):
    def test_factor_shape(self):
        fac = circadian.factor()
        self.assertGreaterEqual(fac["energy"], 0.3)
        self.assertLessEqual(fac["energy"], 1.3)
        self.assertIn("chitchat", fac)
        self.assertIn("latency", fac)

    def test_sleep_window(self):
        self.assertTrue(circadian.in_sleep_window(datetime(2026, 1, 1, 1, 0)))
        self.assertFalse(circadian.in_sleep_window(datetime(2026, 1, 1, 15, 0)))
        out = circadian.sleep_loyalty(datetime(2026, 1, 1, 1, 0))
        self.assertTrue(out["active"])
        self.assertGreater(out["boost"], 0)

    def test_hint(self):
        self.assertIsInstance(circadian.hint(), str)


class TestFrustration(BaseCase):
    def test_bump_to_cold_war(self):
        for _ in range(4):
            frustration.bump(0.2, "被拒")
        self.assertTrue(frustration.is_cold_war())
        self.assertIn("别扭", frustration.hint())

    def test_decay(self):
        frustration.bump(0.8, "很生气")
        later = datetime.now() + timedelta(hours=10)
        frustration.decay(later)
        self.assertLess(frustration.current(), 0.2)

    def test_soothe(self):
        frustration.bump(0.7, "生气")
        frustration.soothe(0.5, "道歉了")
        self.assertLess(frustration.current(), 0.3)
        self.assertFalse(frustration.is_cold_war())


class TestFingerprint(BaseCase):
    def test_observe_and_hint(self):
        for text in ("你在干嘛呀……", "哼，才不理你呢", "好嘛好嘛，我知道啦"):
            fingerprint.observe(text)
        st = fingerprint.status()
        self.assertGreater(st["samples"], 0)
        self.assertTrue(st["particles"] or st["punct"])

    def test_hint_needs_samples(self):
        self.assertEqual(fingerprint.hint(), "")


class TestNarrative(BaseCase):
    def test_generate_without_llm(self):
        out = self_narrative.generate(use_llm=False)
        self.assertIn("今天是", out["text"])
        self.assertTrue(self_narrative.hint())
        self.assertEqual(len(self_narrative.status()["days"]), 1)


class TestSchedulerWiring(BaseCase):
    def test_curiosity_job_registered(self):
        import inspect

        from core.cognition import scheduler

        source = inspect.getsource(scheduler.start)
        self.assertIn("curiosity_engine_tick", source)
        self.assertIn("job_curiosity_engine", source)
        self.assertIn("curiosity_", scheduler.MANAGED_PREFIXES)

    def test_daily_jobs_include_new_modules(self):
        import inspect

        from core.cognition import consolidate

        source = inspect.getsource(consolidate.daily)
        for key in ("coldstore", "circadian", "fingerprint", "self_narrative", "frustration"):
            self.assertIn(key, source)


class TestCostReporting(BaseCase):
    def test_event_time_is_preserved(self):
        """导入历史账本时必须写事件真实时间，不能全写成"现在"。"""
        cost.record_event("chat", task="dialogue", actual=0.01, source="bridge",
                          at="2026-10-26T23:09:18")
        row = db.q1("SELECT t FROM cost_event ORDER BY rowid DESC LIMIT 1")
        self.assertEqual(row["t"], "2026-10-26T23:09:18")

    def test_message_split_shape(self):
        cost.record_event("chitchat", task="chitchat", actual=0.002)
        cost.record_event("other", task="bridge-turn", actual=0.05, source="bridge",
                          meta={"key": "private:1"})
        split = cost.message_split(days=7)
        self.assertIn("send", split)
        self.assertIn("reply", split)
        self.assertIn("backend", split)
        self.assertAlmostEqual(split["send"]["cost"], 0.002, places=4)
        self.assertAlmostEqual(split["reply"]["cost"], 0.05, places=4)

    def test_context_simulation_grows(self):
        sim = cost.context_simulation((10, 30, 100))
        table = sim["table"]
        self.assertEqual([row["days"] for row in table], [10, 30, 100])
        self.assertLess(table[0]["tokens"], table[1]["tokens"])
        self.assertLess(table[1]["tokens"], table[2]["tokens"])


    def test_bridge_tag_is_honored(self):
        """桥接从 v14 起在账本行里带 tag，导入时要用它当 feature_tag。"""
        import json
        import tempfile
        from pathlib import Path

        from core import cost

        tmp = Path(tempfile.mkdtemp()) / "token-usage.jsonl"
        tmp.write_text(json.dumps({
            "k": "turn", "t": 1793250082303, "sid": "s1", "key": "private:1", "seq": 1,
            "turn": 1, "step": 1, "retry": 0, "tag": "chat", "model": "m",
            "b": {"cacheMiss": 100, "output": 10},
        }) + "\n", encoding="utf-8")
        original = cost.BRIDGE_LEDGER
        cost.BRIDGE_LEDGER = tmp
        try:
            cost.import_ledgers(bridge=True, engine=False)
            row = db.q1("SELECT feature_tag FROM cost_event WHERE source='bridge'")
            self.assertIsNotNone(row)
            self.assertEqual(row["feature_tag"], "chat")
        finally:
            cost.BRIDGE_LEDGER = original


if __name__ == "__main__":
    unittest.main()
