"""按冻结原包和唯一原响应验证时间／原因；真实明细只写新的私有目录。"""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from email.utils import parsedate_to_datetime
import re
import hashlib
import json
import os
from pathlib import Path
import socket
import traceback
from zipfile import ZipFile

from noc7.bundle import load_bundle
from noc7.extract.pipeline import analyze_with_context
from noc7.extract.storage import ensure_output_allowed
from noc7.extract.types import ExtractionContext
from noc7.providers.text_config import load_model_config
from noc7.providers.text_http import OpenAICompatibleTextProvider
from noc7.providers.text_prompt import prepare_evidence
from noc7.providers.text_replay import evidence_digest, save_replay, ReplayProvider
from noc7.report import write_reports
from noc7.rules import validate_extraction, ExtractionRejected
from noc7.schema import EvidenceSpan, DataClass, AnalysisResult
from noc7.quote_match import match_quote


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load_inputs(baseline, responses=None, *, closed_only=False, keep_request_failures=False):
    """所有包和响应先验证，再允许任何网络调用；不按目录猜选版本。"""
    responses = responses or baseline
    output = []
    for entry in read(baseline / 'mapping.json'):
        if closed_only and not entry.get('closed', False):
            continue
        bundle = load_bundle(entry['source'])
        if bundle.manifest_sha256 != entry['bundle_sha256']:
            raise ValueError('原输入包哈希发生变化')
        records = [read(p) for p in (responses / entry['alias']).glob('audit*/*.json')]
        if keep_request_failures:
            if len(records) != 1 or ('raw_response' not in records[0]
                                    and records[0].get('outcome') not in {'http_error', 'transport_error'}):
                raise ValueError('原输入不是唯一完成请求审计，不能把缺失响应当作请求失败')
        else:
            records = [r for r in records if 'raw_response' in r]
            if len(records) != 1:
                raise ValueError('原输入不是唯一已响应审计')
        record = records[0]
        if record['bundle_sha256'] != bundle.manifest_sha256:
            raise ValueError('审计包哈希不一致')
        # load_bundle 同时校验每份材料的哈希。
        evidence = [EvidenceSpan.model_validate({k:v for k,v in s.items() if k in EvidenceSpan.model_fields})
                    for s in record['request_evidence']['evidence']]
        ctx = ExtractionContext(bundle, evidence)
        if evidence_digest(ctx) != record['evidence_sha256']:
            raise ValueError('实际请求证据摘要不一致')
        output.append((entry, bundle, record, ctx))
    return output


