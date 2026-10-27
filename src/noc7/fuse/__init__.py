"""证据去重：保留所有来源，引用和摘要永不增加独立佐证。"""

import re

from ..schema.evidence import EvidenceSpan, SpanRole


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).casefold()


def link_duplicates(spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    originals = [
        s
        for s in spans
        if s.role not in (SpanRole.DERIVED_SUMMARY, SpanRole.QUOTED, SpanRole.SIGNATURE)
    ]
    seen: dict[str, str] = {}
    out = []
    known = {s.id for s in spans}
    for s in spans:
        key = normalize(s.text)
        refs = [r for r in s.derived_from if r in known and r != s.id]
        if key in seen:
            refs.append(seen[key])
        elif s.role in (SpanRole.DERIVED_SUMMARY, SpanRole.QUOTED):
            refs.extend(o.id for o in originals if normalize(o.text) == key)
        if s.role not in (
            SpanRole.DERIVED_SUMMARY,
            SpanRole.QUOTED,
            SpanRole.SIGNATURE,
        ):
            seen.setdefault(key, s.id)
        out.append(s.model_copy(update={"derived_from": list(dict.fromkeys(refs))}))
    return out


def independent_evidence(spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    return [
        s
        for s in spans
        if s.role not in (SpanRole.DERIVED_SUMMARY, SpanRole.QUOTED, SpanRole.SIGNATURE)
        and not s.derived_from
    ]
