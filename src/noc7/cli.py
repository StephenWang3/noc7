"""命令行入口：A0 契约检查与 A1 分析、报告、回放。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .bundle import BundleError, load_bundle, rehash_bundle
from .goldcheck import check_gold_file
from .schema import AnalysisResult, BundleManifest, GoldAnswer, ProcessLog, TicketRecord

SCHEMA_MODELS = {
    "bundle-manifest": BundleManifest,
    "ticket": TicketRecord,
    "process-log": ProcessLog,
    "analysis-result": AnalysisResult,
    "gold-answer": GoldAnswer,
}
DEFAULT_SCHEMA_DIR = Path("schemas")
DEFAULT_BUNDLES = Path("fixtures/bundles")
DEFAULT_GOLD = Path("evals/gold")


def render_schemas() -> dict[str, str]:
    out = {}
    for name, model in SCHEMA_MODELS.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["$id"] = f"noc7/{name}.schema.json"
        out[f"{name}.schema.json"] = (
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    return out


def cmd_schema_export(args: argparse.Namespace) -> int:
    args.out.mkdir(parents=True, exist_ok=True)
    for fname, text in render_schemas().items():
        (args.out / fname).write_text(text, encoding="utf-8")
        print(f"写入 {args.out / fname}")
    return 0


def cmd_schema_check(args: argparse.Namespace) -> int:
    stale = [
        fname
        for fname, text in render_schemas().items()
        if not (args.out / fname).exists()
        or (args.out / fname).read_text(encoding="utf-8") != text
    ]
    if stale:
        print("JSON Schema 已过期，请运行 noc7 schema export：" + ", ".join(stale))
        return 1
    print("JSON Schema 与代码一致")
    return 0


def _bundle_dirs(paths: list[Path]) -> list[Path]:
    if not paths:
        paths = [DEFAULT_BUNDLES]
    out = []
    for p in paths:
        if (p / "manifest.json").exists():
            out.append(p)
        else:
            out.extend(sorted(d for d in p.iterdir() if (d / "manifest.json").exists()))
    return out


def cmd_bundle_validate(args: argparse.Namespace) -> int:
    failed = 0
    for d in _bundle_dirs(args.paths):
        try:
            b = load_bundle(d)
        except BundleError as e:
            failed += 1
            print(f"✗ {d}")
            for p in e.problems:
                print(f"    - {p}")
            continue
        print(f"✓ {d}（{b.manifest.data_class}，材料 {len(b.manifest.materials)} 份）")
        for w in b.warnings:
            print(f"    · 警告：{w}")
    return 1 if failed else 0


def cmd_bundle_rehash(args: argparse.Namespace) -> int:
    for d in args.paths:
        changed = rehash_bundle(d)
        print(f"{d}: 更新 {', '.join(changed) if changed else '无变化'}")
    return 0


def cmd_gold_check(args: argparse.Namespace) -> int:
    failed = 0
    gold_files = sorted(args.gold.glob("*.json"))
    bundles = {d.name: d for d in _bundle_dirs([args.bundles])}
    for g in gold_files:
        bundle_dir = bundles.get(g.stem)
        if bundle_dir is None:
            print(f"✗ {g.name}: 找不到对应工单包 {args.bundles / g.stem}")
            failed += 1
            continue
        problems = check_gold_file(g, load_bundle(bundle_dir))
        if problems:
            failed += 1
            print(f"✗ {g.name}")
            for p in problems:
                print(f"    - {p}")
        else:
            print(f"✓ {g.name}")
    missing = sorted(set(bundles) - {g.stem for g in gold_files})
    for name in missing:
        print(f"✗ 工单包 {name} 没有标准答案")
    return 1 if failed or missing else 0


def cmd_analyze(args: argparse.Namespace) -> int:
    from .extract.pipeline import analyze_with_context
    from .providers.text_replay import ReplayProvider, save_replay
    from .report import write_reports
    from .rules import ExtractionRejected

    if args.provider == "replay" and args.replay is None:
        print("replay 提供方必须指定 --replay。", file=sys.stderr)
        return 2
    try:
        directories = _bundle_dirs(args.paths)
    except OSError as e:
        print(f"无法读取输入目录：{e}", file=sys.stderr)
        return 1
    if not directories:
        print("没有找到工单包。", file=sys.stderr)
        return 1
    failed = 0
    # 目录名只作输出子目录；不把未经验证的 bundle_id 当路径。
    names = [d.name for d in directories]
    if len(names) != len(set(names)):
        print("输入目录重名，无法唯一确定输出位置，请分批运行。", file=sys.stderr)
        return 2
    if any(
        (args.out / name).resolve().is_relative_to(source.resolve())
        for name in names
        for source in directories
    ):
        print("输出目录不能位于输入工单包内，请另选 --out。", file=sys.stderr)
        return 2
    for directory in directories:
        try:
            replay = args.replay
            if replay is not None and replay.is_dir():
                replay = replay / directory.name / "replay.json"
            provider = ReplayProvider(replay) if args.provider == "replay" else None
            result, ctx, extraction = analyze_with_context(directory, provider)
            target = args.out / directory.name
            write_reports(result, target, report_type=args.report_type)
            if args.save_replay:
                save_replay(target / "replay.json", ctx, extraction)
            incomplete = sum(m.parse_status != "parsed" for m in result.materials)
            print(
                f"✓ {directory.name}：{len(result.evidence)} 段证据，{len(result.issues)} 项提示，{incomplete} 份材料未完整解析 → {target}"
            )
        except ExtractionRejected as e:
            failed += 1
            print(
                f"✗ {directory.name}：拒绝抽取结果（未生成本次报告）", file=sys.stderr
            )
            for i in e.issues:
                print(f"    {i.code}：{i.message}", file=sys.stderr)
            # 保存可机读的拒绝原因；不保存不合格的提供方结论或证据正文。
            from datetime import datetime, timezone

            from .extract.storage import ensure_output_allowed

            try:
                bundle = load_bundle(directory)
                target = args.out / directory.name / "analysis-rejected.json"
                ensure_output_allowed(bundle.manifest.data_class, target)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    json.dumps(
                        {
                            "status": "rejected",
                            "provider": args.provider,
                            "bundle_sha256": bundle.manifest_sha256,
                            "recorded_at": datetime.now(timezone.utc).isoformat(),
                            "issues": [i.model_dump(mode="json") for i in e.issues],
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            except (BundleError, ValueError, OSError):
                print("    拒绝记录无法写入指定目录。", file=sys.stderr)
        except (BundleError, ValueError, OSError) as e:
            failed += 1
            print(f"✗ {directory.name}：{e}", file=sys.stderr)
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="noc7", description="NOC 故障七要素提取与报告生成"
    )
    ap.add_argument("--version", action="version", version=f"noc7 {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("local-batch", help="仅在本机批量分析顶层工单包，生成逐单索引与脱敏统计")
    p.add_argument("root", type=Path)
    p.add_argument("--out", type=Path, required=True, help="新的仓库外输出目录")
    p.add_argument("--expected-count", type=int)
    p.set_defaults(func=cmd_local_batch)

    p = sub.add_parser("analyze", help="分析工单包并生成 JSON、Markdown、HTML 报告")
    p.add_argument("paths", nargs="*", type=Path, help="工单包或包含多个工单包的目录")
    p.add_argument("--out", type=Path, default=Path("var/reports"))
    p.add_argument("--provider", choices=("rules", "replay"), default="rules")
    p.add_argument(
        "--replay",
        type=Path,
        help="单份回放 JSON 或包含 <工单包目录名>/replay.json 的目录",
    )
    p.add_argument(
        "--save-replay", action="store_true", help="在每份报告目录保存可回放快照"
    )
    p.add_argument("--report-type", choices=("stage", "closure"), default="stage")
    p.set_defaults(func=cmd_analyze)

    schema = sub.add_parser("schema", help="导出/检查 JSON Schema").add_subparsers(
        dest="sub", required=True
    )
    for name, fn, helptext in (
        ("export", cmd_schema_export, "把 Pydantic 契约导出为 JSON Schema"),
        ("check", cmd_schema_check, "检查已提交的 JSON Schema 是否与代码一致"),
    ):
        p = schema.add_parser(name, help=helptext)
        p.add_argument("--out", type=Path, default=DEFAULT_SCHEMA_DIR)
        p.set_defaults(func=fn)

    bundle = sub.add_parser("bundle", help="工单包").add_subparsers(
        dest="sub", required=True
    )
    p = bundle.add_parser(
        "validate", help="校验工单包（默认校验 fixtures/bundles 下全部）"
    )
    p.add_argument("paths", nargs="*", type=Path)
    p.set_defaults(func=cmd_bundle_validate)
    p = bundle.add_parser("rehash", help="重算材料哈希写回 manifest（编写合成样本用）")
    p.add_argument("paths", nargs="+", type=Path)
    p.set_defaults(func=cmd_bundle_rehash)

    gold = sub.add_parser("gold", help="标准答案").add_subparsers(
        dest="sub", required=True
    )
    p = gold.add_parser("check", help="校验标准答案及其证据锚点")
    p.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    p.add_argument("--bundles", type=Path, default=DEFAULT_BUNDLES)
    p.set_defaults(func=cmd_gold_check)
    return ap


def cmd_local_batch(args: argparse.Namespace) -> int:
    from .batch import run_local_batch

    try:
        summary = run_local_batch(
            args.root, args.out, expected_count=args.expected_count,
            progress=lambda alias, status: print(f"{alias}：{'已生成' if status == 'ok' else '失败，见本机记录'}", flush=True),
        )
    except (ValueError, OSError) as e:
        print(f"批次预检/写入失败：{e}", file=sys.stderr)
        return 1
    failed = sum(c["status"] != "ok" for c in summary["cases"])
    print(f"完成 {len(summary['cases']) - failed}，失败 {failed}；请打开输出目录中的 index.html。")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
