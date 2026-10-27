import json

import pytest
from bs4 import BeautifulSoup

from noc7.cli import main
from noc7.report import render, write_reports
from noc7.schema import DataClass

from .conftest import BUNDLES


@pytest.mark.parametrize("format", ["md", "html"])
@pytest.mark.parametrize("report_type", ["stage", "closure"])
def test_report_contains_required_sections_and_unknowns(results, format, report_type):
    text = render(results["SYN-S09"], format=format, report_type=report_type)
    for phrase in [
        "数据截止",
        "事件概述",
        "七要素",
        "关键处理时间线",
        "恢复与验证情况",
        "未决事项",
        "内部证据索引",
        "审核记录",
        "未知",
        "暂不计算",
        "客户反馈",
        "检查显示",
        "尚未人工审核",
    ]:
        assert phrase in text
    assert ("阶段报告" if report_type == "stage" else "结案草稿") in text


def test_html_links_resolve_to_local_evidence_and_css(results, tmp_path):
    write_reports(results["SYN-S10"], tmp_path)
    soup = BeautifulSoup((tmp_path / "report.html").read_text(), "html.parser")
    ids = {node["id"] for node in soup.select("[id]")}
    assert all(a["href"][1:] in ids for a in soup.select("a[href]"))
    assert soup.find("link")["href"] == "report.css"
    assert (tmp_path / "report.css").is_file()
    assert soup.find("script") is None


def test_material_text_cannot_inject_html_or_markdown(results):
    r = results["SYN-S04"].model_copy(deep=True)
    payload = '<script>alert(1)</script><img src="https://evil/x" onerror="alert(2)">[恶意](javascript:alert(3))'
    r.evidence[0].text = payload
    html = render(r)
    soup = BeautifulSoup(html, "html.parser")
    assert soup.find("script") is None and soup.find("img") is None
    assert payload in soup.get_text()
    md = render(r, format="md")
    assert "<script>" not in md and "[恶意](javascript:" not in md
    assert "\\[恶意\\]" in md


def test_real_output_cannot_enter_source_repository(results, tmp_path):
    r = results["SYN-S04"].model_copy(update={"data_class": DataClass.REAL})
    with pytest.raises(ValueError, match="仓库外"):
        write_reports(r, BUNDLES.parents[1] / "var/real-output")
    write_reports(r, tmp_path)
    assert (tmp_path / "analysis.json").is_file()


def test_cli_batch_and_replay_roundtrip(tmp_path, capsys):
    first, second = tmp_path / "first", tmp_path / "second"
    assert main(["analyze", str(BUNDLES), "--out", str(first), "--save-replay"]) == 0
    assert len(list(first.glob("*/analysis.json"))) == 15
    assert (
        main(
            [
                "analyze",
                str(BUNDLES),
                "--out",
                str(second),
                "--provider",
                "replay",
                "--replay",
                str(first),
            ]
        )
        == 0
    )
    for p in first.glob("*/analysis.json"):
        a = json.loads(p.read_text())
        b = json.loads((second / p.parent.name / "analysis.json").read_text())
        assert a["elements"] == b["elements"] and a["evidence"] == b["evidence"]


def test_cli_rejects_corrupt_replay_without_creating_report(tmp_path, capsys):
    source = tmp_path / "source"
    output = tmp_path / "out"
    assert (
        main(
            ["analyze", str(BUNDLES / "SYN-S09"), "--out", str(source), "--save-replay"]
        )
        == 0
    )
    p = source / "SYN-S09/replay.json"
    data = json.loads(p.read_text())
    data["extraction"]["elements"]["end_time"]["evidence_refs"] = ["M99/missing"]
    p.write_text(json.dumps(data))
    assert (
        main(
            [
                "analyze",
                str(BUNDLES / "SYN-S09"),
                "--out",
                str(output),
                "--provider",
                "replay",
                "--replay",
                str(p),
            ]
        )
        == 1
    )
    assert not (output / "SYN-S09/report.html").exists()
    failure = json.loads((output / "SYN-S09/analysis-rejected.json").read_text())
    assert (
        failure["status"] == "rejected"
        and failure["issues"][0]["code"] == "EVIDENCE_REF_MISSING"
    )
    assert "EVIDENCE_REF_MISSING" in capsys.readouterr().err


def test_missing_attachment_refuses_import_and_batch_continues(tmp_path, capsys):
    from shutil import copytree

    root = tmp_path / "inputs"
    copytree(BUNDLES / "SYN-S01", root / "SYN-S01")
    bad = copytree(BUNDLES / "SYN-P04", root / "SYN-P04")
    (bad / "attachments/M03-repair-report.pdf").unlink()
    output = tmp_path / "out"
    assert main(["analyze", str(root), "--out", str(output)]) == 1
    assert (output / "SYN-S01/analysis.json").is_file()
    assert not (output / "SYN-P04/report.html").exists()
    assert "材料文件不存在" in capsys.readouterr().err


def test_cli_requires_replay_and_valid_input(tmp_path):
    assert main(["analyze", "--provider", "replay"]) == 2
    assert main(["analyze", str(tmp_path)]) == 1


def test_cli_cannot_write_generated_files_into_input_bundle(tmp_path):
    from shutil import copytree

    source = copytree(BUNDLES / "SYN-S01", tmp_path / "SYN-S01")
    before = {
        p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()
    }
    assert main(["analyze", str(source), "--out", str(tmp_path)]) == 2
    after = {
        p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()
    }
    assert before == after
