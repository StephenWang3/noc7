"""带类型的时间值。

调研发现字段起止差和“返单历时”经常对不上、正文日期与记录日期冲突、
海外设备记录没有时区、模板占位符 {{end_time}} 未替换（S02、S06、S07、S09、S10）。
所以时间不能只存一个 datetime：要同时保留原文、时区来源、精度和时间语义。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import model_validator

from .common import Model


class TimeZoneSource(StrEnum):
    EXPLICIT = "explicit"  # 原文写明时区（GMT+8、UTC、+08:00、北京时间）
    ASSUMED = "assumed"  # 原文没写，按工单包声明的系统口径假设；报告里要披露
    UNKNOWN = "unknown"  # 无法确定，iso 不带偏移


class TimePrecision(StrEnum):
    DAY = "day"
    HOUR = "hour"
    MINUTE = "minute"
    SECOND = "second"


class TimeKind(StrEnum):
    """时间语义。七要素里的时间候选必须标明自己是哪一种时间。"""

    FAULT_START_FIELD = "fault_start_field"  # 工单“故障发生时间”字段
    RECOVERY_FIELD = "recovery_field"  # 工单“故障恢复时间”字段
    CUSTOMER_REPORTED_START = "customer_reported_start"  # 客户陈述的起障时间
    CUSTOMER_CONFIRMED_RECOVERY = "customer_confirmed_recovery"  # 客户确认恢复的时间
    VENDOR_REPORTED = "vendor_reported"  # 供应商陈述的时间（修复、恢复等）
    REPAIR_COMPLETED = "repair_completed"  # 现场修复完成
    ALARM_RAISED = "alarm_raised"  # 设备告警产生
    ALARM_CLEARED = "alarm_cleared"  # 设备告警清除
    WARNING_RAISED = "warning_raised"  # 中继预警等二次告警
    OBSERVATION = "observation"  # 某次测量/检查的时刻
    CHART_FIRST_NONZERO = "chart_first_nonzero"  # 监控曲线首次出现非零值
    CHART_WINDOW = "chart_window"  # 监控截图的时间窗口端点
    TICKET_CREATED = "ticket_created"  # 建单
    TICKET_RETURNED = "ticket_returned"  # 返单
    TICKET_CLOSED = "ticket_closed"  # 结单 / 同意结单
    TICKET_CANCELLED = "ticket_cancelled"  # 撤单
    RECORD_TIME = "record_time"  # 处理过程的记录时间
    BODY_TEXT_DATE = "body_text_date"  # 处理意见正文里写的日期
    MESSAGE_SENT = "message_sent"  # 邮件发送时间
    PLANNED = "planned"  # 计划/预约时间（未来上门、割接窗口）
    HISTORICAL_SERVICE_EVENT = "historical_service_event"  # 历史交付日期等与本次故障无关的事件
    OTHER = "other"


class TimeValue(Model):
    """一个时间点。

    - raw：原文，永远保留；
    - iso：归一化值。时区已知或已假设时带偏移（2026-09-30T02:40:00+08:00），
      时区未知时不带偏移；原文无法解析（NA、占位符）时为空；
    - 精度只到日的时间，iso 只写日期（2026-09-03）。
    """

    raw: str
    iso: str | None = None
    tz_source: TimeZoneSource = TimeZoneSource.UNKNOWN
    utc_offset: str | None = None
    precision: TimePrecision | None = None
    placeholder: bool = False

    @model_validator(mode="after")
    def _consistent(self) -> TimeValue:
        if self.placeholder and self.iso is not None:
            raise ValueError("占位符时间不能有归一化值")
        if self.iso is None:
            if self.precision is not None:
                raise ValueError("无法解析的时间不能声明精度")
            return self
        if self.precision is None:
            raise ValueError("有归一化值时必须声明精度")
        if self.precision is TimePrecision.DAY:
            if len(self.iso) != 10:
                raise ValueError("精度为 day 时 iso 只写日期 YYYY-MM-DD")
            return self
        dt = datetime.fromisoformat(self.iso)
        has_offset = dt.utcoffset() is not None
        if self.tz_source is TimeZoneSource.UNKNOWN:
            if has_offset or self.utc_offset is not None:
                raise ValueError("时区未知时 iso 不能带偏移")
        else:
            if not has_offset or self.utc_offset is None:
                raise ValueError("时区已知或已假设时 iso 必须带偏移，并填写 utc_offset")
            if dt.isoformat()[-6:] != self.utc_offset:
                raise ValueError("iso 的偏移与 utc_offset 不一致")
        return self

    def as_datetime(self) -> datetime | None:
        """返回 datetime；精度为日或无法解析时返回 None。"""
        if self.iso is None or self.precision is TimePrecision.DAY:
            return None
        return datetime.fromisoformat(self.iso)
