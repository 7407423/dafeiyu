"""v12 底座：灵魂锚点（校验/回退/报警）、Prompt 注入、能力自检、迁移幂等。"""

from __future__ import annotations

import unittest

from .base import BaseCase

import core_ethos
from core import db, selfcheck, settings
from core.llm import provider


class TestEthos(BaseCase):
    def test_verify_ok(self):
        report = core_ethos.verify()
        self.assertTrue(report["ok"], report["message"])
        self.assertTrue(report["canonical_ok"])
        self.assertEqual(report["actual"], report["expected"])

    def test_tamper_detected_and_falls_back(self):
        original = core_ethos.SOUL_ANCHOR
        try:
            core_ethos.SOUL_ANCHOR = "大肥鱼只爱老大一个人。"
            report = core_ethos.verify()
            self.assertFalse(report["ok"])
            self.assertFalse(report["canonical_ok"])
            # 篡改后对外仍返回可信的锚点
            anchor, _mission = core_ethos.settled()
            self.assertEqual(anchor, original)
        finally:
            core_ethos.SOUL_ANCHOR = original

    def test_alarm_writes_state_and_audit(self):
        from core import settings

        original = core_ethos.SOUL_ANCHOR
        try:
            core_ethos.SOUL_ANCHOR = "改过的锚点"
            report = core_ethos.alarm_once()
            self.assertFalse(report["ok"])
            data = settings.read_state("soul_alert.json", {})
            self.assertTrue(data.get("at"))
            rows = db.q("SELECT * FROM audit_event WHERE entity_kind='ethos' AND action='tampered'")
            self.assertTrue(rows)
        finally:
            core_ethos.SOUL_ANCHOR = original

    def test_soul_block_is_stable(self):
        self.assertIn("核心灵魂设定", core_ethos.soul_block())
        self.assertIn("补全", core_ethos.soul_block())
        self.assertEqual(core_ethos.soul_block(), core_ethos.SOUL_BLOCK)


class TestSoulInjection(BaseCase):
    def test_soul_prompt_prepended_once(self):
        block = core_ethos.soul_block()
        text = provider._guard_ethos("今天天气怎么样")
        self.assertTrue(text.startswith(block))
        again = provider._guard_ethos(text)
        self.assertEqual(again.count(block), 1, "同一段 prompt 不该重复注入")

    def test_soul_prompt_covers_all_calls(self):
        """所有调用都过 run()，注入点只有一处。"""
        import inspect

        source = inspect.getsource(provider.run)
        self.assertIn("_guard_ethos", source)


class TestCapabilities(BaseCase):
    def test_write_and_read(self):
        report = selfcheck.write()
        self.assertIn("ffmpeg_available", report)
        self.assertIn("pillow_animation_available", report)
        self.assertTrue(report["ready"]["animation"], "QImage 路线永远可用")
        cached = selfcheck.read()
        self.assertEqual(cached["root"], report["root"])

    def test_summary_line(self):
        selfcheck.write()
        line = selfcheck.summary()
        self.assertIn("自检", line)
        self.assertIn("动图", line)


