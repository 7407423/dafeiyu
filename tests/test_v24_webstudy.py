"""v24 刷抖音学梗：解析、落盘、以及「自己学的词」优先于只读快照。

这条链路的核心承诺是 **0 API 花费**：
  · 看：本机 Edge（有头）
  · 理解：网页版 chat.deepseek.com（免费额度）
  · 记：本地 JSON + 本地 SQLite
这里测的是「记」这一半（不需要浏览器、不需要登录，跑得飞快）。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .base import BaseCase

from core import memewiki, webstudy


class TestMemeParsing(BaseCase):
    def test_parse_pairs(self):
        text = "\n".join([
            "奶蛙|用来自嘲热情讨好却没人理，比如「我简直奶蛙本蛙」",
            "- 纳味|形容说话带一股反差萌的土味，可当夸也可当损",
            "  绝绝子 ｜ 表达极度赞美，等于「太绝了」",
            "说明：以上都是从评论里挑的",
        ])
        rows = webstudy.parse_meme_lines(text)
        titles = [r["title"] for r in rows]
        self.assertEqual(titles, ["奶蛙", "纳味", "绝绝子"])
        self.assertTrue(rows[0]["usage"].startswith("用来自嘲"))
        self.assertEqual(rows[0]["source"], "抖音+网页版DeepSeek")

    def test_parse_ignores_header_and_noise(self):
        text = "\n".join([
            "词|怎么用",
            "这句不是梗|但格式对，会被收（标题在 20 字内）",
            "太长的一个标题会被丢掉因为超过二十个字了吧|用法",
            "|只有用法没有词",
            "只有词没有用法",
        ])
        rows = webstudy.parse_meme_lines(text)
        titles = [r["title"] for r in rows]
        self.assertIn("这句不是梗", titles)
        self.assertNotIn("词", titles, "表头不能当词条")
        self.assertTrue(all(len(t) <= 20 for t in titles))

    def test_parse_empty(self):
        self.assertEqual(webstudy.parse_meme_lines(""), [])
        self.assertEqual(webstudy.parse_meme_lines("无"), [])


class TestLearnedTerms(BaseCase):
    def setUp(self) -> None:
        super().setUp()
        self._tmp = Path(tempfile.mkdtemp(prefix="webstudy-")) / "terms.json"
        self._old = webstudy.TERMS_FILE
        webstudy.TERMS_FILE = self._tmp

    def tearDown(self) -> None:
        webstudy.TERMS_FILE = self._old

    def test_save_and_load(self):
        webstudy.save_terms([{"title": "奶蛙", "usage": "自嘲被冷落"}])
        webstudy.save_terms([{"title": "纳味", "usage": "土味反差萌"}])
        rows = webstudy.load_terms()
        self.assertEqual({r["title"] for r in rows}, {"奶蛙", "纳味"})

    def test_save_merges_same_title(self):
        webstudy.save_terms([{"title": "奶蛙", "usage": "第一版"}])
        webstudy.save_terms([{"title": "奶蛙", "usage": "第二版"}])
        rows = webstudy.load_terms()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["usage"], "第二版")

    def test_corrupt_file_is_empty_not_crash(self):
        self._tmp.parent.mkdir(parents=True, exist_ok=True)
        self._tmp.write_text("{ not json", encoding="utf-8")
        self.assertEqual(webstudy.load_terms(), [])

    def test_learned_terms_win_over_snapshot(self):
        """自己刷到的梗优先于只读快照 —— 那是「她刚学的」，比快照新。"""
        webstudy.save_terms([{"title": "奶蛙", "usage": "抖音评论区学到的：自嘲被冷落",
                              "source": "抖音+网页版DeepSeek"}])
        data = memewiki.search("奶蛙")
        self.assertTrue(data["found"])
        self.assertEqual(data["title"], "奶蛙", "不能再落到前缀兜底的「奶蛙之母」")
        self.assertIn("自嘲被冷落", data["usage"])
        self.assertEqual(data["source"], "抖音+网页版DeepSeek")

    def test_learned_inside_match(self):
        webstudy.save_terms([{"title": "奶蛙", "usage": "自嘲"}])
        data = memewiki.search("奶蛙是什么")
        self.assertTrue(data["found"])
        self.assertEqual(data["title"], "奶蛙")
        self.assertEqual(data["match"], "inside")

    def test_status_counts_user_terms(self):
        webstudy.save_terms([{"title": "奶蛙", "usage": "自嘲"}])
        self.assertEqual(memewiki.status()["user_terms"], 1)


if __name__ == "__main__":
    unittest.main()
