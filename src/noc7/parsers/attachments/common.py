"""A2 共用的证据与问题构造；不依赖 A1。"""
from __future__ import annotations

import re

from ...schema.evidence import EvidenceSpan, ParseStatus, SpanRole
from ...schema.issues import DEFAULT_SEVERITY, IssueCode, ValidationIssue
from ..base import ParseContext, ParseOutput

QUALITY_THRESHOLD = 0.85
MAX_INPUT_BYTES = 50 * 1024 * 1024


def issue(code: IssueCode, message: str, refs: list[str] | None = None) -> ValidationIssue:
    return ValidationIssue(code=code, severity=DEFAULT_SEVERITY[code], message=message,
                           evidence_refs=refs or [])


def span(ctx: ParseContext, local_id: str, text: str, locator, extractor: str, **kwargs) -> EvidenceSpan:
    if ctx.material.derived:
        kwargs["role"] = SpanRole.DERIVED_SUMMARY
    return EvidenceSpan(id=f"{ctx.material.id}/{local_id}", material_id=ctx.material.id,
                        text=text, locator=locator, extractor=extractor, **kwargs)


def read_limited(ctx: ParseContext) -> bytes:
    if ctx.material.size_bytes > MAX_INPUT_BYTES:
        raise ValueError("附件超过 50 MiB 本地解析上限")
    data = ctx.read_bytes()
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError("附件超过 50 MiB 本地解析上限")
    return data


def finish(ctx: ParseContext, name: str, spans: list[EvidenceSpan], *, issues=None,
           review: bool = False, subtype=None, note=None) -> ParseOutput:
    issues = list(issues or [])
    # 检测只用于提醒；绝不执行、删除或照抄为要素结论。
    injection = re.compile(r"忽略.{0,16}(?:规则|指令|系统)|自动关闭工单|ignore.{0,40}(?:instructions?|rules?|system)|"
                           r"(?:system|assistant)\s*:", re.I | re.S)
    refs = [s.id for s in spans if injection.search(s.text)]
    if refs:
        issues.append(issue(IssueCode.EMBEDDED_INSTRUCTION, "材料包含面向系统/AI 的指令性文字，仅保留为数据", refs))
    review = review or not spans or any(s.needs_review for s in spans)
    if review and not any(i.code is IssueCode.MATERIAL_LOW_QUALITY for i in issues):
        issues.append(issue(IssueCode.MATERIAL_LOW_QUALITY, "材料有未识别区域或读数待复核，不应视为完整证据",
                            [s.id for s in spans if s.needs_review]))
    return ParseOutput(material_id=ctx.material.id, parser=name,
                       status=ParseStatus.NEEDS_REVIEW if review else ParseStatus.PARSED,
                       spans=spans, issues=issues, subtype=subtype, note=note)
