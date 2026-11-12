"""两段式提供方：全部用本地桩服务和合成工单，不请求真实模型。"""
import json

import pytest

from noc7.extract.pipeline import analyze_with_context
from noc7.providers import facts, narrative
from noc7.providers.text_config import TextProviderError
from noc7.providers.two_stage import TwoStageTextProvider
from noc7.report.company import build_company_report
from noc7.schema import AnalysisResult
from tests.a1.conftest import text_registry

from .conftest import BUNDLES, envelope, qwen_config

FACTS = {"facts": [
    {"type": "phenomenon", "evidence_id": "M01/f:description", "quote": "客户报专线 SYN-CKT-1024 业务中断。"},
    {"type": "step", "evidence_id": "M02/log:3", "quote": "OTDR 测试显示断点距 A 端局站约 3.2 km。"},
    {"type": "step", "evidence_id": "M02/log:4", "quote": "派线路维护部现场抢修。"},
    {"type": "step", "evidence_id": "M02/log:6", "quote": "18:55 熔接完成。", "time": "18:55"},
    {"type": "step", "evidence_id": "M02/log:7", "quote": "19:15 客户电话确认业务正常。"},
    {"type": "cause", "evidence_id": "M02/log:5", "quote": "市政道路施工挖断 24 芯光缆", "source": "branch_log",
     "certainty": "asserted"},
    {"type": "cause", "evidence_id": "M02/log:3", "quote": "所在光缆段 R_LOS", "source": "noc", "certainty": "suspected"},
    {"type": "recovery_time", "evidence_id": "M02/log:7", "quote": "19:08 告警清除，业务恢复", "time": "19:08",
     "source": "unicom_log"},
    # 以下两条对不上原文，只应丢弃这两条。
    {"type": "cause", "evidence_id": "M02/log:5", "quote": "设备板卡故障", "source": "rfo", "certainty": "asserted"},
    {"type": "step", "evidence_id": "M09/log:1", "quote": "派线路维护部现场抢修。"},
]}
WRITING = {
    "phenomenon": "中断",
    "process": [
        {"refs": ["S1", "S2"], "text": "INOC 经 OTDR 测试定位断点，派线路维护部现场抢修。"},
        {"refs": ["S3"], "text": "现场于 17:30 完成熔接。"},  # 17:30 不在事实里，应退回原文
        {"refs": ["S4"], "text": "客户确认业务正常。"},
        {"refs": ["S99"], "text": "凭空的一行。"},
    ],
    "cause": "市政道路施工挖断 24 芯光缆。",
}


def run(server, replies, bundle="SYN-P04"):
    server.replies.extend((200, {}, envelope(r)) if isinstance(r, dict) else r for r in replies)
    provider = TwoStageTextProvider(qwen_config(server))
    result, _, extraction = analyze_with_context(BUNDLES / bundle, provider, registry=text_registry())
    return result, extraction


def cell(result, key):
    return ["".join(p.text for p in line) for line in build_company_report(result).cells[key]]


def test_two_requests_and_item_level_drop(server):
    result, extraction = run(server, [FACTS, WRITING])
    assert len(server.requests) == 2
    assert "facts" in json.loads(server.requests[1]["body"]["messages"][1]["content"])
    dropped = result.semantic_assessment.original["facts_dropped"]
    assert [d["reason"] for d in dropped] == ["引文不在证据原文中", "证据编号不存在或不可用"]
    statements = [c.statement for c in result.elements.cause.candidates]
    # 模型摘到的原因在前，工单结单原因字段作最后一层兜底。
    assert statements[:2] == ["市政道路施工挖断 24 芯光缆", "所在光缆段 R_LOS"]
    assert [c.id for c in result.elements.cause.candidates][2:] == ["CSYS1"]
    assert result.elements.cause.value == "市政道路施工挖断 24 芯光缆" and result.elements.cause.note is None
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result


def run_passes(server, replies, passes=2):
    server.replies.extend((200, {}, envelope(r)) if isinstance(r, dict) else r for r in replies)
    provider = TwoStageTextProvider(qwen_config(server, fact_passes=passes))
    return analyze_with_context(BUNDLES / "SYN-P04", provider, registry=text_registry())


NO_RECOVERY = {"facts": [f for f in FACTS["facts"] if f["type"] != "recovery_time"]}


def test_system_fields_fill_times_when_business_sources_are_unusable(server):
    result, _ = run(server, [NO_RECOVERY, WRITING])
    e = result.elements
    assert e.start_time.value.raw == "2026-10-10 15:42:00"
    # 原文没有恢复时刻：取系统恢复字段并标注。
    assert e.end_time.value.raw == "2026-10-10 19:08:00"
    record = result.semantic_assessment.recovery_selection
    assert record.sources[record.selected] == "system_field"
    assert "系统恢复字段（兜底，待核实）" in cell(result, "resumed")[1]
    assert cell(result, "duration") == ["约 206 分钟【待核实：恢复未确认】"]


def test_log_time_without_date_takes_the_log_record_date(server):
    result, _ = run(server, [FACTS, WRITING])
    end = result.elements.end_time
    # 日志 7 记于 2026-10-10 19:16:31，正文只写“19:08”。
    assert end.value.raw == "19:08" and end.value.iso.startswith("2026-10-10T19:08")
    record = result.semantic_assessment.recovery_selection
    assert record.sources[record.selected] == "unicom_monitor"
    assert "【日期按日志记录时间推定】" in cell(result, "resumed")[0]
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result


