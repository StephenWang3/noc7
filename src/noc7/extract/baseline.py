"""保守的本地规则基线：可解释、可复现，不宣称模型准确率。"""

from __future__ import annotations

import re
from datetime import datetime

from ..fuse import normalize
from ..parsers.text import INSTRUCTION
from ..parsers.text.email import split_signature
from ..schema import (
    ATTRIBUTION_LABELS_ZH,
    Attribution,
    CauseCandidate,
    CauseElement,
    CauseKind,
    Event,
    HandlingProcessElement,
    IdentityStatus,
    LocationCandidate,
    LocationElement,
    LocationRole,
    Observation,
    PartyCandidate,
    PhenomenonElement,
    ProcessStep,
    ResponsibilityBasis,
    ResponsiblePartyElement,
    ServiceIdentifier,
    ServiceIdentity,
    SevenElements,
    SpanRole,
    StepKind,
    TimeCandidate,
    TimeElement,
    TimeKind,
    TimeValue,
)
from ..schema import (
    ElementStatus as Status,
)
from ..schema.elements import CAUSE_KINDS_ALLOWED_AS_VALUE
from ..timeparse import parse_time
from .types import QUALITY_REVIEW_THRESHOLD, Extraction, ExtractionContext
from .fact_phrases import responsibility_claims, rfo_fault_points

DATE = r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?"
CLOCK = r"\d{1,2}[:：]\d{2}(?:[:：]\d{2})?"
ZONE_RE = re.compile(
    r"\b(?:GMT|UTC)\b(?:\s*[+-]\s*\d{1,2}(?::?\d{2})?)?|(?:(?<![\w-])|(?<=\d[:：]\d{2}))[+-](?:0\d|1[0-4]):?[0-5]\d(?!\d)|\bZ\b|北京时间|香港时间",
    re.I,
)
TIME_RE = re.compile(
    rf"{DATE}(?:[ T]+{CLOCK})?|(?<![\d:.]){CLOCK}|\{{\{{\s*[\w.]+\s*\}}\}}", re.I
)
CONFIRMATION_TIME_NOTE = "客户确认时刻，仅表示此时已正常，不替代实际恢复时刻。"
METRIC = re.compile(
    r"丢包|时延|告警|中断|不通|宕机|无流量|收光|没有光|没光|packet loss|latency|down|timed? out|not working|RTT",
    re.I,
)
RECOVERY_CONFIRM = re.compile(
    r"客户.{0,15}确认.{0,25}(?:业务恢复|恢复正常|业务正常|线路已正常)|客户来电确认.{0,25}恢复|customer.{0,20}confirm.{0,25}(?:restor|normal)",
    re.I,
)
NEGATED = re.compile(
    r"未确认|没有确认|尚未|未恢复|未能|未查明|未定位|未找到|未发生|排除|并非|not (?:yet )?(?:confirmed|identified|restored)|no evidence",
    re.I,
)
RECOVERY_NEGATED = re.compile(
    r"客户.{0,5}(?:未|没有|尚未).{0,3}确认|未恢复|未确认.{0,6}恢复|not (?:yet )?(?:confirmed|restored)",
    re.I,
)


def confirms_recovery(text: str) -> bool:
    return bool(RECOVERY_CONFIRM.search(text) and not RECOVERY_NEGATED.search(text))


def chart_observation_text(series, unit) -> str:
    return f"{series.series}：max={series.max}，avg={series.avg}，min={series.min} {unit or ''}"


def usable_text(span) -> str:
    if (
        span.role in (SpanRole.SIGNATURE, SpanRole.DERIVED_SUMMARY)
        or span.needs_review
        or (span.quality is not None and span.quality < QUALITY_REVIEW_THRESHOLD)
    ):
        return ""
    text = split_signature(span.text)[0]
    if text.strip().lower() in {
        "无",
        "暂无",
        "未知",
        "待定",
        "未定责",
        "未定",
        "待确认",
        "na",
        "n/a",
        "none",
        "null",
        "-",
        "--",
    }:
        return ""
    return "\n".join(line for line in text.splitlines() if not INSTRUCTION.search(line))


