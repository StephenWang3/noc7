"""责任方和城市级故障点：模型判断语义，本地核验关系、覆盖和来源优先级。"""
from __future__ import annotations

import hashlib

from ..quote_match import match_quote
from ..schema import ElementStatus, IssueCode, SpanRole
from ..schema.relations import BusinessCoverage, ConstraintCheck

NAMES = ("responsible_party", "location")
ROLE_FIELDS = {
    "responsible_party": {"vendor", "handler", "handling_dept"},
    "location": {"a_end", "z_end", "device_location", "device_name", "region", "shelf_slot_port"},
}
PRIORITY = {"rfo": 0, "vendor_feedback": 1, "branch_log": 2}
SOURCE_LABELS = {"rfo": "RFO", "vendor_feedback": "供应商反馈", "branch_log": "分公司处理日志", "unknown": "来源未明"}
PATH_LABELS = {"explicit_responsibility": "明确责任归属", "customer_self_check": "客户自查且未再追问",
               "vendor_onsite_contact": "联络供应商上门", "unicom_onsite_recovery": "联通上门处理后恢复",
               "equipment_ownership": "设备采购归属线索", "role_only": "仅角色", "unknown": "依据未明"}
ANCHORS = ("responsibility_quote", "source_quote", "procurement_quote", "self_check", "vendor_contact", "unicom_onsite", "service_recovered", "city_quote")


def relation_quotes(relation):
    if relation:
        yield from relation.context
        for key in ANCHORS:
            quote = getattr(relation, key, None)
            if quote:
                yield quote


def _hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def build_coverage(ctx):
    """只声明本包原始处理记录的覆盖，不声明源系统绝对完整。"""
    entries = [e for e in ctx.bundle.process_log.entries if e.entry_kind != "ai_summary" and e.content.strip()]
    hashes = {str(e.seq): _hash(e.content) for e in entries}
    covered = {}
    for span in ctx.evidence:
        if span.locator.type == "log_entry" and reliable(span):
            seq = str(span.locator.seq)
            if hashes.get(seq) == _hash(span.text):
                covered[seq] = span.id
    related = {mid for e in entries for mid in [*e.emails, *e.attachments]}
    available = {s.material_id for s in ctx.evidence if reliable(s)}
    return BusinessCoverage(detail_status=ctx.bundle.ticket.status.detail_status,
                            log_hashes=hashes, covered_logs=covered,
                            related_materials_complete=related <= available)


def reliable(span):
    return (not span.needs_review and (span.quality is None or span.quality >= 0.7)
            and span.role not in {SpanRole.SIGNATURE, SpanRole.DERIVED_SUMMARY, SpanRole.QUOTED})


def coverage_complete(coverage, spans):
    if not coverage or coverage.detail_status != "已结单" or not coverage.log_hashes or not coverage.related_materials_complete:
        return False
    if set(coverage.log_hashes) != set(coverage.covered_logs):
        return False
    for seq, ref in coverage.covered_logs.items():
        span = spans.get(ref)
        if (not span or not reliable(span) or span.locator.type != "log_entry"
            or str(span.locator.seq) != seq or _hash(span.text) != coverage.log_hashes[seq]):
            return False
    return True


def formal_value(candidate, name):
    if candidate.relation:
        return candidate.relation.category if name == "responsible_party" else candidate.relation.city
    return candidate.party if name == "responsible_party" else candidate.description


