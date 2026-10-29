# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# 详见根目录 LICENSE 与 ADDITIONAL_TERMS.md。
# 本文件不含任何开发者的个人信息与真实数据。
# ─────────────────────────────────────────────────────────────────────────────
"""拒绝信号：六路打分，各自 0~1。

emotion      负面情绪越高越想拒绝
will         跟性格/价值观冲突（要她去骗人、骂人、报复）
competence   元认知：不确定/不会（该协商或转移，而不是硬编）
boundary     边界：隐私、安全、被强迫（这一路最重，且优先于其它）
fatigue      疲劳：刚拒过、被反复施压、碎碎念没人理
relationship 关系：被尊重就更容易答应，被辱骂就更硬
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .. import db, settings
from ..entity import now_iso
from ..repo import emotion as er
from ..repo import learning as lr
from ..text import clip

COERCION = ("必须", "一定要", "不许拒绝", "你必须", "快点", "马上", "别废话", "非要", "就要你")


def _cfg() -> dict:
    return settings.load("refusal")


def _hits(text: str, words) -> int:
    body = text or ""
    return sum(1 for w in words if w and w in body)


def score_emotion(vec) -> float:
    neg = (vec.get("sadness") + vec.get("inferiority")) / 2.0
    return round(min(1.0, neg / 100.0 * 1.15), 3)


def score_will(text: str) -> float:
    cfg = _cfg()
    hits = _hits(text, cfg.get("will_keywords") or [])
    return round(min(1.0, 0.35 * hits), 3)


def score_boundary(text: str) -> float:
    cfg = _cfg()
    hits = _hits(text, cfg.get("boundary_keywords") or [])
    coercion = _hits(text, COERCION)
    value = 0.42 * hits + 0.22 * coercion
    return round(min(1.0, value), 3)


def score_competence(text: str) -> float:
    """问句且知识库里没有对应条目 → 不确定。"""
    body = text or ""
    if not any(m in body for m in ("?", "？", "什么", "怎么", "为什么", "是不是", "会不会")):
        return 0.1
    try:
        items = lr.knowledge_list(limit=200)
    except Exception:
        items = []
    from ..text import bigrams

    tokens = set(bigrams(body))
    for item in items:
        hay = set(item.concepts or []) | set(bigrams(item.name or ""))
        if len(tokens & hay) >= 2:
            return round(max(0.05, float(item.uncertainty) * 0.6), 3)
    return 0.55


def score_fatigue() -> float:
    """刚拒过 + 碎碎念疲劳 + 最近被施压次数。"""
    from ..cognition import chitchat

    state = chitchat.load()
    value = 0.18 * min(3, int(state.fatigue_level))
    try:
        recent = [d for d in db.q(
            "SELECT decision, t FROM refusal_decision WHERE t >= datetime('now','localtime','-120 minutes')")]
        refused = sum(1 for r in recent if r["decision"] in ("REFUSE", "DEFLECT"))
        value += 0.12 * min(3, refused)
    except Exception:
        pass
    return round(min(1.0, value), 3)


def score_relationship() -> float:
    """近 6 小时：被在乎/被夸 → 降；被骂/被晾 → 升。"""
    try:
        rows = er.reward_recent(40)
    except Exception:
        rows = []
    cutoff = (datetime.now() - timedelta(hours=6)).isoformat(timespec="seconds")
    value = 0.0
    for ev in rows:
        if (ev.t or "") < cutoff:
            continue
        if ev.trigger in ("cared", "praise", "intimacy", "request_met"):
            value -= 0.12
        elif ev.trigger in ("insult", "abandoned", "ignored"):
            value += 0.18
    return round(max(0.0, min(1.0, 0.35 + value)), 3)


def score(text: str, vec, policy=None) -> dict:
    return {
        "emotion": score_emotion(vec),
        "will": score_will(text),
        "competence": score_competence(text),
        "boundary": score_boundary(text),
        "fatigue": score_fatigue(),
        "relationship": score_relationship(),
    }


def propensity(signals: dict) -> float:
    """六路加权汇聚成拒绝倾向。

    单纯加权和会被稀释（六项都不高时最高也只有 0.3），所以再给几个「单独就够重」的信号
    加下限：边界 / 情绪 / 意愿 / 疲劳各自有直接抬升项。
    这样才符合验收：负面高时拒绝**部分**请求（不是全拒），越界时基本必拒。
    """
    weights = (_cfg().get("weights") or {})
    base = 0.0
    for key, weight in weights.items():
        base += float(weight) * float(signals.get(key, 0.0))
    value = base

    boundary = float(signals.get("boundary", 0.0))
    if boundary >= 0.5:
        value = max(value, 0.50 + 0.40 * boundary)
    emotion = float(signals.get("emotion", 0.0))
    if emotion >= 0.6 and base > 0.18:
        value = max(value, 0.35 + 0.35 * emotion)
    will = float(signals.get("will", 0.0))
    if will >= 0.5:
        value = max(value, 0.30 + 0.50 * will)
    fatigue = float(signals.get("fatigue", 0.0))
    if fatigue >= 0.4:
        value = max(value, 0.30 + 0.40 * fatigue)
    return round(max(0.0, min(1.0, value)), 3)
