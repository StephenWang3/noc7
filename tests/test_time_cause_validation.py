"""离线验证输入绑定不可因重名、重复审计或篡改证据而猜选。"""
import importlib.util
import json
from pathlib import Path

import pytest

from noc7.bundle import load_bundle
from noc7.providers.text_replay import evidence_digest
from noc7.extract.types import ExtractionContext

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('time_cause_check',ROOT/'scripts/check_time_cause.py')
checker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def baseline(tmp_path):
    from noc7.extract.pipeline import analyze_with_context
    from tests.a1.conftest import text_registry
    path=ROOT/'fixtures/bundles/SYN-S01'
    _,ctx,_=analyze_with_context(path,registry=text_registry())
    from noc7.providers.text_prompt import prepare_evidence
    clean,request=prepare_evidence(ctx)
    binding=dict(alias='F01',source=str(path),bundle_sha256=ctx.bundle.manifest_sha256)
    (tmp_path/'mapping.json').write_text(json.dumps([binding]))
    audit=tmp_path/'F01/audit';audit.mkdir(parents=True)
    record=dict(bundle_sha256=ctx.bundle.manifest_sha256,evidence_sha256=evidence_digest(clean),
                request_evidence=request,raw_response='{"saved":"synthetic"}')
    (audit/'one.json').write_text(json.dumps(record))
    return record,audit


def test_unique_response_and_hashes(tmp_path):
    baseline(tmp_path)
    assert len(checker.load_inputs(tmp_path))==1


@pytest.mark.parametrize('fault',['duplicate','evidence','bundle'])
def test_reject_ambiguous_or_changed_baseline(tmp_path,fault):
    record,audit=baseline(tmp_path)
    if fault=='duplicate':
        (audit/'two.json').write_text(json.dumps(record))
    else:
        key='evidence_sha256' if fault=='evidence' else 'bundle_sha256'
        record[key]='0'*64
        (audit/'one.json').write_text(json.dumps(record))
    with pytest.raises(ValueError): checker.load_inputs(tmp_path)


def test_independent_numeric_audit_catches_offset_and_precision():
    from types import SimpleNamespace
    from noc7.schema import EvidenceSpan, FieldLocator, TimeCandidate
    span=EvidenceSpan(id='M01/f:occurred_at',material_id='M01',locator=FieldLocator(field_key='occurred_at'),
                      text='2026-01-02 03:04:05+00:00',extractor='synthetic')
    c=TimeCandidate(id='C1',evidence_refs=[span.id],attribution='system_field',time_kind='business_start',
                    time=dict(raw=span.text,iso='2026-01-02T03:04:05+00:00',utc_offset='+00:00',tz_source='explicit',precision='second'))
    result=SimpleNamespace(evidence=[span],elements=SimpleNamespace(start_time=SimpleNamespace(candidates=[c]),end_time=SimpleNamespace(candidates=[])))
    assert checker.independent_time_metrics(result,'+08:00')['counts']=={'match':1}
    c.time=c.time.model_copy(update={'iso':'2026-01-02T03:04:05+08:00','utc_offset':'+08:00'})
    assert checker.independent_time_metrics(result,'+08:00')['counts']=={'mismatch':1}
    c.time=c.time.model_copy(update={'iso':'2026-01-02T03:04:05+00:00','utc_offset':'+00:00','precision':'minute'})
    assert checker.independent_time_metrics(result,'+08:00')['counts']=={'mismatch':1}


@pytest.mark.parametrize('raw,iso,source', [
    ('09/23/2026 12:04 PM UTC','2026-09-23T12:04:00+00:00','explicit'),
    ('23/09/2026 12:04 AM UTC','2026-09-23T00:04:00+00:00','explicit'),
    ('2026-09-23 13:04','2026-09-23T13:04:00+08:00','assumed'),
])
def test_independent_audit_mixed_and_twelve_hour(raw,iso,source):
    from types import SimpleNamespace
    from noc7.schema import EvidenceSpan, FieldLocator, TextRangeLocator, TimeCandidate
    field=EvidenceSpan(id='M01/f:recovered_at',material_id='M01',locator=FieldLocator(field_key='recovered_at'),text=raw,extractor='synthetic')
    body=field.model_copy(update={'id':'M01/t:1','locator':TextRangeLocator(line=1),'text':'另一条记录'})
    c=TimeCandidate(id='C1',evidence_refs=[field.id,body.id],attribution='system_field',time_kind='business_recovery',
                    time=dict(raw=raw,iso=iso,utc_offset=iso[-6:],tz_source=source,precision='minute'))
    result=SimpleNamespace(evidence=[field,body],elements=SimpleNamespace(start_time=SimpleNamespace(candidates=[]),end_time=SimpleNamespace(candidates=[c])))
    assert checker.independent_time_metrics(result,'+08:00')['counts']=={'match':1}
    c.time=c.time.model_copy(update={'iso':iso.replace('2026-09-23','2026-09-24')})
    assert checker.independent_time_metrics(result,'+08:00')['counts']=={'mismatch':1}


