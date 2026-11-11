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
        for key in ("date_anchor", "timezone_anchor", "customer_confirmation", "recovery_source_basis", "correction_basis",
                    "responsibility_quote", "source_quote", "procurement_quote", "self_check", "vendor_contact",
                    "unicom_onsite", "service_recovered", "city_quote"):
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


# 只有时刻：可带 hrs、LT 这类无信息词和时区，如“13:05 LT, (GMT+7)”。
TIME_ONLY = re.compile(
    r"\s*\d{1,2}[:：]\d{2}(?:[:：]\d{2})?\s*(?:(?:hrs?|hours?|LT|local\s+time)\b[\s,，]*)?[(（]?\s*"
    r"(?:(?:UTC|GMT|Z).*|[+-]\d{2}:?\d{2})?\s*[)）]?\s*", re.I)


def system_record(span, ctx):
    """该证据所属的处理日志条目：日志条目本身，或“追单记录表单原文”这类与某条日志精确对应的文本材料。"""
    if span.locator.type == "log_entry":
        return ctx.bundle.process_log.entry(span.locator.seq)
    if span.locator.type == "text_range":
        material = next((m for m in ctx.bundle.manifest.materials if m.id == span.material_id), None)
        if material and material.origin and material.origin.log_seq:
            return ctx.bundle.process_log.entry(material.origin.log_seq)
    return None


# 日志里的口语写法：“7日早上8：30”“昨晚22点23分”“今天下午3点半”。
COLLOQUIAL = re.compile(
    r"\s*(?:(?P<rel>今天|今日|今早|今晨|今晚|昨天|昨日|昨晚|昨夜|前天)|(?:(?P<mo>\d{1,2})月)?(?P<day>\d{1,2})[日号])\s*"
    r"(?P<part>凌晨|早上|早晨|上午|中午|下午|傍晚|晚上|夜里|晚)?\s*"
    r"(?P<h>\d{1,2})(?:[:：点时](?P<m>\d{1,2})分?|(?P<half>点半)|[点时])\s*")
_REL_DAYS = {"今": 0, "昨": 1, "前": 2}


def colloquial_time(raw, recorded):
    """按日志记录时间把口语时间换成完整时间；算不出或晚于记录时间就返回 None。"""
    m = COLLOQUIAL.fullmatch(raw)
    if not m:
        return None
    hour, minute = int(m["h"]), 30 if m["half"] else int(m["m"] or 0)
    evening = (m["part"] in {"下午", "傍晚", "晚上", "夜里", "晚"}) or (m["rel"] or "").endswith(("晚", "夜"))
    if hour < 12 and (evening or (m["part"] == "中午" and hour < 11)):
        hour += 12
    if hour > 23 or minute > 59:
        return None
    if m["rel"]:
        day = recorded.date() - timedelta(days=_REL_DAYS[m["rel"][0]])
    else:
        # 只写了“几日”：取记录时间当天或之前最近的那一天，最多回看一个月。
        day = next((d for d in (recorded.date() - timedelta(days=n) for n in range(0, 32))
                    if d.day == int(m["day"]) and (not m["mo"] or d.month == int(m["mo"]))), None)
        if day is None:
            return None
    moment = recorded.replace(year=day.year, month=day.month, day=day.day, hour=hour, minute=minute,
                              second=0, microsecond=0)
    return moment if moment <= recorded else None


def date_inferred(candidate):
    """只有时刻、又没有原文日期锚点而取得完整时间的，日期是推定的；返回推定依据的说法，否则为空串。"""
    raw = candidate.time.raw
    if not (candidate.time.iso and candidate.relation
            and (COLLOQUIAL.fullmatch(raw) or (not candidate.relation.date_anchor and TIME_ONLY.fullmatch(raw)))):
        return ""
    return "日志记录时间" if any("/log:" in ref for ref in candidate.evidence_refs) else "工单恢复时间"


