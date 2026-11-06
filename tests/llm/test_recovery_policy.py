"""业务确认的恢复取值边界；输入全部为合成证据。"""
from copy import deepcopy

import pytest

from noc7.extract.types import ExtractionContext
from noc7.providers.recovery_policy import initial_selection
from noc7.rules import ExtractionRejected, validate_extraction
from noc7.schema import SpanRole
from tests.llm.test_semantic_constraints import build, decode


def recovery(sample, specs, selected='C1'):
    ctx, data = build(sample, name='end_time', kind='business_recovery')
    template = data['elements']['end_time']['candidates'][0]
    candidates, spans = [], []
    for i, (source, raw) in enumerate(specs, 1):
        c = deepcopy(template)
        span = ctx.evidence[0].model_copy(update={'id': f'M01/t:{i}', 'text': f'{source} 本次业务恢复于 {raw}'})
        q = dict(evidence_id=span.id, quote=span.text)
        c.update(id=f'C{i}', evidence_refs=[span.id], time=dict(raw=raw))
        c['relation'].update(context=[q], recovery_source=source, recovery_source_basis=q)
        candidates.append(c); spans.append(span)
    el = data['elements']['end_time']
    el.update(candidates=candidates, status='unknown', value=None, selected=None, evidence_refs=[])
    if selected:
        chosen = next(c for c in candidates if c['id'] == selected)
        el.update(status='documented', value=chosen['time'], selected=selected, evidence_refs=chosen['evidence_refs'])
    return ExtractionContext(ctx.bundle, spans), data


def at(clock):
    return '2026-01-02 ' + clock + '+00:00'


@pytest.mark.parametrize('specs,chosen,status', [
    ([('customer', at('10:30:00')), ('vendor_rfo', at('10:00:00'))], 'C2', 'documented'),
    ([('customer', at('10:30:01')), ('vendor_rfo', at('10:00:00'))], 'C1', 'documented'),
    ([('customer', at('10:40:00')), ('vendor_rfo', at('10:20:00')), ('unicom_monitor', at('10:00:00'))], 'C1', 'documented'),
    ([('vendor_rfo', at('11:00:00')), ('unicom_monitor', at('10:00:00'))], 'C1', 'documented'),
    ([('unicom_monitor', at('10:00:00'))], 'C1', 'documented'),
    ([('unknown', at('10:00:00'))], None, 'unknown'),
    ([('customer', at('10:00:00')), ('customer', at('11:00:00')), ('vendor_rfo', at('10:20:00'))], None, 'conflicted'),
    ([('customer', at('10:00:00')), ('vendor_rfo', at('11:00:00')), ('vendor_rfo', at('12:00:00'))], 'C1', 'documented'),
    ([('customer', at('10:00:00')), ('customer', at('10:00:00'))], 'C1', 'documented'),
    ([('customer', at('10:30:00')), ('customer', at('10:00:00')), ('vendor_rfo', at('09:00:00'))], 'C2', 'documented'),
])
def test_business_selection_matrix(sample, specs, chosen, status):
    ctx, data = recovery(sample, specs)
    result = decode(ctx, data)
    assert result.elements.end_time.selected == chosen
    assert result.elements.end_time.status == status
    assert len(result.elements.end_time.candidates) == len(specs)
    assert result.semantic_assessment.recovery_selection.selected == chosen
    if len(specs) == 3 and specs[1][0] == specs[2][0] == 'vendor_rfo':
        assert result.semantic_assessment.recovery_selection.source_conflicts == ['vendor_rfo']
    validate_extraction(ctx, result)


@pytest.mark.parametrize('value', ['NaN', 'inf', '-1', 'wrong', ''])
def test_invalid_threshold_fails(value, monkeypatch):
    monkeypatch.setenv('NOC7_RECOVERY_CLOSE_MINUTES', value)
    with pytest.raises(ValueError, match='有限非负数'):
        initial_selection()


