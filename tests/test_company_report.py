"""公司格式故障报告（ADR 0007）。只用合成包；真实样例只在本机用 scripts/check_company_report.py 对照。"""

import json
import zipfile
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from docx import Document
from docx.enum.text import WD_COLOR_INDEX
from docx.oxml.ns import qn
from PIL import Image

from noc7.batch import _index
from noc7.extract import analyze
from noc7.report import write_reports
from noc7.report.company import (
    DEFAULT_IMPROVEMENT,
    LAYOUT,
    PENDING,
    ReportProfile,
    build_company_report,
    company_time,
    load_report_profile,
    render_company_html,
    write_company_docx,
)
from noc7.schema import DataClass, TimeValue

BUNDLES = Path(__file__).resolve().parents[1] / "fixtures/bundles"
REPO = BUNDLES.parents[1]


@pytest.fixture(scope="module")
def results():
    return {name: analyze(BUNDLES / name) for name in ("SYN-P04", "SYN-S05", "SYN-S09", "SYN-S10")}


def text(report, key):
    return "\n".join("".join(p.text for p in line) for line in report.cells[key])


def expected_grid():
    owner = {}
    for i, (r, c, rs, cs, _) in enumerate(LAYOUT):
        for rr in range(r, r + rs):
            for cc in range(c, c + cs):
                owner[(rr, cc)] = i
    return [[owner[(r, c)] for c in range(4)] for r in range(11)]


def read_grid(table):
    seen, alive, grid = {}, [], []
    for r in range(len(table.rows)):
        line = []
        for c in range(len(table.columns)):
            tc = table.cell(r, c)._tc
            alive.append(tc)
            line.append(seen.setdefault(id(tc), len(seen)))
        grid.append(line)
    return grid


def normalize(grid):
    order = {}
    return [[order.setdefault(x, len(order)) for x in row] for row in grid]


def test_docx_layout_matches_company_template(results, tmp_path):
    path = tmp_path / "r.docx"
    write_company_docx(results["SYN-P04"], path)
    doc = Document(str(path))
    assert len(doc.tables) == 1
    table = doc.tables[0]
    assert (len(table.rows), len(table.columns)) == (11, 4)
    assert normalize(read_grid(table)) == normalize(expected_grid())
    for r, c, _, _, spec in LAYOUT:
        if isinstance(spec, tuple):
            assert table.cell(r, c).text == "\n".join(spec)
    paragraphs = [p.text for p in doc.paragraphs if p.text]
    assert paragraphs[0] == "故障处理报告 Failure Report"
    assert paragraphs[1].startswith("合成演示数据")
    assert paragraphs[-3:] == [
        "故障处理报告人(Failure Reporter)：",
        "故障处理报告审核(Failure Report Audit): ",
        "审核日期(Audit Date)：",
    ]
    section = doc.sections[0]
    assert (section.page_width, section.page_height) == (7560310, 10692130)
    margins = [getattr(section, f"{s}_margin").twips for s in ("left", "right", "top", "bottom")]
    assert margins == [1440, 1800, 1440, 1440]
    assert not section.header.paragraphs[0].text.strip()
    assert "PAGE" in section.footer._element.xml


def test_table_width_is_fixed_even_with_long_unbroken_text(results, tmp_path):
    # 处理过程里无空格的长串不能让 Word 自动撑开列宽。
    r = results["SYN-P04"].model_copy(deep=True)
    r.elements.handling_process.value[0].action = "A" * 300
    path = tmp_path / "r.docx"
    write_company_docx(r, path)
    table = Document(str(path)).tables[0]
    tbl_pr = table._tbl.tblPr
    width = tbl_pr.find(qn("w:tblW"))
    assert (width.get(qn("w:w")), width.get(qn("w:type"))) == ("9753", "dxa")
    assert tbl_pr.find(qn("w:tblLayout")).get(qn("w:type")) == "fixed"
    assert not table.autofit
    grid = [int(c.get(qn("w:w"))) for c in table._tbl.tblGrid.findall(qn("w:gridCol"))]
    assert grid == [1444, 1620, 1620, 5069]
    # schema 顺序：tblBorders 在 tblLayout 之前，tblLook 最后。
    tags = [c.tag.split("}")[1] for c in tbl_pr]
    assert tags.index("tblBorders") < tags.index("tblLayout") < tags.index("tblLook")


def test_cells_follow_mapping_rules(results):
    report = build_company_report(results["SYN-P04"])
    assert text(report, "customer") == "示例客户壬（合成）"
    assert text(report, "circuit_id") == "SYN-CKT-1024"
    assert text(report, "ticket_no") == "SYN-P04"
    assert text(report, "service") == "业务中断"
    assert text(report, "declared") == "2026-10-10 15:42:00 (GMT+8)"
    assert text(report, "resumed") == "2026-10-10 19:08:00 (GMT+8)"
    assert text(report, "duration") == "206分钟"
    process = text(report, "process").splitlines()
    assert process[0] == "2026-10-10 15:50:08 GMT+8 系统 客户来电报障建单。"
    assert len(process) == len(results["SYN-P04"].elements.handling_process.value)
    analysis = text(report, "analysis").splitlines()
    assert analysis[0].startswith("现场确认：")
    assert analysis[-1].startswith("责任方：责任认定：") and analysis[-1].endswith("故障位置：【待核实：有冲突】")
    assert text(report, "improvement") == DEFAULT_IMPROVEMENT + "【系统默认表述，待审核】"
    assert report.report_date.endswith("日") and report.synthetic