def _ticket_recovery(ctx):
    """工单系统的恢复时间字段，只用来给缺日期的时刻定日期。"""
    from ..extract.baseline import time_phrase
    for span in ctx.evidence:
        if span.locator.type == "field" and span.id.endswith("/f:recovered_at"):
            value = time_phrase(span.text, ctx.bundle.manifest.default_timezone)
            if value.as_datetime() and value.as_datetime().tzinfo:
                return value.as_datetime()
    return None


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
    # 处理日志由工单系统记录，正文里没写时区的时刻按系统时区假设并在报告中标注；邮件、RFO 正文不假设。
    records = [entry for s in source if match_quote(raw, s.text).status != "mismatch"
               for entry in [system_record(s, ctx)] if entry]
    log_backed = bool(records)
    offset = ctx.bundle.manifest.default_timezone if field_backed or log_backed else None
    value = time_phrase(raw, offset)
    if not relation:
        return value
    if value.iso is None and not relation.date_anchor and TIME_ONLY.fullmatch(raw):
        # 日志里只写了时刻：取该条日志记录时间之前最近的那个时刻，报告注明日期为推定。
        for entry in records:
            recorded = time_phrase(entry.recorded_at, offset) if entry.recorded_at else None
            if recorded and recorded.as_datetime():
                guess = time_phrase(recorded.iso[:10] + " " + raw, offset)
                if guess.as_datetime() and guess.as_datetime() > recorded.as_datetime():
                    guess = time_phrase((recorded.as_datetime() - timedelta(days=1)).date().isoformat() + " " + raw, offset)
                if guess.as_datetime():
                    value = guess
                    break
    # 口语写法即使模型另给了日期锚点也先按记录时间推；与锚点日期不符时由下面的锚点核对撤回。
    if value.iso is None and COLLOQUIAL.fullmatch(raw):
        for entry in records:
            recorded = time_phrase(entry.recorded_at, offset) if entry.recorded_at else None
            moment = colloquial_time(raw, recorded.as_datetime()) if recorded and recorded.as_datetime() else None
            if moment:
                value = time_phrase(moment.strftime("%Y-%m-%d %H:%M"), offset)
                break
    if (value.iso is None and not relation.date_anchor and not records and TIME_ONLY.fullmatch(raw)
            and candidate.time_kind == "business_recovery"):
        # 邮件、RFO 里写了时区但没写日期的恢复时刻：取工单恢复时间之前最近的那个时刻，报告注明日期为推定。
        # 没写时区的不推定。
        limit = _ticket_recovery(ctx)
        if limit:
            for back in (0, 1):
                guess = time_phrase((limit.date() - timedelta(days=back)).isoformat() + " " + raw, None)
                moment = guess.as_datetime()
                if not moment or guess.tz_source != TimeZoneSource.EXPLICIT:
                    break
                if moment <= limit:
                    value = guess
                    break
    # 邮件、RFO 正文里的时刻不取发送时间；须有原文日期锚点。
    if relation.date_anchor:
        from ..extract.baseline import DATE
        anchor_dates = set(re.findall(DATE, relation.date_anchor.quote))
        if len(anchor_dates) > 1:
            return TimeValue(raw=raw)
        anchor = time_phrase(relation.date_anchor.quote, None)
        date = anchor.iso[:10] if anchor.iso else None
        if date and value.iso and value.iso[:10] != date:
            return TimeValue(raw=raw)
        if date and value.iso is None and TIME_ONLY.fullmatch(raw):
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
        if data.semantic_assessment.adjudication == "local_priority":
            # 候选顺序即本地优先级（系统字段／来源层级在前）；不同口径的起障时间不算冲突。
            chosen = eligible[0] if eligible else None
            if name == "start_time" and chosen and chosen.time_kind == TimeKind.FAULT_START_FIELD:
                # 系统发生时间常是建单时刻；客户明确给出更早的起始时刻时采用客户的，系统字段留作参照。
                earlier = [c for c in eligible if c.time_kind == TimeKind.CUSTOMER_REPORTED_START
                           and _interval(c)[0] < _interval(chosen)[0]]
                if earlier:
                    chosen = min(earlier, key=lambda c: _interval(c)[0])
                    checks.append(ConstraintCheck(element=name, candidate_id=chosen.id, outcome="eligible",
                        reason="客户报告的起始时刻早于工单系统发生时间，采用客户报告时刻。", evidence_refs=chosen.evidence_refs))
            el = _clear(el)
            if chosen:
                el = el.model_copy(update=dict(status=ElementStatus.DOCUMENTED, selected=chosen.id,
                    value=chosen.statement if name == "cause" else chosen.time, evidence_refs=chosen.evidence_refs))
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
