"""校验问题码。

问题码是 A1（文本链路、确定性规则）、A2（附件）、A4（评测）与标准答案共用的词表。
规则：只追加，不改名、不删除；新增时在 docs/CONTRACTS.md 的问题码表里补一行。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from .common import CandidateId, ElementName, EvidenceId, Model


class Severity(StrEnum):
    CRITICAL = "critical"  # 关键冲突：未解决前不能标记为“已审核结案报告”
    WARNING = "warning"  # 需要人工核对
    INFO = "info"  # 提示，报告中披露即可


class IssueCode(StrEnum):
    SEMANTIC_ASSERTIONS_CONFLICT = "SEMANTIC_ASSERTIONS_CONFLICT"
    SEMANTIC_RELATION_INCOMPLETE = "SEMANTIC_RELATION_INCOMPLETE"
    SEMANTIC_STATUS_DOWNGRADED = "SEMANTIC_STATUS_DOWNGRADED"
    # —— 时间 ——
    TIME_ORDER_INVERTED = "TIME_ORDER_INVERTED"  # 恢复早于发生等时间倒置
    NEGATIVE_DURATION = "NEGATIVE_DURATION"  # 历时为负
    TIME_PLACEHOLDER = "TIME_PLACEHOLDER"  # 未替换的模板占位符，如 {{end_time}}
    TIME_TZ_MISSING = "TIME_TZ_MISSING"  # 原文无时区，按系统口径假设或无法归一
    TIME_CANDIDATES_DIFFER = "TIME_CANDIDATES_DIFFER"  # 同一要素有多个语义不同/数值不同的时间候选
    TIME_BODY_RECORD_MISMATCH = "TIME_BODY_RECORD_MISMATCH"  # 正文日期与记录日期不一致
    DURATION_BASIS_MISMATCH = "DURATION_BASIS_MISMATCH"  # 返单历时与字段起止差口径不同
    # —— 恢复 ——
    ONGOING_NO_END = "ONGOING_NO_END"  # 未见恢复：结束时间留空，不计最终历时
    RECOVERY_UNVERIFIED = "RECOVERY_UNVERIFIED"  # 有恢复字段，但没有客户确认等依据
    RECOVERY_SCOPE_LIMITED = "RECOVERY_SCOPE_LIMITED"  # 只有范围内正常/无告警，不能视为业务恢复
    # —— 原因 / 责任 ——
    CAUSE_NOT_DIAGNOSIS = "CAUSE_NOT_DIAGNOSIS"  # 原因栏是排查结论/告警解释/恢复方式/资源状态，不是根因
    CAUSE_CANDIDATE_LIST = "CAUSE_CANDIDATE_LIST"  # 原因栏是可能原因清单，未确认哪项发生
    RESPONSIBILITY_NO_BASIS = "RESPONSIBILITY_NO_BASIS"  # 没有定责依据，不按供应商/处理部门补齐
    # —— 现象 ——
    OBSERVATION_SCOPE_DIFFERS = "OBSERVATION_SCOPE_DIFFERS"  # 客户与网络侧观测范围不同，不能互相否定
    # —— 地点 ——
    LOCATION_NOT_LOCATED = "LOCATION_NOT_LOCATED"  # 只有业务端点/告警位置/测试节点，未定位故障点
    # —— 身份与关联 ——
    SERVICE_IDENTITY_UNVERIFIED = "SERVICE_IDENTITY_UNVERIFIED"  # 新旧编号、带宽、拆机、归属冲突
    RELATED_TICKET_SHARED_SOURCE = "RELATED_TICKET_SHARED_SOURCE"  # 与其他工单共用告警：不是独立证据
    RELATED_TICKET_INVALID = "RELATED_TICKET_INVALID"  # 关联单为作废/撤销/重复单：不作为有效结论
    RELATED_TICKET_REOPENED = "RELATED_TICKET_REOPENED"  # 重开历史单：旧单结单不代表已恢复
    TICKET_CANCELLED = "TICKET_CANCELLED"  # 本单已撤销/作废：不按有效故障结案、不计历时
    STATUS_VIEW_MISMATCH = "STATUS_VIEW_MISMATCH"  # 列表与详情状态不一致
    # —— 证据 ——
    EVIDENCE_REF_MISSING = "EVIDENCE_REF_MISSING"  # 引用了不存在的证据编号
    EVIDENCE_QUOTE_MISMATCH = "EVIDENCE_QUOTE_MISMATCH"  # 引用的原文不在该证据片段里
    DERIVED_SOURCE_DUPLICATE = "DERIVED_SOURCE_DUPLICATE"  # AI 摘要/邮件引用与原文重复，不计独立证据
    DUPLICATE_CONTENT = "DUPLICATE_CONTENT"  # 同一结论被重复记录多次
    # —— 材料 ——
    MATERIAL_PARSE_FAILED = "MATERIAL_PARSE_FAILED"  # 材料解析失败：该材料的证据缺失，相关要素不能据此判断
    MATERIAL_LOW_QUALITY = "MATERIAL_LOW_QUALITY"  # OCR/识图质量低：读数需要人工复核
    MATERIAL_UNSUPPORTED = "MATERIAL_UNSUPPORTED"  # 格式不支持或解析器未实现：显式提示，不能静默漏掉
    MATERIAL_MISSING = "MATERIAL_MISSING"  # 清单声明的材料缺失/哈希不符
    ATTACHMENT_FLAG_MISMATCH = "ATTACHMENT_FLAG_MISMATCH"  # 日志的附件标志与实际附件不一致
    # —— 安全 ——
    EMBEDDED_INSTRUCTION = "EMBEDDED_INSTRUCTION"  # 材料里有面向系统/AI 的指令性文字，只作数据处理


DEFAULT_SEVERITY: dict[IssueCode, Severity] = {
    IssueCode.SEMANTIC_ASSERTIONS_CONFLICT: Severity.WARNING,
    IssueCode.SEMANTIC_RELATION_INCOMPLETE: Severity.WARNING,
    IssueCode.SEMANTIC_STATUS_DOWNGRADED: Severity.INFO,
    IssueCode.TIME_ORDER_INVERTED: Severity.CRITICAL,
    IssueCode.NEGATIVE_DURATION: Severity.CRITICAL,
    IssueCode.EVIDENCE_REF_MISSING: Severity.CRITICAL,
    IssueCode.EVIDENCE_QUOTE_MISMATCH: Severity.CRITICAL,
    IssueCode.TIME_PLACEHOLDER: Severity.WARNING,
    IssueCode.TIME_TZ_MISSING: Severity.INFO,
    IssueCode.TIME_CANDIDATES_DIFFER: Severity.WARNING,
    IssueCode.TIME_BODY_RECORD_MISMATCH: Severity.WARNING,
    IssueCode.DURATION_BASIS_MISMATCH: Severity.INFO,
    IssueCode.ONGOING_NO_END: Severity.INFO,
    IssueCode.RECOVERY_UNVERIFIED: Severity.WARNING,
    IssueCode.RECOVERY_SCOPE_LIMITED: Severity.WARNING,
    IssueCode.CAUSE_NOT_DIAGNOSIS: Severity.WARNING,
    IssueCode.CAUSE_CANDIDATE_LIST: Severity.WARNING,
    IssueCode.RESPONSIBILITY_NO_BASIS: Severity.INFO,
    IssueCode.OBSERVATION_SCOPE_DIFFERS: Severity.WARNING,
    IssueCode.LOCATION_NOT_LOCATED: Severity.INFO,
    IssueCode.SERVICE_IDENTITY_UNVERIFIED: Severity.WARNING,
    IssueCode.RELATED_TICKET_SHARED_SOURCE: Severity.INFO,
    IssueCode.RELATED_TICKET_INVALID: Severity.WARNING,
    IssueCode.RELATED_TICKET_REOPENED: Severity.INFO,
    IssueCode.TICKET_CANCELLED: Severity.WARNING,
    IssueCode.STATUS_VIEW_MISMATCH: Severity.INFO,
    IssueCode.DERIVED_SOURCE_DUPLICATE: Severity.INFO,
    IssueCode.DUPLICATE_CONTENT: Severity.INFO,
    IssueCode.MATERIAL_PARSE_FAILED: Severity.WARNING,
    IssueCode.MATERIAL_LOW_QUALITY: Severity.WARNING,
    IssueCode.MATERIAL_UNSUPPORTED: Severity.WARNING,
    IssueCode.MATERIAL_MISSING: Severity.CRITICAL,
    IssueCode.ATTACHMENT_FLAG_MISMATCH: Severity.INFO,
    IssueCode.EMBEDDED_INSTRUCTION: Severity.WARNING,
}


class ValidationIssue(Model):
    code: IssueCode
    severity: Severity
    message: str = Field(description="给审核人员看的中文说明")
    element: ElementName | None = Field(default=None, description="影响的要素；整单级问题为空")
    evidence_refs: list[EvidenceId] = Field(default_factory=list)
    candidate_ids: list[CandidateId] = Field(default_factory=list)
    rule_id: str | None = Field(default=None, description="产生该问题的规则及版本，如 'r.time.order@1'")
    resolved: bool = False
    resolution_note: str | None = None
