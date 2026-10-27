#!/usr/bin/env python3
"""已登录 Chrome → 本机真实工单包；不向 NOC 写入，不调用模型或 OCR。"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import shlex
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from noc7.bundle import load_bundle

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_ROOT = Path.home() / '.noc7' / 'real'


def private_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    # 拒绝当前仓库、其他 git 工作树及源码副本；resolve 同时检查符号链接。
    if root == REPO or REPO in root.parents:
        raise ValueError('真实数据目录必须在仓库外')
    for parent in (root, *root.parents):
        if (parent / '.git').exists() or (parent / 'pyproject.toml').exists():
            raise ValueError('真实数据目录不能位于代码项目中')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    return root


def dump(path: Path, data: object) -> None:
    """只写私有临时文件，再原子替换；不跟随最终路径的符号链接。"""
    # 每次写入都复核父目录，防止运行目录里的旧符号链接指回代码仓库。
    private_root(path.parent)
    fd, tmp = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def text(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def key(value: str) -> str:
    value = re.sub(r'(?<!^)(?=[A-Z])', '_', value).lower()
    value = re.sub('[^a-z0-9_]', '_', value).strip('_')
    return value if re.match('^[a-z]', value) else 'source_' + value


BUSINESS_FIELDS = {
    'faultNo': ('ticket_no', '故障单编号'), 'customerName': ('customer', '客户名称'),
    'faultDealTimeLength': ('duration_returned', '故障处理历时(返单)(分钟)'),
    'faultStartTime': ('occurred_at', '故障发生时间'),
    'faultRecoveryTime': ('recovered_at', '故障恢复时间'),
    'faultReason': ('cause', '故障原因'), 'remark': ('description', '故障描述'),
    'descriptionNew': ('fault_type', '报障类型（新）'),
    'description': ('source_fault_type', '报障类型（原）'),
    'circuitCode': ('circuit_id', '电路编号（原）'),
    'circuitCodeNew': ('circuit_id_new', '电路编号（新）'),
    'creationDate': ('created_at', '建单时间'),
}
WORKFLOW_FIELDS = {
    'alarmTitle': ('alarm_title', '告警标题'), 'alarmTime': ('alarm_time', '告警时间'),
    'cleanUpTime': ('alarm_cleared_at', '告警清除时间'),
    'alarmUniqueId': ('alarm_serial', '告警流水号'),
    'locationInfo': ('device_location', '位置信息'), 'neName': ('device_name', '设备名称'),
    'equipmentClass': ('device_type', '设备类型'), 'vendor': ('vendor', '供应商'),
    'remark': ('description', '描述'), 'circuitCode': ('circuit_id', '电路编号'),
}
LABEL_FIELDS = {'故障原因': 'cause', '可能原因': 'possible_causes', '故障描述': 'description',
                '中继名称': 'trunk_name', '故障发生时间': 'occurred_at',
                '故障恢复时间': 'recovered_at', '客户名称': 'customer', '电路编号': 'circuit_id'}


def form_labels(value: object) -> dict:
    labels = {}
    if isinstance(value, dict):
        if value.get('model') and value.get('label'):
            labels[value['model']] = value['label']
        for item in value.values():
            labels.update(form_labels(item))
    elif isinstance(value, list):
        for item in value:
            labels.update(form_labels(item))
    return labels


def make_ticket(c: dict) -> dict:
    row, info = c['row'], c['info']
    fields, used = [], set()
    business = c['layout'] == 'business'
    network = c['layout'] == 'network'
    labels = {} if business or network else form_labels(info.get('formDefinition'))
    values = info if business or network else info['formData']
    mapping = BUSINESS_FIELDS if business else WORKFLOW_FIELDS
    if network:
        mapping = {'sheetNo':('ticket_no','故障单编号'),'sheetCreateTime':('created_at','创建时间'),
                   'alarmCreateTime':('alarm_time','告警发生时间'),'alarmClearTime':('alarm_cleared_at','告警清除时间'),
                   'faultPhenomenon':('description','故障现象'),'faultComment':('fault_comment','故障备注'),
                   'alarmTitle':('alarm_title','告警标题'),'neName':('device_name','网元名称')}
    for name, value in values.items():
        if name.startswith(('mongo_', '_')):
            continue
        label = labels.get(name, name)
        k, label = mapping.get(name, (LABEL_FIELDS.get(label, key(name)), label))
        if k in used:
            k = 'source_' + key(name)
        used.add(k)
        if not business and isinstance(value, dict) and 'sourceValue' in value:
            value = value['sourceValue'].get('defaultValue')
        fields.append({'key': k, 'label': label, 'value': text(value),
                       'section': '业务详情' if business else '流程表单'})
    family = 'business'
    if network:
        family = 'other'
    elif not business:
        family = next((v for k, v in [('板卡', 'device'), ('设备', 'device'), ('中继', 'trunk'),
                                      ('大客户', 'key_account')] if k in row.get('orderType', '')), 'other')
    return {'ticket_ref': info['faultNo'] if business else (info['sheetNo'] if network else row['orderId']),
            'title': row.get('display_title') or row.get('orderTitle') or '',
            'ticket_family': family,
            'category': (info.get('descriptionNew') or info.get('description')) if business else (info.get('orgType') if network else row.get('orderType')),
            'status': {'list_status': row.get('orderStatus'),
                       'detail_status': info.get('status') if business else (info.get('sheetStatus') if network else info['processInstance'].get('processStateName'))},
            'fields': fields, 'related_tickets': []}


def normalize_logs(c: dict) -> tuple[list, dict]:
    logs = c['logs']
    if c['layout'] == 'business':
        # 对齐页面的编号过程；邮件/内部记录原本无编号，置于编号过程之后，映射另存。
        ordered = sorted(enumerate(logs), key=lambda x: x[1].get('dealTime') or '', reverse=True)
        numbered = [x for x in ordered if x[1].get('nodeCnName') not in ('邮件关联处理', '内部记录')]
        extra = [x for x in ordered if x[1].get('nodeCnName') in ('邮件关联处理', '内部记录')]
        ordered = list(reversed(numbered)) + list(reversed(extra))
    else:
        ordered = list(enumerate(logs))
        ordered += [(len(logs)+i, x) for i, x in enumerate(c.get('extra_logs') or [])]
    entries, indices = [], {}
    for i, (idx, item) in enumerate(ordered, 1):
        indices[idx] = i
        action = item.get('nodeCnName') or item.get('taskName') or item.get('processType') or item.get('actionName') or '追加记录'
        actor = item.get('dealName') or item.get('operatorName') or item.get('createByUserName') or item.get('opPerson')
        ai = bool(re.search(r'AI|数字员工|智能摘要', action + (actor or '')))
        flag = item.get('hasAttachments')
        if flag is not None and not isinstance(flag, bool):
            raise ValueError('附件标志结构已变化')
        entries.append({'seq': i, 'recorded_at': item.get('dealTime') or item.get('operateTime') or item.get('createTime') or item.get('completedTime'),
                        'actor': actor, 'actor_org': item.get('deptName') or item.get('opDeptName'), 'action': action,
                        'content': item.get('remark') or item.get('operateMessage') or item.get('processNote') or item.get('processSuggestion') or '',
                        'entry_kind': 'ai_summary' if ai else ('email' if item.get('emailIds') else 'human'),
                        'attachment_flag': flag, 'attachments': [], 'emails': []})
    return entries, indices


def file_kind(name: str, data: bytes) -> tuple[str, str, str]:
    suffix = Path(name).suffix.lower()
    if data.startswith(b'%PDF-'):
        return 'pdf', 'application/pdf', '.pdf'
    if suffix == '.pdf':
        raise ValueError('PDF 扩展名与文件签名不符')
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image', 'image/png', '.png'
    if data.startswith(b'\xff\xd8\xff'):
        return 'image', 'image/jpeg', '.jpg'
    if suffix == '.eml':
        from email import policy
        from email.parser import BytesParser
        message = BytesParser(policy=policy.default).parsebytes(data)
        if not any(message.get(k) for k in ('From', 'Subject', 'Date', 'Message-ID')):
            raise ValueError('EML 没有可识别的邮件头')
        return 'email_eml', 'message/rfc822', '.eml'
    if suffix == '.docx':
        import io
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if 'word/document.xml' not in z.namelist():
                    raise ValueError('DOCX 缺少文档主体')
        except zipfile.BadZipFile as exc:
            raise ValueError('DOCX 文件签名错误') from exc
        return 'docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', suffix
    return 'other', 'application/octet-stream', '.bin'


def publish(c: dict, root: Path) -> Path:
    root = private_root(root)
    if c.get('capture_version') != 1 or c.get('kind') != 'ticket' or not c.get('finished_at'):
        raise ValueError('采集未完成，不能发布工单包')
    ticket = make_ticket(c)
    entries, indices = normalize_logs(c)
    digest = hashlib.sha256(('bundle-v2\n' + str(c['row']['id']) + '\n' + c['captured_at']).encode()).hexdigest()[:20]
    target = root / ('REAL-' + digest)
    if target.exists():
        load_bundle(target)
        return target
    stage = Path(tempfile.mkdtemp(prefix='.partial-', dir=root))
    materials = []
    def add(path: str, kind: str, data: bytes, mime: str, seq: int | None = None, note: str = '') -> str:
        mid = f'M{len(materials)+1:02d}'
        p = stage / path
        p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        p.write_bytes(data)
        p.chmod(0o600)
        materials.append({'id': mid, 'kind': kind, 'path': path,
                          'sha256': hashlib.sha256(data).hexdigest(), 'size_bytes': len(data),
                          'media_type': mime, 'origin': {'log_seq': seq, 'note': note or '只读导出原始材料'}})
        return mid
    def json_bytes(value: object) -> bytes:
        return (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()
    try:
        add('ticket.json', 'ticket_fields', json_bytes(ticket), 'application/json')
        # 原始响应和序号映射同样登记哈希；临时授权参数不会进入 capture。
        source_capture = {**c, 'files': [{k: v for k, v in f.items() if k != 'base64'} for f in c.get('files', [])]}
        add('source/capture.json', 'other', json_bytes(source_capture), 'application/json',
            note='只读响应存档；保留未归一化字段、详情、原始日志与邮件头')
        add('source/log-map.json', 'other', json_bytes({'raw_log_index_to_seq': indices}), 'application/json',
            note='编号过程沿用页面序号；原无编号的邮件/内部记录置于编号过程后')
        details_to_seq = {}
        for di, d in enumerate(c.get('details', [])):
            row = d['row']
            # 只做精确匹配，拒绝按十秒容差或最后一条记录猜附件归属。
            matches = [indices[i] for i, l in enumerate(c['logs'])
                       if l.get('dealName') == row.get('operaUserName')
                       and l.get('dealTime') and l.get('dealTime') == row.get('deletionDate')]
            seq = matches[0] if len(matches) == 1 else None
            details_to_seq[di] = seq
            body = '\n'.join(str(f.get('label') or f.get('id') or '') + ': ' + (text(f.get('defaultValue')) or '')
                             for f in d.get('fields', []) if not f.get('isHidden'))
            add(f'details/{di+1:03d}.txt', 'text', body.encode(), 'text/plain', seq,
                note=f"{d.get('type', '记录')}表单原文；精确日志匹配" if seq else '详情表单；未找到唯一对应日志，未猜测归属')
        import html
        email_materials = {}
        for ei, e in enumerate(c.get('emails', [])):
            eid = str(e.get('emailId') or e.get('id') or '')
            header = '\n'.join(k + ': ' + (text(e.get(k)) or '') for k in ('fromAddress', 'recipients', 'ccList', 'subject', 'sendTime', 'receiveTime') if e.get(k) is not None)
            body = ('<pre>' + html.escape(header) + '</pre>\n' + e['htmlContent']) if e.get('htmlContent') else header + '\n\n' + (e.get('textContent') or '')
            mid = add(f'emails/{ei+1:03d}.html' if e.get('htmlContent') else f'emails/{ei+1:03d}.txt',
                      'email_html' if e.get('htmlContent') else 'text',
                      body.encode(),
                      'text/html' if e.get('htmlContent') else 'text/plain', note='完整邮件正文；头字段见 source/capture.json')
            email_materials[eid] = mid
        for idx, log in enumerate(c['logs']):
            for eid in re.split(r'[,;\s]+', str(log.get('emailIds') or log.get('emailId') or '')):
                if eid in email_materials:
                    mid = email_materials[eid]
                    if next(m for m in materials if m['id']==mid)['kind'] in ('email_html','email_eml'):
                        entries[indices[idx]-1]['emails'].append(mid)
        for fi, f in enumerate(c.get('files', [])):
            data = base64.b64decode(f['base64'], validate=True)
            if not data or len(data) != f['size_bytes']:
                raise ValueError('附件大小校验失败')
            kind, mime, suffix = file_kind(f['name'], data)
            seqs = set()
            for src in f.get('sources', []):
                if 'log_index' in src and src['log_index'] in indices:
                    seqs.add(indices[src['log_index']])
                if 'detail_index' in src and details_to_seq.get(src['detail_index']):
                    seqs.add(details_to_seq[src['detail_index']])
                if 'email_id' in src:
                    for idx, log in enumerate(c['logs']):
                        if src['email_id'] in re.split(r'[,;\s]+', str(log.get('emailIds') or '')):
                            seqs.add(indices[idx])
            mid = add(f'attachments/{fi+1:03d}{suffix}', kind, data, mime,
                      min(seqs) if seqs else None,
                      note=f"源文件名：{f['name']}；详情/邮件索引见 source/capture.json" +
                           ('；无精确日志匹配，未猜测归属' if not seqs else ''))
            for seq in seqs:
                entries[seq-1]['attachments'].append(mid)
        add('process_log.json', 'process_log', json_bytes({'entries': entries}), 'application/json')
        manifest = {'bundle_format_version': '1.0', 'bundle_id': target.name, 'data_class': 'real',
                    'source': {'kind': 'noc_export', 'tool': 'noc7-readonly-export@0.1',
                               'note': '本机只读采集；未调用外部模型；完整性及匹配记录见 source/capture.json'},
                    'captured_at': c['finished_at'], 'default_timezone': '+08:00', 'materials': materials}
        dump(stage / 'manifest.json', manifest)
        load_bundle(stage)
        os.rename(stage, target)
        return target
    except Exception:
        # 保留 .partial 供本机排错，没有通过校验就不会出现在 REAL-* 列表。
        raise


def accept_capture(envelope: dict, root: Path) -> dict:
    root = private_root(root)
    if envelope.get('status') == 'failed':
        dump(root / 'last-failure.json', envelope)
        raise ValueError('采集失败；原始错误已保存在本机 last-failure.json：' + envelope.get('error', '未知'))
    if envelope.get('status') != 'done':
        raise ValueError('没有已完成的采集结果')
    c = envelope['result']
    if c['kind'] == 'discovery':
        ident = hashlib.sha256(str(c['row']['id']).encode()).hexdigest()[:20]
        dump(root / 'discoveries' / (ident + '.json'), c)
        return {'kind': 'discovery', 'files': len(c['files'])}
    if c['kind'] == 'inspection':
        ident = hashlib.sha256(str(c['row']['id']).encode()).hexdigest()[:20]
        dump(root / 'inspections' / (ident + '.json'), c)
        return {'kind': 'inspection', 'saved': True}
    if c['kind'] == 'list':
        dump(root / 'candidates.json', c)
        return {'kind': 'list', 'count': len(c['rows']), 'total': c.get('total')}
    path = publish(c, root)
    # 本机索引允许包含真编号和匹配依据；终端仅输出数量及无业务意义的包名。
    index_path = root / 'index.json'
    index = json.loads(index_path.read_text()) if index_path.exists() else []
    if not any(x['path'] == path.name for x in index):
        index.append({'path': path.name, 'ticket_ref': make_ticket(c)['ticket_ref'],
                      'row_id': c['row']['id'], 'alias': c.get('alias'), 'match': c.get('match'),
                      'captured_at': c['finished_at'], 'warnings': c.get('warnings', [])})
        dump(index_path, index)
    b = load_bundle(path)
    return {'kind': 'ticket', 'path': path.name, 'materials': len(b.manifest.materials),
            'logs': len(b.process_log.entries), 'warnings': len(b.warnings)+len(c.get('warnings', []))}


class McpClient:
    """JSON 行 stdio MCP 客户端；响应只在本机进程中流转，绝不打印正文。"""
    def __init__(self, command: str, root: Path):
        log_path = root / 'mcp-stderr.log'
        if log_path.is_symlink():
            raise ValueError('MCP 日志不能是符号链接')
        fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        self.log = os.fdopen(fd, 'ab')
        os.chmod(log_path, 0o600)
        self.proc = subprocess.Popen(shlex.split(command), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.log, text=True, bufsize=1, start_new_session=True, cwd=root)
        self.counter = 0
        try:
            self.call('initialize', {'protocolVersion':'2024-11-05','capabilities':{},
                                    'clientInfo':{'name':'noc7-local-export','version':'0.1'}})
            self.send({'jsonrpc':'2.0','method':'notifications/initialized'})
        except BaseException:
            self.close()
            raise

    def send(self, payload):
        self.proc.stdin.write(json.dumps(payload)+'\n')
        self.proc.stdin.flush()

    def call(self, method, params):
        self.counter += 1
        ident = self.counter
        self.send({'jsonrpc':'2.0','id':ident,'method':method,'params':params})
        # 独立读线程带超时；连接失败原文保存在本机，调用者停止而不是反复重连。
        import queue
        results = queue.Queue()
        def read():
            try:
                for line in self.proc.stdout:
                    obj = json.loads(line)
                    if obj.get('id') == ident:
                        results.put(obj)
                        return
                    if 'id' in obj and 'method' in obj:
                        self.send({'jsonrpc':'2.0','id':obj['id'],'error':{'code':-32601,'message':'不支持服务端请求'}})
                results.put({'error':{'message':'MCP 进程已退出'}})
            except Exception as exc:
                results.put({'error':{'message':str(exc)}})
        threading.Thread(target=read, daemon=True).start()
        try:
            obj = results.get(timeout=90)
        except queue.Empty:
            self.close()
            raise RuntimeError('MCP 连接或调用等待超过 90 秒；已停止，请查看本机 mcp-stderr.log') from None
        if 'error' in obj:
            raise RuntimeError(json.dumps(obj['error'], ensure_ascii=False))
        return obj.get('result')

    def evaluate(self, function: str):
        r = self.call('tools/call', {'name':'browser_evaluate','arguments':{'function':function}})
        if r.get('isError'):
            raise RuntimeError('\n'.join(c.get('text','') for c in r.get('content',[])))
        for c in r.get('content', []):
            s = c.get('text','')
            if '### Result\n' in s:
                return json.JSONDecoder().raw_decode(s.split('### Result\n',1)[1].lstrip())[0]
        raise RuntimeError('浏览器工具返回格式已变化')

    def close(self):
        if self.proc.poll() is None:
            if self.proc.stdin and not self.proc.stdin.closed:
                self.proc.stdin.close()
            try:
                if os.name == 'posix':
                    os.killpg(self.proc.pid, signal.SIGTERM)
                else:
                    self.proc.terminate()
            except ProcessLookupError:
                pass
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                if os.name == 'posix':
                    os.killpg(self.proc.pid, signal.SIGKILL)
                else:
                    self.proc.kill()
                self.proc.wait()
        self.log.close()


def run(args):
    root = private_root(args.root)
    plan = json.loads(args.plan.expanduser().read_text())
    if not isinstance(plan, list) or not 1 <= len(plan) <= 20:
        raise ValueError('计划必须包含 1–20 个显式查询或工单，不遍历全库')
    client = McpClient(args.mcp_command, root)
    try:
        source = (HERE / 'browser.js').read_text()
        client.evaluate('() => { '+source+'; window.__noc7Collector=createNocCollector('+json.dumps({'intervalMs':args.interval_ms,'maxRequests':args.max_requests})+'); return {ready:true}; }')
        for job in plan:
            client.evaluate('() => window.__noc7Collector.start('+json.dumps(job)+')')
            while True:
                time.sleep(1)
                status = client.evaluate('() => window.__noc7Collector.status()')
                if status['status'] != 'running':
                    break
            envelope = client.evaluate('() => window.__noc7Collector.take()')
            print(json.dumps(accept_capture(envelope, root), ensure_ascii=False))
    except BaseException:
        try:
            client.evaluate('() => { window.__noc7Collector?.cancel(); delete window.__noc7Collector; return {stopped:true}; }')
        except Exception:
            pass
        raise
    finally:
        try:
            client.evaluate('() => { delete window.__noc7Collector; return {cleared:true}; }')
        except Exception:
            pass
        client.close()


def serve(args):
    """已有工具会话的本机桥；仅收采集结果，不能代理请求或接受文件路径。"""
    root = private_root(args.root)
    token = secrets.token_urlsafe(32)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass
        def do_POST(self):
            if self.path != '/capture' or self.headers.get('X-Noc-Export') != token:
                self.send_error(403)
                return
            n = int(self.headers.get('Content-Length', '0'))
            if not 0 < n <= 150 * 1024 * 1024:
                self.send_error(413)
                return
            try:
                result = accept_capture(json.loads(self.rfile.read(n)), root)
                code = 200
            except Exception as exc:
                result, code = {'error': str(exc)}, 400
            data = json.dumps(result, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
    server = HTTPServer(('127.0.0.1', 0), Handler)
    bridge = root / '.bridge.json'
    dump(bridge, {'url':f'http://127.0.0.1:{server.server_port}/capture','token':token})
    print('本机接收器已启动；连接信息仅存于 ~/.noc7/real/.bridge.json', flush=True)
    try:
        server.serve_forever()
    finally:
        bridge.unlink(missing_ok=True)
        server.server_close()


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=DEFAULT_ROOT, help='仓库外私有目录')
    sub = p.add_subparsers(dest='command', required=True)
    r = sub.add_parser('run', help='通过浏览器扩展执行本机采集计划')
    r.add_argument('--plan', type=Path, required=True)
    r.add_argument('--mcp-command', default='npx --yes @playwright/mcp@0.0.83 --extension', help='本机 stdio MCP 命令')
    r.add_argument('--interval-ms', type=int, default=1500)
    r.add_argument('--max-requests', type=int, default=300)
    sub.add_parser('serve', help='给当前已共享的浏览器工具会话提供本机接收器')
    v = sub.add_parser('validate', help='核验本机已发布工单包')
    args = p.parse_args()
    try:
        if args.command == 'run':
            run(args)
        elif args.command == 'serve':
            serve(args)
        else:
            root = private_root(args.root)
            bundles = [load_bundle(x) for x in root.glob('REAL-*') if x.is_dir()]
            print(f'已校验 {len(bundles)} 个真实工单包')
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
