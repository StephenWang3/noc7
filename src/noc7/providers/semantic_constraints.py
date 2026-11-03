"""对模型关系做结构、来源和数值约束；不根据句式重判业务语义。"""
from datetime import timedelta
from itertools import combinations
import re

from ..schema import ElementStatus, TimeKind, TimePrecision, TimeZoneSource, SpanRole, IssueCode
from ..schema.relations import ConstraintCheck
from ..quote_match import match_quote
from ..timeparse import parse_time
from ..schema.timeval import TimeValue

NAMES = ("start_time", "end_time", "cause")
START = {TimeKind.BUSINESS_START, TimeKind.FAULT_START_FIELD, TimeKind.CUSTOMER_REPORTED_START, TimeKind.ALARM_RAISED}
END = {TimeKind.BUSINESS_RECOVERY, TimeKind.RECOVERY_FIELD}
TIME_LABELS = {
    "business_start": "业务起点", "fault_start_field": "起障字段记载",
    "customer_reported_start": "客户报告起点", "alarm_raised": "告警时刻",
    "business_recovery": "业务恢复时刻", "recovery_field": "恢复字段记载",
    "confirmation_action": "确认动作时刻", "protocol_down": "协议 Down",
    "protocol_up": "协议 Up", "customer_confirmed_recovery": "客户确认时刻（旧口径）",
}


def relation_quotes(relation):
    if relation:
        yield from relation.context
        for key in ("date_anchor", "timezone_anchor", "customer_confirmation", "recovery_source_basis", "correction_basis"):
            quote = getattr(relation, key, None)
            if quote:
                yield quote


def original_quotes(node):
    if isinstance(node, dict):
        if isinstance(node.get("evidence_id"), str) and isinstance(node.get("quote"), str):
            yield node["evidence_id"], node["quote"]
        for value in node.values():
            yield from original_quotes(value)
    elif isinstance(node, list):
        for value in node:
            yield from original_quotes(value)


def original_refs(node):
    """补全丢弃的异常候选也不能隐藏不存在的来源。"""
    if isinstance(node, dict):
        refs = node.get("evidence_refs", []) or []
        if isinstance(refs, str):
            refs = [refs]
        if isinstance(refs, list):
            yield from (r for r in refs if isinstance(r, str))
        if isinstance(node.get("evidence_id"), str):
            yield node["evidence_id"]
        for value in node.values():
            yield from original_refs(value)
    elif isinstance(node, list):
        for value in node:
            yield from original_refs(value)


def normalized_time(candidate, ctx):
    try:
        return _normalized_time(candidate, ctx)
    except (ValueError, OverflowError):
        return TimeValue(raw=candidate.time.raw)


def _normalized_time(candidate, ctx):
    """raw 不变。仅来源字段用系统时区；正文锚点必须单独引用。"""
    from ..extract.baseline import time_phrase, ZONE_RE
    spans = {s.id: s for s in ctx.evidence}
    relation = candidate.relation
    source = [spans[r] for r in candidate.evidence_refs if r in spans]
    raw = candidate.time.raw
    field_backed = any(s.locator.type == "field" and match_quote(raw, s.text).status != "mismatch"
                       for s in source)
    offset = ctx.bundle.manifest.default_timezone if field_backed else None
    value = time_phrase(raw, offset)
    if not relation:
        return value
    # 引文的真实性由 validate_extraction 独立核验，不能取记录发送时间。
    if relation.date_anchor:
        from ..extract.baseline import DATE
        anchor_dates = set(re.findall(DATE, relation.date_anchor.quote))
        if len(anchor_dates) > 1:
            return TimeValue(raw=raw)
        anchor = time_phrase(relation.date_anchor.quote, None)
        date = anchor.iso[:10] if anchor.iso else None
        if date and value.iso and value.iso[:10] != date:
            return TimeValue(raw=raw)
        if date and value.iso is None and re.fullmatch(
            r"\s*\d{1,2}[:：]\d{2}(?:[:：]\d{2})?\s*(?:(?:UTC|GMT|Z).*|[+-]\d{2}:?\d{2})?\s*", raw, re.I
        ):
            value = time_phrase(date + " " + raw, offset)
    if relation.timezone_anchor:
        zone = ZONE_RE.search(relation.timezone_anchor.quote)
        if zone:
            # 字段的口径不能被另一段正文的时区覆盖；矛盾的显式锚点留待核实。
            anchored = time_phrase("2000-01-01 00:00 " + zone.group(), None)
            if field_backed and value.utc_offset and anchored.utc_offset != value.utc_offset:
                return TimeValue(raw=raw)
            if value.tz_source == TimeZoneSource.EXPLICIT:
                if anchored.utc_offset != value.utc_offset:
                    return TimeValue(raw=raw)
                return value.model_copy(update={"raw": raw})
            base = (value.iso[:16] if value.precision == TimePrecision.MINUTE else value.iso[:19]) if value.iso and value.as_datetime() else raw
            value = time_phrase(base + " " + zone.group(), None)
    return value.model_copy(update={"raw": raw})


