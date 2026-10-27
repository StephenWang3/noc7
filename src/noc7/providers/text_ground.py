"""把模型摘录收成规则基线能支持的结论。

模型只提供带引用的原文。定责、故障点、原因类别、时间语义和能否确认，
都按 baseline 对引用片段重算；对不上的结论改为 unknown。
现象的 value 与 evidence_refs 在本地写入。旁白和身份文本必须是引用原文的子串。
"""

from __future__ import annotations

import re

from ..extract.baseline import (
    _time_kind,
    cause_kind,
    conclusion_observations,
    confirms_recovery,
    location_role,
    responsibility_basis,
    step_kind,
    time_phrase,
    usable_text,
)
from ..extract.types import Extraction, ExtractionContext
from ..schema import (
    ATTRIBUTION_LABELS_ZH,
    CAUSE_KINDS_ALLOWED_AS_VALUE,
    CauseKind,
    ElementStatus,
    IdentityStatus,
    LocationRole,
    ResponsibilityBasis,
    SpanRole,
    StepKind,
    TimeKind,
)
from ..schema.timeval import TimeValue

# 与 RulesProvider 的字段时间和流程动作一致。
_FIELD_TIME = {
    "occurred_at": TimeKind.FAULT_START_FIELD,
    "recovered_at": TimeKind.RECOVERY_FIELD,
    "alarm_time": TimeKind.ALARM_RAISED,
    "warning_time": TimeKind.WARNING_RAISED,
    "created_at": TimeKind.TICKET_CREATED,
    "alarm_cleared_at": TimeKind.ALARM_CLEARED,
}
_WORKFLOW_TIME = {
    "建单": TimeKind.TICKET_CREATED,
    "创建工单": TimeKind.TICKET_CREATED,
    "返单": TimeKind.TICKET_RETURNED,
    "结单": TimeKind.TICKET_CLOSED,
    "撤销": TimeKind.TICKET_CANCELLED,
}
_START_CONCLUSION = {
    TimeKind.FAULT_START_FIELD,
    TimeKind.CUSTOMER_REPORTED_START,
    TimeKind.ALARM_RAISED,
}
_END_CONCLUSION = {TimeKind.RECOVERY_FIELD, TimeKind.CUSTOMER_CONFIRMED_RECOVERY}
_CONCLUSIVE = {ElementStatus.DOCUMENTED, ElementStatus.CONFIRMED}


def normalize_model_payload(payload, offset: str | None):
    """时间只保留原文。iso、精度和时区在本地填写，避免结构校验拒绝合格摘录。"""

    def walk(node, parent_key=None):
        if isinstance(node, list):
            return [walk(item, parent_key) for item in node]
        if not isinstance(node, dict):
            return node
        if _is_time(node):
            raw = node.get("raw")
            if not isinstance(raw, str):
                return {key: walk(value, parent_key) for key, value in node.items()}
            try:
                filled = time_phrase(raw, offset)
            except ValueError:
                filled = TimeValue(raw=raw)
            return filled.model_dump(mode="json")
        copied = {key: walk(value, key) for key, value in node.items()}
        if (
            parent_key == "candidates"
            and "time" in copied
            and "evidence_refs" in copied
            and "time_kind" not in copied
            and "event_kind" not in copied
            and "step_kind" not in copied
        ):
            copied["time_kind"] = TimeKind.OTHER.value
        return copied

    return walk(payload)


def ground_extraction(ctx: ExtractionContext, data: Extraction) -> Extraction:
    spans = {span.id: span for span in ctx.evidence}
    elements = data.elements
    elements = elements.model_copy(update={
        "start_time": _ground_time(elements.start_time, spans, ctx, end=False),
        "end_time": _ground_time(elements.end_time, spans, ctx, end=True),
        "responsible_party": _ground_party(elements.responsible_party, spans),
        "cause": _ground_cause(elements.cause, spans),
        "location": _ground_location(elements.location, spans),
        "phenomenon": _ground_phenomenon(elements.phenomenon, ctx),
        "handling_process": _ground_steps(elements.handling_process, spans),
    })
    return data.model_copy(update={
        "elements": elements,
        "events": [_ground_event(event, spans) for event in data.events],
        "service_identity": _ground_identity(data.service_identity, spans),
    })


