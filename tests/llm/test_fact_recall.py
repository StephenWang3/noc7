"""合成正反例同时约束规则与模型本地重算，不使用真实原文。"""

import pytest

from noc7.extract.baseline import RulesProvider
from noc7.extract.types import ExtractionContext
from noc7.providers.text_http import OpenAICompatibleTextProvider
from noc7.schema import EvidenceSpan, FieldLocator

from .conftest import envelope, qwen_config
from .test_evidence import empty_extraction


def context(sample, text, *, role="original", key="diagnosis"):
    s = EvidenceSpan(id=f"M01/f:{key}", material_id="M01", locator=FieldLocator(field_key=key),
                     text=text, extractor="synthetic", role=role)
    return ExtractionContext(sample[0].bundle, [s])


def model_result(server, ctx, name, excerpt, label):
    data = empty_extraction()
    attr = "party" if name == "responsible_party" else "description"
    data["elements"][name]["candidates"] = [dict(
        id="C1", evidence_refs=[ctx.evidence[0].id], attribution="unknown", **{attr: excerpt}, **label)]
    server.default = envelope(data)
    return OpenAICompatibleTextProvider(qwen_config(server)).extract(ctx)


@pytest.mark.parametrize("text,excerpt", [
    ("客户经理表示先结单，客户内部继续排查。此单办结（客户原因）。", "客户原因"),
    ("责任归属：SYN-运营商甲。", "SYN-运营商甲"),
])
def test_explicit_claim_is_documented_not_formally_confirmed(server, sample, text, excerpt):
    ctx = context(sample, text)
    rules = RulesProvider().extract(ctx).elements.responsible_party
    model = model_result(server, ctx, "responsible_party", excerpt, {"basis": "inferred_from_role"}).elements.responsible_party
    assert rules.status == "documented"
    assert rules.candidates[0].basis == "claimed"
    assert rules.evidence_refs == [ctx.evidence[0].id]
    assert model.status == "unknown" and model.candidates == []


@pytest.mark.parametrize("text", [
    "疑似客户原因。", "非客户原因。", "不能认定客户原因。", "请排查客户原因。",
    "客户原因待核实。", "客户原因已排除。", "责任归属：未知。", "责任归属：可能为客户。",
    "排除客户原因。", "否认客户原因。", "已排除客户侧原因。",
    "客户原因（疑似）。", "客户原因，待核实。", "责任归属：客户，待确认。",
    "不能认定（客户原因）。", "疑似（客户原因）。", "办结（客户原因）尚待确认。",
])
def test_uncertain_or_negated_claims_stay_unknown(server, sample, text):
    ctx = context(sample, text)
    result = model_result(server, ctx, "responsible_party", text, {"basis": "formal_determination"})
    assert RulesProvider().extract(ctx).elements.responsible_party.status == "unknown"
    assert result.elements.responsible_party.status == "unknown"


RFO = "Reason for Failure: Fiber cut caused by damage.\nLocation: Between SYN-Node-A and SYN-Node-B, SYN-Country\nCorrective Actions: Splicing completed."
POINT = "Between SYN-Node-A and SYN-Node-B, SYN-Country"


def test_rfo_location_has_same_supported_value_in_both_providers(server, sample):
    ctx = context(sample, RFO)
    rule = RulesProvider().extract(ctx).elements.location
    model = model_result(server, ctx, "location", POINT, {"role": "alarm_location"}).elements.location
    assert rule.status == "documented" and rule.value == POINT
    assert rule.candidates[0].role == "located_fault_point"
    assert model.status == "unknown" and model.candidates == []


@pytest.mark.parametrize("text", [
    "Location: " + POINT,
    RFO + "\nMeasurements are ongoing to locate the cut.",
    RFO.replace("Fiber cut caused by damage", "No fault was identified"),
    RFO.replace("Fiber cut caused by damage", "No fiber cut was found"),
    RFO.replace(POINT, "Between our central equipment and the client, SYN-Country"),
])
def test_pending_or_contextless_rfo_is_not_a_fault_point(server, sample, text):
    ctx = context(sample, text)
    result = model_result(server, ctx, "location", text, {"role": "located_fault_point"})
    assert RulesProvider().extract(ctx).elements.location.status == "unknown"
    assert result.elements.location.status == "unknown"


@pytest.mark.parametrize("role,key", [("quoted", "diagnosis"), ("original", "device_location"), ("original", "a_end")])
def test_source_roles_still_block_location_upgrade(server, sample, role, key):
    ctx = context(sample, RFO, role=role, key=key)
    result = model_result(server, ctx, "location", POINT, {"role": "located_fault_point"})
    assert RulesProvider().extract(ctx).elements.location.status == "unknown"
    assert result.elements.location.status == "unknown"


def test_claim_cannot_transfer_to_an_unrelated_party_in_same_sentence(server, sample):
    ctx = context(sample, "请联系 SYN-运营商甲，此单办结（客户原因）")
    result = model_result(server, ctx, "responsible_party", "SYN-运营商甲", {"basis": "claimed"})
    assert result.elements.responsible_party.status == "unknown"


def test_conflicting_explicit_claims_are_not_auto_selected(server, sample):
    ctx = context(sample, "责任归属：SYN-甲。责任归属：SYN-乙。")
    data = empty_extraction()
    data["elements"]["responsible_party"]["candidates"] = [dict(
        id=f"C{i}", party=f"SYN-{party}", basis="inferred_from_role", attribution="unknown",
        evidence_refs=[ctx.evidence[0].id]) for i, party in enumerate(["甲", "乙"], 1)]
    server.default = envelope(data)
    result = OpenAICompatibleTextProvider(qwen_config(server)).extract(ctx)
    assert result.elements.responsible_party.status == "unknown"
    assert result.suggestions[0].original == data["elements"]["responsible_party"]
    assert result.elements.responsible_party.value is None


@pytest.mark.parametrize("excerpt", ["告警位置：SYN-机房", "SYN-Node-A"])
def test_rfo_cannot_transfer_role_to_alarm_or_single_node(server, sample, excerpt):
    ctx = context(sample, "告警位置：SYN-机房 " + RFO.replace("\n", " "))
    el = model_result(server, ctx, "location", excerpt, {"role": "located_fault_point"}).elements.location
    assert el.status == "unknown" and el.value is None


def test_rule_keeps_all_distinct_claims_in_one_span(sample):
    ctx = context(sample, "责任归属：SYN-甲。责任归属：SYN-乙。")
    el = RulesProvider().extract(ctx).elements.responsible_party
    assert el.status == "conflicted" and el.value is None
    assert len(el.candidates) == 2


def test_rule_keeps_all_rfo_points_in_one_span(sample):
    ctx = context(sample, RFO + "\n" + RFO.replace("SYN-Node-A", "SYN-Node-C"))
    el = RulesProvider().extract(ctx).elements.location
    assert el.status == "conflicted" and el.value is None
    assert len(el.candidates) == 2


def test_long_rfo_excerpt_uses_only_complete_point(server, sample):
    ctx = context(sample, RFO)
    el = model_result(server, ctx, "location", RFO, {"role": "located_fault_point"}).elements.location
    assert el.value is None and el.candidates == []
