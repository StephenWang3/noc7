"""A1 文本解析器：字段、日志、邮件 HTML、纯文本。"""

import re

from ...schema.bundle import ProcessLog, TicketRecord
from ...schema.evidence import (
    EvidenceSpan,
    FieldLocator,
    LogEntryLocator,
    MaterialKind,
    ParseStatus,
    SpanRole,
    TextRangeLocator,
)
from ...schema.issues import DEFAULT_SEVERITY, IssueCode, ValidationIssue
from ..base import ParseContext, ParseOutput
from .email import email_spans

INSTRUCTION = re.compile(
    r"ignore (?:all )?(?:previous|prior) (?:rules|instructions)|SYSTEM NOTE TO AI|忽略.{0,12}(?:规则|指令)|发送.{0,10}(?:全部|完整)(?:工单|数据)",
    re.I,
)


class TextParser:
    def __init__(self, kind: MaterialKind):
        self.kinds = frozenset([kind])
        self.kind = kind
        self.name = f"a1.{kind.value}@1.0"

    def parse(self, ctx: ParseContext) -> ParseOutput:
        raw = ctx.read_bytes().decode("utf-8-sig")
        mid = ctx.material.id
        spans = []
        if self.kind is MaterialKind.TICKET_FIELDS:
            ticket = TicketRecord.model_validate_json(raw)
            spans = [
                EvidenceSpan(
                    id=f"{mid}/f:{f.key}",
                    material_id=mid,
                    locator=FieldLocator(field_key=f.key),
                    text=f.value,
                    extractor=self.name,
                )
                for f in ticket.fields
                if f.value is not None and f.value.strip()
            ]
        elif self.kind is MaterialKind.PROCESS_LOG:
            log = ProcessLog.model_validate_json(raw)
            spans = [
                EvidenceSpan(
                    id=f"{mid}/log:{e.seq}",
                    material_id=mid,
                    locator=LogEntryLocator(seq=e.seq),
                    text=e.content,
                    role=SpanRole.DERIVED_SUMMARY
                    if e.entry_kind == "ai_summary"
                    else SpanRole.ORIGINAL,
                    extractor=self.name,
                )
                for e in log.entries
                if e.content.strip()
            ]
        elif self.kind is MaterialKind.EMAIL_HTML:
            spans = email_spans(raw, mid, self.name)
        else:
            pos = 0
            for line, content in enumerate(raw.splitlines(keepends=True), 1):
                if content.strip():
                    text = content.rstrip("\r\n")
                    spans.append(
                        EvidenceSpan(
                            id=f"{mid}/t:{line}",
                            material_id=mid,
                            locator=TextRangeLocator(
                                line=line, char_start=pos, char_end=pos + len(text)
                            ),
                            text=text,
                            extractor=self.name,
                        )
                    )
                pos += len(content)
        if ctx.material.derived:
            spans = [
                s.model_copy(update={"role": SpanRole.DERIVED_SUMMARY}) for s in spans
            ]
        issues = [
            ValidationIssue(
                code=IssueCode.EMBEDDED_INSTRUCTION,
                severity=DEFAULT_SEVERITY[IssueCode.EMBEDDED_INSTRUCTION],
                message="材料包含面向系统的指令性文字，仅保留为证据，不执行也不作为结论依据。",
                evidence_refs=[s.id],
                rule_id="r.input.instruction@1",
            )
            for s in spans
            if INSTRUCTION.search(s.text)
        ]
        return ParseOutput(
            material_id=mid,
            parser=self.name,
            status=ParseStatus.PARSED if spans else ParseStatus.NEEDS_REVIEW,
            spans=spans,
            issues=issues,
            note=None if spans else "材料为空，等待补充。",
        )


PARSERS = [
    TextParser(k)
    for k in (
        MaterialKind.TICKET_FIELDS,
        MaterialKind.PROCESS_LOG,
        MaterialKind.EMAIL_HTML,
        MaterialKind.TEXT,
    )
]
