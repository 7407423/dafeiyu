"""视觉：切块路由、坐标聚合、资产落库、识别结果解析。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .base import BaseCase, make_memory

from PySide6.QtGui import QColor, QImage

from core.vision import pipeline, preprocessor, reader, store

WORK = Path(tempfile.mkdtemp(prefix="dafeiyu-vision-"))


def make_image(name: str, width: int, height: int, color: str = "#336699") -> Path:
    path = WORK / name
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor(color))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(path), "PNG")
    return path


class TestTiling(BaseCase):
    def test_big_image_is_tiled(self):
        path = make_image("big.png", 4000, 3000)
        pre = preprocessor.VisionPreprocessor()
        plan = pre.prepare(path)
        self.assertTrue(plan.tiled)
        self.assertGreater(plan.count, 1)
        self.assertTrue(all(Path(t.path).exists() for t in plan.tiles))
        self.assertTrue(plan.thumb and Path(plan.thumb).exists())
        self.assertGreaterEqual(plan.manifest["cols"] * plan.manifest["rows"], plan.count)

    def test_small_image_skips_tiling(self):
        path = make_image("small.png", 600, 400)
        plan = preprocessor.VisionPreprocessor().prepare(path)
        self.assertFalse(plan.tiled)
        self.assertEqual(plan.count, 1)
        self.assertEqual(plan.tiles[0].label, "整体")
        self.assertEqual(plan.thumb, "")

    def test_labels_and_positions(self):
        path = make_image("wide.png", 2000, 900)
        plan = preprocessor.VisionPreprocessor().prepare(path)
        labels = [t.label for t in plan.tiles]
        self.assertEqual(len(labels), len(set(labels)), "切块标签应当唯一")
        self.assertTrue(all("(" in lab for lab in labels))
        self.assertEqual(plan.tiles[0].x, 0)
        self.assertEqual(plan.tiles[0].y, 0)

    def test_sampling_when_too_many_tiles(self):
        path = make_image("huge.png", 9000, 9000)
        plan = preprocessor.VisionPreprocessor(max_tiles=9).prepare(path)
        self.assertLessEqual(plan.count, 9)
        self.assertTrue(plan.manifest["sampled"])

    def test_aggregate_orders_by_position(self):
        path = make_image("grid.png", 2000, 2000)
        pre = preprocessor.VisionPreprocessor()
        plan = pre.prepare(path)
        results = [{"i": plan.tiles[-1].index, "text": "最后一块"},
                   {"i": plan.tiles[0].index, "text": "第一块"}]
        report = pre.aggregate(plan, results)
        self.assertEqual(report["blocks"][0]["text"], "第一块")
        self.assertIn("第一块", report["summary"])
        self.assertAlmostEqual(report["coverage"], round(2 / plan.count, 3), places=3)


class TestStoreAndReader(BaseCase):
    def test_attach_writes_asset_and_pointer(self):
        item = make_memory(layer="instant", subtype="chat", content="老大发了张图",
                           concepts=["图片"], status="resolved")
        path = make_image("pic.png", 1200, 900)
        out = pipeline.analyze(path, memory_item_id=item.id, kind="upload", created_from="test",
                               reader=reader.NullReader())
        self.assertTrue(out["ok"])
        self.assertEqual(store.count(), 1)

        from core import db

        row = db.q1("SELECT vision_tiles FROM memory_item WHERE id=?", (item.id,))
        pointer = json.loads(row["vision_tiles"])
        self.assertEqual(pointer["asset_id"], out["asset_id"])
        self.assertEqual(pointer["count"], out["tiles"])
        asset = store.get(out["asset_id"])
        self.assertIsNotNone(asset)
        self.assertEqual(asset["kind"], "upload")

    def test_parse_tolerates_code_fence(self):
        text = '```json\n[{"i": 0, "text": "左上角有字", "confidence": 0.9}]\n```'
        rows = reader._parse(text, [0, 1])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["text"], "左上角有字")

    def test_parse_drops_unknown_index(self):
        text = '[{"i": 5, "text": "越界"}, {"i": 1, "text": "正常"}]'
        rows = reader._parse(text, [0, 1])
        self.assertEqual([r["i"] for r in rows], [1])

    def test_no_reader_still_records(self):
        path = make_image(Path(__import__("tempfile").mkdtemp()) / "x.png", 500, 500)
        out = pipeline.analyze(path, reader=reader.NullReader(), created_from="test")
        self.assertTrue(out["ok"])
        self.assertEqual(out["tiles"], 1)
        self.assertIn("暂未识别", out["summary"])


if __name__ == "__main__":
    unittest.main()
