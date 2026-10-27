"""工单包的加载与校验。

导入层的唯一入口：不论工单包来自合成样本、上传还是导出脚本，都先过 validate_bundle。
校验失败的工单包不进入解析；缺件、哈希不符都要明确报出来，不能静默跳过。
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from .schema.bundle import BundleManifest, ProcessLog, TicketRecord
from .schema.common import DataClass
from .schema.evidence import ManifestMaterial, MaterialKind

MANIFEST = "manifest.json"
SYNTHETIC_PREFIX = "SYN-"

# 源码仓库根目录（从源码运行时存在）。真实工单包不允许放在仓库里。
_REPO_ROOT = Path(__file__).resolve().parents[2]
_IS_SOURCE_CHECKOUT = (_REPO_ROOT / "pyproject.toml").exists() and (_REPO_ROOT / "src" / "noc7").is_dir()

ATTACHMENT_KINDS = {
    MaterialKind.IMAGE,
    MaterialKind.PDF,
    MaterialKind.DOCX,
    MaterialKind.EMAIL_EML,
    MaterialKind.TEXT,
    MaterialKind.OTHER,
}
EMAIL_KINDS = {MaterialKind.EMAIL_HTML, MaterialKind.EMAIL_EML}


class BundleError(Exception):
    """工单包无法加载。problems 列出全部问题，便于一次改完。"""

    def __init__(self, path: Path, problems: list[str]):
        self.path = path
        self.problems = problems
        super().__init__(f"{path}: " + "; ".join(problems))


@dataclass
class Bundle:
    root: Path
    manifest: BundleManifest
    ticket: TicketRecord
    process_log: ProcessLog
    manifest_sha256: str
    warnings: list[str] = field(default_factory=list)

    def path_of(self, material: ManifestMaterial) -> Path:
        return self.root / material.path

    def read_bytes(self, material_id: str) -> bytes:
        return self.path_of(self.manifest.material(material_id)).read_bytes()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _inside_repo(path: Path) -> bool:
    if not _IS_SOURCE_CHECKOUT:
        return False
    try:
        path.resolve().relative_to(_REPO_ROOT)
        return True
    except ValueError:
        return False


def _load_json(path: Path, problems: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        problems.append(f"缺少文件 {path.name}")
    except json.JSONDecodeError as e:
        problems.append(f"{path.name} 不是合法 JSON: {e}")
    return None


def _fmt(e: ValidationError, name: str) -> list[str]:
    return [f"{name}: {'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()]


def load_bundle(path: str | Path) -> Bundle:
    """加载并校验工单包；有任何错误抛 BundleError，警告放在 Bundle.warnings。"""
    root = Path(path)
    problems: list[str] = []
    warnings: list[str] = []

    raw_manifest = _load_json(root / MANIFEST, problems)
    if raw_manifest is None:
        raise BundleError(root, problems)
    try:
        manifest = BundleManifest.model_validate(raw_manifest)
    except ValidationError as e:
        raise BundleError(root, _fmt(e, MANIFEST)) from None

    # —— 数据分级 ——
    if manifest.data_class is DataClass.REAL and _inside_repo(root):
        problems.append("真实工单包不能放在源码仓库里，请放到仓库外的本机目录（默认 ~/.noc7/real/）")
    if manifest.data_class is DataClass.SYNTHETIC and not manifest.bundle_id.startswith(SYNTHETIC_PREFIX):
        problems.append(f"合成工单包的 bundle_id 必须以 {SYNTHETIC_PREFIX} 开头")

    # —— 材料文件：存在、大小、哈希 ——
    declared = set()
    for m in manifest.materials:
        p = root / m.path
        declared.add(p.resolve())
        if not p.is_file():
            problems.append(f"{m.id}: 材料文件不存在 {m.path}")
            continue
        if p.stat().st_size != m.size_bytes:
            problems.append(f"{m.id}: 文件大小与清单不符（清单 {m.size_bytes}，实际 {p.stat().st_size}）")
        if sha256_file(p) != m.sha256:
            problems.append(f"{m.id}: sha256 与清单不符，文件可能被改动")
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != MANIFEST and p.resolve() not in declared and not p.name.startswith("."):
            problems.append(f"清单未声明的文件: {p.relative_to(root)}（材料必须逐一登记，避免漏件或夹带）")

    # —— ticket.json / process_log.json ——
    ticket = None
    tm = manifest.material_of_kind(MaterialKind.TICKET_FIELDS)
    raw_ticket = _load_json(root / tm.path, problems) if tm else None
    if raw_ticket is not None:
        try:
            ticket = TicketRecord.model_validate(raw_ticket)
        except ValidationError as e:
            problems.extend(_fmt(e, tm.path))

    process_log = ProcessLog(entries=[])
    lm = manifest.material_of_kind(MaterialKind.PROCESS_LOG)
    if lm is None:
        warnings.append("工单包没有处理过程（process_log）")
    else:
        raw_log = _load_json(root / lm.path, problems)
        if raw_log is not None:
            try:
                process_log = ProcessLog.model_validate(raw_log)
            except ValidationError as e:
                problems.extend(_fmt(e, lm.path))

    if ticket is not None and manifest.data_class is DataClass.SYNTHETIC and ticket.ticket_ref != manifest.bundle_id:
        problems.append("合成工单包的 ticket_ref 必须与 bundle_id 相同")

    # —— 处理过程里的附件/邮件引用 ——
    by_id = {m.id: m for m in manifest.materials}
    for e in process_log.entries:
        for mid in e.attachments:
            m = by_id.get(mid)
            if m is None:
                problems.append(f"处理过程第 {e.seq} 条引用了不存在的附件 {mid}")
            elif m.kind not in ATTACHMENT_KINDS:
                problems.append(f"处理过程第 {e.seq} 条把 {mid}（{m.kind}）当作附件")
        for mid in e.emails:
            m = by_id.get(mid)
            if m is None:
                problems.append(f"处理过程第 {e.seq} 条引用了不存在的邮件 {mid}")
            elif m.kind not in EMAIL_KINDS:
                problems.append(f"处理过程第 {e.seq} 条把 {mid}（{m.kind}）当作邮件")
        if e.attachment_flag is not None and e.attachment_flag != bool(e.attachments):
            warnings.append(f"处理过程第 {e.seq} 条的附件标志为 {e.attachment_flag}，实际附件 {len(e.attachments)} 个")
    referenced = process_log.referenced_materials()
    for m in manifest.materials:
        if m.kind in (MaterialKind.TICKET_FIELDS, MaterialKind.PROCESS_LOG):
            continue
        if m.id not in referenced and (m.origin is None or m.origin.log_seq is None):
            warnings.append(f"{m.id} 没有被任何处理过程引用，也没有注明出处")

    if problems:
        raise BundleError(root, problems)
    assert ticket is not None
    return Bundle(
        root=root,
        manifest=manifest,
        ticket=ticket,
        process_log=process_log,
        manifest_sha256=sha256_file(root / MANIFEST),
        warnings=warnings,
    )


def rehash_bundle(path: str | Path) -> list[str]:
    """重新计算清单里每份材料的 sha256 和大小，写回 manifest.json。仅供编写合成样本时使用。"""
    root = Path(path)
    data = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    changed = []
    for m in data["materials"]:
        p = root / m["path"]
        digest, size = sha256_file(p), p.stat().st_size
        if m.get("sha256") != digest or m.get("size_bytes") != size:
            changed.append(m["id"])
        m["sha256"], m["size_bytes"] = digest, size
        if not m.get("media_type"):
            m["media_type"] = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    (root / MANIFEST).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return changed
