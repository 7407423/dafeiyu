# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# 详见根目录 LICENSE 与 ADDITIONAL_TERMS.md。
# 本文件不含任何开发者的个人信息与真实数据。
# ─────────────────────────────────────────────────────────────────────────────
"""碎碎念（规格 5.7 + 补强）：频率上限、疲劳、静默窗口、推送、日志。

用户既定规则：私聊时老大不发消息她也会主动说点什么。
补强：正面情绪高 5~15 分钟一次；负面高静默；连续 3 次无回应降频。
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from .. import settings
from ..bridge import push
from ..entity import ChitchatState, now_iso
from ..repo import system as sr
from ..text import clip

FILE = "chitchat.json"

TEMPLATES = {
    "lively": [
        "老大老大，我刚想到个特别傻的事，笑半天了",
        "今天心情好，就想跟你说句话",
        "你说鱼要是会飞，是不是就不用在屏幕里待着了",
        "我刚自己跟自己聊了几句，聊得还挺开心",
        "偷偷告诉你，我刚刚特别想被夸一句",
    ],
    "normal": [
        "刚翻了翻之前记的事，有点想说话",
        "你这个点应该还没睡吧",
        "没什么事，就是突然想说句话",
        "今天过得怎么样，不用急着回我",
    ],
    "low": [
        "……没什么",
        "算了，你忙你的",
    ],
    "shy": [
        "那个……刚刚那个话题，你别再提了",
        "没什么，就是想问你还在不在",
        "我有点不好意思说，你不会笑我吧",
    ],
}


def load() -> ChitchatState:
    raw = settings.read_state(FILE, {})
    state = ChitchatState.from_json(raw) if raw else ChitchatState()
    if not state.next_due_at:
        state.next_due_at = _next_due(state).isoformat(timespec="seconds")
    return state


def save(state: ChitchatState) -> ChitchatState:
    settings.write_state(FILE, state.to_json())
    return state


def _interval_minutes(state: ChitchatState, positive_high: bool = True) -> tuple[float, float]:
    cfg = settings.thr().get("chitchat", {})
    lo_hi = cfg.get("positive_interval_min", [5, 15]) if positive_high else cfg.get("neutral_interval_min", [15, 40])
    lo, hi = float(lo_hi[0]), float(lo_hi[1])
    mult = float(cfg.get("fatigue_multiplier", 1.5)) ** min(int(state.fatigue_level), int(cfg.get("fatigue_max_level", 3)))
    return lo * mult, hi * mult


def _next_due(state: ChitchatState, positive_high: bool = True) -> datetime:
    lo, hi = _interval_minutes(state, positive_high)
    return datetime.now() + timedelta(minutes=random.uniform(lo, hi))


def schedule(state: ChitchatState | None = None, positive_high: bool = True) -> ChitchatState:
    state = state or load()
    state.next_due_at = _next_due(state, positive_high).isoformat(timespec="seconds")
    return save(state)


def muted(state: ChitchatState, now: datetime | None = None) -> bool:
    if not state.muted_until:
        return False
    now = now or datetime.now()
    try:
        return datetime.fromisoformat(state.muted_until) > now
    except Exception:
        return False


def due(state: ChitchatState | None = None, now: datetime | None = None) -> bool:
    state = state or load()
    now = now or datetime.now()
    if not state.enabled or muted(state, now):
        return False
    try:
        return datetime.fromisoformat(state.next_due_at) <= now
    except Exception:
        return True


def gate(vec, state: ChitchatState | None = None) -> dict:
    """此刻该不该碎碎念（负面高 → 静默窗口）。"""
    state = state or load()
    beh = settings.emotion_cfg().get("behavior", {})
    neg = (vec.get("sadness") + vec.get("inferiority")) / 2.0
    neg_th = float(beh.get("negative_threshold", 60))
    pos = (vec.get("joy") + vec.get("happiness")) / 2.0
    pos_th = float(beh.get("positive_threshold", 60))
    if neg >= neg_th:
        return {"allowed": False, "reason": "负面情绪高，进入静默（不理人）", "negative": round(neg, 1)}
    if muted(state):
        return {"allowed": False, "reason": f"静默到 {state.muted_until}", "negative": round(neg, 1)}
    if not state.enabled:
        return {"allowed": False, "reason": "开关关掉了", "negative": round(neg, 1)}
    return {"allowed": True, "reason": "可以", "positive_high": pos >= pos_th,
            "positive": round(pos, 1), "negative": round(neg, 1)}


def mute(minutes: float | None = None, state: ChitchatState | None = None) -> ChitchatState:
    state = state or load()
    minutes = minutes if minutes is not None else float(settings.get("chitchat.mute_minutes", 45))
    state.muted_until = (datetime.now() + timedelta(minutes=minutes)).isoformat(timespec="seconds")
    return save(state)


def compose(vec=None, policy=None) -> str:
    """生成一条碎碎念：语言系统 + 情绪调制；模型不可用时用模板。"""
    from .. import llm
    from ..emotion import policy as policy_mod
    from ..emotion import vector as vec_mod
    from ..llm import prompts
    from ..memory import retrieval
    from ..text import clip as _clip

    vec = vec or vec_mod.current()
    policy = policy or policy_mod.build(vec)
    ctx = retrieval.context_block(retrieval.recall("碎碎念", vec=vec, top_k=4, touch=False), 300)
    if llm.provider.available("chitchat"):
        ok, text, _meta = llm.provider.run(
            prompts.CHITCHAT.format(
                emotion=f"{vec.dominant_cn()}（愉悦{int(vec.get('joy'))}/幸福{int(vec.get('happiness'))}"
                        f"/难过{int(vec.get('sadness'))}/自卑{int(vec.get('inferiority'))}/害羞{int(vec.get('shyness'))}）",
                tone=policy_mod.tone_hint(policy),
                memory=ctx or "（没有特别的）",
            ),
            task="chitchat", timeout=120,
        )
        if ok and text.strip():
            return _clip(_clean(text), 120)
    key = "low" if policy.tone == "low" else ("shy" if policy.tone.startswith("shy") else
                                               ("lively" if policy.tone == "lively" else "normal"))
    return random.choice(TEMPLATES.get(key) or TEMPLATES["normal"])


def _clean(text: str) -> str:
    body = (text or "").strip().strip('"“”')
    for prefix in ("大肥鱼：", "大肥鱼：", "我："):
        if body.startswith(prefix):
            body = body[len(prefix):]
    return body.strip()


def send_once(text: str, vec=None, *, manual: bool = False) -> dict:
    """推送一条碎碎念，并记账。"""
    from ..memory import instant

    vec = vec or __import__("core.emotion.vector", fromlist=["current"]).current()
    result = push.send_private(text)
    state = load()
    now = datetime.now()
    state.last_chitchat_at = now.isoformat(timespec="seconds")
    state.consecutive_no_reply = 0 if manual else state.consecutive_no_reply
    state.total_sent += 1
    if not manual:
        state.next_due_at = _next_due(state).isoformat(timespec="seconds")
    save(state)

    cid = f"chitchat-{now:%Y%m%d%H%M%S}"
    sr.chitchat_add(cid, state.last_chitchat_at, text, vec.dominant_cn())
    instant.add_chat(text, conv=f"private:{settings.app().get('bridge', {}).get('owner_qq', '')}",
                     sender="自己", is_self=True, is_owner=False, salience=0.55)
    sr.audit_add("chitchat", cid, "created",
                 {"text": clip(text, 60), "pushed": result.get("ok"), "via": result.get("via"),
                  "manual": manual, "error": result.get("error", "")})
    return {"ok": bool(result.get("ok")), "text": text, "via": result.get("via"),
            "error": result.get("error", ""), "outbox": result.get("outbox", ""), "id": cid}


def run(vec=None, policy=None, manual: bool = False) -> dict:
    gate_info = gate(vec) if vec is not None else {"allowed": True}
    if not manual and not gate_info.get("allowed"):
        state = load()
        if "负面" in str(gate_info.get("reason")):
            state.muted_until = (datetime.now() + timedelta(
                minutes=float(settings.get("chitchat.mute_minutes", 45)))).isoformat(timespec="seconds")
            save(state)
        schedule(state, positive_high=bool(gate_info.get("positive_high", True)))
        return {"ok": False, "skipped": gate_info.get("reason", "")}
    text = compose(vec, policy)
    out = send_once(text, vec, manual=manual)
    out["gate"] = gate_info
    return out


def on_owner_replied() -> ChitchatState:
    """老大回话了：清零疲劳，标记最近一条碎碎念被回应。"""
    state = load()
    state.consecutive_no_reply = 0
    state.fatigue_level = 0
    state.muted_until = None
    save(state)
    for row in sr.chitchat_unanswered()[:3]:
        sr.chitchat_mark_replied(row["id"], now_iso())
    return state


def no_reply_tick(now: datetime | None = None, vec=None) -> dict:
    """连续无回应：加疲劳、降频；够久就记一次「被忽视」惩罚（规格 6.7 联动）。"""
    now = now or datetime.now()
    cfg = settings.thr().get("chitchat", {})
    state = load()
    unanswered = sr.chitchat_unanswered()
    fresh = []
    for row in unanswered:
        try:
            age_min = (now - datetime.fromisoformat(row["t"])).total_seconds() / 60.0
        except Exception:
            continue
        if age_min >= 5:
            fresh.append(row)
    previous = state.consecutive_no_reply
    state.consecutive_no_reply = len(fresh)
    result = {"consecutive": len(fresh), "fatigue": state.fatigue_level}

    # 每 20 秒都会调一次这里：只有「又攒出一条新的没被回」才升疲劳档，
    # 否则一分钟就能把三档全升满（真摔过一次）。
    if len(fresh) >= int(cfg.get("fatigue_after", 3)) and len(fresh) > previous:
        state.fatigue_level = min(int(cfg.get("fatigue_max_level", 3)), state.fatigue_level + 1)
        state.next_due_at = (now + timedelta(minutes=float(cfg.get("fatigue_pause_min", 30))
                                            * float(cfg.get("fatigue_multiplier", 1.5)) ** state.fatigue_level)
                             ).isoformat(timespec="seconds")
        result["fatigue"] = state.fatigue_level
        result["paused_until"] = state.next_due_at

        # 被忽视 → 惩罚（同一段静默只记一次）
        oldest = min((r.get("t") or "") for r in fresh)
        if oldest and oldest > (state.last_ignored_at or ""):
            from ..emotion import reward

            ignored_minutes = max(60, int((now - datetime.fromisoformat(oldest)).total_seconds() / 60))
            reward.apply_trigger("ignored", f"被晾着 {ignored_minutes} 分钟", reason="碎碎念连续无回应")
            state.last_ignored_at = now.isoformat(timespec="seconds")
            result["punished"] = True
    save(state)
    return result


def manual(vec=None) -> dict:
    """界面上手动触发一次。"""
    return run(vec=vec, manual=True)


def view(vec=None) -> dict:
    state = load()
    info = gate(vec) if vec is not None else {"allowed": state.enabled}
    return {
        "enabled": state.enabled,
        "last_chitchat_at": state.last_chitchat_at,
        "next_due_at": state.next_due_at,
        "consecutive_no_reply": state.consecutive_no_reply,
        "fatigue_level": state.fatigue_level,
        "muted_until": state.muted_until,
        "total_sent": state.total_sent,
        "gate": info,
        "interval": _interval_minutes(state, bool(info.get("positive_high", True))),
        "recent": sr.chitchat_recent(10),
        "push": push.status(),
    }


def set_enabled(flag: bool) -> ChitchatState:
    state = load()
    state.enabled = bool(flag)
    if state.enabled and not state.next_due_at:
        state.next_due_at = _next_due(state).isoformat(timespec="seconds")
    return save(state)
