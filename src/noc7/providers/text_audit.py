"""可选的本机模型诊断。只写仓库外私有文件，不保存请求头或密钥。"""

import json
import os
from pathlib import Path
from uuid import uuid4

from .text_config import TextProviderError
from .text_replay import evidence_digest


class AuditStore:
    def __init__(self, root: Path):
        supplied = root.expanduser()
        self.root = supplied.resolve()
        if supplied.is_symlink() or any((p / ".git").exists() or (p / "pyproject.toml").exists()
                                        for p in (self.root, *self.root.parents)):
            raise TextProviderError("模型诊断必须使用仓库外的新私有目录。")
        if self.root.exists():
            raise TextProviderError("模型诊断目录已存在，请使用新目录。")
        self.root.mkdir(parents=True, mode=0o700)

    def begin(self, ctx, request, prompt_version):
        return AuditRecord(self.root / (uuid4().hex + ".json"), {
            "version": "1.0", "bundle_sha256": ctx.bundle.manifest_sha256,
            "evidence_sha256": evidence_digest(ctx), "prompt_version": prompt_version,
            "request_evidence": request, "outcome": "request_prepared",
        })


class AuditRecord:
    def __init__(self, path, data):
        self.path, self.data = path, data
        self.record()

    def record(self, **values):
        self.data.update(values)
        if self.path.parent.is_symlink() or self.path.is_symlink():
            raise TextProviderError("模型诊断路径变成了符号链接，已停止。")
        tmp = self.path.with_name(uuid4().hex + ".tmp")
        try:
            with os.fdopen(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            tmp.replace(self.path)
        finally:
            tmp.unlink(missing_ok=True)


def grounding_changes(before, after):
    """摘要与完整两阶段快照并存，空候选与本地删除可区分。"""
    changes = []
    for name, old in before["elements"].items():
        new = after["elements"][name]
        if old.get("status") != new.get("status"):
            changes.append(dict(element=name, action="status_changed", before=old["status"], after=new["status"]))
        prior = {c["id"]: c for c in old.get("candidates", [])}
        later = {c["id"]: c for c in new.get("candidates", [])}
        for cid, candidate in prior.items():
            if cid not in later:
                changes.append(dict(element=name, candidate=cid, action="candidate_removed",
                                    reason="local_semantics_not_recognized"))
            else:
                for label in ("basis", "role", "cause_kind", "time_kind"):
                    if candidate.get(label) != later[cid].get(label):
                        changes.append(dict(element=name, candidate=cid, action="label_changed", label=label,
                                            before=candidate.get(label), after=later[cid].get(label)))
    return changes
