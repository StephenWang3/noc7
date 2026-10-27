"""所有工单、报告与时间均为虚构，真实 NOC 不进入自动测试。"""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from noc7.bundle import load_bundle
from noc7.evaluation.__main__ import main
from noc7.evaluation.prepare import load_dataset, prepare, private_path
from noc7.evaluation.reference import Fact, Selection
from noc7.evaluation.score import compare, matches_points, run, score
from noc7.schema import KeyPoint
from noc7.timeparse import parse_time


def dump(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def sample(tmp_path):
    root = tmp_path / "original"
    root.mkdir()
    conclusion = "经人工复核，本次故障原因为模块失效，复位模块后业务恢复。"
    logs = [
        dict(
            seq=1,
            recorded_at="2026-01-01 00:01:00",
            action="信息追加",
            content="现场诊断发现模块失效。",
        ),
        dict(
            seq=2,
            recorded_at="2026-01-01 00:02:00",
            action="信息追加",
            content=conclusion,
        ),
        dict(
            seq=3,
            recorded_at="2026-01-01 01:00:00",
            action="结单签收",
            content=conclusion,
        ),
        dict(seq=4, recorded_at=None, action="信息追加", content="未注明时间的答案"),
        dict(
            seq=5,
            recorded_at="2026-01-01 02:00:00",
            action="信息追加",
            content="后到的结论",
        ),
    ]
    logs[0]["attachments"] = ["M04", "M05"]
    logs[2]["emails"] = ["M03"]
    data = {
        "ticket.json": dict(
            ticket_ref="FAKE-001",
            title="标题也包含最终答案",
            ticket_family="business",
            status=dict(list_status="已结单", detail_status="已结单"),
            fields=[dict(key="cause", label="原因", value="模块失效")],
        ),
        "process_log.json": dict(entries=logs),
        "emails/a.html": "<p>" + conclusion + "</p>",
        "attachments/a.txt": conclusion,
        "attachments/safe.txt": "现场读取端口计数为零。",
        "source/capture.json": {"answer": conclusion},
    }
    materials = []
    kinds = ["ticket_fields", "process_log", "email_html", "text", "text", "other"]
    for i, (name, obj) in enumerate(data.items(), 1):
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False),
            encoding="utf-8",
        )
        materials.append(
            dict(
                id=f"M{i:02d}",
                kind=kinds[i - 1],
                path=name,
                sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
                size_bytes=p.stat().st_size,
                media_type="text/plain",
                origin={"log_seq": 1 if i in (4, 5) else 3} if i > 2 else None,
            )
        )
    dump(
        root / "manifest.json",
        dict(
            bundle_format_version="1.0",
            bundle_id="REAL-FAKE",
            data_class="real",
            source={"kind": "upload"},
            captured_at="2026-01-02T00:00:00+08:00",
            default_timezone="+08:00",
            materials=materials,
        ),
    )
    ref = tmp_path / "reference.txt"
    ref.write_text(conclusion, encoding="utf-8")
    source = dict(
        id="H1",
        kind="closure_note",
        path=str(ref),
        format="text",
        sha256=hashlib.sha256(ref.read_bytes()).hexdigest(),
        author="虚构处理人",
        human_basis="明确标记人工复核的结单签收意见",
        anchor={"material_id": "M02", "log_seq": 3},
    )
    fact = dict(
        element="cause",
        source_id="H1",
        quote=conclusion,
        key_points=[{"any_of": ["模块失效", "模块损坏"]}],
        support=[
            dict(anchor={"material_id": "M02", "log_seq": 1}, quote=logs[0]["content"])
        ],
    )
    selection = tmp_path / "selection.json"
    dump(
        selection,
        {
            "cases": [
                dict(alias="E01", bundle=str(root), sources=[source], facts=[fact])
            ]
        },
    )
    return tmp_path, root, selection, conclusion


