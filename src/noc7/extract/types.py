"""提供方内部输出；最终仍输出 A0 的 AnalysisResult。"""

from dataclasses import dataclass
from typing import Protocol

from ..schema.relations import SemanticAssessment
from ..schema.narrative import ReportNarrative

from pydantic import Field

from ..bundle import Bundle
from ..quote_match import QuoteCheck
from ..schema import BusinessSuggestion, Event, EvidenceSpan, ServiceIdentity, SevenElements
from ..schema.common import Model

QUALITY_REVIEW_THRESHOLD = 0.7  # 本地保守阈值，依据与代价见决策 0005。


class EvidenceQuote(Model):
    evidence_id: str
    quote: str = Field(min_length=1)


class Extraction(Model):
    semantic_assessment: SemanticAssessment | None = None
    narrative: ReportNarrative | None = None
    suggestions: list[BusinessSuggestion] = Field(default_factory=list)
    quote_checks: list[QuoteCheck] = Field(default_factory=list)
    elements: SevenElements
    events: list[Event] = Field(default_factory=list)
    service_identity: ServiceIdentity | None = None
    quotes: list[EvidenceQuote] = Field(default_factory=list)


@dataclass(frozen=True)
class ExtractionContext:
    bundle: Bundle
    evidence: list[EvidenceSpan]


class TextProvider(Protocol):
    name: str

    def extract(self, ctx: ExtractionContext) -> Extraction: ...
