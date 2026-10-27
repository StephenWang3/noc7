"""本机批处理：固定默认解析器与本地规则，正文和异常只写仓库外。

summary.json 采用白名单字段；本机 mapping.json 才保留真实身份与输入位置。
不递归扫描历史目录，不复用已有结果，单单失败后继续并返回失败计数。
"""

from __future__ import annotations

import html
import json
import platform
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from .bundle import load_bundle
from .extract.baseline import usable_text
from .extract.pipeline import analyze
from .extract.storage import ensure_output_allowed
from .report import write_reports
from .schema import DataClass


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def summarize_case(alias, result):
    """仅输出枚举、计数与本轮代号，不复制任意来源字符串或异常文本。"""
    used = {ref for _, el in result.elements.items() for ref in el.evidence_refs}
    materials = []
    for material in result.materials:
        spans = [s for s in result.evidence if s.material_id == material.id]
        materials.append({
            "id": material.id,
            "kind": material.kind.value,
            "status": material.parse_status.value,
            "subtype": material.subtype.value if material.subtype else None,
            "spans": len(spans),
            "eligible_spans": sum(bool(usable_text(s)) for s in spans),
            "conclusion_spans": sum(s.id in used for s in spans),
            # 仅这两个导出器固定路径作为留档计数；不把一般 other 材料排除在外。
            "source_archive": material.kind.value == "other" and material.path in {
                "source/capture.json", "source/log-map.json"
            },
        })
    elements = {}
    for name, element in result.elements.items():
        candidates = list(element.iter_candidates())
        kinds = Counter()
        for c in candidates:
            for field in ("time_kind", "cause_kind", "basis", "role", "step_kind"):
                if hasattr(c, field):
                    kinds[str(getattr(c, field))] += 1
                    break
        elements[name.value] = {
            "status": element.status.value,
            "candidates": len(candidates),
            "candidate_kinds": dict(kinds),
        }
    return {
        "alias": alias, "status": "ok", "materials": materials, "elements": elements,
        "issues": dict(Counter(i.code.value for i in result.issues)),
    }


def aggregate(cases):
    materials = defaultdict(Counter)
    elements = defaultdict(Counter)
    affected = Counter()
    for case in cases:
        if case["status"] != "ok":
            continue
        for m in case["materials"]:
            materials[m["kind"]][m["status"]] += 1
        for name, el in case["elements"].items():
            elements[name][el["status"]] += 1
        affected.update(case["issues"].keys())
    return {"materials": dict(materials), "elements": dict(elements), "issue_cases": dict(affected)}


def _index(rows):
    lines = []
    for row in rows:
        alias = row["alias"]
        identity = html.escape(row.get("ticket_ref", "输入校验失败"))
        if row["status"] == "ok":
            links = f'<a href="{alias}/report.html">查看报告</a> · <a href="{alias}/analysis.json">七要素 JSON</a>'
        else:
            links = f'<a href="{alias}/failure.json">查看本机失败记录</a>'
        lines.append(f"<tr><td>{alias}</td><td>{identity}</td><td>{links}</td></tr>")
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<link rel="stylesheet" href="index.css"><title>本机联调结果</title></head><body><main>'
            '<h1>本机联调结果</h1><p>仅供本机逐单对照；全部报告均为待人工审核草稿。</p>'
            '<p>代号映射与输入绝对路径见 mapping.json；统计见 summary.json。'
            '解析通过率不代表七要素准确率，未知不等于源系统缺失。</p>'
            '<table><thead><tr><th>本轮代号</th><th>工单编号（仅本机）</th><th>结果</th></tr></thead><tbody>'
            + "".join(lines) + '</tbody></table></main></body></html>\n')


def run_local_batch(root: Path, out: Path, *, expected_count=None, progress=None):
    root, out = root.expanduser().resolve(), out.expanduser().resolve()
    # 即使混有合成包，本机联调产物也统一放仓库外；预检早于任何正文写入。
    ensure_output_allowed(DataClass.REAL, out)
    if not root.is_dir():
        raise ValueError("输入必须是包含工单包的目录。")
    directories = sorted(d for d in root.iterdir() if d.is_dir() and (d / "manifest.json").is_file())
    if not directories or (expected_count is not None and len(directories) != expected_count):
        raise ValueError(f"顶层工单包数量为 {len(directories)}，与要求不符。")
    if out.is_relative_to(root) or root.is_relative_to(out):
        raise ValueError("输入与输出目录必须互不包含。")
    if out.exists():
        raise ValueError("输出目录已存在，请指定新的批次目录，避免混入旧报告。")
    out.mkdir(parents=True, mode=0o700)
    started = datetime.now(timezone.utc).isoformat()
    cases, mapping = [], []
    for i, directory in enumerate(directories, 1):
        alias = f"R{i:02d}"
        entry = {"alias": alias, "source": str(directory), "status": "failed"}
        target = out / alias
        target.mkdir(mode=0o700)
        try:
            bundle = load_bundle(directory)
            entry["ticket_ref"] = bundle.ticket.ticket_ref
            entry["bundle_sha256"] = bundle.manifest_sha256
            result = analyze(directory)
            write_reports(result, target)
            for path in target.iterdir():
                path.chmod(0o600)
            case = summarize_case(alias, result)
            entry["status"] = "ok"
        except Exception:
            # 原始异常可能包含路径、客户或材料正文，只在本机保存。
            _write_json(target / "failure.json", {"traceback": traceback.format_exc()})
            case = {"alias": alias, "status": "failed"}
        cases.append(case)
        mapping.append(entry)
        summary = {"format_version": "1.0", "cases": cases, "totals": aggregate(cases)}
        _write_json(out / "summary.json", summary)
        _write_json(out / "mapping.json", mapping)
        (out / "index.html").write_text(_index(mapping), encoding="utf-8")
        (out / "index.html").chmod(0o600)
        if progress:
            progress(alias, case["status"])
    css = Path(__file__).parent / "report" / "report.css"
    (out / "index.css").write_bytes(css.read_bytes())
    (out / "index.css").chmod(0o600)
    _write_json(out / "run.json", {
        "started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "provider": "rules", "external_services": False,
        "packages": {name: version(name) for name in ("noc7", "rapidocr-onnxruntime", "onnxruntime", "pymupdf", "python-docx")},
        "pipeline_version": "integration.1.0", "expected_count": expected_count,
        "completed": sum(c["status"] == "ok" for c in cases),
        "failed": sum(c["status"] != "ok" for c in cases),
    })
    return summary
