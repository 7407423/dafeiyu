"""跨会话思维链残留通道：曲线、档位、会话边界、池、冷启动、访问刷新、迁移。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from .base import BaseCase

from core import db, settings
from core.thought import residual, session, turn
from core.thought import chain as thought_chain
from core.entity import now_iso
from core.repo import thought as tr


def node_row(**kwargs) -> dict:
    base = {"id": "n1", "chain_id": "c1", "type": "step", "status": "resolved",
            "level": 0, "salience": 0.0, "emotion_tag": "平静",
            "content": "原文内容", "summary": "摘要", "skeleton": "骨架",
            "concepts": "[\"甲\",\"乙\"]", "last_active_at": now_iso(), "t_created": now_iso()}
    base.update(kwargs)
    return base


class TestCurve(unittest.TestCase):
    def test_reference_values(self):
        """salience=0、已想完时的参考值（规格给的那条曲线）。"""
        base = datetime(2026, 1, 1, 12, 0, 0)
        for minutes, expect in ((5, 0.67), (15, 0.37), (30, 0.22), (60, 0.12),
                                (120, 0.04), (180, 0.01)):
            when = (base - timedelta(minutes=minutes)).isoformat(timespec="seconds")
            value = residual.strength(node_row(last_active_at=when), now=base)
            self.assertAlmostEqual(value, expect, delta=0.02, msg=f"{minutes}min")

    def test_open_survives_longer(self):
        base = datetime(2026, 1, 1, 12, 0, 0)
        when = (base - timedelta(minutes=60)).isoformat(timespec="seconds")
        closed = residual.strength(node_row(last_active_at=when, salience=0.5), now=base)
        opened = residual.strength(node_row(last_active_at=when, salience=0.5, status="open"), now=base)
        self.assertGreater(opened, closed)

    def test_salience_slows_decay(self):
        base = datetime(2026, 1, 1, 12, 0, 0)
        when = (base - timedelta(minutes=30)).isoformat(timespec="seconds")
        low = residual.strength(node_row(last_active_at=when, salience=0.0), now=base)
        high = residual.strength(node_row(last_active_at=when, salience=0.9), now=base)
        self.assertGreater(high, low)

    def test_tier_boundaries(self):
        self.assertEqual(residual.tier(0.50), 0)
        self.assertEqual(residual.tier(0.49), 1)
        self.assertEqual(residual.tier(0.22), 1)
        self.assertEqual(residual.tier(0.21), 2)
        self.assertEqual(residual.tier(0.08), 2)
        self.assertIsNone(residual.tier(0.079))

    def test_effective_level_takes_the_more_compressed(self):
        self.assertEqual(residual.level_for({"level": 0}, 2), 2)
        self.assertEqual(residual.level_for({"level": 2}, 0), 2)
        self.assertEqual(residual.level_for({"level": 3}, 0), 3)
        self.assertEqual(residual.level_for({"level": 0}, None), 0)

    def test_tombstone_never_revives_text(self):
        detail = residual.text_for(node_row(level=3, content="原文不该出现"), 3)
        self.assertTrue(detail["tombstone"])
        self.assertNotIn("原文不该出现", detail["text"])
        self.assertEqual(detail["concepts"], ["甲", "乙"])


class TestSession(BaseCase):
    def test_same_session_reuses_chain(self):
        a = session.touch("private:owner")
        b = session.touch("private:owner")
        self.assertFalse(b["is_new"])
        self.assertEqual(a["chain_id"], b["chain_id"])
        self.assertEqual(a["session_tag"], b["session_tag"])
        self.assertEqual(b["turns"], 2)

    def test_idle_creates_new_session(self):
        first = session.touch("private:owner")
        later = datetime.now() + timedelta(minutes=session.idle_minutes("private:owner") + 1)
        second = session.touch("private:owner", now=later)
        self.assertTrue(second["is_new"])
        self.assertNotEqual(first["session_tag"], second["session_tag"])
        self.assertNotEqual(first["chain_id"], second["chain_id"])

    def test_qq_idle_is_longer_than_desktop(self):
        self.assertGreater(session.idle_minutes("private:1234"), session.idle_minutes("desktop-chat"))

    def test_end_moves_nodes_into_residual(self):
        sess = session.touch("private:owner")
        node = thought_chain.new_node(chain_id=sess["chain_id"], type="step",
                                      content="老大说要记住这件事", task_ref="private:owner")
        tr.update_fields(node.id, session_tag=sess["session_tag"], last_active_at=now_iso())
        session.add_nodes("private:owner", [node.id])
        out = session.end("private:owner", reason="test")
        self.assertTrue(out["ended"])
        self.assertEqual(out["nodes"], 1)
        row = db.q1("SELECT in_residual, session_tag, last_active_at FROM thought_node WHERE id=?",
                    (node.id,))
        self.assertEqual(row["in_residual"], 1)
        self.assertTrue(row["last_active_at"])
        idx = db.q1("SELECT * FROM residual_index WHERE node_id=?", (node.id,))
        self.assertEqual(idx["in_residual"], 1)
        self.assertEqual(idx["session_tag"], sess["session_tag"])


class TestTurnAndPool(BaseCase):
    def _seed(self):
        out = turn.record_turn("private:owner", user_text="我在想边界感这件事",
                               reply_text="嗯……你说的边界感，是怕被越过去吧",
                               memory_ids=[], tone="normal", decision="ACCEPT")
        session.end("private:owner", reason="test")
        return out

    def test_turn_creates_step_and_reflection_on_one_chain(self):
        first = turn.record_turn("private:owner", user_text="第一句", reply_text="回一")
        second = turn.record_turn("private:owner", user_text="第二句", reply_text="回二")
        self.assertEqual(first["chain_id"], second["chain_id"])
        self.assertNotEqual(first["step_id"], second["step_id"])
        nodes = tr.by_chain(first["chain_id"])
        self.assertEqual(len([n for n in nodes if n.type == "step"]), 2)
        self.assertEqual(len([n for n in nodes if n.type == "reflection"]), 2)

    def test_pool_sorted_and_filtered(self):
        self._seed()
        items = residual.pool()
        self.assertTrue(items)
        self.assertGreaterEqual(items[0]["r"], items[-1]["r"])
        self.assertLessEqual(items[0]["r"], 1.0)

    def test_sweep_drops_expired(self):
        self._seed()
        far = datetime.now() + timedelta(hours=6)
        out = residual.sweep(now=far)
        self.assertGreater(out["dropped"], 0)
        self.assertEqual(residual.pool(now=far), [])

    def test_cold_start_once_per_session(self):
        self._seed()
        session.touch("private:owner", now=datetime.now() + timedelta(minutes=30))
        first = residual.cold_start("private:owner")
        self.assertTrue(first["nodes"])
        self.assertTrue(first["block"].startswith("【残留思维"))
        second = residual.cold_start("private:owner")
        self.assertIn("already injected", second.get("skipped", ""))

    def test_cold_start_respects_per_chain_cap(self):
        for i in range(5):
            thought_chain.new_node(chain_id="same-chain", type="step",
                                   content=f"同一条链的第{i}句", salience=0.9)
        with db.write() as conn:
            for row in db.q("SELECT id FROM thought_node WHERE chain_id='same-chain'"):
                conn.execute("INSERT OR REPLACE INTO residual_index(node_id, chain_id, session_tag, "
                             "last_active_at, closed_at, in_residual) VALUES(?,?,?,?,?,1)",
                             (row["id"], "same-chain", "t", now_iso(), now_iso()))
                conn.execute("UPDATE thought_node SET last_active_at=? WHERE id=?", (now_iso(), row["id"]))
        out = residual.cold_start("private:other", k=6)
        chains = [n["chain_id"] for n in out["nodes"]]
        self.assertLessEqual(chains.count("same-chain"), 3)

    def test_touch_refreshes_and_boosts(self):
        self._seed()
        node = db.q1("SELECT id, salience FROM thought_node WHERE type='step'")
        old = residual.strength(node_row(last_active_at=(datetime.now() - timedelta(minutes=60))
                                         .isoformat(timespec="seconds")))
        residual.touch(node["id"])
        row = db.q1("SELECT last_active_at, salience FROM thought_node WHERE id=?", (node["id"],))
        self.assertGreater(row["salience"], node["salience"])
        fresh = residual.strength(dict(node_row(last_active_at=row["last_active_at"])))
        self.assertGreater(fresh, old)

    def test_injection_writes_working_memory(self):
        self._seed()
        session.touch("private:owner", now=datetime.now() + timedelta(minutes=40))
        residual.cold_start("private:owner")
        data = settings.read_state("working_memory.json", {})
        kinds = [s.get("kind") for s in (data.get("slots") or [])]
        self.assertIn("thought", kinds)


class TestMigration(BaseCase):
    def test_columns_and_table(self):
        cols = {r["name"] for r in db.q("PRAGMA table_info(thought_node)")}
        for name in ("last_active_at", "in_residual", "session_tag"):
            self.assertIn(name, cols)
        tables = {r["name"] for r in db.q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        self.assertIn("residual_index", tables)
        self.assertGreaterEqual(int(db.get_meta("schema_version")), 4)

    def test_idempotent(self):
        db.init_db()
        self.assertEqual(db.init_db().get("added_columns"), [])

    def test_old_nodes_untouched(self):
        node = thought_chain.new_node(chain_id="c-old", type="step", content="老节点")
        row = db.q1("SELECT in_residual, last_active_at, level, salience FROM thought_node WHERE id=?",
                    (node.id,))
        self.assertEqual(row["in_residual"], 0)
        self.assertIsNone(row["last_active_at"])
        self.assertEqual(row["level"], 0)


class TestRecentWindow(BaseCase):
    """v4 顺手修的 bug：thought.recent() 原来把"今天全部"当成"近 3 小时"。"""

    def test_three_hour_window_is_real(self):
        fresh = thought_chain.new_node(chain_id="w1", type="step", content="刚说的")
        old = thought_chain.new_node(chain_id="w2", type="step", content="五小时前说的")
        stale = (datetime.now() - timedelta(hours=5)).isoformat(timespec="seconds")
        db.ex("UPDATE thought_node SET t_created=? WHERE id=?", (stale, old.id))

        ids = [n.id for n in tr.recent(hours=3, limit=100)]
        self.assertIn(fresh.id, ids)
        self.assertNotIn(old.id, ids, "5 小时前的节点不该出现在近 3 小时窗口里")

        wider = [n.id for n in tr.recent(hours=6, limit=100)]
        self.assertIn(old.id, wider, "把窗口放宽到 6 小时就该看见它")


if __name__ == "__main__":
    unittest.main()