def independent_time_metrics(result, default_timezone):
    """用标准 datetime 检查数值表示，不调用被测 time_phrase 或语义分类器。"""
    spans={s.id:s for s in result.evidence}
    rows=[]
    def zone_offset(token):
        token=token.strip(' ()')
        if token.upper() in {'Z','GMT','UTC'}: return '+00:00'
        if token in {'北京时间','香港时间'}: return '+08:00'
        m=re.fullmatch(r'(?:UTC|GMT)?\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?',token,re.I)
        return f'{m[1]}{int(m[2]):02d}:{int(m[3] or 0):02d}' if m else None
    for name in ('start_time','end_time'):
        for c in getattr(result.elements,name).candidates:
            text=re.sub(r'\s+', ' ', c.time.raw.strip()).replace('：',':')
            m=re.fullmatch(r'(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?\s*(?:T?\s*(\d{1,2})[:时](\d{2})(?:分|[:分](\d{2})秒?)?)?\s*(.*?)',text)
            dayfirst=re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})\s*(.*)',text)
            slash=re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)\s*(.*)',text,re.I)
            meridiem=None
            expected=None
            try:
                if slash:
                    first,second,y,h,mi,se,meridiem,tail=slash.groups()
                    a,b=int(first),int(second)
                    if (a>12)==(b>12): raise ValueError('日月不明确')
                    mo,da=(b,a) if a>12 else (a,b)
                if m or dayfirst or slash:
                    if m: y,mo,da,h,mi,se,tail=m.groups()
                    elif dayfirst: da,mo,y,h,mi,tail=dayfirst.groups(); se=None
                    ampm=re.fullmatch(r'(AM|PM)\s*(.*)',tail,re.I)
                    if ampm: meridiem,tail=ampm.groups()
                    if meridiem and h is not None:
                        if not 1<=int(h)<=12: raise ValueError('非法十二小时制')
                        h=int(h)%12+(12 if meridiem.upper()=='PM' else 0)
                    if h is None:
                        if meridiem:
                            expected=dict(iso=None,precision=None,utc_offset=None,tz_source='unknown')
                        elif not re.search(r'\d[:时]\d', tail):
                            expected=dict(iso=f'{int(y):04d}-{int(mo):02d}-{int(da):02d}',precision='day',tz_source='unknown',utc_offset=None)
                    elif not tail or zone_offset(tail):
                        zone=zone_offset(tail) if tail else None
                        explicit=zone is not None
                        field_backed=any(r in spans and spans[r].locator.type=='field'
                                         and match_quote(c.time.raw,spans[r].text).status!='mismatch'
                                         for r in c.evidence_refs)
                        if zone is None and field_backed:
                            zone=default_timezone
                        anchor=c.relation.timezone_anchor if c.relation else None
                        invalid_anchor=False
                        if anchor:
                            matches=re.findall(r'\b(?:UTC|GMT)(?:\s*[+-]\s*\d{1,2}(?::?\d{2})?)?|[+-]\d{2}:?\d{2}|北京时间|香港时间',anchor.quote,re.I)
                            if len(set(matches))==1:
                                anchored=zone_offset(matches[0])
                                invalid_anchor=bool(zone and zone!=anchored)
                                if not invalid_anchor:
                                    zone=anchored; explicit=True
                        dt=datetime(int(y),int(mo),int(da),int(h),int(mi),int(se or 0))
                        expected=dict(iso=dt.isoformat()+(zone or ''),precision='second' if se else 'minute',
                                      utc_offset=zone,tz_source='explicit' if explicit else 'assumed' if zone else 'unknown')
                        if invalid_anchor:
                            expected=dict(iso=None,precision=None,utc_offset=None,tz_source='unknown')
                elif re.match('[A-Za-z]{3},',text):
                    dt=parsedate_to_datetime(text); zone=dt.strftime('%z');zone=zone[:3]+':'+zone[3:]
                    expected=dict(iso=dt.isoformat(),precision='second',tz_source='explicit',utc_offset=zone)
            except (ValueError,TypeError,OverflowError):
                expected=None
            state='not_assessed' if expected is None else 'match' if all(getattr(c.time,k)==v for k,v in expected.items()) else 'mismatch'
            rows.append(dict(element=name,candidate=c.id,state=state))
    return dict(counts=dict(Counter(r['state'] for r in rows)),items=rows)


def response_digest(record):
    raw = record.get('raw_response')
    return hashlib.sha256(raw.encode()).hexdigest() if raw is not None else None


def load_comparison(path, inputs, *, allow_subset=False, new_responses=False):
    """比较前验证完整集合、唯一绑定及成功结果身份；不把失败伪造成空七栏。"""
    bindings = read(path / 'source-binding.json')
    runs = read(path / 'run.json')
    aliases = {entry['alias'] for entry, _, _, _ in inputs}
    binding_aliases = {r['alias'] for r in bindings}
    run_aliases = {r['alias'] for r in runs}
    valid_sets = (aliases <= binding_aliases and binding_aliases == run_aliases) if allow_subset else binding_aliases == run_aliases == aliases
    if (len(aliases) != len(inputs) or len(bindings) != len(binding_aliases)
        or len(runs) != len(run_aliases) or not valid_sets):
        raise ValueError('旧结果集合不唯一或不完整')
    bindings = {r['alias']: r for r in bindings}
    runs = {r['alias']: r for r in runs}
    output = {}
    for entry, bundle, record, _ in inputs:
        alias = entry['alias']
        expected = dict(alias=alias, bundle_sha256=bundle.manifest_sha256,
                        evidence_sha256=record['evidence_sha256'],
                        response_sha256=response_digest(record))
        keys = ('alias', 'bundle_sha256', 'evidence_sha256') if new_responses else tuple(expected)
        if any(bindings[alias].get(k) != expected[k] for k in keys):
            raise ValueError('旧结果输入或响应绑定不一致')
        result = None
        if runs[alias]['status'] == 'ok':
            result = AnalysisResult.model_validate(read(path / alias / 'analysis.json'))
            if (result.bundle_id != bundle.manifest.bundle_id
                or result.ticket_ref != bundle.ticket.ticket_ref
                or result.run.bundle_sha256 != bundle.manifest_sha256):
                raise ValueError('旧结果身份或包哈希不一致')
        output[alias] = dict(status=runs[alias]['status'], result=result,
                             response_sha256=bindings[alias]['response_sha256'])
    return output