def pending_reason(candidate, name, spans, coverage=None):
    r = candidate.relation
    if r is None:
        return "缺少完整结构化业务关系，保留待核对。"
    if not r.current_event or r.modality != "asserted":
        return "不是本次事件的明确断言。"
    if r.source_tier not in PRIORITY:
        return "来源不属于 RFO、供应商反馈或分公司处理日志。"
    if r.source_quote is None:
        return "缺少来源层级的直接引文依据。"
    quotes = list(relation_quotes(r))
    for q in quotes:
        span = spans.get(q.evidence_id)
        if not span or match_quote(q.quote, span.text).status == "mismatch":
            return "业务关系引文不匹配或缺少来源，待核对。"
        if not reliable(span):
            return "业务关系依据仅为引用、摘要、签名或低质量材料。"
    support = [spans[ref] for ref in dict.fromkeys([*candidate.evidence_refs, *(q.evidence_id for q in quotes)]) if ref in spans]
    if support and all(span.locator.type == "field" and span.locator.field_key in ROLE_FIELDS[name] for span in support):
        return "依据仅为角色或端点／告警位置字段，保留候选待核对，不影响其他要素。"
    raw = candidate.party if name == "responsible_party" else candidate.description
    if not any(ref in spans and reliable(spans[ref]) and match_quote(raw, spans[ref].text).status != "mismatch"
               for ref in candidate.evidence_refs):
        return "候选原文缺少可靠直接来源。"
    if not any(match_quote(r.statement, q.quote).status != "mismatch" for q in r.context):
        return "关系上下文没有包含本条原文断言。"
    if match_quote(raw, r.statement).status == "mismatch":
        return "原文断言未包含候选摘录。"
    if name == "location":
        if candidate.role != "located_fault_point" or not r.located:
            return "不是已定位故障点，端点、告警位置和测试节点不能采用。"
        if r.city_scope != "single_city":
            return "城市范围未明确为 single_city，跨城或范围未知只能留候选。"
        if candidate.granularity in {None, "country"}:
            return "地点仅到国家、跨城段落或粒度未明，不能推测城市。"
        if not r.city or not r.city.strip() or not r.city_quote or match_quote(r.city, r.city_quote.quote).status == "mismatch":
            return "没有可核验的明确城市归属。"
    else:
        if r.category not in {"客户", "供应商", "联通"}:
            return "其他主体、共同责任或分类未明，只保留候选。"
        if candidate.basis == "claimed":
            return "责任仅为某方主张，保留候选待核对。"
        if candidate.basis == "inferred_from_role":
            return "仅凭供应商、处理部门等角色不能定责。"
        path = r.decision_path
        if r.category == "客户" and (r.vendor_contact or r.unicom_onsite):
            return "客户侧设备仍有其他提供方上门处理线索，不能据设备故障直接采用客户责任。"
        if path == "explicit_responsibility":
            if candidate.basis != "formal_determination" or r.customer_device_fault is not False:
                return "明确归属须为 formal_determination 且 customer_device_fault is False；客户设备或前提未明须走完整上下文路径。"
            if r.self_check or r.vendor_contact or r.unicom_onsite:
                return "明确归属不能绕过自查或上门上下文路径。"
            if not r.responsibility_quote:
                return "明确归属路径缺少专门责任依据，不能把供应商角色或客户侧现象当成责任。"
            if not any(match_quote(r.responsibility_quote.quote, q.quote).status != "mismatch" for q in r.context):
                return "责任依据没有包含在本条关系上下文中。"
            return None
        if not r.customer_device_fault:
            return "上下文路径缺少客户侧设备故障前提。"
        if path == "customer_self_check":
            if r.category != "客户" or not r.self_check or r.no_followup is not True:
                return "客户责任路径缺少自查或未再追问关系。"
            if r.vendor_contact or r.unicom_onsite or r.procurement in {"供应商", "联通"}:
                return "仍有其他提供方或上门处理线索，不能采用客户自查路径。"
            if not coverage_complete(coverage, spans):
                return "输入未覆盖完整已结单处理记录及关联材料，不能判断未再追问。"
        elif path == "vendor_onsite_contact":
            if r.unicom_onsite:
                return "供应商与联通上门线索同时存在，责任待核对。"
            if r.category != "供应商" or not r.vendor_contact:
                return "供应商责任路径缺少联络供应商上门依据。"
        elif path == "unicom_onsite_recovery":
            if r.vendor_contact:
                return "供应商与联通上门线索同时存在，责任待核对。"
            if r.category != "联通" or not r.unicom_onsite or not r.service_recovered:
                return "联通责任路径缺少上门处理与业务恢复依据。"
        else:
            return "采购归属或角色本身不能替代明确责任或业务上下文路径。"
        if r.procurement != "unknown" and not r.procurement_quote:
            return "采购归属没有原文依据。"
    return None


def grounded_assertion(candidate, name, spans):
    """反证不必能成为正面结论，但原断言、上下文和出处都必须可靠。"""
    r = candidate.relation
    if not r or not r.source_quote:
        return False
    quotes = list(relation_quotes(r))
    if not all(q.evidence_id in spans and reliable(spans[q.evidence_id])
               and match_quote(q.quote, spans[q.evidence_id].text).status != "mismatch" for q in quotes):
        return False
    raw = candidate.party if name == "responsible_party" else candidate.description
    return (bool(candidate.evidence_refs)
            and all(ref in spans for ref in candidate.evidence_refs)
            and any(reliable(spans[ref]) and match_quote(raw, spans[ref].text).status != "mismatch"
                    for ref in candidate.evidence_refs)
            and match_quote(raw, r.statement).status != "mismatch"
            and any(match_quote(r.statement, q.quote).status != "mismatch" for q in r.context))