def attribution(span, text: str) -> Attribution:
    key = getattr(span.locator, "field_key", "")
    if key == "description" or re.search(
        r"客户(?:报|反映|反馈|确认|来电)|our customer|our (?:link|router)|we see",
        text,
        re.I,
    ):
        return Attribution.CUSTOMER
    if key in {"alarm_title", "underlying_alarm", "alarm_time", "warning_time"}:
        return Attribution.ALARM_SYSTEM
    if re.search(r"现场(?:确认|反馈|工程师)", text):
        return Attribution.FIELD_ENGINEER
    if re.search(
        r"上游称|供应商|运营商回复|We found|our device|decommissioned|Reason for outage",
        text,
        re.I,
    ):
        return Attribution.VENDOR
    if getattr(span.locator, "type", "") in {"image_region", "page", "doc_block"}:
        return (
            Attribution.MONITORING_CHART
            if span.reading and span.reading.type == "chart"
            else Attribution.FIELD_ENGINEER
        )
    if key:
        return Attribution.SYSTEM_FIELD
    return Attribution.NOC_CHECK


def step_kind(text: str, action: str = "") -> StepKind:
    if re.search(
        r"预计|约定|预约|计划.{0,8}(?:测试|上门)|尚未到达|will |schedule", text, re.I
    ):
        return StepKind.PLANNED
    if re.search(
        r"^(建单|创建工单|受理|转派|返单|结单|撤销|撤单申请|挂起|解挂|索要报告)$",
        action,
    ):
        return StepKind.WORKFLOW
    if re.search(r"熔接|抢修|更换|重启|修复", text):
        return StepKind.TECHNICAL_ACTION
    if re.search(r"检查|检测|查告警|测试|日志|监控|ping|We found|收光", text, re.I):
        return StepKind.CHECK_RESULT
    return StepKind.COMMUNICATION


def cause_kind(text: str, key: str = "") -> CauseKind | None:
    if key == "possible_causes" or re.search(r"^\s*1[.、].*2[.、]", text, re.S):
        return CauseKind.CANDIDATE_LIST_ITEM
    if re.search(
        r"已拆机|非本运营商|不属于本运营商|未交接|decommissioned|disconnected",
        text,
        re.I,
    ):
        return CauseKind.RESOURCE_STATE
    if re.search(r"客户怀疑|疑似|可能(?:是|由)|suspect", text, re.I):
        return CauseKind.CUSTOMER_SUSPICION
    if re.search(r"(?:计划|升级)割接|计划维护", text):
        return (
            CauseKind.PROCESS_BLOCKER
            if re.search(r"预计|预约|将于|尚未|计划于", text)
            else CauseKind.PLANNED_WORK
        )
    if re.search(r"缺.{0,5}联系人|未提供.{0,10}(?:联系人|资料)|等待客户补充", text):
        return CauseKind.PROCESS_BLOCKER
    if re.search(r"自恢|重启后恢复", text):
        return CauseKind.RECOVERY_MODE
    if re.search(r"告警机制|超过.{0,15}(?:阈值|门限)|告警解释", text):
        return CauseKind.ALARM_EXPLANATION
    root = re.search(r"挖断|光缆中断|光纤断裂|cable was damaged|fiber cut", text, re.I)
    if root and not NEGATED.search(text):
        return (
            CauseKind.ROOT_CAUSE_CONFIRMED
            if re.search(r"现场确认|诊断确认|正式报告|责任认定", text)
            else CauseKind.ROOT_CAUSE_CLAIMED
        )
    if key == "cause" or re.search(
        r"无告警|无丢包|未发现倒换|端口流量正常|登录.{0,5}超时|device.{0,20}down",
        text,
        re.I,
    ):
        return CauseKind.INVESTIGATION_FINDING
    return None


def _time_matches(text: str):
    zones = list(ZONE_RE.finditer(text))
    return [
        m
        for m in TIME_RE.finditer(text)
        if not any(z.start() <= m.start() < z.end() for z in zones)
    ]


def _time_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    """分号/句号/换行及相邻时刻构成语义边界，不借用下一时刻的动作。"""
    left, right = 0, len(text)
    for boundary in re.finditer(r"[。；;!?！？\n]|\.(?=\s+[A-Za-z])", text):
        if boundary.end() <= start:
            left = boundary.end()
        elif boundary.start() >= end:
            right = boundary.start()
            break
    for other in _time_matches(text):
        if other.end() <= start:
            left = max(left, other.end())
        elif other.start() >= end:
            right = min(right, other.start())
            break
    return left, right