def test_customer_start_not_earlier_than_system_field_changes_nothing(server):
    start = {"type": "start_time", "evidence_id": "M02/log:3", "quote": "查告警：15:42 起 SYN-CKT-1024 所在光缆段 R_LOS",
             "time": "15:42", "kind": "customer_reported"}
    result, _ = run(server, [{"facts": [*FACTS["facts"], start]}, WRITING])
    assert result.elements.start_time.selected == "SYS1"


def test_second_pass_adds_missed_facts_without_duplicating_steps(server):
    party = {"type": "responsibility", "evidence_id": "M02/log:5", "quote": "市政道路施工挖断 24 芯光缆", "party": "供应商",
             "source": "branch_log", "third_party": True}
    second = {"facts": [*FACTS["facts"][:8], party, {"type": "step", "evidence_id": "M02/log:5", "quote": "市政道路施工挖断 24 芯光缆"}]}
    result, _, _ = run_passes(server, [FACTS, second, WRITING])
    assert len(server.requests) == 3
    assert "复核遍" in server.requests[1]["body"]["messages"][0]["content"]
    assert result.elements.responsible_party.value == "供应商"
    assert len(result.elements.handling_process.value) == 4


def test_failed_second_pass_keeps_first_pass(server):
    result, _, _ = run_passes(server, [FACTS, (500, {}, b"{}"), (500, {}, b"{}"), (500, {}, b"{}"), WRITING])
    assert result.elements.cause.value == "市政道路施工挖断 24 芯光缆"
    assert any("第 2 遍" in d["reason"] for d in result.semantic_assessment.original["facts_dropped"])


def test_fault_area_field_is_a_labelled_last_resort(server):
    from noc7.providers.responsibility_location import area_party, evaluate
    from noc7.schema.elements import PartyCandidate
    assert (area_party("海外-其他运营商-国际运营商"), area_party("省内-用户"), area_party("海外-局方检测正常自恢")) == ("供应商", "客户", None)
    party = {"type": "responsibility", "evidence_id": "M02/log:5", "quote": "市政道路施工挖断 24 芯光缆", "party": "联通",
             "source": "branch_log"}
    result, ctx, _ = run_passes(server, [{"facts": [*FACTS["facts"][:8], party]}, WRITING], passes=1)
    base = next(s for s in ctx.evidence if s.id == "M01/f:description")
    area = base.model_copy(update={"id": "M01/f:fault_area", "text": "海外-其他运营商-国际运营商",
                                   "locator": base.locator.model_copy(update={"field_key": "fault_area"})})
    spans = {s.id: s for s in ctx.evidence} | {area.id: area}
    fallback = PartyCandidate.model_validate(facts._party_nodes([], {area.id: area})[0])
    coverage = result.semantic_assessment.business_coverage

    def party_after(candidates):
        el = result.elements.responsible_party.model_copy(update={"candidates": candidates})
        return evaluate(result.elements.model_copy(update={"responsible_party": el}), spans, coverage)[0]["responsible_party"]

    alone = party_after([fallback])
    assert (alone.value, alone.selected) == ("供应商", "PSYS1") and alone.note.startswith("兜底，待核实")
    both = party_after([*result.elements.responsible_party.candidates, fallback])
    assert both.value == "联通" and "不一致，待核实" in both.note


def test_business_source_beats_system_field(server):
    dated = dict(FACTS["facts"][7], date_evidence_id="M01/f:occurred_at", date_quote="2026-10-10 15:42:00")
    result, _ = run(server, [{"facts": [*FACTS["facts"][:7], dated]}, WRITING])
    record = result.semantic_assessment.recovery_selection
    assert record.sources[record.selected] == "unicom_monitor"
    assert "系统字段只作参照" in record.excluded["SYS1"]


def test_report_uses_verified_writing(server):
    result, _ = run(server, [FACTS, WRITING])
    assert result.narrative.replaced == 2
    assert cell(result, "phenomenon") == ["中断"]
    process = cell(result, "process")
    assert process == [
        "2026-10-10 15:58:14 GMT+8 INOC 经 OTDR 测试定位断点，派线路维护部现场抢修。",
        "2026-10-10 18:57:05 GMT+8 18:55 熔接完成。",
        "2026-10-10 19:16:31 GMT+8 客户确认业务正常。",
    ]
    assert cell(result, "analysis")[0] == "分公司反馈记载：市政道路施工挖断 24 芯光缆。【有记录，未经人工审核】"


@pytest.mark.parametrize("second", [(500, {}, b"{}"), {"process": "不是列表"}, (200, {}, b"not json")])
def test_writing_failure_keeps_elements_and_falls_back(server, second):
    replies = [FACTS, second] if isinstance(second, dict) else [FACTS, second, second, second]
    result, _ = run(server, replies)
    assert result.elements.cause.value and result.elements.end_time.value
    process = cell(result, "process")
    assert len(process) == 4 and "（时间未知）" not in "".join(process)
    if isinstance(second, tuple):
        assert result.narrative is None


def test_malformed_fact_list_is_rejected(server):
    with pytest.raises(TextProviderError):
        run(server, [{"elements": {}}])
    assert len(server.requests) == 1


