"""noc7 的数据契约。A1、A2、A3、A4 之间只通过这里定义的结构交换数据。"""

from .analysis import AnalysisResult, Event, IdentityStatus, RunInfo, ServiceIdentifier, ServiceIdentity
from .bundle import (
    KNOWN_FIELD_KEYS,
    BundleManifest,
    BundleSource,
    LogEntryKind,
    ProcessLog,
    ProcessLogEntry,
    RelatedTicket,
    RelationKind,
    StatusView,
    TicketFamily,
    TicketField,
    TicketRecord,
)
from .common import (
    ATTRIBUTION_LABELS_ZH,
    ELEMENT_LABELS_ZH,
    Attribution,
    DataClass,
    ElementName,
    ElementStatus,
    material_of,
)
from .narrative import NarrativeLine, ReportNarrative
from .elements import (
    CAUSE_KINDS_ALLOWED_AS_VALUE,
    CauseCandidate,
    CauseElement,
    CauseKind,
    HandlingProcessElement,
    LocationCandidate,
    LocationElement,
    LocationGranularity,
    LocationRole,
    Observation,
    PartyCandidate,
    PhenomenonElement,
    ProcessStep,
    ResponsibilityBasis,
    ResponsiblePartyElement,
    ReviewAction,
    ReviewInfo,
    SevenElements,
    StepKind,
    TimeCandidate,
    TimeElement,
)
from .evidence import (
    ChartReading,
    ChartSeriesStat,
    DocBlockLocator,
    EmailMessageLocator,
    EvidenceSpan,
    FieldLocator,
    ImageRegionLocator,
    ImageSubtype,
    LogEntryLocator,
    ManifestMaterial,
    Material,
    MaterialKind,
    MaterialOrigin,
    PageLocator,
    ParseStatus,
    SpanRole,
    TableReading,
    TextRangeLocator,
)
from .gold import EvidenceAnchor, GoldAnswer, GoldCandidate, GoldElement, GoldIssue, GoldTime, KeyPoint
from .issues import DEFAULT_SEVERITY, IssueCode, Severity, ValidationIssue
from .timeval import TimeKind, TimePrecision, TimeValue, TimeZoneSource

from .suggestions import BusinessSuggestion

__all__ = [name for name in dir() if not name.startswith("_")]
