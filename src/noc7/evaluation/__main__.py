"""python -m noc7.evaluation：本机参考评估，不打印真实内容。"""

import argparse
import os
from pathlib import Path

from .prepare import prepare
from .score import run, score


def main(argv=None):
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--selection", type=Path, required=True)
    r = sub.add_parser("run")
    r.add_argument("--dataset", type=Path, required=True)
    s = sub.add_parser("score")
    s.add_argument("--dataset", type=Path, required=True)
    s.add_argument("--results", type=Path, required=True)
    for p in (p, r, s):
        p.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            rows = prepare(args.selection.expanduser(), args.out)
            ok = sum(c["status"] == "ok" for c in rows)
            print(f"参考冻结：纳入 {ok}，排除 {len(rows) - ok}")
            return int(not ok)
        if args.command == "run":
            rows = run(args.dataset.expanduser(), args.out)
            failed = sum(c["status"] != "ok" for c in rows)
            print(f"基线提取：完成 {len(rows) - failed}，失败 {failed}")
            return int(not rows or bool(failed))
        summary = score(args.dataset.expanduser(), args.results.expanduser(), args.out)
        m = summary["totals"]
        print(
            f"评分：可判定 {m['determinate']}，待判定 {m['pending']}，未确认输入支持 {m['reference_only']}，失败 {summary['failed']}"
        )
        return int(not m["determinate"] or bool(summary["failed"]))
    except Exception:
        # 路径/校验异常可能包含真实身份；不给终端或自动收集的控制台日志。
        print("评估未完成：请核对本机输入、冻结记录、输出目录及逐例失败文件。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