def _zone_for_time(text: str, start: int, end: int):
    """时区只在当前时间的分句/相邻时刻边界内绑定，后置时区优先。"""
    left, right = _time_bounds(text, start, end)
    zones = list(ZONE_RE.finditer(text, left, right))
    for zone in zones:
        if zone.start() >= end:
            gap = text[end:zone.start()]
            # 裸数字偏移必须紧邻时间（允许空白和括号），不跨旁边的电话号码。
            if zone.group()[0] not in "+-" or re.fullmatch(r"[\s()（）]*", gap):
                return zone
    # 左边界若是上一个时刻的末尾，后面的时区属于它，不能再借给当前时刻。
    if any(other.end() == left for other in _time_matches(text)):
        return None
    for zone in reversed(zones):
        if zone.end() <= start:
            gap = text[zone.end():start]
            if zone.group()[0] not in "+-" or re.fullmatch(r"[\s()（）]*", gap):
                return zone
    return None


def time_phrase(raw: str, offset: str | None, record: str | None = None) -> TimeValue:
    """解析含间隔词的时间短语；归一时去掉间隔词，raw 始终保留原文。"""
    # 与引用核验采用相同的空白口径；原始 raw 与证据位置不改写。
    parse_raw = re.sub(r"\s+", " ", raw)
    direct = parse_time(parse_raw, offset)
    if direct.iso is not None or direct.placeholder:
        return direct.model_copy(update={"raw": raw})
    match = next(iter(_time_matches(parse_raw)), None)
    if not match:
        return TimeValue(raw=raw)
    core = match.group()
    zone = _zone_for_time(parse_raw, match.start(), match.end())
    value = core + (" " + zone.group() if zone else "")
    clock_only = bool(re.fullmatch(CLOCK, core))
    if clock_only and record:
        value = record[:10] + " " + value
    tv = parse_time(value, offset)
    if clock_only and record and tv.as_datetime() and tv.as_datetime().tzinfo:
        anchor = datetime.fromisoformat(record)
        if anchor.tzinfo:
            local_date = anchor.astimezone(tv.as_datetime().tzinfo).date().isoformat()
            tv = parse_time(
                local_date + " " + core + (" " + zone.group() if zone else ""), offset
            )
    return tv.model_copy(update={"raw": raw})


def _time_kind(text: str, start: int, end: int, planned: bool) -> TimeKind:
    left, right = _time_bounds(text, start, end)
    before = text[left:start]
    clause = text[left:right]
    if planned:
        return TimeKind.PLANNED
    if confirms_recovery(clause):
        return TimeKind.CUSTOMER_CONFIRMED_RECOVERY
    if re.search(r"告警清除|恢复 UP", clause, re.I):
        return TimeKind.ALARM_CLEARED
    if re.search(r"熔接完成|修复完成", clause):
        return TimeKind.REPAIR_COMPLETED
    if re.search(r"restored|业务恢复|恢复正常|未见丢包|无丢包|主用正常", clause, re.I):
        return TimeKind.OBSERVATION
    if re.search(r"since|down since|客户.*自", before, re.I):
        return TimeKind.CUSTOMER_REPORTED_START
    positive_alarm = re.sub(
        r"(?:无|没有|未见|未发现)\s*(?:任何|相关)?\s*告警|no alarms?",
        "",
        clause,
        flags=re.I,
    )
    positive_alarm = re.sub(r"查告警[：:]?", "", positive_alarm)
    if re.search(r"告警|LINK DOWN|R_LOS", positive_alarm, re.I):
        return TimeKind.ALARM_RAISED
    return TimeKind.OBSERVATION


