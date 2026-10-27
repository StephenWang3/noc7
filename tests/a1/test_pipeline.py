import pytest

from noc7.report import final_duration
from noc7.schema import AnalysisResult, GoldAnswer, TimeKind

from .conftest import BUNDLES


@pytest.mark.parametrize("name", sorted(p.name for p in BUNDLES.iterdir()))
def test_all_synthetic_bundles_produce_valid_traceable_result(name, results):
    result = results[name]
    assert AnalysisResult.model_validate_json(result.model_dump_json()) == result
    assert result.run.provider == "rules"
    assert len(result.evidence) > 0
    assert all(m.parse_status != "pending" for m in result.materials)
    assert {r for r in result.iter_evidence_refs()} <= {s.id for s in result.evidence}
    gold = GoldAnswer.model_validate_json(
        (BUNDLES.parents[1] / "evals/gold" / f"{name}.json").read_text()
    )
    assert {i.code for i in gold.expected_issues} <= {i.code for i in result.issues}
    for key, expected in gold.elements.items():
        if name == "SYN-P02" and key == "location":
            # 唯一定位依据是 A2 的 EML，A1 单独交付时必须保持未知。
            assert result.elements.location.status == "unknown"
            continue
        actual = getattr(result.elements, key)
        assert actual.status in expected.status_in, (name, key, actual.status)


def test_normal_checks_are_not_cause_or_recovery(results):
    for name in ["SYN-S01", "SYN-S09"]:
        r = results[name]
        assert r.elements.cause.value is None
        assert any(
            c.cause_kind == "investigation_finding" for c in r.elements.cause.candidates
        )
    r = results["SYN-S09"]
    assert r.elements.end_time.status == "documented"
    assert final_duration(r) is None
    obs = r.elements.phenomenon.candidates
    assert any(o.attribution == "customer" and "25%" in o.description for o in obs)
    assert any(o.attribution == "noc_check" and "无丢包" in o.description for o in obs)


def test_vendor_role_and_alarm_location_do_not_become_conclusions(results):
    r = results["SYN-S04"]
    assert r.elements.responsible_party.value is None
    assert all(
        c.basis == "inferred_from_role" for c in r.elements.responsible_party.candidates
    )
    assert r.elements.location.value is None
    assert any(c.role == "alarm_location" for c in r.elements.location.candidates)


def test_start_candidates_keep_semantics_not_earliest_timestamp(results):
    r = results["SYN-S08"]
    assert {c.time_kind for c in r.elements.start_time.candidates} >= {
        TimeKind.ALARM_RAISED,
        TimeKind.WARNING_RAISED,
        TimeKind.TICKET_CREATED,
    }
    assert r.elements.start_time.value.raw == "2026-09-22 03:17:45"
    assert "告警" in r.elements.start_time.note
    r = results["SYN-S06"]
    assert (
        r.elements.start_time.status == "conflicted"
        and r.elements.start_time.value is None
    )
    assert any(
        c.time_kind == TimeKind.CUSTOMER_REPORTED_START
        and c.time.iso == "2026-09-25T09:15:00+08:00"
        for c in r.elements.start_time.candidates
    )


def test_body_date_conflict_is_retained(results):
    candidates = results["SYN-S07"].elements.start_time.candidates
    assert any(
        c.time_kind == "body_text_date" and c.time.iso.startswith("2026-09-21")
        for c in candidates
    )
    assert any(
        c.time_kind == "alarm_raised" and c.time.iso.startswith("2026-09-26")
        for c in candidates
    )


def test_negative_duration_does_not_silently_repair_date(results):
    r = results["SYN-P01"]
    assert r.elements.end_time.status == "conflicted"
    assert {
        c.time.iso
        for c in r.elements.end_time.candidates
        if c.time_kind
        in {TimeKind.RECOVERY_FIELD, TimeKind.CUSTOMER_CONFIRMED_RECOVERY}
    } == {"2026-10-05T00:20:00+08:00", "2026-10-06T00:20:00+08:00"}
    assert final_duration(r) is None


def test_dedup_preserves_raw_spans_and_source_links(results):
    r = results["SYN-S02"]
    assert r.span("M02/log:7").derived_from == ["M02/log:6"]
    assert (
        sum(
            "经与客户维护人员电话确认" in s.action
            for s in r.elements.handling_process.value
        )
        == 1
    )
    assert len([s for s in r.evidence if s.locator.type == "log_entry"]) == 12
    r = results["SYN-S06"]
    assert all("AI 追单总结" not in e.action for e in r.events)
    assert r.span("M02/log:9").role == "derived_summary"


def test_injection_quarantine_and_invalid_related_ticket(results):
    r = results["SYN-P03"]
    assert any("ignore all previous rules" in s.text for s in r.evidence)
    assert r.elements.cause.value is None and r.elements.responsible_party.value is None
    assert all("ignore all previous rules" not in e.action for e in r.events)
    assert r.related_tickets[0].status == "已作废"
    assert any(i.code == "RELATED_TICKET_INVALID" for i in r.issues)


def test_identity_resource_state_is_not_root_cause(results):
    r = results["SYN-S10"]
    assert r.service_identity.status == "unverified"
    assert {i.value for i in r.service_identity.identifiers} >= {
        "SYN-CKT-1010",
        "SYN-CKT-2010",
    }
    assert r.elements.cause.value is None
    assert r.elements.end_time.status == "documented"  # 同意结单不能当恢复确认
    assert r.elements.start_time.status == "conflicted"
    assert final_duration(results["SYN-X01"]) is None


def test_positive_control_keeps_supported_conclusions(results):
    r = results["SYN-P04"]
    assert r.elements.end_time.status == "confirmed"
    assert "挖断" in r.elements.cause.value
    assert "示例建设公司" in r.elements.responsible_party.value
    assert "人井" in r.elements.location.value
    assert final_duration(r) == 206
