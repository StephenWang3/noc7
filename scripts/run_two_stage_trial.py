"""两段式试跑：只跑已结单，串行，每单最多两次请求；控制台只输出代号与状态。

真实明细只写仓库外的新目录。遇到 HTTP 402 或连续三张失败即停，不继续提交后面的工单。
"""
from __future__ import annotations

import argparse
import json
import os
import traceback
from collections import Counter
from pathlib import Path

from noc7.bundle import load_bundle
from noc7.extract.pipeline import analyze_with_context
from noc7.extract.storage import ensure_output_allowed
from noc7.providers.text_config import create_text_provider, load_model_config
from noc7.providers.text_replay import save_replay
from noc7.report import write_reports
from noc7.schema import DataClass

from run_full_ticket_trial import choose_complete_version, version_info, write

NAMES = ("start_time", "end_time", "phenomenon", "responsible_party", "cause", "handling_process", "location")


def metrics(result):
    e = result.elements
    record = result.semantic_assessment.recovery_selection
    steps = [s for s in e.handling_process.value if not s.duplicate_of]
    n = result.narrative
    return dict(
        filled={name: bool(getattr(e, name).value) for name in NAMES},
        candidates={name: len(list(getattr(e, name).iter_candidates())) for name in NAMES},
        recovery_source=record.sources.get(record.selected) if record and record.selected else None,
        facts_dropped=dict(Counter(d["reason"] for d in result.semantic_assessment.original.get("facts_dropped", []))),
        steps=len(steps), steps_without_time=sum(s.time is None for s in steps),
        narrative=None if n is None else dict(lines=len(n.process), replaced=n.replaced,
                                             phenomenon=bool(n.phenomenon), cause=bool(n.cause)),
    )


def usage_total(calls):
    total = Counter()
    for call in calls:
        total.update(call)
    return dict(requests=len(calls), **total)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("roots", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model-config", type=Path, required=True)
    ap.add_argument("--limit", type=int, help="只跑前 N 张，用于冒烟")
    ap.add_argument("--only", nargs="+", help="只跑这些代号，如 F10 F19")
    args = ap.parse_args()
    if load_model_config(args.model_config).pipeline != "two_stage":
        raise SystemExit("模型配置的 pipeline 不是 two_stage。")
    os.umask(0o077)
    out = args.out.expanduser().resolve()
    ensure_output_allowed(DataClass.REAL, out)
    if out.exists():
        raise SystemExit("输出必须为新目录")
    versions = {}
    for root in args.roots:
        for p in sorted(root.expanduser().resolve().iterdir()):
            if (p / "manifest.json").is_file():
                v = version_info(load_bundle(p))
                versions.setdefault(v["ticket_ref"], []).append(v)
    entries = [dict(choose_complete_version(v), alias=f"F{i:02d}") for i, v in enumerate(versions.values(), 1)]
    entries = [e for e in entries if e["closed"] and (not args.only or e["alias"] in args.only)][: args.limit]
    create_text_provider(args.model_config).preflight(DataClass.REAL)  # 缺密钥时在建目录和发请求前失败
    out.mkdir(parents=True, mode=0o700)
    write(out / "mapping.json", entries)
    rows, streak = [], 0
    for entry in entries:
        target = out / entry["alias"]
        target.mkdir(mode=0o700)
        row = dict(alias=entry["alias"], status="failed")
        try:
            provider = create_text_provider(args.model_config, audit_dir=target / "audit")
            result, ctx, extraction = analyze_with_context(entry["source"], provider)
            write_reports(result, target, report_type="closure")
            save_replay(target / "replay.json", ctx, extraction)
            row.update(status="ok", **metrics(result))
            row["usage"] = usage_total(provider.usage)
        except Exception as exc:
            row["status"] = "rejected" if hasattr(exc, "issues") else "failed"
            row["error"] = type(exc).__name__ + "：" + str(exc)[:80] if not hasattr(exc, "issues") else None
            write(target / "failure.json", dict(traceback=traceback.format_exc()))
        rows.append(row)
        write(out / "metrics.json", rows)
        print(row["alias"], row["status"], f"{len(rows)}/{len(entries)}", flush=True)
        streak = 0 if row["status"] == "ok" else streak + 1
        if "HTTP 402" in (row.get("error") or "") or streak >= 3:
            print("已停止：欠费或连续三张失败。", flush=True)
            break
    ok = [r for r in rows if r["status"] == "ok"]
    summary = dict(total=len(entries), attempted=len(rows), ok=len(ok),
                   filled={name: sum(r["filled"][name] for r in ok) for name in NAMES},
                   recovery_sources=dict(Counter(r["recovery_source"] for r in ok)),
                   narrative_ok=sum(r["narrative"] is not None for r in ok),
                   usage=usage_total(r["usage"] for r in ok if r.get("usage")))
    write(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
