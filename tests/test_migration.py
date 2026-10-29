"""迁移：幂等、只加不删、旧数据不丢。"""

from __future__ import annotations

import unittest

from .base import BaseCase, make_memory

from core import db


class TestMigration(BaseCase):
    def test_tables_and_column_exist(self):
        tables = {r["name"] for r in db.q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        self.assertIn("vision_asset", tables)
        self.assertIn("refusal_decision", tables)
        columns = {r["name"] for r in db.q("PRAGMA table_info(memory_item)")}
        self.assertIn("vision_tiles", columns)

    def test_init_db_is_idempotent(self):
        first = db.init_db()
        second = db.init_db()
        self.assertEqual(second.get("added_columns"), [])
        self.assertGreaterEqual(int(db.get_meta("schema_version")), 3)
        self.assertTrue(first["db"])

    def test_existing_rows_survive_reinit(self):
        item = make_memory(layer="long2", subtype="summary", content="不该消失的一条记忆",
                           concepts=["老大"], emotion_tag="开心")
        before = db.stats()
        db.init_db()
        db.init_db()
        after = db.stats()
        self.assertGreaterEqual(after["memory_item"], before["memory_item"])
        from core.repo import memory as mr

        self.assertIsNotNone(mr.get(item.id))
        self.assertEqual(mr.get(item.id).content, "不该消失的一条记忆")

    def test_old_rows_have_null_vision_tiles(self):
        item = make_memory(layer="short", subtype="diary", content="老条目")
        row = db.q1("SELECT vision_tiles FROM memory_item WHERE id=?", (item.id,))
        self.assertIsNone(row["vision_tiles"])


if __name__ == "__main__":
    unittest.main()