def test_context_paths_follow_business_rule():
    class Span:
        def __init__(self, sid):
            self.id, self.text = sid, "原文"
            self.locator = type("L", (), {"type": "log_entry", "field_key": None})()
            self.role = "original"
    spans = {f"M02/log:{n}": Span(f"M02/log:{n}") for n in range(1, 6)}
    def fact(kind, n, **extra):
        return {"type": kind, "evidence_id": f"M02/log:{n}", "quote": "原文", **extra}
    device = fact("customer_device_fault", 1, source="other")
    cases = [
        ([device, fact("self_check", 2)], "客户", "customer_self_check"),
        ([device, fact("self_check", 2), fact("customer_followup", 3)], None, None),
        ([device, fact("self_check", 2), fact("vendor_onsite", 3)], "供应商", "vendor_onsite_contact"),
        ([device, fact("unicom_onsite", 3), fact("service_recovered", 4)], "联通", "unicom_onsite_recovery"),
        ([device, fact("unicom_onsite", 3)], None, None),
        ([device, fact("unicom_onsite", 2), fact("self_check", 3)], "客户", "customer_self_check"),
        ([device, fact("unicom_onsite", 2), fact("self_check", 3), fact("service_recovered", 4)], "联通",
         "unicom_onsite_recovery"),
        ([device, fact("vendor_onsite", 2), fact("unicom_onsite", 3), fact("service_recovered", 4)], None, None),
    ]
    for items, category, path in cases:
        nodes = facts._party_nodes(items, spans)
        got = (nodes[0]["relation"]["category"], nodes[0]["relation"]["decision_path"]) if nodes else (None, None)
        assert got == (category, path)


def test_writing_check_and_contact_masking():
    assert narrative.grounded("INOC 查看 R_LOS 告警", "查告警：R_LOS")
    assert not narrative.grounded("17:30 熔接完成", "18:55 熔接完成")
    assert not narrative.grounded("更换 OTU-7 板卡", "更换板卡")
    masked = narrative.mask_contacts("联系张工 13800138000，邮箱 a.b@example.com，2026-10-10 15:42:00")
    assert masked == "联系张工 [电话已隐去]，邮箱 [邮箱已隐去]，2026-10-10 15:42:00"
    assert narrative.mask_contacts("工程师张工-13800138000") == "工程师张工-[电话已隐去]"
    assert narrative.mask_contacts("延伸单 GZ3-20261027-13800138000") == "延伸单 GZ3-20261027-13800138000"


def test_third_party_cause_is_vendor_responsibility_with_note(server):
    quote = "市政道路施工挖断 24 芯光缆"
    party = {"type": "responsibility", "evidence_id": "M02/log:5", "quote": quote, "party": "供应商",
             "source": "branch_log", "third_party": True}
    result, _ = run(server, [{"facts": [*FACTS["facts"][:8], party]}, WRITING])
    assert result.elements.responsible_party.selected
    assert "原文写明由第三方原因造成，按线路所属方记责。" in cell(result, "analysis")[1]


def test_request_drops_repeats_but_keeps_logs_and_originals(server):
    from noc7.providers.text_prompt import repeated_ids
    from noc7.schema import SpanRole

    def span(sid, kind, text, role=SpanRole.ORIGINAL):
        return type("S", (), {"id": sid, "text": text, "role": role,
                              "locator": type("L", (), {"type": kind})()})()

    body = "供应商反馈：光缆已于今日完成熔接。 请客户确认业务是否恢复正常。"
    history = "。 ".join(f"第 {n} 次往来记录的正文内容，逐条累积" for n in range(30)) + "。"
    spans = [
        span("M2/log:1", "log_entry", "【接收】<br>供应商反馈：光缆已于今日完成熔接。<br>请客户确认业务是否恢复正常。"),
        span("M3/t:5", "text_range", "追加信息内容: 请客户确认业务是否恢复正常。"),
        span("M4/msg:0:body", "email_message", body),
        span("M5/msg:1:body", "email_message", "另一封邮件里才有的新内容，需要发给模型。", SpanRole.QUOTED),
        span("M6/msg:0:body", "email_message", "另一封邮件里才有的新内容，需要发给模型。"),
        span("M7/msg:0:table", "email_message", "最新一条的抬头不同。 " + history),
        span("M8/msg:0:table", "email_message", history + " 更早的一封多带一条独有记录，篇幅最长所以保留。"),
        span("M1/f:description", "field", body),
    ]
    assert repeated_ids(spans) == {"M3/t:5", "M4/msg:0:body", "M5/msg:1:body", "M7/msg:0:table"}

    run(server, [FACTS, WRITING])
    sent = json.loads(server.requests[0]["body"]["messages"][1]["content"])["evidence"]
    assert all(set(item) <= {"id", "text", "role", "needs_review", "recorded_at"} for item in sent)
    assert any("recorded_at" in item for item in sent)


