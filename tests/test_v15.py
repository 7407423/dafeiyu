"""v15 表情包字典：查表 0 花费、用一次记一次、人工批注。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .base import BaseCase

from core import db, sticker


class TestStickerDict(BaseCase):
    def test_remember_and_lookup(self):
        sha = "a" * 64
        self.assertIsNone(sticker.lookup(sha))
        self.assertTrue(sticker.remember(sha, summary="叉腰比 ok，很得意", concepts=["得意", "ok"]))
        hit = sticker.lookup(sha)
        self.assertIsNotNone(hit)
        self.assertIn("得意", hit["summary"])
        self.assertEqual(hit["hits"], 2, "remember 记 1 次，lookup 再加 1 次")

    def test_second_lookup_is_free(self):
        sha = "b" * 64
        sticker.remember(sha, summary="哭唧唧")
        first = sticker.lookup(sha)
        second = sticker.lookup(sha)
        self.assertEqual(second["hits"], first["hits"] + 1)
        self.assertEqual(second["summary"], first["summary"])

    def test_annotate(self):
        sha = "c" * 64
        sticker.remember(sha, summary="黄团子笑")
        self.assertTrue(sticker.annotate(sha, "老大叫它「好耶」"))
        self.assertIn("好耶", sticker.lookup(sha)["note"])

    def test_observe_usage_enriches(self):
        sha = "d" * 64
        sticker.remember(sha, summary="竖大拇指")
        sticker.observe_usage(sha, "他说搞定了")
        sticker.observe_usage(sha, "他说搞定了")      # 重复语境不重复记
        sticker.observe_usage(sha, "他说再来一局")
        data = sticker.lookup(sha)
        self.assertEqual(data["usages"], 3)
        self.assertEqual(data["contexts"], ["他说搞定了", "他说再来一局"])
        text = sticker.describe(data)
        self.assertIn("这么用", text)

    def test_describe_plain(self):
        self.assertEqual(sticker.describe(None), "")
        self.assertEqual(sticker.describe({"summary": "笑"}), "笑")

    def test_sha256_file(self):
        path = Path(tempfile.mkdtemp()) / "a.bin"
        path.write_bytes(b"hello")
        self.assertEqual(len(sticker.sha256_file(str(path))), 64)
        self.assertEqual(sticker.sha256_file(str(path)), sticker.sha256_bytes(b"hello"))
        self.assertEqual(sticker.sha256_file(str(path))[:8], "2cf24dba")

    def test_status_and_entries(self):
        sticker.remember("e" * 64, summary="挥手再见", concepts=["告别"])
        sticker.observe_usage("e" * 64, "他说我走了")
        status = sticker.status()
        self.assertEqual(status["total"], 1)
        entries = sticker.all_entries()
        self.assertEqual(entries[0]["sha256"], "e" * 64)
        self.assertEqual(entries[0]["concepts"], ["告别"])

    def test_columns_exist(self):
        cols = {r["name"] for r in db.q("PRAGMA table_info(sticker_cache)")}
        for name in ("usages", "contexts", "last_used_at", "kind", "note"):
            self.assertIn(name, cols)


if __name__ == "__main__":
    unittest.main()
