"""公司格式故障报告（对齐公司「故障处理报告 Failure Report」模板，见 ADR 0007）。

只消费校验后的 AnalysisResult，不调用模型。证据、候选和待核实清单仍在审核报告
（report.md / report.html）里；这里把结论填进公司模板，拿不准的格子标【待核实】。
页眉的公司名和 logo 出自真实样例，只从仓库外的本机配置读取。
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Emu, Pt, Twips
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..schema import (
    AnalysisResult,
    DataClass,
    ElementStatus,
    MaterialKind,
    StepKind,
    TimePrecision,
    TimeValue,
)

COMPANY_TEMPLATE_VERSION = "1.1"
ROOT = Path(__file__).parent
TITLE = "故障处理报告 Failure Report"
PENDING = "【待核实】"
DEFAULT_IMPROVEMENT = (
    "国际公司将持续关注线路运行情况，监控线路运行情况，发现隐患尽早处理，快速响应处置故障。"
)
IMPROVEMENT_NOTE = "【系统默认表述，待审核】"
SYNTHETIC_NOTICE = "合成演示数据，不代表真实工单或真实模型质量。"
SIGNATURES = (
    "故障处理报告人(Failure Reporter)：",
    "故障处理报告审核(Failure Report Audit): ",
    "审核日期(Audit Date)：",
)
# 报告日期按公司模板口径（GMT+8）。
REPORT_TZ = timezone(timedelta(hours=8))
PROFILE_ENV = "NOC7_REPORT_PROFILE"
DEFAULT_PROFILE_DIR = Path("~/.noc7/report_profile")

# 版式：(行, 列, 跨行, 跨列, 标签段落 或 取值键)。与样例 A05 的 11×4 表格逐格对应。
LAYOUT: tuple[tuple[int, int, int, int, tuple[str, ...] | str], ...] = (
    (0, 0, 7, 1, ("故障基本情况", "The basic situation of failure")),
    (0, 1, 1, 1, ("客户名称Customer",)),
    (0, 2, 1, 2, "customer"),
    (1, 1, 1, 1, ("电路编号", "Circuit ID.")),
    (1, 2, 1, 2, "circuit_id"),
    (2, 1, 1, 1, ("故障号: ", "Fault Ticket no.")),
    (2, 2, 1, 2, "ticket_no"),
    (3, 1, 1, 1, ("业务类型 Service",)),
    (3, 2, 1, 2, "service"),
    (4, 1, 3, 1, ("故障时间 Downtime",)),
    (4, 2, 1, 1, ("申报时间", "Time to declare")),
    (4, 3, 1, 1, "declared"),
    (5, 2, 1, 1, ("恢复时间", "Resumed time")),
    (5, 3, 1, 1, "resumed"),
    (6, 2, 1, 1, ("故障历时", "Fault duration")),
    (6, 3, 1, 1, "duration"),
    (7, 0, 1, 1, ("故障现象", "Failure")),
    (7, 1, 1, 3, "phenomenon"),
    (8, 0, 1, 1, ("处理过程", "Process")),
    (8, 1, 1, 3, "process"),
    (9, 0, 1, 1, ("故障原因", "分析", "Failure Analysis")),
    (9, 1, 1, 3, "analysis"),
    (10, 0, 1, 1, ("改进及预防措施", "Improvement and preventive measures")),
    (10, 1, 1, 3, "improvement"),
)
ROWS, COLS = 11, 4
COLUMN_TWIPS = (1444, 1620, 1620, 5069)
TABLE_TWIPS = sum(COLUMN_TWIPS)  # 9753，与样例 tblW 一致
# 样例 pgMar：左/上/下 1440、右 1800 twip。
MARGIN_TWIPS = {"left_margin": 1440, "right_margin": 1800, "top_margin": 1440, "bottom_margin": 1440}


@dataclass(frozen=True)
class Part:
    text: str
    pending: bool = False


Line = tuple[Part, ...]
PENDING_LINE: Line = (Part(PENDING, True),)


@dataclass(frozen=True)
class GridCell:
    row: int
    col: int
    rowspan: int
    colspan: int
    lines: tuple[Line, ...]
    label: bool


@dataclass(frozen=True)
class CompanyReport:
    ticket_ref: str
    report_date: str
    generated: datetime | None
    synthetic: bool
    cells: dict[str, tuple[Line, ...]]

    def grid(self) -> list[GridCell]:
        return [
            GridCell(
                r, c, rs, cs,
                tuple((Part(t),) for t in spec) if isinstance(spec, tuple) else self.cells[spec],
                isinstance(spec, tuple),
            )
            for r, c, rs, cs, spec in LAYOUT
        ]


@dataclass(frozen=True)
class ReportProfile:
    """页眉配置。公司名和 logo 属于真实样例内容，放仓库外，未配置时页眉留空。"""

    company_name: str | None = None
    logo: Path | None = None


def load_report_profile(directory: Path | None = None) -> ReportProfile:
    base = Path(directory or os.environ.get(PROFILE_ENV) or DEFAULT_PROFILE_DIR).expanduser()
    path = base / "profile.json"
    if not path.is_file():
        return ReportProfile()
    data = json.loads(path.read_text(encoding="utf-8"))
    logo = data.get("logo")
    logo_path = (base / logo) if logo else None
    if logo_path is not None and not logo_path.is_file():
        raise ValueError(f"页眉配置 {path} 指定的 logo 不存在。")
    return ReportProfile(company_name=data.get("company_name") or None, logo=logo_path)


def gmt_label(dt: datetime) -> str:
    offset = dt.utcoffset() or timedelta(0)
    sign = "-" if offset < timedelta(0) else "+"
    hours, rest = divmod(abs(int(offset.total_seconds())) // 60, 60)
    return f"GMT{sign}{hours}" + (f":{rest:02d}" if rest else "")


def company_time(value: TimeValue, *, paren: bool = True) -> Line:
    """2026-07-13 04:36:22 (GMT+8)；处理过程里不带括号。"""
    if value.iso is None:
        return (Part(value.raw), Part("【待核实：时间无法解析】", True))
    if value.precision is TimePrecision.DAY:
        return (Part(value.iso), Part("【待核实：只精确到日】", True))
    dt = datetime.fromisoformat(value.iso)
    if dt.utcoffset() is None:
        return (Part(value.raw), Part("（时区未知）", True))
    seconds = value.precision in (None, TimePrecision.SECOND)
    text = dt.strftime("%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M")
    zone = gmt_label(dt)
    return (Part(f"{text} ({zone})" if paren else f"{text} {zone}"),)


def _ticket_fields(result: AnalysisResult) -> dict[str, str]:
    """工单字段原文：取 ticket_fields 材料的 f:<key> 片段，不写死材料编号。"""
    mids = {m.id for m in result.materials if m.kind == MaterialKind.TICKET_FIELDS}
    fields: dict[str, str] = {}
    for span in result.evidence:
        local = span.id.partition("/")[2]
        if span.material_id in mids and local.startswith("f:") and span.text.strip():
            fields.setdefault(local[2:], span.text.strip())
    return fields


def _text_lines(text: str | None) -> tuple[Line, ...]:
    lines = tuple((Part(s.strip()),) for s in (text or "").splitlines() if s.strip())
    return lines or (PENDING_LINE,)


def _value_parts(el) -> Line:
    if el.status == ElementStatus.CONFLICTED:
        return (Part("【待核实：有冲突】", True),)
    if not el.value:
        return PENDING_LINE
    return (Part(" ".join(str(el.value).split())),)


def _element_lines(el) -> tuple[Line, ...]:
    if el.status == ElementStatus.CONFLICTED:
        return (_value_parts(el),)
    return _text_lines(el.value)


def _time_lines(el, *, semantic=False) -> tuple[Line, ...]:
    if el.status == ElementStatus.CONFLICTED:
        return ((Part("【待核实：时间有冲突】", True),),)
    if not el.value:
        return (PENDING_LINE,)
    line = company_time(el.value)
    if semantic:
        from ..providers.semantic_constraints import TIME_LABELS
        c = next((c for c in el.candidates if c.id == el.selected), None)
        if c:
            label = TIME_LABELS.get(c.time_kind, str(c.time_kind))
            line = (Part(label + "："), *line)
            if el.value.tz_source == "assumed":
                line = (*line, Part("【时区按系统口径假设】", True))
    return (line,)


def _duration_lines(result: AnalysisResult) -> tuple[Line, ...]:
    from . import final_duration, duration_basis

    if not duration_basis(result):
        return (PENDING_LINE,)

    minutes = final_duration(result)
    if minutes is not None:
        return ((Part(f"{math.floor(minutes + 0.5)}分钟"),),)
    start, end = result.elements.start_time, result.elements.end_time
    cancelled = any(i.code == "TICKET_CANCELLED" for i in result.issues)
    if not cancelled and end.status != ElementStatus.CONFIRMED and start.value and end.value:
        a, b = start.value.as_datetime(), end.value.as_datetime()
        if a and b and a.utcoffset() is not None and b.utcoffset() is not None and b >= a:
            approx = math.floor((b - a).total_seconds() / 60 + 0.5)
            return ((Part(f"约 {approx} 分钟"), Part("【待核实：恢复未确认】", True)),)
    return (PENDING_LINE,)


def _process_lines(result: AnalysisResult) -> tuple[Line, ...]:
    lines = []
    for step in result.elements.handling_process.value:
        if step.duplicate_of:
            continue
        when = company_time(step.time, paren=False) if step.time else (Part("（时间未知）"),)
        text = step.action.strip()
        if step.result:
            text = f"{text.rstrip('。；;，, ')}，{step.result.strip().rstrip('。')}。"
        if step.step_kind == StepKind.PLANNED:
            text = f"（计划）{text}"
        actor = f"{step.actor} " if step.actor else ""
        lines.append((*when, Part(f" {actor}{' '.join(text.split())}")))
    return tuple(lines) or (PENDING_LINE,)


def _report_date(generated: datetime | None, raw: str) -> str:
    if generated is None:
        return raw
    local = generated.astimezone(REPORT_TZ) if generated.utcoffset() is not None else generated
    return f"{local.year}年 {local.month} 月 {local.day} 日"


def build_company_report(result: AnalysisResult) -> CompanyReport:
    e = result.elements
    fields = _ticket_fields(result)
    circuit = [v for v in (fields.get("circuit_id_new"), fields.get("circuit_id")) if v]
    if len(set(circuit)) == 2:
        circuit_line: Line = (Part(f"新：{circuit[0]}；原：{circuit[1]}"),)
    else:
        circuit_line = (Part(circuit[0]),) if circuit else PENDING_LINE
    service = fields.get("business_type") or fields.get("fault_type")
    raw = result.run.finished_at or result.run.started_at
    try:
        generated = datetime.fromisoformat(raw)
    except ValueError:
        generated = None
    cause_lines = _element_lines(e.cause)
    if result.semantic_assessment and e.cause.value:
        c = next(c for c in e.cause.candidates if c.id == e.cause.selected)
        cause_lines = ((Part(f"{c.relation.speaker}记载："), *cause_lines[0],
                        Part("【有记录，未经人工审核】", True)), *cause_lines[1:])
    def business_parts(el):
        parts = _value_parts(el)
        chosen = next((c for c in el.candidates if c.id == el.selected), None)
        if el.value and chosen and chosen.relation and not el.review:
            parts = (*parts, Part("【" + (el.note or "有记录，未经人工审核") + "】", True))
        return parts

    analysis = (
        *cause_lines,
        (Part("责任方："), *business_parts(e.responsible_party),
         Part("；故障位置："), *business_parts(e.location)),
    )
    cells = {
        "customer": _text_lines(fields.get("customer")),
        "circuit_id": (circuit_line,),
        "ticket_no": ((Part(fields.get("ticket_no") or result.ticket_ref),),),
        "service": _text_lines(service),
        "declared": _time_lines(e.start_time, semantic=result.semantic_assessment is not None),
        "resumed": _time_lines(e.end_time, semantic=result.semantic_assessment is not None),
        "duration": _duration_lines(result),
        "phenomenon": _element_lines(e.phenomenon),
        "process": _process_lines(result),
        "analysis": analysis,
        "improvement": ((Part(DEFAULT_IMPROVEMENT), Part(IMPROVEMENT_NOTE, True)),),
    }
    return CompanyReport(
        ticket_ref=result.ticket_ref,
        report_date=_report_date(generated, raw),
        generated=generated,
        synthetic=result.data_class == DataClass.SYNTHETIC,
        cells=cells,
    )


def render_company_html(result: AnalysisResult, profile: ReportProfile | None = None) -> str:
    report = build_company_report(result)
    rows: list[list[GridCell]] = [[] for _ in range(ROWS)]
    for cell in report.grid():
        rows[cell.row].append(cell)
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        undefined=StrictUndefined,
        autoescape=True,
    )
    return env.get_template("company_report.html.j2").render(
        report=report,
        rows=rows,
        title=TITLE,
        signatures=SIGNATURES,
        synthetic_notice=SYNTHETIC_NOTICE,
        company_name=(profile or ReportProfile()).company_name,
        template_version=COMPANY_TEMPLATE_VERSION,
    )


# ---------------------------------------------------------------------------
# Word
# ---------------------------------------------------------------------------
def _font(run, size: Pt | None = None, east_asia: str = "宋体", highlight: bool = False) -> None:
    run.font.name = "Times New Roman"
    if size is not None:
        run.font.size = size
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), east_asia)
    if highlight:
        run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def _write_lines(paragraphs, lines: tuple[Line, ...], size: Pt) -> None:
    for paragraph, line in zip(paragraphs, lines):
        for part in line:
            _font(paragraph.add_run(part.text), size, highlight=part.pending)


def _fill_cell(cell, grid: GridCell) -> None:
    # 合并后可能留下多个空段落，统一清成一个再写。
    for extra in cell.paragraphs[1:]:
        extra._element.getparent().remove(extra._element)
    paragraphs = [cell.paragraphs[0]] + [cell.add_paragraph() for _ in grid.lines[1:]]
    for p in paragraphs:
        p.paragraph_format.space_after = Pt(0)
        if grid.label and grid.col == 0:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    _write_lines(paragraphs, grid.lines, Pt(10))


def _borders(table) -> None:
    """显式写边框：部分阅读器不渲染表格样式里的边框。按 schema 顺序插在 tblLook 之前。"""
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        for key, value in (("val", "single"), ("sz", "4"), ("space", "0"), ("color", "000000")):
            el.set(qn(f"w:{key}"), value)
        borders.append(el)
    tbl_pr = table._tbl.tblPr
    later = [c for c in tbl_pr if c.tag in {qn("w:shd"), qn("w:tblLayout"), qn("w:tblCellMar"), qn("w:tblLook")}]
    if later:
        later[0].addprevious(borders)
    else:
        tbl_pr.append(borders)


def _page_field(paragraph) -> None:
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "1"
    run.append(text)
    field.append(run)
    paragraph._p.append(field)


def write_company_docx(
    result: AnalysisResult, path: Path, profile: ReportProfile | None = None
) -> None:
    report = build_company_report(result)
    profile = profile or ReportProfile()
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Emu(7560310), Emu(10692130)  # A4
    for side, twips in MARGIN_TWIPS.items():
        setattr(section, side, Twips(twips))
    section.header_distance, section.footer_distance = Emu(540385), Emu(629920)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = "Times New Roman", Pt(10)
    normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
    normal.paragraph_format.space_before = normal.paragraph_format.space_after = Pt(0)

    header = section.header.paragraphs[0]
    if profile.logo is not None:
        header.add_run().add_picture(str(profile.logo), height=Cm(1.2))
    if profile.company_name:
        _font(header.add_run(f"    {profile.company_name}"), Pt(10))
    footer = section.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _page_field(footer)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _font(title.add_run(TITLE), Pt(18), east_asia="方正小标宋简体")
    if report.synthetic:
        notice = doc.add_paragraph()
        notice.alignment = WD_ALIGN_PARAGRAPH.CENTER
        _font(notice.add_run(SYNTHETIC_NOTICE), Pt(9), highlight=True)
    date = doc.add_paragraph()
    date.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _font(date.add_run(report.report_date), Pt(10))

    table = doc.add_table(rows=ROWS, cols=COLS)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    _borders(table)
    # 固定布局 + 显式表宽：否则 Word 按内容自动调整列宽，长串会撑破 11×4 版式。
    table.autofit = False
    tbl_w = table._tbl.tblPr.find(qn("w:tblW"))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_w.set(qn("w:w"), str(TABLE_TWIPS))
    for i, width in enumerate(COLUMN_TWIPS):
        table.columns[i].width = Twips(width)
        for cell in table.columns[i].cells:
            cell.width = Twips(width)
    for grid in report.grid():
        cell = table.cell(grid.row, grid.col)
        if grid.rowspan > 1 or grid.colspan > 1:
            cell = cell.merge(table.cell(grid.row + grid.rowspan - 1, grid.col + grid.colspan - 1))
        _fill_cell(cell, grid)

    for label in SIGNATURES:
        _font(doc.add_paragraph().add_run(label), Pt(9))

    props = doc.core_properties
    props.title, props.author, props.last_modified_by = "故障处理报告", "noc7", "noc7"
    props.revision = 1
    if report.generated is not None:
        props.created = props.modified = report.generated.astimezone(timezone.utc).replace(tzinfo=None)
    doc.save(str(path))


__all__ = [
    "COMPANY_TEMPLATE_VERSION",
    "DEFAULT_IMPROVEMENT",
    "LAYOUT",
    "PENDING",
    "CompanyReport",
    "ReportProfile",
    "build_company_report",
    "company_time",
    "load_report_profile",
    "render_company_html",
    "write_company_docx",
]