def test_fault_area_fallback_survives_validation_and_reports(server, monkeypatch, tmp_path):
    """合成工单没有“故障区域”字段，借“故障类型”字段走一遍完整流程，覆盖结构校验和各种报告。"""
    from noc7.providers import responsibility_location as rl
    from noc7.report import write_reports
    for module in (rl, facts):
        monkeypatch.setattr(module, "AREA_FIELD", "fault_type")
    monkeypatch.setattr(rl, "AREA_PARTIES", (("业务中断", "供应商"),))
    result, _ = run(server, [FACTS, WRITING])
    party = result.elements.responsible_party
    assert (party.value, party.selected) == ("供应商", "PSYS1")
    assert "兜底，待核实" in cell(result, "analysis")[1]
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result
    write_reports(result, tmp_path)
    assert any(tmp_path.iterdir())


def test_system_time_field_cannot_pose_as_a_business_source():
    span = type("S", (), {"id": "M01/f:recovered_at", "text": "2026-09-03 10:00:00"})()
    item = {"type": "recovery_time", "evidence_id": span.id, "quote": span.text,
            "time": span.text, "source": "vendor_rfo"}
    kept, dropped = facts.check_facts({"facts": [item]}, {span.id: span})
    assert kept == [] and "系统时间字段" in dropped[0]["reason"]


S06_MAIL = "M03/msg:1:body"


def _s06(server, time, quote):
    fact = {"type": "recovery_time", "evidence_id": S06_MAIL, "quote": quote, "time": time, "source": "customer"}
    phenomenon = {"type": "phenomenon", "evidence_id": S06_MAIL, "quote": quote}
    return run(server, [{"facts": [phenomenon, fact]}, {"facts": []}, WRITING], bundle="SYN-S06")[0]


def test_zoned_clock_without_date_takes_the_date_before_ticket_recovery(server):
    # 邮件只写“09:15 GMT+8”，工单恢复时间字段是 2026-09-25 10:01:00：取其之前最近的 09:15。
    # 夹具里这个时刻其实早于起障，正式值会被“恢复早于起点”撤回；这里只验日期推定本身。
    from noc7.providers.semantic_constraints import date_inferred
    result = _s06(server, "09:15 GMT+8", "since 09:15 GMT+8")
    candidate = next(c for c in result.elements.end_time.candidates if c.id == "T1")
    assert candidate.time.raw == "09:15 GMT+8" and candidate.time.iso == "2026-09-25T09:15:00+08:00"
    assert date_inferred(candidate) == "工单恢复时间"


def test_clock_without_zone_in_mail_is_not_inferred_but_is_shown_beside_fallback(server):
    # 没写时区的不推定：仍走系统字段兜底，但把原文时刻列在旁边。
    result = _s06(server, "09:15", "since 09:15")
    record = result.semantic_assessment.recovery_selection
    assert record.sources[record.selected] == "system_field"
    lines = cell(result, "resumed")
    assert any("原文另有客户恢复时间：09:15" in line and "未采用" in line for line in lines)



def test_colloquial_and_relative_log_times_take_the_date_from_the_record():
    from datetime import datetime
    from noc7.providers.semantic_constraints import colloquial_time
    recorded = datetime.fromisoformat("2026-11-07T09:10:00+08:00")
    assert colloquial_time("7日早上8：30", recorded).isoformat() == "2026-11-07T08:30:00+08:00"
    assert colloquial_time("昨晚22点23分", recorded).isoformat() == "2026-11-06T22:23:00+08:00"
    assert colloquial_time("昨晚10点", recorded).isoformat() == "2026-11-06T22:00:00+08:00"
    assert colloquial_time("31日 8:00", recorded).isoformat() == "2026-10-31T08:00:00+08:00"
    # 晚于记录时间的不可能是已发生的恢复；普通时刻不归这里管。
    assert colloquial_time("今天下午3点半", recorded) is None
    assert colloquial_time("8:30", recorded) is None


def test_not_fault_ticket_gets_no_party_or_location(server, monkeypatch):
    from noc7.providers import responsibility_location
    monkeypatch.setattr(responsibility_location, "AREA_FIELD", "fault_type")
    monkeypatch.setattr(facts, "AREA_FIELD", "fault_type")
    party = {"type": "responsibility", "evidence_id": "M02/log:5", "quote": "市政道路施工挖断 24 芯光缆",
             "party": "供应商", "source": "branch_log"}
    marker = {"type": "not_fault", "evidence_id": "M01/f:description", "quote": "客户报专线 SYN-CKT-1024 业务中断。"}
    with_party, _ = run(server, [{"facts": [*FACTS["facts"], party]}, WRITING])
    assert with_party.elements.responsible_party.value
    result, _ = run(server, [{"facts": [*FACTS["facts"], party, marker]}, WRITING])
    e = result.elements
    assert not e.responsible_party.value and not list(e.responsible_party.iter_candidates())
    assert not e.location.value
    assert any("不是业务故障" in line for line in cell(result, "analysis"))


def test_usage_is_recorded_per_request(server):
    from noc7.providers.text_http import response_usage
    usage = {"prompt_tokens": 100, "completion_tokens": 20, "prompt_cache_hit_tokens": 40,
             "prompt_cache_miss_tokens": 60, "completion_tokens_details": {"reasoning_tokens": 15}}
    def with_usage(data):
        body = json.loads(envelope(data))
        body["usage"] = usage
        return (200, {}, json.dumps(body, ensure_ascii=False).encode())
    server.replies.extend([with_usage(FACTS), with_usage({"facts": []}), with_usage(WRITING)])
    provider = TwoStageTextProvider(qwen_config(server, fact_passes=2))
    analyze_with_context(BUNDLES / "SYN-P04", provider, registry=text_registry())
    assert len(provider.usage) == 3
    assert provider.usage[0] == {"prompt_tokens": 100, "completion_tokens": 20, "prompt_cache_hit_tokens": 40,
                                 "prompt_cache_miss_tokens": 60, "reasoning_tokens": 15}
    assert response_usage(b"not json") == {} and response_usage(envelope({"facts": []})) == {}


