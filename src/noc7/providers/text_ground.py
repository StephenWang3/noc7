"""两栏建议独立保存；其他模型摘录收成规则基线能支持的结论。

模型责任方和地点在结构补全前保存为建议，正式字段置空。
其余要素按 baseline 对引用片段重算；对不上的结论改为 unknown。
现象的 value 与 evidence_refs 在本地写入。旁白和身份文本必须是引用原文的子串。
"""

from __future__ import annotations

import re

from ..extract.baseline import (
    _time_kind,
    attribution as span_attribution,
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
from ..extract.fact_phrases import responsibility_claims, rfo_fault_points
from ..schema import (
    ATTRIBUTION_LABELS_ZH,
    CAUSE_KINDS_ALLOWED_AS_VALUE,
    Attribution,
    CauseKind,
    ElementStatus,
    IdentityStatus,
    IssueCode,
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


_EVIDENCE_RE = re.compile(r"^M\d{2,}/[A-Za-z0-9:_.\-]+$")
_CANDIDATE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.\-]*$")
_EVENT_RE = re.compile(r"^EV[A-Za-z0-9_.\-]+$")
_GRANULARITY = {"country", "city", "site", "segment", "device", "port"}
_ID_ROLES = {"reported", "old", "new", "current", "other"}
_CONCLUSIVE_STATUS = {"documented", "confirmed"}
_QUOTE_ELEMENTS = {
    "responsible_party": "party",
    "cause": "statement",
    "location": "description",
}


def _one_of(value, enum_cls):
    try:
        return enum_cls(value).value
    except ValueError:
        return None


def _refs(value):
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and _EVIDENCE_RE.match(item)]


def _time_node(value):
    if isinstance(value, str) and value:
        return {"raw": value}
    if isinstance(value, dict) and isinstance(value.get("raw"), str) and value["raw"]:
        return {"raw": value["raw"]}
    return None


def _raw(value):
    node = _time_node(value)
    return node["raw"] if node else None


def _attribution(value, refs, spans):
    """归属只认所引片段上的规则，模型交来的合法枚举也覆盖。"""
    for ref in refs:
        span = spans.get(ref)
        if span is not None:
            return span_attribution(span, span.text).value
    parsed = _one_of(value, Attribution)
    return parsed or Attribution.UNKNOWN.value


def _number_ids(items, pattern, prefix):
    used = set()
    mapping = {}
    n = 1
    for item in items:
        old = item.get("id")
        if isinstance(old, str) and pattern.match(old) and old not in used:
            new = old
        else:
            while True:
                new = f"{prefix}{n}"
                n += 1
                if new not in used:
                    break
        used.add(new)
        if isinstance(old, str) and old not in mapping:
            mapping[old] = new
        item["id"] = new
    return mapping


def _selected(value, mapping, ids):
    if not isinstance(value, str):
        return None
    value = mapping.get(value, value)
    return value if value in ids else None


def _optional_text(value):
    return value if isinstance(value, str) else None


def _meta(node):
    meta = {}
    note = _optional_text(node.get("note"))
    if note is not None:
        meta["note"] = note
    if isinstance(node.get("review"), dict):
        meta["review"] = node["review"]
    issues = []
    if isinstance(node.get("issues"), list):
        for code in node["issues"]:
            parsed = _one_of(code, IssueCode)
            if parsed:
                issues.append(parsed)
    if issues:
        meta["issues"] = issues
    return meta


def _shell(item, spans, quote_key):
    if not isinstance(item, dict):
        return None
    text = item.get(quote_key)
    if not isinstance(text, str) or not text:
        return None
    refs = _refs(item.get("evidence_refs"))
    if not refs:
        return None
    out = {
        "id": item.get("id"),
        "evidence_refs": refs,
        "attribution": _attribution(item.get("attribution"), refs, spans),
        quote_key: text,
    }
    note = _optional_text(item.get("note"))
    if note is not None:
        out["note"] = note
    return out


