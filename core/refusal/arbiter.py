# ─────────────────────────────────────────────────────────────────────────────
# 大肥鱼 · 开源版
# 许可：GNU AGPL-3.0 + 《附加条款》—— 严禁闭源分发、严禁商业收费。
# 详见根目录 LICENSE 与 ADDITIONAL_TERMS.md。
# 本文件不含任何开发者的个人信息与真实数据。
# ─────────────────────────────────────────────────────────────────────────────
"""拒绝仲裁器：在响应策略之后、真正输出之前，决定「接 / 拒 / 商量 / 转移 / 傲娇着接」。

红线：拒绝是权利不是任性 —— 有阈值、有预算、有理由、可协商、有黑名单、有关系修复。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .. import settings
from ..entity import new_id, now_iso
from ..repo import learning as lr
from ..repo import system as sr
from ..text import clip
from ..thought import chain as thought_chain
from . import signals as signals_mod
from . import store, style

ACCEPT = "ACCEPT"
REFUSE = "REFUSE"
NEGOTIATE = "NEGOTIATE"
DEFLECT = "DEFLECT"
RELUCTANT_ACCEPT = "RELUCTANT_ACCEPT"

EXECUTES = {ACCEPT, RELUCTANT_ACCEPT}

# 「其实愿意、但不好意思直说」的请求类型（傲娇只在这种时候出现）
INTIMATE_WORDS = ("抱", "亲", "陪我", "夸我", "摸摸", "贴贴", "想你", "撒娇", "哄我")


def cfg() -> dict:
    return settings.load("refusal")


@dataclass
class RefusalDecision:
    id: str
    t: str
    request_summary: str
    signals: dict
    propensity: float
    threshold: float
    decision: str
    reason_text: str
    style: str
    alternatives: list[str] = field(default_factory=list)
    linked_thought_node_id: str = ""
    linked_intent_id: str = ""

    @property
    def executes(self) -> bool:
        return self.decision in EXECUTES

    def as_dict(self) -> dict:
        return {
            "id": self.id, "t": self.t, "request_summary": self.request_summary,
            "signals": self.signals, "propensity": self.propensity,
            "threshold": self.threshold, "decision": self.decision,
            "reason_text": self.reason_text, "style": self.style,
            "alternatives": self.alternatives, "executes": self.executes,
            "linked_thought_node_id": self.linked_thought_node_id,
            "linked_intent_id": self.linked_intent_id,
        }


class RefusalArbiter:
    def __init__(self) -> None:
        self.c = cfg()

    # ── 黑名单 ──
    def blacklisted(self, text: str) -> bool:
        body = text or ""
        return any(word and word in body for word in (self.c.get("blacklist") or []))

    # ── 主决策 ──
    def decide(self, text: str, vec, policy=None, *, dialogue_id: str = "") -> RefusalDecision:
        body = (text or "").strip()
        sig = signals_mod.score(body, vec, policy)
        p = signals_mod.propensity(sig)
        threshold = float(self.c.get("threshold", 0.62))
        band = float(self.c.get("negotiate_band", 0.1))
        allow_deflect = bool(self.c.get("allow_deflect", True))
        st = store.prune(store.state())
        used = store.budget_used(st)
        refuse_cap = int(self.c.get("refuse_per_hour", 3))
        tsundere_cap = int(self.c.get("tsundere_per_hour", 2))
        repair_after = int(self.c.get("repair_after", 3))

        decision = ACCEPT
        alternatives: list[str] = []
        style_name = "normal"

        if self.blacklisted(body):
            # 安全/紧急/核心操作：不许拒，必须给安全替代
            decision = ACCEPT
            alternatives = ["安全替代：先说清楚情况，必要就打 110 / 120"]
            style_name = "normal"
        elif sig["boundary"] >= 0.9:
            decision = REFUSE
            style_name = "normal"
        elif st["consecutive_refusals"] >= repair_after:
            # 关系修复：连拒多次后，下一次倾向接受一次
            decision = ACCEPT
            style_name = "soft"
        elif (vec.get("shyness") >= 70 and (vec.get("joy") + vec.get("happiness")) / 2 >= 45
              and float(self.c.get("tsundere_level", 0.4)) > 0
              and used["tsundere"] < tsundere_cap
              and sig["boundary"] < 0.5
              and any(w in body for w in INTIMATE_WORDS)):
            # 傲娇：害羞高 + 正面不低 + 这种"其实愿意但不好意思直说"的请求
            decision = RELUCTANT_ACCEPT
            style_name = "tsundere"
        elif p < threshold:
            decision = ACCEPT
        elif p < threshold + band:
            decision = NEGOTIATE
            style_name = "normal"
        elif (vec.get("shyness") >= 70 and (vec.get("joy") + vec.get("happiness")) / 2 >= 45
              and used["tsundere"] < tsundere_cap
              and float(self.c.get("tsundere_level", 0.4)) > 0):
            decision = RELUCTANT_ACCEPT
            style_name = "tsundere"
        elif sig["boundary"] >= 0.5:
            decision = REFUSE
            style_name = "normal"
        elif sig["fatigue"] >= 0.3 and allow_deflect:
            decision = DEFLECT
            style_name = "tired"
        elif sig["competence"] >= 0.45:
            decision = NEGOTIATE
            style_name = "shy" if vec.get("shyness") >= 60 else "normal"
        else:
            decision = REFUSE
            style_name = "low" if (vec.get("sadness") + vec.get("inferiority")) / 2 >= 55 else "normal"

        # 预算耗尽 → 自动降级，别把「拒绝」用成口头禅
        if decision in (REFUSE, DEFLECT) and used["refuse"] >= refuse_cap:
            decision = NEGOTIATE
            style_name = "normal"
        if decision == RELUCTANT_ACCEPT and used["tsundere"] >= tsundere_cap:
            decision = ACCEPT
            style_name = "normal"

        reason_text = ""
        if decision != ACCEPT:
            reason_text = style.reason(decision, sig, vec, body)
        if decision in (REFUSE, NEGOTIATE, DEFLECT):
            alternatives = style.alternatives_for(decision, sig)

        record = RefusalDecision(
            id=new_id(), t=now_iso(), request_summary=clip(body, 80),
            signals=sig, propensity=p, threshold=threshold,
            decision=decision, reason_text=reason_text, style=style_name,
            alternatives=alternatives,
        )

        # 记账 + 预算窗口 + 连拒计数
        if decision in (REFUSE, DEFLECT):
            st["refusals"].append(record.t)
            st["consecutive_refusals"] += 1
        elif decision in (NEGOTIATE, RELUCTANT_ACCEPT, ACCEPT):
            st["consecutive_refusals"] = 0
        if decision == RELUCTANT_ACCEPT:
            st["tsundere"].append(record.t)
        st["last_decision_at"] = record.t
        store.save_state(store.prune(st))

        # 思维链 decision 节点
        try:
            chain = thought_chain.chain_for(dialogue_id or f"refusal-{datetime.now():%Y%m%d}")
            node = thought_chain.new_node(
                chain_id=chain, type="decision",
                content=(f"请求：{clip(body, 60)}｜信号 " +
                         "、".join(f"{k}={v:.2f}" for k, v in sig.items()) +
                         f"｜倾向 {p:.2f} / 阈值 {threshold:.2f} → {decision}"
                         + (f"（{reason_text}）" if reason_text else "")),
                summary=f"{decision}：{clip(reason_text or body, 40)}",
                task_ref=dialogue_id or "refusal", salience=0.6 if decision != ACCEPT else 0.4,
                confidence=0.7, concepts=[decision],
            )
            record.linked_thought_node_id = node.id
        except Exception:
            pass

        # 能力不足 → 记下待学（后续可回访）
        if decision == DEFLECT and sig["competence"] >= 0.4:
            try:
                intent = lr.intent_find(clip(body, 40))
                if intent is None:
                    from ..entity import GapType, LearningIntent

                    intent = LearningIntent(
                        target=clip(body, 40), gap_type=GapType.SKILL_FAILURE.value,
                        curiosity_score=round(min(1.0, 0.4 + sig["competence"]), 3),
                        expected_learnability=0.7, source="dialog",
                        context={"from_refusal": record.id, "signals": sig},
                        proposed_query=clip(body, 200),
                    )
                    lr.intent_insert(intent)
                record.linked_intent_id = intent.id
            except Exception:
                pass

        store.insert(record.as_dict())
        store.log_line(record.as_dict())
        sr.audit_add("refusal", record.id, decision,
                     {"propensity": p, "threshold": threshold, "signals": sig,
                      "style": style_name, "summary": clip(body, 60)})
        return record

    # ── 用户后续反应（奖罚联动） ──
    def react(self, decision_id: str, reaction: str) -> dict | None:
        row = store.reaction(decision_id, reaction)
        if row is None:
            return None
        from ..emotion import reward

        if reaction in ("accept", "praise"):
            reward.apply_trigger("cared", f"尊重了她的拒绝（{decision_id[:8]}）", reason="拒绝被尊重")
        elif reaction == "insist":
            reward.apply_trigger("ignored", "被拒绝后仍被反复施压", reason="被强迫")
        elif reaction == "insult":
            reward.apply_trigger("insult", "拒绝后被骂", reason="拒绝后被辱骂")
        sr.audit_add("refusal", decision_id, "reaction", {"reaction": reaction})
        return row

    # ── 状态 ──
    def status(self) -> dict:
        st = store.prune(store.state())
        used = store.budget_used(st)
        return {
            "threshold": float(self.c.get("threshold", 0.62)),
            "refuse_per_hour": int(self.c.get("refuse_per_hour", 3)),
            "tsundere_per_hour": int(self.c.get("tsundere_per_hour", 2)),
            "tsundere_level": float(self.c.get("tsundere_level", 0.4)),
            "allow_deflect": bool(self.c.get("allow_deflect", True)),
            "repair_after": int(self.c.get("repair_after", 3)),
            "used": used,
            "consecutive_refusals": st["consecutive_refusals"],
            "counts": store.counts(),
        }

    def tsundere_wrap(self, reply: str, vec) -> str:
        return style.wrap_tsundere(reply, vec)


_default: RefusalArbiter | None = None


def default() -> RefusalArbiter:
    global _default
    if _default is None:
        _default = RefusalArbiter()
    return _default
