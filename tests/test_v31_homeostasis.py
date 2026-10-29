"""v31/v32 内稳态：误差信号 → 主导动机 → 情绪着色 → 好奇心联动（含疲劳熔断）。"""

from __future__ import annotations

from datetime import datetime, timedelta

from .base import BaseCase

from core import curiosity_engine, homeostasis, settings


def _write(values: dict, *, last_activity: datetime | None = None, dominant: str = "") -> dict:
    now = datetime.now()
    motives = homeostasis.motives_of(values)
    auto_dominant, auto_strength = homeostasis.dominant_of(motives)
    data = {
        "values": values,
        "motives": motives,
        "dominant": dominant or auto_dominant,
        "strength": auto_strength if not dominant or auto_dominant == dominant else max(
            float(motives.get(dominant, 0)), auto_strength),
        "last_activity_at": (last_activity or now).isoformat(timespec="seconds"),
        "updated_at": now.isoformat(timespec="seconds"),
        "tick_count": 0,
    }
    settings.write_state(homeostasis.FILE, data)
    return data


class TestMotives(BaseCase):
    def test_motive_is_setpoint_minus_value(self):
        m = homeostasis.motives_of({"energy": 0.5, "social_connection": 0.2, "cognitive_novelty": 0.5})
        self.assertAlmostEqual(m["fatigue"], 0.3, places=3)
        self.assertAlmostEqual(m["loneliness"], 0.4, places=3)
        self.assertAlmostEqual(m["boredom"], 0.0, places=3, msg="到设定点就没有无聊")

    def test_no_negative_motive(self):
        m = homeostasis.motives_of({"energy": 0.95, "social_connection": 0.9, "cognitive_novelty": 0.9})
        self.assertEqual(m, {"fatigue": 0.0, "loneliness": 0.0, "boredom": 0.0})

    def test_dominant_picks_max_and_needs_floor(self):
        name, strength = homeostasis.dominant_of({"fatigue": 0.1, "loneliness": 0.6, "boredom": 0.2})
        self.assertEqual(name, "loneliness")
        self.assertAlmostEqual(strength, 0.6, places=3)
        self.assertEqual(homeostasis.dominant_of({"fatigue": 0.01, "loneliness": 0.02, "boredom": 0.0}),
                         ("", 0.0), "都低于地板值就算平静")


class TestTick(BaseCase):
    def test_idle_recovers_energy_and_decays_social(self):
        old = datetime.now() - timedelta(minutes=60)
        _write({"energy": 0.4, "social_connection": 0.9, "cognitive_novelty": 0.9}, last_activity=old)
        out = homeostasis.tick()
        self.assertTrue(out["idle"])
        self.assertGreater(out["values"]["energy"], 0.4, "闲着要回血")
        self.assertLess(out["values"]["social_connection"], 0.9, "没人理要掉")

    def test_active_drains_energy(self):
        already = datetime.now()
        _write({"energy": 0.9, "social_connection": 0.5, "cognitive_novelty": 0.5}, last_activity=already)
        out = homeostasis.tick()
        self.assertFalse(out["idle"])
        self.assertLess(out["values"]["energy"], 0.9)

    def test_tick_is_capped_at_a_day(self):
        old = datetime.now() - timedelta(days=3)
        _write({"energy": 0.1, "social_connection": 0.1, "cognitive_novelty": 0.1}, last_activity=old)
        out = homeostasis.tick()
        self.assertLessEqual(out["values"]["energy"], 1.0, "睡三天也不能超过 1.0")

    def test_loneliness_dominates_after_idle(self):
        old = datetime.now() - timedelta(hours=2)
        _write({"energy": 0.8, "social_connection": 0.05, "cognitive_novelty": 0.5}, last_activity=old)
        out = homeostasis.tick(apply_coloring=False)
        self.assertEqual(out["dominant"], "loneliness")
        self.assertTrue(homeostasis.prompt_block().count("孤独") >= 1)


class TestEvents(BaseCase):
    def test_user_message_raises_social(self):
        _write({"energy": 0.8, "social_connection": 0.1, "cognitive_novelty": 0.5})
        out = homeostasis.note("user_message")
        self.assertAlmostEqual(out["values"]["social_connection"], 0.38, places=3)

    def test_learning_raises_novelty_and_costs_energy(self):
        _write({"energy": 0.6, "social_connection": 0.6, "cognitive_novelty": 0.1})
        out = homeostasis.note("learning")
        self.assertGreater(out["values"]["cognitive_novelty"], 0.4)
        self.assertLess(out["values"]["energy"], 0.6)

    def test_refusal_costs_extra_energy(self):
        _write({"energy": 0.6, "social_connection": 0.6, "cognitive_novelty": 0.5})
        out = homeostasis.note("refusal")
        self.assertAlmostEqual(out["values"]["energy"], 0.54, places=3)

    def test_unknown_event_is_noop(self):
        _write({"energy": 0.6, "social_connection": 0.6, "cognitive_novelty": 0.5})
        self.assertFalse(homeostasis.note("whatever")["ok"])


class TestCuriosityFusion(BaseCase):
    """v32：困到 0.2 以下 → 自主好奇心直接停；无聊 → 门槛压下来。"""

    def setUp(self) -> None:
        super().setUp()
        settings.write_state("curiosity_engine.json", {
            "domains": {"聊梗": {"name": "聊梗", "last_error": 0.9, "previous_error": 0.5,
                                 "progress": 0.0, "boredom": 0.0, "specific_gap_score": 0.2,
                                 "last_explored_at": "", "explore_count": 0, "note": ""}},
            "last_run": "",
        })

    def test_fatigue_fuse_blocks_tick(self):
        _write({"energy": 0.1, "social_connection": 0.6, "cognitive_novelty": 0.6})
        out = curiosity_engine.tick()
        self.assertTrue(out.get("fuse"))
        self.assertIn("困", out.get("skipped", ""))
        self.assertFalse(out.get("target"))

    def test_boredom_lowers_threshold(self):
        _write({"energy": 0.8, "social_connection": 0.6, "cognitive_novelty": 0.02}, dominant="boredom")
        out = curiosity_engine.tick()
        self.assertGreater(out.get("bias", {}).get("boredom", 0), 0.3)
        # 领域紧迫度本身不高，但无聊把门槛压下来后应该能选出来
        self.assertTrue(out.get("target") or out.get("note"))
        if out.get("target"):
            self.assertIn("[内稳态]", out.get("trace", ""))

    def test_loneliness_biases_social_domains(self):
        _write({"energy": 0.8, "social_connection": 0.05, "cognitive_novelty": 0.6}, dominant="loneliness")
        bias = curiosity_engine.homeostasis_bias()
        self.assertGreater(bias["loneliness"], 0.2)
        self.assertTrue(curiosity_engine.social_like("聊梗"))
        self.assertFalse(curiosity_engine.social_like("数据库索引"))


class TestStatus(BaseCase):
    def test_status_shape(self):
        _write({"energy": 0.5, "social_connection": 0.3, "cognitive_novelty": 0.4})
        st = homeostasis.status()
        for key in ("values", "setpoints", "motives", "dominant", "label", "expressiveness", "fuse"):
            self.assertIn(key, st)
        self.assertEqual(set(st["values"]), {"energy", "social_connection", "cognitive_novelty"})

    def test_expressiveness_follows_energy(self):
        _write({"energy": 0.1, "social_connection": 0.6, "cognitive_novelty": 0.5})
        low = homeostasis.expressiveness()
        _write({"energy": 1.0, "social_connection": 0.6, "cognitive_novelty": 0.5})
        self.assertLess(low, homeostasis.expressiveness())