def _is_time(node: dict) -> bool:
    return "raw" in node and not any(
        key in node for key in ("status", "candidates", "elements", "id", "evidence_refs", "action")
    )


def _support(refs, spans):
    return [spans[ref] for ref in refs if ref in spans]


def _blob(refs, spans) -> str:
    return "\n".join(span.text for span in _support(refs, spans))


def _note(note, blob: str):
    if note and note in blob:
        return note
    return None


def _field_key(span) -> str:
    return getattr(span.locator, "field_key", "") or ""


def _trusted(span) -> bool:
    return span.role != SpanRole.QUOTED


def _clause(text: str, excerpt: str) -> str:
    index = text.find(excerpt)
    if index < 0:
        return excerpt
    left = 0
    for boundary in re.finditer(r"[。；;!?！？\n]", text):
        if boundary.end() <= index:
            left = boundary.end()
        elif boundary.start() >= index + len(excerpt):
            return text[left:boundary.start()]
    return text[left:]


def _excerpt_in(text: str, spans) -> bool:
    return bool(text) and any(text in span.text or text == usable_text(span) for span in spans)


def _clear(element, candidates, note):
    return element.model_copy(update={
        "status": ElementStatus.UNKNOWN,
        "value": None,
        "selected": None,
        "candidates": candidates,
        "evidence_refs": [],
        "note": note,
    })


def _party_basis(excerpt: str, spans):
    found = []
    for span in spans:
        if excerpt not in span.text and excerpt != usable_text(span):
            continue
        found.append(responsibility_basis(
            _clause(span.text, excerpt), _field_key(span), trusted=_trusted(span)
        ))
    found = [item for item in found if item is not None]
    if len(set(found)) == 1:
        return found[0]
    return None


def _ground_party(element, spans):
    revised = []
    for candidate in element.candidates:
        support = _support(candidate.evidence_refs, spans)
        blob = _blob(candidate.evidence_refs, spans)
        if not _excerpt_in(candidate.party, support):
            revised.append(candidate.model_copy(update={"note": _note(candidate.note, blob)}))
            continue
        basis = _party_basis(candidate.party, support) or ResponsibilityBasis.INFERRED_FROM_ROLE
        revised.append(candidate.model_copy(update={
            "basis": basis, "note": _note(candidate.note, blob)
        }))
    note = _note(element.note, _blob(_all_refs(element), spans))
    chosen = next((item for item in revised if item.id == element.selected), None)

    def supported(candidate, status):
        if candidate.basis is ResponsibilityBasis.FORMAL_DETERMINATION:
            return status in _CONCLUSIVE
        if candidate.basis is ResponsibilityBasis.CLAIMED:
            return status is ElementStatus.DOCUMENTED
        return False

    if element.status in _CONCLUSIVE and (chosen is None or not supported(chosen, element.status)):
        return _clear(element, revised, note)
    if element.status is ElementStatus.CONFLICTED and len(revised) < 2:
        return _clear(element, revised, note)
    return element.model_copy(update={"candidates": revised, "note": note})


def _location_of(excerpt: str, spans):
    found = []
    for span in spans:
        if excerpt not in span.text and excerpt != usable_text(span):
            continue
        found.append(location_role(
            _clause(span.text, excerpt), _field_key(span), trusted=_trusted(span)
        ))
    found = [item for item in found if item is not None]
    if len(set(found)) == 1:
        return found[0]
    return None


