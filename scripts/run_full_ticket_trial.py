"""完整包实用性试跑；真实明细写仓库外，控制台仅输出代号与状态。"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import traceback
from types import SimpleNamespace

from noc7.batch import _index
from noc7.bundle import load_bundle
from noc7.extract.pipeline import analyze_with_context
from noc7.extract.storage import ensure_output_allowed
from noc7.providers.text_config import create_text_provider
from noc7.providers.text_replay import save_replay
from noc7.quote_match import match_quote
from noc7.report import write_reports
from noc7.schema import DataClass

KEYS = dict(start_time='time', end_time='time', phenomenon='description',
            responsible_party='party', cause='statement', handling_process='action', location='description')


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def measure(name, node, spans, metadata=None):
    """候选逐条查原文；原文时间戳另计，不与正文匹配混算。"""
    node = node if isinstance(node, dict) else {}
    candidates = node.get('value', []) if name == 'handling_process' else node.get('candidates', [])
    candidates = candidates if isinstance(candidates, list) else []
    counts = Counter(total=0, strict=0, whitespace=0, metadata=0, mismatch=0, missing_source=0)
    checks, statuses = [], {}
    for i, c in enumerate(candidates):
        counts['total'] += 1
        refs = c.get('evidence_refs') if isinstance(c, dict) else None
        refs = [refs] if isinstance(refs, str) else refs
        if not refs or not isinstance(refs, list) or any(r not in spans for r in refs):
            counts['missing_source'] += 1
            statuses[i] = 'missing_source'
            continue
        text = c.get(KEYS[name], '')
        if isinstance(text, dict):
            text = text.get('raw', '')
        text = text if isinstance(text, str) else ''
        matches = [match_quote(text, spans[r].text, path=f'{name}/{i}', evidence_id=r) for r in refs]
        checks.extend(m.model_dump() for m in matches)
        status = 'strict' if any(m.status == 'strict' for m in matches) else 'whitespace' if any(m.status == 'whitespace' for m in matches) else 'mismatch'
        if status == 'mismatch' and name in ('start_time', 'end_time') and any(text in (metadata or {}).get(r, []) for r in refs):
            status = 'metadata'
        counts[status] += 1
        statuses[i] = status
    selected = node.get('selected')
    chosen = [i for i, c in enumerate(candidates) if isinstance(c, dict) and c.get('id') == selected] if selected else list(statuses)
    filled = bool(node.get('value'))
    traced = filled and bool(chosen) and all(statuses[i] in ('strict', 'whitespace', 'metadata') for i in chosen)
    return dict(filled=filled, filled_candidate_traceable=traced, candidate_cases=int(bool(candidates)), counts=dict(counts), checks=checks)


def result_metrics(result, bundle=None):
    spans = {s.id: s for s in result.evidence}
    metadata = {}
    if bundle is not None:
        for ref, span in spans.items():
            if span.locator.type == 'log_entry':
                entry = bundle.process_log.entry(span.locator.seq)
                if entry and entry.recorded_at:
                    metadata[ref] = [entry.recorded_at]
    elements = {n.value: measure(n.value, e.model_dump(mode='json'), spans, metadata) for n, e in result.elements.items()}
    suggestions = {s.element: measure(s.element, s.original, spans) for s in result.suggestions}
    return dict(elements=elements, suggestions=suggestions)


def aggregate(rows):
    output = dict(cases=len(rows), completed=sum(r['status'] == 'ok' for r in rows),
                  failures=dict(Counter(r['status'] for r in rows if r['status'] != 'ok')))
    for group in ('elements', 'suggestions'):
        output[group] = {}
        for name in KEYS:
            nodes = [r[group][name] for r in rows if name in r.get(group, {})]
            if not nodes:
                continue
            counts = Counter()
            for n in nodes:
                counts.update(n['counts'])
            output[group][name] = dict(filled=sum(n['filled'] for n in nodes),
                candidate_cases=sum(n['candidate_cases'] for n in nodes),
                filled_candidate_traceable=sum(n['filled_candidate_traceable'] for n in nodes), counts=dict(counts))
    return output


def raw_suggestions(target, status):
    """被拒答复也保留在原始建议统计；未解析答复另列。"""
    row = dict(status=status)
    records = list((target / 'audit').glob('*.json'))
    if len(records) != 1:
        return row
    record = json.loads(records[0].read_text())
    try:
        payload = json.loads(json.loads(record['raw_response'])['choices'][0]['message']['content'])
        spans = {s['id']: SimpleNamespace(text=s['text']) for s in record['request_evidence']['evidence']}
        row['suggestions'] = {n: measure(n, payload.get('elements', {}).get(n), spans)
                              for n in ('responsible_party', 'location')}
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        pass
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('roots', nargs='+', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--model-config', type=Path, required=True)
    ap.add_argument('--workers', type=int, default=2, choices=range(1, 5))
    args = ap.parse_args()
    os.umask(0o077)
    out = args.out.expanduser().resolve()
    ensure_output_allowed(DataClass.REAL, out)
    if out.exists():
        raise ValueError('输出必须为新目录')
    mapping, seen, duplicates = [], set(), 0
    # 全部输入先校验；按源工单身份去重，切分包不作为本轮输入。
    for root in args.roots:
        root = root.expanduser().resolve()
        if out.is_relative_to(root) or root.is_relative_to(out):
            raise ValueError('输入输出不能互相包含')
        for p in sorted(root.iterdir()):
            if not (p / 'manifest.json').is_file():
                continue
            b = load_bundle(p)
            if b.ticket.ticket_ref in seen:
                duplicates += 1
                continue
            seen.add(b.ticket.ticket_ref)
            mapping.append(dict(alias=f'F{len(mapping)+1:02d}', source=str(p),
                ticket_ref=b.ticket.ticket_ref, bundle_sha256=b.manifest_sha256,
                closed=b.ticket.status.detail_status == '已结单'))
    if not mapping:
        raise ValueError('没有输入包')
    out.mkdir(parents=True, mode=0o700)
    write(out / 'mapping.json', mapping)
    write(out / 'config.json', json.loads(args.model_config.read_text()))
    started = datetime.now(timezone.utc).isoformat()

    def run(entry):
        alias = entry['alias']
        target = out / alias
        target.mkdir(mode=0o700)
        row = dict(alias=alias, status='failed', closed=entry['closed'])
        try:
            provider = create_text_provider(args.model_config, audit_dir=target / 'audit')
            result, ctx, extraction = analyze_with_context(entry['source'], provider)
            report_type = 'closure' if ctx.bundle.ticket.status.detail_status == '已结单' else 'stage'
            write_reports(result, target, report_type=report_type)
            save_replay(target / 'replay.json', ctx, extraction)
            row.update(status='ok', **result_metrics(result, ctx.bundle))
            row['materials'] = dict(Counter(m.parse_status.value for m in result.materials))
            row['issues'] = dict(Counter(i.code.value for i in result.issues))
        except Exception as exc:
            row['status'] = 'rejected' if hasattr(exc, 'issues') else 'failed'
            row['issue_codes'] = [i.code.value for i in getattr(exc, 'issues', [])]
            write(target / 'failure.json', dict(traceback=traceback.format_exc()))
        row['raw_suggestions'] = raw_suggestions(target, row['status'])
        row['input_unchanged'] = load_bundle(entry['source']).manifest_sha256 == entry['bundle_sha256']
        write(target / 'metrics.json', row)
        return row

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for f in as_completed([pool.submit(run, e) for e in mapping]):
            row = f.result()
            rows.append(row)
            write(out / 'summary.json', aggregate(rows))
            print(row['alias'], row['status'], f'{len(rows)}/{len(mapping)}', flush=True)
    rows.sort(key=lambda r: r['alias'])
    write(out / 'metrics.json', rows)
    write(out / 'subgroups.json', {name: aggregate([r for r in rows if r['closed'] == flag])
                                  for name, flag in (('closed', True), ('other', False))})
    raw = [r['raw_suggestions'] for r in rows]
    write(out / 'raw-summary.json', dict(aggregate(raw), unavailable_cases=sum('suggestions' not in r for r in raw)))
    write(out / 'run.json', dict(started_at=started, finished_at=datetime.now(timezone.utc).isoformat(),
        duplicates=duplicates, total=len(mapping), workers=args.workers, input_unchanged=all(r['input_unchanged'] for r in rows)))
    statuses = {r['alias']: r['status'] for r in rows}
    index = [dict(e, status=statuses[e['alias']]) for e in mapping]
    (out / 'index.html').write_text(_index(index), encoding='utf-8')
    import noc7.report
    (out / 'index.css').write_bytes((Path(noc7.report.__file__).parent / 'report.css').read_bytes())


if __name__ == '__main__':
    main()