def compare_result(previous, result, status):
    """记录原始值和归一值差异；私有输出，不冒充语义判断。"""
    old = previous['result']
    changes = []
    if old is not None and result is not None:
        for name in ('start_time', 'end_time', 'cause'):
            before = getattr(old.elements, name).model_dump(mode='json')
            after = getattr(result.elements, name).model_dump(mode='json')
            formal = ('value', 'status', 'selected', 'evidence_refs')
            changed = {k: dict(before=before[k], after=after[k]) for k in formal if before[k] != after[k]}
            left = {c['id']: c for c in before['candidates']}
            right = {c['id']: c for c in after['candidates']}
            candidates = [dict(id=key, before=left.get(key), after=right.get(key))
                          for key in sorted(left.keys() | right.keys()) if left.get(key) != right.get(key)]
            if changed or candidates:
                changes.append(dict(element=name, formal=changed, candidates=candidates))
        for name in ('events', 'suggestions', 'service_identity'):
            before = old.model_dump(mode='json')[name]
            after = result.model_dump(mode='json')[name]
            if before != after:
                changes.append(dict(element=name, before=before, after=after))
        for name in ('phenomenon', 'responsible_party', 'location'):
            before = getattr(old.elements, name).model_dump(mode='json')
            after = getattr(result.elements, name).model_dump(mode='json')
            if before != after:
                changes.append(dict(element=name, before=before, after=after))
        before_steps = old.elements.handling_process.model_dump(mode='json')
        after_steps = result.elements.handling_process.model_dump(mode='json')
        if before_steps != after_steps:
            changes.append(dict(element='handling_process', before=before_steps, after=after_steps))
    old_original = old.semantic_assessment.original if old and old.semantic_assessment else None
    new_original = result.semantic_assessment.original if result and result.semantic_assessment else None
    record = result.semantic_assessment.recovery_selection if result and result.semantic_assessment else None
    return dict(before_status=previous['status'], after_status=status, changes=changes,
                model_answer_changed=old_original != new_original if old_original is not None and new_original is not None else None,
                recovery_selection=record.model_dump(mode='json') if record else None)


def comparison_summary(inputs, previous, rows):
    runs = {r['alias']: r for r in rows}
    output = {}
    for label, closed in (('closed', True), ('other', False)):
        entries = [e for e, _, _, _ in inputs if e['closed'] == closed]
        group = dict(total=len(entries), before_ok=0, after_ok=0, elements={})
        for e in entries:
            group['before_ok'] += previous[e['alias']]['status'] == 'ok'
            group['after_ok'] += runs[e['alias']]['status'] == 'ok'
        for name in ('start_time', 'end_time', 'cause'):
            counts = dict(before=0, after=0, added=0, removed=0)
            for e in entries:
                old = previous[e['alias']]['result']
                row = runs[e['alias']]
                a = bool(old and getattr(old.elements, name).value)
                b = bool(row.get('elements', {}).get(name, {}).get('filled'))
                counts['before'] += a; counts['after'] += b
                # 拒绝与成功的转换单列，不算同一已交付报告的新增/撤回。
                if old is not None and row['status'] == 'ok':
                    counts['added'] += b and not a; counts['removed'] += a and not b
            group['elements'][name] = counts
        group['status_transitions'] = dict(Counter(
            previous[e['alias']]['status'] + '->' + runs[e['alias']]['status'] for e in entries))
        output[label] = group
    return output


