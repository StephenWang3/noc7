"""恢复时间的业务裁决；语义由模型声明，本地只核对来源、分组与数值。"""
from __future__ import annotations

import os

from ..quote_match import match_quote
from ..schema import SpanRole
from ..schema.relations import RecoverySelection

SOURCE_LABELS = {
    "customer": "客户恢复时间", "vendor_rfo": "供应商 RFO",
    "unicom_monitor": "联通网管恢复时间",
}
PRIORITY = tuple(SOURCE_LABELS)
# 系统恢复字段不在业务优先级内；只在三类业务来源都没有合格记载时兜底，并在报告中标注。
FALLBACK = "system_field"
FALLBACK_LABEL = "系统恢复字段（兜底，待核实）"


def initial_selection():
    try:
        return RecoverySelection(threshold_minutes=float(os.environ.get("NOC7_RECOVERY_CLOSE_MINUTES", "30")))
    except (ValueError, TypeError, OverflowError):
        raise ValueError("NOC7_RECOVERY_CLOSE_MINUTES 必须为有限非负数。") from None


def group(candidate):
    r = candidate.relation
    return (r.event_id, r.scope, r.recovery_round)


def usable_quote(quote, spans):
    span = spans.get(quote.evidence_id) if quote else None
    return bool(span and not span.needs_review
                and span.role not in {SpanRole.SIGNATURE, SpanRole.DERIVED_SUMMARY}
                and match_quote(quote.quote, span.text).status != "mismatch")


def source_reason(candidate, spans):
    r = candidate.relation
    if r.recovery_source == FALLBACK:
        if candidate.time_kind != "recovery_field" or not any(
                ref in spans and spans[ref].locator.type == "field" for ref in candidate.evidence_refs):
            return "系统字段兜底只接受工单恢复时间字段。"
        return None
    if r.recovery_source not in PRIORITY:
        return "恢复来源未知，不使用系统字段兜底。"
    if not usable_quote(r.recovery_source_basis, spans):
        return "缺少可定位且可靠的恢复来源依据。"
    return None


def _model_group(original, candidates):
    """从原始模型选择确定组，避免复算时让策略选中项改变目标组。"""
    if not isinstance(original, dict) or not original.get("selected"):
        return None
    items = original.get("candidates")
    if not isinstance(items, list):
        return None
    selected = [c for c in items if isinstance(c, dict) and c.get("id") == original["selected"]]
    if len(selected) != 1:
        return None
    raw = selected[0].get("time")
    raw = raw.get("raw") if isinstance(raw, dict) else raw
    relation = selected[0].get("relation")
    if not isinstance(relation, dict):
        return None
    target = (relation.get("event_id"), relation.get("scope"), relation.get("recovery_round", "current"))
    # 原编号可能被规范化；用原串与关系确定组，不按生成编号碰巧命中。
    if any(c.relation and c.time.raw == raw and group(c) == target for c in candidates):
        return target
    return None


