"""分析结果：流水线的最终输出 JSON，也是报告模板和审核界面唯一的输入。"""

from __future__ import annotations

from enum import StrEnum
from typing import Iterator, Literal

from pydantic import Field, model_validator

from .bundle import RelatedTicket
from .suggestions import BusinessSuggestion, source_refs
from ..quote_match import QuoteCheck, match_quote
from .common import Attribution, DataClass, EvidenceId, Model, material_of
from .elements import SevenElements, StepKind
from .evidence import EvidenceSpan, Material
from .issues import ValidationIssue
from .timeval import TimeKind, TimeValue


class Event(Model):
    """时间线上的一个事件（ARCHITECTURE_OPTIONS §5.4 第一步“事件抽取”的产物）。"""

    id: str = Field(pattern=r"^EV[A-Za-z0-9_.\-]+$")
    time: TimeValue | None = None
    time_kind: TimeKind | None = None
    actor: str | None = None
    attribution: Attribution
    action: str
    target: str | None = None
    result: str | None = None
    scope: str | None = None
    event_kind: StepKind
    evidence_refs: list[EvidenceId] = Field(min_length=1)
    duplicate_of: str | None = Field(default=None, description="重复事件指向首次出现的事件编号")


class IdentityStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CONFLICTING = "conflicting"


class ServiceIdentifier(Model):
    value: str
    role: Literal["reported", "old", "new", "current", "other"]
    evidence_refs: list[EvidenceId] = Field(default_factory=list)
    note: str | None = None


class ServiceIdentity(Model):
    """本次报障到底对应哪条服务（S10 新旧编号、X01 运营商归属）。"""

    status: IdentityStatus
    identifiers: list[ServiceIdentifier] = Field(default_factory=list)
    note: str | None = None


class RunInfo(Model):
    """结果绑定的输入快照与各组件版本（PRD §10：所有结果绑定版本）。"""

    pipeline_version: str
    schema_version: str
    provider: str = Field(description="rules / replay / local / openai_compatible:<name>")
    prompt_version: str | None = None
    rules_version: str | None = None
    bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$", description="manifest.json 的哈希，代表输入快照")
    started_at: str
    finished_at: str | None = None


class AnalysisResult(Model):
    schema_version: Literal["1.0"] = "1.0"
    bundle_id: str
    ticket_ref: str
    data_class: DataClass
    data_cutoff: str = Field(description="数据截止时间（= 工单包 captured_at）")
    materials: list[Material]
    evidence: list[EvidenceSpan]
    events: list[Event] = Field(default_factory=list)
    suggestions: list[BusinessSuggestion] = Field(default_factory=list)
    quote_checks: list[QuoteCheck] = Field(default_factory=list)
    elements: SevenElements
    issues: list[ValidationIssue] = Field(default_factory=list)
    service_identity: ServiceIdentity | None = None
    related_tickets: list[RelatedTicket] = Field(default_factory=list)
    run: RunInfo

    def iter_evidence_refs(self) -> Iterator[str]:
        yield from self.elements.iter_evidence_refs()
        for suggestion in self.suggestions:
            yield from suggestion.iter_evidence_refs()
        for check in self.quote_checks:
            yield check.evidence_id
        for ev in self.events:
            yield from ev.evidence_refs
        for issue in self.issues:
            yield from issue.evidence_refs
        for span in self.evidence:
            yield from span.derived_from
        if self.service_identity:
            for ident in self.service_identity.identifiers:
                yield from ident.evidence_refs

    @model_validator(mode="after")
    def _referential_integrity(self) -> AnalysisResult:
        """引用完整性：防止模型编造证据编号（实现计划 §7“模型返回不存在的证据 ID”）。"""
        material_ids = {m.id for m in self.materials}
        if len(material_ids) != len(self.materials):
            raise ValueError("材料编号重复")
        span_ids = [s.id for s in self.evidence]
        if len(span_ids) != len(set(span_ids)):
            raise ValueError("证据编号重复")
        orphan = sorted({s.material_id for s in self.evidence} - material_ids)
        if orphan:
            raise ValueError(f"证据指向不存在的材料: {orphan}")
        known = set(span_ids)
        missing = sorted({r for r in self.iter_evidence_refs() if r not in known})
        if missing:
            raise ValueError(f"引用了不存在的证据编号: {missing}")
        spans = {s.id: s for s in self.evidence}
        for suggestion in self.suggestions:
            if any(not source_refs(c) for c in suggestion.original.get("candidates", []) or []):
                raise ValueError("建议候选缺少来源")
            if suggestion.original.get("value") and not source_refs(suggestion.original):
                raise ValueError("建议答案缺少来源")
            expected = [match_quote(text, spans[ref].text, path=path, evidence_id=ref)
                        for path, ref, text in suggestion.quote_requests()]
            if suggestion.checks != expected:
                raise ValueError("建议引用核验记录与原文不一致")
        for check in self.quote_checks:
            if check != match_quote(check.quote, spans[check.evidence_id].text,
                                    path=check.path, evidence_id=check.evidence_id):
                raise ValueError("引用核验记录与原文不一致")
        event_ids = [e.id for e in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("事件编号重复")
        return self

    def span(self, evidence_id: str) -> EvidenceSpan:
        for s in self.evidence:
            if s.id == evidence_id:
                return s
        raise KeyError(evidence_id)

    def material_for(self, evidence_id: str) -> Material:
        mid = material_of(evidence_id)
        return next(m for m in self.materials if m.id == mid)
