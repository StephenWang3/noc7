"""仅统一空白的引用匹配；位置始终指向未改写的原文。"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from pydantic import BaseModel, ConfigDict


class QuoteCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    evidence_id: str
    quote: str
    status: Literal["strict", "whitespace", "mismatch"]
    start: int | None = Field(default=None, ge=0)
    end: int | None = Field(default=None, ge=0)
    original: str | None = None


def _fold(text):
    chars, positions = [], []
    for token in re.finditer(r"\s+|\S", text):
        chars.append(" " if token[0].isspace() else token[0])
        positions.append(token.span())
    return "".join(chars), positions


def match_quote(quote: str, source: str, *, path="", evidence_id="") -> QuoteCheck:
    base = dict(path=path, evidence_id=evidence_id, quote=quote)
    if not quote or not quote.strip():
        return QuoteCheck(**base, status="mismatch")
    start = source.find(quote)
    if start >= 0:
        return QuoteCheck(**base, status="strict", start=start, end=start + len(quote), original=quote)
    folded, positions = _fold(source)
    needle, _ = _fold(quote)
    start = folded.find(needle)
    if start < 0:
        return QuoteCheck(**base, status="mismatch")
    left, right = positions[start][0], positions[start + len(needle) - 1][1]
    return QuoteCheck(**base, status="whitespace", start=left, end=right, original=source[left:right])
