"""冻结反例驱动的完整解码、证据校验和报告回归。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from noc7.extract.types import ExtractionContext
from noc7.providers.text_http import OpenAICompatibleTextProvider
from noc7.rules import ExtractionRejected, validate_extraction
from noc7.schema import EvidenceSpan, FieldLocator
from noc7.extract.baseline import time_phrase
from noc7.report import final_duration, render
from noc7.report.company import build_company_report
from tests.llm.conftest import envelope

EXPECTED = json.loads((Path(__file__).parent / "cases/time_cause_expectations.json").read_text())["cases"]


def build(sample, *, raw="2026-01-02 03:04:05+00:00", name="start_time", kind="business_start",
          statement="现场设备故障影响本次业务。", modality="asserted", assertion="fault", field=True):
    data = deepcopy(sample[1])
    for n in ("start_time", "end_time", "cause", "responsible_party", "location"):
        data['elements'][n] = dict(status="unknown", value=None, selected=None, evidence_refs=[], candidates=[])
    data.update(events=[], quotes=[], service_identity=None)
    data['elements']['phenomenon'] = dict(status="unknown", value=None, evidence_refs=[], candidates=[])
    data['elements']['handling_process'] = dict(status="unknown", value=[], evidence_refs=[])
    text = statement if name == "cause" else "本次线路恢复／起障时间：" + raw
    ref = "M01/f:description"
    span = EvidenceSpan(id=ref, material_id="M01", locator=FieldLocator(field_key="description"),
                        text=text, extractor="synthetic")
    if not field:
        from noc7.schema import TextRangeLocator
        span = span.model_copy(update={"locator": TextRangeLocator(line=1)})
    ctx = ExtractionContext(sample[0].bundle, [span])
    relation = dict(event_id="current", scope="本次业务", current_event=True,
                    modality=modality, context=[dict(evidence_id=ref, quote=text)])
    c = dict(id="C1", evidence_refs=[ref], attribution="vendor", relation=relation)
    if name == "cause":
        relation.update(assertion=assertion, affects_service=True, occurred=True, speaker="供应商")
        c.update(statement=statement, cause_kind="root_cause_claimed")
        value = statement
    else:
        c.update(time=dict(raw=raw), time_kind=kind)
        value = dict(raw=raw)
    data['elements'][name] = dict(status="documented", value=value, selected="C1", evidence_refs=[ref], candidates=[c])
    return ctx, data


def decode(ctx, data):
    return OpenAICompatibleTextProvider._decode(envelope(data), ctx)


@pytest.mark.parametrize('label,raw', [
    ('explicit_zero_offset', '2026-01-02 03:04:05+00:00'),
    ('fullwidth_clock', '2026-01-02 03：04'),
    ('english_date', '02 Jan 2026 03:04 UTC'),
])
def test_frozen_normalization(label, raw):
    tv = time_phrase(raw, '+08:00')
    assert tv.iso == EXPECTED[label]
    assert tv.raw == raw


def test_title_and_confirmation_downgrade(sample):
    ctx, data = build(sample, name="cause")
    data['elements']['cause']['value'] = '设备故障'
    data['elements']['cause']['status'] = 'confirmed'
    result = decode(ctx, data)
    assert result.elements.cause.value == '现场设备故障影响本次业务。'
    assert result.elements.cause.status == EXPECTED['title_difference'] == EXPECTED['confirmed_cause']
    assert result.semantic_assessment.original['cause']['value'] == '设备故障'
    assert result.elements.cause.candidates[0].attribution == 'vendor'
    assert any(c.outcome == 'downgraded' for c in result.semantic_assessment.checks)


@pytest.mark.parametrize('label,updates', [
    ('suspected_mechanism', dict(name='cause', modality='suspected', assertion='mechanism')),
    ('self_recovery', dict(name='cause', assertion='recovery')),
    ('alarm_start', dict(kind='alarm_raised')),
    ('protocol_down', dict(kind='protocol_down')),
    ('confirmation_action', dict(name='end_time', kind='confirmation_action')),
    ('missing_date', dict(raw='03：04')),
    ('unknown_timezone', dict(raw='2026-01-02 03:04', field=False)),
])
def test_frozen_boundaries(sample, label, updates):
    ctx, data = build(sample, **updates)
    result = decode(ctx, data)
    el = getattr(result.elements, updates.get('name', 'start_time'))
    assert el.status == EXPECTED[label]
    assert len(el.candidates) == 1


def test_missing_relation_and_unknown_kind_never_promote(sample):
    ctx, data = build(sample, name='cause')
    c = data['elements']['cause']['candidates'][0]
    c.pop('relation')
    c['cause_kind'] = 'vendor_suspected_cause'
    result = decode(ctx, data)
    assert result.elements.cause.status == EXPECTED['missing_relation']
    assert result.elements.cause.candidates[0].cause_kind == 'unclassified'
    assert result.semantic_assessment.original['cause']['candidates'][0]['cause_kind'] == 'vendor_suspected_cause'


@pytest.mark.parametrize('label', ['same_instant', 'different_purpose', 'conflicting_recovery'])
def test_frozen_time_conflicts(sample, label):
    ctx, data = build(sample, name='end_time', kind='business_recovery')
    el = data['elements']['end_time']
    other = deepcopy(el['candidates'][0]); other['id'] = 'C2'
    raw = '2026-01-02 11:04:05+08:00' if label == 'same_instant' else '2026-01-02 03:05:05+00:00'
    other['time']['raw'] = raw
    if label == 'different_purpose':
        other['time_kind'] = 'confirmation_action'
    el['candidates'].append(other)
    span = ctx.evidence[0].model_copy(update={'text': ctx.evidence[0].text + '; ' + raw})
    for c in el['candidates']: c['relation']['context'][0]['quote'] = span.text
    ctx = ExtractionContext(ctx.bundle, [span])
    result = decode(ctx, data)
    assert result.elements.end_time.status == EXPECTED[label]
    assert len(result.elements.end_time.candidates) == 2


@pytest.mark.parametrize('fault,code', [('missing_evidence','EVIDENCE_REF_MISSING'), ('wrong_quote','EVIDENCE_QUOTE_MISMATCH')])
def test_hard_rejection_survives_withheld_value(sample, fault, code):
    ctx, data = build(sample, kind='protocol_down')
    relation = data['elements']['start_time']['candidates'][0]['relation']
    if fault == 'missing_evidence':
        relation['context'][0]['evidence_id'] = 'M99/not-there'
    else:
        relation['context'][0]['quote'] = '凭空捏造的句子'
    with pytest.raises(ExtractionRejected) as ex:
        decode(ctx, data)
    assert EXPECTED[fault] in [i.code for i in ex.value.issues]


def test_whitespace_and_duplicate_do_not_change_status(sample):
    ctx, data = build(sample, name='cause', statement='设备\u00a0故障影响本次业务。')
    c = data['elements']['cause']['candidates'][0]
    c['statement'] = c['statement'].replace('\u00a0',' ')
    c['relation']['context'][0]['quote'] = c['statement']
    result = decode(ctx, data)
    assert result.elements.cause.status == EXPECTED['whitespace_equivalence']
    assert any(q.status == 'whitespace' for q in result.quote_checks)
    duplicate = deepcopy(c); duplicate['id'] = 'C2'
    data['elements']['cause']['candidates'].append(duplicate)
    assert decode(ctx, data).elements.cause.status == EXPECTED['duplicate_source']


def test_inverted_times_and_confirmation_separation(sample):
    ctx, data = build(sample)
    end = deepcopy(data['elements']['start_time'])
    end['candidates'][0]['time_kind'] = 'business_recovery'
    end['candidates'][0]['time']['raw'] = '2026-01-02 02:04:05+00:00'
    end['value'] = end['candidates'][0]['time']
    span = ctx.evidence[0].model_copy(update={'text':ctx.evidence[0].text + '; ' + end['value']['raw']})
    end['candidates'][0]['relation']['context'][0]['quote'] = span.text
    data['elements']['end_time'] = end
    ctx = ExtractionContext(ctx.bundle,[span])
    result = decode(ctx,data)
    assert result.elements.end_time.status == EXPECTED['inverted_business_times']
    assert result.elements.start_time.value


def test_cause_contradiction_and_split_mechanism(sample):
    ctx, data = build(sample, name='cause')
    el = data['elements']['cause']
    other = deepcopy(el['candidates'][0]); other['id']='C2'
    other['relation'].update(modality='suspected', assertion='mechanism')
    other['cause_kind']='suspected_mechanism'
    el['candidates'].append(other)
    assert decode(ctx,data).elements.cause.status == 'documented'
    other['relation'].update(modality='negated', assertion='fault', contradicts=['C1'])
    assert decode(ctx,data).elements.cause.status == 'conflicted'


def test_model_cannot_submit_local_assessment(sample):
    from noc7.providers.text_config import TextProviderError
    ctx,data=build(sample)
    data['semantic_assessment']={'checks':[]}
    with pytest.raises(TextProviderError): decode(ctx,data)


def test_report_alarm_duration_source_and_escaping(sample):
    from noc7.extract.pipeline import analyze
    from tests.a1.conftest import text_registry
    from tests.llm.conftest import BUNDLES
    result = analyze(BUNDLES/'SYN-S01', registry=text_registry())
    ctx,data=build(sample,name='cause',statement='<script>设备故障</script>')
    extraction=decode(ctx,data)
    result = result.model_copy(update=dict(evidence=ctx.evidence, elements=extraction.elements,
        semantic_assessment=extraction.semantic_assessment, suggestions=[], events=[], quote_checks=extraction.quote_checks, issues=[]))
    # 构造的报告去掉原案例服务身份，防止它引用本次单证据之外的编号。
    result = result.model_copy(update={'service_identity':None})
    report=render(result)
    assert '<script>设备故障</script>' not in report and '&lt;script&gt;' in report
    company=build_company_report(result)
    assert '供应商记载' in str(company.cells['analysis']) and '未经人工审核' in str(company.cells['analysis'])
    ctx,data=build(sample,kind='alarm_raised')
    extraction=decode(ctx,data)
    result=result.model_copy(update=dict(evidence=ctx.evidence,elements=extraction.elements,
        semantic_assessment=extraction.semantic_assessment,quote_checks=extraction.quote_checks))
    assert '告警时刻' in str(build_company_report(result).cells['declared'])
    assert final_duration(result) is None


def test_normalization_tampering_rejected(sample):
    ctx,data=build(sample)
    result=decode(ctx,data)
    c=result.elements.start_time.candidates[0]
    c.time=c.time.model_copy(update={'iso':'2026-01-02T03:04:05+08:00','utc_offset':'+08:00'})
    with pytest.raises(ExtractionRejected): validate_extraction(ctx,result)


def test_quoted_confirmation_is_not_confirmation_basis(sample):
    from noc7.schema import SpanRole
    ctx,data=build(sample,name='end_time',kind='business_recovery')
    c=data['elements']['end_time']['candidates'][0]
    c['relation']['customer_confirmation']=deepcopy(c['relation']['context'][0])
    assert decode(ctx,data).elements.end_time.status == 'confirmed'
    ctx=ExtractionContext(ctx.bundle,[ctx.evidence[0].model_copy(update={'role':SpanRole.QUOTED})])
    assert decode(ctx,data).elements.end_time.status == 'documented'


def test_date_and_timezone_anchor_with_source_ranges(sample):
    ctx,data=build(sample,raw='03：04',field=False)
    c=data['elements']['start_time']['candidates'][0]
    anchor=ctx.evidence[0].model_copy(update={'id':'M01/t:anchor','text':'2026-01-02 UTC'})
    c['relation']['date_anchor']=dict(evidence_id=anchor.id,quote='2026-01-02 UTC')
    c['relation']['timezone_anchor']=dict(evidence_id=anchor.id,quote='UTC')
    ctx=ExtractionContext(ctx.bundle,[*ctx.evidence,anchor])
    result=decode(ctx,data)
    assert result.elements.start_time.value.iso == '2026-01-02T03:04:00+00:00'
    assert result.elements.start_time.value.precision == 'minute'
    assert any(c.evidence_id==anchor.id for c in result.quote_checks)
    # 冲突的显式时区锚点不能静默覆盖原偏移。
    ctx,data=build(sample)
    c=data['elements']['start_time']['candidates'][0]
    anchor=ctx.evidence[0].model_copy(update={'id':'M01/t:anchor','text':'GMT+8'})
    c['relation']['timezone_anchor']=dict(evidence_id=anchor.id,quote=anchor.text)
    result=decode(ExtractionContext(ctx.bundle,[*ctx.evidence,anchor]),data)
    assert result.elements.start_time.value is None


def test_malformed_relation_cannot_hide_wrong_source(sample):
    ctx,data=build(sample)
    r=data['elements']['start_time']['candidates'][0]['relation']
    r.pop('modality')
    r['context'][0]['quote']='不存在的引文'
    with pytest.raises(ExtractionRejected): decode(ctx,data)


def test_original_missing_source_not_hidden_by_repair(sample):
    ctx,data=build(sample,name='cause')
    data['elements']['cause']['candidates'].append(dict(id='broken',evidence_refs=['M99/absent']))
    with pytest.raises(ExtractionRejected) as e: decode(ctx,data)
    assert 'EVIDENCE_REF_MISSING' in [i.code for i in e.value.issues]


def test_interval_precision_and_scoped_conflicts(sample):
    ctx,data=build(sample,raw='2026-01-02 03:04 UTC')
    c=deepcopy(data['elements']['start_time']['candidates'][0]);c['id']='C2'
    c['time']['raw']='2026-01-02 03:04:30 UTC'
    span=ctx.evidence[0].model_copy(update={'text':ctx.evidence[0].text+'; '+c['time']['raw']})
    c['relation']['context'][0]['quote']=span.text
    data['elements']['start_time']['candidates'].append(c)
    ctx=ExtractionContext(ctx.bundle,[span])
    assert decode(ctx,data).elements.start_time.status=='documented'
    c['relation']['scope']='另一条业务'
    c['time']['raw']='2026-01-02 03:05:30 UTC'
    span=span.model_copy(update={'text':span.text+'; '+c['time']['raw']})
    c['relation']['context'][0]['quote']=span.text
    assert decode(ExtractionContext(ctx.bundle,[span]),data).elements.start_time.status=='documented'


def test_business_duration_uses_confirmation_not_action_time(sample):
    from noc7.extract.pipeline import analyze
    from tests.a1.conftest import text_registry
    from tests.llm.conftest import BUNDLES
    result=analyze(BUNDLES/'SYN-S01',registry=text_registry())
    ctx,data=build(sample)
    end=deepcopy(data['elements']['start_time'])
    c=end['candidates'][0]; c['time_kind']='business_recovery'
    c['time']['raw']='2026-01-02 04:04:05+00:00';end['value']=c['time']
    span=ctx.evidence[0].model_copy(update={'text':ctx.evidence[0].text+'; '+c['time']['raw']})
    c['relation']['context'][0]['quote']=span.text
    c['relation']['customer_confirmation']=dict(evidence_id=span.id,quote=span.text)
    data['elements']['end_time']=end
    extraction=decode(ExtractionContext(ctx.bundle,[span]),data)
    result=result.model_copy(update=dict(elements=extraction.elements,semantic_assessment=extraction.semantic_assessment))
    assert final_duration(result)==60
    data['elements']['start_time']['candidates'][0]['time_kind']='alarm_raised'
    extraction=decode(ExtractionContext(ctx.bundle,[span]),data)
    result=result.model_copy(update=dict(elements=extraction.elements,semantic_assessment=extraction.semantic_assessment))
    assert final_duration(result) is None
    assert '分钟' not in str(build_company_report(result).cells['duration'])


def test_rfo_dotted_day_first_and_no_date_invention():
    value = time_phrase("02.01.2026 03:04 GMT+0", "+08:00")
    assert value.iso == "2026-01-02T03:04:00+00:00"
    assert value.tz_source == "explicit"
    assert time_phrase("03：04", "+08:00").iso is None


@pytest.mark.parametrize('selection',['not-there','duplicate'])
def test_ambiguous_candidate_number_never_guessed(sample,selection):
    ctx,data=build(sample,name='cause')
    if selection=='duplicate':
        data['elements']['cause']['candidates'].append(deepcopy(data['elements']['cause']['candidates'][0]))
    else:
        data['elements']['cause']['selected']=selection
    result=decode(ctx,data)
    assert result.elements.cause.value is None
    assert result.semantic_assessment.original['cause']['selected']==('C1' if selection=='duplicate' else selection)


@pytest.mark.parametrize('change',[dict(tz_source='assumed'),dict(precision='minute')])
def test_time_metadata_not_just_iso_is_revalidated(sample,change):
    ctx,data=build(sample)
    result=decode(ctx,data)
    c=result.elements.start_time.candidates[0]
    c.time=c.time.model_copy(update=change)
    with pytest.raises(ExtractionRejected): validate_extraction(ctx,result)


def test_model_path_never_calls_semantic_wordlists(sample,monkeypatch):
    import noc7.rules as rules
    import noc7.extract.baseline as baseline
    def forbidden(*args,**kwargs): raise AssertionError('不能用词表重判模型时间或原因')
    monkeypatch.setattr(rules,'cause_kind',forbidden)
    monkeypatch.setattr(baseline,'cause_kind',forbidden)
    monkeypatch.setattr(baseline,'_time_kind',forbidden)
    for name,kind in [('cause','unused'),('start_time','business_start')]:
        ctx,data=build(sample,name=name,kind=kind)
        assert getattr(decode(ctx,data).elements,name).status=='documented'


def test_chinese_date_without_separator_keeps_clock():
    raw="2026年01月02日03：04"
    value=time_phrase(raw,"+08:00")
    assert value.iso=="2026-01-02T03:04:00+08:00"
    assert value.precision=="minute" and value.raw==raw
