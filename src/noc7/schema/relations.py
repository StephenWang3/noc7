"""模型关系与本地约束检查分开；原始模型断言不是人工审核。"""
from typing import Any, Literal

from pydantic import Field

from .common import EvidenceId, Model
from .issues import IssueCode


class RelationQuote(Model):
    evidence_id: EvidenceId
    quote: str = Field(min_length=1)


class SemanticRelation(Model):
    event_id: str = Field(min_length=1, description="模型分组的事件标识，不是已核实的身份")
    scope: str = Field(min_length=1, description="业务／设备范围")
    context: list[RelationQuote] = Field(min_length=1)
    current_event: bool
    modality: Literal["asserted", "suspected", "negated", "unknown"]


class TimeRelation(SemanticRelation):
    # time_kind 在候选上；关系用于解释它与事件、原文和确认的连接。
    date_anchor: RelationQuote | None = None
    timezone_anchor: RelationQuote | None = None
    customer_confirmation: RelationQuote | None = None


class CauseRelation(SemanticRelation):
    contradicts: list[str] = Field(default_factory=list)
    assertion: Literal["fault", "mechanism", "planned_work", "phenomenon", "finding", "recovery", "unknown"]
    affects_service: bool
    occurred: bool
    speaker: str = Field(min_length=1)


class ConstraintCheck(Model):
    element: Literal["start_time", "end_time", "cause"]
    candidate_id: str | None = None
    code: IssueCode = IssueCode.SEMANTIC_RELATION_INCOMPLETE
    outcome: Literal["eligible", "pending", "conflict", "downgraded"]
    reason: str
    evidence_refs: list[EvidenceId] = Field(default_factory=list)


class SemanticAssessment(Model):
    """只由本地解码器构建；original 的来源与引文须核验，但不用于补造正式结论。"""
    original: dict[str, Any] = Field(default_factory=dict)
    checks: list[ConstraintCheck] = Field(default_factory=list)
