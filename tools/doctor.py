"""只读体检：不写任何记忆，只报告现在的状态。

用法：python tools/doctor.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import db, settings  # noqa: E402


def main() -> int:
    settings.ensure_dirs()
    db.init_db()
    from core.cognition import scheduler  # noqa: F401  (确认能导入)
    from core.bridge import push
    from core.cognition import chitchat
    from core.emotion import policy, vector
    from core.language import memory as langmem
    from core.memory import longterm, shortterm

    vec = vector.current()
    report = {
        "root": str(settings.ROOT),
        "db": db.stats(),
        "emotion": vector.status(),
        "policy": policy.summary(),
        "chitchat": {"next_due_at": chitchat.load().next_due_at,
                     "enabled": chitchat.load().enabled,
                     "gate": chitchat.gate(vec)},
        "push": push.status(),
        "long2": longterm.lt2_counts(),
        "short": shortterm.stats(),
        "language": langmem.status("language")["chars"],
        "emotion_memory": langmem.status("emotion")["chars"],
        "bridge_mode": settings.app().get("bridge", {}).get("emotion_mode"),
        "llm": {"providers": settings.llm_cfg().get("default"),
                "dsh_exists": Path(settings.llm_cfg().get("providers", {})
                                   .get("dsh", {}).get("cmd", "")).exists()},
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
