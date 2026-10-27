"""复现审核指出的六类语义错误，直接检查值、分类和结论证据。"""

import pytest

from noc7.bundle import load_bundle
from noc7.extract.baseline import RulesProvider, text_times
from noc7.extract.types import ExtractionContext
from noc7.schema import EvidenceSpan, TimeKind

from .conftest import BUNDLES


def extract_text(text):
    bundle = load_bundle(BUNDLES / "SYN-S01")
    span = EvidenceSpan(
        id="M03/t:1",
        material_id="M03",
        locator={"type": "text_range", "line": 1},
        text=text,
        extractor="test@1",
    )
    return RulesProvider().extract(ExtractionContext(bundle, [span]))


@pytest.mark.parametrize(
    "zone,offset",
    [
        ("GMT+8", "+08:00"),
        ("UTC", "+00:00"),
        ("北京时间", "+08:00"),
        ("GMT+08:00", "+08:00"),
    ],
)
def test_s06_original_phrase_binds_separated_explicit_zone(results, zone, offset):
    original = results["SYN-S06"].span("M03/msg:2:body").text
    text = original.replace("GMT+8", zone)
    tv, kind, _ = next(text_times(text, "2026-09-25T09:16:42+08:00", "+08:00"))
    assert tv.raw == f"09:15 this morning ({zone})"
    assert tv.raw in text and tv.tz_source == "explicit"
    assert tv.iso == f"2026-09-25T09:15:00{offset}"
    assert kind == TimeKind.CUSTOMER_REPORTED_START


def test_pipeline_retains_s06_original_explicit_zone(results):
    r = results["SYN-S06"]
    c = next(
        c
        for c in r.elements.start_time.candidates
        if "M03/msg:2:body" in c.evidence_refs
    )
    assert c.time.raw == "09:15 this morning (GMT+8)"
    assert c.time.tz_source == "explicit"
    assert c.time.iso == "2026-09-25T09:15:00+08:00"


def test_explicit_zone_does_not_attach_across_clauses():
    times = list(
        text_times(
            "09:15 this morning (UTC); 17:00 检查正常",
            "2026-09-25T17:30:00+08:00",
            "+08:00",
        )
    )
    assert len(times) == 2
    assert times[0][0].tz_source == "explicit" and times[0][0].iso.endswith("+00:00")
    assert times[1][0].tz_source == "assumed" and times[1][0].iso.endswith("+08:00")


def test_p04_service_identifier_is_not_a_numeric_timezone(results):
    r = results["SYN-P04"]
    candidate = next(
        c for c in r.elements.start_time.candidates if c.time_kind == "alarm_raised"
    )
    assert candidate.time.iso == "2026-10-10T15:42:00+08:00"
    assert candidate.time.raw == "15:42"


def test_p04_each_time_uses_its_own_recovery_clause(results):
    r = results["SYN-P04"]
    candidates = [
        c for c in r.elements.end_time.candidates if "M02/log:7" in c.evidence_refs
    ]
    assert [(c.time.raw, c.time_kind) for c in candidates] == [
        ("19:08", TimeKind.ALARM_CLEARED),
        ("19:15", TimeKind.CUSTOMER_CONFIRMED_RECOVERY),
    ]
    assert all(
        "M02/log:7" not in c.evidence_refs for c in r.elements.start_time.candidates
    )
    assert r.elements.end_time.status == "confirmed"
    assert r.elements.end_time.value.iso == "2026-10-10T19:08:00+08:00"


@pytest.mark.parametrize("negative", ["无告警", "没有告警", "未见告警", "未发现告警"])
def test_negated_alarm_cannot_become_fault_start(negative):
    r = extract_text(f"{negative}，2026-10-06 14:00 主用正常")
    assert not r.elements.start_time.candidates
    assert r.elements.start_time.value is None
    assert r.elements.end_time.candidates[0].time_kind == "observation"
    assert r.elements.end_time.value is None  # 正常检查同样不能替代恢复确认


def test_s10_normal_monitoring_is_only_an_end_side_observation(results):
    r = results["SYN-S10"]
    assert all(
        "M02/log:9" not in c.evidence_refs for c in r.elements.start_time.candidates
    )
    c = next(
        c for c in r.elements.end_time.candidates if "M02/log:9" in c.evidence_refs
    )
    assert c.time.raw == "07:30" and c.time_kind == "observation"


def test_scope_warning_requires_opposed_measurements(results):
    assert all(i.code != "OBSERVATION_SCOPE_DIFFERS" for i in results["SYN-P04"].issues)
    assert any(i.code == "OBSERVATION_SCOPE_DIFFERS" for i in results["SYN-S09"].issues)
    assert all(
        "M02/log:10" not in o.evidence_refs
        for o in results["SYN-P04"].elements.phenomenon.candidates
    )


def test_s06_quoted_loss_keeps_candidates_without_multiplying_conclusion_evidence(
    results,
):
    r = results["SYN-S06"]
    phenomenon = r.elements.phenomenon
    assert phenomenon.value.count("86%") == 1
    assert "M03/msg:1:body" not in phenomenon.evidence_refs
    assert "M03/msg:2:body" not in phenomenon.evidence_refs
    assert any(
        "M03/msg:2:body" in c.evidence_refs
        and c.time.iso == "2026-09-25T09:15:00+08:00"
        for c in r.elements.start_time.candidates
    )


def test_s02_exact_duplicates_do_not_add_confirmation_evidence(results):
    r = results["SYN-S02"]
    refs = r.elements.end_time.evidence_refs
    assert "M02/log:6" in refs
    assert all(f"M02/log:{i}" not in refs for i in range(7, 11))
    assert all(not r.span(ref).derived_from for ref in refs)


def test_s10_migration_date_stays_in_table_and_restored_placeholder_is_end_side(
    results,
):
    r = results["SYN-S10"]
    for element in [r.elements.start_time, r.elements.end_time]:
        assert all("M03/msg:1:table" not in c.evidence_refs for c in element.candidates)
    assert r.span("M03/msg:1:table").reading.rows[0][3] == "2026-07-15"
    assert not any(c.time.placeholder for c in r.elements.start_time.candidates)
    assert any(
        c.time.raw == "{{end_time}}" and c.time.placeholder
        for c in r.elements.end_time.candidates
    )
