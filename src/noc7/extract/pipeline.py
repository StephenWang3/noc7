"""导入 → 解析 → 去重 → 提供方抽取 → 规则 → A0 结果。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..bundle import load_bundle
from ..fuse import link_duplicates
from ..parsers import ParseContext, default_registry
from ..rules import VERSION, check, issue, validate_extraction
from ..schema import AnalysisResult, IssueCode, Material, RunInfo
from .baseline import RulesProvider
from .types import ExtractionContext, TextProvider


def analyze(
    path: str | Path, provider: TextProvider | None = None, *, registry=None
) -> AnalysisResult:
    result, _, _ = analyze_with_context(path, provider, registry=registry)
    return result


def analyze_with_context(path, provider=None, *, registry=None):
    started = datetime.now(timezone.utc).isoformat()
    b = load_bundle(path)
    provider = provider or RulesProvider()
    registry = registry or default_registry()
    materials, spans, issues = [], [], []
    for m in b.manifest.materials:
        output = registry.parse(ParseContext(b, m))
        materials.append(
            Material(
                **m.model_dump(),
                parse_status=output.status,
                subtype=output.subtype,
                parser=output.parser,
                parse_note=output.note,
            )
        )
        spans.extend(
            output.spans
            if output.status == "parsed"
            else [s.model_copy(update={"needs_review": True}) for s in output.spans]
        )
        issues.extend(output.issues)
        status_code = {
            "failed": IssueCode.MATERIAL_PARSE_FAILED,
            "unsupported": IssueCode.MATERIAL_UNSUPPORTED,
            "needs_review": IssueCode.MATERIAL_LOW_QUALITY,
        }.get(output.status)
        if status_code and not any(i.code == status_code for i in output.issues):
            issues.append(
                issue(
                    status_code,
                    f"材料 {m.id} 未完整解析：{output.note or output.status}。",
                    [s.id for s in output.spans],
                )
            )
    spans = link_duplicates(spans)
    ctx = ExtractionContext(b, spans)
    data = provider.extract(ctx)
    validate_extraction(ctx, data)
    issues.extend(check(ctx, data))
    for warning in b.warnings:
        issues.append(issue(IssueCode.ATTACHMENT_FLAG_MISMATCH, warning))
    # 相同规则、要素、证据只保留一条；保留不同来源的同类问题。
    unique = {}
    for i in issues:
        unique.setdefault((i.code, i.element, tuple(sorted(i.evidence_refs))), i)
    issues = list(unique.values())
    payload = data.elements.model_dump(mode="json")
    for name, el in data.elements.items():
        payload[name.value]["issues"] = list(
            dict.fromkeys(i.code for i in issues if i.element == name)
        )
    result = AnalysisResult(
        bundle_id=b.manifest.bundle_id,
        ticket_ref=b.ticket.ticket_ref,
        data_class=b.manifest.data_class,
        data_cutoff=b.manifest.captured_at,
        materials=materials,
        evidence=spans,
        events=data.events,
        elements=payload,
        issues=issues,
        service_identity=data.service_identity,
        related_tickets=b.ticket.related_tickets,
        run=RunInfo(
            pipeline_version="a1.1.0",
            schema_version="1.0",
            provider=provider.name,
            rules_version=VERSION,
            bundle_sha256=b.manifest_sha256,
            started_at=started,
            finished_at=datetime.now(timezone.utc).isoformat(),
        ),
    )
    return result, ctx, data
