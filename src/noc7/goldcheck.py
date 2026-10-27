"""标准答案与工单包的一致性检查：锚点必须指向工单包里真实存在的位置。"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .bundle import Bundle
from .schema.evidence import MaterialKind
from .schema.gold import EvidenceAnchor, GoldAnswer


def load_gold(path: str | Path) -> GoldAnswer:
    return GoldAnswer.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _check_anchor(anchor: EvidenceAnchor, bundle: Bundle, where: str) -> list[str]:
    try:
        m = bundle.manifest.material(anchor.material_id)
    except KeyError:
        return [f"{where}: 材料 {anchor.material_id} 不存在"]
    out = []
    if anchor.field_key is not None:
        if m.kind is not MaterialKind.TICKET_FIELDS:
            out.append(f"{where}: field_key 只能用于 ticket_fields 材料")
        elif bundle.ticket.field(anchor.field_key) is None:
            out.append(f"{where}: ticket.json 没有字段 {anchor.field_key}")
        elif bundle.ticket.field(anchor.field_key).value is None:
            out.append(f"{where}: 字段 {anchor.field_key} 为空，不能作为证据")
    if anchor.log_seq is not None:
        if m.kind is not MaterialKind.PROCESS_LOG:
            out.append(f"{where}: log_seq 只能用于 process_log 材料")
        elif bundle.process_log.entry(anchor.log_seq) is None:
            out.append(f"{where}: 处理过程没有第 {anchor.log_seq} 条")
    if anchor.message_index is not None and m.kind not in (MaterialKind.EMAIL_HTML, MaterialKind.EMAIL_EML):
        out.append(f"{where}: message_index 只能用于邮件材料")
    if anchor.page is not None and m.kind is not MaterialKind.PDF:
        out.append(f"{where}: page 只能用于 PDF 材料")
    return out


def check_gold(gold: GoldAnswer, bundle: Bundle) -> list[str]:
    problems: list[str] = []
    if gold.bundle_id != bundle.manifest.bundle_id:
        problems.append(f"bundle_id 不一致：标准答案 {gold.bundle_id}，工单包 {bundle.manifest.bundle_id}")
    for name, el in gold.elements.items():
        for i, a in enumerate(el.evidence):
            problems += _check_anchor(a, bundle, f"{name}.evidence[{i}]")
        for i, c in enumerate(el.required_candidates):
            for j, a in enumerate(c.evidence):
                problems += _check_anchor(a, bundle, f"{name}.required_candidates[{i}].evidence[{j}]")
    return problems


def check_gold_file(gold_path: Path, bundle: Bundle) -> list[str]:
    try:
        gold = load_gold(gold_path)
    except ValidationError as e:
        return [f"{gold_path.name}: {'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
    return check_gold(gold, bundle)