def test_frozen_threshold_replay_and_record_tampering(sample, monkeypatch):
    ctx, data = recovery(sample, [('customer', at('10:20:00')), ('vendor_rfo', at('10:00:00'))])
    monkeypatch.setenv('NOC7_RECOVERY_CLOSE_MINUTES', '10')
    result = decode(ctx, data)
    assert result.elements.end_time.selected == 'C1'
    monkeypatch.setenv('NOC7_RECOVERY_CLOSE_MINUTES', '30')
    validate_extraction(ctx, result)
    assert result.semantic_assessment.recovery_selection.threshold_minutes == 10
    assert decode(ctx, data).elements.end_time.selected == 'C2'
    result.semantic_assessment.recovery_selection.reason = '伪造裁决理由'
    with pytest.raises(ExtractionRejected):
        validate_extraction(ctx, result)


def test_zero_threshold_and_same_instant_different_zone(sample, monkeypatch):
    monkeypatch.setenv('NOC7_RECOVERY_CLOSE_MINUTES', '0')
    ctx, data = recovery(sample, [('customer', at('10:00:00')), ('vendor_rfo', '2026-01-02 18:00:00+08:00')])
    result = decode(ctx, data)
    assert result.elements.end_time.selected == 'C1'
    assert result.semantic_assessment.recovery_selection.span_seconds == 0


@pytest.mark.parametrize('field', ['recovery_source_basis', 'correction_basis'])
@pytest.mark.parametrize('bad', ['missing', 'mismatch', 'malformed'])
def test_source_quotes_cannot_hide_after_repair(sample, field, bad):
    ctx, data = recovery(sample, [('customer', at('10:00:00'))])
    q = dict(evidence_id='M99/absent' if bad == 'missing' else ctx.evidence[0].id,
             quote='不存在的内容' if bad != 'missing' else '内容')
    r = data['elements']['end_time']['candidates'][0]['relation']
    r[field] = q
    if bad == 'malformed':
        r.pop('modality')
    with pytest.raises(ExtractionRejected):
        decode(ctx, data)


@pytest.mark.parametrize('change', [
    dict(recovery_source_basis=None), dict(recovery_source='unknown'),
])
def test_source_missing_does_not_fall_back_to_field(sample, change):
    ctx, data = recovery(sample, [('customer', at('10:00:00'))])
    data['elements']['end_time']['candidates'][0]['relation'].update(change)
    result = decode(ctx, data)
    assert result.elements.end_time.value is None
    assert result.elements.end_time.candidates[0].time.iso is not None


@pytest.mark.parametrize('role,needs_review', [('derived_summary', False), ('signature', False), ('original', True)])
def test_source_basis_quality_gates(sample, role, needs_review):
    ctx, data = recovery(sample, [('customer', at('10:00:00'))])
    basis = ctx.evidence[0].model_copy(update={'id':'M01/t:basis', 'role':SpanRole(role), 'needs_review':needs_review})
    data['elements']['end_time']['candidates'][0]['relation']['recovery_source_basis'] = dict(evidence_id=basis.id, quote=basis.text)
    ctx = ExtractionContext(ctx.bundle, [*ctx.evidence, basis])
    assert decode(ctx, data).elements.end_time.value is None


@pytest.mark.parametrize('kind', ['protocol_up', 'confirmation_action', 'repair_completed'])
def test_source_priority_cannot_promote_other_time_purposes(sample, kind):
    ctx, data = recovery(sample, [('customer', at('10:00:00'))])
    data['elements']['end_time']['candidates'][0]['time_kind'] = kind
    assert decode(ctx, data).elements.end_time.value is None


@pytest.mark.parametrize('field', ['event_id', 'scope', 'recovery_round'])
def test_groups_never_mix_and_model_group_stable_on_revalidation(sample, field):
    ctx, data = recovery(sample, [('vendor_rfo', at('10:00:00')), ('customer', at('09:00:00'))])
    data['elements']['end_time']['candidates'][1]['relation'][field] = 'other'
    result = decode(ctx, data)
    assert result.elements.end_time.selected == 'C1'
    validate_extraction(ctx, result)
    el = data['elements']['end_time']
    el.update(selected=None, value=None, status='unknown')
    assert decode(ctx, data).elements.end_time.value is None


