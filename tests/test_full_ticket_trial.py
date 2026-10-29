"""统计器不能把缺来源、仅空白等价和记录时间混为一类。"""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('trial', Path(__file__).parents[1] / 'scripts/run_full_ticket_trial.py')
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)


def test_trace_and_denominators():
    spans = {'E1': SimpleNamespace(text='光纤\u00a0中断')}
    node = {'value': '光纤 中断', 'selected': 'C1', 'candidates': [
        {'id': 'C1', 'statement': '光纤 中断', 'evidence_refs': ['E1']},
        {'id': 'C2', 'statement': '中断', 'evidence_refs': ['missing']},
        {'id': 'C3', 'statement': '恢复', 'evidence_refs': ['E1']},
    ]}
    m = trial.measure('cause', node, spans)
    assert m['counts'] == dict(total=3, strict=0, whitespace=1, metadata=0, mismatch=1, missing_source=1)
    assert m['filled_candidate_traceable']
    check = m['checks'][0]
    assert spans['E1'].text[check['start']:check['end']] == '光纤\u00a0中断'
    rows = [dict(status='ok', elements={'cause': m}), dict(status='rejected')]
    total = trial.aggregate(rows)
    assert total['cases'] == 2 and total['completed'] == 1
    assert total['elements']['cause']['filled'] == 1


def test_metadata_separate_and_empty_suggestions():
    spans = {'E1': SimpleNamespace(text='已受理')}
    node = {'candidates': [{'time': {'raw': '2026-10-29 10:00'}, 'evidence_refs': ['E1']}]}
    m = trial.measure('start_time', node, spans, {'E1': ['2026-10-29 10:00']})
    assert m['counts']['metadata'] == 1 and m['counts']['strict'] == 0
    for original in (None, '', {'candidates': [None, {'party': '甲', 'evidence_refs': None}]}):
        m = trial.measure('responsible_party', original, spans)
        assert not m['filled']
        assert m['counts']['missing_source'] == m['counts']['total']


def test_rejected_raw_suggestions_still_count(tmp_path):
    import json
    audit = tmp_path / 'audit'
    audit.mkdir()
    payload = {'elements': {'location': {'value': None, 'candidates': [
        {'description': '故障在甲乙之间', 'evidence_refs': ['E1']}
    ]}}}
    record = {'raw_response': json.dumps({'choices': [{'message': {'content': json.dumps(payload)}}]}),
              'request_evidence': {'evidence': [{'id': 'E1', 'text': '故障在甲乙之间'}]}}
    (audit / 'one.json').write_text(json.dumps(record))
    row = trial.raw_suggestions(tmp_path, 'rejected')
    summary = trial.aggregate([row])
    assert summary['completed'] == 0
    assert summary['suggestions']['location']['candidate_cases'] == 1
    assert summary['suggestions']['location']['counts']['strict'] == 1


def test_complete_version_wins_in_both_directory_orders():
    old = dict(source='/old', closed=False, closure_actions=[], log_entries=18,
               materials=9, bundle_sha256='old')
    closed = dict(source='/closed', closed=True,
                  closure_actions=['销障', '结单签收', '回访结单'], log_entries=21,
                  materials=10, bundle_sha256='closed')
    assert trial.choose_complete_version([old, closed]) == closed
    assert trial.choose_complete_version([closed, old]) == closed
    partial = dict(closed, source='/partial', closure_actions=['销障'], bundle_sha256='partial')
    assert trial.choose_complete_version([partial, closed]) == closed
    import pytest
    with pytest.raises(ValueError, match='清单哈希不同'):
        trial.choose_complete_version([closed, dict(closed, bundle_sha256='conflict')])
    assert trial.choose_complete_version([closed, dict(closed)]) == closed


def test_result_metrics_uses_bundle_recorded_at():
    from noc7.bundle import load_bundle
    from noc7.schema import AnalysisResult
    from noc7.extract.pipeline import analyze
    bundle = load_bundle(Path(__file__).parents[1] / 'fixtures/bundles/SYN-S01')
    result = analyze(bundle.root)
    # 使用真实 schema 的合成结果，在原文不含时间的日志片段上加入时间候选。
    span = next(s for s in result.evidence if s.locator.type == 'log_entry')
    recorded = bundle.process_log.entry(span.locator.seq).recorded_at
    payload = result.model_dump(mode='json')
    payload['elements']['end_time'] = dict(status='unknown', value=None, candidates=[dict(
        id='Cmetadata', evidence_refs=[span.id], attribution='noc_check',
        time=dict(raw=recorded), time_kind='other')])
    result = AnalysisResult.model_validate(payload)
    counts = trial.result_metrics(result, bundle)['elements']['end_time']['counts']
    assert counts['metadata'] == 1 and counts['mismatch'] == 0