def evaluate(result, targets):
    """冻结目标是原先被清空的具体答案，不将整张单填出当语义正确率。"""
    rows = []
    for target in targets:
        el = getattr(result.elements, target['element'])
        # 本函数只统计正式状态；语义和范围须据冻结原文逐项核对。
        rows.append(dict(element=target['element'], expected=target['expected'],
                         filled=bool(el.value), selected=el.selected,
                         state=el.status.value, requires_semantic_review=True))
    return rows


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['replay','trial'])
    ap.add_argument('--baseline', type=Path, required=True)
    ap.add_argument('--responses', type=Path, help='离线复核新试跑保存的响应；仍与原基线输入绑定')
    ap.add_argument('--compare-local-results', type=Path, help='同一响应按旧策略重算的结果；严格校验响应绑定，分开统计本地规则效果')
    ap.add_argument('--compare-results', type=Path, help='离线模式比较已绑定的旧完整结果')
    ap.add_argument('--expectations', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--model-config', type=Path, default=Path('config/models/deepseek.json'))
    ap.add_argument('--keep-request-failures', action='store_true', help='离线保留唯一审计证实的 HTTP／连接失败，分母不变且不再请求')
    ap.add_argument('--closed-only', action='store_true', help='仅使用映射中详情已结单工单')
    ap.add_argument('--compare-new-responses', action='store_true', help='显式允许新旧模型响应不同，仍校验原包与实际证据绑定')
    ap.add_argument('--legacy-recovery', action='store_true', help='仅离线诊断：同一回答按原冲突规则处理恢复时间')
    ap.add_argument('--workers', type=int, choices=range(1,5), default=3)
    args=ap.parse_args()
    os.umask(0o077)
    baseline=args.baseline.expanduser().resolve(); out=args.out.expanduser().resolve()
    private=(Path.home()/'.noc7').resolve()
    if not out.is_relative_to(private) or out.exists() or out.is_relative_to(baseline):
        raise ValueError('输出必须为 ~/.noc7/ 下新的独立目录')
    ensure_output_allowed(DataClass.REAL,out)
    # trial 中 responses 只冻结旧请求证据；输出始终来自一次新的在线请求。
    if args.compare_local_results and args.mode != 'replay':
        raise ValueError('同一回答的本地规则对照只允许离线模式')
    if args.keep_request_failures and (args.mode != 'replay' or not args.responses):
        raise ValueError('保留请求失败仅用于指定响应目录的离线模式')
    if args.legacy_recovery and args.mode != 'replay':
        raise ValueError('旧恢复策略只允许禁网诊断')
    if args.compare_new_responses and not args.compare_results:
        raise ValueError('新回答对照必须指定旧结果目录')
    inputs=load_inputs(baseline, args.responses.expanduser().resolve() if args.responses else None,
                       closed_only=args.closed_only, keep_request_failures=args.keep_request_failures)
    if args.compare_results and args.mode != 'replay' and not args.compare_new_responses:
        raise ValueError('只允许离线比较')
    previous=load_comparison(args.compare_results.expanduser().resolve(),inputs,
                             allow_subset=args.closed_only, new_responses=args.compare_new_responses) if args.compare_results else None
    local_previous=load_comparison(args.compare_local_results.expanduser().resolve(), inputs) if args.compare_local_results else None
    targets=read(args.expectations.expanduser())
    out.mkdir(mode=0o700)
    write(out/'frozen-expectations.json',targets)
    write(out/('input-binding.json' if args.mode=='trial' else 'source-binding.json'),[dict(alias=e['alias'], bundle_sha256=b.manifest_sha256,
                                         evidence_sha256=r['evidence_sha256'],
                                         response_sha256=response_digest(r))
                                    for e,b,r,c in inputs])
    config=load_model_config(args.model_config)
    config=config.model_copy(update={'max_request_bytes':4194304,'max_retries':0})
    write(out/'config.json',config.model_dump(mode='json'))
    from noc7.providers.recovery_policy import initial_selection
    threshold=initial_selection().threshold_minutes
    write(out/'recovery-policy.json', dict(threshold_minutes=threshold, provisional=True,
          legacy_recovery=args.legacy_recovery, comparison='new_responses' if args.compare_new_responses else 'same_response'))
    if args.mode=='replay':
        # 禁止网络，旧原响应在新规则下重算不伪造缺失的模型关系。
        socket.socket=lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('离线重算禁止网络'))

    def run(item):
        entry,bundle,record,request_ctx=item
        alias=entry['alias']; folder=out/alias; folder.mkdir()
        row=dict(alias=alias,mode=args.mode,status='failed')
        result=None
        try:
            if args.mode=='replay':
                class BoundProvider:
                    name="replay:model-audit"
                    prompt_version=record.get('prompt_version')
                    def extract(self, ctx):
                        if 'raw_response' not in record:
                            from noc7.providers.text_config import TextProviderError
                            raise TextProviderError('原请求失败，没有模型响应；离线保留失败，不追加请求。')
                        clean,request=prepare_evidence(ctx)
                        if (evidence_digest(clean)!=record['evidence_sha256'] or request!=record['request_evidence']):
                            raise ValueError('本次解析证据与保存响应的实际请求不同，停止重算')
                        return OpenAICompatibleTextProvider._decode_payload(record['raw_response'].encode(),clean,
                                                                           legacy_recovery=args.legacy_recovery)
                provider=BoundProvider()
            else:
                online=OpenAICompatibleTextProvider(config,audit_dir=folder/'audit')
                class BoundProvider:
                    name=online.name
                    prompt_version=online.prompt_version
                    def extract(self,ctx):
                        clean,request=prepare_evidence(ctx)
                        if (evidence_digest(clean)!=record['evidence_sha256'] or request!=record['request_evidence']):
                            raise ValueError('本次解析证据与基线实际请求不同，停止该单发送')
                        return online.extract(ctx)
                provider=BoundProvider()
            result,fullctx,data=analyze_with_context(entry['source'],provider)
            write_reports(result,folder,report_type='closure' if entry['closed'] else 'stage')
            save_replay(folder/'replay.json',fullctx,data)
            reloaded=ReplayProvider(folder/'replay.json').extract(fullctx)
            validate_extraction(fullctx,reloaded)
            row['replay_equal']=reloaded.model_dump(mode='json')==data.model_dump(mode='json')
            if args.mode=='replay':
                write(folder/'extraction.json',data.model_dump(mode='json'))
            row['status']='ok'
            row['elements']={n:dict(filled=bool(getattr(data.elements,n).value),
                                   candidates=len(getattr(data.elements,n).candidates),
                                   status=getattr(data.elements,n).status.value)
                             for n in ('start_time','end_time','cause')}
            row['checks']=dict(Counter(c.outcome for c in data.semantic_assessment.checks))
            selection=data.semantic_assessment.recovery_selection
            row['recovery_selection']=selection.model_dump(mode='json') if selection else None
            if result:
                row['normalization']=independent_time_metrics(result,bundle.manifest.default_timezone)
                row['targets']=evaluate(result,[t for t in targets if t['alias']==alias])
                with ZipFile(folder/'company_report.docx') as z:
                    row['word_valid']=z.testzip() is None
        except Exception as exc:
            row.update(status='rejected' if isinstance(exc,ExtractionRejected) else 'failed',
                       issue_codes=sorted({i.code.value for i in getattr(exc,'issues',[])}))
            write(folder/'failure.json',dict(type=type(exc).__name__,traceback=traceback.format_exc()))
        if previous is not None:
            write(folder/'comparison.json',compare_result(previous[alias],result,row['status']))
        if local_previous is not None:
            write(folder/'local-comparison.json',compare_result(local_previous[alias],result,row['status']))
        write(folder/'metrics.json',row)
        return row

    rows=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for f in as_completed([pool.submit(run,item) for item in inputs]):
            row=f.result(); rows.append(row)
            print(row['alias'],row['status'],f'{len(rows)}/{len(inputs)}',flush=True)
            write(out/'run.json',sorted(rows,key=lambda r:r['alias']))
    if args.mode == 'trial':
        bindings=[]
        for e,b,original,_ in inputs:
            audits=[read(p) for p in (out/e['alias']/'audit').glob('*.json')]
            if len(audits)>1:
                raise ValueError('单次试跑产生多份审计，不能猜选响应')
            actual=audits[0] if audits else {}
            if actual and (actual['bundle_sha256']!=b.manifest_sha256
                           or actual['evidence_sha256']!=original['evidence_sha256']):
                raise ValueError('新请求审计的包或证据发生变化')
            bindings.append(dict(alias=e['alias'], bundle_sha256=b.manifest_sha256,
                                 evidence_sha256=original['evidence_sha256'], response_sha256=response_digest(actual)))
        write(out/'source-binding.json',bindings)
    summary=dict(cases=len(rows),outcomes=dict(Counter(r['status'] for r in rows)),
                 elements={n:dict(filled=sum(r.get('elements',{}).get(n,{}).get('filled',False) for r in rows),
                                  candidates=sum(r.get('elements',{}).get(n,{}).get('candidates',0) for r in rows))
                           for n in ('start_time','end_time','cause')},
                 normalization=dict(sum((Counter(r.get('normalization',{}).get('counts',{})) for r in rows),Counter())),
                 recovery_outcomes=dict(Counter((r.get('recovery_selection') or {}).get('outcome','unavailable') for r in rows)),
                 threshold_minutes=threshold, threshold_provisional=True,
                 external_services=args.mode=='trial',semantic_accuracy=None,
                 limitation='冻结目标的语义与推测范围必须逐项复核；旧响应缺新关系不算新语义能力。')
    if previous is not None:
        summary['comparison']=comparison_summary(inputs,previous,rows)
    if local_previous is not None:
        summary['local_comparison']=comparison_summary(inputs,local_previous,rows)
    write(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__': main()
