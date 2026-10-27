"""离线回放：绑定工单与实际解析证据快照，不访问网络。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from ..extract.types import Extraction, ExtractionContext
from ..schema.common import Model


def evidence_digest(ctx: ExtractionContext) -> str:
    raw = json.dumps(
        [s.model_dump(mode="json") for s in ctx.evidence],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class ReplayRecord(Model):
    replay_version: Literal["1.0"] = "1.0"
    bundle_sha256: str
    evidence_sha256: str
    extraction: Extraction


def save_replay(path: Path, ctx: ExtractionContext, extraction: Extraction) -> None:
    from ..extract.storage import ensure_output_allowed

    ensure_output_allowed(ctx.bundle.manifest.data_class, path)
    record = ReplayRecord(
        bundle_sha256=ctx.bundle.manifest_sha256,
        evidence_sha256=evidence_digest(ctx),
        extraction=extraction,
    )
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")


class ReplayProvider:
    name = "replay"

    def __init__(self, path: Path):
        self.path = path

    def extract(self, ctx: ExtractionContext) -> Extraction:
        record = ReplayRecord.model_validate_json(self.path.read_text(encoding="utf-8"))
        if (
            record.bundle_sha256 != ctx.bundle.manifest_sha256
            or record.evidence_sha256 != evidence_digest(ctx)
        ):
            raise ValueError("回放快照与工单包或解析证据不一致，请重新录制。")
        return record.extraction
