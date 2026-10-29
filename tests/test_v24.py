"""v24 梗百科：本地查词 0 花费、查不到就明说、前缀兜底要说清楚是「最接近」。"""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from .base import BaseCase

from core import memewiki


def _make_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE memes (title TEXT PRIMARY KEY, slug TEXT, tags TEXT,
                            usage TEXT, origin TEXT, other TEXT, summary TEXT);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        """
    )
    rows = [
        ("奶蛙之母", "nai-wa-zhi-mu", "文字梗、奶蛙、奶龙", "用来称呼最早生成奶蛙形象的用户。", "出自一次赛博考古。", "", ""),
        ("奶蛙被嫌弃", "nai-wa", "动画梗、奶龙、自嘲", "表达单方面付出却得不到回应。", "源于奶龙的二创。", "", ""),
        ("绝绝子", "jue-jue-zi", "网络用语、赞美", "表达高度赞美，意为太绝了。", "", "", ""),
        ("YYDS", "yyds", "缩写、赞美", "永远的神。", "", "", ""),
        ("测试专用梗", "test", "冷门、测试", "只用来测 tag 命中。", "", "", ""),
    ]
    conn.executemany("INSERT INTO memes VALUES (?,?,?,?,?,?,?)", rows)
    conn.execute("INSERT INTO meta VALUES ('built_at', '2026-10-26 19:07:22')")
    conn.execute("INSERT INTO meta VALUES ('count', '5')")
    conn.commit()
    conn.close()


class TestMemeWiki(BaseCase):
    def setUp(self) -> None:
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="memewiki-test-"))
        self.db = self.tmp / "memes.db"
        _make_db(self.db)
        self._old_db = memewiki.DB_PATH
        self._old_state = memewiki.STATE_FILE
        memewiki.DB_PATH = self.db
        memewiki.STATE_FILE = self.tmp / "state.json"
        memewiki._conn = None

    def tearDown(self) -> None:
        memewiki.DB_PATH = self._old_db
        memewiki.STATE_FILE = self._old_state
        memewiki._conn = None

    # ── 查询词提取 ──────────────────────────────────────────────────────
    def test_extract_query(self):
        self.assertEqual(memewiki.extract_query("奶蛙是什么"), "奶蛙")
        self.assertEqual(memewiki.extract_query("奶蛙"), "奶蛙")
        self.assertEqual(memewiki.extract_query("@大肥鱼 绝绝子啥意思"), "绝绝子")
        self.assertEqual(memewiki.extract_query("大肥鱼 奶蛙怎么用"), "奶蛙")
        self.assertEqual(memewiki.extract_query("在吗"), "")
        self.assertEqual(memewiki.extract_query("这个梗是什么意思"), "")

    # ── 匹配层级 ────────────────────────────────────────────────────────
    def test_exact_hit(self):
        data = memewiki.search("绝绝子")
        self.assertTrue(data["found"])
        self.assertEqual(data["match"], "exact")
        self.assertEqual(data["title"], "绝绝子")
        self.assertIn("赞美", data["usage"])

    def test_prefix_hit_is_labelled(self):
        """「奶蛙」没有独立词条 → 给最接近的，并且**不能**说成同名。"""
        data = memewiki.search("奶蛙")
        self.assertTrue(data["found"])
        self.assertEqual(data["match"], "prefix")
        self.assertEqual(data["title"], "奶蛙之母", "应取最短的前缀命中")
        block = memewiki.block("奶蛙")
        self.assertIn("没有同名条目", block)
        self.assertIn("奶蛙之母", block)

    def test_case_insensitive_prefix(self):
        data = memewiki.search("yyds")
        self.assertTrue(data["found"])
        self.assertEqual(data["title"], "YYDS")

    def test_miss_is_explicit(self):
        data = memewiki.search("完全不存在的词xyz")
        self.assertFalse(data["found"])
        self.assertEqual(memewiki.block("完全不存在的词xyz"), "", "查不到就不占 token")

    def test_block_contains_usage_and_tags(self):
        block = memewiki.block("绝绝子")
        self.assertIn("梗百科", block)
        self.assertIn("怎么用", block)
        self.assertIn("网络用语", block)
        self.assertLessEqual(len(block), 760)

    # ── 学习 ────────────────────────────────────────────────────────────
    def test_learn_records_note_and_hits(self):
        self.assertTrue(memewiki.learn("绝绝子", note="老大说这是个夸人的词", context="群里有人说绝绝子"))
        got = memewiki.learned("绝绝子")
        self.assertEqual(got["hits"], 0)
        self.assertIn("夸人", got["note"])
        self.assertIn("群里有人说绝绝子", got["contexts"])
        block = memewiki.block("绝绝子")
        self.assertIn("我自己的理解", block)

    def test_search_with_record_counts_usage(self):
        memewiki.search("绝绝子", record=True, context="测试语境")
        memewiki.search("绝绝子", record=True, context="测试语境")
        self.assertEqual(memewiki.learned("绝绝子")["hits"], 2)

    def test_state_is_capped(self):
        memewiki.cfg_override = None
        for i in range(30):
            memewiki.learn(f"词{i}", note=f"第{i}个")
        self.assertLessEqual(len(memewiki.all_learned()), 40, "学习条数要有上限，别无限长")

    # ── 状态 ────────────────────────────────────────────────────────────
    def test_status(self):
        st = memewiki.status()
        self.assertTrue(st["available"])
        self.assertEqual(st["count"], 5)
        self.assertEqual(st["built_at"], "2026-10-26 19:07:22")
        self.assertEqual(st["learned"], 0)


if __name__ == "__main__":
    unittest.main()