def test_single_group_can_select_without_model_selection(sample):
    ctx, data = recovery(sample, [('vendor_rfo', at('10:00:00'))], selected=None)
    assert decode(ctx, data).elements.end_time.selected == 'C1'


@pytest.mark.parametrize('fault', [None, 'missing_basis', 'cycle', 'other_source', 'missing_id'])
def test_explicit_correction_only_with_basis_same_source_and_acyclic(sample, fault):
    second_source = 'vendor_rfo' if fault == 'other_source' else 'customer'
    ctx, data = recovery(sample, [('customer', at('10:00:00')), (second_source, at('12:00:00'))])
    a, b = data['elements']['end_time']['candidates']
    b['relation'].update(supersedes=['C1'], correction_basis=deepcopy(b['relation']['context'][0]))
    if fault == 'missing_basis': b['relation']['correction_basis'] = None
    if fault == 'cycle': a['relation'].update(supersedes=['C2'], correction_basis=deepcopy(a['relation']['context'][0]))
    if fault == 'missing_id': b['relation']['supersedes'] = ['C99']
    result = decode(ctx, data)
    if fault is None:
        assert result.elements.end_time.selected == 'C2'
        assert 'C1' in result.semantic_assessment.recovery_selection.excluded
    elif fault == 'other_source':
        assert result.elements.end_time.selected == 'C1'
        assert result.elements.end_time.value.iso == '2026-01-02T10:00:00+00:00'
        assert '忽略该链接' in result.semantic_assessment.recovery_selection.excluded['C2']
    else:
        assert result.elements.end_time.status == 'conflicted'


def test_no_source_cannot_be_inferred_from_attribution_or_title(sample):
    ctx, data = recovery(sample, [('unknown', at('10:00:00'))])
    c = data['elements']['end_time']['candidates'][0]
    c['attribution'] = 'customer'
    c['note'] = 'RFO'
    assert decode(ctx, data).elements.end_time.value is None


def test_report_explains_selection_and_threshold(sample):
    from noc7.extract.pipeline import analyze
    from noc7.report import render
    from noc7.report.company import build_company_report
    from tests.a1.conftest import text_registry
    from tests.llm.conftest import BUNDLES
    ctx, data = recovery(sample, [('vendor_rfo', at('10:00:00'))])
    extraction = decode(ctx, data)
    result = analyze(BUNDLES/'SYN-S01', registry=text_registry()).model_copy(update=dict(
        evidence=ctx.evidence, elements=extraction.elements, semantic_assessment=extraction.semantic_assessment,
        suggestions=[], events=[], quote_checks=extraction.quote_checks, issues=[], service_identity=None))
    assert '待业务方确认' in render(result)
    assert '恢复时间业务取值' in render(result, format='md') and '待业务方确认' in render(result, format='md')
    text = str(build_company_report(result).cells['resumed'])
    assert '供应商 RFO' in text and '待业务方确认' in text


def test_model_cannot_inject_recovery_selection(sample):
    from noc7.providers.text_config import TextProviderError
    ctx, data = recovery(sample, [('customer', at('10:00:00'))])
    data['recovery_selection'] = dict(threshold_minutes=100)
    with pytest.raises(TextProviderError):
        decode(ctx, data)


def test_recovery_before_start_is_withdrawn_without_lower_source_fallback(sample):
    start_ctx, start_data = build(sample, raw=at('11:00:00'))
    ctx, data = recovery(sample, [('customer', at('10:00:00')), ('vendor_rfo', at('12:00:00'))])
    data['elements']['start_time'] = start_data['elements']['start_time']
    ctx = ExtractionContext(ctx.bundle, [*ctx.evidence, *start_ctx.evidence])
    result = decode(ctx, data)
    assert result.elements.start_time.value
    assert result.elements.end_time.value is None
    assert result.semantic_assessment.recovery_selection.selected is None
    assert '早于业务起点' in result.semantic_assessment.recovery_selection.reason
    validate_extraction(ctx, result)