def _ground_location(element, spans):
    revised = []
    for candidate in element.candidates:
        support = _support(candidate.evidence_refs, spans)
        blob = _blob(candidate.evidence_refs, spans)
        if not _excerpt_in(candidate.description, support):
            revised.append(candidate.model_copy(update={"note": _note(candidate.note, blob)}))
            continue
        role = _location_of(candidate.description, support)
        if role is None:
            continue
        revised.append(candidate.model_copy(update={
            "role": role, "note": _note(candidate.note, blob)
        }))
    note = _note(element.note, _blob(_all_refs(element), spans))
    chosen = next((item for item in revised if item.id == element.selected), None)
    supported = (
        chosen is not None
        and chosen.role is LocationRole.LOCATED_FAULT_POINT
        and element.status is ElementStatus.DOCUMENTED
    )
    if element.status in _CONCLUSIVE and not supported:
        return _clear(element, revised, note)
    if element.status is ElementStatus.CONFLICTED and len(revised) < 2:
        return _clear(element, revised, note)
    return element.model_copy(update={"candidates": revised, "note": note})


def _cause_of(excerpt: str, spans):
    found = []
    for span in spans:
        if excerpt not in span.text and excerpt != usable_text(span):
            continue
        found.append(cause_kind(excerpt, _field_key(span)))
    found = [item for item in found if item is not None]
    if len(set(found)) == 1:
        return found[0]
    return None


def _ground_cause(element, spans):
    revised = []
    for candidate in element.candidates:
        support = _support(candidate.evidence_refs, spans)
        blob = _blob(candidate.evidence_refs, spans)
        if not _excerpt_in(candidate.statement, support):
            revised.append(candidate.model_copy(update={"note": _note(candidate.note, blob)}))
            continue
        kind = _cause_of(candidate.statement, support)
        if kind is None:
            continue
        revised.append(candidate.model_copy(update={
            "cause_kind": kind, "note": _note(candidate.note, blob)
        }))
    note = _note(element.note, _blob(_all_refs(element), spans))
    chosen = next((item for item in revised if item.id == element.selected), None)

    def supported(candidate, status):
        if candidate.cause_kind not in CAUSE_KINDS_ALLOWED_AS_VALUE:
            return False
        if status is ElementStatus.CONFIRMED:
            return candidate.cause_kind is CauseKind.ROOT_CAUSE_CONFIRMED
        return status is ElementStatus.DOCUMENTED

    if element.status in _CONCLUSIVE and (chosen is None or not supported(chosen, element.status)):
        return _clear(element, revised, note)
    if element.status is ElementStatus.CONFLICTED and len(revised) < 2:
        return _clear(element, revised, note)
    return element.model_copy(update={"candidates": revised, "note": note})


def _time_of(raw: str, spans, ctx: ExtractionContext):
    found = []
    for span in spans:
        key = _field_key(span)
        if key in _FIELD_TIME and raw in span.text:
            found.append(_FIELD_TIME[key])
            continue
        if getattr(span.locator, "type", "") == "log_entry":
            entry = ctx.bundle.process_log.entry(span.locator.seq)
            if entry and entry.recorded_at and raw == entry.recorded_at.strip():
                if "同意结单" in span.text:
                    found.append(TimeKind.TICKET_CLOSED)
                elif entry.action in _WORKFLOW_TIME:
                    found.append(_WORKFLOW_TIME[entry.action])
                continue
        if raw in span.text:
            start = span.text.find(raw)
            planned = step_kind(span.text) is StepKind.PLANNED
            found.append(_time_kind(span.text, start, start + len(raw), planned))
            continue
        reading = span.reading
        if reading and reading.type == "chart":
            if any(series.first_nonzero and raw in series.first_nonzero for series in reading.series):
                found.append(TimeKind.CHART_FIRST_NONZERO)
    if len(set(found)) == 1:
        return found[0]
    return None


def _time_grounded(raw: str, spans, ctx: ExtractionContext) -> bool:
    if not raw:
        return False
    for span in spans:
        if raw in span.text:
            return True
        reading = span.reading
        if reading and reading.type == "chart" and any(
            series.first_nonzero and raw in series.first_nonzero for series in reading.series
        ):
            return True
        if getattr(span.locator, "type", "") == "log_entry":
            entry = ctx.bundle.process_log.entry(span.locator.seq)
            if entry and entry.recorded_at and raw in entry.recorded_at:
                return True
    return False


