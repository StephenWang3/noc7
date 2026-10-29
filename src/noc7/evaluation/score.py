"""确定性、保守的参考一致性评分。未命中不等于业务错误。"""

from __future__ import annotations

import hashlib
import traceback
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ..extract import analyze
from ..schema import AnalysisResult
from ..schema.common import ElementName
from .prepare import load_dataset, new_root, write_json
from .reference import Fact, matches_points, positions, read_json

OUTCOMES = (
    "agree",
    "missing",
    "conflict",
    "pending",
    "reference_only",
    "source_conflict",
)
LABELS = {
    "agree": "一致",
    "missing": "遗漏",
    "conflict": "明确冲突",
    "pending": "待判定",
    "reference_only": "未确认输入支持",
    "source_conflict": "参考来源冲突",
}


def _zone(offset: str | None):
    if not offset or len(offset) != 6 or offset[0] not in "+-" or offset[3] != ":":
        return None
    try:
        sign = 1 if offset[0] == "+" else -1
        return timezone(
            sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[4:6]))
        )
    except ValueError:
        return None


def _local_date(iso: str, default_timezone: str | None):
    """日期精度按工单时区折到当地日期。只有日期的值本身就是日期。"""
    if len(iso) == 10:
        return date.fromisoformat(iso)
    try:
        moment = datetime.fromisoformat(iso)
    except ValueError:
        return None
    zone = _zone(default_timezone)
    if moment.utcoffset() is None or zone is None:
        return None
    return moment.astimezone(zone).date()


def compare_time(fact, element, default_timezone=None):
    value = element.value
    if value is None or not value.iso:
        return "missing"
    candidate = next((c for c in element.candidates if c.id == element.selected), None)
    if candidate is None or candidate.time_kind != fact.time_kind:
        return "pending"
    want = fact.expected_time.iso
    got = value.iso
    if len(want) == 10:
        left, right = _local_date(want, default_timezone), _local_date(got, default_timezone)
        if left is None or right is None:
            return "pending"
        return "agree" if left == right else "conflict"
    if len(got) == 10 or value.precision not in {"second", "minute"}:
        return "pending"
    a, b = datetime.fromisoformat(want), datetime.fromisoformat(got)
    if a.utcoffset() is None or b.utcoffset() is None:
        return "pending"
    # 参考精度冻结在标注中，不能用一分钟容差吞掉跨分钟差异。
    if fact.time_precision == "minute":
        a = a.replace(second=0, microsecond=0)
        b = b.replace(second=0, microsecond=0)
    elif value.precision != "second":
        return "pending"
    return (
        "agree"
        if abs((a - b).total_seconds()) <= fact.expected_time.tolerance_minutes * 60
        else "conflict"
    )


def compare(fact: Fact, element, default_timezone=None):
    if not element.value:
        return "missing"
    if getattr(element, "status", "documented") not in fact.allowed_statuses:
        return "conflict"
    if fact.value_kind:
        chosen = next((c for c in element.candidates if c.id == element.selected), None)
        if chosen is None:
            return "pending"
        kind = next(
            (
                getattr(chosen, k)
                for k in ("cause_kind", "basis", "role")
                if hasattr(chosen, k)
            ),
            None,
        )
        if kind != fact.value_kind:
            return "conflict"
    if fact.expected_time:
        return compare_time(fact, element, default_timezone)
    if fact.element == ElementName.HANDLING_PROCESS:
        text = "\n".join(
            " ".join(filter(None, [s.actor, s.action, s.target, s.result]))
            for s in element.value
            if not s.duplicate_of
        )
    else:
        text = element.value
    if any(positions(text, term) for term in fact.contradicts):
        return "conflict"
    if not matches_points(text, fact.key_points):
        return "pending"
    if fact.element == ElementName.HANDLING_PROCESS:
        last = -1
        for point in fact.key_points:
            choices = sorted(
                p for s in point.any_of for p in positions(text, s) if p >= last
            )
            if not choices:
                return "conflict"
            last = choices[0]
    return "agree"


def run(dataset: Path, out: Path):
    data = load_dataset(dataset)
    root = new_root(out, dataset)
    rows = []
    for c in data["cases"]:
        if c["status"] != "ok":
            continue
        try:
            result = analyze(dataset / "inputs" / c["alias"])
            write_json(
                root / c["alias"] / "analysis.json", result.model_dump(mode="json")
            )
            rows.append({"alias": c["alias"], "status": "ok"})
        except Exception:
            write_json(
                root / c["alias"] / "failure.json",
                {"traceback": traceback.format_exc()},
            )
            rows.append({"alias": c["alias"], "status": "failed"})
    write_json(
        root / "run.json",
        {
            "cases": rows,
            "dataset_sha256": hashlib.sha256(
                (dataset / "references.json").read_bytes()
            ).hexdigest(),
            "provider": "rules",
            "external_services": False,
        },
    )
    return rows


def metric(counts):
    counts = {name: counts.get(name, 0) for name in OUTCOMES}
    determinate = sum(counts[k] for k in ("agree", "missing", "conflict"))
    eligible = determinate + counts["pending"]
    return dict(
        counts,
        determinate=determinate,
        eligible=eligible,
        agreement=counts["agree"] / determinate if determinate else None,
        decision_coverage=determinate / eligible if eligible else None,
    )


