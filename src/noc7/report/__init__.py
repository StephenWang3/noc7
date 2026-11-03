"""模板只消费校验后的 AnalysisResult；不再调用模型，不执行来源 HTML。"""

from __future__ import annotations

import html
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from ..schema import (
    ATTRIBUTION_LABELS_ZH,
    ELEMENT_LABELS_ZH,
    AnalysisResult,
    ElementStatus,
    TimeValue,
)
from .company import (
    ReportProfile,
    load_report_profile,
    render_company_html,
    write_company_docx,
)

TEMPLATE_VERSION = "1.1"
ROOT = Path(__file__).parent
STATUS = {
    "documented": "原文记载",
    "confirmed": "有确认依据",
    "unknown": "未知",
    "conflicted": "有冲突",
}
ROLE = {
    "original": "原文",
    "quoted": "邮件引用（不独立计数）",
    "signature": "签名/免责声明",
    "derived_summary": "衍生摘要（不独立计数）",
    "ocr_text": "OCR 文字",
    "visual_observation": "视觉读数",
}
PARSE = {
    "pending": "待解析",
    "parsed": "已解析",
    "needs_review": "待复核",
    "failed": "失败",
    "unsupported": "不支持/待实现",
}
STEP = {
    "technical_action": "排障动作",
    "check_result": "检查结果",
    "communication": "沟通",
    "workflow": "流程",
    "planned": "计划（未执行）",
}


def time_text(value: TimeValue | None) -> str:
    if value is None:
        return "未知"
    tz = {
        "explicit": "原文明确时区",
        "assumed": "时区按系统口径假设",
        "unknown": "时区未知",
    }[value.tz_source]
    return f"{value.raw}（归一：{value.iso or '未解析'}；{tz}）"


def md(value) -> str:
    """转义 HTML 与 Markdown 语法，材料不能注入链接、图片或表格。"""
    text = html.escape(str(value), quote=True)
    text = re.sub(r"([\\`*_{\}\[\]()#!|>+.!-])", r"\\\1", text)
    return text.replace("\r", "").replace("\n", "<br>")


def _value(el):
    if el.value is None or el.value == []:
        return "未知；见候选和未决事项。"
    if isinstance(el.value, TimeValue):
        return time_text(el.value)
    if isinstance(el.value, list):
        return f"{len(el.value)} 条处理记录，见时间线。"
    return el.value


def _relation_text(r):
    if r is None:
        return None
    certainty = {"asserted": "明确陈述", "suspected": "推测", "negated": "否定", "unknown": "未明"}[r.modality]
    text = f"事件：{r.event_id}；范围：{r.scope}；{certainty}；{'本次事件' if r.current_event else '非本次事件'}。"
    if hasattr(r, "assertion"):
        assertion = {"fault": "故障", "mechanism": "机制", "planned_work": "作业", "phenomenon": "现象", "finding": "排查", "recovery": "恢复方式", "unknown": "未明"}[r.assertion]
        text += f"{r.speaker}陈述的{assertion}；{'影响本次业务' if r.affects_service else '未说明业务影响'}；{'已发生' if r.occurred else '未证明已发生'}。"
        if r.contradicts:
            text += "相矛盾候选：" + "、".join(r.contradicts) + "。"
    if hasattr(r, "source_tier"):
        from ..providers.responsibility_location import SOURCE_LABELS, PATH_LABELS
        text += f"来源：{SOURCE_LABELS[r.source_tier]}；陈述方：{r.speaker or '未署名'}；原文断言：{r.statement}。"
        if hasattr(r, "category"):
            text += f"责任分类：{r.category}；路径：{PATH_LABELS[r.decision_path]}；采购归属：{r.procurement}。"
        else:
            text += f"城市：{r.city or '未明确'}；{'已定位' if r.located else '未定位'}。"
        if r.contradicts:
            text += "相矛盾候选：" + "、".join(r.contradicts) + "。"
        from ..providers.responsibility_location import ANCHORS
        for key in ANCHORS:
            q = getattr(r, key, None)
            if q:
                text += f"{key} {q.evidence_id}：{q.quote}；"
    for q in r.context:
        text += f"依据 {q.evidence_id}：{q.quote}；"
    for key, label in (("date_anchor", "日期锚点"), ("timezone_anchor", "时区锚点"), ("customer_confirmation", "客户确认依据")):
        q = getattr(r, key, None)
        if q:
            text += f"{label} {q.evidence_id}：{q.quote}；"
    return text


def _candidate(c):
    kind = next(
        (
            getattr(c, k)
            for k in ("time_kind", "cause_kind", "basis", "role", "step_kind")
            if hasattr(c, k)
        ),
        c.attribution,
    )
    text = next(
        (
            getattr(c, k)
            for k in ("statement", "party", "description", "action")
            if hasattr(c, k)
        ),
        None,
    )
    if hasattr(c, "time") and hasattr(c, "time_kind"):
        text = time_text(c.time)
    return {
        "id": c.id,
        "kind": str(kind),
        "text": text or "",
        "source": ATTRIBUTION_LABELS_ZH[c.attribution],
        "refs": c.evidence_refs,
        "note": c.note,
        "relation": _relation_text(getattr(c, "relation", None)),
    }