def _time_side(kind: TimeKind, text: str) -> str | None:
    """只把有起止语义的时间送入对应要素，其余时间留在原文/事件。"""
    if kind in {
        TimeKind.CUSTOMER_CONFIRMED_RECOVERY,
        TimeKind.ALARM_CLEARED,
        TimeKind.REPAIR_COMPLETED,
    }:
        return "end"
    if kind in {
        TimeKind.CUSTOMER_REPORTED_START,
        TimeKind.ALARM_RAISED,
        TimeKind.BODY_TEXT_DATE,
    }:
        return "start"
    if kind == TimeKind.OBSERVATION:
        if re.search(
            r"restored|恢复|正常|未见丢包|无丢包|(?:无|没有|未见|未发现)告警",
            text,
            re.I,
        ):
            return "end"
        if re.search(r"检测到.*(?:不通|中断)", text):
            return "start"
    return None


def text_times(
    text: str, record: str | None, offset: str | None, planned: bool = False
):
    for m in _time_matches(text):
        left, right = _time_bounds(text, m.start(), m.end())
        zone = _zone_for_time(text, m.start(), m.end())
        start, end = m.start(), m.end()
        if zone:
            start, end = min(start, zone.start()), max(end, zone.end())
            if text[end : end + 1] in {")", "）"}:
                end += 1
        raw = text[start:end].strip()
        default = None if re.search(r"未标注时区|时区未知", text) else offset
        note = (
            "仅有时刻，日期按同条记录/邮件头补齐；跨日需复核。"
            if re.fullmatch(CLOCK, m.group()) and record
            else None
        )
        try:
            tv = time_phrase(raw, default, record)
        except ValueError:
            tv = TimeValue(raw=raw)
        kind = _time_kind(text, m.start(), m.end(), planned)
        clause = text[left:right]
        if kind == TimeKind.CUSTOMER_CONFIRMED_RECOVERY and not re.search(
            r"起.{0,4}(?:业务)?恢复|告警清除|恢复 UP", clause, re.I
        ):
            note = CONFIRMATION_TIME_NOTE
        if tv.iso or tv.placeholder:
            yield tv, kind, note


def conclusion_observations(observations, evidence):
    """原始观测优先；引用独有事实仍保留，重复引用不增加结论证据。"""
    by_id = {s.id: s for s in evidence}
    observations = [o for o in observations if all(r in by_id for r in o.evidence_refs)]

    def key(observation):
        circuits = tuple(
            sorted(set(re.findall(r"\bSYN-CKT-[\w-]+", observation.description)))
        )
        fact = (
            (observation.metric, observation.value, observation.unit, circuits)
            if observation.value is not None
            else normalize(observation.description)
        )
        return observation.attribution, fact

    originals = [
        o
        for o in observations
        if all(
            by_id[r].role != SpanRole.QUOTED and not by_id[r].derived_from
            for r in o.evidence_refs
        )
    ]
    selected = list(originals)
    seen = {key(o) for o in originals}
    for o in observations:
        if any(by_id[r].derived_from for r in o.evidence_refs):
            continue
        if (
            all(by_id[r].role == SpanRole.QUOTED for r in o.evidence_refs)
            and key(o) not in seen
        ):
            selected.append(o)
            seen.add(key(o))
    return selected


def _time_element(candidates, *, end=False, confirmation_refs=()):
    primary = (
        {TimeKind.RECOVERY_FIELD, TimeKind.CUSTOMER_CONFIRMED_RECOVERY}
        if end
        else {TimeKind.FAULT_START_FIELD, TimeKind.CUSTOMER_REPORTED_START}
    )
    viable = [
        c
        for c in candidates
        if c.time_kind in primary
        and c.time.iso
        and not c.time.placeholder
        and c.note != CONFIRMATION_TIME_NOTE
    ]
    if not viable and not end:
        viable = [
            c
            for c in candidates
            if c.time_kind == TimeKind.ALARM_RAISED and c.time.iso and c.note is None
        ]
    values = {c.time.as_datetime() or c.time.iso for c in viable}
    if len(values) > 1:
        return TimeElement(
            status=Status.CONFLICTED,
            candidates=candidates,
            note="时间候选不同，保留原值待核实。",
        )
    if not viable:
        return TimeElement(
            status=Status.UNKNOWN,
            candidates=candidates,
            note="未见可用于结论的恢复依据。" if end else "未提供实际起障时间。",
        )
    c = viable[0]
    confirmed = end and bool(confirmation_refs)
    return TimeElement(
        status=Status.CONFIRMED if confirmed else Status.DOCUMENTED,
        value=c.time,
        selected=c.id,
        candidates=candidates,
        evidence_refs=list(dict.fromkeys(c.evidence_refs + list(confirmation_refs))),
        note="时间取自告警，不能等同客户实际起障。"
        if c.time_kind == TimeKind.ALARM_RAISED
        else None,
    )


