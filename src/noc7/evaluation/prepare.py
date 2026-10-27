"""构造物理隔离的截止前材料包。默认拒绝没有可核对归属的材料。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from ..bundle import load_bundle
from ..parsers import ParseContext, default_registry
from ..schema.common import DataClass
from ..schema.evidence import MaterialKind
from ..timeparse import parse_time
from .reference import (
    Selection,
    matches_points,
    normalized,
    read_json,
    times_in_quote,
    verify_sources,
)

CLOSED = re.compile(r"^(?:回访结单|结单签收|本地关单|结单归档|工单结案|结案|结单)$")
FINAL = re.compile(r"故障处理报告|故障报告|结案结论|最终结论|Failure\s+Report", re.I)


def private_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    for parent in (path, *path.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            raise ValueError("评估产物必须位于仓库外私有目录")
    return path


def write_json(path: Path, data):
    if path.is_symlink():
        raise ValueError("输出文件不能是符号链接")
    private_path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    path.chmod(0o600)


def new_root(out: Path, *inputs: Path) -> Path:
    out = private_path(out)
    for p in inputs:
        p = p.expanduser().resolve()
        if out == p or out.is_relative_to(p) or p.is_relative_to(out):
            raise ValueError("输入与输出不能互相包含")
    out.mkdir(parents=True, mode=0o700, exist_ok=False)
    return out


def clock(raw, offset):
    t = parse_time(raw, offset).as_datetime()
    return t if t is not None and t.utcoffset() is not None else None


def prepare_case(case, target: Path):
    private_path(case.bundle)
    for source in case.sources:
        private_path(source.path)
    b = load_bundle(case.bundle)
    blocks = verify_sources(case, b)
    offset = b.manifest.default_timezone
    closings = [
        clock(e.recorded_at, offset)
        for e in b.process_log.entries
        if CLOSED.fullmatch(e.action)
    ]
    if not closings or any(t is None for t in closings):
        raise ValueError("没有可确认时间的结案节点")
    cutoff = min(closings)
    if b.ticket.status.detail_status != "已结单":
        raise ValueError("详情状态不是已结单")
    # 源参考锚点排除，外部报告相同字节排除，长引文的重复出现也隔离。
    reference_logs = {
        s.anchor.log_seq for s in case.sources if s.anchor and s.anchor.log_seq
    }
    reference_materials = {
        s.anchor.material_id for s in case.sources if s.anchor and not s.anchor.log_seq
    }
    reference_hashes = {s.sha256 for s in case.sources}
    fingerprints = [
        normalized(f.quote) for f in case.facts if len(normalized(f.quote)) >= 12
    ]

    def leaked(text):
        t = normalized(text)
        return bool(FINAL.search(text)) or any(f in t for f in fingerprints)

    decisions, kept = [], []

    def record(where, keep, reason):
        decisions.append({"where": where, "keep": keep, "reason": reason})

    for e in b.process_log.entries:
        t = clock(e.recorded_at, offset)
        why = (
            "reference"
            if e.seq in reference_logs
            or leaked(
                " ".join(filter(None, [e.content, e.action, e.actor, e.actor_org]))
            )
            else "derived"
            if e.entry_kind == "ai_summary"
            else "time_unknown"
            if t is None
            else "after_cutoff"
            if t >= cutoff
            else "before_cutoff"
        )
        record(f"log:{e.seq}", why == "before_cutoff", why)
        if why == "before_cutoff":
            kept.append(e.model_copy(deep=True))
    seqs = {e.seq for e in kept}
    registry = default_registry()
    safe_spans = []
    lm = b.manifest.material_of_kind(MaterialKind.PROCESS_LOG)
    if lm:
        safe_spans = [
            s
            for s in registry.parse(ParseContext(b, lm)).spans
            if s.locator.seq in seqs and not s.needs_review
        ]
    # 仅显式指定、且字段值与保留日志原文逐字核对的最终快照字段可进入输入。
    fields = []
    for proof in case.field_proofs:
        field = b.ticket.field(proof.key)
        support = [
            s
            for s in safe_spans
            if proof.support.anchor.matches(s) and proof.support.quote in s.text
        ]
        if (
            field is None
            or not field.value
            or not support
            or field.value not in proof.support.quote
            or leaked(field.value)
        ):
            raise ValueError("字段历史依据不足或包含参考结论")
        fields.append(field)
    for f in b.ticket.fields:
        record(
            f"field:{f.key}",
            f in fields,
            "verified_history" if f in fields else "no_history",
        )
    target.mkdir(parents=True, mode=0o700)
    manifest = b.manifest.model_dump(mode="json")
    manifest.update(
        bundle_id=f"EVAL-{case.alias}",
        captured_at=cutoff.isoformat(),
        source={
            "kind": "upload",
            "tool": "noc7-human-reference-evaluation",
            "note": "仅截止前白名单材料",
        },
        materials=[],
    )
    if b.manifest.data_class == DataClass.SYNTHETIC:
        manifest["bundle_id"] = f"SYN-EVAL-{case.alias}"

    def add(mid, kind, path, data, mime="application/json", origin=None):
        p = target / path
        p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        p.write_bytes(data)
        p.chmod(0o600)
        manifest["materials"].append(
            dict(
                id=mid,
                kind=kind,
                path=path,
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
                media_type=mime,
                origin=origin,
            )
        )

    def encoded(data):
        return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()

    ticket = b.ticket.model_dump(mode="json")
    # 身份、标题、分类、状态、关联单均不传给提取器，避免元数据夹带结论。
    ticket.update(
        ticket_ref=manifest["bundle_id"],
        title="评估输入",
        category=None,
        fields=[f.model_dump(mode="json") for f in fields],
        related_tickets=[],
        status={"list_status": None, "detail_status": None},
    )
    tm = b.manifest.material_of_kind(MaterialKind.TICKET_FIELDS)
    add(tm.id, "ticket_fields", "ticket.json", encoded(ticket))
    safe_materials = set()
    for m in b.manifest.materials:
        if m.kind in {"ticket_fields", "process_log"}:
            continue
        parents = [
            e for e in b.process_log.entries if m.id in (*e.attachments, *e.emails)
        ]
        why = (
            "reference"
            if m.id in reference_materials
            or m.sha256 in reference_hashes
            or FINAL.search(m.path)
            else "excluded"
            if m.id in case.excluded_materials
            else "archive"
            if m.kind == "other" or m.path.startswith("source/")
            else "derived"
            if m.derived or m.derived_from
            else "origin_unknown"
            if not parents or any(e.seq not in seqs for e in parents)
            else "before_cutoff"
        )
        # origin.log_seq 不是时间证明；需要完整且唯一的日志归属。
        if why == "before_cutoff" and (
            len(parents) != 1 or not m.origin or m.origin.log_seq != parents[0].seq
        ):
            why = "origin_unknown"
        if why == "before_cutoff":
            result = registry.parse(ParseContext(b, m))
            if result.status in {"failed", "unsupported"} or any(
                s.needs_review for s in result.spans
            ):
                why = "uninspectable"
            elif any(leaked(s.text) for s in result.spans):
                why = "reference_copy"
            # EML 子附件或 DOCX 未覆盖区域也不能排除藏有答案。
            elif result.status != "parsed":
                why = "uninspectable"
        record(m.id, why == "before_cutoff", why)
        if why == "before_cutoff":
            safe_materials.add(m.id)
            add(
                m.id,
                m.kind.value,
                m.path,
                b.read_bytes(m.id),
                m.media_type,
                {"log_seq": parents[0].seq, "note": "截止前唯一归属已核对"},
            )
    for e in kept:
        e.attachments = [x for x in e.attachments if x in safe_materials]
        e.emails = [x for x in e.emails if x in safe_materials]
        e.attachment_flag = bool(e.attachments)
        # 操作者/组织作为过程证据保留；自由动作名也检查过最终结论标记。
    if lm:
        add(
            lm.id,
            "process_log",
            "process_log.json",
            encoded({"entries": [e.model_dump(mode="json") for e in kept]}),
        )
    write_json(target / "manifest.json", manifest)
    prepared = load_bundle(target)
    # 支持依据在最终隔离包重新解析、重新核验，不由标注者布尔值决定。
    spans = []
    for m in prepared.manifest.materials:
        out = registry.parse(ParseContext(prepared, m))
        if out.status in {"parsed", "needs_review"}:
            spans.extend(s for s in out.spans if not s.needs_review)
    # 对同语义但互斥的多个参考时间自动标记冲突；文本冲突由预先标注的互斥词判断。
    for i, f in enumerate(case.facts):
        for other in case.facts[i + 1 :]:
            if f.element != other.element:
                continue
            conflict = (
                f.expected_time
                and other.expected_time
                and f.time_kind == other.time_kind
                and not f.expected_time.matches(
                    parse_time(other.expected_time.iso, offset)
                )
            )
            conflict = conflict or any(
                normalized(t) in normalized(other.quote) for t in f.contradicts
            )
            conflict = conflict or any(
                normalized(t) in normalized(f.quote) for t in other.contradicts
            )
            if conflict:
                f.conflict = other.conflict = True
    from ..fuse import link_duplicates

    spans = link_duplicates(spans)
    evidence_hash = hashlib.sha256(
        json.dumps(
            [s.model_dump(mode="json") for s in spans],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    support = []
    for f in case.facts:
        refs = [
            s.id
            for proof in f.support
            for s in spans
            if proof.anchor.matches(s) and proof.quote in s.text
        ]
        supporting_text = "\n".join(
            proof.quote
            for proof in f.support
            if any(proof.anchor.matches(s) and proof.quote in s.text for s in spans)
        )
        if f.key_points and not matches_points(supporting_text, f.key_points):
            refs = []
        if f.expected_time:
            if not any(
                f.expected_time.matches(t) and proof.time_kind == f.time_kind
                for proof in f.support
                if any(proof.anchor.matches(s) and proof.quote in s.text for s in spans)
                for t in times_in_quote(proof.quote, offset)
            ):
                refs = []
        support.append(sorted(set(refs)))
    return dict(
        alias=case.alias,
        bundle_sha256=prepared.manifest_sha256,
        original_sha256=b.manifest_sha256,
        evidence_sha256=evidence_hash,
        cutoff=cutoff.isoformat(),
        facts=[f.model_dump(mode="json") for f in case.facts],
        sources=[s.model_dump(mode="json") for s in case.sources],
        support=support,
        decisions=decisions,
        reference_blocks=blocks,
    )


def prepare(selection_path: Path, out: Path):
    selection = Selection.model_validate(read_json(selection_path))
    root = new_root(
        out,
        selection_path,
        *[c.bundle for c in selection.cases],
        *[s.path for c in selection.cases for s in c.sources],
    )
    (root / "inputs").mkdir(mode=0o700)
    cases = []
    for case in selection.cases:
        try:
            result = prepare_case(case, root / "inputs" / case.alias)
            result["status"] = "ok"
        except Exception as exc:
            import shutil

            shutil.rmtree(root / "inputs" / case.alias, ignore_errors=True)
            result = {"alias": case.alias, "status": "excluded", "error": str(exc)}
        cases.append(result)
    # 冻结文件与所有 input 清单哈希绑定；run/score 均复核。
    write_json(
        root / "references.json",
        {
            "cases": cases,
            "selection_sha256": hashlib.sha256(selection_path.read_bytes()).hexdigest(),
        },
    )
    write_json(
        root / "freeze.json",
        {
            "references_sha256": hashlib.sha256(
                (root / "references.json").read_bytes()
            ).hexdigest()
        },
    )
    write_json(root / "selection.json", selection.model_dump(mode="json"))
    return cases


def load_dataset(root: Path):
    root = private_path(root)
    expected = read_json(root / "freeze.json")["references_sha256"]
    if hashlib.sha256((root / "references.json").read_bytes()).hexdigest() != expected:
        raise ValueError("冻结参考被修改，请创建新的数据集")
    data = read_json(root / "references.json")
    for c in data["cases"]:
        if c["status"] == "ok":
            b = load_bundle(root / "inputs" / c["alias"])
            if b.manifest_sha256 != c["bundle_sha256"]:
                raise ValueError("评估输入已变化")
    return data
