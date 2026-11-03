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


class BusinessRelation(SemanticRelation):
    statement: str = Field(min_length=1, description="原文断言，与标准化结论分开")
    source_tier: Literal["rfo", "vendor_feedback", "branch_log", "unknown"]
    source_quote: RelationQuote | None = None
    speaker: str | None = Field(default=None, min_length=1)
    contradicts: list[str] = Field(default_factory=list)


class PartyRelation(BusinessRelation):
    responsibility_quote: RelationQuote | None = None
    category: Literal["客户", "供应商", "联通", "other", "joint", "unknown"]
    decision_path: Literal["explicit_responsibility", "customer_self_check", "vendor_onsite_contact",
                           "unicom_onsite_recovery", "equipment_ownership", "role_only", "unknown"]
    customer_device_fault: bool | None = None
    procurement: Literal["客户", "供应商", "联通", "unknown"] = "unknown"
    procurement_quote: RelationQuote | None = None
    self_check: RelationQuote | None = None
    no_followup: bool | None = None
    vendor_contact: RelationQuote | None = None
    unicom_onsite: RelationQuote | None = None
    service_recovered: RelationQuote | None = None


class LocationRelation(BusinessRelation):
    city: str | None = None
    city_quote: RelationQuote | None = None
    located: bool | None = None
    city_scope: Literal["single_city", "cross_city", "unknown"] = "unknown"


class BusinessCoverage(Model):
    """本地记录输入覆盖范围，不能由模型提交；哈希绑定完整处理记录。"""
    detail_status: str | None = None
    log_hashes: dict[str, str] = Field(default_factory=dict)
    covered_logs: dict[str, EvidenceId] = Field(default_factory=dict)
    related_materials_complete: bool = False



class ConstraintCheck(Model):
    element: Literal["start_time", "end_time", "cause", "responsible_party", "location"]
    candidate_id: str | None = None
    code: IssueCode = IssueCode.SEMANTIC_RELATION_INCOMPLETE
    outcome: Literal["eligible", "pending", "conflict", "downgraded"]
    reason: str
    evidence_refs: list[EvidenceId] = Field(default_factory=list)


class SemanticAssessment(Model):
    """只由本地解码器构建；original 的来源与引文须核验，但不用于补造正式结论。"""
    original: dict[str, Any] = Field(default_factory=dict)
    checks: list[ConstraintCheck] = Field(default_factory=list)
    business_coverage: BusinessCoverage | None = None
