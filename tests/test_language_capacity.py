"""语言系统容量：从 3000 提到 6000 之后，行为必须跟着变。

沙盒（tests.base 的临时 DAFEIYU_HOME），不碰真实记忆。
"""

from __future__ import annotations

import unittest

from .base import BaseCase

from core.entity import Layer
from core.language import memory


class TestLanguageCapacity(BaseCase):
    def test_limits_are_6000(self):
        limits = memory._limits(Layer.LANGUAGE.value)
        self.assertEqual(limits["trigger"], 6000)
        self.assertEqual(limits["target"], 6000)
        self.assertEqual(limits["tolerance"], 1000)

    def test_emotion_layer_stays_6000(self):
        limits = memory._limits(Layer.EMOTION.value)
        self.assertEqual(limits["trigger"], 6000)
        self.assertEqual(limits["target"], 6000)

    def test_3000_no_longer_triggers_compression(self):
        # 4 × 900 = 3600 字：旧的 3000 阈值会压缩，新阈值不该压。
        for index in range(4):
            memory.append(Layer.LANGUAGE.value, "字" * 900, head=f"第 {index + 1} 轮")
        status = memory.status(Layer.LANGUAGE.value)
        self.assertGreaterEqual(status["chars"], 3000)
        self.assertLess(status["chars"], 6000)
        self.assertFalse(status["locked"], "3600 字不该触发两周冷却")

    def test_over_6000_compresses_and_locks(self):
        for index in range(8):
            memory.append(Layer.LANGUAGE.value, "字" * 1000, head=f"第 {index + 1} 轮")
        status = memory.status(Layer.LANGUAGE.value)
        self.assertTrue(status["locked"], "超过 6000 应该整体压缩并进入冷却")
        self.assertLessEqual(status["chars"], 7000)


if __name__ == "__main__":
    unittest.main()