def cause_signature(candidate):
    # 只归并明确同义的故障类型；候选原文与来源仍全部保留。
    text = candidate.statement
    if candidate.cause_kind == CauseKind.PLANNED_WORK and "割接" in text:
        return (candidate.cause_kind, "割接")
    if re.search(r"光缆中断|光纤断裂|fiber cut", text, re.I) and not re.search(
        r"施工|挖断|civil works", text, re.I
    ):
        return (candidate.cause_kind, "光缆中断")
    return normalize(text)


def responsibility_basis(text: str, key: str = "", *, trusted: bool = True) -> ResponsibilityBasis | None:
    """定责依据只认明确认定、责任字段或处理角色，与规则抽取使用同一判断。"""
    formal = bool(re.search(r"责任认定[：:]|定责意见[：:]", text))
    if key in {"vendor", "handling_dept", "handler", "responsible_party"} or (trusted and formal):
        if formal:
            return ResponsibilityBasis.FORMAL_DETERMINATION
        if key == "responsible_party":
            return ResponsibilityBasis.CLAIMED
        return ResponsibilityBasis.INFERRED_FROM_ROLE
    if trusted and responsibility_claims(text):
        return ResponsibilityBasis.CLAIMED
    return None


def location_role(text: str, key: str = "", *, trusted: bool = True) -> LocationRole | None:
    """故障点、端点、告警位置和测试节点的角色，与规则抽取使用同一判断。"""
    if key in {"a_end", "z_end"}:
        return LocationRole.SERVICE_ENDPOINT
    if key in {"device_location", "device_name", "shelf_slot_port"}:
        return LocationRole.ALARM_LOCATION
    if re.search(r"现场地址[：:]", text) or re.search(r"[AZ]\s*端接入设备", text):
        return LocationRole.CUSTOMER_SITE
    if (
        trusted
        and re.search(r"现场确认[：:].*(?:处|人井|交叉口)|故障点(?:位于|[：:])", text)
        and not NEGATED.search(text)
    ):
        return LocationRole.LOCATED_FAULT_POINT
    if trusted and rfo_fault_points(text):
        return LocationRole.LOCATED_FAULT_POINT
    if re.search(r"ping|测试节点|PoP 设备|\b(?:\d{1,3}\.){3}\d{1,3}\b", text, re.I):
        return LocationRole.TEST_NODE
    return None


def _text_element(cls, candidates, value_attr, allowed, confirmed=None, signature=None):
    choices = [c for c in candidates if allowed(c)]
    signature = signature or (lambda c: normalize(getattr(c, value_attr)))
    unique = {signature(c) for c in choices}
    if not choices:
        return cls(status=Status.UNKNOWN, candidates=candidates)
    # 同一类别中的多份结论有差异则交给审核；确认过的现场诊断优先于一般陈述。
    direct = [c for c in choices if confirmed and confirmed(c)]
    if direct:
        choices = direct
        unique = {signature(c) for c in choices}
    if len(unique) > 1:
        return cls(status=Status.CONFLICTED, candidates=candidates)
    c = choices[0]
    return cls(
        status=Status.CONFIRMED if direct else Status.DOCUMENTED,
        value=getattr(c, value_attr),
        selected=c.id,
        candidates=candidates,
        evidence_refs=c.evidence_refs,
    )


