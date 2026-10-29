"""两周冷却：锁、到期询问、同意/再等等。"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from .base import BaseCase

from core.language import memory as langmem


class TestCooldown(BaseCase):
    def test_lock_blocks_and_counts_days(self):
        until = langmem.lock("language")
        self.assertTrue(until)
        self.assertTrue(langmem.locked("language"))
        self.assertFalse(langmem.due("language"))
        st = langmem.status("language")
        self.assertGreater(st["days_left"], 13.0)
        self.assertLessEqual(st["days_left"], 14.0)

    def test_expiry_asks_user(self):
        langmem.lock("language")
        state = langmem.cooldowns()
        state.language["cooldown_until"] = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
        langmem.save_cooldowns(state)

        self.assertFalse(langmem.locked("language"))
        self.assertTrue(langmem.due("language"))
        ask = langmem.ask("language")
        self.assertTrue(ask["due"])
        self.assertIn("要不要更新", ask["question"])
        self.assertTrue(langmem.status("language")["awaiting_user"])

    def test_answer_no_postpones_one_week(self):
        langmem.lock("emotion")
        state = langmem.cooldowns()
        state.emotion["cooldown_until"] = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
        langmem.save_cooldowns(state)
        langmem.ask("emotion")
        out = langmem.answer("emotion", False)
        self.assertEqual(out["action"], "postponed")
        self.assertTrue(langmem.locked("emotion"))
        st = langmem.status("emotion")
        self.assertGreater(st["days_left"], 6.0)
        self.assertLessEqual(st["days_left"], 7.0)

    def test_answer_yes_unlocks(self):
        langmem.lock("language")
        state = langmem.cooldowns()
        state.language["cooldown_until"] = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
        langmem.save_cooldowns(state)
        langmem.ask("language")
        out = langmem.answer("language", True)
        self.assertEqual(out["action"], "unlocked")
        self.assertFalse(langmem.locked("language"))


if __name__ == "__main__":
    unittest.main()