def _step_label(value, action, refs, spans):
    """步骤和事件类别只认所引片段上的规则，模型交来的合法枚举也覆盖。"""
    text = action if isinstance(action, str) else ""
    for ref in refs:
        span = spans.get(ref)
        if span is not None and text and text in span.text:
            text = span.text
            break
    if text:
        return step_kind(text, action if isinstance(action, str) else "").value
    parsed = _one_of(value, StepKind)
    return parsed or StepKind.COMMUNICATION.value


def _cause_label(value, selected):
    parsed = _one_of(value, CauseKind)
    if selected:
        allowed = {kind.value for kind in CAUSE_KINDS_ALLOWED_AS_VALUE}
        return parsed if parsed in allowed else CauseKind.ROOT_CAUSE_CLAIMED.value
    return parsed or CauseKind.INVESTIGATION_FINDING.value


def _basis_label(value, selected):
    parsed = _one_of(value, ResponsibilityBasis)
    if selected:
        allowed = {
            ResponsibilityBasis.FORMAL_DETERMINATION.value,
            ResponsibilityBasis.CLAIMED.value,
        }
        return parsed if parsed in allowed else ResponsibilityBasis.CLAIMED.value
    return parsed or ResponsibilityBasis.INFERRED_FROM_ROLE.value


def _role_label(value, selected):
    parsed = _one_of(value, LocationRole)
    if selected:
        return LocationRole.LOCATED_FAULT_POINT.value
    return parsed or LocationRole.ALARM_LOCATION.value


def _finish_conclusion(node, candidates, value, quote_key):
    status = _one_of(node.get("status"), ElementStatus)
    selected = node.get("selected") if isinstance(node.get("selected"), str) else None
    ids = {item["id"] for item in candidates}
    if selected not in ids:
        selected = None
    refs = _refs(node.get("evidence_refs"))
    if status == ElementStatus.CONFLICTED.value:
        if len(candidates) < 2:
            return "unknown", None, None, refs
        # 非结论状态不保留 selected，避免重算后的类别和选中项互相打架。
        return status, None, None, refs
    attempted = status in _CONCLUSIVE_STATUS or (status is None and value is not None)
    if attempted:
        chosen = next(
            (item for item in candidates if item["id"] == selected and item.get(quote_key) == value),
            None,
        )
        if chosen is None:
            chosen = next((item for item in candidates if item.get(quote_key) == value), None)
        if chosen is None or not chosen["evidence_refs"]:
            return "unknown", None, None, refs
        if not refs:
            refs = list(chosen["evidence_refs"])
        kept = status if status in _CONCLUSIVE_STATUS else ElementStatus.DOCUMENTED.value
        return kept, value, chosen["id"], refs
    return ElementStatus.UNKNOWN.value, None, None, refs


def _repair_quote_element(node, spans, quote_key):
    if not isinstance(node, dict):
        node = {}
    candidates = []
    for item in node.get("candidates") or []:
        shell = _shell(item, spans, quote_key)
        if shell is None:
            continue
        if quote_key == "statement":
            shell["cause_kind"] = item.get("cause_kind")
        elif quote_key == "party":
            shell["basis"] = item.get("basis")
        else:
            shell["role"] = item.get("role")
            if item.get("granularity") in _GRANULARITY:
                shell["granularity"] = item["granularity"]
        candidates.append(shell)
    mapping = _number_ids(candidates, _CANDIDATE_RE, "C")
    patched = dict(node)
    patched["selected"] = _selected(node.get("selected"), mapping, {item["id"] for item in candidates})
    value = node.get("value") if isinstance(node.get("value"), str) and node.get("value") else None
    status, value, selected, refs = _finish_conclusion(patched, candidates, value, quote_key)
    for item in candidates:
        chosen = item["id"] == selected
        if quote_key == "statement":
            item["cause_kind"] = _cause_label(item.get("cause_kind"), chosen)
        elif quote_key == "party":
            item["basis"] = _basis_label(item.get("basis"), chosen)
        else:
            item["role"] = _role_label(item.get("role"), chosen)
    repaired = dict(status=status, value=value, selected=selected, evidence_refs=refs, candidates=candidates)
    repaired.update(_meta(node))
    return repaired


