"""标准答案（evals/gold/<bundle_id>.json）。

标准答案描述“正确的分析结果应满足什么”，而不是一份完整的 AnalysisResult：
- 证据用“锚点”（材料 + 字段/处理过程序号/邮件消息/页码）表示，不依赖解析器生成的证据编号，
  所以 A1/A2 怎么切片段都不影响标准答案；
- 文本要素用“要点”判分（每个要点给出几种同义写法，命中任一即可），不要求逐字一致；
- 允许的状态可以有多个（例如 documented 或 confirmed 都算对），但 unknown 和有值不会同时允许，
  除非 rationale 写明理由；
- 每个要素写明标注理由，这些理由同时是答辩材料。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import Field, model_validator

from .analysis import IdentityStatus
from .common import Attribution, ElementName, ElementStatus, MaterialId, Model
from .elements import CauseKind, LocationRole, ResponsibilityBasis, StepKind
from .evidence import EvidenceSpan
from .issues import IssueCode
from .timeval import TimeKind, TimeValue, TimeZoneSource

TIME_ELEMENTS = {ElementName.START_TIME, ElementName.END_TIME}
VALUE_STATUSES = {ElementStatus.DOCUMENTED, ElementStatus.CONFIRMED}
CANDIDATE_KINDS = {
    e.value for enum in (TimeKind, CauseKind, LocationRole, ResponsibilityBasis, StepKind, Attribution) for e in enum
}


class EvidenceAnchor(Model):
    material_id: MaterialId
    field_key: str | None = None
    log_seq: int | None = Field(default=None, ge=1)
    message_index: int | None = Field(default=None, ge=0)
    page: int | None = Field(default=None, ge=1)
    note: str | None = Field(default=None, description="图片区域等无法自动比对的位置说明")

    def matches(self, span: EvidenceSpan) -> bool:
        if span.material_id != self.material_id:
            return False
        loc = span.locator
        checks = (
            ("field_key", self.field_key),
            ("seq", self.log_seq),
            ("message_index", self.message_index),
            ("page", self.page),
        )
        for attr, expected in checks:
            if expected is not None and getattr(loc, attr, None) != expected:
                return False
        return True


class GoldTime(Model):
    iso: str = Field(description="带偏移、不带偏移或只有日期，口径同 TimeValue.iso")
    tolerance_minutes: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _parsable(self) -> GoldTime:
        if len(self.iso) == 10:
            date.fromisoformat(self.iso)
        else:
            datetime.fromisoformat(self.iso)
        return self

    def matches(self, value: TimeValue | None) -> bool:
        if value is None or value.iso is None:
            return False
        if len(self.iso) == 10 or len(value.iso) == 10:
            return value.iso[:10] == self.iso[:10]
        got = datetime.fromisoformat(value.iso)
        want = datetime.fromisoformat(self.iso)
        if (got.utcoffset() is None) != (want.utcoffset() is None):
            # 一个有时区一个没有：只比较墙上时间，并由评测另行记一次时区错误
            got, want = got.replace(tzinfo=None), want.replace(tzinfo=None)
        return abs(got - want) <= timedelta(minutes=self.tolerance_minutes)


class KeyPoint(Model):
    any_of: list[str] = Field(min_length=1, description="同义写法，命中任一即算覆盖该要点（不区分大小写）")

    def covered_by(self, text: str | None) -> bool:
        if not text:
            return False
        low = text.lower()
        return any(s.lower() in low for s in self.any_of)


class GoldCandidate(Model):
    """系统必须保留的候选（即使它最终不是结论值）。"""

    kind_in: list[str] = Field(
        min_length=1,
        description="可接受的类别，取值来自 TimeKind / CauseKind / LocationRole / ResponsibilityBasis / StepKind / Attribution",
    )
    time: GoldTime | None = None
    tz_source_in: list[TimeZoneSource] | None = None
    contains_any: list[str] = Field(default_factory=list)
    evidence: list[EvidenceAnchor] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="after")
    def _known_kinds(self) -> GoldCandidate:
        unknown = [k for k in self.kind_in if k not in CANDIDATE_KINDS]
        if unknown:
            raise ValueError(f"未知的候选类别: {unknown}")
        return self


class GoldElement(Model):
    status_in: list[ElementStatus] = Field(min_length=1)
    expected_time: GoldTime | None = None
    key_points: list[KeyPoint] = Field(default_factory=list)
    required_candidates: list[GoldCandidate] = Field(default_factory=list)
    forbidden_values: list[str] = Field(default_factory=list, description="结论值里不得出现的内容")
    evidence: list[EvidenceAnchor] = Field(default_factory=list, description="结论应引用的证据位置（任一）")
    rationale: str = Field(min_length=8, description="标注理由")


class GoldIssue(Model):
    code: IssueCode
    element: ElementName | None = None
    note: str | None = None


class Annotation(Model):
    annotator: str
    annotated_at: str
    method: str


class GoldAnswer(Model):
    gold_version: Literal["1.0"] = "1.0"
    bundle_id: str
    patterns: list[str] = Field(min_length=1, description="对应的调研问题模式（S01…X01）或 PRD 必测用例")
    summary: str
    annotation: Annotation
    elements: dict[ElementName, GoldElement]
    expected_issues: list[GoldIssue] = Field(default_factory=list)
    service_identity: IdentityStatus | None = None
    attachment_dependent: list[ElementName] = Field(
        default_factory=list, description="必须读懂附件才能答全的要素（用于有/无附件对照实验）"
    )
    notes: str | None = None

    @model_validator(mode="after")
    def _check(self) -> GoldAnswer:
        missing = [e.value for e in ElementName if e not in self.elements]
        if missing:
            raise ValueError(f"标准答案缺少要素: {missing}")
        for name, el in self.elements.items():
            expects_value = bool(set(el.status_in) & VALUE_STATUSES)
            if name in TIME_ELEMENTS:
                if el.key_points:
                    raise ValueError(f"{name}: 时间要素用 expected_time，不用 key_points")
                if expects_value and el.expected_time is None:
                    raise ValueError(f"{name}: 允许有值的时间要素必须给 expected_time")
            else:
                if el.expected_time is not None:
                    raise ValueError(f"{name}: 非时间要素不能给 expected_time")
                if expects_value and not el.key_points and name is not ElementName.HANDLING_PROCESS:
                    raise ValueError(f"{name}: 允许有值时必须给 key_points")
            if not expects_value and (el.expected_time or el.key_points):
                raise ValueError(f"{name}: 只允许 unknown/conflicted 时不能给期望值")
        return self
