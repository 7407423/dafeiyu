"""v5：动图抽帧路由 + 表情缓存 + 费用归因（标签/预估/实际/偏差/区间/导入幂等）。"""

from __future__ import annotations

import json
import struct
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from .base import BaseCase, make_memory

from core import db, settings
from core.cost import attribute, detail, estimate_for, export_csv, import_ledgers, record_event, tag_of_task
from core.vision import animated, pipeline, reader

WORK = Path(tempfile.mkdtemp(prefix="dafeiyu-v5-"))


def tiny_gif(path: Path, frames: int = 3, delay: int = 10) -> Path:
    """手搓一个真正多帧的最小 GIF89a（不依赖任何图像库；delay 单位 1/100 秒）。"""
    header = b"GIF89a"
    lsd = struct.pack("<HHBBB", 2, 2, 0xF1, 0, 0)          # 2x2，带 4 色全局色表
    gct = bytes([0, 0, 0, 255, 0, 0, 255, 255, 255, 0, 0, 255])
    netscape = b"\x21\xFF\x0BNETSCAPE2.0\x03\x01\x00\x00\x00"
    # min code size=2；3 字节里是 CLEAR + 4 个像素 + END（LZW 最小编码）
    data = b"\x02\x03\x04\x40\x01\x00"
    body = b""
    for _ in range(frames):
        gce = b"\x21\xF9\x04\x04" + struct.pack("<H", delay) + b"\x00\x00"
        desc = b"\x2C" + struct.pack("<HHHHB", 0, 0, 2, 2, 0x00)
        body += gce + desc + data
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + lsd + gct + netscape + body + b"\x3B")
    return path


class TestAnimation(BaseCase):
    def setUp(self) -> None:
        super().setUp()
        self.gif = tiny_gif(WORK / "wave.gif", frames=3, delay=10)

    def test_supports_by_suffix_and_frames(self):
        dec = animated.AnimatedDecoder()
        self.assertTrue(dec.supports(self.gif))
        plain = WORK / "plain.png"
        from PySide6.QtGui import QColor, QImage

        img = QImage(40, 30, QImage.Format_RGB32)
        img.fill(QColor("#123456"))
        img.save(str(plain), "PNG")
        self.assertFalse(dec.supports(plain))

    def test_decode_extracts_frames_and_duration(self):
        plan = animated.AnimatedDecoder(frames=3).decode(self.gif)
        self.assertEqual(plan.count, 3)
        self.assertGreaterEqual(plan.duration_ms, 300)      # 3 帧 × 100ms
        self.assertTrue(all(Path(f.path).exists() for f in plan.frames))
        self.assertEqual([f.index for f in plan.frames], [0, 1, 2])
        self.assertEqual(plan.frames[1].t_ms, 100)
        self.assertTrue(plan.sha256)

    def test_sampling_caps_frames(self):
        gif = tiny_gif(WORK / "long.gif", frames=6, delay=10)
        plan = animated.AnimatedDecoder(frames=3).decode(gif)
        self.assertEqual(plan.count, 3)
        self.assertEqual(plan.frames[0].index, 0)
        self.assertGreaterEqual(plan.frames[-1].index, 4)

    def test_cache_roundtrip_and_hits(self):
        dec = animated.AnimatedDecoder(frames=3)
        plan = dec.decode(self.gif)
        self.assertIsNone(dec.cache_get(plan.sha256))
        dec.cache_put(plan.sha256, plan, "一个人挥手说再见", ["动态表情", "挥手"])
        hit = dec.cache_get(plan.sha256)
        self.assertIsNotNone(hit)
        self.assertIn("挥手", hit["summary"])
        self.assertEqual(hit["hits"], 2)          # 命中一次 +1
        self.assertTrue(dec.cache_get(plan.sha256)["hits"] >= 2)

    def test_pipeline_uses_cache_on_second_call(self):
        item = make_memory(layer="instant", subtype="chat", content="老大发了个动图",
                           concepts=["表情"], status="resolved")
        first = pipeline.analyze(self.gif, memory_item_id=item.id, kind="sticker",
                                 created_from="test", reader=reader.NullReader())
        self.assertTrue(first["ok"])
        self.assertTrue(first["animated"])
        self.assertEqual(first["frames"], 3)
        self.assertFalse(first["cache_hit"])

        second = pipeline.analyze(self.gif, memory_item_id=item.id, kind="sticker",
                                  created_from="test", reader=reader.NullReader())
        self.assertTrue(second["cache_hit"], "第二次应命中缓存，不再调视觉模型")

        row = db.q1("SELECT animation_meta FROM memory_item WHERE id=?", (item.id,))
        meta = json.loads(row["animation_meta"])
        self.assertEqual(meta["frames"], 3)
        cached = db.q1("SELECT summary, concepts FROM sticker_cache")
        self.assertIsNotNone(cached, "第一次识别应写入表情缓存")
        self.assertIn("动态表情", cached["concepts"])

    def test_annotate_writes_note(self):
        dec = animated.AnimatedDecoder(frames=3)
        plan = dec.decode(self.gif)
        dec.cache_put(plan.sha256, plan, "挥手", ["挥手"])
        self.assertTrue(dec.annotate(plan.sha256, "这是老大常用的「好耶」"))
        self.assertIn("好耶", dec.cache_get(plan.sha256)["note"])