def _repair_time_element(node, spans):
    if not isinstance(node, dict):
        node = {}
    candidates = []
    for item in node.get("candidates") or []:
        if not isinstance(item, dict):
            continue
        raw = _time_node(item.get("time"))
        refs = _refs(item.get("evidence_refs"))
        if raw is None or not refs:
            continue
        candidate = {
            "id": item.get("id"),
            "evidence_refs": refs,
            "attribution": _attribution(item.get("attribution"), refs, spans),
            "time": raw,
            "time_kind": _one_of(item.get("time_kind"), TimeKind) or TimeKind.OTHER.value,
        }
        note = _optional_text(item.get("note"))
        if note is not None:
            candidate["note"] = note
        candidates.append(candidate)
    mapping = _number_ids(candidates, _CANDIDATE_RE, "C")
    value = _time_node(node.get("value"))
    comparable = [
        {**item, "raw": item["time"]["raw"]} for item in candidates
    ]
    patched = dict(node)
    patched["selected"] = _selected(node.get("selected"), mapping, {item["id"] for item in candidates})
    status, _, selected, refs = _finish_conclusion(
        patched, comparable, value["raw"] if value else None, "raw"
    )
    repaired = dict(
        status=status,
        value=value if status in _CONCLUSIVE_STATUS else None,
        selected=selected,
        evidence_refs=refs,
        candidates=candidates,
    )
    repaired.update(_meta(node))
    return repaired


def _repair_observations(node, spans):
    if not isinstance(node, dict):
        node = {}
    candidates = []
    for item in node.get("candidates") or []:
        shell = _shell(item, spans, "description")
        if shell is None:
            continue
        for key in ("metric", "value_text", "unit", "scope"):
            if isinstance(item.get(key), str):
                shell[key] = item[key]
        number = item.get("value")
        if isinstance(number, (int, float)) and not isinstance(number, bool):
            shell["value"] = number
        observed = _time_node(item.get("observed_at"))
        if observed:
            shell["observed_at"] = observed
        candidates.append(shell)
    _number_ids(candidates, _CANDIDATE_RE, "C")
    refs = _refs(node.get("evidence_refs"))
    status = _one_of(node.get("status"), ElementStatus)
    value = node.get("value") if isinstance(node.get("value"), str) and node.get("value") else None
    if status in _CONCLUSIVE_STATUS and value and (refs or candidates):
        if not refs:
            refs = list(dict.fromkeys(ref for item in candidates for ref in item["evidence_refs"]))
        kept = status
    else:
        kept, value = ElementStatus.UNKNOWN.value, None
    repaired = dict(status=kept, value=value, evidence_refs=refs, candidates=candidates)
    repaired.update(_meta(node))
    return repaired


def _repair_steps(node, spans):
    if not isinstance(node, dict):
        node = {}
    steps = []
    for item in node.get("value") or []:
        shell = _shell(item, spans, "action")
        if shell is None or not isinstance(item, dict):
            continue
        shell["step_kind"] = _step_label(item.get("step_kind"), shell["action"], shell["evidence_refs"], spans)
        for key in ("actor", "target", "result"):
            if isinstance(item.get(key), str):
                shell[key] = item[key]
        moment = _time_node(item.get("time"))
        if moment:
            shell["time"] = moment
        if isinstance(item.get("duplicate_of"), str):
            shell["duplicate_of"] = item["duplicate_of"]
        steps.append(shell)
    mapping = _number_ids(steps, _CANDIDATE_RE, "C")
    ids = {item["id"] for item in steps}
    for item in steps:
        dup = item.get("duplicate_of")
        if not isinstance(dup, str):
            continue
        dup = mapping.get(dup, dup)
        if dup in ids and dup != item["id"]:
            item["duplicate_of"] = dup
        else:
            item.pop("duplicate_of", None)
    refs = _refs(node.get("evidence_refs"))
    status = _one_of(node.get("status"), ElementStatus)
    # 步骤本身就是 value，conflicted 既要空 value 又要两个候选，结构上站不住。
    if steps:
        kept = (
            ElementStatus.CONFIRMED.value
            if status == ElementStatus.CONFIRMED.value
            else ElementStatus.DOCUMENTED.value
        )
        if not refs:
            refs = list(dict.fromkeys(ref for item in steps for ref in item["evidence_refs"]))
        value = steps
    else:
        kept, value, refs = ElementStatus.UNKNOWN.value, [], []
    repaired = dict(status=kept, value=value, evidence_refs=refs)
    repaired.update(_meta(node))
    return repaired