def evaluate(elements, spans, coverage, suggestions=()):
    """纯函数，首次分析、完整证据校验及保存结果再加载共同调用。"""
    updates, checks = {}, []
    for name in NAMES:
        el = getattr(elements, name)
        eligible = []
        known = {c.id for c in el.candidates}
        for c in el.candidates:
            reason = pending_reason(c, name, spans, coverage)
            if reason is None and any(q["evidence_id"] in c.evidence_refs
                                      and (q["evidence_id"] not in spans
                                           or match_quote(q["quote"], spans[q["evidence_id"]].text).status == "mismatch")
                                      for s in suggestions if s.element == name for q in s.quotes):
                reason = "该候选的显式业务引文不匹配，保留待核对。"
            if (reason is None and name == "responsible_party" and c.relation.category == "客户"
                and any(other.relation and other.id != c.id and other.relation.current_event
                        and (other.relation.event_id, other.relation.scope) == (c.relation.event_id, c.relation.scope)
                        and any(q and q.evidence_id in spans and reliable(spans[q.evidence_id])
                                and match_quote(q.quote, spans[q.evidence_id].text).status != "mismatch"
                                for q in (other.relation.vendor_contact, other.relation.unicom_onsite))
                        for other in el.candidates)):
                reason = "其他候选仍有同事件的提供方上门线索，不能据客户侧设备故障采用客户责任。"
            if c.relation and any(ref not in known or ref == c.id for ref in c.relation.contradicts):
                reason = "矛盾关系指向缺失、歧义或自身候选。"
            checks.append(ConstraintCheck(element=name, candidate_id=c.id,
                outcome="pending" if reason else "eligible", reason=reason or "结构及引文核验通过；业务语义未经人工审核。",
                evidence_refs=c.evidence_refs))
            if reason is None:
                eligible.append(c)
        update = dict(status=ElementStatus.UNKNOWN, value=None, selected=None, evidence_refs=[], note="依据不足，保留候选及原始回答待核对。" if el.candidates else None)
        if eligible:
            rank = min(PRIORITY[c.relation.source_tier] for c in eligible)
            top = [c for c in eligible if PRIORITY[c.relation.source_tier] == rank]
            different = len({formal_value(c, name) for c in top}) > 1
            opponents = [b for b in el.candidates if any(
                b.id != a.id and b.relation
                and b.relation.source_tier == a.relation.source_tier
                and (b.relation.event_id, b.relation.scope) == (a.relation.event_id, a.relation.scope)
                and b.relation.current_event and b.relation.modality in {"asserted", "negated"}
                and grounded_assertion(b, name, spans)
                and (b.id in a.relation.contradicts or a.id in b.relation.contradicts
                     or (b.relation.modality == "negated" and formal_value(b, name) == formal_value(a, name)))
                for a in top)]
            opposing = bool(opponents)
            if different or opposing:
                update.update(status=ElementStatus.CONFLICTED, note="最高有效来源同层结论无法消解，正式留空。")
                checks.append(ConstraintCheck(element=name, outcome="conflict", code=IssueCode.SEMANTIC_ASSERTIONS_CONFLICT,
                    reason=update['note'], evidence_refs=list(dict.fromkeys(r for c in [*top, *opponents] for r in c.evidence_refs))))
            else:
                chosen = top[0]
                refs = list(dict.fromkeys([*chosen.evidence_refs, *(q.evidence_id for q in relation_quotes(chosen.relation))]))
                lower = [c for c in el.candidates if c.relation and c.relation.source_tier in PRIORITY
                         and PRIORITY[c.relation.source_tier] > rank
                         and (formal_value(c, name) != formal_value(chosen, name) or c.id in chosen.relation.contradicts
                              or chosen.id in c.relation.contradicts)]
                note = SOURCE_LABELS[chosen.relation.source_tier] + "；有记录，未经人工审核。"
                if name == "responsible_party":
                    note += "路径：" + PATH_LABELS[chosen.relation.decision_path] + "。"
                    if chosen.relation.decision_path == "customer_self_check":
                        note += "未再追问仅指本次提供的完整已结单处理记录。"
                if lower:
                    note += "低优先级差异保留待核对：" + "、".join(c.id for c in lower) + "。"
                    checks.append(ConstraintCheck(element=name, candidate_id=chosen.id, outcome="downgraded",
                        reason="按来源优先级采用；" + note, evidence_refs=refs))
                update.update(status=ElementStatus.DOCUMENTED, value=formal_value(chosen, name),
                              selected=chosen.id, evidence_refs=refs, note=note)
        updates[name] = el.model_copy(update=update)
    return updates, checks


def apply_constraints(ctx, data):
    assessment = data.semantic_assessment
    if not assessment or not any(n in assessment.original for n in NAMES):
        return data  # 规则提供方和没有新关系的旧保存结果不重解释
    updates, checks = evaluate(data.elements, {s.id: s for s in ctx.evidence}, assessment.business_coverage, data.suggestions)
    kept = [c for c in assessment.checks if c.element not in NAMES]
    return data.model_copy(update={"elements": data.elements.model_copy(update=updates),
                                  "semantic_assessment": assessment.model_copy(update={"checks": [*kept, *checks]})})


def validate_saved(elements, spans, assessment, suggestions=()):
    if not assessment or not any(n in assessment.original for n in NAMES):
        if any(c.relation is not None for name in NAMES for c in getattr(elements, name).candidates):
            raise ValueError("新增业务关系缺少本地原答审计，不能伪装成旧结果")
        return
    updates, _ = evaluate(elements, spans, assessment.business_coverage, suggestions)
    for name in NAMES:
        actual, expected = getattr(elements, name), updates[name]
        if any(getattr(actual, k) != getattr(expected, k) for k in ("status", "value", "selected", "evidence_refs", "note")):
            raise ValueError("正式责任方或地点未遵守结构化业务约束")