def _p04_recovery(server, iso):
    fact = {"type": "recovery_time", "evidence_id": "M02/log:7", "quote": "19:08 告警清除，业务恢复",
            "time": "19:08 告警清除", "source": "unicom_log", "iso": iso}
    others = [f for f in FACTS["facts"] if f["type"] != "recovery_time"]
    return run(server, [{"facts": [*others, fact]}, WRITING])[0]


def test_model_normalized_time_is_used_only_after_checking_the_original(server):
    # “19:08 告警清除”本地解析不了；模型规整值的时、分、时区（日志按系统时区）、日期（记录当天）都对得上才采用。
    result = _p04_recovery(server, "2026-10-10 19:08+08:00")
    end = result.elements.end_time
    assert end.value.raw == "19:08 告警清除" and end.value.iso.startswith("2026-10-10T19:08")
    record = result.semantic_assessment.recovery_selection
    assert record.sources[record.selected] == "unicom_monitor"
    assert "【日期按日志记录时间推定】" in cell(result, "resumed")[0]
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize("iso", ["2026-10-10 19:18+08:00", "2026-10-10 11:08+00:00", "2026-10-08 19:08+08:00",
                                 "2026-10-10 19:08", "not a time"])
def test_model_normalized_time_that_disagrees_with_the_original_is_not_used(server, iso):
    result = _p04_recovery(server, iso)
    record = result.semantic_assessment.recovery_selection
    assert record.sources[record.selected] == "system_field"


def test_model_normalized_time_keeps_the_written_zone(server):
    from noc7.providers.semantic_constraints import date_inferred
    result = _s06(server, "since 09:15 GMT+8", "since 09:15 GMT+8")  # 本地格式认不得
    candidate = next(c for c in result.elements.end_time.candidates if c.id == "T1")
    assert candidate.time.iso is None  # 没给规整值就不猜
    server.requests.clear()
    fact = {"type": "recovery_time", "evidence_id": S06_MAIL, "quote": "since 09:15 GMT+8", "time": "since 09:15 GMT+8",
            "source": "customer"}
    for iso, expected in [("2026-09-25 09:15+08:00", "2026-09-25T09:15:00+08:00"), ("2026-09-25 01:15+00:00", None)]:
        server.replies.clear()  # 这份夹具不走成文那一步，排着的成文回复不留给下一轮
        result = run(server, [{"facts": [{**fact, "iso": iso}]}, {"facts": []}, WRITING], bundle="SYN-S06")[0]
        candidate = next(c for c in result.elements.end_time.candidates if c.id == "T1")
        assert candidate.time.iso == expected
        if expected:
            assert date_inferred(candidate) == "工单恢复时间"


def test_dates_written_in_the_original_must_agree_with_the_normalized_value():
    from datetime import datetime
    from noc7.providers.semantic_constraints import _day_written
    at = datetime.fromisoformat
    assert _day_written("Tue Oct 20 15:30:00 GMT 2026", at("2026-10-20T15:30:00+00:00")) is True
    assert _day_written("Tue Oct 20 15:30:00 GMT 2026", at("2026-10-21T15:30:00+00:00")) is False
    assert _day_written("2026年10月20日 星期二 15:30:00 GMT", at("2026-10-20T15:30:00+00:00")) is True
    assert _day_written("北京时间10月20号23:34", at("2026-10-20T23:34:00+08:00")) is True
    assert _day_written("北京时间10月20号23:34", at("2026-10-19T23:34:00+08:00")) is False
    assert _day_written("北京时间19日 15:49 - 18:12", at("2026-10-19T18:12:00+08:00")) is True
    assert _day_written("10:12 UTC", at("2026-10-19T10:12:00+00:00")) is None
    assert _day_written("12:45左右", at("2026-10-20T12:45:00+08:00")) is None


def test_clock_in_description_field_is_read_as_beijing_time(server):
    # 工单描述由联通侧建单时录入：没写时区的时刻按北京时间推定，日期不晚于建单（发生时间字段 2026-10-08 08:15）。
    from noc7.providers.semantic_constraints import date_inferred
    start = {"type": "start_time", "evidence_id": "M01/f:description", "quote": "自 08:15 起中断", "time": "08:15",
             "source": "customer"}
    phenomenon = {"type": "phenomenon", "evidence_id": "M01/f:description", "quote": "自 08:15 起中断"}
    for iso, expected in [("2026-10-08 08:15+08:00", "2026-10-08T08:15:00+08:00"), (None, None),
                          ("2026-10-08 08:15+00:00", None), ("2026-10-09 08:15+08:00", None)]:
        server.replies.clear()
        fact = {**start, "iso": iso} if iso else start
        result = run(server, [{"facts": [phenomenon, fact]}, {"facts": []}, WRITING], bundle="SYN-P03")[0]
        candidate = next(c for c in result.elements.start_time.candidates if c.time.raw == "08:15")
        assert candidate.time.iso == expected
        if expected:
            assert candidate.time.tz_source == "assumed" and date_inferred(candidate) == "建单时间"