def test_physical_isolation_and_reference_freeze(sample):
    tmp, original, selection, answer = sample
    before = {
        p.relative_to(original): p.read_bytes()
        for p in original.rglob("*")
        if p.is_file()
    }
    cases = prepare(selection, tmp / "dataset")
    assert cases[0]["status"] == "ok"
    b = load_bundle(tmp / "dataset/inputs/E01")
    assert [e.seq for e in b.process_log.entries] == [1]
    assert (
        not b.ticket.fields
        and b.ticket.title == "评估输入"
        and not b.ticket.status.detail_status
    )
    assert {m.id for m in b.manifest.materials} == {"M01", "M02", "M05"}
    assert all(answer not in p.read_text() for p in b.root.rglob("*") if p.is_file())
    assert cases[0]["support"] == [["M02/log:1"]]
    assert before == {
        p.relative_to(original): p.read_bytes()
        for p in original.rglob("*")
        if p.is_file()
    }
    assert load_dataset(tmp / "dataset")
    with pytest.raises(FileExistsError):
        prepare(selection, tmp / "dataset")
    (tmp / "dataset/references.json").write_text("{}")
    with pytest.raises(ValueError, match="冻结"):
        load_dataset(tmp / "dataset")


def test_wrong_quote_and_unknown_closure_excluded(sample):
    tmp, root, selection, _ = sample
    d = json.loads(selection.read_text())
    d["cases"][0]["facts"][0]["quote"] = "伪造的结论"
    dump(selection, d)
    assert prepare(selection, tmp / "badquote")[0]["status"] == "excluded"
    d["cases"][0]["facts"][0]["quote"] = (tmp / "reference.txt").read_text()
    dump(selection, d)
    log = json.loads((root / "process_log.json").read_text())
    log["entries"][2]["recorded_at"] = None
    dump(root / "process_log.json", log)
    manifest = json.loads((root / "manifest.json").read_text())
    m = manifest["materials"][1]
    m.update(
        size_bytes=(root / "process_log.json").stat().st_size,
        sha256=hashlib.sha256((root / "process_log.json").read_bytes()).hexdigest(),
    )
    dump(root / "manifest.json", manifest)
    assert prepare(selection, tmp / "badtime")[0]["status"] == "excluded"


def test_reference_only_and_no_false_support(sample):
    tmp, _, selection, _ = sample
    d = json.loads(selection.read_text())
    d["cases"][0]["facts"][0]["support"][0]["quote"] = "不存在的原文"
    dump(selection, d)
    cases = prepare(selection, tmp / "dataset")
    assert cases[0]["support"] == [[]]
    assert (
        main(["run", "--dataset", str(tmp / "dataset"), "--out", str(tmp / "baseline")])
        == 0
    )
    assert (
        main(
            [
                "score",
                "--dataset",
                str(tmp / "dataset"),
                "--results",
                str(tmp / "baseline"),
                "--out",
                str(tmp / "scored"),
            ]
        )
        == 1
    )
    m = json.loads((tmp / "scored/summary.json").read_text())["totals"]
    assert m["reference_only"] == 1 and m["agreement"] is None and m["eligible"] == 0


def test_end_to_end_repeatability_and_input_binding(sample):
    tmp, _, selection, _ = sample
    prepare(selection, tmp / "dataset")
    run(tmp / "dataset", tmp / "baseline")
    a = score(tmp / "dataset", tmp / "baseline", tmp / "scored")
    b = score(tmp / "dataset", tmp / "baseline", tmp / "repeated")
    assert (
        a == b and a["totals"]["missing"] == 1 and a["totals"]["decision_coverage"] == 1
    )
    assert (tmp / "scored/report.md").is_file()
    r = json.loads((tmp / "baseline/E01/analysis.json").read_text())
    r["run"]["bundle_sha256"] = "a" * 64
    dump(tmp / "baseline/E01/analysis.json", r)
    assert score(tmp / "dataset", tmp / "baseline", tmp / "mismatch")["failed"] == 1


