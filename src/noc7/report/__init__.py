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

TEMPLATE_VERSION = "1.0"
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
    }


def final_duration(result: AnalysisResult) -> float | None:
    if any(i.code == "TICKET_CANCELLED" for i in result.issues):
        return None
    start, end = result.elements.start_time, result.elements.end_time
    if end.status != ElementStatus.CONFIRMED or not start.value or not end.value:
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
        title="结案草稿" if report_type == "closure" else "阶段报告",
        template_version=TEMPLATE_VERSION,
        duration=final_duration(result),
        generated=result.run.finished_at or result.run.started_at,
    )


def write_reports(
    result: AnalysisResult, directory: Path, *, report_type: str = "stage"
) -> None:
    from ..extract.storage import ensure_output_allowed

    ensure_output_allowed(result.data_class, directory)
    for name in ("analysis.json", "report.md", "report.html", "report.css"):
        ensure_output_allowed(result.data_class, directory / name)
    outputs = {
        f"report.{fmt}": render(result, format=fmt, report_type=report_type)
        for fmt in ("md", "html")
    }
    outputs["analysis.json"] = result.model_dump_json(indent=2) + "\n"
    outputs["report.css"] = (ROOT / "report.css").read_text(encoding="utf-8")
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        (directory / name).write_text(content, encoding="utf-8")
