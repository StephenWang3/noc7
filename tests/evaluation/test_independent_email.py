"""人工审定的截止前邮件仍须通过来源、时间、正文与隔离验证。"""

import hashlib
import json

import pytest

from noc7.bundle import load_bundle
from noc7.evaluation.prepare import prepare

from tests.evaluation.test_evaluation import dump, sample  # noqa: F401


def write_material(root, name, data):
    dump(root / name, data)
    manifest = json.loads((root / "manifest.json").read_text())
    raw = (root / name).read_bytes()
    m = next(m for m in manifest["materials"] if m["path"] == name)
    m.update(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw))
    dump(root / "manifest.json", manifest)


def independent_sample(sample):
    tmp, root, selection, quote = sample
    logs = json.loads((root / "process_log.json").read_text())
    logs["entries"][2]["emails"] = []
    logs["entries"] += [
        dict(seq=6, recorded_at="2026-01-01 00:20:00", action="邮件关联处理",
             entry_kind="email", content="<br>" + quote, emails=["M03"]),
        dict(seq=7, recorded_at="2026-01-01 00:20:01", action="内部记录",
             entry_kind="ai_summary", content=quote, emails=["M03"]),
    ]
    write_material(root, "process_log.json", logs)
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["materials"][2]["origin"] = {"log_seq": 6}
    dump(root / "manifest.json", manifest)
    d = json.loads(selection.read_text())
    c = d["cases"][0]
    c["independent_emails"] = [dict(log_seq=6, material_id="M03", quote=quote,
                                    provenance="已核对原始邮件来源与时间，邮件早于结案且不是由参考报告衍生。")]
    c["facts"][0]["support"] = [dict(anchor={"material_id": "M03", "message_index": 0}, quote=quote)]
    dump(selection, d)
    return tmp, root, selection, quote


def test_reviewed_original_email_survives_but_reference_and_summary_do_not(sample):
    tmp, root, selection, _ = independent_sample(sample)
    cases = prepare(selection, tmp / "dataset")
    assert cases[0]["status"] == "ok"
    bundle = load_bundle(tmp / "dataset/inputs/E01")
    assert [e.seq for e in bundle.process_log.entries] == [1, 6]
    assert "M03" in {m.id for m in bundle.manifest.materials}
    assert cases[0]["support"][0] and all(ref.startswith("M03/") for ref in cases[0]["support"][0])
    assert cases[0]["independent_emails"]
    assert next(d for d in cases[0]["decisions"] if d["where"] == "log:6")["reason"] == "independent_preclosure_email"


def test_without_explicit_review_html_copy_stays_excluded(sample):
    tmp, _, selection, _ = independent_sample(sample)
    d = json.loads(selection.read_text())
    del d["cases"][0]["independent_emails"]
    dump(selection, d)
    cases = prepare(selection, tmp / "dataset")
    bundle = load_bundle(tmp / "dataset/inputs/E01")
    assert [e.seq for e in bundle.process_log.entries] == [1]
    assert "M03" not in {m.id for m in bundle.manifest.materials}
    assert cases[0]["support"] == [[]]


@pytest.mark.parametrize("failure", ["after_cutoff", "no_time", "human_copy", "reference_anchor", "wrong_quote", "derived", "wrong_origin", "second_original"])
def test_independent_flag_cannot_override_invalid_provenance(sample, failure):
    tmp, root, selection, _ = independent_sample(sample)
    d = json.loads(selection.read_text())
    logs = json.loads((root / "process_log.json").read_text())
    entry = next(e for e in logs["entries"] if e["seq"] == 6)
    manifest = json.loads((root / "manifest.json").read_text())
    if failure == "after_cutoff":
        entry["recorded_at"] = "2026-01-01 02:00:00"
    elif failure == "no_time":
        entry["recorded_at"] = None
    elif failure == "human_copy":
        entry["entry_kind"] = "human"
    elif failure == "reference_anchor":
        d["cases"][0]["sources"][0]["anchor"]["log_seq"] = 6
    elif failure == "wrong_quote":
        d["cases"][0]["independent_emails"][0]["quote"] = "不存在于邮件或日志中的合成原文依据。"
    elif failure == "derived":
        manifest["materials"][2]["derived"] = True
    elif failure == "wrong_origin":
        manifest["materials"][2]["origin"] = {"log_seq": 3}
    elif failure == "second_original":
        logs["entries"][0]["emails"] = ["M03"]
    dump(root / "manifest.json", manifest)
    write_material(root, "process_log.json", logs)
    dump(selection, d)
    assert prepare(selection, tmp / "dataset")[0]["status"] == "excluded"


@pytest.mark.parametrize("extra", [
    "<p>结案结论：合成结果</p>",
    "<blockquote>故障处理报告：合成结果</blockquote>",
    "<blockquote>结<b>案</b>结论：合成结果</blockquote>",
])
@pytest.mark.parametrize("where", ["log", "email"])
def test_reviewed_quote_does_not_allow_final_markers_elsewhere(sample, extra, where):
    tmp, root, selection, _ = independent_sample(sample)
    if where == "log":
        logs = json.loads((root / "process_log.json").read_text())
        next(e for e in logs['entries'] if e['seq'] == 6)['content'] += extra
        write_material(root, 'process_log.json', logs)
    else:
        p = root / 'emails/a.html'
        p.write_text(p.read_text() + extra)
        manifest = json.loads((root / 'manifest.json').read_text())
        m = manifest['materials'][2]
        m.update(sha256=hashlib.sha256(p.read_bytes()).hexdigest(), size_bytes=p.stat().st_size)
        dump(root / 'manifest.json', manifest)
    assert prepare(selection, tmp / 'dataset')[0]['status'] == 'excluded'


@pytest.mark.parametrize('where', ['log', 'email', 'quoted_email'])
def test_reviewed_quote_does_not_exempt_another_reference_fact(sample, where):
    tmp, root, selection, quote = independent_sample(sample)
    extra = '备用模块已经永久退服并转入回收流程。'
    d = json.loads(selection.read_text())
    ref = tmp / 'reference.txt'
    ref.write_text(quote + '\n' + extra)
    d['cases'][0]['sources'][0]['sha256'] = hashlib.sha256(ref.read_bytes()).hexdigest()
    d['cases'][0]['facts'].append(dict(element='phenomenon', source_id='H1', quote=extra,
                                     key_points=[{'any_of': ['备用模块']}], support=[]))
    logs = json.loads((root / 'process_log.json').read_text())
    logs['entries'][2]['content'] = quote + '\n' + extra
    if where == 'log':
        next(e for e in logs['entries'] if e['seq'] == 6)['content'] += extra
    else:
        p = root / 'emails/a.html'
        p.write_text(p.read_text() + ('<blockquote>' + extra + '</blockquote>' if where == 'quoted_email' else '<p>' + extra + '</p>'))
        manifest = json.loads((root / 'manifest.json').read_text())
        manifest['materials'][2].update(sha256=hashlib.sha256(p.read_bytes()).hexdigest(), size_bytes=p.stat().st_size)
        dump(root / 'manifest.json', manifest)
    write_material(root, 'process_log.json', logs)
    dump(selection, d)
    assert prepare(selection, tmp / 'dataset')[0]['status'] == 'excluded'
