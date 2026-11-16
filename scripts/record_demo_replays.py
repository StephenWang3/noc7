"""给操作台的五张合成演示单各真实调用一次模型，把诊断记录存进 fixtures/demo-replays/，以后演示时回放。

只处理合成单（data_class=synthetic），记录里没有真实数据，可以进仓库。需要 DEEPSEEK_API_KEY
（或 --model-config 指向的模型所需的密钥），每张单 fact_passes + 1 次请求。

    DEEPSEEK_API_KEY=… uv run python scripts/record_demo_replays.py
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from noc7.bundle import load_bundle
from noc7.extract.pipeline import analyze_with_context
from noc7.providers.text_config import create_text_provider
from noc7.web.jobs import PREPARED

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model-config", type=Path, default=ROOT / "config/models/deepseek.json")
    ap.add_argument("--only", nargs="+", choices=PREPARED, help="只录这几张")
    args = ap.parse_args()
    out = ROOT / "fixtures/demo-replays"
    out.mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="noc7-demo-record-"))
    try:
        for ref in args.only or PREPARED:
            bundle_dir = ROOT / "fixtures/bundles" / ref
            if load_bundle(bundle_dir).manifest.data_class != "synthetic":
                raise SystemExit(f"{ref} 不是合成单，不能录进仓库")
            audit = scratch / ref
            provider = create_text_provider(args.model_config, audit_dir=audit)
            try:
                analyze_with_context(bundle_dir, provider)
            except Exception as exc:  # 一张失败不影响其他张
                print(f"✗ {ref}：{type(exc).__name__}：{exc}")
                continue
            records = [json.loads(p.read_text(encoding="utf-8")) for p in audit.glob("*.json")]
            accepted = [r for r in records if r.get("outcome") == "accepted"]
            if not accepted:
                print(f"✗ {ref}：没有成功的模型结果")
                continue
            target = out / f"{ref}.json"
            target.write_text(json.dumps(accepted[-1], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"✓ {ref} → {target.relative_to(ROOT)}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