class TestCostTag(BaseCase):
    def test_task_mapping(self):
        self.assertEqual(tag_of_task("dialogue"), "chat")
        self.assertEqual(tag_of_task("chitchat"), "chitchat")
        self.assertEqual(tag_of_task("compress"), "memory_compress")
        self.assertEqual(tag_of_task("vision"), "vision_static")
        self.assertEqual(tag_of_task("refusal"), "other")
        self.assertEqual(tag_of_task("不存在的任务"), "other")

    def test_record_and_attribute(self):
        record_event("chat", task="dialogue", usage={"cache_miss": 1000, "output": 300},
                     estimated=0.006, actual=0.006, source="engine")
        record_event("chat", task="dialogue", usage={"cache_miss": 1000, "output": 300},
                     estimated=0.006, actual=0.006, source="engine")
        record_event("vision_animation", task="vision", usage={"cache_miss": 2000, "output": 400},
                     estimated=0.01, actual=0.02, source="engine")
        record_event("other", task="bridge-turn", usage={"cache_hit": 5000, "output": 100},
                     estimated=0.0, actual=0.003, source="bridge")
        data = attribute()
        self.assertEqual(data["total"]["calls"], 4)
        self.assertAlmostEqual(data["total"]["cost"], 0.035, places=4)
        tags = {item["tag"]: item for item in data["by_tag"]}
        self.assertEqual(tags["chat"]["calls"], 2)
        self.assertAlmostEqual(tags["chat"]["avg_actual"], 0.006, places=4)
        self.assertAlmostEqual(tags["chat"]["avg_estimated"], 0.006, places=4)
        self.assertEqual(tags["chat"]["deviation"]["level"], "ok")
        self.assertAlmostEqual(tags["vision_animation"]["deviation"]["pct"], 1.0, places=3)
        self.assertEqual(tags["vision_animation"]["deviation"]["level"], "fail")
        self.assertEqual(data["unclassified"], 1)
        self.assertTrue(0 < tags["chat"]["share"] <= 1)

    def test_missing_estimate_is_not_faked(self):
        record_event("other", task="bridge-turn", usage={"cache_hit": 100}, actual=0.002, source="bridge")
        data = attribute()
        item = data["by_tag"][0]
        self.assertEqual(item["avg_estimated"], 0)
        self.assertEqual(item["deviation"]["level"], "none")

    def test_range_and_day_aggregation(self):
        record_event("chat", task="dialogue", usage={"cache_miss": 100}, actual=0.001)
        db.ex("UPDATE cost_event SET t=? WHERE feature_tag='chat'",
              ((datetime.now() - timedelta(days=3)).isoformat(timespec="seconds"),))
        record_event("chat", task="dialogue", usage={"cache_miss": 100}, actual=0.002)
        today = attribute(days=1)
        self.assertEqual(today["total"]["calls"], 1)
        every = attribute()
        self.assertEqual(every["total"]["calls"], 2)
        self.assertEqual(len(every["by_day"]), 2)

    def test_estimate_is_positive_and_tag_aware(self):
        small = estimate_for("chitchat", 200)
        big = estimate_for("self_dialogue", 4000)
        self.assertGreater(small, 0)
        self.assertGreater(big, small)

    def test_export_csv(self):
        record_event("voice", task="voice", usage={"cache_miss": 100}, actual=0.001)
        out = WORK / "cost.csv"
        export_csv(str(out))
        self.assertTrue(out.exists())
        text = out.read_text(encoding="utf-8-sig")
        self.assertIn("语音", text)
        self.assertIn("功能", text)

    def test_detail_filter(self):
        record_event("learning", task="learning", usage={"cache_miss": 300}, actual=0.004)
        rows = detail(tag="learning")
        self.assertTrue(rows)
        self.assertEqual(rows[0]["feature_tag"], "learning")

    def test_import_ledgers_is_idempotent(self):
        first = import_ledgers()
        after_first = db.scalar("SELECT COUNT(*) FROM cost_event")
        second = import_ledgers()
        after_second = db.scalar("SELECT COUNT(*) FROM cost_event")
        self.assertEqual(after_first, after_second, "重复导入不应新增行")
        self.assertGreaterEqual(second["skipped"], first["skipped"])


class TestMigrationV5(BaseCase):
    def test_schema_and_columns(self):
        self.assertGreaterEqual(int(db.get_meta("schema_version")), 5)
        tables = {r["name"] for r in db.q(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        self.assertIn("cost_event", tables)
        self.assertIn("sticker_cache", tables)
        cols = {r["name"] for r in db.q("PRAGMA table_info(memory_item)")}
        self.assertIn("animation_meta", cols)

    def test_idempotent(self):
        db.init_db()
        self.assertEqual(db.init_db().get("added_columns"), [])

    def test_old_items_have_null_animation(self):
        item = make_memory(layer="long2", subtype="summary", content="老记忆")
        row = db.q1("SELECT animation_meta FROM memory_item WHERE id=?", (item.id,))
        self.assertIsNone(row["animation_meta"])

    def test_cost_event_columns(self):
        cols = {r["name"] for r in db.q("PRAGMA table_info(cost_event)")}
        for name in ("feature_tag", "estimated_cost", "actual_cost", "session_id", "meta"):
            self.assertIn(name, cols)


if __name__ == "__main__":
    unittest.main()