def test_model_time_fills_in_when_local_parser_only_finds_the_date(server):
    # 本地只解析出日期（时刻夹在星期和时区之间认不得）时，也用核对过的模型值补全时刻。
    from noc7.extract.baseline import time_phrase
    from noc7.providers.semantic_constraints import normalized_time
    from noc7.schema.timeval import TimeValue
    written = "2026年09月25日 星期四 09:15 GMT+8"
    assert time_phrase(written, None).precision == "day"
    server.replies.extend((200, {}, envelope(r)) for r in [
        {"facts": [{"type": "recovery_time", "evidence_id": S06_MAIL, "quote": "since 09:15 GMT+8",
                    "time": "09:15 GMT+8", "source": "customer"}]}, {"facts": []}, WRITING])
    result, ctx, _ = analyze_with_context(BUNDLES / "SYN-S06", TwoStageTextProvider(qwen_config(server)),
                                          registry=text_registry())
    candidate = next(c for c in result.elements.end_time.candidates if c.id == "T1")
    from dataclasses import replace
    ctx = replace(ctx, evidence=[s.model_copy(update={"text": s.text + "\n" + written}) if s.id == S06_MAIL else s
                                 for s in ctx.evidence])
    candidate = candidate.model_copy(update={"time": TimeValue(raw=written)})
    assert normalized_time(candidate, ctx, None).precision == "day"
    assert normalized_time(candidate, ctx, "2026-09-25 09:15+08:00").iso == "2026-09-25T09:15:00+08:00"
    assert normalized_time(candidate, ctx, "2026-09-24 09:15+08:00").precision == "day"
    settled = candidate.model_copy(update={"time": normalized_time(candidate, ctx, "2026-09-25 09:15+08:00")})
    assert normalized_time(settled, ctx) == settled.time  # 复核重算一致


def test_record_time_of_a_customer_confirmation_call_is_not_recovery(server):
    # 日志开头的记录时间 + “致电客户表示已恢复”：是确认动作的时刻，不能当业务恢复时间。
    from dataclasses import replace
    from noc7.providers.semantic_constraints import confirmation_record_time, pending_reason
    from noc7.schema.timeval import TimeValue
    assert confirmation_record_time("2026-10-20 15:29:41", "2026-10-20 15:29:41\n\n联系客户确认恢复，请核实原因")
    assert confirmation_record_time("2026-10-20 17:36:28", "2026-10-20 17:36:28  联系客户表示已解决，可结单")
    assert not confirmation_record_time("2026-10-20 15:29", "2026-10-20 15:29:41 联系客户确认 15:29 恢复")  # 正文写了时刻
    assert not confirmation_record_time("2026-10-20 15:29:41", "2026-10-20 15:29:41 告警清除，业务恢复")  # 不是确认动作
    assert not confirmation_record_time("19:08", "19:08 告警清除，业务恢复")

    result, ctx, _ = run_passes(server, [FACTS, WRITING], passes=1)
    candidate = next(c for c in result.elements.end_time.candidates if "M02/log:7" in c.evidence_refs)
    assert pending_reason(candidate, "end_time", {s.id: s for s in ctx.evidence}) is None
    text = "2026-10-10 19:20:00\n\n致电客户，客户表示业务已恢复"
    spans = {s.id: (s.model_copy(update={"text": text}) if s.id == "M02/log:7" else s) for s in ctx.evidence}
    relation = candidate.relation.model_copy(update={"context": [
        candidate.relation.context[0].model_copy(update={"quote": text})]})
    called = candidate.model_copy(update={"time": TimeValue(raw="2026-10-10 19:20:00", iso="2026-10-10T19:20:00+08:00",
                                                             tz_source="assumed", utc_offset="+08:00", precision="second"),
                                          "relation": relation})
    assert "客户确认时刻不等于业务恢复时刻" in pending_reason(called, "end_time", spans)


def _recorded_run(server, tmp_path, replies, bundle="SYN-P04"):
    server.replies.extend((200, {}, envelope(r)) if isinstance(r, dict) else r for r in replies)
    provider = TwoStageTextProvider(qwen_config(server, fact_passes=2), audit_dir=tmp_path / "audit")
    result, _, _ = analyze_with_context(BUNDLES / bundle, provider, registry=text_registry())
    (path,) = (tmp_path / "audit").glob("*.json")
    return result, json.loads(path.read_text(encoding="utf-8"))


def _replay(server, record, bundle="SYN-P04"):
    from noc7.providers.two_stage_replay import TwoStageReplayProvider
    sent = len(server.requests)
    provider = TwoStageReplayProvider(qwen_config(server, fact_passes=2), record)
    result, _, _ = analyze_with_context(BUNDLES / bundle, provider, registry=text_registry())
    assert len(server.requests) == sent  # 重放不发请求
    return result, provider


