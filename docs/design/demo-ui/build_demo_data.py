"""生成设计稿用的示例数据 demo-data.js。

只读取仓库里的合成工单包（fixtures/bundles），用规则基线跑一遍真实流水线，
把 AnalysisResult 的必要字段和公司报告表格（build_company_report）写成静态 JS，
让设计稿不依赖服务就能直接打开。设计稿阶段的临时脚本，前端实现时由真实接口取代。

用法（在仓库根目录）：uv run python docs/design/demo-ui/build_demo_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

from noc7.extract.pipeline import analyze
from noc7.report.company import (
    ReportProfile,
    build_company_report,
    render_company_html,
    write_company_docx,
)
from noc7.quote_match import match_quote
from noc7.report import render
from noc7.schema import ELEMENT_LABELS_ZH, AnalysisResult
from noc7.schema.suggestions import BusinessSuggestion

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("demo-data.js")
SAMPLES = Path(__file__).with_name("samples")
# 示例下载件用空页眉配置：不读取本机 ~/.noc7/report_profile 里的真实公司名和 logo。
NO_PROFILE = ReportProfile()
# 覆盖四种要素状态：P04 已确认较多、S09 未知多、P01 / S06 时间矛盾、S02 重复记录
TICKETS = ["SYN-P04", "SYN-S09", "SYN-P01", "SYN-S06", "SYN-S02"]
ELEMENT_ORDER = list(ELEMENT_LABELS_ZH)

# 「AI 建议，待确认」的示例。规则基线不产生建议，这里手写 original（模型原始两栏 JSON 的形状），
# 再由 BusinessSuggestion 和 match_quote 生成真正的 checks，整份结果过 AnalysisResult 校验。
# 通过的一条取原文里确有的子串（strict），另一条是原文里没有的推测（mismatch）。
SAMPLE_SUGGESTIONS = {
    "SYN-S09": [
        {
            "element": "location",
            "original": {
                "status": "unknown", "value": None, "selected": None,
                "candidates": [{
                    "id": "L1", "evidence_refs": ["M01/f:description"], "attribution": "customer",
                    "description": "25% packet loss from our proxy 198.51.100.20 (Frankfurt) to target 203.0.113.50 (Hong Kong)",
                    "role": "service_endpoint", "granularity": "segment",
                    "note": "客户感知丢包的路径，不是已定位的故障点",
                }],
            },
        },
        {
            "element": "responsible_party",
            "original": {
                "status": "unknown", "value": None, "selected": None,
                "candidates": [{
                    "id": "P1", "evidence_refs": ["M01/f:description"], "attribution": "unknown",
                    "party": "境外对端运营商", "basis": "inferred_from_role",
                    "note": "模型推测，材料里没有任何一方被认定为责任方",
                }],
            },
        },
    ]
}


def with_suggestions(result, name):
    """把示例建议接到结果上，checks 用真实的 match_quote 生成，最后整体重新校验。"""
    raw = SAMPLE_SUGGESTIONS.get(name)
    if not raw:
        return result
    spans = {s.id: s for s in result.evidence}
    suggestions = []
    for item in raw:
        draft = BusinessSuggestion(element=item["element"], original=item["original"])
        checks = [
            match_quote(text, spans[ref].text, path=path, evidence_id=ref)
            for path, ref, text in draft.quote_requests()
        ]
        suggestions.append(BusinessSuggestion(element=item["element"], original=item["original"], checks=checks))
    data = result.model_dump(mode="json")
    data["suggestions"] = [x.model_dump(mode="json") for x in suggestions]
    return AnalysisResult.model_validate(data)


def span_view(span) -> dict:
    return {
        "id": span.id,
        "material_id": span.material_id,
        "role": span.role.value,
        "locator": span.locator.model_dump(mode="json", exclude_none=True),
        "text": span.text,
    }


def build_ticket(name: str) -> dict:
    bundle_dir = ROOT / "fixtures" / "bundles" / name
    result = with_suggestions(analyze(bundle_dir), name)
    ticket = json.loads((bundle_dir / "ticket.json").read_text(encoding="utf-8"))
    data = result.model_dump(mode="json", exclude_none=True)
    report = build_company_report(result)
    write_company_docx(result, SAMPLES / f"{name}-company-report.docx", NO_PROFILE)
    # 公司网页版页脚链到“审核报告”（report.html）；示例里按工单写成真实存在的文件名。
    review = f"{name}-review-report.html"
    (SAMPLES / review).write_text(render(result, format="html"), encoding="utf-8")
    company_html = render_company_html(result, NO_PROFILE)
    assert 'href="report.html"' in company_html
    (SAMPLES / f"{name}-company-report.html").write_text(
        company_html.replace('href="report.html"', f'href="{review}"'), encoding="utf-8"
    )
    company = {
        "ticket_ref": report.ticket_ref,
        "report_date": report.report_date,
        "synthetic": report.synthetic,
        "cells": [
            {
                "row": c.row, "col": c.col, "rowspan": c.rowspan, "colspan": c.colspan,
                "label": c.label,
                "lines": [[{"text": p.text, "pending": p.pending} for p in line] for line in c.lines],
            }
            for c in report.grid()
        ],
    }
    return {
        "ticket": {
            "ticket_ref": result.ticket_ref,
            "title": ticket["title"],
            "category": ticket.get("category"),
            "list_status": ticket["status"]["list_status"],
            "data_class": result.data_class.value,
            "captured": result.data_cutoff,
        },
        "downloads": {
            "docx": f"samples/{name}-company-report.docx",
            "html": f"samples/{name}-company-report.html",
        },
        "analysis": {
            "schema_version": result.schema_version,
            "ticket_ref": result.ticket_ref,
            "data_class": result.data_class.value,
            "data_cutoff": result.data_cutoff,
            "run": {k: data["run"].get(k) for k in ("provider", "rules_version", "prompt_version", "finished_at")},
            "materials": [
                {k: m.get(k) for k in ("id", "kind", "path", "parse_status")} for m in data["materials"]
            ],
            "evidence": [span_view(s) for s in result.evidence],
            "elements": {k: data["elements"][k] for k in ELEMENT_ORDER},
            "issues": [
                {k: i.get(k) for k in ("code", "severity", "message", "element", "evidence_refs")}
                for i in data["issues"]
            ],
            "suggestions": data["suggestions"],
        },
        "company_report": company,
    }


def main() -> None:
    SAMPLES.mkdir(exist_ok=True)
    (SAMPLES / "report.css").write_text(
        (ROOT / "src/noc7/report/report.css").read_text(encoding="utf-8"), encoding="utf-8"
    )
    payload = {
        "element_labels": {k.value: v for k, v in ELEMENT_LABELS_ZH.items()},
        "tickets": [build_ticket(n) for n in TICKETS],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    OUT.write_text(
        "// 由 build_demo_data.py 生成，数据全部来自 fixtures/ 的合成工单包。不要手改。\n"
        f"window.NOC7_DEMO = {text};\n",
        encoding="utf-8",
    )
    print(f"写入 {OUT.relative_to(ROOT)}（{OUT.stat().st_size // 1024} KB，{len(TICKETS)} 张合成单）")


if __name__ == "__main__":
    main()
