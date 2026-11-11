"""七要素结构。

每个要素 = 结论（value）+ 状态（status）+ 全部候选（candidates）+ 证据引用 + 问题码 + 审核信息。
设计要点（详见 docs/decisions/0002-seven-element-schema.md）：

- 缺失就是 null，不用“正常”“其他”“无”填充；
- unknown / conflicted 时 value 必须为空，候选照样保留；
- 每个候选都有语义分类（时间语义、原因类别、地点角色、定责依据），因为调研发现
  “字段名 ≠ 语义”：原因栏常是排查结论，地址常是业务端点而非故障点；
- 这里只放结构不变式（任何时候都必须成立）；业务规则（时间先后、身份冲突等）
  属于 A1 的确定性规则模块，不写在 schema 里。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Iterator

from pydantic import Field, model_validator

from .common import Attribution, CandidateId, ElementName, ElementStatus, EvidenceId, Model
from .issues import IssueCode
from .timeval import TimeKind, TimeValue
from .relations import TimeRelation, CauseRelation, PartyRelation, LocationRelation


# ---------------------------------------------------------------------------
# 候选
# ---------------------------------------------------------------------------
class CandidateBase(Model):
    id: CandidateId
    evidence_refs: list[EvidenceId] = Field(min_length=1, description="候选必须有证据，否则不能成为候选")
    attribution: Attribution
    note: str | None = None


class TimeCandidate(CandidateBase):
    time: TimeValue
    time_kind: TimeKind
    relation: TimeRelation | None = None


class Observation(CandidateBase):
    """一次观测。不同时刻、不同来源的观测并列保存，不压成一个数（S06：86%、10%、ping 中断）。"""

    description: str
    metric: str | None = Field(default=None, description="指标：丢包率、时延、收光功率、告警……")
    value: float | None = None
    value_text: str | None = Field(default=None, description="非数值读数的原文，如 ping 中断、R_LOS")
    unit: str | None = None
    scope: str | None = Field(default=None, description="观测范围/测试对象：端到端、国内段、某 QoS 类别……")
    observed_at: TimeValue | None = None


class ResponsibilityBasis(StrEnum):
    FORMAL_DETERMINATION = "formal_determination"  # 有明确的定责结论（责任认定、定责意见）
    CLAIMED = "claimed"  # 某方自称/指称，未经认定
    BUSINESS_CONTEXT = "business_context"  # 按已确认业务路径判定，未经人工审核
    INFERRED_FROM_ROLE = "inferred_from_role"  # 只是供应商、处理部门、经办人等角色——不能作为结论
    SYSTEM_FIELD = "system_field"  # 工单系统分类字段（结单人填写），只在原文没有依据时兜底并标注待核实


class PartyCandidate(CandidateBase):
    party: str
    basis: ResponsibilityBasis
    relation: PartyRelation | None = None


class CauseKind(StrEnum):
    UNCLASSIFIED = "unclassified"  # 未知模型类别保留候选，不升级
    SUSPECTED_MECHANISM = "suspected_mechanism"
    ROOT_CAUSE_CONFIRMED = "root_cause_confirmed"  # 有现场/诊断依据的根因
    ROOT_CAUSE_CLAIMED = "root_cause_claimed"  # 某方陈述的原因（供应商称……），未经核实
    CANDIDATE_LIST_ITEM = "candidate_list_item"  # 告警的“可能原因”清单中的一项
    INVESTIGATION_FINDING = "investigation_finding"  # 排查结论：无告警、某段正常、未见倒换
    ALARM_EXPLANATION = "alarm_explanation"  # 告警机制说明
    RECOVERY_MODE = "recovery_mode"  # 恢复方式：自恢、重启后恢复
    RESOURCE_STATE = "resource_state"  # 资源状态：线路已拆机、非本运营商业务
    PLANNED_WORK = "planned_work"  # 计划割接/维护
    PROCESS_BLOCKER = "process_blocker"  # 处理阻塞：缺联系人、待约测试窗口
    CUSTOMER_SUSPICION = "customer_suspicion"  # 客户的怀疑


# 可以作为“故障原因”结论值的类别；其余类别只能留在候选里
CAUSE_KINDS_ALLOWED_AS_VALUE = {
    CauseKind.ROOT_CAUSE_CONFIRMED,
    CauseKind.ROOT_CAUSE_CLAIMED,
    CauseKind.PLANNED_WORK,
}


class CauseCandidate(CandidateBase):
    statement: str
    cause_kind: CauseKind
    relation: CauseRelation | None = None


class StepKind(StrEnum):
    TECHNICAL_ACTION = "technical_action"  # 实际排障/修复动作
    CHECK_RESULT = "check_result"  # 检查及其结果
    COMMUNICATION = "communication"  # 联系客户、报障供应商、索要资料
    WORKFLOW = "workflow"  # 受理、转派、挂起、返单、结单等流程流转
    PLANNED = "planned"  # 计划中、尚未发生的动作


class ProcessStep(CandidateBase):
    time: TimeValue | None = None
    actor: str | None = None
    action: str
    target: str | None = None
    result: str | None = None
    step_kind: StepKind
    duplicate_of: CandidateId | None = Field(default=None, description="与哪一步重复（重复结论去重后保留关系）")


class LocationRole(StrEnum):
    LOCATED_FAULT_POINT = "located_fault_point"  # 已定位的故障点：只有它能成为“故障地点”的结论
    ALARM_LOCATION = "alarm_location"  # 告警所在设备/槽位/端口
    SERVICE_ENDPOINT = "service_endpoint"  # 业务端点
    CUSTOMER_SITE = "customer_site"  # 客户现场/地址
    TEST_NODE = "test_node"  # 测试源/目的、检查节点
    TRANSIT_NODE = "transit_node"  # 途经节点


class LocationGranularity(StrEnum):
    COUNTRY = "country"
    CITY = "city"
    SITE = "site"
    SEGMENT = "segment"  # 两点之间的线路段
    DEVICE = "device"
    PORT = "port"


class LocationCandidate(CandidateBase):
    description: str
    role: LocationRole
    granularity: LocationGranularity | None = None
    relation: LocationRelation | None = None


# ---------------------------------------------------------------------------
# 审核
# ---------------------------------------------------------------------------
class ReviewAction(StrEnum):
    ACCEPTED = "accepted"
    EDITED = "edited"
    CLEARED = "cleared"


class ReviewInfo(Model):
    action: ReviewAction
    reviewer: str
    reviewed_at: datetime
    reason: str | None = None
    machine_value: Any = Field(default=None, description="审核前机器给出的值快照，便于比较人工修改率")


# ---------------------------------------------------------------------------
# 要素
# ---------------------------------------------------------------------------
class ElementBase(Model):
    status: ElementStatus
    evidence_refs: list[EvidenceId] = Field(default_factory=list, description="支撑结论值的证据")
    issues: list[IssueCode] = Field(default_factory=list)
    review: ReviewInfo | None = None
    note: str | None = Field(default=None, description="给报告和审核人员的说明，如“未见恢复确认”")

    # 子类提供
    def _has_value(self) -> bool:
        raise NotImplementedError

    def iter_candidates(self) -> Iterator[CandidateBase]:
        return iter(getattr(self, "candidates", []) or [])

    @model_validator(mode="after")
    def _invariants(self) -> ElementBase:
        has_value = self._has_value()
        candidates = list(self.iter_candidates())
        if self.status in (ElementStatus.UNKNOWN, ElementStatus.CONFLICTED) and has_value:
            raise ValueError(f"状态为 {self.status} 时 value 必须为空")
        if self.status is ElementStatus.DOCUMENTED:
            if not has_value or not self.evidence_refs:
                raise ValueError("documented 要求有 value 且有 evidence_refs")
        if self.status is ElementStatus.CONFIRMED:
            if not has_value or not (self.evidence_refs or self.review):
                raise ValueError("confirmed 要求有 value，且有证据或人工审核记录")
        if self.status is ElementStatus.CONFLICTED and len(candidates) < 2:
            raise ValueError("conflicted 至少要有两个候选")
        ids = [c.id for c in candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("候选编号重复")
        selected = getattr(self, "selected", None)
        if selected is not None and selected not in ids:
            raise ValueError(f"selected={selected} 不在候选中")
        if self.review and self.review.action is ReviewAction.CLEARED and has_value:
            raise ValueError("人工清空后 value 必须为空")
        return self


class TimeElement(ElementBase):
    value: TimeValue | None = None
    selected: CandidateId | None = Field(default=None, description="结论值取自哪个候选")
    candidates: list[TimeCandidate] = Field(default_factory=list)

    def _has_value(self) -> bool:
        return self.value is not None


class PhenomenonElement(ElementBase):
    value: str | None = Field(default=None, description="现象概述，必须保留观测方归属")
    candidates: list[Observation] = Field(default_factory=list, description="全部观测，并列保存")

    def _has_value(self) -> bool:
        return self.value is not None


class ResponsiblePartyElement(ElementBase):
    value: str | None = None
    selected: CandidateId | None = None
    candidates: list[PartyCandidate] = Field(default_factory=list)

    def _has_value(self) -> bool:
        return self.value is not None

    @model_validator(mode="after")
    def _needs_determination(self) -> ResponsiblePartyElement:
        # 只靠角色推断（供应商、处理部门）的候选不能成为结论
        if self.selected is not None:
            chosen = next(c for c in self.candidates if c.id == self.selected)
            if chosen.basis is ResponsibilityBasis.INFERRED_FROM_ROLE:
                raise ValueError("仅凭角色推断的责任方不能作为结论值")
        return self


class CauseElement(ElementBase):
    value: str | None = None
    selected: CandidateId | None = None
    candidates: list[CauseCandidate] = Field(default_factory=list)

    def _has_value(self) -> bool:
        return self.value is not None

    @model_validator(mode="after")
    def _kind_allowed(self) -> CauseElement:
        if self.selected is not None:
            chosen = next(c for c in self.candidates if c.id == self.selected)
            if chosen.cause_kind not in CAUSE_KINDS_ALLOWED_AS_VALUE:
                raise ValueError(f"原因类别 {chosen.cause_kind} 不能作为故障原因结论，只能留作候选")
        return self


class HandlingProcessElement(ElementBase):
    value: list[ProcessStep] = Field(default_factory=list, description="按时间排列的处理步骤")

    def _has_value(self) -> bool:
        return bool(self.value)

    def iter_candidates(self) -> Iterator[CandidateBase]:
        return iter(self.value)


class LocationElement(ElementBase):
    value: str | None = None
    selected: CandidateId | None = None
    candidates: list[LocationCandidate] = Field(default_factory=list)

    def _has_value(self) -> bool:
        return self.value is not None

    @model_validator(mode="after")
    def _located_only(self) -> LocationElement:
        if self.selected is not None:
            chosen = next(c for c in self.candidates if c.id == self.selected)
            if chosen.role is not LocationRole.LOCATED_FAULT_POINT:
                raise ValueError("只有 located_fault_point 角色的候选能作为故障地点结论")
        return self


class SevenElements(Model):
    start_time: TimeElement
    end_time: TimeElement
    phenomenon: PhenomenonElement
    responsible_party: ResponsiblePartyElement
    cause: CauseElement
    handling_process: HandlingProcessElement
    location: LocationElement

    def items(self) -> Iterator[tuple[ElementName, ElementBase]]:
        for name in ElementName:
            yield name, getattr(self, name.value)

    def iter_evidence_refs(self) -> Iterator[str]:
        for _, el in self.items():
            yield from el.evidence_refs
            for c in el.iter_candidates():
                yield from c.evidence_refs
                relation = getattr(c, "relation", None)
                if relation:
                    for quote in relation.context:
                        yield quote.evidence_id
                    for key in ("date_anchor", "timezone_anchor", "customer_confirmation", "recovery_source_basis", "correction_basis",
                                "responsibility_quote", "source_quote", "procurement_quote", "self_check", "vendor_contact",
                                "unicom_onsite", "service_recovered", "city_quote"):
                        quote = getattr(relation, key, None)
                        if quote:
                            yield quote.evidence_id