def score(dataset: Path, results: Path, out: Path):
    data = load_dataset(dataset)
    root = new_root(out, dataset, results)
    details = []
    counts = Counter()
    by_source = defaultdict(Counter)
    by_element = defaultdict(Counter)
    failed = 0
    for kind in ("formal_report", "closure_note", "final_email"):
        by_source[kind]
    for element in ElementName:
        by_element[element.value]
    for c in data["cases"]:
        if c["status"] != "ok":
            continue
        try:
            r = AnalysisResult.model_validate(
                read_json(results / c["alias"] / "analysis.json")
            )
            if r.run.bundle_sha256 != c["bundle_sha256"] or r.bundle_id not in {
                f"EVAL-{c['alias']}",
                f"SYN-EVAL-{c['alias']}",
            }:
                raise ValueError("分析结果与隔离输入不一致")
            manifest = read_json(dataset / "inputs" / c["alias"] / "manifest.json")
            expected = {m["id"]: m for m in manifest["materials"]}
            if {m.id: m.sha256 for m in r.materials} != {
                k: v["sha256"] for k, v in expected.items()
            }:
                raise ValueError("结果材料清单不一致")
            import json

            evidence_hash = hashlib.sha256(
                json.dumps(
                    [s.model_dump(mode="json") for s in r.evidence],
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            if evidence_hash != c["evidence_sha256"]:
                raise ValueError("结果证据与冻结输入解析快照不一致")
            sources = {s["id"]: s for s in c["sources"]}
            case = []
            for i, raw in enumerate(c["facts"]):
                f = Fact.model_validate(raw)
                status = (
                    "source_conflict"
                    if f.conflict
                    else "reference_only"
                    if not c["support"][i]
                    else compare(
                        f,
                        getattr(r.elements, f.element.value),
                        manifest.get("default_timezone"),
                    )
                )
                kind = sources[f.source_id]["kind"]
                counts[status] += 1
                by_source[kind][status] += 1
                by_element[f.element.value][status] += 1
                case.append(
                    dict(
                        element=f.element.value,
                        source=kind,
                        audit=sources[f.source_id]["audit"],
                        outcome=status,
                        reference_quote=f.quote,
                        input_support=c["support"][i],
                        actual=getattr(r.elements, f.element.value).model_dump(
                            mode="json"
                        ),
                    )
                )
            details.append({"alias": c["alias"], "status": "ok", "facts": case})
        except Exception:
            failed += 1
            write_json(
                root / c["alias"] / "failure.json",
                {"traceback": traceback.format_exc()},
            )
            details.append({"alias": c["alias"], "status": "failed"})
    # 仅固定枚举和数字；不复制来源、路径、业务身份、自由异常或哈希。
    summary = {
        "cases": len(data["cases"]),
        "prepared": sum(c["status"] == "ok" for c in data["cases"]),
        "excluded": sum(c["status"] != "ok" for c in data["cases"]),
        "failed": failed,
        "totals": metric(counts),
        "by_source": {k: metric(v) for k, v in by_source.items()},
        "by_element": {k: metric(v) for k, v in by_element.items()},
    }
    run_path = results / "run.json"
    if run_path.is_file():
        record = read_json(run_path)
        if record.get("provider") == "replay:model-audit":
            if record.get("dataset_sha256") != hashlib.sha256((dataset / "references.json").read_bytes()).hexdigest():
                raise ValueError("重放统计与冻结集不一致")
            from .audit_replay import summarize_metrics
            summary["suggestions"] = summarize_metrics(record["cases"])
    write_json(root / "summary.json", summary)
    write_json(root / "details.json", {"cases": details})
    lines = [
        "# 人工参考一致性评估",
        "",
        "本结果衡量与参考的一致程度，不代表人工结论或系统结论的业务正确率。",
        "一致率＝一致／（一致＋遗漏＋明确冲突）；可判定覆盖率＝可判定／（可判定＋待判定）。",
        "未确认输入支持及来源冲突不入分母；未知不视为参考答案。",
        "",
        "| 要素 | 一致 | 遗漏 | 明确冲突 | 待判定 | 未确认输入支持 | 来源冲突 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    from ..schema.common import ELEMENT_LABELS_ZH

    for k, m in summary["by_element"].items():
        lines.append(
            "| "
            + ELEMENT_LABELS_ZH[ElementName(k)]
            + " | "
            + " | ".join(str(m[n]) for n in OUTCOMES)
            + " |"
        )
    lines += ["", "## 逐例明细", ""]
    for c in details:
        lines.append(f"### {c['alias']}")
        for f in c.get("facts", []):
            lines.extend(
                [
                    "",
                    f"- {ELEMENT_LABELS_ZH[ElementName(f['element'])]}：{LABELS[f['outcome']]}；参考来源 {f['source']}。",
                    "",
                    "    " + f["reference_quote"].replace("\n", "\n    "),
                ]
            )
    if "suggestions" in summary:
        lines += ["", "## AI 建议引用核验（独立于正式结论评分）", "",
                  "候选有据率仅衡量引用可核验，不代表业务正确性。严格匹配与空白等价分列；全部原始候选入分母。重复候选不代表独立佐证。",
                  "", "```json", __import__("json").dumps(summary["suggestions"], ensure_ascii=False, indent=2), "```"]
    report = root / "report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report.chmod(0o600)
    return summary