def _ground_time(element, spans, ctx: ExtractionContext, *, end: bool):
    revised = []
    for candidate in element.candidates:
        support = _support(candidate.evidence_refs, spans)
        blob = _blob(candidate.evidence_refs, spans)
        raw = candidate.time.raw
        if not _time_grounded(raw, support, ctx):
            revised.append(candidate.model_copy(update={"note": _note(candidate.note, blob)}))
            continue
        kind = _time_of(raw, support, ctx) or TimeKind.OTHER
        revised.append(candidate.model_copy(update={
            "time_kind": kind, "note": _note(candidate.note, blob)
        }))
    note = _note(element.note, _blob(_all_refs(element), spans))
    chosen = next((item for item in revised if item.id == element.selected), None)
    allowed = _END_CONCLUSION if end else _START_CONCLUSION

    def supported(candidate, status):
        if candidate.time_kind not in allowed:
            return False
        if status is ElementStatus.CONFIRMED:
            if not end:
                return False
            support = _support(candidate.evidence_refs, spans)
            return any(
                confirms_recovery(usable_text(span)) and span.role != SpanRole.QUOTED
                for span in support
            )
        return status is ElementStatus.DOCUMENTED

    if element.status in _CONCLUSIVE and (chosen is None or not supported(chosen, element.status)):
        return _clear(element, revised, note)
    if element.status is ElementStatus.CONFLICTED and len(revised) < 2:
        return _clear(element, revised, note)
    return element.model_copy(update={"candidates": revised, "note": note})


def _ground_phenomenon(element, ctx: ExtractionContext):
    selected = conclusion_observations(element.candidates, ctx.evidence)
    note = _note(element.note, _blob(_all_refs(element), {span.id: span for span in ctx.evidence}))
    if not selected:
        return element.model_copy(update={
            "status": ElementStatus.UNKNOWN,
            "value": None,
            "evidence_refs": [],
            "note": note,
        })
    refs = list(dict.fromkeys(ref for observation in selected for ref in observation.evidence_refs))
    value = "；".join(
        f"{ATTRIBUTION_LABELS_ZH[item.attribution]}：{item.description}" for item in selected
    )
    return element.model_copy(update={
        "status": ElementStatus.DOCUMENTED,
        "value": value,
        "evidence_refs": refs,
        "note": note,
    })


def _narrative(item, spans):
    blob = _blob(item.evidence_refs, spans)
    update = {"note": _note(getattr(item, "note", None), blob)}
    for field in ("actor", "result", "target"):
        value = getattr(item, field, None)
        update[field] = value if value and value in blob else None
    return item.model_copy(update=update)


def _ground_steps(element, spans):
    steps = [_narrative(step, spans) for step in element.value]
    note = _note(element.note, _blob(_all_refs(element), spans))
    return element.model_copy(update={"value": steps, "note": note})


def _ground_event(event, spans):
    blob = _blob(event.evidence_refs, spans)
    return event.model_copy(update={
        "actor": event.actor if event.actor and event.actor in blob else None,
        "result": event.result if event.result and event.result in blob else None,
        "target": event.target if event.target and event.target in blob else None,
    })


def _ground_identity(identity, spans):
    if identity is None:
        return None
    kept = []
    for identifier in identity.identifiers:
        blob = _blob(identifier.evidence_refs, spans)
        if not identifier.evidence_refs or identifier.value not in blob:
            continue
        kept.append(identifier.model_copy(update={"note": _note(identifier.note, blob)}))
    blob = "\n".join(_blob(item.evidence_refs, spans) for item in kept)
    note = _note(identity.note, blob)
    if not kept and note is None:
        return None
    status = identity.status
    if status is IdentityStatus.VERIFIED:
        status = IdentityStatus.UNVERIFIED
    return identity.model_copy(update={"status": status, "identifiers": kept, "note": note})


def _all_refs(element):
    refs = list(element.evidence_refs)
    for candidate in element.iter_candidates():
        refs.extend(candidate.evidence_refs)
    return refs
