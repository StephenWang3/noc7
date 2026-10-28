"""仓库外参考标注。转录可核对，人工记录的业务正确性不作保证。"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

from pydantic import Field, field_validator, model_validator

from ..parsers import ParseContext, default_registry
from ..schema.common import ElementName, ElementStatus, Model
from ..schema.evidence import ManifestMaterial
from ..schema.gold import EvidenceAnchor, GoldTime, KeyPoint
from ..schema.timeval import TimeKind


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold().replace("−", "-")
    # 保留百分号、符号和小数点，不让 25%、25ms 或负值变成同一个键。
    return re.sub(r"[^\w%+.\-]+", "", text).replace("_", "")


# 向前管到当前小句的否定。单字「无 / 非」和「排除」不在这里，避免「无线」「排除故障」。
_FORWARD = re.compile(
    r"没有|尚无|并无|不是|不属|否认|并未|并非|未(?![来知])|\b(?:not|no|without|never)\b",
    re.I,
)
# 紧贴要点之后，或紧挨逗号的下一小句，才算否定该要点。
_AFTER = re.compile(r"^(?:已|被|并|所)?(?:排除|否认)|^(?:并)?(?:不是|不属)|^(?:没有|并未|并非)")


def _folded(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold().replace("−", "-")


def _kept_indexes(folded: str) -> list[int]:
    return [
        i
        for i, ch in enumerate(folded)
        if ch != "_" and re.fullmatch(r"[\w%+.\-]", ch)
    ]


def _tight_before(before: str) -> bool:
    compact = re.sub(r"\s+", "", before)
    if compact.endswith("排除") or compact.endswith("否认"):
        return True
    if compact.endswith(("无", "非")):
        prev = compact[-2:-1]
        return not prev or re.fullmatch(r"[\w]", prev) is None
    return False


def _negated(text: str, start: int, end: int) -> bool:
    """否定只覆盖紧贴要点的词，以及要点之后、逗号之后的同一小句。"""
    ranges, cursor = [], 0
    for mark in re.finditer(r"[，,、]", text):
        ranges.append((cursor, mark.start()))
        cursor = mark.end()
    ranges.append((cursor, len(text)))
    for i, (left, right) in enumerate(ranges):
        if not (left <= start < right):
            continue
        before, after = text[left:start], text[end:right]
        if _FORWARD.search(before) or _tight_before(before):
            return True
        if _AFTER.match(re.sub(r"[\s，,、]+", "", after)):
            return True
        if re.search(r"\b(?:not|no|without|never)\b", after, re.I):
            return True
        if i + 1 < len(ranges):
            nxt = re.sub(r"\s+", "", text[ranges[i + 1][0] : ranges[i + 1][1]])
            if _AFTER.match(nxt):
                return True
        return False
    return False


def _spans(folded: str, phrase: str):
    """英文词边界在去掉空格之前判断。返回 (原文起、止、规范化起点)。"""
    if re.search(r"[a-z]", phrase, re.I):
        term = _folded(phrase).strip()
        pattern = r"\s*".join(re.escape(p) for p in term.split())
        if re.match(r"[a-z0-9_]", term):
            pattern = r"(?<![a-z0-9_])" + pattern
        if re.search(r"[a-z0-9_]$", term):
            pattern += r"(?![a-z0-9_])"
        idxs = _kept_indexes(folded)
        return [
            (m.start(), m.end(), sum(1 for i in idxs if i < m.start()))
            for m in re.finditer(pattern, folded)
        ]
    needle = normalized(phrase)
    if not needle:
        return []
    norm, idxs = normalized(folded), _kept_indexes(folded)
    spans = []
    for m in re.finditer(re.escape(needle), norm):
        if (
            needle[0].isdigit()
            and m.start()
            and norm[m.start() - 1] in "0123456789.+-"
        ):
            continue
        if needle[-1].isdigit() and m.end() < len(norm) and norm[m.end()] in "0123456789.":
            continue
        spans.append((idxs[m.start()], idxs[m.end() - 1] + 1, m.start()))
    return spans


def positions(text, phrase):
    """局部否定、数值单位与英文标识边界优先；模糊改写留待判定。"""
    out, offset = [], 0
    for sentence in re.split(r"[。；;\n]", text):
        folded = _folded(sentence)
        for start, end, norm_start in _spans(folded, phrase):
            if not _negated(folded, start, end):
                out.append(offset + norm_start)
        offset += len(normalized(sentence)) + 1
    return out


def matches_points(text, points):
    return all(any(positions(text, p) for p in point.any_of) for point in points)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Source(Model):
    id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")
    kind: Literal["formal_report", "closure_note", "final_email"]
    path: Path
    format: Literal["text", "docx", "pdf", "email_html", "email_eml"]
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("path")
    @classmethod
    def absolute_path(cls, value):
        value = value.expanduser()
        if not value.is_absolute():
            raise ValueError("参考路径必须是绝对路径")
        return value.resolve()

    author: str = Field(min_length=1)
    recorded_at: str | None = None
    audit: Literal["audited", "unaudited", "unknown"] = "unknown"
    reviewer: str | None = None
    reviewed_at: str | None = None
    audit_quote: str | None = None

    @model_validator(mode="after")
    def audit_evidence(self):
        if self.audit == "audited" and not (
            self.reviewer and self.reviewed_at and self.audit_quote
        ):
            raise ValueError("已审核必须提供审核人、时间及原文依据")
        return self

    human_basis: str = Field(
        min_length=8, description="为何认定为人工最终结论；创建者不证明人工审核"
    )
    anchor: EvidenceAnchor | None = None


class Support(Model):
    anchor: EvidenceAnchor
    quote: str = Field(min_length=2)
    time_kind: TimeKind | None = None


class Fact(Model):
    element: ElementName
    source_id: str
    quote: str = Field(min_length=2)
    block_id: str | None = None
    key_points: list[KeyPoint] = Field(default_factory=list)
    expected_time: GoldTime | None = None
    time_kind: TimeKind | None = None
    time_precision: Literal["second", "minute"] = "second"
    support: list[Support] = Field(default_factory=list)
    allowed_statuses: list[ElementStatus] = Field(
        default_factory=lambda: [ElementStatus.DOCUMENTED, ElementStatus.CONFIRMED],
        min_length=1,
    )
    value_kind: str | None = None
    conflict: bool = False
    # 明确反义或互斥值必须提前标注；普通未命中不当作错误。
    contradicts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def coherent(self):
        if self.element in {ElementName.START_TIME, ElementName.END_TIME}:
            if self.expected_time is None or self.time_kind is None or self.key_points:
                raise ValueError("时间参考必须有值、时间语义，不能用文本要点")
        elif (
            not self.key_points
            or self.expected_time is not None
            or self.time_kind is not None
        ):
            raise ValueError("文本参考必须有要点，不能有时间值")
        if not set(self.allowed_statuses) <= {
            ElementStatus.DOCUMENTED,
            ElementStatus.CONFIRMED,
        }:
            raise ValueError("有参考事实不能允许 unknown/conflicted 结论值")
        from ..schema.gold import CANDIDATE_KINDS

        value_kinds = {
            ElementName.CAUSE: {
                "root_cause_claimed",
                "root_cause_confirmed",
                "planned_work",
            },
            ElementName.RESPONSIBLE_PARTY: {"claimed", "formal_determination"},
            ElementName.LOCATION: {"located_fault_point"},
        }
        if self.value_kind is not None and (
            self.value_kind not in CANDIDATE_KINDS
            or self.value_kind not in value_kinds.get(self.element, set())
        ):
            raise ValueError("未知的参考结论语义类别")
        if any(not normalized(s) for p in self.key_points for s in p.any_of):
            raise ValueError("同义词不能是空白或标点")
        return self


class FieldProof(Model):
    key: str
    support: Support


class IndependentEmailInput(Model):
    """来源审查后声明的截止前邮件；prepare 仍核验时间、归属与正文。"""

    log_seq: int = Field(gt=0)
    material_id: str
    quote: str = Field(min_length=12)
    provenance: str = Field(min_length=12)


class SelectionCase(Model):
    alias: str = Field(pattern=r"^E[0-9]{2,}$")
    bundle: Path

    @field_validator("bundle")
    @classmethod
    def absolute_bundle(cls, value):
        value = value.expanduser()
        if not value.is_absolute():
            raise ValueError("原包路径必须是绝对路径")
        return value.resolve()

    sources: list[Source] = Field(min_length=1)
    facts: list[Fact] = Field(min_length=1)
    field_proofs: list[FieldProof] = Field(default_factory=list)
    # 无法从原始结构确认材料归属时，不接受仅凭操作者填入的时间。
    excluded_materials: list[str] = Field(default_factory=list)
    independent_emails: list[IndependentEmailInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self):
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)) or any(f.source_id not in ids for f in self.facts):
            raise ValueError("参考来源编号重复或事实引用了不存在的来源")
        keys = [(f.element, f.source_id, f.quote, f.block_id) for f in self.facts]
        if len(set(keys)) != len(keys):
            raise ValueError("同一来源事实不能重复计分")
        proofs = [(p.log_seq, p.material_id) for p in self.independent_emails]
        if len(set(proofs)) != len(proofs):
            raise ValueError("独立邮件输入依据重复")
        return self


class Selection(Model):
    cases: list[SelectionCase] = Field(min_length=1, max_length=20)
    notes: str = ""

    @model_validator(mode="after")
    def unique(self):
        if len({c.alias for c in self.cases}) != len(self.cases):
            raise ValueError("样本代号重复")
        if len({c.bundle.resolve() for c in self.cases}) != len(self.cases):
            raise ValueError("同一原包不能重复计样本")
        return self


def read_source(source: Source) -> dict[str, str]:
    """只用本地解析器，不请求邮件内链接。返回定位块，保留部分解析的边界。"""
    path = source.path.expanduser().resolve()
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("参考原件超过本地解析上限")
    if digest(path) != source.sha256:
        raise ValueError("参考原件哈希不符")
    if source.format == "text":
        return {"text": path.read_text(encoding="utf-8")}
    m = ManifestMaterial(
        id="M99",
        kind=source.format,
        path=path.name,
        sha256=source.sha256,
        size_bytes=path.stat().st_size,
        media_type="application/octet-stream",
    )
    bundle = SimpleNamespace(
        path_of=lambda _: path,
        manifest=SimpleNamespace(default_timezone="+08:00", data_class="real"),
    )
    output = default_registry().parse(ParseContext(bundle, m))
    if output.status in {"failed", "unsupported"}:
        raise ValueError("参考文档解析失败")
    return {s.id: s.text for s in output.spans if not s.needs_review}


def verify_sources(case: SelectionCase, bundle) -> dict[str, dict[str, str]]:
    from ..parsers import ParseContext, default_registry

    blocks = {}
    registry = default_registry()
    for source in case.sources:
        data = read_source(source)
        if source.anchor:
            m = bundle.manifest.material(source.anchor.material_id)
            output = registry.parse(ParseContext(bundle, m))
            if output.status not in {"parsed", "needs_review"}:
                raise ValueError("参考锚点未可靠解析")
            spans = output.spans
            text = "\n".join(
                s.text for s in spans if source.anchor.matches(s) and not s.needs_review
            )
            # 本机转录文件不可凭空增加结论。
            if not data or not all(
                text.strip() and normalized(t) in normalized(text)
                for t in data.values()
                if t.strip()
            ):
                raise ValueError("参考转录与原包锚点不一致")
        if source.audit_quote and source.audit_quote not in "\n".join(data.values()):
            raise ValueError("审核依据不在参考原件中")
        blocks[source.id] = data
    for fact in case.facts:
        data = blocks[fact.source_id]
        text = (
            data.get(fact.block_id, "") if fact.block_id else "\n".join(data.values())
        )
        if fact.quote not in text:
            raise ValueError("参考引文不在指定原文块中")
        if fact.key_points and not matches_points(fact.quote, fact.key_points):
            raise ValueError("参考要点必须至少有一个写法能在引文中核对")
        if fact.expected_time:
            # 时间的 ISO 必须可从引文核验，不能只相信标注者填入的值。
            if not any(
                fact.expected_time.matches(t)
                for t in times_in_quote(fact.quote, bundle.manifest.default_timezone)
            ):
                raise ValueError("参考时间无法从引文核验")
    return blocks


def times_in_quote(text: str, offset: str | None):
    from ..timeparse import parse_time

    pattern = r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}[ T]+\d{1,2}:\d{2}(?::\d{2})?(?:\s*\(?(?:(?:GMT|UTC)(?:[+-]\d{1,2}(?::\d{2})?)?|[+-]\d{2}:?\d{2}|Z)\)?)?"
    return [parse_time(m.group(), offset) for m in re.finditer(pattern, text, re.I)]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