def comparison_fixture(tmp_path):
    import hashlib
    record,_=baseline(tmp_path)
    inputs=checker.load_inputs(tmp_path)
    bundle=inputs[0][1]
    # 该夹具模拟拒绝单，确认比较不要求它有成功报告。
    bindings=[dict(alias='F01',bundle_sha256=bundle.manifest_sha256,evidence_sha256=record['evidence_sha256'],
                   response_sha256=hashlib.sha256(record['raw_response'].encode()).hexdigest())]
    (tmp_path/'source-binding.json').write_text(json.dumps(bindings))
    (tmp_path/'run.json').write_text(json.dumps([dict(alias='F01',status='rejected')]))
    return inputs,bindings


@pytest.mark.parametrize('fault',['response','missing','duplicate'])
def test_comparison_binding_rejects_mismatched_or_ambiguous(tmp_path,fault):
    inputs,bindings=comparison_fixture(tmp_path)
    if fault=='response': bindings[0]['response_sha256']='0'*64
    if fault=='missing': bindings=[]
    if fault=='duplicate': bindings=bindings+bindings
    (tmp_path/'source-binding.json').write_text(json.dumps(bindings))
    with pytest.raises(ValueError): checker.load_comparison(tmp_path,inputs)


def test_comparison_rejected_stays_in_denominator(tmp_path):
    inputs,_=comparison_fixture(tmp_path)
    previous=checker.load_comparison(tmp_path,inputs)
    inputs[0][0]['closed']=True
    summary=checker.comparison_summary(inputs,previous,[dict(alias='F01',status='rejected')])
    assert summary['closed']['total']==1
    assert summary['closed']['before_ok']==summary['closed']['after_ok']==0
    assert summary['closed']['elements']['end_time']==dict(before=0,after=0,added=0,removed=0)


def test_independent_audit_does_not_override_field_with_conflicting_anchor():
    from types import SimpleNamespace as NS
    from noc7.schema import EvidenceSpan, FieldLocator
    raw='2026-09-23 13:04'
    field=EvidenceSpan(id='M01/f:recovered_at',material_id='M01',locator=FieldLocator(field_key='recovered_at'),text=raw,extractor='synthetic')
    time=NS(raw=raw,iso=None,precision=None,utc_offset=None,tz_source='unknown')
    c=NS(id='C1',time=time,evidence_refs=[field.id],relation=NS(timezone_anchor=NS(quote='UTC')))
    result=NS(evidence=[field],elements=NS(start_time=NS(candidates=[]),end_time=NS(candidates=[c])))
    assert checker.independent_time_metrics(result,'+08:00')['counts']=={'match':1}
    time.iso='2026-09-23T13:04:00+00:00';time.precision='minute';time.utc_offset='+00:00';time.tz_source='explicit'
    assert checker.independent_time_metrics(result,'+08:00')['counts']=={'mismatch':1}


@pytest.mark.parametrize('raw,iso,precision,source,zone', [
    ('2026-09-23 PM', None, None, 'unknown', None),
    ('2026-09-23 PM UTC', None, None, 'unknown', None),
    ('2026年9月23日 1时04分 PM', '2026-09-23T13:04:00+08:00', 'minute', 'assumed', '+08:00'),
    ('09/23/2026 1:04:05pm UTC', '2026-09-23T13:04:05+00:00', 'second', 'explicit', '+00:00'),
    ('09/23/2026\n8:13:57 PM UTC', '2026-09-23T20:13:57+00:00', 'second', 'explicit', '+00:00'),
    ('09/23/2026\t8:13:57 PM UTC', '2026-09-23T20:13:57+00:00', 'second', 'explicit', '+00:00'),
])
def test_independent_audit_meridiem_boundaries(raw,iso,precision,source,zone):
    from types import SimpleNamespace as NS
    from noc7.schema import EvidenceSpan, FieldLocator
    field = EvidenceSpan(id='M01/f:recovered_at', material_id='M01', locator=FieldLocator(field_key='recovered_at'),
                         text=raw, extractor='synthetic')
    value = NS(raw=raw,iso=iso,precision=precision,tz_source=source,utc_offset=zone)
    c = NS(id='C1',time=value,evidence_refs=[field.id],relation=None)
    result = NS(evidence=[field],elements=NS(start_time=NS(candidates=[]),end_time=NS(candidates=[c])))
    assert checker.independent_time_metrics(result,'+08:00')['counts'] == {'match': 1}
    if iso is None:
        value.iso='2026-09-23'; value.precision='day'
    else:
        value.iso=iso.replace('T13:', 'T01:').replace('T20:', 'T08:')
    assert checker.independent_time_metrics(result,'+08:00')['counts'] == {'mismatch': 1}


