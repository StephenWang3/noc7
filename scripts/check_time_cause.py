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
from noc7.schema import EvidenceSpan, DataClass


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load_inputs(baseline, responses=None):
    """所有包和响应先验证，再允许任何网络调用；不按目录猜选版本。"""
    responses = responses or baseline
    output = []
    for entry in read(baseline / 'mapping.json'):
        bundle = load_bundle(entry['source'])
        if bundle.manifest_sha256 != entry['bundle_sha256']:
            raise ValueError('原输入包哈希发生变化')
        records = [read(p) for p in (responses / entry['alias']).glob('audit*/*.json')]
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
            text=c.time.raw.strip().replace('：',':')
            m=re.fullmatch(r'(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?\s*(?:T?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*(.*?)',text)
            dayfirst=re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})\s*(.*)',text)
            expected=None
            try:
                if m or dayfirst:
                    if m: y,mo,da,h,mi,se,tail=m.groups()
                    else: da,mo,y,h,mi,tail=dayfirst.groups(); se=None
                    if h is None:
                        expected=dict(iso=f'{int(y):04d}-{int(mo):02d}-{int(da):02d}',precision='day',tz_source='unknown',utc_offset=None)
                    elif not tail or zone_offset(tail):
                        zone=zone_offset(tail) if tail else None
                        explicit=zone is not None
                        anchor=c.relation.timezone_anchor if c.relation else None
                        if not explicit and anchor:
                            matches=re.findall(r'\b(?:UTC|GMT)(?:\s*[+-]\s*\d{1,2}(?::?\d{2})?)?|[+-]\d{2}:?\d{2}|北京时间|香港时间',anchor.quote,re.I)
                            if len(set(matches))==1:
                                zone=zone_offset(matches[0]); explicit=zone is not None
                        if zone is None and all(spans[r].locator.type=='field' for r in c.evidence_refs):
                            zone=default_timezone
                        dt=datetime(int(y),int(mo),int(da),int(h),int(mi),int(se or 0))
                        expected=dict(iso=dt.isoformat()+(zone or ''),precision='second' if se else 'minute',
                                      utc_offset=zone,tz_source='explicit' if explicit else 'assumed' if zone else 'unknown')
                elif re.match('[A-Za-z]{3},',text):
                    dt=parsedate_to_datetime(text); zone=dt.strftime('%z');zone=zone[:3]+':'+zone[3:]
                    expected=dict(iso=dt.isoformat(),precision='second',tz_source='explicit',utc_offset=zone)
            except (ValueError,TypeError,OverflowError):
                expected=None
            state='not_assessed' if expected is None else 'match' if all(getattr(c.time,k)==v for k,v in expected.items()) else 'mismatch'
            rows.append(dict(element=name,candidate=c.id,state=state))
    return dict(counts=dict(Counter(r['state'] for r in rows)),items=rows)


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
    ap.add_argument('--expectations', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--model-config', type=Path, default=Path('config/models/deepseek.json'))
    ap.add_argument('--workers', type=int, choices=range(1,5), default=3)
    args=ap.parse_args()
    os.umask(0o077)
    baseline=args.baseline.expanduser().resolve(); out=args.out.expanduser().resolve()
    private=(Path.home()/'.noc7').resolve()
    if not out.is_relative_to(private) or out.exists() or out.is_relative_to(baseline):
        raise ValueError('输出必须为 ~/.noc7/ 下新的独立目录')
    ensure_output_allowed(DataClass.REAL,out)
    if args.mode == "trial" and args.responses:
        raise ValueError("在线试跑不能指定替代响应")
    inputs=load_inputs(baseline, args.responses.expanduser().resolve() if args.responses else None)
    targets=read(args.expectations.expanduser())
    out.mkdir(mode=0o700)
    write(out/'frozen-expectations.json',targets)
    write(out/'source-binding.json',[dict(alias=e['alias'], bundle_sha256=b.manifest_sha256,
                                         evidence_sha256=r['evidence_sha256'],
                                         response_sha256=hashlib.sha256(r['raw_response'].encode()).hexdigest())
                                    for e,b,r,c in inputs])
    config=load_model_config(args.model_config)
    config=config.model_copy(update={'max_request_bytes':4194304,'max_retries':0})
    write(out/'config.json',config.model_dump(mode='json'))
    if args.mode=='replay':
        # 禁止网络，旧原响应在新规则下重算不伪造缺失的模型关系。
        socket.socket=lambda *a,**kw: (_ for _ in ()).throw(RuntimeError('离线重算禁止网络'))

    def run(item):
        entry,bundle,record,request_ctx=item
        alias=entry['alias']; folder=out/alias; folder.mkdir()
        row=dict(alias=alias,mode=args.mode,status='failed')
        try:
            if args.mode=='replay':
                class BoundProvider:
                    name="replay:model-audit"
                    prompt_version=record.get('prompt_version')
                    def extract(self, ctx):
                        clean,request=prepare_evidence(ctx)
                        if (evidence_digest(clean)!=record['evidence_sha256'] or request!=record['request_evidence']):
                            raise ValueError('本次解析证据与保存响应的实际请求不同，停止重算')
                        return OpenAICompatibleTextProvider._decode(record['raw_response'].encode(),clean)
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
            if result:
                row['normalization']=independent_time_metrics(result,bundle.manifest.default_timezone)
                row['targets']=evaluate(result,[t for t in targets if t['alias']==alias])
                with ZipFile(folder/'company_report.docx') as z:
                    row['word_valid']=z.testzip() is None
        except Exception as exc:
            row.update(status='rejected' if isinstance(exc,ExtractionRejected) else 'failed',
                       issue_codes=sorted({i.code.value for i in getattr(exc,'issues',[])}))
            write(folder/'failure.json',dict(type=type(exc).__name__,traceback=traceback.format_exc()))
        write(folder/'metrics.json',row)
        return row

    rows=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for f in as_completed([pool.submit(run,item) for item in inputs]):
            row=f.result(); rows.append(row)
            print(row['alias'],row['status'],f'{len(rows)}/{len(inputs)}',flush=True)
            write(out/'run.json',sorted(rows,key=lambda r:r['alias']))
    summary=dict(cases=len(rows),outcomes=dict(Counter(r['status'] for r in rows)),
                 elements={n:dict(filled=sum(r.get('elements',{}).get(n,{}).get('filled',False) for r in rows),
                                  candidates=sum(r.get('elements',{}).get(n,{}).get('candidates',0) for r in rows))
                           for n in ('start_time','end_time','cause')},
                 normalization=dict(sum((Counter(r.get('normalization',{}).get('counts',{})) for r in rows),Counter())),
                 external_services=args.mode=='trial',semantic_accuracy=None,
                 limitation='冻结目标的语义与推测范围必须逐项复核；旧响应缺新关系不算新语义能力。')
    write(out/'summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__': main()
