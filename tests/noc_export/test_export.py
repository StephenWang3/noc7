"""仅用虚构数据验证目录隔离、材料完整性及归属，不接触 NOC。"""
import base64
import importlib.util
import json
from pathlib import Path

import pytest

from noc7.bundle import load_bundle

SPEC = importlib.util.spec_from_file_location('noc_export', Path(__file__).parents[2] / 'scripts/noc_export/exporter.py')
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def capture():
    return {'capture_version':1, 'kind':'ticket', 'layout':'business',
            'captured_at':'2026-01-01T00:00:00+08:00', 'finished_at':'2026-01-01T00:01:00+08:00',
            'row':{'id':'fake-row','orderId':'fake-id','orderStatus':'列表状态','display_title':'虚构工单'},
            'info':{'faultNo':'FAKE-001','status':'详情状态','remark':'虚构描述'},
            'logs':[{'dealTime':'2026-01-01 00:00:00','dealName':'虚构处理人','nodeCnName':'信息追加',
                     'remark':'虚构正文','hasAttachments':False,'emailIds':'FAKE-MAIL'}],
            'details':[{'row':{'operaUserName':'虚构处理人','deletionDate':'2026-01-01 00:00:00'},
                        'fields':[]}],
            'emails':[{'emailId':'FAKE-MAIL','htmlContent':'<p>虚构正文</p>'}],
            'files':[{'name':'../../escape.pdf','base64':base64.b64encode(b'%PDF-1.4\nFAKE').decode(),
                      'size_bytes':13,'sources':[{'detail_index':0}]}], 'warnings':[]}


def test_hidden_attachment_hash_and_exact_origin(tmp_path):
    c = capture()
    c['files'][0]['size_bytes'] = len(base64.b64decode(c['files'][0]['base64']))
    root = exporter.publish(c, tmp_path / 'real')
    bundle = load_bundle(root)
    assert bundle.manifest.data_class.value == 'real'
    assert bundle.ticket.status.list_status != bundle.ticket.status.detail_status
    entry = bundle.process_log.entries[0]
    assert entry.attachment_flag is False and len(entry.attachments) == 1 and len(entry.emails) == 1
    assert bundle.manifest.material(entry.attachments[0]).kind.value == 'pdf'
    assert any('附件标志' in w for w in bundle.warnings)
    assert not (tmp_path / 'escape.pdf').exists()
    assert root.stat().st_mode & 0o077 == 0
    assert all(p.stat().st_mode & 0o077 == 0 for p in root.rglob('*'))
    assert exporter.publish(c, tmp_path / 'real') == root


def test_ambiguous_attachment_origin_stays_unassigned(tmp_path):
    c = capture()
    c['logs'].append(dict(c['logs'][0]))
    c['files'][0]['size_bytes'] = len(base64.b64decode(c['files'][0]['base64']))
    b = load_bundle(exporter.publish(c, tmp_path / 'real'))
    assert not any(e.attachments for e in b.process_log.entries)
    assert any('未猜测' in (m.origin.note or '') for m in b.manifest.materials)


def test_repo_and_symlink_output_rejected(tmp_path):
    with pytest.raises(ValueError, match='仓库外'):
        exporter.private_root(exporter.REPO / 'real')
    link = tmp_path / 'link'
    link.symlink_to(exporter.REPO, target_is_directory=True)
    with pytest.raises(ValueError, match='仓库外'):
        exporter.private_root(link / 'real')
    repo = tmp_path / 'other-repo'
    repo.mkdir()
    (repo / '.git').mkdir()
    with pytest.raises(ValueError, match='代码项目'):
        exporter.private_root(repo / 'data')


def test_incomplete_bad_attachment_and_failure_not_published(tmp_path):
    c = capture()
    c.pop('finished_at')
    with pytest.raises(ValueError, match='未完成'):
        exporter.publish(c, tmp_path)
    c = capture()
    c['files'][0]['size_bytes'] = 999
    with pytest.raises(ValueError, match='大小'):
        exporter.publish(c, tmp_path)
    assert not list(tmp_path.glob('REAL-*'))
    with pytest.raises(ValueError, match='HTTP 429'):
        exporter.accept_capture({'status':'failed','error':'HTTP 429','partial':{}}, tmp_path)
    assert json.loads((tmp_path / 'last-failure.json').read_text())['status'] == 'failed'


def test_signatures_and_eml():
    with pytest.raises(ValueError, match='签名'):
        exporter.file_kind('fake.pdf', b'<html>login</html>')
    with pytest.raises(ValueError, match='邮件头'):
        exporter.file_kind('fake.eml', b'not a mail')
    assert exporter.file_kind('mail.eml', b'From: fake@example.test\r\nSubject: fake\r\n\r\nbody')[0] == 'email_eml'


def test_workflow_labels_values_and_status():
    c = capture()
    c.update(layout='workflow', logs=[], files=[], emails=[], details=[])
    c['row'].update(orderType='板卡故障单')
    c['info']={'formData':{'alarmTitle':{'sourceValue':{'defaultValue':'虚构告警'}}},
               'formDefinition':{'list':[{'model':'alarmTitle','label':'告警标题'}]},
               'processInstance':{'processStateName':'处理中'}}
    t = exporter.make_ticket(c)
    assert t['ticket_family'] == 'device'
    assert t['fields'][0]['value'] == '虚构告警'


def test_network_void_status_and_process_text(tmp_path):
    c = capture()
    c.update(layout='network', files=[], emails=[], details=[])
    c['info']={'sheetNo':'FAKE-VOID','sheetStatus':'作废','orgType':'网络中断','faultPhenomenon':'虚构现象'}
    c['logs']=[{'completedTime':'2026-01-01 00:00:00','opPerson':'虚构处理人',
                'opDeptName':'虚构部门','actionName':'作废','processSuggestion':'虚构作废理由','hasAttachments':False}]
    b = load_bundle(exporter.publish(c, tmp_path / 'real'))
    assert b.ticket.ticket_ref == 'FAKE-VOID'
    assert b.ticket.status.detail_status == '作废'
    assert b.process_log.entries[0].content == '虚构作废理由'
    assert b.process_log.entries[0].actor_org == '虚构部门'


def test_nested_output_symlink_cannot_write_to_repo(tmp_path):
    root = exporter.private_root(tmp_path / 'real')
    (root / 'discoveries').symlink_to(exporter.REPO, target_is_directory=True)
    with pytest.raises(ValueError, match='仓库外'):
        exporter.dump(root / 'discoveries' / 'blocked.real.json', {'fake':'private'})
    assert not (exporter.REPO / 'blocked.real.json').exists()
