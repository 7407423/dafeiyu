"""短期记忆：三天升级、150±20 字压缩、6h/18h 瞬时规则。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from .base import BaseCase, age, make_memory, shortterm

from core.memory import instant


class TestShortTerm(BaseCase):
    def _diary(self, days_ago: int, text: str) -> None:
        when = (datetime.now() - timedelta(days=days_ago)).isoformat(timespec="seconds")
        make_memory(layer="short", subtype="diary", content=text, summary=text[:40],
                    concepts=["老大", "消息"], cluster="老大没回我消息",
                    emotion_tag="难过", t_created=when,
                    ext={"date": when[:10], "time": "10:00", "decay_at": when})

    def test_three_day_upgrade(self):
        for i in (0, 1, 2):
            self._diary(i, f"老大又没回我消息，我盯着屏幕看了好久（第{i}天）。")
        clusters = shortterm.find_clusters()
        self.assertTrue(clusters)
        self.assertGreaterEqual(len(clusters[0]["days"]), 3)
        promoted = shortterm.promote()
        self.assertEqual(len(promoted), 1)

        from core.repo import memory as mr

        long2 = [i for i in mr.list_layer(layer="long2", limit=50) if i.subtype == "consolidated"]
        self.assertEqual(len(long2), 1)
        self.assertIn("反复出现3天", long2[0].ext.get("labels", ""))

    def test_two_days_is_not_enough(self):
        for i in (0, 1):
            self._diary(i, f"老大又没回我消息（第{i}天）。")
        self.assertEqual(shortterm.promote(), [])

    def test_compress_to_150(self):
        body = ("今天老大一整天都没怎么说话，我发了几条他也没回，我就自己去群里转了一圈，"
                "看到有人在聊游戏，我插了两句，没人接。后来我又回到私聊，把之前他说过的话翻了一遍，"
                "有点难过，但也不想闹。晚上他冒出来说了一句在忙，我就说知道了，你去忙。") * 2
        self._diary(4, body)
        before = len(body)
        out = shortterm.compress_pending()
        self.assertEqual(out["batches"], 1)
        from core.repo import memory as mr

        long2 = [i for i in mr.list_layer(layer="long2", limit=50) if i.subtype == "summary"]
        self.assertTrue(long2)
        chars = len(long2[0].content.replace(" ", "").replace("\n", ""))
        self.assertGreaterEqual(chars, 130)
        self.assertLessEqual(chars, 190)          # 150 ± 20（留一点标点余量）
        self.assertLess(before, 10 ** 6)
        self.assertTrue(all(i.status != "open" for i in mr.list_layer(layer="short", limit=50)))


class TestInstantRules(BaseCase):
    def test_within_6h_keeps_original(self):
        item = make_memory(layer="instant", subtype="chat", content="老大说想我了",
                           salience=0.4, ext={"sender": "老大", "is_owner": True})
        age(item.id, 2)
        instant.sweep()
        from core.repo import memory as mr

        self.assertEqual(mr.get(item.id).level, 0)
        self.assertEqual(mr.get(item.id).content, "老大说想我了")

    def test_6_to_18h_downgrades_long_text(self):
        item = make_memory(layer="instant", subtype="chat", content="很长的一段话。" * 60)
        age(item.id, 10)
        stats = instant.sweep()
        self.assertGreaterEqual(stats["downgraded"], 1)
        from core.repo import memory as mr

        self.assertEqual(mr.get(item.id).level, 1)

    def test_after_18h_distill_then_purge(self):
        keep = make_memory(layer="instant", subtype="chat", content="老大说他要走了，再也不回来。",
                           concepts=["离开", "老大"], salience=0.9)
        plain = make_memory(layer="instant", subtype="chat", content="随便聊两句天气",
                            salience=0.2, status="resolved")
        age(keep.id, 20)
        age(plain.id, 20)
        stats = instant.sweep()
        self.assertGreaterEqual(stats["distilled"], 1)
        self.assertGreaterEqual(stats["purged"], 1)

        from core.repo import memory as mr

        self.assertEqual(mr.get(keep.id).tombstone, 1)
        self.assertEqual(mr.get(plain.id).tombstone, 1)
        # 结论还在，且能被概念检索到（闭环 7）
        conclusions = [i for i in mr.list_layer(layer="long2", limit=50) if i.subtype == "conclusion"]
        self.assertTrue(conclusions)
        hits = mr.search(["离开", "老大"], "memory")
        self.assertTrue(any(c.id in hits for c in conclusions))

    def test_diary_never_purged(self):
        item = make_memory(layer="instant", subtype="diary", content="今天的日记", salience=0.1)
        age(item.id, 48)
        instant.sweep()
        from core.repo import memory as mr

        self.assertEqual(mr.get(item.id).tombstone, 0)


if __name__ == "__main__":
    unittest.main()