@pytest.mark.parametrize('old,new', [('1', '2'), ('bad id', 'C1')])
def test_correction_candidate_ids_remapped_together(sample, old, new):
    ctx, data = recovery(sample, [('customer', at('10:00:00')), ('customer', at('12:00:00'))])
    el = data['elements']['end_time']
    a, b = el['candidates']
    a['id'], b['id'], el['selected'] = old, new, old
    b['relation'].update(supersedes=[old], correction_basis=deepcopy(b['relation']['context'][0]))
    result = decode(ctx, data)
    assert result.elements.end_time.value.iso == '2026-01-02T12:00:00+00:00'
    a, b = result.elements.end_time.candidates
    assert b.relation.supersedes == [a.id]


def test_old_saved_result_stays_legacy_but_raw_redecode_does_not_invent_source(sample):
    from tests.llm.conftest import envelope
    from noc7.providers.text_http import OpenAICompatibleTextProvider
    ctx, data = recovery(sample, [('unknown', at('10:00:00'))])
    legacy = OpenAICompatibleTextProvider._decode_payload(envelope(data), ctx, legacy_recovery=True)
    assert legacy.elements.end_time.value is not None
    assert legacy.semantic_assessment.recovery_selection is None
    validate_extraction(ctx, legacy)
    assert decode(ctx, data).elements.end_time.value is None


def test_correction_ambiguous_ids_never_resolve_by_generated_number(sample):
    ctx, data = recovery(sample, [('customer', at('10:00:00')), ('customer', at('12:00:00'))])
    a, b = data['elements']['end_time']['candidates']
    a['id'] = b['id'] = 'duplicate'
    data['elements']['end_time']['selected'] = 'duplicate'
    b['relation'].update(supersedes=['duplicate'], correction_basis=deepcopy(b['relation']['context'][0]))
    result = decode(ctx, data)
    assert result.elements.end_time.value is None
    assert result.elements.end_time.candidates[1].relation.supersedes == ['unresolved correction']


@pytest.mark.parametrize('raw', ['10:00 UTC', '2026-01-02', '2026-01-02 10:00'])
def test_source_does_not_supply_missing_date_precision_or_timezone(sample, raw):
    from noc7.schema import TextRangeLocator
    ctx, data = recovery(sample, [('customer', raw)])
    ctx = ExtractionContext(ctx.bundle, [s.model_copy(update={'locator':TextRangeLocator(line=1)}) for s in ctx.evidence])
    result = decode(ctx, data)
    assert result.elements.end_time.value is None
    assert len(result.elements.end_time.candidates) == 1


def test_invalid_threshold_preflight_fails_before_network_or_key_read(monkeypatch):
    from pathlib import Path
    from noc7.providers.text_config import load_model_config, TextProviderError
    from noc7.providers.text_http import OpenAICompatibleTextProvider
    from noc7.schema import DataClass
    config = load_model_config(Path(__file__).resolve().parents[2]/'config/models/deepseek.json')
    monkeypatch.setenv('NOC7_RECOVERY_CLOSE_MINUTES', 'NaN')
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    with pytest.raises(TextProviderError, match='有限非负数'):
        OpenAICompatibleTextProvider(config).preflight(DataClass.SYNTHETIC)


def test_final_relation_missing_source_rejected_even_without_original_copy(sample):
    ctx, data = recovery(sample, [('customer', at('10:00:00'))])
    result = decode(ctx, data)
    result.semantic_assessment.original = {}
    result.elements.end_time.candidates[0].relation.recovery_source_basis.evidence_id = 'M99/absent'
    with pytest.raises(ExtractionRejected) as exc:
        validate_extraction(ctx, result)
    assert 'EVIDENCE_REF_MISSING' in [i.code for i in exc.value.issues]


