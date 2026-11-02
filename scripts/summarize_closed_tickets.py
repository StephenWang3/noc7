"""只读汇总已保存结果；不调用模型、不重跑提取，逐单记录仅写 ~/.noc7/。"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import socket

from check_time_cause import load_inputs
from noc7.schema import AnalysisResult

ELEMENTS = ('start_time', 'end_time', 'phenomenon', 'responsible_party',
            'cause', 'handling_process', 'location')


def read(path):
    return json.loads(path.read_text())


def aggregate(rows):
    successful = [r for r in rows if r['status'] == 'ok']
    elements = {}
    for key in ELEMENTS:
        nodes = [r['result']['elements'][key] for r in successful]
        filled = sum(bool(n['value']) for n in nodes)
        elements[key] = dict(filled=filled, unfilled_success=len(nodes)-filled,
                            rejected=len(rows)-len(nodes),
                            states=dict(Counter(n['status'] for n in nodes)),
                            candidate_cases=sum(bool(n.get('candidates', n.get('value'))) for n in nodes))
    return dict(cases=len(rows), delivered=len(successful), elements=elements,
                suggestions={key: sum(any(s['element'] == key and isinstance(s['original'], dict) and s['original'].get('candidates')
                                          for s in r['result']['suggestions']) for r in successful)
                             for key in ('responsible_party', 'location')})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--responses', type=Path, required=True)
    ap.add_argument('--results', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    os.umask(0o077)
    private = (Path.home()/'.noc7').resolve()
    paths = {k: v.expanduser().resolve() for k, v in vars(args).items()}
    if any(not p.is_relative_to(private) for p in paths.values()) or paths['out'].exists():
        raise ValueError('所有路径须在 ~/.noc7/ 下，输出目录须为新目录')
    socket.socket = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('统计禁止网络'))
    inputs = load_inputs(paths['baseline'], paths['responses'])
    bindings = {r['alias']: r for r in read(paths['results']/'source-binding.json')}
    runs = {r['alias']: r for r in read(paths['results']/'run.json')}
    if set(bindings) != {e['alias'] for e, *_ in inputs} or set(runs) != set(bindings):
        raise ValueError('输入、结果和运行记录集合不同')
    rows = []
    for entry, bundle, record, _ in inputs:
        alias = entry['alias']; binding = bindings[alias]
        if (binding['bundle_sha256'] != bundle.manifest_sha256 or
            binding['response_sha256'] != hashlib.sha256(record['raw_response'].encode()).hexdigest() or
            binding['evidence_sha256'] != record['evidence_sha256']):
            raise ValueError('输入／响应绑定不符')
        row = dict(alias=alias, closed=entry['closed'], status=runs[alias]['status'])
        folder = paths['results']/alias
        if row['status'] == 'ok':
            result = AnalysisResult.model_validate(read(folder/'analysis.json'))
            if result.run.bundle_sha256 != bundle.manifest_sha256 or result.ticket_ref != entry['ticket_ref']:
                raise ValueError('结果与输入身份不同')
            row['result'] = result.model_dump(mode='json')
            row['result_sha256'] = hashlib.sha256((folder/'analysis.json').read_bytes()).hexdigest()
        else:
            row['failure'] = read(folder/'failure.json')
        rows.append(row)
    summary = {key: aggregate(subset) for key, subset in (
        ('all', rows), ('closed', [r for r in rows if r['closed']]),
        ('other', [r for r in rows if not r['closed']]))}
    summary['method'] = 'saved_results_only_no_network'
    paths['out'].mkdir(mode=0o700)
    for name, value in [('summary.json', summary), ('private-details.json', rows)]:
        (paths['out']/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