class RulesProvider:
    name = "rules"

    def extract(self, ctx: ExtractionContext) -> Extraction:
        (
            times_start,
            times_end,
            observations,
            parties,
            causes,
            locations,
            steps,
            events,
        ) = [], [], [], [], [], [], [], []
        confirmations = []
        identifiers = []
        identity_refs = []
        seen_steps = {}
        bundle = ctx.bundle
        offset = bundle.manifest.default_timezone
        field_time = {
            "occurred_at": TimeKind.FAULT_START_FIELD,
            "recovered_at": TimeKind.RECOVERY_FIELD,
            "alarm_time": TimeKind.ALARM_RAISED,
            "warning_time": TimeKind.WARNING_RAISED,
            "created_at": TimeKind.TICKET_CREATED,
            "alarm_cleared_at": TimeKind.ALARM_CLEARED,
        }
        headers = {}
        field_spans = {
            s.locator.field_key: s for s in ctx.evidence if s.locator.type == "field"
        }
        for span in ctx.evidence:
            if getattr(span.locator, "part", "") == "header":
                m = re.search(r"(?im)^(?:Date|Sent|发送时间):\s*(.+)$", span.text)
                if m:
                    headers[(span.material_id, span.locator.message_index)] = (
                        parse_time(m[1], offset).iso
                    )

        def candidate_id(group):
            return f"C{len(group) + 1}"

        for span in ctx.evidence:
            text = usable_text(span)
            if not text:
                continue
            key = getattr(span.locator, "field_key", "")
            part = getattr(span.locator, "part", "")
            if part == "header":
                continue
            attr = attribution(span, text)
            log = (
                bundle.process_log.entry(span.locator.seq)
                if span.locator.type == "log_entry"
                else None
            )
            record = (
                log.recorded_at
                if log
                else headers.get(
                    (span.material_id, getattr(span.locator, "message_index", -1))
                )
            )
            kind = step_kind(text, log.action if log else "")
            trusted_original = span.role != SpanRole.QUOTED
            if trusted_original and not span.derived_from and confirms_recovery(text):
                confirmations.append(span.id)
            if key in field_time:
                tv = parse_time(text, offset)
                tk = field_time[key]
                dest = (
                    times_end
                    if tk in {TimeKind.RECOVERY_FIELD, TimeKind.ALARM_CLEARED}
                    else times_start
                )
                dest.append(
                    TimeCandidate(
                        id=candidate_id(dest),
                        time=tv,
                        time_kind=tk,
                        attribution=attr,
                        evidence_refs=[span.id],
                    )
                )
            elif (
                part != "table"
                and not (span.reading and span.reading.type == "table")
                and key
                not in {
                    "duration_returned",
                    "circuit_id",
                    "ticket_no",
                    "vendor",
                    "customer",
                    "bandwidth",
                }
            ):
                time_cursor = 0
                for tv, tk, note in text_times(
                    text, record, offset, kind == StepKind.PLANNED
                ):
                    if (
                        log
                        and log.entry_kind == "system"
                        and re.search(r"自动建单|检测到", text)
                        and re.match(DATE, tv.raw)
                    ):
                        tk = TimeKind.BODY_TEXT_DATE
                    match = next(iter(_time_matches(tv.raw)), None)
                    source_match = next(
                        (
                            m
                            for m in _time_matches(text)
                            if match
                            and m.start() >= time_cursor
                            and m.group() == match.group()
                        ),
                        None,
                    )
                    left, right = (
                        _time_bounds(text, source_match.start(), source_match.end())
                        if source_match
                        else (0, len(text))
                    )
                    if source_match:
                        time_cursor = source_match.end()
                    side = _time_side(tk, text[left:right])
                    if side is None:
                        continue
                    dest = times_end if side == "end" else times_start
                    refs = [span.id]
                    anchor_key = "occurred_at" if tk == TimeKind.ALARM_RAISED else None
                    anchor = field_spans.get(anchor_key)
                    if note and anchor and re.match(r"^\d{1,2}:\d{2}", tv.raw):
                        at = parse_time(anchor.text, offset)
                        dt = tv.as_datetime()
                        anchor_dt = at.as_datetime()
                        if (
                            dt
                            and anchor_dt
                            and (dt.hour, dt.minute)
                            == (anchor_dt.hour, anchor_dt.minute)
                            and abs(
                                (
                                    dt.replace(tzinfo=None)
                                    - anchor_dt.replace(tzinfo=None)
                                ).total_seconds()
                            )
                            <= 86400
                        ):
                            tv = time_phrase(
                                at.iso[:10] + " " + tv.raw, offset
                            ).model_copy(update={"raw": tv.raw})
                            refs.append(anchor.id)
                            note = "原文只有时刻；日期与同单对应起止字段对齐，保留两处依据。"
                    dest.append(
                        TimeCandidate(
                            id=candidate_id(dest),
                            time=tv,
                            time_kind=tk,
                            attribution=attr,
                            evidence_refs=refs,
                            note=note,
                        )
                    )
            if log:
                workflow_times = {
                    "建单": TimeKind.TICKET_CREATED,
                    "创建工单": TimeKind.TICKET_CREATED,
                    "返单": TimeKind.TICKET_RETURNED,
                    "结单": TimeKind.TICKET_CLOSED,
                    "撤销": TimeKind.TICKET_CANCELLED,
                }
                if "同意结单" in text:
                    workflow_times[log.action] = TimeKind.TICKET_CLOSED
                if log.action in workflow_times and record:
                    dest = (
                        times_end
                        if workflow_times[log.action]
                        in {
                            TimeKind.TICKET_CLOSED,
                            TimeKind.TICKET_RETURNED,
                            TimeKind.TICKET_CANCELLED,
                        }
                        else times_start
                    )
                    dest.append(
                        TimeCandidate(
                            id=candidate_id(dest),
                            time=parse_time(record, offset),
                            time_kind=workflow_times[log.action],
                            attribution=Attribution.SYSTEM_FIELD,
                            evidence_refs=[span.id],
                        )
                    )
                dup = seen_steps.get(normalize(text))
                ev_id = f"EV{len(events) + 1}"
                step_id = f"P{len(steps) + 1}"
                time = parse_time(record, offset) if record else None
                step = ProcessStep(
                    id=step_id,
                    time=time,
                    actor=log.actor,
                    action=text,
                    step_kind=kind,
                    attribution=attr,
                    evidence_refs=[span.id],
                    duplicate_of=dup[0] if dup else None,
                )
                steps.append(step)
                events.append(
                    Event(
                        id=ev_id,
                        time=time,
                        time_kind=TimeKind.RECORD_TIME,
                        actor=log.actor,
                        attribution=attr,
                        action=text,
                        event_kind=kind,
                        evidence_refs=[span.id],
                        duplicate_of=dup[1] if dup else None,
                    )
                )
                seen_steps.setdefault(normalize(text), (step_id, ev_id))
            # 非字段原文（含 A2 页面、图片读数）也进入事件时间线。
            elif not key and trusted_original and not span.derived_from:
                events.append(
                    Event(
                        id=f"EV{len(events) + 1}",
                        attribution=attr,
                        action=text,
                        event_kind=kind,
                        evidence_refs=[span.id],
                    )
                )
            if key in {"description", "alarm_title", "underlying_alarm"} or (
                not key
                and METRIC.search(text)
                and not re.search(r"责任认定[：:]|定责意见[：:]", text)
            ):
                metric = (
                    "丢包率"
                    if re.search(r"丢包|packet loss", text, re.I)
                    else "时延"
                    if re.search(r"时延|RTT|latency", text, re.I)
                    else "告警/状态"
                )
                nums = re.search(r"(\d+(?:\.\d+)?)\s*(%|ms|毫秒)", text, re.I)
                observations.append(
                    Observation(
                        id=candidate_id(observations),
                        description=text,
                        attribution=attr,
                        metric=metric,
                        value=float(nums[1]) if nums else None,
                        unit=nums[2] if nums else None,
                        scope=text,
                        evidence_refs=[span.id],
                    )
                )
            if span.reading and span.reading.type == "chart":
                for series in span.reading.series:
                    observations.append(
                        Observation(
                            id=candidate_id(observations),
                            description=chart_observation_text(
                                series, span.reading.unit
                            ),
                            attribution=Attribution.MONITORING_CHART,
                            metric=span.reading.metric,
                            value=series.max,
                            unit=span.reading.unit,
                            scope=series.series,
                            evidence_refs=[span.id],
                        )
                    )
                    if series.first_nonzero:
                        times_start.append(
                            TimeCandidate(
                                id=candidate_id(times_start),
                                time=parse_time(series.first_nonzero, None),
                                time_kind=TimeKind.CHART_FIRST_NONZERO,
                                attribution=Attribution.MONITORING_CHART,
                                evidence_refs=[span.id],
                                note="首次非零仅是观测点。",
                            )
                        )
            ck = cause_kind(text, key)
            if ck and trusted_original:
                causes.append(
                    CauseCandidate(
                        id=candidate_id(causes),
                        statement=text,
                        cause_kind=ck,
                        attribution=attr,
                        evidence_refs=[span.id],
                    )
                )
            basis = responsibility_basis(text, key, trusted=trusted_original)
            if basis:
                party_values = responsibility_claims(text) if basis == ResponsibilityBasis.CLAIMED and key != "responsible_party" else []
                for party_value in dict.fromkeys(party_values or [text]):
                    parties.append(PartyCandidate(
                        id=candidate_id(parties),
                        party=party_value,
                        basis=basis,
                        attribution=attr,
                        evidence_refs=[span.id],
                    ))
            lr = location_role(text, key, trusted=trusted_original)
            if lr:
                location_values = rfo_fault_points(text) if lr == LocationRole.LOCATED_FAULT_POINT else []
                for location_value in dict.fromkeys(location_values or [text]):
                    locations.append(LocationCandidate(
                        id=candidate_id(locations),
                        description=location_value,
                        role=lr,
                        attribution=attr,
                        evidence_refs=[span.id],
                    ))
            if key == "circuit_id":
                identifiers.append(
                    ServiceIdentifier(
                        value=text, role="reported", evidence_refs=[span.id]
                    )
                )
            if re.search(
                r"新编号|旧编号|旧CID|新CID|未交接|已拆机|报错.{0,4}运营商|非本运营商|不属于本运营商|decommissioned|Old CID",
                text,
                re.I,
            ):
                identity_refs.append(span.id)
                for ident in re.findall(r"\b(?:SYN-)?(?:CKT|CID)-[\w-]+", text, re.I):
                    identifiers.append(
                        ServiceIdentifier(
                            value=ident,
                            role="other",
                            evidence_refs=[span.id],
                            note="编号角色与映射待核实。",
                        )
                    )
        start = _time_element(times_start)
        end = _time_element(times_end, end=True, confirmation_refs=confirmations)
        cause = _text_element(
            CauseElement,
            causes,
            "statement",
            lambda c: c.cause_kind in CAUSE_KINDS_ALLOWED_AS_VALUE,
            lambda c: c.cause_kind == CauseKind.ROOT_CAUSE_CONFIRMED,
            signature=cause_signature,
        )
        party = _text_element(
            ResponsiblePartyElement,
            parties,
            "party",
            lambda c: c.basis != ResponsibilityBasis.INFERRED_FROM_ROLE,
            lambda c: c.basis == ResponsibilityBasis.FORMAL_DETERMINATION,
        )
        location = _text_element(
            LocationElement,
            locations,
            "description",
            lambda c: c.role == LocationRole.LOCATED_FAULT_POINT,
        )
        actual_steps = [s for s in steps if not s.duplicate_of]
        actual_steps.sort(key=lambda s: s.time.iso if s.time and s.time.iso else "")
        selected_observations = conclusion_observations(observations, ctx.evidence)
        phenomenon = PhenomenonElement(
            status=Status.DOCUMENTED if selected_observations else Status.UNKNOWN,
            value="；".join(
                f"{ATTRIBUTION_LABELS_ZH[o.attribution]}：{o.description}"
                for o in selected_observations
            )
            if selected_observations
            else None,
            candidates=observations,
            evidence_refs=list(
                dict.fromkeys(r for o in selected_observations for r in o.evidence_refs)
            ),
        )
        handling = HandlingProcessElement(
            status=Status.DOCUMENTED if actual_steps else Status.UNKNOWN,
            value=actual_steps,
            evidence_refs=[r for s in actual_steps for r in s.evidence_refs],
        )
        identity = ServiceIdentity(
            status=IdentityStatus.UNVERIFIED,
            identifiers=identifiers,
            note="存在编号、归属或资源状态问题，需核实。"
            if identity_refs
            else "服务身份尚未经独立核实。",
        )
        return Extraction(
            elements=SevenElements(
                start_time=start,
                end_time=end,
                phenomenon=phenomenon,
                responsible_party=party,
                cause=cause,
                handling_process=handling,
                location=location,
            ),
            events=events,
            service_identity=identity,
        )
