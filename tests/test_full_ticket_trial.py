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
