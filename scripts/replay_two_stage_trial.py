"""离线重放一次两段式试跑：用每张工单诊断记录里存下的模型回复，按当前代码重跑本地核对、裁决和报告。

不联网、不需要密钥。输出目录结构与试跑相同，可直接用同一套对照脚本；另在 summary.json 里列出
与原运行相比结论变了的工单。提示词改动不能靠重放验证，须真实调用模型（只重跑受影响的工单）。
"""
from __future__ import annotations

import argparse
import json
import os
import traceback
from collections import Counter
from pathlib import Path

from noc7.extract.pipeline import analyze_with_context
from noc7.extract.storage import ensure_output_allowed
from noc7.providers.text_config import load_model_config
from noc7.providers.two_stage_replay import TwoStageReplayProvider
from noc7.report import write_reports
from noc7.schema import DataClass

from run_full_ticket_trial import write
from run_two_stage_trial import NAMES, metrics

# 对照时看的结论：时间看规整值，其余看取值本身。
WATCH = ("start_time", "end_time", "responsible_party", "location", "cause")


def conclusion(elements: dict) -> dict:
    out = {}
    for name in WATCH:
        value = (elements.get(name) or {}).get("value")
        out[name] = value.get("iso") if isinstance(value, dict) else value
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run", type=Path, help="原试跑输出目录（含 mapping.json 和各工单的 audit/）")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model-config", type=Path, default=Path("config/models/deepseek.json"),
                    help="只取其中的抽取遍数等设置，不读密钥")
    ap.add_argument("--only", nargs="+", help="只重放这些代号，如 F07 F13")
    args = ap.parse_args()
    config = load_model_config(args.model_config)
    if config.pipeline != "two_stage":
        raise SystemExit("模型配置的 pipeline 不是 two_stage。")
    os.umask(0o077)
    run = args.run.expanduser().resolve()
    out = args.out.expanduser().resolve()
    ensure_output_allowed(DataClass.REAL, out)
    if out.exists():
        raise SystemExit("输出必须为新目录")
    entries = json.loads((run / "mapping.json").read_text(encoding="utf-8"))
    entries = [e for e in entries if (run / e["alias"]).is_dir() and (not args.only or e["alias"] in args.only)]
    out.mkdir(parents=True, mode=0o700)
    write(out / "mapping.json", entries)
    rows, changed = [], {}
    for entry in entries:
        alias = entry["alias"]
        source, target = run / alias, out / alias
        target.mkdir(mode=0o700)
        row = dict(alias=alias, status="failed")
        try:
            audits = sorted((source / "audit").glob("*.json"))
            if len(audits) != 1:
                raise ValueError(f"诊断记录应恰好一份，实际 {len(audits)} 份")
            provider = TwoStageReplayProvider(config, json.loads(audits[0].read_text(encoding="utf-8")))
            row.update(mode=provider.mode, prompt_changed=provider.prompt_changed)
            result, _, _ = analyze_with_context(entry["source"], provider)
            write_reports(result, target, report_type="closure")
            row.update(status="ok", **metrics(result))
            before_path = source / "analysis.json"
            if before_path.is_file():
                before = conclusion(json.loads(before_path.read_text(encoding="utf-8"))["elements"])
                after = conclusion(json.loads((target / "analysis.json").read_text(encoding="utf-8"))["elements"])
                diff = {k: [before[k], after[k]] for k in WATCH if before[k] != after[k]}
                if diff:
                    changed[alias] = diff
        except Exception as exc:
            row["error"] = type(exc).__name__ + "：" + str(exc)[:120]
            write(target / "failure.json", dict(traceback=traceback.format_exc()))
        rows.append(row)
        print(alias, row["status"], row.get("mode", ""), "提示词已变" if row.get("prompt_changed") else "",
              "结论有变化" if alias in changed else "", flush=True)
    write(out / "metrics.json", rows)
    ok = [r for r in rows if r["status"] == "ok"]
    summary = dict(total=len(entries), ok=len(ok),
                   modes=dict(Counter(r.get("mode") for r in rows)),
                   prompt_changed=sum(bool(r.get("prompt_changed")) for r in rows),
                   filled={name: sum(r["filled"][name] for r in ok) for name in NAMES},
                   recovery_sources=dict(Counter(r["recovery_source"] for r in ok)),
                   changed=changed)
    write(out / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "changed"}, ensure_ascii=False))
    print(f"结论有变化的工单 {len(changed)} 张：" + "、".join(changed) if changed else "结论与原运行一致。")


if __name__ == "__main__":
    main()