def select_recovery(candidates, eligible, original, spans, threshold_minutes, excluded=None):
    record = RecoverySelection(threshold_minutes=threshold_minutes,
                               excluded=dict(excluded or {}))
    for c in eligible:
        reason = source_reason(c, spans)
        if reason:
            record.excluded[c.id] = reason
    pool = [c for c in eligible if c.id not in record.excluded]
    fallback = [c for c in pool if c.relation.recovery_source == FALLBACK]
    pool = [c for c in pool if c.relation.recovery_source != FALLBACK]
    if pool:
        for c in fallback:
            record.excluded[c.id] = "已有客户／供应商 RFO／联通日志的恢复记载，系统字段只作参照。"
    elif fallback:
        chosen = min(fallback, key=lambda c: (c.time.as_datetime(), c.id))
        record.sources = {c.id: c.relation.recovery_source for c in candidates if c.relation}
        record.target_group = group(chosen)
        record.participating = sorted(c.id for c in fallback)
        record.span_seconds = 0.0
        record.selected, record.outcome = chosen.id, "selected"
        record.reason = "客户、供应商 RFO、联通日志均无合格恢复记载，取工单系统恢复时间字段兜底。"
        return record
    record.sources = {c.id: c.relation.recovery_source for c in candidates if c.relation}
    target = _model_group(original, candidates)
    groups = {group(c) for c in pool}
    if target is None and len(groups) == 1:
        target = next(iter(groups))
    record.target_group = target
    if target is None:
        record.reason = "没有合格恢复来源。" if not groups else "存在多个事件／范围／恢复轮次，无法唯一确定目标组。"
        return record
    for c in pool:
        if group(c) != target:
            record.excluded[c.id] = "不属于目标事件／范围／恢复轮次，不参与比较。"
    pool = [c for c in pool if group(c) == target]
    if not pool:
        record.reason = "目标组没有合格恢复来源。"
        return record
    by_id = {c.id: c for c in pool}
    # 新更正即使缺时区／完整时间，也不能使已声明被更正的旧值重新成为唯一答案。
    if any(c.id not in by_id and c.relation and group(c) == target and c.relation.supersedes
           for c in candidates):
        record.reason = "目标组存在尚不合格的更正候选，不能退回采用可能已失效的旧时间。"
        return record
    edges = {}
    for c in pool:
        r = c.relation
        if not r.supersedes:
            continue
        if (not usable_quote(r.correction_basis, spans)
            or any(ref not in by_id or ref == c.id
                   or by_id[ref].relation.recovery_source != r.recovery_source for ref in r.supersedes)):
            record.excluded[c.id] = "更正链接缺少可靠依据或编号／来源／分组不符，忽略该链接；时间候选仍参与跨度与来源优先裁决。"
            continue
        edges[c.id] = r.supersedes
    def cyclic(node, path):
        return node in path or any(cyclic(other, path | {node}) for other in edges.get(node, []))
    if any(cyclic(node, set()) for node in edges):
        record.outcome = "conflict"
        record.reason = "恢复时间更正关系循环，保留冲突。"
        return record
    superseded = {ref for refs in edges.values() for ref in refs}
    for ref in superseded:
        record.excluded[ref] = "有同来源、同组且带原文依据的明确更正，不参与取值。"
    pool = [c for c in pool if c.id not in superseded]
    record.participating = sorted(c.id for c in pool)
    moments = [c.time.as_datetime() for c in pool]
    record.span_seconds = (max(moments) - min(moments)).total_seconds()
    for source in PRIORITY:
        instants = [c.time.as_datetime() for c in pool if c.relation.recovery_source == source]
        if instants:
            spread = (max(instants) - min(instants)).total_seconds()
            record.source_spans_seconds[source] = spread
            if spread / 60 > threshold_minutes:
                record.source_conflicts.append(source)
    # 除以六十比较，避免非常大的有限分钟参数相乘溢出。
    if record.span_seconds / 60 <= threshold_minutes:
        chosen = min(pool, key=lambda c: (c.time.as_datetime(), c.id))
        record.reason = "全部合格恢复时间相差不大，采用最早时间。"
    else:
        source = next(s for s in PRIORITY if any(c.relation.recovery_source == s for c in pool))
        preferred = [c for c in pool if c.relation.recovery_source == source]
        moments = [c.time.as_datetime() for c in preferred]
        if (max(moments) - min(moments)).total_seconds() / 60 > threshold_minutes:
            record.outcome = "conflict"
            record.reason = "最高优先来源内部恢复时间超过阈值，保留冲突，不降级取其他来源。"
            return record
        chosen = min(preferred, key=lambda c: (c.time.as_datetime(), c.id))
        record.reason = "恢复时间跨度超过阈值，按客户→供应商 RFO→联通网管取最高优先来源的最早值。"
    record.selected = chosen.id
    record.outcome = "selected"
    for c in pool:
        if c.id != chosen.id:
            prior = record.excluded.get(c.id)
            reason = "已参与比较，按接近取早／来源优先规则未采用。"
            record.excluded[c.id] = f"{prior} {reason}" if prior else reason
    return record


def selection_text(record):
    if record.sources.get(record.selected) == FALLBACK:
        return f"恢复取值来源：{FALLBACK_LABEL}；{record.reason}"
    source = SOURCE_LABELS.get(record.sources.get(record.selected), "待核实")
    return (f"恢复取值来源：{source}；{record.reason}"
            f" 接近阈值 {record.threshold_minutes:g} 分钟（暂定，待业务方确认）。")
