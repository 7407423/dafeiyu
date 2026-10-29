"""契约文件投影：格式保留 + 防呆（DB 空了也不许清空线上文件）。"""

from __future__ import annotations

import unittest

from .base import BaseCase, make_memory

from core import settings
from core.bridge import projection


class TestProjection(BaseCase):
    def setUp(self) -> None:
        super().setUp()
        settings.LEGACY_LT2.mkdir(parents=True, exist_ok=True)
        for name in ("开心", "难过", "生气", "创伤", "平静", "害羞"):
            (settings.LEGACY_LT2 / f"{name}.md").write_text(
                f"# 2号长期记忆 · {name}\n\n> 测试用。\n\n---\n", encoding="utf-8")

    def test_writes_entries_and_is_idempotent(self):
        make_memory(layer="long2", subtype="summary", content="老大抱了我一下，心情很好。",
                    concepts=["老大", "抱抱"], emotion_tag="开心", salience=0.8,
                    ext={"date": "2026-10-27", "seq": 0,
                         "impact": "被在意", "labels": "老大 / 抱抱", "source": "测试"})
        out = projection.project_lt2()
        self.assertEqual(out["by_category"]["开心"], 1)
        text = (settings.LEGACY_LT2 / "开心.md").read_text(encoding="utf-8")
        self.assertIn("### 2026-10-27", text)
        self.assertIn("老大抱了我一下", text)
        self.assertIn("- 影响：被在意", text)

        first = text
        projection.project_lt2()
        self.assertEqual((settings.LEGACY_LT2 / "开心.md").read_text(encoding="utf-8"), first)

    def test_refuses_to_blank_a_non_empty_file(self):
        path = settings.LEGACY_LT2 / "害羞.md"
        path.write_text(
            "# 2号长期记忆 · 害羞\n\n> 手工写的。\n\n---\n\n### 2026-10-20 · 强度 ●●●○○\n\n"
            "这条不能被投影吃掉。\n\n- 影响：—\n- 标签：—\n- 来源：—\n\n---\n",
            encoding="utf-8",
        )
        out = projection.project_lt2()
        self.assertEqual(out["by_category"]["害羞"], -1)
        self.assertIn("害羞", out["skipped"])
        self.assertIn("这条不能被投影吃掉", path.read_text(encoding="utf-8"))

    def test_instant_projection_respects_hot_window(self):
        from .base import age

        item = make_memory(layer="instant", subtype="chat", content="刚才那句话",
                           status="resolved", ext={"sender": "老大", "is_owner": True})
        projection.project_instant()
        hot = (settings.LEGACY_INSTANT / "热区.jsonl").read_text(encoding="utf-8")
        self.assertIn("刚才那句话", hot)

        age(item.id, 10)
        projection.project_instant()
        hot = (settings.LEGACY_INSTANT / "热区.jsonl").read_text(encoding="utf-8")
        warm = (settings.LEGACY_INSTANT / "温区.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("刚才那句话", hot)
        self.assertIn("刚才那句话", warm)


if __name__ == "__main__":
    unittest.main()
