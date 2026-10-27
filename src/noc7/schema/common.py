"""各模块共用的基类、枚举和编号规则。"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints


class Model(BaseModel):
    """契约模型基类：拒绝未声明字段，避免两条开发线各自偷偷加字段。"""

    model_config = ConfigDict(extra="forbid", use_enum_values=False, validate_assignment=True)


# ---------------------------------------------------------------------------
# 编号规则
# ---------------------------------------------------------------------------
# 材料编号：工单包内唯一，M01、M02……
MATERIAL_ID_PATTERN = r"^M\d{2,}$"
# 证据编号：<材料编号>/<材料内局部编号>。局部编号由负责该材料类型的解析器分配，
# 不使用全局计数器，所以文本解析（A1）和附件解析（A2）并行运行也不会撞号。
EVIDENCE_ID_PATTERN = r"^M\d{2,}/[A-Za-z0-9:_.\-]+$"
# 候选编号：要素内唯一，例如 C1、C2、start.field
CANDIDATE_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_.\-]*$"
# 工单包字段键：snake_case
FIELD_KEY_PATTERN = r"^[a-z][a-z0-9_]*$"

MaterialId = Annotated[str, StringConstraints(pattern=MATERIAL_ID_PATTERN)]
EvidenceId = Annotated[str, StringConstraints(pattern=EVIDENCE_ID_PATTERN)]
CandidateId = Annotated[str, StringConstraints(pattern=CANDIDATE_ID_PATTERN)]
FieldKey = Annotated[str, StringConstraints(pattern=FIELD_KEY_PATTERN)]

_EVIDENCE_RE = re.compile(EVIDENCE_ID_PATTERN)


def material_of(evidence_id: str) -> str:
    """从证据编号取出材料编号：'M03/msg:1' -> 'M03'。"""
    if not _EVIDENCE_RE.match(evidence_id):
        raise ValueError(f"不是合法的证据编号: {evidence_id!r}")
    return evidence_id.split("/", 1)[0]


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------
class DataClass(StrEnum):
    """数据分级。决定数据能否发往外部服务（见 noc7.providers.gate）。"""

    SYNTHETIC = "synthetic"  # 合成数据：可以进仓库，可以发给获准的外部模型调试
    REAL = "real"  # 真实工单：只存仓库外本机目录，外发闸门一律拦截


class ElementName(StrEnum):
    """七要素。顺序即报告中的展示顺序。"""

    START_TIME = "start_time"  # 发生时间
    END_TIME = "end_time"  # 结束时间
    PHENOMENON = "phenomenon"  # 故障现象
    RESPONSIBLE_PARTY = "responsible_party"  # 故障责任方
    CAUSE = "cause"  # 故障原因
    HANDLING_PROCESS = "handling_process"  # 处理过程
    LOCATION = "location"  # 故障地点


ELEMENT_LABELS_ZH: dict[ElementName, str] = {
    ElementName.START_TIME: "发生时间",
    ElementName.END_TIME: "结束时间",
    ElementName.PHENOMENON: "故障现象",
    ElementName.RESPONSIBLE_PARTY: "故障责任方",
    ElementName.CAUSE: "故障原因",
    ElementName.HANDLING_PROCESS: "处理过程",
    ElementName.LOCATION: "故障地点",
}


class ElementStatus(StrEnum):
    """要素状态（PRD §6）。模型自评置信度不能代替状态。"""

    DOCUMENTED = "documented"  # 原文有记载，但没有独立确认依据
    CONFIRMED = "confirmed"  # 有明确确认依据（如客户确认、现场报告、正式定责）或人工确认
    UNKNOWN = "unknown"  # 材料不足以给出结论；value 必须为空
    CONFLICTED = "conflicted"  # 多个候选互相矛盾，未裁定；value 必须为空


class Attribution(StrEnum):
    """陈述归属。报告里要保留“客户反馈”“供应商称”“检查显示”这类归属。"""

    CUSTOMER = "customer"  # 客户反馈
    VENDOR = "vendor"  # 供应商/上游运营商称
    NOC_CHECK = "noc_check"  # 本方网管/值班检查显示
    FIELD_ENGINEER = "field_engineer"  # 现场工程师
    SYSTEM_FIELD = "system_field"  # 工单系统字段记载
    ALARM_SYSTEM = "alarm_system"  # 告警系统
    MONITORING_CHART = "monitoring_chart"  # 监控截图/曲线
    AI_SUMMARY = "ai_summary"  # 源系统已有的 AI 摘要（衍生材料）
    INTERNAL_STAFF = "internal_staff"  # 内部其他人员（客户经理等）
    UNKNOWN = "unknown"


ATTRIBUTION_LABELS_ZH: dict[Attribution, str] = {
    Attribution.CUSTOMER: "客户反馈",
    Attribution.VENDOR: "供应商称",
    Attribution.NOC_CHECK: "检查显示",
    Attribution.FIELD_ENGINEER: "现场工程师称",
    Attribution.SYSTEM_FIELD: "系统记载",
    Attribution.ALARM_SYSTEM: "告警显示",
    Attribution.MONITORING_CHART: "监控截图显示",
    Attribution.AI_SUMMARY: "AI 摘要称",
    Attribution.INTERNAL_STAFF: "内部人员称",
    Attribution.UNKNOWN: "来源不明",
}