def test_ineligible_correction_cannot_revive_superseded_old_time(sample):
    from noc7.schema import TextRangeLocator
    ctx, data = recovery(sample, [('customer', at('10:00:00')), ('customer', '2026-01-02 12:00')])
    ctx = ExtractionContext(ctx.bundle, [s.model_copy(update={'locator':TextRangeLocator(line=1)}) for s in ctx.evidence])
    b = data['elements']['end_time']['candidates'][1]
    b['relation'].update(supersedes=['C1'], correction_basis=deepcopy(b['relation']['context'][0]))
    result = decode(ctx, data)
    assert result.elements.end_time.value is None
    assert '更正候选' in result.semantic_assessment.recovery_selection.reason


@pytest.mark.parametrize('fault', ['missing_basis', 'missing_id', 'other_source', 'self'])
@pytest.mark.parametrize('minutes', [10, 30])
def test_invalid_correction_within_threshold_keeps_both_times(sample, fault, minutes):
    second_source = 'vendor_rfo' if fault == 'other_source' else 'customer'
    ctx, data = recovery(sample, [('customer', at('10:00:00')), (second_source, at(f'10:{minutes:02d}:00'))])
    a, b = data['elements']['end_time']['candidates']
    # 无效链接挂在较早候选上，也不能剥夺它被选中的资格。
    a['relation'].update(supersedes=['C2'], correction_basis=deepcopy(a['relation']['context'][0]))
    if fault == 'missing_basis': a['relation']['correction_basis'] = None
    if fault == 'missing_id': a['relation']['supersedes'] = ['C99']
    if fault == 'self': a['relation']['supersedes'] = ['C1']
    result = decode(ctx, data)
    record = result.semantic_assessment.recovery_selection
    assert result.elements.end_time.selected == 'C1'
    assert record.participating == ['C1', 'C2']
    assert record.span_seconds == minutes * 60
    assert '忽略该链接' in record.excluded['C1']
    validate_extraction(ctx, result)


@pytest.mark.parametrize('source,text', [
    ('customer', '客户报告本次业务于 2026-09-03 10:00 UTC 恢复。'),
    ('vendor_rfo', '供应商 RFO 正文：本次业务恢复时间为 2026-09-03 10:00 UTC。'),
    ('unicom_monitor', '联通追加记录：本次线路恢复时间为 2026-09-03 10:00 UTC。'),
])
def test_prompt_example_cross_evidence_source_is_usable(sample, source, text):
    from noc7.providers.text_prompt import EXAMPLE
    from noc7.schema import EvidenceSpan, FieldLocator, TextRangeLocator
    ctx, data = build(sample)
    end = deepcopy(EXAMPLE['elements']['end_time'])
    candidate = end['candidates'][0]
    relation = candidate['relation']
    relation.update(recovery_source=source, recovery_source_basis=dict(evidence_id='M02/log:3', quote=text))
    data['elements']['start_time'] = dict(status='unknown', value=None, selected=None, evidence_refs=[], candidates=[])
    data['elements']['end_time'] = end
    spans = [EvidenceSpan(id='M01/f:recovered_at', material_id='M01', locator=FieldLocator(field_key='recovered_at'),
                          text=candidate['time']['raw'], extractor='synthetic'),
             EvidenceSpan(id='M02/log:3', material_id='M02', locator=TextRangeLocator(line=1), text=text, extractor='synthetic')]
    ctx = ExtractionContext(ctx.bundle, spans)
    result = decode(ctx, data)
    assert result.elements.end_time.selected == 'C1'
    assert result.elements.end_time.value.iso == '2026-09-03T10:00:00+00:00'
    assert result.elements.end_time.candidates[0].relation.recovery_source == source
    assert result.elements.end_time.evidence_refs == ['M01/f:recovered_at', 'M02/log:3']
    validate_extraction(ctx, result)
