"""绑定冻结输入与原请求证据的模型原响应离线重放；没有网络路径。"""
from __future__ import annotations

import hashlib
import json
import traceback
from collections import Counter
from pathlib import Path

from ..extract import analyze
from ..providers.text_http import OpenAICompatibleTextProvider
from ..providers.text_prompt import prepare_evidence
from ..providers.text_replay import evidence_digest
from ..quote_match import match_quote
from ..schema.suggestions import source_refs
from ..report import write_reports
from ..rules import ExtractionRejected
from .prepare import load_dataset, new_root, private_path, write_json


def candidate_metrics(payload, spans, *, element=None):
    counts = Counter(total=0, strict=0, whitespace=0, mismatch=0, missing_source=0,
                     zero_candidate_elements=0, zero_candidate_cases=0)
    total = 0
    for name, key in (("responsible_party", "party"), ("location", "description")):
        if element is not None and name != element:
            continue
        node = payload.get("elements", {}).get(name)
        node = node if isinstance(node, dict) else {}
        candidates = node.get("candidates")
        candidates = candidates if isinstance(candidates, list) else []
        if not candidates:
            counts["zero_candidate_elements"] += 1
        for candidate in candidates:
            total += 1
            counts["total"] += 1
            if not isinstance(candidate, dict):
                counts["missing_source"] += 1
                continue
            refs = source_refs(candidate)
            if not refs or any(r not in spans for r in refs):
                counts["missing_source"] += 1
                continue
            text = candidate.get(key)
            statuses = [match_quote(text if isinstance(text, str) else "", spans[r].text).status for r in refs]
            counts["strict" if "strict" in statuses else "whitespace" if "whitespace" in statuses else "mismatch"] += 1
    counts["zero_candidate_cases"] = int(total == 0)
    return dict(counts)


def summarize_metrics(rows):
    counts = Counter()
    reasons = Counter()
    unavailable = 0
    for row in rows:
        if "candidate_metrics" in row:
            counts.update(row["candidate_metrics"])
        else:
            unavailable += 1
        reasons.update(row.get("issue_codes", []))
    total = counts["total"]
    by_element = {}
    for name in ("responsible_party", "location"):
        subset = [dict(candidate_metrics=r["candidate_metrics_by_element"][name])
                  for r in rows if "candidate_metrics_by_element" in r]
        if subset:
            combined = Counter()
            for r in subset:
                combined.update(r["candidate_metrics"])
            n = combined["total"]
            by_element[name] = dict(counts=dict(combined), verifiable_rate=(combined["strict"] + combined["whitespace"]) / n if n else None)
    return dict(counts=dict(counts), by_element=by_element,
                verifiable_rate=(counts["strict"] + counts["whitespace"]) / total if total else None,
                unavailable_cases=unavailable, rejection_reasons=dict(reasons))


class AuditResponseProvider:
    name = "replay:model-audit"

    def __init__(self, record):
        self.record = record
        self.metrics = None
        self.metrics_by_element = None
        self.prompt_version = record.get("prompt_version")

    def extract(self, ctx):
        clean, request = prepare_evidence(ctx)
        record = self.record
        if "business_coverage" not in record["request_evidence"]:
            request.pop("business_coverage", None)
        if (record["bundle_sha256"] != ctx.bundle.manifest_sha256
            or record["evidence_sha256"] != evidence_digest(clean)
            or record["request_evidence"] != request):
            raise ValueError("模型审计与输入包、实际请求证据不一致")
        raw = record["raw_response"].encode("utf-8")
        # 即使后续来源或其他要素拒绝，也统计本次原始候选；未绑定输入不统计。
        try:
            payload = json.loads(json.loads(raw)["choices"][0]["message"]["content"])
            allowed = {s.id for s in clean.evidence}
            spans = {s.id: s for s in ctx.evidence if s.id in allowed}
            self.metrics = candidate_metrics(payload, spans)
            self.metrics_by_element = {name: candidate_metrics(payload, spans, element=name)
                                       for name in ("responsible_party", "location")}
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            self.metrics = None
        return OpenAICompatibleTextProvider._decode(raw, clean)


def replay_audit(dataset: Path, audit_dir: Path, out: Path):
    data = load_dataset(dataset)
    audit_dir = private_path(audit_dir)
    root = new_root(out, dataset, audit_dir)
    records = {}
    for path in sorted(audit_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if "raw_response" not in record:
            continue
        key = record["bundle_sha256"]
        if key in records:
            raise ValueError("同一输入存在多份审计响应，请明确选择一份")
        records[key] = record
    rows = []
    for case in data["cases"]:
        if case["status"] != "ok":
            continue
        row = dict(alias=case["alias"], status="failed")
        provider = None
        try:
            provider = AuditResponseProvider(records[case["bundle_sha256"]])
            result = analyze(dataset / "inputs" / case["alias"], provider=provider)
            write_reports(result, root / case["alias"])
            row["status"] = "ok"
        except Exception as exc:
            row["issue_codes"] = sorted({i.code.value for i in exc.issues}) if isinstance(exc, ExtractionRejected) else ["REPLAY_OR_STRUCTURE_REJECTED"]
            write_json(root / case["alias"] / "failure.json", {"traceback": traceback.format_exc()})
        if provider is not None and provider.metrics is not None:
            row["candidate_metrics"] = provider.metrics
            row["candidate_metrics_by_element"] = provider.metrics_by_element
        rows.append(row)
    write_json(root / "run.json", dict(
        cases=rows, provider="replay:model-audit", external_services=False,
        dataset_sha256=hashlib.sha256((dataset / "references.json").read_bytes()).hexdigest(),
    ))
    write_json(root / "suggestion-summary.json", summarize_metrics(rows))
    return rows
