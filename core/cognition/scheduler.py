# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# 详见根目录 LICENSE 与 ADDITIONAL_TERMS.md。
# 本文件不含任何开发者的个人信息与真实数据。
# ─────────────────────────────────────────────────────────────────────────────
"""调度器：唯一叫醒认知循环的地方（APScheduler）。

规格 6.10 / 5.2 / v12 1.1：
- 每 20 秒（界面开）/ 60 秒（后台）：tick
- 每 10 分钟：衰减 + 蒸馏 + 情绪回归
- 学习窗口、自我对话、巩固、归档：**全部从 config/app.json → learning 读**，不写死
  默认：学习 00:00–01:00、自我对话 01:30–02:00、巩固 01:10、归档 04:00
- 每 2 分钟：外发队列重试
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .. import db, settings
from ..bridge import push
from .. import homeostasis, hormones
from ..emotion import vector
from ..language import memory as langmem
from ..repo import system as sr
from . import chitchat, consolidate, curiosity, loop

_lock = threading.RLock()
_sched: BackgroundScheduler | None = None
LAST: dict[str, str] = {}


def _guard(name: str, fn) -> None:
    """失败重试并记录；单次失败不许拖垮整条调度。"""
    try:
        out = fn()
        LAST[name] = datetime.now().isoformat(timespec="seconds")
        if isinstance(out, dict):
            sr.consolidation_add(f"job-{name}-{datetime.now():%Y%m%d%H%M%S}", name,
                                 {"ok": True, "summary": str(out)[:800]})
        return
    except Exception as exc:  # noqa: BLE001
        db.set_meta(f"job_error:{name}", f"{datetime.now():%Y-%m-%d %H:%M:%S} {exc}")
        for attempt in (1, 2):
            try:
                import time

                time.sleep(2 * attempt)
                fn()
                LAST[name] = datetime.now().isoformat(timespec="seconds")
                return
            except Exception:
                continue
        sr.consolidation_add(f"jobfail-{name}-{datetime.now():%Y%m%d%H%M%S}", name,
                             {"ok": False, "error": str(exc)})


# ── 各任务 ──────────────────────────────────────────────────────────────────
def job_tick() -> dict:
    return loop.run_once({"idle": True})


def job_periodic() -> dict:
    return consolidate.periodic()


def job_daily() -> dict:
    return consolidate.daily()


def job_learning() -> dict:
    from ..learning import executor

    today = datetime.now().strftime("%Y-%m-%d")
    if db.get_meta(f"learn_done:{today}") == "1":
        return {"skipped": "今天已经学过"}
    if not executor.window_open():
        return {"skipped": "不在学习窗口"}
    out = executor.scheduled_run(max_items=2)
    if out.get("ok"):
        db.set_meta(f"learn_done:{today}", "1")
    return out


def job_practice() -> dict:
    from ..learning import selfdialog

    today = datetime.now().strftime("%Y-%m-%d")
    if db.get_meta(f"practice_done:{today}") == "1":
        return {"skipped": "今天已经练过"}
    if not selfdialog.window_open():
        return {"skipped": "不在练习窗口"}
    out = selfdialog.run()
    if out.get("rounds"):
        db.set_meta(f"practice_done:{today}", "1")
    return out


def job_archive() -> dict:
    vector.snapshot("archive")
    return {"at": datetime.now().isoformat(timespec="seconds")}


def job_outbox() -> dict:
    return push.flush_outbox()


def job_cooldown() -> dict:
    """语言/情绪冷却到期 → 该问老大要不要更新了。"""
    out = {}
    for layer in ("language", "emotion"):
        out[layer] = langmem.ask(layer)
    return out


def job_chitchat() -> dict:
    state = chitchat.load()
    if not chitchat.due(state):
        return {"due": False}
    return chitchat.run(vec=vector.current())


def job_homeostasis() -> dict:
    """v31 内稳态心跳：每 60 秒一次，慢变量自己朝设定点回家。

    为什么单独一条 job 而不是塞进 tick：tick 是认知循环（20/60 秒，跟着界面模式走），
    内稳态要的是**稳定的一分钟**——界面关着、循环在忙、桥接没消息，它都得照算。
    """
    out = homeostasis.tick()
    if out.get("dominant"):
        db.set_meta("homeostasis:dominant", f"{out['dominant']}:{out['strength']}")
    return out


def job_hormones() -> dict:
    """v33 神经内分泌：每 10 分钟衰减一次、推基线漂移、让性格朝目标挪一小步。

    10 分钟而不是 60 秒：激素是分钟~天级的慢变量，算太勤只是白烧 CPU；
    而且 `tick()` 按 elapsed 分钟积分，隔多久跑都不会算错。
    """
    return hormones.tick()


def job_fatigue() -> dict:
    return curiosity.tick_fatigue()


def job_curiosity_engine() -> dict:
    """v13：自主好奇心引擎。每 30 分钟扫一遍领域，挑一个最紧迫的学习。"""
    from .. import curiosity_engine

    out = curiosity_engine.tick()
    if out.get("target"):
        sr.audit_add("curiosity", out["target"], "autonomous_pick",
                     {"urgency": out.get("urgency"), "intent": out.get("intent")})
    return out


# ── 生命周期 ────────────────────────────────────────────────────────────────
def _tick_seconds() -> int:
    cfg = settings.app().get("tick", {})
    return int(cfg.get("app_seconds", 20) if mode_is_app() else cfg.get("headless_seconds", 60))


_APP_MODE = {"value": True}


def set_app_mode(flag: bool) -> None:
    _APP_MODE["value"] = bool(flag)


def mode_is_app() -> bool:
    return _APP_MODE["value"]


def _at(text: str) -> tuple[int, int]:
    hour, minute = str(text).split(":")
    return int(hour), int(minute)


# 这几类 job 的 id 前缀：启动时先按前缀清掉旧的，再按当前配置重挂（v12 1.1）
MANAGED_PREFIXES = ("learning_", "self_dialogue_", "daily_", "archive_", "curiosity_")


def _clear_managed(sched: BackgroundScheduler) -> list[str]:
    removed = []
    try:
        for job in list(sched.get_jobs()):
            if any(str(job.id).startswith(p) for p in MANAGED_PREFIXES):
                try:
                    sched.remove_job(job.id)
                    removed.append(job.id)
                except Exception:
                    pass
    except Exception:
        pass
    return removed


def start() -> BackgroundScheduler:
    global _sched
    with _lock:
        if _sched is not None:
            return _sched
        win = settings.learning()
        sched = BackgroundScheduler(timezone=win.get("timezone") or "Asia/Shanghai")
        _clear_managed(sched)

        sched.add_job(lambda: _guard("tick", job_tick), IntervalTrigger(seconds=_tick_seconds()),
                      id="tick", max_instances=1, coalesce=True)
        sched.add_job(lambda: _guard("periodic", job_periodic), IntervalTrigger(minutes=10),
                      id="periodic", max_instances=1, coalesce=True)
        sched.add_job(lambda: _guard("chitchat", job_chitchat), IntervalTrigger(minutes=1),
                      id="chitchat", max_instances=1, coalesce=True)
        # v31 内稳态：每分钟一次（规格要求 60 秒），补跑也不会算错（按 elapsed 算）
        sched.add_job(lambda: _guard("homeostasis", job_homeostasis), IntervalTrigger(seconds=60),
                      id="homeostasis", max_instances=1, coalesce=True)
        # v33 激素：10 分钟一次（衰减 + 基线漂移 + 性格演化）
        sched.add_job(lambda: _guard("hormones", job_hormones), IntervalTrigger(minutes=10),
                      id="hormones", max_instances=1, coalesce=True)
        sched.add_job(lambda: _guard("outbox", job_outbox), IntervalTrigger(minutes=2),
                      id="outbox", max_instances=1, coalesce=True)
        sched.add_job(lambda: _guard("cooldown", job_cooldown), CronTrigger(minute=5),
                      id="cooldown", max_instances=1, coalesce=True)
        sched.add_job(lambda: _guard("fatigue", job_fatigue), CronTrigger(hour="*/6", minute=10),
                      id="fatigue", max_instances=1, coalesce=True)

        # ── 学习相关：时间全部来自 config/app.json → learning ──
        sched.add_job(lambda: _guard("learning", job_learning),
                      CronTrigger(hour=_at(win["window_start"])[0], minute=_at(win["window_start"])[1]),
                      id="learning_run", max_instances=1, coalesce=True)
        sched.add_job(lambda: _guard("learning_mid", job_learning),
                      CronTrigger(hour=_at(win["window_end"])[0], minute=_at(win["window_end"])[1]),
                      id="learning_mid", max_instances=1, coalesce=True)
        sched.add_job(lambda: _guard("practice", job_practice),
                      CronTrigger(hour=_at(win["self_dialogue_start"])[0],
                                  minute=_at(win["self_dialogue_start"])[1]),
                      id="self_dialogue_run", max_instances=1, coalesce=True)
        sched.add_job(lambda: _guard("daily", job_daily),
                      CronTrigger(hour=_at(win["consolidate_at"])[0],
                                  minute=_at(win["consolidate_at"])[1]),
                      id="daily_consolidate", max_instances=1, coalesce=True)
        sched.add_job(lambda: _guard("archive", job_archive),
                      CronTrigger(hour=_at(win["archive_at"])[0],
                                  minute=_at(win["archive_at"])[1]),
                      id="archive_daily", max_instances=1, coalesce=True)
        # v13 好奇心引擎：间隔可配（默认 30 分钟），开关在 config/curiosity_engine.json
        try:
            interval = int(settings.load("curiosity_engine").get("interval_minutes", 30) or 30)
        except Exception:
            interval = 30
        sched.add_job(lambda: _guard("curiosity_engine", job_curiosity_engine),
                      IntervalTrigger(minutes=max(1, interval)),
                      id="curiosity_engine_tick", max_instances=1, coalesce=True, jitter=30)
        sched.start()
        _sched = sched
        # 补跑放后台：开局就跑 daily 会卡住界面（要压缩、要调模型）
        threading.Thread(target=_catch_up, name="dafeiyu-catchup", daemon=True).start()
        return sched


def stop() -> None:
    global _sched
    with _lock:
        if _sched is not None:
            try:
                _sched.shutdown(wait=False)
            except Exception:
                pass
            _sched = None


def _catch_up() -> None:
    """开机补跑：窗口过了就算了，但要记一笔，别静默漏掉。"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    try:
        if now.hour >= 3 and db.get_meta(f"daily_done:{today}") != "1":
            _guard("daily_light", lambda: consolidate.daily(light=True))
            db.set_meta(f"daily_done:{today}", "1")
    except Exception:
        pass


def jobs() -> list[dict]:
    if _sched is None:
        return []
    out = []
    for job in _sched.get_jobs():
        out.append({"id": job.id, "next": str(getattr(job, "next_run_time", "")),
                    "trigger": str(job.trigger)})
    return out


def status() -> dict:
    return {"running": _sched is not None, "jobs": jobs(), "last": dict(LAST),
            "tick_seconds": _tick_seconds()}