class TestMigrationV12(BaseCase):
    def test_version_and_tables(self):
        self.assertGreaterEqual(int(db.get_meta("schema_version")), 12)
        tables = {r["name"] for r in db.q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        self.assertIn("pending_topic", tables)
        self.assertIn("ethos_audit", tables)

    def test_idempotent(self):
        db.init_db()
        self.assertEqual(db.init_db().get("added_columns"), [])

    def test_pending_topic_shape(self):
        cols = {r["name"] for r in db.q("PRAGMA table_info(pending_topic)")}
        for name in ("session_tag", "conv", "topic", "node_ids", "opened_at", "status"):
            self.assertIn(name, cols)


class TestLearningWindow(BaseCase):
    """1.1 唯一配置源：时间必须从 config/app.json → learning 算出来。"""

    def test_config_shape(self):
        cfg = settings.learning()
        self.assertEqual(cfg["window_start"], "00:00")
        self.assertEqual(cfg["window_end"], "01:00")
        self.assertEqual(cfg["self_dialogue_start"], "01:30")   # window_end + 30
        self.assertEqual(cfg["self_dialogue_end"], "02:00")     # + 30 分钟时长
        self.assertEqual(cfg["consolidate_at"], "01:10")
        self.assertEqual(cfg["timezone"], "Asia/Shanghai")

    def test_in_window_crosses_midnight(self):
        from datetime import datetime

        self.assertTrue(settings.in_window(datetime(2026, 1, 1, 0, 30), 23 * 60, 60))
        self.assertFalse(settings.in_window(datetime(2026, 1, 1, 12, 0), 23 * 60, 60))
        self.assertTrue(settings.in_window(datetime(2026, 1, 1, 0, 30), 0, 60))
        self.assertFalse(settings.in_window(datetime(2026, 1, 1, 2, 30), 0, 60))

    def test_executor_uses_config(self):
        from datetime import datetime

        from core.learning import executor, selfdialog

        self.assertTrue(executor.window_open(datetime(2026, 1, 1, 0, 30)))
        self.assertFalse(executor.window_open(datetime(2026, 1, 1, 2, 30)))
        self.assertTrue(selfdialog.window_open(datetime(2026, 1, 1, 1, 40)))
        self.assertFalse(selfdialog.window_open(datetime(2026, 1, 1, 2, 30)))

    def test_scheduler_job_ids_are_prefixed(self):
        """启动时按前缀清旧 job，所以 id 必须带前缀。"""
        import inspect

        from core.cognition import scheduler

        source = inspect.getsource(scheduler.start)
        for job_id in ("learning_run", "self_dialogue_run", "daily_consolidate", "archive_daily"):
            self.assertIn(job_id, source)
        self.assertIn("_clear_managed", source)


class TestPendingTopic(BaseCase):
    """2.1 未完成话题：断开时留下，冷启动优先，72 小时降级。"""

    def _session_with_open_node(self):
        from core.thought import session, turn

        turn.record_turn("private:owner", user_text="我们以后要不要一起养猫", reply_text="……你养得活吗")
        sess = session.current("private:owner")
        node = db.q1("SELECT id FROM thought_node WHERE session_tag=? AND type='step'", (sess["session_tag"],))
        db.ex("UPDATE thought_node SET status='open' WHERE id=?", (node["id"],))
        return sess, node["id"]

    def test_open_for_creates_topic(self):
        from core.thought import pending, session

        sess, node_id = self._session_with_open_node()
        out = session.end("private:owner", reason="test")
        self.assertEqual(out["pending_topics"], 1)
        topics = pending.active(limit=5, conv="private:owner")
        self.assertEqual(len(topics), 1)
        self.assertIn("养猫", topics[0]["topic"])
        self.assertIn(node_id, topics[0]["nodes"])

    def test_active_skips_expired(self):
        from datetime import datetime, timedelta

        from core.thought import pending, session

        self._session_with_open_node()
        session.end("private:owner", reason="test")
        far = datetime.now() + timedelta(hours=80)
        self.assertEqual(pending.active(limit=5, now=far), [])
        self.assertEqual(pending.downgrade_stale(hours=72, now=far), 1)
        row = db.q1("SELECT status FROM pending_topic")
        self.assertEqual(row["status"], "downgraded")

    def test_cold_start_puts_topics_first(self):
        from datetime import datetime, timedelta

        from core.thought import pending, residual, session

        self._session_with_open_node()
        session.end("private:owner", reason="test")
        later = datetime.now() + timedelta(minutes=20)
        session.touch("private:owner", now=later)
        out = residual.cold_start("private:owner", now=later)
        self.assertTrue(out["topics"], "冷启动应带回未完成话题")
        self.assertTrue(out["block"].startswith("【上次没聊完的】"))
        # 注入后 last_seen 被刷新，再过 72 小时才会降级
        topics = pending.active(limit=5, conv="private:owner")
        self.assertTrue(topics)


class TestRelationship(BaseCase):
    """3.2 索取度：0 = 不许索取，65 = 默认，100 = 无上限。"""

    def test_default_is_65(self):
        from core import relationship

        self.assertEqual(relationship.demand_level(), 65)
        self.assertTrue(relationship.demand_gate("ask"))
        self.assertFalse(relationship.demand_gate("cold_war"))

    def test_zero_blocks_everything(self):
        from core import relationship

        relationship.set_demand(0)
        for kind in ("ask", "cling", "demand", "cold_war"):
            self.assertFalse(relationship.demand_gate(kind), kind)
        self.assertIn("不索取", relationship.status()["tone"])

    def test_hundred_allows_everything(self):
        from core import relationship

        relationship.set_demand(100)
        for kind in ("ask", "cling", "demand", "cold_war"):
            self.assertTrue(relationship.demand_gate(kind), kind)

    def test_clamped(self):
        from core import relationship

        relationship.set_demand(-30)
        self.assertEqual(relationship.demand_level(), 0)
        relationship.set_demand(999)
        self.assertEqual(relationship.demand_level(), 100)

    def test_intimacy_clamped_and_milestones(self):
        from core import relationship

        relationship.save(intimacy=98, milestones=[])
        relationship.add_intimacy(10, "老大夸她了")
        data = relationship.load()
        self.assertEqual(data["intimacy"], 100)
        self.assertTrue(data["milestones"])

    def test_policy_hint_follows_dial(self):
        from core import relationship
        from core.emotion import policy

        relationship.set_demand(0)
        self.assertIn("不要主动要", policy.demand_hint())
        relationship.set_demand(100)
        self.assertIn("想缠就缠", policy.demand_hint())


class TestWhitelist(BaseCase):
    def test_parse(self):
        from ui.panels.qqbridge import parse_whitelist

        out = parse_whitelist("100000000\n100000001\ng:100000002\n# 注释\np:123456")
        self.assertEqual(out["private"], [123456, 100000001, 100000000])
        self.assertEqual(out["groups"], [100000002])

    def test_parse_empty(self):
        from ui.panels.qqbridge import parse_whitelist

        self.assertEqual(parse_whitelist(""), {"groups": [], "private": []})
        self.assertEqual(parse_whitelist("乱写的东西"), {"groups": [], "private": []})


if __name__ == "__main__":
    unittest.main()
