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