def _repair_events(items, spans):
    if not isinstance(items, list):
        return []
    events = []
    for item in items:
        shell = _shell(item, spans, "action")
        if shell is None or not isinstance(item, dict):
            continue
        shell["event_kind"] = _step_label(item.get("event_kind"), shell["action"], shell["evidence_refs"], spans)
        for key in ("actor", "target", "result", "scope"):
            if isinstance(item.get(key), str):
                shell[key] = item[key]
        moment = _time_node(item.get("time"))
        if moment:
            shell["time"] = moment
            shell["time_kind"] = _one_of(item.get("time_kind"), TimeKind) or TimeKind.OTHER.value
        if isinstance(item.get("duplicate_of"), str):
            shell["duplicate_of"] = item["duplicate_of"]
        events.append(shell)
    mapping = _number_ids(events, _EVENT_RE, "EV")
    ids = {item["id"] for item in events}
    for item in events:
        dup = item.get("duplicate_of")
        if not isinstance(dup, str):
            continue
        dup = mapping.get(dup, dup)
        if dup in ids and dup != item["id"]:
            item["duplicate_of"] = dup
        else:
            item.pop("duplicate_of", None)
    return events


def _repair_identity(node):
    if not isinstance(node, dict):
        return None
    identifiers = node.get("identifiers")
    if not isinstance(identifiers, list):
        if isinstance(node.get("value"), str) and node["value"]:
            identifiers = [node]
        else:
            identifiers = []
    repaired = []
    for item in identifiers:
        if not isinstance(item, dict) or not isinstance(item.get("value"), str) or not item["value"]:
            continue
        role = item.get("role") if item.get("role") in _ID_ROLES else "other"
        entry = {"value": item["value"], "role": role, "evidence_refs": _refs(item.get("evidence_refs"))}
        note = _optional_text(item.get("note"))
        if note is not None and item is not node:
            entry["note"] = note
        repaired.append(entry)
    status = _one_of(node.get("status"), IdentityStatus) or IdentityStatus.UNVERIFIED.value
    result = {"status": status, "identifiers": repaired}
    note = _optional_text(node.get("note"))
    if note is not None:
        result["note"] = note
    if not repaired and "note" not in result:
        return None
    return result


def _repair_quotes(items):
    if not isinstance(items, list):
        return []
    quotes = []
    for item in items:
        if not isinstance(item, dict):
            continue
        evidence_id = item.get("evidence_id")
        quote = item.get("quote")
        if isinstance(evidence_id, str) and _EVIDENCE_RE.match(evidence_id) and isinstance(quote, str) and quote:
            quotes.append({"evidence_id": evidence_id, "quote": quote})
    return quotes


