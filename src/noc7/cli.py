"""命令行入口。A0 提供契约相关命令；analyze / serve / eval 由后续阶段加入。"""

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
        out[f"{name}.schema.json"] = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
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
        if not (args.out / fname).exists() or (args.out / fname).read_text(encoding="utf-8") != text
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


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="noc7", description="NOC 故障七要素提取与报告生成")
    ap.add_argument("--version", action="version", version=f"noc7 {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    schema = sub.add_parser("schema", help="导出/检查 JSON Schema").add_subparsers(dest="sub", required=True)
    for name, fn, helptext in (
        ("export", cmd_schema_export, "把 Pydantic 契约导出为 JSON Schema"),
        ("check", cmd_schema_check, "检查已提交的 JSON Schema 是否与代码一致"),
    ):
        p = schema.add_parser(name, help=helptext)
        p.add_argument("--out", type=Path, default=DEFAULT_SCHEMA_DIR)
        p.set_defaults(func=fn)

    bundle = sub.add_parser("bundle", help="工单包").add_subparsers(dest="sub", required=True)
    p = bundle.add_parser("validate", help="校验工单包（默认校验 fixtures/bundles 下全部）")
    p.add_argument("paths", nargs="*", type=Path)
    p.set_defaults(func=cmd_bundle_validate)
    p = bundle.add_parser("rehash", help="重算材料哈希写回 manifest（编写合成样本用）")
    p.add_argument("paths", nargs="+", type=Path)
    p.set_defaults(func=cmd_bundle_rehash)

    gold = sub.add_parser("gold", help="标准答案").add_subparsers(dest="sub", required=True)
    p = gold.add_parser("check", help="校验标准答案及其证据锚点")
    p.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    p.add_argument("--bundles", type=Path, default=DEFAULT_BUNDLES)
    p.set_defaults(func=cmd_gold_check)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