def test_negation_unknown_and_candidates_are_not_hits(sample):
    _, _, selection, _ = sample
    f = Selection.model_validate_json(selection.read_text()).cases[0].facts[0]
    assert matches_points("现场检测模块损坏。", f.key_points)
    assert not matches_points("未发现模块失效。", f.key_points)
    assert not matches_points(
        "No module failure", [KeyPoint(any_of=["module failure"])]
    )
    assert compare(f, SimpleNamespace(value=None, candidates=["模块失效"])) == "missing"
    assert compare(f, SimpleNamespace(value="仍在排查")) == "pending"
    f.contradicts = ["光缆断裂"]
    assert compare(f, SimpleNamespace(value="光缆断裂")) == "conflict"
    assert compare(f, SimpleNamespace(value="未发现光缆断裂")) == "pending"
    # 否定落在要点上时不能算一致；前缀里无关的「无 / 排除」也不能把引文里的要点否决掉。
    point = [KeyPoint(any_of=["模块失效"])]
    assert not matches_points("is not a module failure", [KeyPoint(any_of=["module failure"])])
    assert not matches_points(
        "did not see module failure", [KeyPoint(any_of=["module failure"])]
    )
    assert not matches_points("模块失效已排除。", point)
    assert not matches_points("模块失效，已排除。", point)
    assert matches_points("无线侧模块失效。", point)
    assert matches_points("排除故障后业务恢复。", [KeyPoint(any_of=["业务恢复"])])
    quote = "该连接便在无需人工干预的情况下恢复了正常。"
    assert matches_points(quote, [KeyPoint(any_of=["无需人工干预"])])
    assert matches_points(quote, [KeyPoint(any_of=["恢复了正常"])])
    assert compare(f, SimpleNamespace(value="模块失效已排除。")) == "pending"
    assert compare(f, SimpleNamespace(value="无线侧模块失效。")) == "agree"
    english = f.model_copy(
        update={"key_points": [KeyPoint(any_of=["module failure"])], "quote": "module failure"}
    )
    assert compare(english, SimpleNamespace(value="is not a module failure")) == "pending"
    assert compare(english, SimpleNamespace(value="did not see module failure")) == "pending"


def test_time_semantics_timezone_and_precision():
    f = Fact(
        element="end_time",
        source_id="H1",
        quote="2026-01-01 08:00:00 GMT+8 恢复",
        expected_time={"iso": "2026-01-01T08:00:00+08:00"},
        time_kind="recovery_field",
    )
    c = SimpleNamespace(id="C1", time_kind="recovery_field")
    el = SimpleNamespace(
        value=parse_time("2026-01-01 00:00:00 UTC"), selected="C1", candidates=[c]
    )
    assert compare(f, el) == "agree"
    c.time_kind = "ticket_closed"
    assert compare(f, el) == "pending"
    c.time_kind = "recovery_field"
    el.value = parse_time("2026-01-01 08:00:00")
    assert compare(f, el) == "pending"
    el.value = parse_time("2026-01-01 08:00 GMT+8")
    assert compare(f, el) == "pending"
    f.time_precision = "minute"
    assert compare(f, el) == "agree"
    el.value = parse_time("2026-01-01 08:01 GMT+8")
    assert compare(f, el) == "conflict"


def test_date_only_reference_uses_ticket_timezone():
    f = Fact(
        element="end_time",
        source_id="H1",
        quote="2026-01-01 当天恢复",
        expected_time={"iso": "2026-01-01"},
        time_kind="recovery_field",
    )
    chosen = SimpleNamespace(id="C1", time_kind="recovery_field")
    late = SimpleNamespace(
        value=parse_time("2026-01-01 20:00:00 UTC"),
        selected="C1",
        candidates=[chosen],
    )
    # 工单口径 +08:00 下，UTC 20:00 已是次日 04:00，不能按 ISO 前 10 位算同一天。
    assert compare(f, late, "+08:00") == "conflict"
    previous = SimpleNamespace(
        value=parse_time("2025-12-31 20:00:00 UTC"),
        selected="C1",
        candidates=[chosen],
    )
    assert compare(f, previous, "+08:00") == "agree"
    assert compare(f, late, None) == "pending"
    naive = SimpleNamespace(
        value=parse_time("2026-01-01 20:00:00"),
        selected="C1",
        candidates=[chosen],
    )
    assert compare(f, naive, "+08:00") == "pending"