def _repair_payload(payload, spans):
    elements = payload.get("elements")
    if not isinstance(elements, dict):
        return payload
    repaired = {}
    for name in ("start_time", "end_time"):
        repaired[name] = _repair_time_element(elements.get(name), spans)
    repaired["phenomenon"] = _repair_observations(elements.get("phenomenon"), spans)
    for name, quote_key in _QUOTE_ELEMENTS.items():
        repaired[name] = _repair_quote_element(elements.get(name), spans, quote_key)
    repaired["handling_process"] = _repair_steps(elements.get("handling_process"), spans)
    result = {
        "elements": repaired,
        "events": _repair_events(payload.get("events"), spans),
        "quotes": _repair_quotes(payload.get("quotes")),
    }
    if "service_identity" in payload:
        result["service_identity"] = _repair_identity(payload.get("service_identity"))
    return result


def normalize_model_payload(payload, offset: str | None, spans=None):
    """先补齐缺字段、收掉非法类别和多余字段，再把时间收成原文。

    缺编号、归属、步骤类别，以及写错的枚举、写成纯文字的时间，不再整单拒绝。
    两栏业务答案已由 separate_suggestions 隔离，其余语义类别由后续规则重算。
    """
    if isinstance(payload, dict):
        payload = _repair_payload(payload, {span.id: span for span in spans or ()})
    return _fill_times(payload, offset)


def _fill_times(node, offset, parent_key=None):
    if isinstance(node, list):
        return [_fill_times(item, offset, parent_key) for item in node]
    if not isinstance(node, dict):
        return node
    if _is_time(node):
        raw = node.get("raw")
        if not isinstance(raw, str):
            return {key: _fill_times(value, offset, parent_key) for key, value in node.items()}
        try:
            filled = time_phrase(raw, offset)
        except ValueError:
            filled = TimeValue(raw=raw)
        return filled.model_dump(mode="json")
    copied = {key: _fill_times(value, offset, key) for key, value in node.items()}
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


