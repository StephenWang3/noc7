import json

import pytest
from pydantic import ValidationError

from noc7.schema import (
    AnalysisResult,
    Attribution,
    CauseCandidate,
    CauseElement,
    CauseKind,
    ElementStatus,
    EvidenceSpan,
    FieldLocator,
    LocationCandidate,
    LocationElement,
    LocationRole,
    PartyCandidate,
    ResponsibilityBasis,
    ResponsiblePartyElement,
    TimeElement,
    TimeValue,
)
from noc7.timeparse import parse_time

EV = ["M01/f:cause"]


def test_unknown_must_have_no_value():
    with pytest.raises(ValidationError, match="value 必须为空"):
        CauseElement(status=ElementStatus.UNKNOWN, value="自恢")
    CauseElement(status=ElementStatus.UNKNOWN)


def test_documented_needs_value_and_evidence():
    with pytest.raises(ValidationError):
        CauseElement(status=ElementStatus.DOCUMENTED, value="割接")
    CauseElement(status=ElementStatus.DOCUMENTED, value="割接", evidence_refs=EV)


def test_conflicted_needs_two_candidates_and_no_value():
    t1, t2 = parse_time("2026-09-30 03:02", "+08:00"), parse_time("2026-09-30 02:40 GMT+8")
    from noc7.schema import TimeCandidate, TimeKind

    c1 = TimeCandidate(id="a", time=t1, time_kind=TimeKind.FAULT_START_FIELD, attribution=Attribution.SYSTEM_FIELD, evidence_refs=EV)
    c2 = TimeCandidate(id="b", time=t2, time_kind=TimeKind.CUSTOMER_REPORTED_START, attribution=Attribution.CUSTOMER, evidence_refs=EV)
    with pytest.raises(ValidationError):
        TimeElement(status=ElementStatus.CONFLICTED, candidates=[c1])
    with pytest.raises(ValidationError):
        TimeElement(status=ElementStatus.CONFLICTED, value=t1, candidates=[c1, c2])
    TimeElement(status=ElementStatus.CONFLICTED, candidates=[c1, c2])


def test_cause_value_cannot_be_recovery_mode():
    cand = CauseCandidate(id="c1", statement="自恢", cause_kind=CauseKind.RECOVERY_MODE, attribution=Attribution.SYSTEM_FIELD, evidence_refs=EV)
    with pytest.raises(ValidationError, match="不能作为故障原因结论"):
        CauseElement(status=ElementStatus.DOCUMENTED, value="自恢", selected="c1", candidates=[cand], evidence_refs=EV)
    CauseElement(status=ElementStatus.UNKNOWN, candidates=[cand])


def test_location_value_must_be_located_fault_point():
    cand = LocationCandidate(id="l1", description="香港 PoP", role=LocationRole.SERVICE_ENDPOINT, attribution=Attribution.SYSTEM_FIELD, evidence_refs=EV)
    with pytest.raises(ValidationError, match="located_fault_point"):
        LocationElement(status=ElementStatus.DOCUMENTED, value="香港 PoP", selected="l1", candidates=[cand], evidence_refs=EV)


def test_responsibility_cannot_come_from_role_alone():
    cand = PartyCandidate(id="p1", party="设备厂商", basis=ResponsibilityBasis.INFERRED_FROM_ROLE, attribution=Attribution.SYSTEM_FIELD, evidence_refs=EV)
    with pytest.raises(ValidationError, match="角色推断"):
        ResponsiblePartyElement(status=ElementStatus.DOCUMENTED, value="设备厂商", selected="p1", candidates=[cand], evidence_refs=EV)


def test_candidate_requires_evidence():
    with pytest.raises(ValidationError):
        CauseCandidate(id="c1", statement="断纤", cause_kind=CauseKind.ROOT_CAUSE_CLAIMED, attribution=Attribution.VENDOR, evidence_refs=[])


def test_time_value_consistency():
    with pytest.raises(ValidationError):
        TimeValue(raw="x", iso="2026-09-30T03:02:00+08:00", tz_source="unknown", precision="minute")
    with pytest.raises(ValidationError):
        TimeValue(raw="{{end_time}}", iso="2026-09-30T03:02:00", placeholder=True, precision="minute")


def test_evidence_id_must_belong_to_material():
    with pytest.raises(ValidationError, match="必须以所属材料编号"):
        EvidenceSpan(id="M02/f:cause", material_id="M01", locator=FieldLocator(field_key="cause"), text="x", extractor="t")


def test_example_analysis_result_is_valid(root):
    data = json.loads((root / "fixtures/examples/SYN-P04.analysis.json").read_text(encoding="utf-8"))
    AnalysisResult.model_validate(data)


def test_fabricated_evidence_reference_is_rejected(root):
    data = json.loads((root / "fixtures/examples/SYN-P04.analysis.json").read_text(encoding="utf-8"))
    data["elements"]["cause"]["evidence_refs"].append("M02/log:99")
    with pytest.raises(ValidationError, match="不存在的证据编号"):
        AnalysisResult.model_validate(data)