def _reliable(candidate, spans):
    relation = candidate.relation
    refs = set(candidate.evidence_refs)
    if relation:
        refs.update(q.evidence_id for q in relation.context)
    sources = [spans[r] for r in refs if r in spans]
    # 重复/引用来源可以追溯，但不增加独立佐证；此处不做数量投票。
    return any(not s.needs_review and s.role not in {SpanRole.SIGNATURE, SpanRole.DERIVED_SUMMARY}
               for s in sources)


def pending_reason(candidate, name, spans):
    r = candidate.relation
    if r is None:
        return "缺少完整结构化关系，保留候选待核实。"
    if not r.current_event or r.modality != "asserted":
        return "不是本次事件的明确断言，保留推测／否定范围。"
    if not _reliable(candidate, spans):
        return "缺少可靠原始依据。"
    # 必须有一段上下文同时包含该时间/断言；不能用无关原句拼出关系。
    text = candidate.statement if name == "cause" else candidate.time.raw
    if not any(match_quote(text, q.quote).status != "mismatch" for q in r.context):
        return "关系上下文没有包含候选原文，关系待核实。"
    if name == "cause":
        if r.assertion not in {"fault", "mechanism", "planned_work"} or not r.affects_service or not r.occurred:
            return "不是已发生并影响本次业务的故障／机制／作业断言。"
        if candidate.cause_kind not in {"root_cause_confirmed", "root_cause_claimed", "planned_work"}:
            return "该原因类别只能保留为候选。"
        if (r.assertion == "planned_work") != (candidate.cause_kind == "planned_work"):
            return "作业关系与原因类别不一致。"
    else:
        if candidate.time_kind not in (END if name == "end_time" else START):
            return "协议状态、确认动作、流程或其他时间不能替代业务起止。"
        if not candidate.time.as_datetime() or candidate.time.precision not in {TimePrecision.MINUTE, TimePrecision.SECOND}:
            return "日期／时区锚点不一致或缺少分钟级以上完整时间，不能正式采用。"
        if candidate.time.tz_source == TimeZoneSource.UNKNOWN:
            return "时区未知，不能正式采用。"
    return None


def _interval(candidate):
    dt = candidate.time.as_datetime()
    return dt, dt + timedelta(seconds=60 if candidate.time.precision == TimePrecision.MINUTE else 1)


def _purpose(c):
    return "alarm" if c.time_kind == TimeKind.ALARM_RAISED else "business"


def _clear(el, *, conflict=False):
    return el.model_copy(update=dict(status=ElementStatus.CONFLICTED if conflict else ElementStatus.UNKNOWN,
                                    value=None, selected=None, evidence_refs=[]))


