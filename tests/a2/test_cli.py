import json
from dataclasses import replace

from noc7.bundle import load_bundle
from noc7.parsers.attachments.__main__ import main
from noc7.schema.common import DataClass
from noc7.parsers import ParseOutput
from tests.conftest import BUNDLES, ROOT


def test_cli_eml_json_schema_and_disclosure(tmp_path):
    out = tmp_path / "result.json"
    assert main([str(BUNDLES / "SYN-P02"), "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["data_class"] == "synthetic"
    assert "尚未验证真实 PDF/EML" in data["validation_scope"]
    assert data["outputs"][0]["status"] == "parsed"


def test_cli_keeps_instruction_as_issue(tmp_path):
    out = tmp_path / "result.json"
    # 用 DOCX 的正文解析与嵌入指令检测演示普通模式，不需要 OCR。
    assert main([str(BUNDLES / "SYN-P03"), "--strict", "--out", str(out)]) == 0
    assert any(i["code"] == "EMBEDDED_INSTRUCTION" for i in json.loads(out.read_text())["outputs"][0]["issues"])


def test_cli_strict_review_exit_code(monkeypatch, tmp_path):
    monkeypatch.setattr("noc7.parsers.attachments.__main__.parse_attachments", lambda *args, **kwargs: [
        ParseOutput(material_id="M03", parser="test", status="needs_review")])
    out = tmp_path / "result.json"
    assert main([str(BUNDLES / "SYN-P02"), "--out", str(out)]) == 0
    assert main([str(BUNDLES / "SYN-P02"), "--strict", "--out", str(out)]) == 1


def test_cli_refuses_real_result_inside_repo(monkeypatch, capsys):
    bundle = load_bundle(BUNDLES / "SYN-P02")
    bundle = replace(bundle, manifest=bundle.manifest.model_copy(update={"data_class": DataClass.REAL}))
    monkeypatch.setattr("noc7.parsers.attachments.__main__.load_bundle", lambda *args: bundle)
    output = ROOT / "var" / "must-not-write-real.json"
    assert main(["unused", "--out", str(output)]) == 2
    assert not output.exists()
    assert "不能写入源码仓库" in capsys.readouterr().err
