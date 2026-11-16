"""分析过程记录：把一次分析里“拆包 → 编号 → 请求模型 → 本地规则 → 出报告”的数据整理成一份，
供操作台按步骤演示。只用这次分析真实产生的数据（结果 + 模型诊断记录），不另编内容。

文件写在这张单的输出目录（仓库外 ~/.noc7/…），和报告放在一起。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from ..schema import ELEMENT_LABELS_ZH, AnalysisResult

MAX_EVIDENCE = 300
EVIDENCE_TEXT = 60
RAW_TEXT = 4000
QUOTE_TEXT = 160


def build_trace(result: AnalysisResult, record: dict | None, *, mode: str, model_label: str,
                elapsed_seconds: float, fallback: dict | None = None) -> dict:
    """record：这次分析写下的模型诊断记录；fallback：回放所用的原记录（较早的记录这次没有逐遍原始回复时补上）。"""
    data = result.model_dump(mode="json")
    spans_per_material: dict[str, int] = {}
    for span in data["evidence"]:
        spans_per_material[span["material_id"]] = spans_per_material.get(span["material_id"], 0) + 1
    materials = [
        {
            "id": m["id"], "kind": m["kind"], "parse_status": m["parse_status"],
            "parser": (m.get("parser") or "").split("@")[0],
            "spans": spans_per_material.get(m["id"], 0),
            "ocr": m["kind"] in {"image", "pdf"} or "ocr" in (m.get("parser") or "").lower(),
            "note": m.get("parse_note") or "",
        }
        for m in data["materials"]
    ]
    kinds = {m["id"]: m["kind"] for m in data["materials"]}
    return {
        "version": 1,
        "mode": mode,
        "model_label": model_label,
        "provider": result.run.provider,
        "rules_version": result.run.rules_version,
        "elapsed_seconds": round(elapsed_seconds, 2),
        "materials": materials,
        "spans": len(data["evidence"]),
        "model": _model_part(record or {}, fallback or {}, kinds),
        "rules": _rules_part(record or {}, data),
    }


def _model_part(record: dict, fallback: dict, kinds: dict[str, str]) -> dict:
    request = record.get("request_evidence") or fallback.get("request_evidence") or {}
    evidence = request.get("evidence") if isinstance(request.get("evidence"), list) else []
    items = [
        {"id": e.get("id", ""), "kind": kinds.get(str(e.get("id", "")).split("/")[0], ""),
         "text": _cut(e.get("text"), EVIDENCE_TEXT)}
        for e in evidence[:MAX_EVIDENCE] if isinstance(e, dict)
    ]
    responses = record.get("fact_responses")
    if not (isinstance(responses, list) and responses):
        raw = record.get("raw_response") or fallback.get("raw_response")
        responses = [raw] if isinstance(raw, str) else []
    kept = record.get("facts_kept") if isinstance(record.get("facts_kept"), list) else []
    dropped = record.get("facts_dropped") if isinstance(record.get("facts_dropped"), list) else []
    return {
        "recorded": bool(record),
        "sent": len(evidence),
        "request_kb": round(len(json.dumps(request, ensure_ascii=False).encode("utf-8")) / 1024, 1),
        "attempts": record.get("request_attempts") or len(responses),
        "passes": [_cut(_reply_text(r), RAW_TEXT) for r in responses if isinstance(r, str)],
        "facts_kept": [_fact(f) for f in kept if isinstance(f, dict)],
        "facts_dropped": [_fact(f) | {"reason": str(f.get("reason") or "")} for f in dropped if isinstance(f, dict)],
        "narrative": record.get("narrative_outcome") or "",
        "narrative_replaced": bool(record.get("narrative_replaced")),
        "usage": record.get("usage") if isinstance(record.get("usage"), list) else [],
        "evidence": items,
    }


def _rules_part(record: dict, data: dict) -> list[dict]:
    before = ((record.get("before_grounding") or {}).get("elements") or {}) if record else {}
    out = []
    for name in ELEMENT_LABELS_ZH:
        key = name.value
        old = before.get(key) if isinstance(before.get(key), dict) else {}
        el = data["elements"][key]
        out.append({
            "element": key,
            "before": old.get("status") or "",
            "model_candidates": len(old.get("candidates") or []),
            "after": el["status"],
            "candidates": len(el.get("candidates") or []),
            "issues": [
                {"severity": i["severity"], "message": i["message"]}
                for i in data["issues"] if i.get("element") == key
            ],
        })
    return out


def _reply_text(raw: str) -> str:
    """原始回复是接口外层 JSON；取出模型写的那段内容，能解析成 JSON 就排成易读的样子。"""
    text = raw
    try:
        body = json.loads(raw)
        text = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        pass
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=1)
    except (ValueError, TypeError):
        return str(text)


def _fact(f: dict) -> dict:
    return {"type": str(f.get("type") or ""), "evidence_id": str(f.get("evidence_id") or ""),
            "quote": _cut(f.get("quote"), QUOTE_TEXT), "time": str(f.get("time") or "")}


def _cut(text, n: int) -> str:
    s = str(text or "")
    return s if len(s) <= n else s[:n] + "…"


def write_trace(path: Path, trace: dict) -> None:
    path.write_text(json.dumps(trace, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def read_trace(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None
