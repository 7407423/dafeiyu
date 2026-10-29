"""碎碎念：负面静默、疲劳降频、静默窗口。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from .base import BaseCase

from core.cognition import chitchat
from core.emotion import vector
from core.repo import system as sr


class TestChitchat(BaseCase):
    def test_gate_allows_when_positive(self):
        vector.set_values({"joy": 80, "happiness": 80})
        gate = chitchat.gate(vector.current())
        self.assertTrue(gate["allowed"])
        self.assertTrue(gate["positive_high"])

    def test_negative_mutes(self):
        vector.set_values({"sadness": 80, "inferiority": 80})
        gate = chitchat.gate(vector.current())
        self.assertFalse(gate["allowed"])
        self.assertIn("负面", gate["reason"])

    def test_fatigue_after_three_unanswered(self):
        old = (datetime.now() - timedelta(minutes=10)).isoformat(timespec="seconds")
        for i in range(3):
            sr.chitchat_add(f"c{i}", old, f"第{i}句碎碎念")
        out = chitchat.no_reply_tick()
        self.assertEqual(out["consecutive"], 3)
        self.assertEqual(out["fatigue"], 1)
        self.assertIn("paused_until", out)
        state = chitchat.load()
        self.assertEqual(state.fatigue_level, 1)
        # 间隔按 1.5^level 放大
        lo, hi = chitchat._interval_minutes(state, True)
        self.assertGreater(lo, 5)

    def test_reply_resets_fatigue(self):
        chitchat.save(chitchat.ChitchatState(consecutive_no_reply=3, fatigue_level=2))
        chitchat.on_owner_replied()
        state = chitchat.load()
        self.assertEqual(state.fatigue_level, 0)
        self.assertEqual(state.consecutive_no_reply, 0)

    def test_mute_window(self):
        state = chitchat.mute(30)
        self.assertTrue(chitchat.muted(state))
        gate = chitchat.gate(vector.current(), state)
        self.assertFalse(gate["allowed"])


if __name__ == "__main__":
    unittest.main()
