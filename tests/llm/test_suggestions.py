"""建议保留原业务判断；本地只核验来源与引用。"""
from copy import deepcopy

import pytest

from noc7.extract.types import ExtractionContext
from noc7.providers.text_config import TextProviderError
from noc7.providers.text_http import OpenAICompatibleTextProvider
from noc7.quote_match import match_quote
from noc7.rules import ExtractionRejected, validate_extraction
from noc7.schema import EvidenceSpan, FieldLocator

from .conftest import envelope
from .test_evidence import empty_extraction


def suggestion_case(sample, text="距 SYN-A 12 公里，尚待定位。", excerpt=None, refs=None):
    span = EvidenceSpan(id="M01/f:diagnosis", material_id="M01", text=text,
                        locator=FieldLocator(field_key="diagnosis"), extractor="synthetic")
    ctx = ExtractionContext(sample[0].bundle, [span])
    payload = empty_extraction()
    payload["elements"]["location"] = dict(status="confirmed", value=excerpt or text,
        selected="same id with spaces", evidence_refs=refs if refs is not None else [span.id],
        candidates=[dict(id="same id with spaces", description=excerpt or text,
            role="custom_model_role", granularity="distance", attribution="vendor",
            evidence_refs=refs if refs is not None else [span.id])])
    return ctx, payload


def decode(ctx, payload):
    return OpenAICompatibleTextProvider._decode(envelope(payload), ctx)


@pytest.mark.parametrize("text", ["距 SYN-A 12 公里。", "坐标 12.3, 45.6。", "不是 SYN-A 故障，待定位。", "告警位置：SYN-A。"])
def test_original_business_labels_and_value_are_retained_without_formal_upgrade(sample, text):
    ctx, payload = suggestion_case(sample, text)
    result = decode(ctx, payload)
    assert result.suggestions[1].original == payload["elements"]["location"]
    assert result.suggestions[1].checks[0].status == "strict"
    assert result.elements.location.status == "unknown"
    assert result.elements.location.value is None and result.elements.location.candidates == []
    assert result.elements.responsible_party.value is None


def test_mismatch_is_visible_and_exclusive_explicit_quote_is_pending(sample):
    ctx, payload = suggestion_case(sample, excerpt="距 SYN-A 99 公里。")
    payload["quotes"] = [dict(evidence_id=ctx.evidence[0].id, quote="不存在的模型引文")]
    result = decode(ctx, payload)
    assert all(c.status == "mismatch" for c in result.suggestions[1].checks)
    assert result.quotes == []
    validate_extraction(ctx, result)


def test_shared_source_explicit_quote_still_rejects_formal_mismatch(sample):
    ctx, payload = suggestion_case(sample)
    ref = ctx.evidence[0].id
    payload["events"] = [dict(id="EV1", action=ctx.evidence[0].text, event_kind="communication",
                              attribution="vendor", evidence_refs=[ref])]
    payload["quotes"] = [dict(evidence_id=ref, quote="凭空捏造")]
    with pytest.raises(ExtractionRejected):
        decode(ctx, payload)


@pytest.mark.parametrize("refs", [[], ["M99/forged"], ["bad ref"]])
def test_missing_or_unknown_suggestion_source_rejects(sample, refs):
    ctx, payload = suggestion_case(sample, refs=refs)
    with pytest.raises(ExtractionRejected):
        decode(ctx, payload)


def test_value_without_candidate_is_preserved_as_unverified(sample):
    ctx, payload = suggestion_case(sample)
    payload["elements"]["location"]["candidates"] = []
    result = decode(ctx, payload)
    assert result.suggestions[1].original == payload["elements"]["location"]
    assert result.elements.location.value is None


@pytest.mark.parametrize("key", ["review", "checks", "quote_checks", "suggestions"])
def test_model_cannot_forge_local_checks_or_review(sample, key):
    ctx, payload = suggestion_case(sample)
    payload["elements"]["location"][key] = []
    with pytest.raises(TextProviderError):
        decode(ctx, payload)


def test_whitespace_event_and_step_do_not_reject_the_ticket(sample):
    ctx, payload = suggestion_case(sample, "已联系\u00a0\u00a0现场\t核查。")
    ref = ctx.evidence[0].id
    payload["events"] = [dict(id="EV1", action="已联系 现场 核查。", event_kind="communication",
                              attribution="vendor", evidence_refs=[ref])]
    payload["elements"]["handling_process"] = dict(status="documented", evidence_refs=[ref], value=[
        dict(id="C1", action="已联系 现场 核查。", step_kind="communication", attribution="vendor", evidence_refs=[ref])])
    result = decode(ctx, payload)
    assert len([c for c in result.quote_checks if c.status == "whitespace"]) == 2
    for check in result.quote_checks:
        assert check.original == ctx.evidence[0].text[check.start:check.end]
    changed = deepcopy(payload)
    changed["events"][0]["action"] = "尚未联系 现场 核查。"
    with pytest.raises(ExtractionRejected):
        decode(ctx, changed)


@pytest.mark.parametrize("quote,source,status", [
    ("A B", "xxA\u00a0Bzz", "whitespace"), ("A B", "A\n\tB", "whitespace"),
    ("A B", "A B", "strict"), ("A B", "AB", "mismatch"),
    ("12 km", "12 m", "mismatch"), ("A B", "a B", "mismatch"),
    ("未故障", "故障", "mismatch"), ("a,b", "a，b", "mismatch"), (" ", " ", "mismatch"),
])
def test_quote_matching_changes_only_whitespace(quote, source, status):
    match = match_quote(quote, source)
    assert match.status == status
    if status != "mismatch":
        assert match.original == source[match.start:match.end]
