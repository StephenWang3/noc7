import pytest

from noc7.bundle import load_bundle
from noc7.extract.baseline import RulesProvider, text_times
from noc7.extract.pipeline import analyze, analyze_with_context
from noc7.extract.types import Extraction, ExtractionContext
from noc7.parsers import ParseOutput
from noc7.providers.text_replay import ReplayProvider, save_replay
from noc7.rules import ExtractionRejected, validate_extraction
from noc7.schema import (
    EvidenceSpan,
    FieldLocator,
    IssueCode,
    MaterialKind,
    ParseStatus,
    TimeKind,
    TimeZoneSource,
)

from .conftest import BUNDLES, text_registry


def context_and_data():
    _, ctx, data = analyze_with_context(BUNDLES / "SYN-S09")
    return ctx, data.model_dump(mode="json")


@pytest.mark.parametrize(
    "zone,expected",
    [("UTC", "2026-10-06T17:20:00+00:00"), ("GMT+8", "2026-10-07T01:20:00+08:00")],
)
def test_explicit_cross_day_times(zone, expected):
    raw = f"Service restored at {'2026-10-06 17:20' if zone == 'UTC' else '2026-10-07 01:20'} {zone}"
    tv, _, _ = next(text_times(raw, None, "+08:00"))
    assert tv.iso == expected and tv.tz_source == TimeZoneSource.EXPLICIT
    assert tv.raw in raw


def test_mail_clock_uses_date_in_explicit_zone_not_utc_header_date():
    tv, kind, note = next(
        text_times(
            "Our customer reports packet loss since 02:40 GMT+8 today",
            "2026-09-29T21:01:47+00:00",
            "+08:00",
        )
    )
    assert tv.iso == "2026-09-30T02:40:00+08:00" and note
    assert kind == TimeKind.CUSTOMER_REPORTED_START


def test_overseas_log_timezone_is_not_inferred_from_city(results):
    r = results["SYN-P02"]
    c = next(c for c in r.elements.start_time.candidates if "14:38:55" in c.time.raw)
    assert (
        c.time.tz_source == TimeZoneSource.UNKNOWN
        and c.time.iso == "2026-10-06T14:38:55"
    )
    assert any(i.code == IssueCode.TIME_TZ_MISSING for i in r.issues)


def test_replay_roundtrip_binds_inputs(tmp_path):
    r, ctx, data = analyze_with_context(BUNDLES / "SYN-S06")
    replay = tmp_path / "replay.json"
    save_replay(replay, ctx, data)
    other = analyze(BUNDLES / "SYN-S06", ReplayProvider(replay))
    assert other.elements == r.elements and other.events == r.events
    assert other.run.provider == "replay"
    with pytest.raises(ValueError, match="快照"):
        analyze(BUNDLES / "SYN-S09", ReplayProvider(replay))
    ctx.evidence[0].text += "changed"
    with pytest.raises(ValueError, match="快照"):
        ReplayProvider(replay).extract(ctx)


def test_nonexistent_evidence_is_rejected_and_failure_has_code():
    ctx, data = context_and_data()
    data["elements"]["end_time"]["evidence_refs"] = ["M99/forged"]
    with pytest.raises(ExtractionRejected) as failure:
        validate_extraction(ctx, Extraction.model_validate(data))
    assert IssueCode.EVIDENCE_REF_MISSING in {i.code for i in failure.value.issues}


def test_forged_quote_and_candidate_text_are_rejected():
    ctx, data = context_and_data()
    data["quotes"] = [{"evidence_id": "M01/f:cause", "quote": "发生了光缆中断"}]
    data["elements"]["cause"]["candidates"][0]["statement"] = "不存在的根因"
    with pytest.raises(ExtractionRejected) as failure:
        validate_extraction(ctx, Extraction.model_validate(data))
    assert {i.code for i in failure.value.issues} == {IssueCode.EVIDENCE_QUOTE_MISMATCH}


