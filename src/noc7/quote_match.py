"""只统一空白和 HTML 字符实体（&#39;、&gt; 等，邮件原文常带）的引用匹配；位置始终指向未改写的原文。"""
from __future__ import annotations

import html
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


_TOKEN = re.compile(r"&(?:#\d{1,7}|#[xX][0-9a-fA-F]{1,6}|[a-zA-Z]{2,8});|\s+|\S")


def _fold(text):
    """连续空白折成一个空格，能解成单个字符的 HTML 实体折成那个字符；positions 记每个折后字符在原文里的范围。"""
    chars, positions = [], []
    for token in _TOKEN.finditer(text):
        char = token[0]
        if len(char) > 1 and char[0] == "&":
            decoded = html.unescape(char)
            char = decoded if len(decoded) == 1 else None
        if char is None:  # 解不出单个字符的实体按原样逐字符比较
            for i, c in enumerate(token[0]):
                chars.append(c)
                positions.append((token.start() + i, token.start() + i + 1))
            continue
        chars.append(" " if char.isspace() else char)
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
