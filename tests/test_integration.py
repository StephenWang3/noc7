"""合成端到端联调；绝不依赖本机真实材料。"""

import json
import shutil
import socket
from email import policy
from email.parser import BytesParser
from pathlib import Path

import pymupdf
import pytest

from noc7.batch import run_local_batch
from noc7.bundle import load_bundle, rehash_bundle
from noc7.cli import main
from noc7.extract import analyze
from noc7.ocr import LayoutResult
from noc7.parsers import ParserRegistry
from noc7.parsers.attachments.image import ImageParser
from noc7.parsers.attachments.pdf import PDFParser
from noc7.parsers.text import PARSERS
from noc7.providers import ProviderConfig, ProviderKind

BUNDLES = Path(__file__).resolve().parents[1] / "fixtures/bundles"


def clone(tmp_path, name):
    target = tmp_path / name
    shutil.copytree(BUNDLES / name, target)
    return target


def registry(parser):
    result = ParserRegistry()
    for p in [*PARSERS, parser]:
        result.register(p)
    return result


def test_default_registry_attachment_evidence_reaches_elements_and_report(tmp_path):
    from noc7.report import write_reports

    for name, mid in [("SYN-P02", "M03"), ("SYN-P04", "M03")]:
        result = analyze(BUNDLES / name)
        attachment_refs = {s.id for s in result.evidence if s.material_id == mid}
        # 全链路确实消费附件；原合成包的语义差异另列联调问题，不能假设均已裁定。
        assert any(set(c.evidence_refs) & attachment_refs for c in result.elements.cause.candidates)
        assert any(set(e.evidence_refs) & attachment_refs for e in result.events)
        assert not any(i.code == "EVIDENCE_REF_MISSING" for i in result.issues)
        write_reports(result, tmp_path / name)
        report = (tmp_path / name / "report.html").read_text()
        for ref in attachment_refs:
            assert f'id="e-{ref}"' in report


def test_eml_with_unparsed_attachment_keeps_reliable_body(tmp_path):
    root = clone(tmp_path, "SYN-P02")
    bundle = load_bundle(root)
    path = bundle.path_of(bundle.manifest.material("M03"))
    mail = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    mail.set_content("故障点位于合成测试点。")
    mail.add_attachment(b"unparsed synthetic", maintype="application", subtype="pdf", filename="synthetic.pdf")
    path.write_bytes(mail.as_bytes())
    rehash_bundle(root)
    result = analyze(root)
    assert result.materials[2].parse_status == "needs_review"
    assert result.elements.location.value
    body = [s for s in result.evidence if s.material_id == "M03" and s.locator.part == "body" and s.role == "original"]
    assert body and not any(s.needs_review for s in body)
    embedded = [s for s in result.evidence if ":mime:" in s.id]
    assert embedded and all(s.needs_review for s in embedded)
    assert all(s.id not in el.evidence_refs for s in embedded for _, el in result.elements.items())
    assert any(i.code == "MATERIAL_UNSUPPORTED" for i in result.issues)


def test_eml_compatibility_decoding_does_not_promote_uncertain_body(tmp_path):
    root = clone(tmp_path, "SYN-P02")
    b = load_bundle(root)
    path = b.path_of(b.manifest.material("M03"))
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\\r\\n"))
    rehash_bundle(root)
    r = analyze(root)
    assert r.elements.location.value is None
    assert all(s.needs_review for s in r.evidence if s.material_id == "M03")


def test_partial_pdf_preserves_readable_page_when_scan_fails(tmp_path):
    root = clone(tmp_path, "SYN-P04")
    b = load_bundle(root)
    path = b.path_of(b.manifest.material("M03"))
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 40), "Reason for outage: fiber cut")
        doc.new_page()
        doc.save(path)
    # 隔离本用例的证据源，验证完整正文能单独支撑结论，不受原包其他诊断优先级影响。
    ticket_path = root / "ticket.json"
    ticket = json.loads(ticket_path.read_text())
    ticket["fields"] = [f for f in ticket["fields"] if f["key"] in {"ticket_no", "occurred_at", "recovered_at"}]
    ticket_path.write_text(json.dumps(ticket, ensure_ascii=False))
    (root / "process_log.json").write_text('{"entries": []}')
    rehash_bundle(root)

    class BrokenOCR:
        config = ProviderConfig(name="test.local", kind=ProviderKind.LOCAL, external=False)

        def read(self, *_):
            raise RuntimeError("合成 OCR 故障")

    r = analyze(root, registry=registry(PDFParser(ocr=BrokenOCR())))
    assert next(m for m in r.materials if m.id == "M03").parse_status == "needs_review"
    assert any(ref.startswith("M03/p1:") for ref in r.elements.cause.evidence_refs)
    assert any(i.code == "MATERIAL_PARSE_FAILED" for i in r.issues)


def test_mixed_image_quality_keeps_good_observation_and_blocks_poor_reading():
    class OCR:
        name = "test.local"
        config = ProviderConfig(name=name, kind=ProviderKind.LOCAL, external=False)

        def read(self, *_):
            return LayoutResult(blocks=[
                {"text": "ping packet loss 25%", "bbox": (0, 0, 200, 20), "quality": .99},
                {"text": "光缆中断", "bbox": (0, 30, 200, 50), "quality": .4},
            ])

    r = analyze(BUNDLES / "SYN-S10", registry=registry(ImageParser(ocr=OCR())))
    assert "M04/img:r0" in r.elements.phenomenon.evidence_refs
    assert r.span("M04/img:r1").needs_review
    assert all("M04/img:r1" not in el.evidence_refs for _, el in r.elements.items())


def test_batch_continues_failure_ignores_archives_and_sanitizes_summary(tmp_path, monkeypatch, capsys):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    clone(inputs, "SYN-P01")
    broken = inputs / "broken"
    broken.mkdir()
    (broken / "manifest.json").write_text('{"private-marker": "客户隐私不可外传"}')
    (inputs / "archive").mkdir()
    clone(inputs / "archive", "SYN-S01")
    # 默认流程在连接层阻断网络后仍能完成；失败异常不会打印到终端或统计中。
    def deny_network(*_):
        raise AssertionError("批处理不能连接网络")

    monkeypatch.setattr(socket.socket, "connect", deny_network)
    out = tmp_path / "outputs"
    assert main(["local-batch", str(inputs), "--out", str(out), "--expected-count", "2"]) == 1
    summary = json.loads((out / "summary.json").read_text())
    assert [c["status"] for c in summary["cases"]] == ["ok", "failed"]
    assert (out / "R01/report.html").is_file()
    assert (out / "R02/failure.json").is_file()
    assert '客户隐私不可外传' not in (out / "summary.json").read_text()
    assert 'private-marker' not in capsys.readouterr().out
    assert 'SYN-P01' not in (out / "summary.json").read_text()
    assert (out.stat().st_mode & 0o777) == 0o700
    assert json.loads((out / "run.json").read_text())["failed"] == 1
    with pytest.raises(ValueError, match="已存在"):
        run_local_batch(inputs, out)


def test_batch_preflight_refuses_count_mismatch_and_repository_output(tmp_path):
    clone(tmp_path, "SYN-P01")
    out = tmp_path.parent / (tmp_path.name + "-out")
    with pytest.raises(ValueError, match="数量"):
        run_local_batch(tmp_path, out, expected_count=15)
    assert not out.exists()
    with pytest.raises(ValueError, match="仓库外"):
        run_local_batch(tmp_path, BUNDLES.parents[1] / "var/private-output")