def apply_constraints(ctx, data):
    if data.semantic_assessment is None:
        return data  # 已保存的旧回放和规则提供方不自动升级
    spans = {s.id: s for s in ctx.evidence}
    checks, updates = [], {}
    recovery_selection = data.semantic_assessment.recovery_selection
    for name in NAMES:
        el = getattr(data.elements, name)
        original = data.semantic_assessment.original.get(name)
        raw_candidates = original.get("candidates") if isinstance(original, dict) else None
        if isinstance(raw_candidates, list) and len(raw_candidates) != len(el.candidates):
            checks.append(ConstraintCheck(element=name, outcome="pending",
                reason="部分候选缺少时间／断言／来源，原始格式保留在原始三栏。"))
        if isinstance(original, dict) and original.get("value") and el.selected is None:
            checks.append(ConstraintCheck(element=name, outcome="pending", reason="原始结论没有唯一有效的选中候选。"))
        candidates = [c.model_copy(update={"time": normalized_time(c, ctx)}) if name != "cause" else c
                      for c in el.candidates]
        el = el.model_copy(update={"candidates": candidates})
        eligible = []
        excluded = {}
        for c in candidates:
            reason = pending_reason(c, name, spans)
            checks.append(ConstraintCheck(element=name, candidate_id=c.id,
                outcome="pending" if reason else "eligible", reason=reason or "关系完整，来源与数值另经独立校验；不代表人工审核。",
                evidence_refs=c.evidence_refs))
            if reason is None:
                eligible.append(c)
            else:
                excluded[c.id] = reason
        if name == "end_time" and recovery_selection is not None:
            from .recovery_policy import select_recovery
            recovery_selection = select_recovery(candidates, eligible, original, spans,
                                                 recovery_selection.threshold_minutes, excluded)
            chosen = next((c for c in eligible if c.id == recovery_selection.selected), None)
            el = _clear(el, conflict=recovery_selection.outcome == "conflict")
            if chosen:
                confirmation = chosen.relation.customer_confirmation
                confirmation_span = spans.get(confirmation.evidence_id) if confirmation else None
                status = ElementStatus.DOCUMENTED
                if (confirmation_span and not confirmation_span.needs_review
                    and confirmation_span.role not in {SpanRole.QUOTED, SpanRole.SIGNATURE, SpanRole.DERIVED_SUMMARY}):
                    status = ElementStatus.CONFIRMED
                el = el.model_copy(update=dict(status=status, selected=chosen.id, value=chosen.time,
                                              evidence_refs=chosen.evidence_refs))
            checks.append(ConstraintCheck(element=name, candidate_id=recovery_selection.selected,
                outcome="eligible" if chosen else "conflict" if recovery_selection.outcome == "conflict" else "pending",
                code=IssueCode.TIME_CANDIDATES_DIFFER if recovery_selection.outcome == "conflict" else IssueCode.SEMANTIC_RELATION_INCOMPLETE,
                reason=recovery_selection.reason, evidence_refs=el.evidence_refs))
            updates[name] = el
            continue
        conflicts = []
        if name != "cause":
            for a, b in combinations(eligible, 2):
                if (a.relation.event_id, a.relation.scope, _purpose(a)) != (b.relation.event_id, b.relation.scope, _purpose(b)):
                    continue
                left, right = _interval(a), _interval(b)
                if max(left[0], right[0]) >= min(left[1], right[1]):
                    conflicts.extend([a, b])
        chosen = next((c for c in eligible if c.id == el.selected), None)
        if name == "cause" and chosen:
            opposing = [c for c in candidates if c.relation and c.id != chosen.id
                        and (c.relation.event_id, c.relation.scope) == (chosen.relation.event_id, chosen.relation.scope)
                        and (c.id in chosen.relation.contradicts or chosen.id in c.relation.contradicts)]
            if opposing:
                conflicts = [chosen, *opposing]
            known = {c.id for c in candidates}
            if any(ref not in known for ref in chosen.relation.contradicts):
                chosen = None
                checks.append(ConstraintCheck(element=name, outcome="pending", reason="矛盾关系指向不存在的候选。"))
        # 只有与选中项同组的冲突才阻止它；不靠事件编号相同自动合并不同用途。
        if conflicts and (chosen is None or any(c.id == chosen.id for c in conflicts)):
            el = _clear(el, conflict=True)
            checks.append(ConstraintCheck(element=name, outcome="conflict", code=IssueCode.SEMANTIC_ASSERTIONS_CONFLICT if name == "cause" else IssueCode.TIME_CANDIDATES_DIFFER, reason="同事件、范围和用途的断言不相容。",
                                          evidence_refs=list(dict.fromkeys(r for c in conflicts for r in c.evidence_refs))))
        elif el.status in {ElementStatus.DOCUMENTED, ElementStatus.CONFIRMED}:
            if chosen is None:
                el = _clear(el)
            else:
                status = ElementStatus.DOCUMENTED
                confirmation = getattr(chosen.relation, "customer_confirmation", None)
                confirmation_span = spans.get(confirmation.evidence_id) if confirmation else None
                if (name == "end_time" and confirmation_span and not confirmation_span.needs_review
                    and confirmation_span.role not in {SpanRole.QUOTED, SpanRole.SIGNATURE, SpanRole.DERIVED_SUMMARY}):
                    status = ElementStatus.CONFIRMED
                if name == "cause" and el.status == ElementStatus.CONFIRMED:
                    checks.append(ConstraintCheck(element=name, candidate_id=chosen.id, outcome="downgraded", code=IssueCode.SEMANTIC_STATUS_DOWNGRADED,
                        reason="自动原因结论最高为有记录，未经人工审核。", evidence_refs=chosen.evidence_refs))
                el = el.model_copy(update=dict(status=status,
                    value=chosen.statement if name == "cause" else chosen.time, evidence_refs=chosen.evidence_refs))
        updates[name] = el
    start, end = updates['start_time'], updates['end_time']
    if start.value and end.value:
        a = next(c for c in start.candidates if c.id == start.selected)
        b = next(c for c in end.candidates if c.id == end.selected)
        if (a.time_kind != TimeKind.ALARM_RAISED and
            (a.relation.event_id, a.relation.scope) == (b.relation.event_id, b.relation.scope) and
            _interval(b)[1] <= _interval(a)[0]):
            updates['end_time'] = _clear(end)
            if recovery_selection is not None:
                recovery_selection = recovery_selection.model_copy(update=dict(selected=None, outcome="pending",
                    reason="按来源规则选出的业务恢复早于业务起点，撤回正式值，不改选低优先来源。"))
            checks.append(ConstraintCheck(element="end_time", outcome="pending", code=IssueCode.TIME_ORDER_INVERTED, reason="业务恢复早于业务起点，禁止历时。",
                                          evidence_refs=a.evidence_refs+b.evidence_refs))
    assessment = data.semantic_assessment.model_copy(update={"checks": checks, "recovery_selection": recovery_selection})
    return data.model_copy(update={"elements": data.elements.model_copy(update=updates), "semantic_assessment": assessment})