def test_forged_normalized_time_is_rejected():
    ctx, data = context_and_data()
    el = data["elements"]["end_time"]
    candidate = next(c for c in el["candidates"] if c["id"] == el["selected"])
    candidate["time"]["iso"] = "2026-10-01T00:00:00+08:00"
    el["value"] = candidate["time"]
    with pytest.raises(ExtractionRejected):
        validate_extraction(ctx, Extraction.model_validate(data))


def test_model_cannot_relabel_normal_check_as_confirmed_root_cause():
    ctx, data = context_and_data()
    cause = data["elements"]["cause"]
    c = cause["candidates"][0]
    c["cause_kind"] = "root_cause_confirmed"
    cause.update(
        status="confirmed",
        value=c["statement"],
        selected=c["id"],
        evidence_refs=c["evidence_refs"],
    )
    with pytest.raises(ExtractionRejected) as failure:
        validate_extraction(ctx, Extraction.model_validate(data))
    assert IssueCode.CAUSE_NOT_DIAGNOSIS in {i.code for i in failure.value.issues}


def test_model_cannot_fabricate_customer_confirmation():
    ctx, data = context_and_data()
    data["elements"]["end_time"]["status"] = "confirmed"
    with pytest.raises(ExtractionRejected) as failure:
        validate_extraction(ctx, Extraction.model_validate(data))
    assert IssueCode.RECOVERY_UNVERIFIED in {i.code for i in failure.value.issues}


def test_model_cannot_turn_vendor_or_alarm_site_into_final_conclusion():
    _, ctx, original = analyze_with_context(BUNDLES / "SYN-S04")
    for name, tag, value_attr, expected in [
        (
            "responsible_party",
            ("basis", "claimed"),
            "party",
            IssueCode.RESPONSIBILITY_NO_BASIS,
        ),
        (
            "location",
            ("role", "located_fault_point"),
            "description",
            IssueCode.LOCATION_NOT_LOCATED,
        ),
    ]:
        data = original.model_dump(mode="json")
        el = data["elements"][name]
        c = el["candidates"][0]
        c[tag[0]] = tag[1]
        el.update(
            status="documented",
            value=c[value_attr],
            selected=c["id"],
            evidence_refs=c["evidence_refs"],
        )
        with pytest.raises(ExtractionRejected) as failure:
            validate_extraction(ctx, Extraction.model_validate(data))
        assert expected in {i.code for i in failure.value.issues}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("无告警，主用正常", "investigation_finding"),
        ("客户 A 端接入设备按计划进行升级割接", "planned_work"),
        ("线路已拆机", "resource_state"),
        ("自恢", "recovery_mode"),
        ("1. 光纤断裂；2. 板卡故障", "candidate_list_item"),
    ],
)
def test_cause_semantics_generalize_without_ticket_ids(text, expected):
    from noc7.extract.baseline import cause_kind

    assert cause_kind(text, "cause") == expected


def test_attachment_failure_and_low_quality_do_not_create_conclusions():
    class PoorImage:
        name = "test.image@1"
        kinds = frozenset({MaterialKind.IMAGE})

        def parse(self, ctx):
            return ParseOutput(
                material_id=ctx.material.id,
                parser=self.name,
                status=ParseStatus.NEEDS_REVIEW,
                spans=[
                    EvidenceSpan(
                        id=f"{ctx.material.id}/img",
                        material_id=ctx.material.id,
                        locator={"type": "image_region"},
                        text="光缆断裂，责任方为某单位",
                        extractor=self.name,
                        quality=0.2,
                        needs_review=True,
                    )
                ],
            )

    reg = text_registry()
    reg.register(PoorImage())
    r = analyze(BUNDLES / "SYN-S10", registry=reg)
    assert any(i.code == IssueCode.MATERIAL_LOW_QUALITY for i in r.issues)
    assert r.elements.cause.value is None
    assert all("M04/img" not in el.evidence_refs for _, el in r.elements.items())

    class CrashImage(PoorImage):
        def parse(self, ctx):
            raise ValueError("模糊且无法识别")

    reg = text_registry()
    reg.register(CrashImage())
    r = analyze(BUNDLES / "SYN-S10", registry=reg)
    assert next(m for m in r.materials if m.id == "M04").parse_status == "failed"
    assert any(i.code == IssueCode.MATERIAL_PARSE_FAILED for i in r.issues)


