"""测试基座：把整套系统搬到一个临时 DAFEIYU_HOME 里，绝不碰真实记忆。

所有测试文件第一行 `from .base import *`（或 import base）即可。
LLM 强制走 offline，不联网、不花钱。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = Path(tempfile.mkdtemp(prefix="dafeiyu-test-"))
os.environ["DAFEIYU_HOME"] = str(TMP)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── 把真配置抄进临时目录（阈值要和线上一致，这样测的是同一套规则）──
(TMP / "config").mkdir(parents=True, exist_ok=True)
for name in ("app.json", "emotion.json", "thresholds.json", "vision.json",
             "refusal.json", "residual.json", "animation.json", "cost_tracking.json",
             "curiosity_engine.json", "circadian.json"):
    src = ROOT / "config" / name
    if src.exists():
        shutil.copy2(src, TMP / "config" / name)

app_cfg = json.loads((TMP / "config" / "app.json").read_text(encoding="utf-8")) if (TMP / "config" / "app.json").exists() else {}
app_cfg.setdefault("bridge", {})["enabled"] = False
app_cfg["bridge"]["emotion_mode"] = "local"
(TMP / "config" / "app.json").write_text(json.dumps(app_cfg, ensure_ascii=False, indent=2), encoding="utf-8")

(TMP / "config" / "llm.json").write_text(json.dumps({
    "default": "offline",
    "providers": {"dsh": {"cmd": "/nonexistent/dsh"}, "http": {"base_url": ""}, "offline": {"mode": "template"}},
    "tasks": {k: "offline" for k in ("summary", "compress", "dialogue", "chitchat",
                                      "learning", "self_dialogue", "judge")},
}, ensure_ascii=False, indent=2), encoding="utf-8")

from core import db, settings  # noqa: E402

# 安全闸：如果因为导入顺序问题指回了真实目录，立刻停，绝不删线上的东西
REAL_ROOT = Path(r"~/.dafeiyu").resolve()
if settings.ROOT.resolve() == REAL_ROOT:
    raise RuntimeError(
        "测试环境指向了真实目录 ~/.dafeiyu —— 拒绝运行（会删掉线上 state）。"
        "请确保先 import tests.base 再 import core。"
    )

settings.ensure_dirs()
db.init_db()

from core.entity import (  # noqa: E402,F401
    Layer, MemoryItem, Status, ThoughtNode, EmotionVector, now_iso,
)
from core.memory import shortterm  # noqa: E402

shortterm.USE_LLM = False


def reset() -> None:
    """每个测试从空库开始。"""
    if settings.ROOT.resolve() == REAL_ROOT:
        raise RuntimeError("拒绝清理真实目录")
    db.close()
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(db.DB_PATH) + suffix)
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass
    db.init_db()
    shortterm.USE_LLM = False
    # 状态文件清干净
    for name in ("emotion.json", "curiosity.json", "cooldown.json", "chitchat.json",
                 "working_memory.json", "sidebar.json", "refusal.json", "vision_session.json",
                 "sessions_v4.json", "residual_state.json", "relationship.json",
                 "capabilities.json", "soul_alert.json", "curiosity_engine.json",
                 "circadian_learned.json", "sleep_loyalty.json", "frustration.json",
                 "language_fingerprint.json", "self_narrative.json", "homeostasis.json",
                 "memewiki.json", "hormones.json", "douyin.json"):
        path = settings.STATE / name
        if path.exists():
            path.unlink()
    for path in (settings.STATE / "refusal_log").glob("*.jsonl"):
        path.unlink()
    for path in (settings.STATE / "outbox").glob("*.json"):
        path.unlink()
    from core.emotion import vector

    vector.reload()


def make_memory(**kwargs) -> MemoryItem:
    from core.repo import memory as mr

    item = MemoryItem(**kwargs)
    mr.insert(item)
    mr.set_index(item.id, "memory",
                 list(kwargs.get("concepts") or []), list(kwargs.get("concepts") or []))
    return item


def age(item_id: str, hours: float) -> None:
    """把条目的创建时间往前拨（测 6h/18h/3 天规则用）。"""
    from datetime import datetime, timedelta

    from core.repo import memory as mr

    when = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    mr.update_fields(item_id, t_created=when, ext={**(mr.get(item_id).ext or {}), "decay_at": when})


class BaseCase(unittest.TestCase):
    def setUp(self) -> None:
        reset()
