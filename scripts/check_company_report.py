"""对照生成的公司格式报告与本机样例的版式（ADR 0007）。

只比较表格行列数、合并结构和栏目标签；不打印任何单元格内容，
所以可以拿仓库外的真实样例对照，输出也可以贴进文档。

    uv run python scripts/check_company_report.py <生成的.docx> ~/.noc7/real/report_samples/gd_A05.docx

有差异时返回 1。
"""

from __future__ import annotations

import sys
from pathlib import Path

from docx import Document

from noc7.report.company import COLS, LAYOUT, ROWS, SIGNATURES, TITLE


def _norm(text: str) -> str:
    return "".join(text.split())


def _structure(path: Path):
    doc = Document(str(path))
    if not doc.tables:
        return None, None, {}, []
    table = doc.tables[0]
    # 同一个 tc（横向合并）或竖向合并到同一格的位置得到同一编号。
    # 保留全部 tc 引用，避免对象被回收后 id() 复用导致编号串格。
    seen: dict[int, int] = {}
    alive, grid = [], []
    for r, row in enumerate(table.rows):
        line = []
        for c in range(len(row.cells)):
            tc = table.cell(r, c)._tc
            alive.append(tc)
            line.append(seen.setdefault(id(tc), len(seen)))
        grid.append(line)
    labels = {
        (r, c): _norm(table.cell(r, c).text)
        for r, c, _, _, spec in LAYOUT
        if isinstance(spec, tuple) and r < len(table.rows) and c < len(table.columns)
    }
    paragraphs = [_norm(p.text) for p in doc.paragraphs if p.text.strip()]
    return (len(table.rows), len(table.columns)), grid, labels, paragraphs


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    generated, sample = (_structure(Path(p).expanduser()) for p in argv)
    problems = []
    if generated[0] != (ROWS, COLS):
        problems.append(f"生成文档表格为 {generated[0]}，应为 {(ROWS, COLS)}")
    if sample[0] != generated[0]:
        problems.append(f"行列数不同：生成 {generated[0]}，样例 {sample[0]}")
    elif generated[1] != sample[1]:
        rows = [i for i, (a, b) in enumerate(zip(generated[1], sample[1])) if a != b]
        problems.append(f"合并结构不同的行：{rows}")
    for pos, label in generated[2].items():
        if sample[2].get(pos) != label:
            problems.append(f"栏目标签不同：第 {pos[0]} 行第 {pos[1]} 列")
    for doc_name, (_, _, _, paragraphs) in (("生成", generated), ("样例", sample)):
        texts = "\n".join(paragraphs)
        if not paragraphs or not paragraphs[0].startswith(_norm("故障处理报告")):
            problems.append(f"{doc_name}文档首段不是标题")
        for label in SIGNATURES:
            if _norm(label) not in texts:
                problems.append(f"{doc_name}文档缺少签名栏：{label.strip()}")
    if not generated[3] or generated[3][0] != _norm(TITLE):
        problems.append("生成文档标题与模板不一致")
    for line in problems:
        print(f"✗ {line}")
    if not problems:
        print(f"✓ 版式一致：{ROWS}×{COLS} 表格、合并结构、{len(generated[2])} 个栏目标签、标题与签名栏")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