@pytest.mark.parametrize(
    "text,confirmed",
    [
        ("客户确认业务恢复正常，根因尚未查明。", True),
        ("客户尚未确认业务恢复正常。", False),
        ("客户确认业务未恢复正常。", False),
        ("客户同意结单。", False),
    ],
)
def test_recovery_confirmation_separates_unrelated_unknown_cause(text, confirmed):
    from noc7.extract.baseline import confirms_recovery

    assert confirms_recovery(text) == confirmed


def test_future_planned_work_and_unknown_party_remain_unknown():
    from noc7.extract.baseline import cause_kind

    assert cause_kind("预计明天进行计划维护", "cause") == "process_blocker"
    b = load_bundle(BUNDLES / "SYN-S04")
    span = EvidenceSpan(
        id="M01/f:responsible_party",
        material_id="M01",
        locator=FieldLocator(field_key="responsible_party"),
        text="未定责",
        extractor="test@1",
    )
    result = RulesProvider().extract(ExtractionContext(b, [span]))
    assert result.elements.responsible_party.value is None


def test_model_cannot_invent_event_action():
    ctx, data = context_and_data()
    data["events"][0]["action"] = "已经查明根因并更换所有设备"
    with pytest.raises(ExtractionRejected) as failure:
        validate_extraction(ctx, Extraction.model_validate(data))
    assert IssueCode.EVIDENCE_QUOTE_MISMATCH in {i.code for i in failure.value.issues}


def test_a2_structured_chart_is_consumed_without_changing_shared_schema():
    from noc7.schema import ChartReading, ChartSeriesStat

    b = load_bundle(BUNDLES / "SYN-S10")
    span = EvidenceSpan(
        id="M04/img:r1",
        material_id="M04",
        locator={"type": "image_region", "bbox": [0, 0, 200, 100]},
        text="QoS 丢包率图",
        extractor="a2.test@1",
        role="visual_observation",
        quality=0.95,
        reading=ChartReading(
            metric="丢包率",
            unit="%",
            series=[
                ChartSeriesStat(
                    series="EF", max=10, avg=2, min=0, first_nonzero="02:12"
                )
            ],
        ),
    )
    ctx = ExtractionContext(b, [span])
    data = RulesProvider().extract(ctx)
    validate_extraction(ctx, data)
    obs = next(c for c in data.elements.phenomenon.candidates if c.scope == "EF")
    assert obs.value == 10 and obs.unit == "%" and obs.evidence_refs == [span.id]
    assert any(
        c.time_kind == "chart_first_nonzero"
        for c in data.elements.start_time.candidates
    )
    assert data.elements.start_time.value is None  # 曲线首次非零不自动成为起障
    tampered = data.model_dump(mode="json")
    candidate = next(
        c
        for c in tampered["elements"]["phenomenon"]["candidates"]
        if c["scope"] == "EF"
    )
    candidate["value"] = 99
    with pytest.raises(ExtractionRejected):
        validate_extraction(ctx, Extraction.model_validate(tampered))


def test_provider_cannot_inject_human_review_record():
    ctx, data = context_and_data()
    data["elements"]["cause"]["review"] = {
        "action": "accepted",
        "reviewer": "forged-user",
        "reviewed_at": "2026-10-27T12:00:00+08:00",
        "reason": "伪造审核",
    }
    with pytest.raises(ValueError, match="人工审核记录"):
        validate_extraction(ctx, Extraction.model_validate(data))