def ground_extraction(ctx: ExtractionContext, data: Extraction) -> Extraction:
    spans = {span.id: span for span in ctx.evidence}
    elements = data.elements
    elements = elements.model_copy(update={
        "start_time": _ground_time(elements.start_time, spans, ctx, end=False),
        "end_time": _ground_time(elements.end_time, spans, ctx, end=True),

        "cause": _ground_cause(elements.cause, spans),

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
        clause = _clause(span.text, excerpt)
        basis = responsibility_basis(clause, _field_key(span), trusted=_trusted(span))
        if basis == ResponsibilityBasis.CLAIMED and _field_key(span) != "responsible_party":
            if not any(excerpt in claim or claim in excerpt for claim in responsibility_claims(clause)):
                basis = None
        found.append(basis)
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
    # 模型可以只交候选；明确归因是否能成为记载由本地证据决定。
    if element.status == ElementStatus.UNKNOWN:
        explicit = [c for c in revised if c.basis == ResponsibilityBasis.CLAIMED
                    and _excerpt_in(c.party, _support(c.evidence_refs, spans))]
        if explicit:
            from ..extract.baseline import _text_element
            return _text_element(type(element), revised, "party",
                                 lambda c: c in explicit)
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
        points = rfo_fault_points(span.text)
        if points:
            # RFO 角色只赋给覆盖完整故障段的摘录，不能借整句转移给告警点。
            complete = any(point in excerpt for point in points)
            role = location_role(span.text, _field_key(span), trusted=_trusted(span))
            if complete and _trusted(span) and role == LocationRole.LOCATED_FAULT_POINT:
                found.append(role)
            else:
                own_role = location_role(excerpt, _field_key(span), trusted=False)
                found.append(own_role)
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
        description = candidate.description
        if role == LocationRole.LOCATED_FAULT_POINT:
            complete = [p for span in support for p in rfo_fault_points(span.text) if p in description]
            if len(set(complete)) == 1:
                description = complete[0]
        revised.append(candidate.model_copy(update={
            "description": description, "role": role, "note": _note(candidate.note, blob)
        }))
    note = _note(element.note, _blob(_all_refs(element), spans))
    if element.status == ElementStatus.UNKNOWN:
        explicit = [c for c in revised if c.role == LocationRole.LOCATED_FAULT_POINT
                    and _excerpt_in(c.description, _support(c.evidence_refs, spans))]
        if explicit:
            from ..extract.baseline import _text_element
            return _text_element(type(element), revised, "description", lambda c: c in explicit)
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
    return element.model_copy(update={"candidates": revised, "note": note,
                                      "value": chosen.description if supported else element.value})


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
    spans = {span.id: span for span in ctx.evidence}
    revised = [
        item.model_copy(update={
            "attribution": Attribution(_attribution(None, item.evidence_refs, spans))
        })
        for item in element.candidates
    ]
    selected = conclusion_observations(revised, ctx.evidence)
    note = _note(element.note, _blob(_all_refs(element), spans))
    if not selected:
        return element.model_copy(update={
            "status": ElementStatus.UNKNOWN,
            "value": None,
            "evidence_refs": [],
            "candidates": revised,
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
        "candidates": revised,
        "note": note,
    })


def _narrative(item, spans):
    blob = _blob(item.evidence_refs, spans)
    update = {
        "note": _note(getattr(item, "note", None), blob),
        "attribution": Attribution(_attribution(None, item.evidence_refs, spans)),
        "step_kind": StepKind(_step_label(None, item.action, item.evidence_refs, spans)),
    }
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
        "attribution": Attribution(_attribution(None, event.evidence_refs, spans)),
        "event_kind": StepKind(_step_label(None, event.action, event.evidence_refs, spans)),
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


def separate_suggestions(payload):
    """在结构补全前保存业务字段；不接受模型自报的本地核验或审核记录。"""
    from copy import deepcopy
    from ..schema import BusinessSuggestion
    from ..schema.suggestions import source_refs

    def reject_review(node):
        if isinstance(node, dict):
            if any(k in node and (k != "review" or node[k] is not None)
                   for k in ("review", "suggestions", "quote_checks", "checks")):
                from .text_config import TextProviderError
                raise TextProviderError("模型不能提交人工审核或本地核验记录，已拒绝。")
            for value in node.values():
                reject_review(value)
        elif isinstance(node, list):
            for value in node:
                reject_review(value)

    if not isinstance(payload, dict):
        raise ValueError("模型结果必须是对象")
    reject_review(payload)
    result = deepcopy(payload)
    elements = result.get("elements")
    if not isinstance(elements, dict):
        raise ValueError("缺少七要素")
    suggestions = []
    for name in ("responsible_party", "location"):
        node = elements.get(name, {})
        if not isinstance(node, dict):
            raise ValueError("建议必须是对象")
        candidates = node.get("candidates")
        candidates = [] if candidates is None else candidates
        if not isinstance(candidates, list) or any(not isinstance(c, dict) for c in candidates):
            raise ValueError("建议候选必须是对象列表")
        source_refs(node)
        for candidate in candidates:
            source_refs(candidate)
        suggestions.append(BusinessSuggestion(element=name, original=deepcopy(node)))
        elements[name] = dict(status="unknown", value=None, selected=None,
                              candidates=[], evidence_refs=[])
    # 顶层 quotes 没有要素归属；只有建议独占的来源可以移入建议核验。
    other_refs = set()
    def collect(node):
        if isinstance(node, dict):
            if "evidence_refs" in node:
                other_refs.update(source_refs(node))
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for v in node:
                collect(v)
    collect(elements)
    collect(result.get("events", []))
    collect(result.get("service_identity"))
    kept = []
    for quote in result.get("quotes") or []:
        if not isinstance(quote, dict) or not isinstance(quote.get("quote"), str) or not isinstance(quote.get("evidence_id"), str):
            raise ValueError("引文结构不合格")
        owners = [s for s in suggestions if quote["evidence_id"] in set(s.iter_evidence_refs())]
        if owners and quote["evidence_id"] not in other_refs:
            for owner in owners:
                owner.quotes.append(dict(quote=quote["quote"], evidence_id=quote["evidence_id"]))
        else:
            kept.append(quote)
    result["quotes"] = kept
    return result, suggestions