def duration_basis(result: AnalysisResult) -> bool:
    if result.semantic_assessment is None:
        return True
    start, end = result.elements.start_time, result.elements.end_time
    a = next((c for c in start.candidates if c.id == start.selected), None)
    b = next((c for c in end.candidates if c.id == end.selected), None)
    return bool(a and b and a.relation and b.relation and a.time_kind != "alarm_raised"
                and (a.relation.event_id, a.relation.scope) == (b.relation.event_id, b.relation.scope)
                and a.time.utc_offset is not None and b.time.utc_offset is not None)


def final_duration(result: AnalysisResult) -> float | None:
    if any(i.code == "TICKET_CANCELLED" for i in result.issues):
        return None
    start, end = result.elements.start_time, result.elements.end_time
    if not duration_basis(result) or end.status != ElementStatus.CONFIRMED or not start.value or not end.value:
        return None
    a, b = start.value.as_datetime(), end.value.as_datetime()
    if not a or not b or (a.utcoffset() is None) != (b.utcoffset() is None):
        return None
    minutes = (b - a).total_seconds() / 60
    return minutes if minutes >= 0 else None


def render(
    result: AnalysisResult, *, format: str = "html", report_type: str = "stage"
) -> str:
    if format not in {"html", "md"} or report_type not in {"stage", "closure"}:
        raise ValueError("报告格式必须为 html/md，类型必须为 stage/closure。")
    # model_copy 不触发验证；导出前重新校验，拒绝被内存修改破坏的结果。
    result = AnalysisResult.model_validate(result.model_dump(mode="json"))
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        undefined=StrictUndefined,
        autoescape=(format == "html"),
    )
    env.filters["md"] = md
    env.filters["time_text"] = time_text
    env.filters["status"] = lambda v: STATUS[v]
    env.filters["role"] = lambda v: ROLE[v]
    env.filters["parse"] = lambda v: PARSE[v]
    env.filters["step"] = lambda v: STEP[v]
    env.filters["constraint_status"] = lambda v: {"eligible": "可采用候选", "pending": "待核实", "conflict": "有冲突", "downgraded": "降低确认等级"}[v]
    env.filters["quote_status"] = lambda v: {"strict": "严格匹配", "whitespace": "仅空白等价匹配", "mismatch": "待核对：引文不匹配"}[v]
    env.filters["model_source"] = lambda v: ATTRIBUTION_LABELS_ZH.get(v, v or "未提供") if isinstance(v, str) else str(v or "未提供")
    env.filters["source"] = lambda v: ATTRIBUTION_LABELS_ZH[v]
    rows = [
        {
            "name": name.value,
            "label": ELEMENT_LABELS_ZH[name],
            "el": el,
            "value": _value(el),
            "candidates": [_candidate(c) for c in el.iter_candidates()],
        }
        for name, el in result.elements.items()
    ]
    return env.get_template(f"report.{format}.j2").render(
        result=result,
        rows=rows,
        suggestions=_suggestion_rows(result),
        semantic_assessment=result.semantic_assessment,
        whitespace_checks=[c for c in result.quote_checks if c.status == "whitespace"],
        title="结案草稿" if report_type == "closure" else "阶段报告",
        template_version=TEMPLATE_VERSION,
        duration=final_duration(result),
        generated=result.run.finished_at or result.run.started_at,
    )


def _suggestion_rows(result):
    from ..schema.suggestions import source_refs

    rows = []
    for suggestion in result.suggestions:
        if getattr(result.elements, suggestion.element).value is not None:
            continue  # 原答保留在审计与关系区，不重复标成待确认建议
        original = suggestion.node
        candidates = []
        key = "party" if suggestion.element == "responsible_party" else "description"
        for i, candidate in enumerate(suggestion.candidates):
            checks = [c for c in suggestion.checks if c.path == f"candidates/{i}"]
            node = candidate if isinstance(candidate, dict) else {}
            candidates.append(dict(original=node, raw=candidate, malformed=not isinstance(candidate, dict),
                                   missing_source=not source_refs(candidate), text=node.get(key, ""), checks=checks))
        rows.append(dict(label=ELEMENT_LABELS_ZH[suggestion.element], original=original,
                         unprovided=not isinstance(suggestion.original, dict), raw=suggestion.original,
                         missing_value_source=bool(original.get("value")) and not source_refs(original),
                         candidates=candidates,
                         checks=[c for c in suggestion.checks if not c.path.startswith("candidates/")]))
    return rows


OUTPUT_NAMES = (
    "analysis.json",
    "report.md",
    "report.html",
    "report.css",
    "company_report.html",
    "company_report.docx",
)


def write_reports(
    result: AnalysisResult,
    directory: Path,
    *,
    report_type: str = "stage",
    profile: ReportProfile | None = None,
) -> None:
    from ..extract.storage import ensure_output_allowed

    ensure_output_allowed(result.data_class, directory)
    for name in OUTPUT_NAMES:
        ensure_output_allowed(result.data_class, directory / name)
    profile = profile if profile is not None else load_report_profile()
    outputs = {
        f"report.{fmt}": render(result, format=fmt, report_type=report_type)
        for fmt in ("md", "html")
    }
    outputs["analysis.json"] = result.model_dump_json(indent=2) + "\n"
    outputs["report.css"] = (ROOT / "report.css").read_text(encoding="utf-8")
    # 公司格式与审核报告同源：同一份校验后的结果，不重新抽取。
    checked = AnalysisResult.model_validate(result.model_dump(mode="json"))
    outputs["company_report.html"] = render_company_html(checked, profile)
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        (directory / name).write_text(content, encoding="utf-8")
    write_company_docx(checked, directory / "company_report.docx", profile)