def test_unknown_conflicted_and_unconfirmed_cells_are_marked(results):
    s10 = build_company_report(results["SYN-S10"])
    assert text(s10, "declared") == "【待核实：时间有冲突】"
    assert text(s10, "duration") == PENDING
    assert text(s10, "analysis") == f"{PENDING}\n责任方：{PENDING}；故障位置：{PENDING}"
    s05 = build_company_report(results["SYN-S05"])
    assert text(s05, "resumed") == PENDING and text(s05, "duration") == PENDING
    # 起止都有记载但恢复未确认：给出字段差，并标明不是最终历时。
    s09 = build_company_report(results["SYN-S09"])
    assert text(s09, "duration") == "约 36 分钟【待核实：恢复未确认】"
    assert s09.cells["duration"][0][1].pending


def test_pending_parts_are_highlighted_in_word(results, tmp_path):
    path = tmp_path / "r.docx"
    write_company_docx(results["SYN-S10"], path)
    runs = [run for p in Document(str(path)).tables[0].cell(9, 1).paragraphs for run in p.runs]
    marked = {run.text for run in runs if run.font.highlight_color == WD_COLOR_INDEX.YELLOW}
    assert marked == {PENDING}
    assert all(run.font.highlight_color is None for run in runs if run.text.startswith("责任方"))


def test_duplicates_skipped_and_circuit_renumbering_shown(results):
    r = results["SYN-P04"].model_copy(deep=True)
    steps = r.elements.handling_process.value
    steps[1].duplicate_of = steps[0].id
    span = next(s for s in r.evidence if s.id == "M01/f:circuit_id")
    r.evidence.append(span.model_copy(update={"id": "M01/f:circuit_id_new", "text": "SYN-CKT-2024"}))
    report = build_company_report(r)
    assert len(text(report, "process").splitlines()) == len(steps) - 1
    assert text(report, "circuit_id") == "新：SYN-CKT-2024；原：SYN-CKT-1024"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (TimeValue(raw="x", iso="2026-07-13T04:36:22+08:00", tz_source="explicit", utc_offset="+08:00", precision="second"), "2026-07-13 04:36:22 (GMT+8)"),
        (TimeValue(raw="x", iso="2026-07-13T04:36:00+05:30", tz_source="explicit", utc_offset="+05:30", precision="minute"), "2026-07-13 04:36 (GMT+5:30)"),
        (TimeValue(raw="07-13 04:36", iso="2026-07-13T04:36:00", tz_source="unknown", precision="minute"), "07-13 04:36（时区未知）"),
        (TimeValue(raw="{{end_time}}", placeholder=True), "{{end_time}}【待核实：时间无法解析】"),
    ],
)
def test_company_time_format(value, expected):
    assert "".join(p.text for p in company_time(value)) == expected


def test_html_preview_escapes_material_text(results):
    r = results["SYN-P04"].model_copy(deep=True)
    payload = '<script>alert(1)</script><img src=x onerror="alert(2)">'
    next(s for s in r.evidence if s.id == "M01/f:customer").text = payload
    soup = BeautifulSoup(render_company_html(r), "html.parser")
    assert soup.find("script") is None and soup.find("img") is None
    assert payload in soup.get_text()
    assert [len(tr.find_all(["th", "td"])) for tr in soup.select("table tr")][:5] == [3, 2, 2, 2, 3]
    assert soup.find("th", rowspan="7") is not None and soup.find("mark") is not None


def test_header_profile_is_loaded_from_outside_repository(results, tmp_path):
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    Image.new("RGB", (40, 20), "red").save(profile_dir / "logo.png")
    (profile_dir / "profile.json").write_text(
        json.dumps({"company_name": "示例公司（合成）", "logo": "logo.png"}), encoding="utf-8"
    )
    profile = load_report_profile(profile_dir)
    assert profile == ReportProfile("示例公司（合成）", profile_dir / "logo.png")
    write_reports(results["SYN-P04"], tmp_path / "out", profile=profile)
    header = Document(str(tmp_path / "out/company_report.docx")).sections[0].header
    assert "示例公司（合成）" in header.paragraphs[0].text
    assert "a:blip" in header._element.xml
    assert "示例公司（合成）" in (tmp_path / "out/company_report.html").read_text()
    (profile_dir / "logo.png").unlink()
    with pytest.raises(ValueError, match="logo 不存在"):
        load_report_profile(profile_dir)
    assert load_report_profile(tmp_path / "missing") == ReportProfile()


def test_write_reports_outputs_are_stable_and_gated(results, tmp_path):
    for name in ("a", "b"):
        write_reports(results["SYN-P04"], tmp_path / name)
    parts = ("word/document.xml", "word/header1.xml", "word/footer1.xml", "docProps/core.xml")

    def read(name):
        with zipfile.ZipFile(tmp_path / name / "company_report.docx") as z:
            return {p: z.read(p) for p in parts if p in z.namelist()}

    assert read("a") == read("b") and "word/document.xml" in read("a")
    assert (tmp_path / "a/company_report.html").read_text() == (tmp_path / "b/company_report.html").read_text()
    real = results["SYN-P04"].model_copy(update={"data_class": DataClass.REAL})
    with pytest.raises(ValueError, match="仓库外"):
        write_reports(real, REPO / "var/real-company-output")
    assert not (REPO / "var/real-company-output").exists()


def test_batch_index_links_company_outputs():
    page = _index([{"alias": "R01", "ticket_ref": "SYN-P04", "status": "ok"}])
    assert 'href="R01/company_report.docx"' in page and 'href="R01/company_report.html"' in page
