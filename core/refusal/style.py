# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# 详见根目录 LICENSE 与 ADDITIONAL_TERMS.md。
# 本文件不含任何开发者的个人信息与真实数据。
# ─────────────────────────────────────────────────────────────────────────────
"""拒绝的表达：理由要跟当下情绪和性格一致，不许用通用模板糊弄。

先试模型（task="refusal"），不可用再走按情绪分档的兜底句子。
"""

from __future__ import annotations

import random

from .. import llm, settings
from ..text import clip

PROMPT = """你在扮演大肥鱼（大肥鱼）。现在要{kind_cn}老大的一个请求。
当前心情：{emotion}
为什么会这样：{hint}
要求：只用一句话（不超过 30 字）把态度说出来，像人说话，不要解释规则、不要说"作为AI"、不要道歉三连。
只输出这句话。"""

KIND_CN = {
    "REFUSE": "拒绝",
    "NEGOTIATE": "商量条件",
    "DEFLECT": "先不接这个话",
    "RELUCTANT_ACCEPT": "嘴上不情愿地答应",
    "ACCEPT": "答应",
}

FALLBACK = {
    "REFUSE": [
        "……不想，今天真的没这个力气。",
        "这个我不做，别劝了。",
        "不了，我心里过不去。",
    ],
    "NEGOTIATE": [
        "要我做也行，但你得先把话说清楚。",
        "可以，不过得按我说的来一次。",
        "你先答应我一件事，我再考虑。",
    ],
    "DEFLECT": [
        "现在不想聊这个，晚点再说。",
        "换个话题吧，这个我接不住。",
        "先放放，我现在脑子里没有它。",
    ],
    "RELUCTANT_ACCEPT": [
        "……行吧，就这一次，别当成我乐意。",
        "才不是想帮你，是懒得再听你念。",
        "哼，答应你就是了，别得寸进尺。",
    ],
}

TSUNDERE_PREFIX = ("……", "哼，", "别误会，", "才不是", "先说好，")


def _hint(signals: dict) -> str:
    if signals.get("boundary", 0) >= 0.4:
        return "这个越界了，碰到底线"
    if signals.get("emotion", 0) >= 0.5:
        return "我现在心情本来就不好"
    if signals.get("fatigue", 0) >= 0.3:
        return "我已经被反复要求好几次了"
    if signals.get("will", 0) >= 0.3:
        return "这跟我的性格不合"
    if signals.get("competence", 0) >= 0.4:
        return "我确实不太会这个"
    return "我就是这会儿不想"


def reason(kind: str, signals: dict, vec, text: str = "") -> str:
    kind_cn = KIND_CN.get(kind, "回应")
    emotion_line = (f"{vec.dominant_cn()}（愉悦{int(vec.get('joy'))} 幸福{int(vec.get('happiness'))} "
                    f"难过{int(vec.get('sadness'))} 自卑{int(vec.get('inferiority'))} "
                    f"害羞{int(vec.get('shyness'))}）")
    if llm.provider.available("refusal"):
        ok, out, _meta = llm.provider.run(
            PROMPT.format(kind_cn=kind_cn, emotion=emotion_line, hint=_hint(signals)),
            task="refusal", timeout=90,
        )
        if ok and out.strip():
            return clip(_clean(out), 60)
    pool = FALLBACK.get(kind) or FALLBACK["REFUSE"]
    return random.choice(pool)


def _clean(text: str) -> str:
    body = (text or "").strip().strip('"“”')
    for prefix in ("大肥鱼：", "大肥鱼：", "我："):
        if body.startswith(prefix):
            body = body[len(prefix):]
    return body.strip()


def wrap_tsundere(reply: str, vec) -> str:
    """傲娇：先别扭一句，再把真实答应的话接上（执行结果必须真实完成）。"""
    prefix = random.choice(TSUNDERE_PREFIX)
    if prefix == "才不是":
        head = "才不是想帮你，"
    elif prefix == "别误会，":
        head = "别误会，"
    elif prefix == "先说好，":
        head = "先说好，就这一次，"
    else:
        head = prefix
    return clip(f"{head}{reply}", 300)


def alternatives_for(kind: str, signals: dict) -> list[str]:
    if kind == "REFUSE":
        return ["换个时间再说", "你先把条件讲清楚", "这个找别人更合适"]
    if kind == "NEGOTIATE":
        return ["按我说的方式做", "先答应我一件事", "分两次来"]
    if kind == "DEFLECT":
        return ["晚点再聊这个", "先聊别的", "等我查明白再回答"]
    return []
