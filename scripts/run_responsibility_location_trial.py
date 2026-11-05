"""固定已结单输入的在线试跑及禁网回放；真实明细仅写新的 ~/.noc7/ 目录。"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import traceback
from zipfile import ZipFile

from check_time_cause import load_inputs
from summarize_closed_tickets import aggregate
from noc7.extract.pipeline import analyze_with_context
from noc7.extract.storage import ensure_output_allowed
from noc7.providers.text_config import load_model_config
from noc7.providers.text_http import OpenAICompatibleTextProvider
from noc7.providers.text_prompt import prepare_evidence
from noc7.providers.text_replay import evidence_digest, save_replay, ReplayProvider
from noc7.report import write_reports
from noc7.rules import validate_extraction, ExtractionRejected
from noc7.schema import AnalysisResult, DataClass


class ModelResponseUnavailable(ValueError):
    """上游未返回模型回答，离线不能复现服务端生成。"""


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def private_path(path):
    path = path.expanduser().resolve()
    if not path.is_relative_to((Path.home() / '.noc7').resolve()):
        raise ValueError('真实输入输出必须位于 ~/.noc7/')
    return path


def summarize(rows):
    base = aggregate(rows)
    base['paths'] = dict(Counter(c['relation']['decision_path'] for r in rows if r['status'] == 'ok'
        for c in r['result']['elements']['responsible_party']['candidates']
        if c['id'] == r['result']['elements']['responsible_party']['selected'] and c.get('relation')))
    base['sources'] = {name: dict(Counter(c['relation']['source_tier'] for r in rows if r['status'] == 'ok'
        for c in r['result']['elements'][name]['candidates']
        if c['id'] == r['result']['elements'][name]['selected'] and c.get('relation')))
        for name in ('responsible_party', 'location')}
    base['rejections'] = dict(Counter(code for r in rows for code in r.get('issue_codes', [])))
    base['failure_types'] = dict(Counter(r.get('failure_type', 'unknown') for r in rows if r['status'] != 'ok'))
    base['http_failures'] = dict(Counter(str(r['http_status']) for r in rows if 'http_status' in r))
    base['reused_responses'] = sum(r.get('reused_response', False) for r in rows)
    base['roundtrip_equal'] = sum(r.get('roundtrip_equal', False) for r in rows)
    base['word_valid'] = sum(r.get('word_valid', False) for r in rows)
    base['semantic_accuracy'] = None
    return base


def invalid_response(status, audits):
    return status != 'ok' and any('raw_response' in r or r.get('outcome') == 'response_too_large' for r in audits)


def run_serial(items, run, checkpoint):
    """不预提交下一单；每单结束后先检查停止条件。"""
    rows, streak, stop_reason = [], 0, None
    for item in items:
        row = run(item)
        rows.append(row)
        if row.get('http_status') == 402:
            stop_reason = 'http_402'
        else:
            bad = row.get('http_status') == 503 or row.get('invalid_response', False)
            streak = streak + 1 if bad else 0
            if streak >= 3:
                stop_reason = 'three_consecutive_503_or_invalid_responses'
            elif row.get('request_count', 0) == 0:
                stop_reason = 'local_failure_before_request'
        checkpoint(rows, stop_reason)
        if stop_reason:
            break
    return rows, stop_reason


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--responses', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--model-config', type=Path, default=Path('config/models/deepseek.json'))
    ap.add_argument('--workers', type=int, choices=range(1, 5), default=1)
    ap.add_argument('--replay-from', type=Path)

    args = ap.parse_args()
    if not args.replay_from and args.workers != 1:
        ap.error("在线试跑仅允许 workers=1，每张一次且不自动重试")
    os.umask(0o077)
    baseline, responses, out = map(private_path, (args.baseline, args.responses, args.out))
    ensure_output_allowed(DataClass.REAL, out)
    if out.exists() or any(out.is_relative_to(p) or p.is_relative_to(out) for p in (baseline, responses)):
        raise ValueError('输出须为新的独立目录')
    # 全量校验映射、原包材料与唯一原响应，再筛详情已结单，不能按输出好坏选样本。
    inputs = [item for item in load_inputs(baseline, responses)
              if item[0]['closed'] and item[1].ticket.status.detail_status == '已结单']
    for entry, bundle, *_ in inputs:
        private_path(Path(entry['source']))
    if len(inputs) != 22:
        raise ValueError('固定已结单集合应恰好为 22 张')
    planned_cases = len(inputs)
    replay = private_path(args.replay_from) if args.replay_from else None
    reuse = replay
    if reuse and (out.is_relative_to(reuse) or reuse.is_relative_to(out)):
        raise ValueError('输出与复用响应目录不能互相包含')
    if replay:
        source_rows = read(replay / 'private-details.json')
        aliases = [r['alias'] for r in source_rows]
        if len(set(aliases)) != len(aliases) or not set(aliases) <= {e['alias'] for e, *_ in inputs}:
            raise ValueError('回放记录与固定输入集合不符')
        inputs = [item for item in inputs if item[0]['alias'] in set(aliases)]
        socket.socket = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError('回放禁止网络'))
    config = load_model_config(args.model_config).model_copy(update={'max_request_bytes': 4194304, 'max_retries': 0})
    out.mkdir(mode=0o700)
    write(out / 'mapping.json', [entry for entry, *_ in inputs])
    write(out / 'config.json', config.model_dump(mode='json'))
    import noc7.providers.text_http
    module_root = Path(noc7.providers.text_http.__file__).parent
    write(out / 'code-binding.json', {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in module_root.glob('*.py')})

    def run(item):
        entry, bundle, original, _ = item
        alias = entry['alias']; folder = out / alias
        folder.mkdir()
        row = dict(alias=alias, closed=True, status='failed', bundle_sha256=bundle.manifest_sha256)
        try:
            saved = None
            if reuse:
                candidates = [read(p) for p in (reuse / alias / 'audit').glob('*.json')]
                candidates = [r for r in candidates if 'raw_response' in r]
                if len(candidates) > 1:
                    raise ValueError('回放必须恰好一份原响应')
                if replay and not candidates:
                    raise ModelResponseUnavailable('原试跑没有模型回答，离线不补造响应')
                saved = candidates[0] if candidates else None
                row['reused_response'] = bool(saved)
            online = None if saved else OpenAICompatibleTextProvider(config, audit_dir=folder / 'audit')

            class BoundProvider:
                name = 'replay:responsibility-location' if saved else online.name
                prompt_version = saved.get('prompt_version') if saved else online.prompt_version

                def extract(self, ctx):
                    clean, request = prepare_evidence(ctx)
                    if (evidence_digest(clean) != original['evidence_sha256']
                        or request['evidence'] != original['request_evidence']['evidence']):
                        raise ValueError('本次请求证据与冻结证据不同，停止发送')
                    if saved:
                        if (saved['bundle_sha256'] != bundle.manifest_sha256
                            or saved['evidence_sha256'] != evidence_digest(clean)
                            or saved['request_evidence']['evidence'] != request['evidence']):
                            raise ValueError('回放输入或请求证据不符')
                        write(folder / 'audit' / 'response.json', saved)
                        return OpenAICompatibleTextProvider._decode(saved['raw_response'].encode(), clean)
                    return online.extract(ctx)

            result, ctx, data = analyze_with_context(entry['source'], BoundProvider())
            write_reports(result, folder, report_type='closure')
            save_replay(folder / 'replay.json', ctx, data)
            again = ReplayProvider(folder / 'replay.json').extract(ctx)
            validate_extraction(ctx, again)
            reloaded = AnalysisResult.model_validate_json((folder / 'analysis.json').read_text())
            row['roundtrip_equal'] = again.model_dump(mode='json') == data.model_dump(mode='json') and reloaded == result
            with ZipFile(folder / 'company_report.docx') as z:
                row['word_valid'] = z.testzip() is None
            row.update(status='ok', result=result.model_dump(mode='json'))
        except Exception as exc:
            row.update(status='rejected' if isinstance(exc, ExtractionRejected) else 'failed',
                       issue_codes=sorted({i.code.value for i in getattr(exc, 'issues', [])}), failure_type=type(exc).__name__)
            http = re.search(r'HTTP (\d{3})', str(exc))
            if http:
                row['http_status'] = int(http[1])
            write(folder / 'failure.json', dict(type=type(exc).__name__, traceback=traceback.format_exc()))
        audits = [read(p) for p in (folder / 'audit').glob('*.json')]
        row['request_count'] = 0 if replay else sum(r.get('request_attempts', 0) for r in audits)
        records = [r for r in audits if 'raw_response' in r]
        row['invalid_response'] = invalid_response(row['status'], audits)
        if records:
            row['binding'] = {k: records[0][k] for k in ('bundle_sha256', 'evidence_sha256', 'prompt_version')}
            row['binding']['response_sha256'] = hashlib.sha256(records[0]['raw_response'].encode()).hexdigest()
        write(folder / 'metrics.json', row)
        return row

    def checkpoint(rows, stop_reason=None):
        write(out / 'private-details.json', sorted(rows, key=lambda r: r['alias']))
        counts = dict(summarize(rows), planned_cases=planned_cases, completed_cases=len(rows),
                      not_attempted_cases=planned_cases-len(rows),
                      request_count=sum(r.get('request_count', 0) for r in rows),
                      stop_reason=stop_reason, external_services=not bool(replay),
                      workers=args.workers, max_retries=0)
        write(out / 'summary.json', counts)
        print(f"完成 {len(rows)}/{len(inputs)}；本单 {rows[-1]['status']}；模型请求累计 {counts['request_count']}", flush=True)

    if replay:
        rows = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for future in as_completed([pool.submit(run, item) for item in inputs]):
                rows.append(future.result())
                checkpoint(rows)
    else:
        run_serial(inputs, run, checkpoint)


if __name__ == '__main__':
    main()