def test_offline_replay_reproduces_a_recorded_run(server, tmp_path):
    original, record = _recorded_run(server, tmp_path, [FACTS, {"facts": []}, WRITING])
    assert len(record["fact_responses"]) == 2 and record["raw_response"] == record["fact_responses"][0]
    for mode, rec in [("responses", record), ("facts", {k: v for k, v in record.items() if k != "fact_responses"})]:
        replayed, provider = _replay(server, rec)
        assert provider.mode == mode and not provider.prompt_changed
        assert replayed.elements.model_dump() == original.elements.model_dump()
        assert replayed.narrative == original.narrative  # 成文回复按当前要素重新核验后复用


def test_offline_replay_keeps_a_failed_second_pass_failed(server, tmp_path):
    original, record = _recorded_run(server, tmp_path, [FACTS, (500, {}, b"{}"), (500, {}, b"{}"), (500, {}, b"{}"), WRITING])
    assert record["fact_responses"][1] is None
    replayed, _ = _replay(server, record)
    assert any("第 2 遍" in d["reason"] for d in replayed.semantic_assessment.original["facts_dropped"])
    assert replayed.elements.model_dump() == original.elements.model_dump()


def test_offline_replay_refuses_other_evidence_and_flags_prompt_changes(server, tmp_path):
    _, record = _recorded_run(server, tmp_path, [FACTS, {"facts": []}, WRITING])
    with pytest.raises(TextProviderError, match="证据摘要"):
        _replay(server, {**record, "evidence_sha256": "0" * 64})
    _, provider = _replay(server, {**record, "prompt_version": "old"})
    assert provider.prompt_changed


def test_closing_cause_field_marks_removed_duplicate_or_retired_tickets():
    from types import SimpleNamespace
    def spans(text):
        span = SimpleNamespace(id="M01/f:cause", text=text, locator=SimpleNamespace(type="field"))
        return {span.id: span}
    hit = facts.closing_not_fault(spans("工程师反馈：此条线路已拆除，见文件某号。请核实"))
    assert hit["kind"] == "已拆机" and hit["quote"] == "工程师反馈：此条线路已拆除，见文件某号"
    assert facts.closing_not_fault(spans("与BZ-某地-业务故障X重单，此单销账，以该单跟进处理"))["kind"].startswith("重单")
    assert facts.closing_not_fault(spans("某地3G基站已退网，建议使用VOLTE"))["kind"] == "网络退网说明"
    # 只写销账（中止查障）、普通原因都不算。
    assert facts.closing_not_fault(spans("已超24小时客户未回复邮件，请销账")) is None
    assert facts.closing_not_fault(spans("市政道路施工挖断 24 芯光缆，已熔接恢复。")) is None


def test_removed_line_in_closing_cause_needs_no_model_marker(server):
    # SYN-S10 的结单原因写“线路已拆机”：模型没摘 not_fault，本地规则也判为非故障，责任方、地点留空。
    party = {"type": "responsibility", "evidence_id": "M01/f:cause", "quote": "线路已拆机", "party": "客户",
             "source": "noc"}
    result, _ = run(server, [{"facts": [party]}, {"facts": []}, WRITING], bundle="SYN-S10")
    marker = result.semantic_assessment.original["not_fault"]
    assert (marker["kind"], marker["basis"], marker["quote"]) == ("已拆机", "closing_field", "线路已拆机")
    assert not result.elements.responsible_party.value and not list(result.elements.responsible_party.iter_candidates())
    assert any("本单按结单原因不是业务故障（已拆机）" in line for line in cell(result, "analysis"))


NO_CAUSE_WRITING = {**WRITING, "cause": None}


def test_suspected_cause_is_used_only_when_nothing_is_asserted(server):
    suspected = FACTS["facts"][6]
    result, _ = run(server, [{"facts": [*FACTS["facts"][:5], suspected]}, NO_CAUSE_WRITING])
    cause = result.elements.cause
    assert cause.value == "所在光缆段 R_LOS" and cause.note == "原文仅为怀疑，待确认"
    assert any("【原文仅为怀疑，待确认】" in line for line in cell(result, "analysis"))
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result
    server.replies.clear()
    result, _ = run(server, [FACTS, WRITING])  # 有明确的原因时不取怀疑的
    assert result.elements.cause.value == "市政道路施工挖断 24 芯光缆" and result.elements.cause.note is None


def test_closing_cause_field_is_the_last_layer_for_cause(server):
    result, _ = run(server, [{"facts": FACTS["facts"][:5]}, NO_CAUSE_WRITING])
    cause = result.elements.cause
    assert cause.selected == "CSYS1" and cause.value == "市政道路施工挖断 24 芯光缆，已熔接恢复。"
    assert cause.note.startswith("兜底，待核实")
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result


def test_closing_cause_field_ignores_process_remarks():
    from types import SimpleNamespace as N
    for text, used in [("先返单，后续反馈故障原因", False), ("已超24小时客户未回复邮件，请销账", False),
                       ("烦请让客户提供源IP，谢谢！", False), ("线路已恢复，先返单", False),
                       ("局方检测自恢", True), ("供应商反馈线路正常，返单", True)]:
        assert bool(facts.closing_cause({"M01/f:cause": N(text=text)})) is used, text


