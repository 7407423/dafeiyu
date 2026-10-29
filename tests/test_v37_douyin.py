"""v37 刷抖音学梗：纯文本抓取、验证拦截、连续空抓、以及「不准偷偷花钱」的守卫。

浏览器不在这里启动（那是真去刷才做的事），这里只测**逻辑**：
哪些字符串算验证拦截、哪一屏算「什么都没抓到」、账本标签对不对。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .base import BaseCase

from core import deskstate, douyin, settings


class TestCaptcha(unittest.TestCase):
    def test_detects_common_walls(self):
        for text in ("请完成安全验证", "拖动滑块完成拼图", "人机验证", "访问过于频繁，请稍后再试",
                     "异常流量", "操作频繁"):
            self.assertTrue(douyin.captcha_hit(text), text)

    def test_ignores_normal_pages(self):
        # 「验证码登录」是登录方式，不是风控 —— 之前误报成 captcha，害得登录墙被当成被拦
        for text in ("推荐 关注 朋友 我的", "这个视频太好笑了", "评论区都在刷奶蛙",
                     "验证码登录 密码登录 扫码登录"):
            self.assertEqual(douyin.captcha_hit(text), "", text)


class TestCapture(BaseCase):
    def test_useful_lines_filters_noise(self):
        text = "\n".join([
            "首页", "推荐", "关注",           # 导航词，必须丢
            "哈哈哈哈这个猫好离谱",
            "哈哈哈哈这个猫好离谱",           # 重复，只留一条
            "1.2万",                         # 纯数字点赞，丢
            "有没有人知道这个梗叫什么",
        ])
        lines = douyin.useful_lines(text)
        self.assertEqual(lines, ["哈哈哈哈这个猫好离谱", "有没有人知道这个梗叫什么"])

    def test_empty_capture_needs_two_real_lines(self):
        self.assertTrue(douyin.is_empty_capture([]))
        self.assertTrue(douyin.is_empty_capture(["首页", "推荐"]))
        self.assertFalse(douyin.is_empty_capture(["这是一条够长的评论", "这也是一条够长的评论"]))

    def test_summarize_takes_longest(self):
        out = douyin.summarize(["短", "这是一条比较长的评论内容", "中等长度的评论"])
        self.assertIn("这是一条比较长的评论内容", out)

    def test_config_defaults_and_override(self):
        conf = douyin.cfg()
        self.assertEqual(conf["perVideoSeconds"], 10)
        self.assertEqual(conf["jitterSeconds"], 2)
        self.assertAlmostEqual(conf["likeProbability"], 0.15)
        self.assertEqual(conf["maxEmptyStreak"], 3)


class TestRunnerGuards(BaseCase):
    def test_start_refuses_when_already_running(self):
        with douyin._lock:
            douyin._run["running"] = True
        try:
            out = douyin.start(1)
            self.assertFalse(out["ok"], "已经在跑就别再开一条浏览器")
        finally:
            with douyin._lock:
                douyin._run["running"] = False

    def test_status_has_no_thread_handle(self):
        st = douyin.status()
        self.assertNotIn("stop", st, "线程事件不能进状态（JSON 序列化会炸）")
        for key in ("running", "videos", "lines", "minutes", "need", "shot"):
            self.assertIn(key, st)

    def test_stop_is_idempotent(self):
        self.assertEqual(douyin.stop()["ok"], True)
        self.assertEqual(douyin.stop()["ok"], True)


class TestLedgerTag(BaseCase):
    def test_local_browse_tag_is_free(self):
        from core import cost

        self.assertIn("local_browse", cost.TAG_CN)
        self.assertGreaterEqual(len(cost.TAG_CN["local_browse"]), 4)


class TestDeskState(unittest.TestCase):
    def test_state_shape(self):
        st = deskstate.state()
        for key in ("idle_seconds", "locked", "active", "checked_at"):
            self.assertIn(key, st)
        self.assertIsInstance(st["active"], bool)
        self.assertGreaterEqual(st["idle_seconds"], 0)

    def test_locked_means_not_active(self):
        # 锁屏时 active 必须是 False（这里只验算关系，不真去锁屏）
        st = deskstate.state()
        if st["locked"]:
            self.assertFalse(st["active"])


if __name__ == "__main__":
    unittest.main()
