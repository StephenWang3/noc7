"""模型业务判断的原始副本，只用于待确认区，不属于正式七要素。"""
from __future__ import annotations

from typing import Literal
from pydantic import Field, JsonValue, model_validator

from .common import Model
from ..quote_match import QuoteCheck


def source_refs(node):
    if not isinstance(node, dict):
        return []
    refs = node.get("evidence_refs")
    if isinstance(refs, str):
        return [refs] if refs else []
    return [ref for ref in refs if isinstance(ref, str) and ref] if isinstance(refs, list) else []


class BusinessSuggestion(Model):
    element: Literal["responsible_party", "location"]
    original: JsonValue
    quotes: list[dict[str, str]] = Field(default_factory=list)
    checks: list[QuoteCheck] = Field(default_factory=list)

    @model_validator(mode="after")
    def _original_shape(self):
        def check(node):
            if isinstance(node, dict):
                if any(k in node and (k != "review" or node[k] is not None)
                       for k in ("review", "checks", "quote_checks", "suggestions")):
                    raise ValueError("建议原始答案不能包含审核或本地核验记录")
                for v in node.values():
                    check(v)
            elif isinstance(node, list):
                for v in node:
                    check(v)
        check(self.original)
        if any(set(q) != {"evidence_id", "quote"} for q in self.quotes):
            raise ValueError("建议显式引文必须包含来源和引文")
        return self

    @property
    def node(self):
        return self.original if isinstance(self.original, dict) else {}

    @property
    def candidates(self):
        candidates = self.node.get("candidates")
        return candidates if isinstance(candidates, list) else []

    def iter_evidence_refs(self):
        yield from source_refs(self.original)
        for candidate in self.candidates:
            if isinstance(candidate, dict):
                yield from source_refs(candidate)
        for quote in self.quotes:
            yield quote["evidence_id"]

    def quote_requests(self):
        key = "party" if self.element == "responsible_party" else "description"
        for i, candidate in enumerate(self.candidates):
            if isinstance(candidate, dict):
                text = candidate.get(key)
                for ref in source_refs(candidate):
                    yield f"candidates/{i}", ref, text if isinstance(text, str) else ""
        value = self.node.get("value")
        if isinstance(value, str) and value:
            for ref in source_refs(self.original):
                yield "value", ref, value
        for i, quote in enumerate(self.quotes):
            yield f"quotes/{i}", quote["evidence_id"], quote["quote"]
