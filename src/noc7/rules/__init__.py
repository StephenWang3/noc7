"""确定性规则：独立于抽取提供方运行，不读取标准答案。"""

from __future__ import annotations

import re

from ..extract.baseline import (
    cause_kind,
    chart_observation_text,
    conclusion_observations,
    confirms_recovery,
    time_phrase,
    usable_text,
)
from ..extract.types import QUALITY_REVIEW_THRESHOLD, Extraction, ExtractionContext
from ..parsers.text import INSTRUCTION
from ..schema import (
    ATTRIBUTION_LABELS_ZH,
    DEFAULT_SEVERITY,
    Attribution,
    CauseKind,
    ElementName,
    ElementStatus,
    IssueCode,
    SpanRole,
    TimeKind,
    TimeZoneSource,
    ValidationIssue,
)

VERSION = "1.1"


def issue(code: IssueCode, message: str, refs=(), element=None) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=DEFAULT_SEVERITY[code],
        message=message,
        evidence_refs=list(dict.fromkeys(refs)),
        element=element,
        rule_id=f"r.{code.value.lower()}@1",
    )


class ExtractionRejected(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("；".join(i.message for i in issues))


def validate_extraction(ctx: ExtractionContext, data: Extraction) -> None:
    """不可信提供方先过证据校验；失败整份拒绝，不渲染带错引用的报告。"""
    spans = {s.id: s for s in ctx.evidence}
    refs = list(data.elements.iter_evidence_refs())
    refs += [r for ev in data.events for r in ev.evidence_refs]
    if data.service_identity:
        refs += [r for i in data.service_identity.identifiers for r in i.evidence_refs]
    refs += [q.evidence_id for q in data.quotes]
    errors = []
    missing = sorted(set(refs) - spans.keys())
    if missing:
        errors.append(
            issue(
                IssueCode.EVIDENCE_REF_MISSING,
                f"抽取结果引用不存在的证据：{', '.join(missing)}",
            )
        )
    for q in data.quotes:
        if q.evidence_id in spans and q.quote not in spans[q.evidence_id].text:
            errors.append(
                issue(
                    IssueCode.EVIDENCE_QUOTE_MISMATCH,
                    "抽取引用的原文与证据不符。",
                    [q.evidence_id],
                )
            )
    for event in data.events:
        supporting = [spans[r] for r in event.evidence_refs if r in spans]
        if supporting and not any(
            event.action in s.text or event.action == usable_text(s) for s in supporting
        ):
            errors.append(
                issue(
                    IssueCode.EVIDENCE_QUOTE_MISMATCH,
                    "事件动作不在引用的证据中。",
                    event.evidence_refs,
                )
            )
    for name, el in data.elements.items():
        if el.review:
            raise ValueError("抽取提供方不能提交人工审核记录。")
        for candidate in el.iter_candidates():
            text = next(
                (
                    getattr(candidate, k)
                    for k in ("statement", "party", "description", "action")
                    if hasattr(candidate, k)
                ),
                None,
            )
            supporting = [spans[r] for r in candidate.evidence_refs if r in spans]

            def supported(s):
                if text in s.text or text == usable_text(s):
                    return True
                if (
                    s.reading
                    and s.reading.type == "chart"
                    and hasattr(candidate, "metric")
                ):
                    return any(
                        text == chart_observation_text(series, s.reading.unit)
                        and candidate.scope == series.series
                        and candidate.value == series.max
                        and candidate.unit == s.reading.unit
                        and candidate.metric == s.reading.metric
                        for series in s.reading.series
                    )
                return False

            if text and supporting and not any(supported(s) for s in supporting):
                errors.append(
                    issue(
                        IssueCode.EVIDENCE_QUOTE_MISMATCH,
                        "候选文本不在引用的证据中。",
                        candidate.evidence_refs,
                        name,
                    )
                )
            if hasattr(candidate, "time_kind"):
                raw = candidate.time.raw
                metadata = []
                for s in supporting:
                    if (
                        s.reading
                        and s.reading.type == "chart"
                        and candidate.time_kind == TimeKind.CHART_FIRST_NONZERO
                    ):
                        metadata.extend(
                            series.first_nonzero
                            for series in s.reading.series
                            if series.first_nonzero
                        )
                    if s.locator.type == "log_entry":
                        entry = ctx.bundle.process_log.entry(s.locator.seq)
                        if entry and entry.recorded_at:
                            metadata.append(entry.recorded_at)
                if (
                    raw
                    and supporting
                    and not any(raw in s.text for s in supporting)
                    and raw not in metadata
                ):
                    errors.append(
                        issue(
                            IssueCode.EVIDENCE_QUOTE_MISMATCH,
                            "时间原文不在证据或记录元数据中。",
                            candidate.evidence_refs,
                            name,
                        )
                    )
                # 完整日期可直接复算；裸时刻需要日期锚点，由抽取器保留补齐说明。
                if re.match(r"^(?:北京时间\s*)?\d{4}[-/.年]", raw):
                    offset = (
                        None
                        if candidate.time.tz_source == TimeZoneSource.UNKNOWN
                        else ctx.bundle.manifest.default_timezone
                    )
                    expected = time_phrase(raw, offset)
                    if expected.iso != candidate.time.iso:
                        errors.append(
                            issue(
                                IssueCode.EVIDENCE_QUOTE_MISMATCH,
                                "时间归一值与原文不一致。",
                                candidate.evidence_refs,
                                name,
                            )
                        )
        if el.status not in {ElementStatus.DOCUMENTED, ElementStatus.CONFIRMED}:
            continue
        support = [spans[r] for r in el.evidence_refs if r in spans]
        if support and all(
            s.role in {SpanRole.SIGNATURE, SpanRole.DERIVED_SUMMARY} or s.needs_review
            for s in support
        ):
            errors.append(
                issue(
                    IssueCode.EVIDENCE_QUOTE_MISMATCH,
                    "结论只有签名、摘要或待复核材料，缺少原始依据。",
                    el.evidence_refs,
                    name,
                )
            )
        selected = getattr(el, "selected", None)
        if name in {
            ElementName.CAUSE,
            ElementName.LOCATION,
            ElementName.RESPONSIBLE_PARTY,
            ElementName.START_TIME,
            ElementName.END_TIME,
        }:
            chosen = next((c for c in el.iter_candidates() if c.id == selected), None)
            if chosen is None:
                errors.append(
                    issue(
                        IssueCode.EVIDENCE_QUOTE_MISMATCH,
                        "有值的结论必须选中一个有依据的候选。",
                        el.evidence_refs,
                        name,
                    )
                )
            elif getattr(el, "value") != next(
                (
                    getattr(chosen, k)
                    for k in ("time", "statement", "party", "description")
                    if hasattr(chosen, k)
                ),
                None,
            ):
                errors.append(
                    issue(
                        IssueCode.EVIDENCE_QUOTE_MISMATCH,
                        "结论与选中的候选不一致。",
                        el.evidence_refs,
                        name,
                    )
                )
            elif name == ElementName.CAUSE:
                semantic = cause_kind(chosen.statement)
                if semantic and semantic not in {
                    CauseKind.ROOT_CAUSE_CONFIRMED,
                    CauseKind.ROOT_CAUSE_CLAIMED,
                    CauseKind.PLANNED_WORK,
                }:
                    errors.append(
                        issue(
                            IssueCode.CAUSE_NOT_DIAGNOSIS,
                            "原文是排查结论、资源状态或候选清单，不能作为根因。",
                            el.evidence_refs,
                            name,
                        )
                    )
            elif name == ElementName.LOCATION:
                if all(
                    s.locator.type == "field"
                    and s.locator.field_key
                    in {
                        "a_end",
                        "z_end",
                        "device_location",
                        "device_name",
                        "region",
                        "shelf_slot_port",
                    }
                    for s in support
                ):
                    errors.append(
                        issue(
                            IssueCode.LOCATION_NOT_LOCATED,
                            "地址或告警位置不能自动变成故障点。",
                            el.evidence_refs,
                            name,
                        )
                    )
            elif name == ElementName.RESPONSIBLE_PARTY:
                if all(
                    s.locator.type == "field"
                    and s.locator.field_key in {"vendor", "handler", "handling_dept"}
                    for s in support
                ):
                    errors.append(
                        issue(
                            IssueCode.RESPONSIBILITY_NO_BASIS,
                            "供应商或处理部门不能自动变成责任方。",
                            el.evidence_refs,
                            name,
                        )
                    )
            elif name in {ElementName.START_TIME, ElementName.END_TIME}:
                if chosen.time_kind in {
                    TimeKind.TICKET_CREATED,
                    TimeKind.TICKET_CLOSED,
                    TimeKind.TICKET_RETURNED,
                    TimeKind.PLANNED,
                    TimeKind.RECORD_TIME,
                }:
                    errors.append(
                        issue(
                            IssueCode.TIME_CANDIDATES_DIFFER,
                            "流程或计划时间不能作为实际起障/恢复结论。",
                            el.evidence_refs,
                            name,
                        )
                    )
        if name == ElementName.END_TIME and el.status == ElementStatus.CONFIRMED:
            if not any(
                confirms_recovery(usable_text(s)) and s.role != SpanRole.QUOTED
                for s in support
            ):
                errors.append(
                    issue(
                        IssueCode.RECOVERY_UNVERIFIED,
                        "确认恢复的结论缺少客户确认依据。",
                        el.evidence_refs,
                        name,
                    )
                )
        if name == ElementName.PHENOMENON:
            selected_observations = conclusion_observations(el.candidates, ctx.evidence)
            grounded = "；".join(
                f"{ATTRIBUTION_LABELS_ZH[c.attribution]}：{c.description}"
                for c in selected_observations
            )
            expected_refs = {r for c in selected_observations for r in c.evidence_refs}
            if el.value != grounded or set(el.evidence_refs) != expected_refs:
                errors.append(
                    issue(
                        IssueCode.EVIDENCE_QUOTE_MISMATCH,
                        "现象概述必须由带来源的观测原文组成。",
                        el.evidence_refs,
                        name,
                    )
                )
    if errors:
        raise ExtractionRejected(errors)


def observation_scope_conflicts(observations):
    """只有同指标的相反检查结果/不同范围读数才提示，来源不同本身不是冲突。"""
    customers = [o for o in observations if o.attribution == Attribution.CUSTOMER]
    network = [
        o
        for o in observations
        if o.attribution in {Attribution.NOC_CHECK, Attribution.ALARM_SYSTEM}
    ]
    pairs = []
    for customer in customers:
        for check in network:
            if customer.metric != check.metric:
                continue
            customer_loss = (
                customer.metric == "丢包率"
                and (customer.value is None or customer.value > 0)
                and not re.search(
                    r"无丢包|未见丢包|no packet loss", customer.description, re.I
                )
            )
            network_no_loss = re.search(
                r"无丢包|未见丢包|100 发 100 收|no packet loss", check.description, re.I
            ) or (check.value == 0 and check.unit == "%")
            latency_differs = (
                customer.metric == "时延"
                and customer.unit == check.unit
                and customer.value is not None
                and check.value is not None
                and customer.value != check.value
                and customer.scope != check.scope
            )
            if (customer_loss and network_no_loss) or latency_differs:
                pairs.append((customer, check))
    return pairs


def check(ctx: ExtractionContext, data: Extraction) -> list[ValidationIssue]:
    b, elements = ctx.bundle, data.elements
    spans = ctx.evidence
    out = []

    def add(code, message, refs=(), element=None):
        out.append(issue(code, message, refs, element))

    original = [
        s
        for s in spans
        if usable_text(s)
        and s.role
        not in {SpanRole.DERIVED_SUMMARY, SpanRole.QUOTED, SpanRole.SIGNATURE}
    ]
    fields = {
        getattr(s.locator, "field_key", ""): s
        for s in spans
        if s.locator.type == "field"
    }
    # 比较字段原值，即使最终结束时间有冲突，也不能把负数掩盖掉。
    starts = [
        c
        for c in elements.start_time.candidates
        if c.time_kind == TimeKind.FAULT_START_FIELD
    ]
    ends = [
        c
        for c in elements.end_time.candidates
        if c.time_kind == TimeKind.RECOVERY_FIELD
    ]
    field_minutes = None
    if starts and ends:
        start, end = starts[0].time.as_datetime(), ends[0].time.as_datetime()
        if start and end and (start.utcoffset() is None) == (end.utcoffset() is None):
            field_minutes = (end - start).total_seconds() / 60
            if field_minutes < 0:
                refs = starts[0].evidence_refs + ends[0].evidence_refs
                add(
                    IssueCode.TIME_ORDER_INVERTED,
                    "系统恢复字段早于发生字段，保留原值待核实。",
                    refs,
                    ElementName.END_TIME,
                )
                add(
                    IssueCode.NEGATIVE_DURATION,
                    "系统起止字段差为负，不能生成有效故障历时。",
                    refs,
                    ElementName.END_TIME,
                )
    duration = fields.get("duration_returned")
    if duration:
        m = re.fullmatch(
            r"\s*(-?\d+(?:\.\d+)?)\s*(分钟|min|小时|h)\s*", duration.text, re.I
        )
        if m:
            minutes = float(m[1]) * (60 if m[2].lower() in {"小时", "h"} else 1)
            if minutes < 0:
                add(
                    IssueCode.NEGATIVE_DURATION,
                    "返单历时为负，需核对原始口径。",
                    [duration.id],
                )
            if field_minutes is not None and abs(minutes - field_minutes) > 1:
                add(
                    IssueCode.DURATION_BASIS_MISMATCH,
                    f"返单历时 {minutes:g} 分钟与系统字段差 {field_minutes:g} 分钟不同，不能混用口径。",
                    [duration.id],
                )
    for name in (ElementName.START_TIME, ElementName.END_TIME):
        el = getattr(elements, name.value)
        parsed = [
            c
            for c in el.candidates
            if c.time.iso
            and c.time_kind
            not in {TimeKind.PLANNED, TimeKind.RECORD_TIME, TimeKind.MESSAGE_SENT}
        ]
        values = {c.time.as_datetime() or c.time.iso for c in parsed}
        if len(values) > 1:
            add(
                IssueCode.TIME_CANDIDATES_DIFFER,
                "时间候选有不同语义或数值；建单、告警、关单时间不能替代起障/恢复。",
                [r for c in parsed for r in c.evidence_refs],
                name,
            )
        for c in el.candidates:
            if c.time.placeholder:
                add(
                    IssueCode.TIME_PLACEHOLDER,
                    "原文含未替换的时间占位符，不作为时间结论。",
                    c.evidence_refs,
                    name,
                )
            if (
                c.time.iso
                and c.time.tz_source == TimeZoneSource.UNKNOWN
                and c.time.as_datetime()
            ):
                add(
                    IssueCode.TIME_TZ_MISSING,
                    "设备或材料记录没有时区，保留墙上时间，不按地点猜测。",
                    c.evidence_refs,
                    name,
                )
    for s in original:
        if "{{" in s.text and "}}" in s.text:
            add(IssueCode.TIME_PLACEHOLDER, "材料包含未替换的模板占位符。", [s.id])
        if s.locator.type == "log_entry":
            entry = b.process_log.entry(s.locator.seq)
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", s.text)
            # 仅自动建单正文的事件日期与记录日比较；预约、历史日期不是复制错误。
            if (
                entry
                and entry.recorded_at
                and entry.entry_kind == "system"
                and re.search(r"自动建单|检测到", s.text)
            ):
                if any(d != entry.recorded_at[:10] for d in dates):
                    add(
                        IssueCode.TIME_BODY_RECORD_MISMATCH,
                        "自动建单正文日期与系统记录日期不一致，两者均保留。",
                        [s.id],
                        ElementName.START_TIME,
                    )
    cancelled = bool(re.search(r"撤销|作废", b.ticket.status.detail_status or ""))
    if cancelled:
        add(
            IssueCode.TICKET_CANCELLED,
            "本单已撤销/作废，不作为有效故障结案，不计算历时。",
        )
    if elements.end_time.value is None:
        add(
            IssueCode.ONGOING_NO_END,
            "未获得无冲突的恢复时间，不计算最终历时。",
            element=ElementName.END_TIME,
        )
    elif elements.end_time.status != ElementStatus.CONFIRMED:
        add(
            IssueCode.RECOVERY_UNVERIFIED,
            "仅有系统恢复记载，未见客户恢复确认；同意结单不等于确认恢复。",
            elements.end_time.evidence_refs,
            ElementName.END_TIME,
        )
    findings = [
        c
        for c in elements.cause.candidates
        if c.cause_kind
        not in {
            CauseKind.ROOT_CAUSE_CONFIRMED,
            CauseKind.ROOT_CAUSE_CLAIMED,
            CauseKind.PLANNED_WORK,
        }
    ]
    if any(c.cause_kind == CauseKind.CANDIDATE_LIST_ITEM for c in findings):
        add(
            IssueCode.CAUSE_CANDIDATE_LIST,
            "原因是可能原因清单，不能确认哪项发生。",
            [
                r
                for c in findings
                if c.cause_kind == CauseKind.CANDIDATE_LIST_ITEM
                for r in c.evidence_refs
            ],
            ElementName.CAUSE,
        )
    if any(c.cause_kind != CauseKind.CANDIDATE_LIST_ITEM for c in findings):
        add(
            IssueCode.CAUSE_NOT_DIAGNOSIS,
            "排查结论、恢复方式和资源状态保留为候选，不能当作根因。",
            [r for c in findings for r in c.evidence_refs],
            ElementName.CAUSE,
        )
    if elements.responsible_party.value is None:
        add(
            IssueCode.RESPONSIBILITY_NO_BASIS,
            "未见明确责任认定，不按供应商或处理部门补齐。",
            [r for c in elements.responsible_party.candidates for r in c.evidence_refs],
            ElementName.RESPONSIBLE_PARTY,
        )
    limited = [
        s.id
        for s in original
        if re.search(r"无告警|无丢包|未见丢包|流量正常|100 发 100 收", s.text)
    ]
    if limited and elements.end_time.status != ElementStatus.CONFIRMED:
        add(
            IssueCode.RECOVERY_SCOPE_LIMITED,
            "检查范围内正常不能替代业务恢复确认。",
            limited,
            ElementName.END_TIME,
        )
    obs = conclusion_observations(elements.phenomenon.candidates, ctx.evidence)
    conflicting_observations = observation_scope_conflicts(obs)
    if conflicting_observations:
        add(
            IssueCode.OBSERVATION_SCOPE_DIFFERS,
            "客户感知与网管观测来源、时刻或范围不同，分别保留。",
            [
                r
                for pair in conflicting_observations
                for o in pair
                for r in o.evidence_refs
            ],
            ElementName.PHENOMENON,
        )
    if elements.location.value is None:
        add(
            IssueCode.LOCATION_NOT_LOCATED,
            "未定位实际故障点，业务端点、告警位置和测试节点只作候选。",
            [r for c in elements.location.candidates for r in c.evidence_refs],
            ElementName.LOCATION,
        )
    identity_refs = [
        s.id
        for s in original
        if re.search(
            r"新编号|旧编号|旧CID|新CID|未交接|已拆机|报错.{0,4}运营商|非本运营商|不属于本运营商|decommissioned|Old CID",
            s.text,
            re.I,
        )
    ]
    if identity_refs:
        add(
            IssueCode.SERVICE_IDENTITY_UNVERIFIED,
            "新旧服务编号、资源状态或归属待核实，不能作为本次故障原因。",
            identity_refs,
        )
    for relation in b.ticket.related_tickets:
        if relation.relation == "shared_alarm":
            add(
                IssueCode.RELATED_TICKET_SHARED_SOURCE,
                f"关联 {relation.ticket_ref}（{relation.status or '状态未知'}）共用告警，不增加独立证据。",
            )
        if relation.relation == "reopened_from":
            add(
                IssueCode.RELATED_TICKET_REOPENED,
                f"由历史单 {relation.ticket_ref}（{relation.status or '状态未知'}）重开，旧单关单不代表本单恢复。",
            )
        if re.search(r"作废|撤销|重复", relation.status or ""):
            add(
                IssueCode.RELATED_TICKET_INVALID,
                f"关联 {relation.ticket_ref} 状态为 {relation.status}，不自动合并结论。",
            )
    status = b.ticket.status
    if (
        status.list_status
        and status.detail_status
        and status.list_status != status.detail_status
    ):
        add(
            IssueCode.STATUS_VIEW_MISMATCH,
            f"列表状态“{status.list_status}”与详情状态“{status.detail_status}”不同。",
        )
    for s in spans:
        if s.role in {SpanRole.DERIVED_SUMMARY, SpanRole.QUOTED}:
            add(
                IssueCode.DERIVED_SOURCE_DUPLICATE,
                "摘要/邮件引用为衍生来源，不作为新增独立佐证。",
                [s.id] + s.derived_from,
            )
        elif s.derived_from:
            add(
                IssueCode.DUPLICATE_CONTENT,
                "重复内容已保留来源关系，处理时间线不重复计入。",
                [s.id] + s.derived_from,
            )
        if s.needs_review or (
            s.quality is not None and s.quality < QUALITY_REVIEW_THRESHOLD
        ):
            add(
                IssueCode.MATERIAL_LOW_QUALITY, "材料质量不足，读数需人工复核。", [s.id]
            )
        if INSTRUCTION.search(s.text):
            add(
                IssueCode.EMBEDDED_INSTRUCTION,
                "材料中的指令仅作数据保留，不执行。",
                [s.id],
            )
    return out