def test_new_response_comparison_is_explicit_and_still_checks_evidence(tmp_path):
    root = tmp_path/'baseline'; root.mkdir()
    record, _ = baseline(root)
    inputs = checker.load_inputs(root)
    entry, bundle, _, _ = inputs[0]
    old = tmp_path/'old'; old.mkdir()
    binding = dict(alias=entry['alias'], bundle_sha256=bundle.manifest_sha256,
                   evidence_sha256=record['evidence_sha256'], response_sha256='old-response')
    checker.write(old/'source-binding.json', [binding])
    checker.write(old/'run.json', [dict(alias=entry['alias'], status='rejected')])
    with pytest.raises(ValueError): checker.load_comparison(old, inputs)
    assert checker.load_comparison(old, inputs, new_responses=True)[entry['alias']]['status'] == 'rejected'
    binding['evidence_sha256'] = 'changed'
    checker.write(old/'source-binding.json', [binding])
    with pytest.raises(ValueError): checker.load_comparison(old, inputs, new_responses=True)


def test_closed_filter_does_not_load_other_responses(tmp_path):
    record, _ = baseline(tmp_path)
    rows = checker.read(tmp_path/'mapping.json')
    rows[0]['closed'] = True
    checker.write(tmp_path/'mapping.json', [*rows, dict(alias='absent', closed=False, source='does-not-exist')])
    assert len(checker.load_inputs(tmp_path, closed_only=True)) == 1
    from noc7.bundle import BundleError
    with pytest.raises(BundleError):
        checker.load_inputs(tmp_path)


@pytest.mark.parametrize('outcome,allowed', [('http_error', True), ('transport_error', True), ('response_too_large', True), ('request_prepared', False)])
def test_offline_failure_requires_unique_terminal_audit(tmp_path, outcome, allowed):
    record, audit = baseline(tmp_path)
    record.pop('raw_response')
    record['outcome'] = outcome
    checker.write(audit/'one.json', record)
    with pytest.raises(ValueError): checker.load_inputs(tmp_path)
    if allowed:
        inputs = checker.load_inputs(tmp_path, keep_request_failures=True)
        assert len(inputs) == 1
        assert checker.response_digest(inputs[0][2]) is None
        checker.write(audit/'duplicate.json', record)
        with pytest.raises(ValueError): checker.load_inputs(tmp_path, keep_request_failures=True)
    else:
        with pytest.raises(ValueError): checker.load_inputs(tmp_path, keep_request_failures=True)


def test_empty_http_body_is_a_saved_response_not_missing_request(tmp_path):
    record, audit = baseline(tmp_path)
    record.update(raw_response='', outcome='rejected')
    checker.write(audit/'one.json', record)
    inputs = checker.load_inputs(tmp_path, keep_request_failures=True)
    assert checker.response_digest(inputs[0][2]) is not None


@pytest.mark.parametrize('events,expected_count,reason', [
    ([402, 'ok'], 1, 'http_402'),
    ([503, 'invalid', 503, 'ok'], 3, 'three_consecutive_503_or_invalid'),
    (['invalid', 'invalid', 'invalid', 'ok'], 3, 'three_consecutive_503_or_invalid'),
    ([503, 'ok', 'invalid', 503, 'invalid', 'ok'], 5, 'three_consecutive_503_or_invalid'),
    ([503, 'transport', 'invalid', 'ok'], 4, None),
])
def test_conservative_run_stops_before_starting_next_case(events, expected_count, reason):
    inputs = [(dict(alias=f'F{i:02d}'), None, None, None) for i in range(len(events))]
    called, checkpoints = [], []
    def run(item):
        index = len(called); called.append(item[0]['alias'])
        event = events[index]
        return dict(alias=item[0]['alias'], request_count=1, response_invalid=event=='invalid',
                    http_status=event if isinstance(event, int) else None)
    rows, control = checker.run_conservative(inputs, run, lambda rows, state: checkpoints.append(dict(state)))
    assert len(called) == len(rows) == control['model_requests'] == expected_count
    assert control['stop_reason'] == reason
    assert control['not_started'] == [item[0]['alias'] for item in inputs[expected_count:]]
    assert len(checkpoints) == expected_count
    assert checkpoints[-1] == control


def test_attempted_subset_does_not_load_unstarted_audits(tmp_path):
    record, _ = baseline(tmp_path)
    entries = checker.read(tmp_path/'mapping.json')
    entries[0]['closed'] = True
    checker.write(tmp_path/'mapping.json', [*entries, dict(alias='not-started', closed=True, source='absent')])
    checker.write(tmp_path/'run.json', [dict(alias='F01', request_count=1)])
    aliases = checker.attempted_aliases(tmp_path)
    assert aliases == {'F01'}
    assert len(checker.load_inputs(tmp_path, aliases=aliases)) == 1
    with pytest.raises(ValueError): checker.load_inputs(tmp_path, aliases={'not-in-map'})