def test_suspected_party_sits_between_explicit_party_and_fault_area_field(server):
    from noc7.providers.responsibility_location import evaluate
    from noc7.schema.elements import PartyCandidate
    party = {"type": "responsibility", "evidence_id": "M02/log:5", "quote": "市政道路施工挖断 24 芯光缆", "party": "联通",
             "source": "branch_log"}
    guess = {**party, "party": "供应商", "certainty": "suspected"}
    result, ctx, _ = run_passes(server, [{"facts": [*FACTS["facts"][:8], party, guess]}, WRITING], passes=1)
    el = result.elements.responsible_party
    assert el.value == "联通" and "怀疑" not in el.note  # 有明确的就不取怀疑的
    checks = {c.candidate_id: c for c in result.semantic_assessment.checks if c.element == "responsible_party"}
    assert "怀疑的不采用" in checks["P2"].reason

    base = next(s for s in ctx.evidence if s.id == "M01/f:description")
    area = base.model_copy(update={"id": "M01/f:fault_area", "text": "省内-用户",
                                   "locator": base.locator.model_copy(update={"field_key": "fault_area"})})
    spans = {s.id: s for s in ctx.evidence} | {area.id: area}
    fallback = PartyCandidate.model_validate(facts._party_nodes([], {area.id: area})[0])
    only_guess = [c for c in el.candidates if c.id == "P2"]
    elements = result.elements.model_copy(update={"responsible_party": el.model_copy(update={"candidates": [*only_guess, fallback]})})
    after = evaluate(elements, spans, result.semantic_assessment.business_coverage, layered=True)[0]["responsible_party"]
    assert after.value == "供应商" and "原文仅为怀疑，待确认" in after.note and "不一致，待核实" in after.note
    strict = evaluate(elements, spans, result.semantic_assessment.business_coverage)[0]["responsible_party"]
    assert strict.value == "客户"  # 不分层时怀疑的不采用，退回故障区域字段


def test_noc_or_field_source_is_the_lowest_tier_for_party(server):
    from noc7.providers.responsibility_location import evaluate
    noc = {"type": "responsibility", "evidence_id": "M02/log:5", "quote": "市政道路施工挖断 24 芯光缆", "party": "联通",
           "source": "noc"}
    result, ctx, _ = run_passes(server, [{"facts": [*FACTS["facts"][:8], noc]}, WRITING], passes=1)
    el = result.elements.responsible_party
    assert el.value == "联通" and "来源层级最低" in el.note  # 没有更高层来源时用最低一层
    spans = {s.id: s for s in ctx.evidence}
    strict = evaluate(result.elements, spans, result.semantic_assessment.business_coverage)[0]["responsible_party"]
    assert strict.value is None  # 不分层时仍不采用

    high = {**noc, "party": "供应商", "source": "branch_log"}
    result, _, _ = run_passes(server, [{"facts": [*FACTS["facts"][:8], noc, high]}, WRITING], passes=1)
    el = result.elements.responsible_party
    assert el.value == "供应商" and "来源层级最低" not in el.note and "低优先级差异保留待核对" in el.note


def test_customer_guess_is_not_a_suspected_party(server):
    guess = {"type": "responsibility", "evidence_id": "M02/log:5", "quote": "市政道路施工挖断 24 芯光缆", "party": "联通",
             "source": "customer", "certainty": "suspected"}
    result, _, _ = run_passes(server, [{"facts": [*FACTS["facts"][:8], guess]}, WRITING], passes=1)
    assert result.elements.responsible_party.value is None
    checks = [c for c in result.semantic_assessment.checks if c.element == "responsible_party"]
    assert any("客户（报障方）的猜测" in (c.reason or "") for c in checks)


def test_negation_vetoes_suspected_party_but_not_asserted(server):
    guess = {"type": "responsibility", "evidence_id": "M02/log:5", "quote": "市政道路施工挖断 24 芯光缆", "party": "供应商",
             "source": "branch_log", "certainty": "suspected"}
    denial = {**guess, "source": "vendor_feedback", "certainty": "negated"}
    result, _, _ = run_passes(server, [{"facts": [*FACTS["facts"][:8], guess, denial]}, WRITING], passes=1)
    assert result.elements.responsible_party.value is None
    checks = {c.candidate_id: c for c in result.semantic_assessment.checks if c.element == "responsible_party"}
    assert "否定这一方故障" in checks["P1"].reason

    sure = {**guess, "certainty": "asserted"}
    result, _, _ = run_passes(server, [{"facts": [*FACTS["facts"][:8], sure, denial]}, WRITING], passes=1)
    assert result.elements.responsible_party.value == "供应商"  # 明确结论不因否定说法变成冲突


def test_conflicting_top_tier_falls_back_to_next_tier_then_to_most_cited(server):
    a = {"type": "responsibility", "evidence_id": "M02/log:5", "quote": "市政道路施工挖断 24 芯光缆", "party": "联通",
         "source": "branch_log"}
    b = {**a, "party": "供应商"}
    low = {**a, "party": "供应商", "source": "noc"}
    result, _, _ = run_passes(server, [{"facts": [*FACTS["facts"][:8], a, b, low]}, WRITING], passes=1)
    el = result.elements.responsible_party
    assert el.value == "供应商" and "较高层来源结论冲突" in el.note and "取下一层来源" in el.note

    result, _, _ = run_passes(server, [{"facts": [*FACTS["facts"][:8], a, b]}, WRITING], passes=1)
    el = result.elements.responsible_party
    assert el.status == "documented" and el.value == "联通" and "同层来源结论冲突" in el.note
