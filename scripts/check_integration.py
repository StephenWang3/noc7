"""默认全链路对照合成 gold；语义差异与 pytest 是否通过分别报告。"""

import argparse
import json
from pathlib import Path

from noc7.extract import analyze
from noc7.schema import DataClass, GoldAnswer

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "var/integration-synthetic.json")
    args = parser.parse_args()
    cases = []
    for path in sorted((ROOT / "fixtures/bundles").iterdir()):
        result = analyze(path)
        if result.data_class != DataClass.SYNTHETIC:
            raise ValueError("该对照脚本只允许仓库中的合成包。")
        gold = GoldAnswer.model_validate_json((ROOT / "evals/gold" / f"{path.name}.json").read_text())
        missing = sorted({i.code.value for i in gold.expected_issues} - {i.code.value for i in result.issues})
        mismatches = {
            name.value: {"expected": [s.value for s in expected.status_in],
                         "actual": getattr(result.elements, name).status.value}
            for name, expected in gold.elements.items()
            if getattr(result.elements, name).status not in expected.status_in
        }
        cases.append({"case": path.name, "missing_issues": missing, "status_mismatches": mismatches})
    failed = sum(bool(c["missing_issues"] or c["status_mismatches"]) for c in cases)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"scope": "仅合成包的要素状态与期望问题码，不是准确率评测",
                                   "cases": cases}, ensure_ascii=False, indent=2) + "\n")
    print(f"默认全链路：{len(cases)} 包可运行，{failed} 包与合成 gold 有语义差异；详见输出记录。")
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
