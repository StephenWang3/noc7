"""合成验证：拒绝留分母，候选与建议不能充作正式值。"""
import importlib.util
from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('closed_summary', SCRIPTS/'summarize_closed_tickets.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_rejection_and_suggestions_do_not_inflate_filled():
    nodes = {k: dict(value=None, status='unknown', candidates=[])
             for k in module.ELEMENTS}
    nodes['start_time'] = dict(value=None, status='conflicted', candidates=[{'id': 'C1'}])
    nodes['handling_process'] = dict(value=[{'action': '合成检查'}], status='documented')
    result = dict(elements=nodes, suggestions=[dict(element='location', original={'candidates': [{}]})])
    summary = module.aggregate([dict(status='ok', result=result), dict(status='rejected')])
    assert (summary['cases'], summary['delivered']) == (2, 1)
    assert summary['elements']['start_time'] == dict(
        filled=0, unfilled_success=1, rejected=1,
        states={'conflicted': 1}, candidate_cases=1)
    assert summary['elements']['handling_process']['filled'] == 1
    assert summary['elements']['location']['filled'] == 0
    assert summary['suggestions']['location'] == 1


def test_empty_subset_has_zero_counts():
    summary = module.aggregate([])
    assert summary['cases'] == summary['delivered'] == 0
    assert all(n['filled'] == n['unfilled_success'] == n['rejected'] == 0
               for n in summary['elements'].values())
