"""标准工单包格式（bundle format 1.0）。

所有入口（合成样本、手动上传、只读导出脚本、将来的正式接口）都只负责产出这个包；
导入层以后不因数据来源变化而修改。格式说明见 docs/BUNDLE_FORMAT.md。

    <bundle>/
      manifest.json       BundleManifest：数据分级、来源、抓取时间、材料清单与哈希
      ticket.json         TicketRecord：基本字段、故障字段、列表/详情两种状态、关联单
      process_log.json    ProcessLog：处理过程逐条记录，每条逐一列出实际附件
      emails/*.html|eml   完整邮件详情（不是列表摘要）
      attachments/*       原始附件
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from .common import DataClass, FieldKey, MaterialId, Model
from .evidence import ManifestMaterial, MaterialKind


class BundleSource(Model):
    kind: Literal["synthetic", "noc_export", "upload"]
    tool: str | None = Field(default=None, description="生成工具及版本")
    note: str | None = None


class BundleManifest(Model):
    bundle_format_version: Literal["1.0"] = "1.0"
    bundle_id: str = Field(min_length=1)
    data_class: DataClass
    source: BundleSource
    captured_at: str = Field(description="抓取/数据截止时间，带时区的 ISO 8601")
    default_timezone: str | None = Field(
        default=None,
        pattern=r"^[+-]\d{2}:\d{2}$",
        description="源系统时间口径。原文无时区的时间按它解析并标记 assumed；为空表示口径未知",
    )
    synthetic_notice: str | None = Field(default=None, description="合成数据声明；合成包必填")
    materials: list[ManifestMaterial]

    @model_validator(mode="after")
    def _check(self) -> BundleManifest:
        ids = [m.id for m in self.materials]
        if len(ids) != len(set(ids)):
            raise ValueError("材料编号重复")
        paths = [m.path for m in self.materials]
        if len(paths) != len(set(paths)):
            raise ValueError("材料路径重复")
        kinds = [m.kind for m in self.materials]
        if kinds.count(MaterialKind.TICKET_FIELDS) != 1:
            raise ValueError("工单包必须恰好有一份 ticket_fields 材料（ticket.json）")
        if kinds.count(MaterialKind.PROCESS_LOG) > 1:
            raise ValueError("工单包最多一份 process_log 材料")
        known = set(ids)
        for m in self.materials:
            missing = [d for d in m.derived_from if d not in known]
            if missing:
                raise ValueError(f"{m.id} 的 derived_from 引用了不存在的材料 {missing}")
        if self.data_class is DataClass.SYNTHETIC and not self.synthetic_notice:
            raise ValueError("合成工单包必须填写 synthetic_notice")
        return self

    def material(self, material_id: str) -> ManifestMaterial:
        for m in self.materials:
            if m.id == material_id:
                return m
        raise KeyError(material_id)

    def material_of_kind(self, kind: MaterialKind) -> ManifestMaterial | None:
        return next((m for m in self.materials if m.kind is kind), None)


# ---------------------------------------------------------------------------
# ticket.json
# ---------------------------------------------------------------------------
class TicketFamily(StrEnum):
    """工单大类：业务单与自动大客户/中继/设备单在源系统里是两套详情布局。"""

    BUSINESS = "business"  # 业务故障（业务性能、业务中断）
    KEY_ACCOUNT = "key_account"  # 大客户
    TRUNK = "trunk"  # 中继
    DEVICE = "device"  # 设备
    OTHER = "other"


# 字段键的推荐词表。解析器和规则按键识别字段语义；label 保留源系统显示名。
# 字段名不等于语义（PRD §2）：例如 cause 字段里常常只是排查结论，规则要另行判断。
KNOWN_FIELD_KEYS: dict[str, str] = {
    "ticket_no": "工单编号",
    "fault_type": "故障类型",
    "customer": "客户名称",
    "circuit_id": "电路编号",
    "bandwidth": "带宽",
    "a_end": "A 端",
    "z_end": "Z 端",
    "created_at": "建单时间",
    "occurred_at": "故障发生时间",
    "recovered_at": "故障恢复时间",
    "duration_returned": "返单历时",
    "description": "故障描述",
    "cause": "故障原因",
    "responsible_party": "故障责任方",
    "handling_dept": "处理部门",
    "handler": "处理人",
    "vendor": "供应商",
    "region": "国家/城市",
    "alarm_serial": "告警流水号",
    "alarm_title": "告警标题",
    "alarm_level": "告警级别",
    "alarm_time": "告警时间",
    "alarm_cleared_at": "告警清除时间",
    "warning_title": "预警标题",
    "warning_time": "预警时间",
    "underlying_alarm": "底层告警",
    "possible_causes": "可能原因",
    "device_type": "设备类型",
    "device_name": "设备名称",
    "shelf_slot_port": "槽位/端口",
    "device_location": "位置信息",
    "trunk_name": "中继名称",
}


class TicketField(Model):
    key: FieldKey
    label: str = Field(description="源系统显示的字段名")
    value: str | None = Field(description="原文；空字段为 null，不填“无”“正常”")
    section: str | None = Field(default=None, description="所在页签/分区，如 基础信息、故障信息")


class StatusView(Model):
    """列表与详情状态可能不一致（S04、S05），两者都保留，不互相覆盖。"""

    list_status: str | None = None
    detail_status: str | None = None


class RelationKind(StrEnum):
    SHARED_ALARM = "shared_alarm"  # 共用同一告警流水号：不是独立证据
    REOPENED_FROM = "reopened_from"  # 客户要求重开的历史单
    SAME_CIRCUIT = "same_circuit"  # 同电路的其他工单（含作废、重复）
    PARENT_CHILD = "parent_child"  # 派生的延伸单/子单
    OTHER = "other"


class RelatedTicket(Model):
    ticket_ref: str
    relation: RelationKind
    status: str | None = Field(default=None, description="关联单在源系统中的状态，如 已作废、已结单")
    note: str | None = None


class TicketRecord(Model):
    ticket_ref: str = Field(min_length=1)
    title: str
    ticket_family: TicketFamily
    category: str | None = Field(default=None, description="源系统分类原文，如 业务性能-丢包")
    status: StatusView
    fields: list[TicketField]
    related_tickets: list[RelatedTicket] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_keys(self) -> TicketRecord:
        keys = [f.key for f in self.fields]
        dup = {k for k in keys if keys.count(k) > 1}
        if dup:
            raise ValueError(f"字段键重复: {sorted(dup)}")
        return self

    def field(self, key: str) -> TicketField | None:
        return next((f for f in self.fields if f.key == key), None)


# ---------------------------------------------------------------------------
# process_log.json
# ---------------------------------------------------------------------------
class LogEntryKind(StrEnum):
    HUMAN = "human"  # 人工处理意见
    SYSTEM = "system"  # 系统自动记录（建单、流转）
    EMAIL = "email"  # 邮件到达记录
    AI_SUMMARY = "ai_summary"  # 源系统的 AI 追单摘要/数字员工追加：衍生材料


class ProcessLogEntry(Model):
    seq: int = Field(ge=1, description="源系统显示的序号")
    recorded_at: str | None = Field(description="记录时间原文")
    actor: str | None = None
    actor_org: str | None = None
    action: str = Field(description="源系统动作名：建单、受理、转派、处理意见、信息追加、挂起、返单、结单、撤单申请……")
    content: str
    entry_kind: LogEntryKind = LogEntryKind.HUMAN
    attachment_flag: bool | None = Field(
        default=None,
        description="源系统日志顶层的 hasAttachments 原值，只留档。S10 证实它会与实际附件不符，不能据此判断有无附件",
    )
    attachments: list[MaterialId] = Field(default_factory=list, description="逐条详情里实际枚举到的附件")
    emails: list[MaterialId] = Field(default_factory=list, description="该条记录对应的完整邮件")


class ProcessLog(Model):
    entries: list[ProcessLogEntry]

    @model_validator(mode="after")
    def _seq(self) -> ProcessLog:
        seqs = [e.seq for e in self.entries]
        if seqs != sorted(seqs) or len(seqs) != len(set(seqs)):
            raise ValueError("处理过程序号必须唯一且升序")
        return self

    def entry(self, seq: int) -> ProcessLogEntry | None:
        return next((e for e in self.entries if e.seq == seq), None)

    def referenced_materials(self) -> set[str]:
        out: set[str] = set()
        for e in self.entries:
            out.update(e.attachments)
            out.update(e.emails)
        return out


__all__ = [
    "BundleManifest",
    "BundleSource",
    "KNOWN_FIELD_KEYS",
    "LogEntryKind",
    "MaterialId",
    "ProcessLog",
    "ProcessLogEntry",
    "RelatedTicket",
    "RelationKind",
    "StatusView",
    "TicketFamily",
    "TicketField",
    "TicketRecord",
]