def test_xiaozhang_is_the_earliest_cutoff(sample):
    tmp, root, selection, _ = sample
    log = json.loads((root / "process_log.json").read_text())
    log["entries"].extend(
        [
            dict(
                seq=6,
                recorded_at="2026-01-01 00:30:00",
                action="销障",
                content="办理销障。",
            ),
            dict(
                seq=7,
                recorded_at="2026-01-01 00:40:00",
                action="信息追加",
                content="销障之后的补充记录。",
            ),
        ]
    )
    dump(root / "process_log.json", log)
    manifest = json.loads((root / "manifest.json").read_text())
    raw = (root / "process_log.json").read_bytes()
    manifest["materials"][1].update(
        sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)
    )
    dump(root / "manifest.json", manifest)
    cases = prepare(selection, tmp / "dataset")
    assert cases[0]["status"] == "ok"
    assert cases[0]["cutoff"].startswith("2026-01-01T00:30:00")
    assert [e.seq for e in load_bundle(tmp / "dataset/inputs/E01").process_log.entries] == [
        1
    ]
    reasons = {d["where"]: d["reason"] for d in cases[0]["decisions"]}
    assert reasons["log:6"] == "after_cutoff" and reasons["log:7"] == "after_cutoff"


def test_process_order_and_source_conflict(sample):
    tmp, _, selection, _ = sample
    f = Fact(
        element="handling_process",
        source_id="H1",
        quote="复位后验证恢复",
        key_points=[{"any_of": ["复位"]}, {"any_of": ["验证恢复"]}],
    )
    step = lambda text: SimpleNamespace(
        actor=None, action=text, target=None, result=None, duplicate_of=None
    )
    assert (
        compare(f, SimpleNamespace(value=[step("复位"), step("验证恢复")])) == "agree"
    )
    assert (
        compare(f, SimpleNamespace(value=[step("验证恢复"), step("复位")]))
        == "conflict"
    )
    d = json.loads(selection.read_text())
    d["cases"][0]["facts"][0]["conflict"] = True
    dump(selection, d)
    prepare(selection, tmp / "dataset")
    run(tmp / "dataset", tmp / "baseline")
    m = score(tmp / "dataset", tmp / "baseline", tmp / "scored")["totals"]
    assert m["source_conflict"] == 1 and m["determinate"] == 0


def test_private_paths_and_reference_validation(sample, tmp_path):
    _, root, selection, _ = sample
    with pytest.raises(ValueError):
        private_path(Path.cwd() / "var/evaluation")
    link = tmp_path / "link"
    link.symlink_to(Path.cwd(), target_is_directory=True)
    with pytest.raises(ValueError):
        private_path(link / "eval")
    with pytest.raises(ValueError):
        prepare(selection, root / "eval")
    d = json.loads(selection.read_text())
    d["cases"].append(d["cases"][0])
    with pytest.raises(ValueError):
        Selection.model_validate(d)
    d["cases"] = d["cases"][:1]
    d["cases"][0]["sources"][0]["sha256"] = "a" * 64
    dump(selection, d)
    assert prepare(selection, tmp_path / "wronghash")[0]["status"] == "excluded"


def test_input_snapshot_change_and_evidence_forgery(sample):
    tmp, _, selection, _ = sample
    prepare(selection, tmp / "dataset")
    run(tmp / "dataset", tmp / "baseline")
    r = json.loads((tmp / "baseline/E01/analysis.json").read_text())
    r["evidence"][0]["text"] = "伪造模块失效证据"
    dump(tmp / "baseline/E01/analysis.json", r)
    assert score(tmp / "dataset", tmp / "baseline", tmp / "forged")["failed"] == 1
    (tmp / "dataset/inputs/E01/process_log.json").write_text('{"entries":[]}')
    with pytest.raises(Exception):
        load_dataset(tmp / "dataset")


def test_polarity_and_proof_are_verified_before_scoring(sample):
    tmp, _, selection, _ = sample
    d = json.loads(selection.read_text())
    # 不能把某条确实存在但无关的原文当作事实的支持。
    d["cases"][0]["facts"][0]["support"][0]["quote"] = "现场诊断"
    dump(selection, d)
    assert prepare(selection, tmp / "unsupported")[0]["support"] == [[]]


def test_missing_source_reference_not_fabricated(sample):
    tmp, _, selection, _ = sample
    prepare(selection, tmp / "dataset")
    run(tmp / "dataset", tmp / "baseline")
    s = score(tmp / "dataset", tmp / "baseline", tmp / "scored")
    assert all(m["eligible"] == 0 for k, m in s["by_element"].items() if k != "cause")
    assert s["totals"]["determinate"] == 1
    assert all(p.stat().st_mode & 0o077 == 0 for p in (tmp / "dataset").rglob("*"))


def test_claimed_cause_cannot_be_upgraded_to_confirmed(sample):
    _, _, selection, _ = sample
    f = Selection.model_validate_json(selection.read_text()).cases[0].facts[0]
    f.allowed_statuses = ["documented"]
    assert (
        compare(f, SimpleNamespace(value="模块失效", status="confirmed")) == "conflict"
    )
    f.value_kind = "root_cause_claimed"
    c = SimpleNamespace(id="C1", cause_kind="root_cause_confirmed")
    assert (
        compare(
            f,
            SimpleNamespace(
                value="模块失效", status="documented", selected="C1", candidates=[c]
            ),
        )
        == "conflict"
    )


def test_audit_claim_requires_original_evidence(sample):
    from noc7.evaluation.reference import Source

    _, _, selection, _ = sample
    d = json.loads(selection.read_text())["cases"][0]["sources"][0]
    d["audit"] = "audited"
    with pytest.raises(ValueError, match="已审核"):
        Source.model_validate(d)


def test_time_support_does_not_depend_on_tested_extractor(sample, monkeypatch):
    from noc7.evaluation import reference

    tmp, root, selection, _ = sample
    log = json.loads((root / "process_log.json").read_text())
    log["entries"][0]["content"] = "客户确认在 2026-01-01 00:01:00 GMT+8 恢复。"
    dump(root / "process_log.json", log)
    manifest = json.loads((root / "manifest.json").read_text())
    m = manifest["materials"][1]
    m.update(
        sha256=hashlib.sha256((root / "process_log.json").read_bytes()).hexdigest(),
        size_bytes=(root / "process_log.json").stat().st_size,
    )
    dump(root / "manifest.json", manifest)
    ref = tmp / "time-reference.txt"
    ref.write_text("正式报告恢复时间：2026-01-01 00:01:00 GMT+8。")
    d = json.loads(selection.read_text())
    c = d["cases"][0]
    c["sources"] = [
        dict(
            id="R1",
            kind="formal_report",
            path=str(ref),
            format="text",
            sha256=reference.digest(ref),
            author="虚构报告人",
            human_basis="具名人工报告记载恢复时间，未进行业务审核",
        )
    ]
    c["facts"] = [
        dict(
            element="end_time",
            source_id="R1",
            quote=ref.read_text(),
            expected_time={"iso": "2026-01-01T00:01:00+08:00"},
            time_kind="customer_confirmed_recovery",
            support=[
                dict(
                    anchor={"material_id": "M02", "log_seq": 1},
                    quote=log["entries"][0]["content"],
                    time_kind="customer_confirmed_recovery",
                )
            ],
        )
    ]
    dump(selection, d)
    monkeypatch.setattr("noc7.extract.baseline.text_times", lambda *a: iter([]))
    assert prepare(selection, tmp / "dataset")[0]["support"] == [["M02/log:1"]]


def test_numbers_units_and_identifiers_do_not_match_substrings():
    point = lambda s: [KeyPoint(any_of=[s])]
    assert matches_points("丢包 25%", point("25%"))
    assert not matches_points("丢包 125%", point("25%"))
    assert not matches_points("时延 25ms", point("25%"))
    assert not matches_points("读数 -25%", point("25%"))
    assert not matches_points("读数 25.8%", point("25"))
    assert not matches_points("OTN_LOF2 告警", point("OTN_LOF"))
    assert matches_points("设备收到 OTN_LOF 告警", point("OTN_LOF"))
    assert not matches_points("Between Ruizy and Tepic", point("Ruiz"))
