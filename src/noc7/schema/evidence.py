"""材料与证据片段。

“证据优先”流水线的接缝：所有解析器（文本线 A1、附件线 A2）都只产出 EvidenceSpan，
抽取、校验、报告只消费 EvidenceSpan。两条线之间不需要互相调用。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .common import EvidenceId, FieldKey, MaterialId, Model


class MaterialKind(StrEnum):
    TICKET_FIELDS = "ticket_fields"  # ticket.json：基本信息 + 故障信息字段
    PROCESS_LOG = "process_log"  # process_log.json：处理过程，逐条
    EMAIL_HTML = "email_html"  # 邮件详情页的 HTML 正文
    EMAIL_EML = "email_eml"  # EML 原件
    IMAGE = "image"  # PNG / JPEG
    PDF = "pdf"
    DOCX = "docx"
    TEXT = "text"  # 用户粘贴的纯文本
    OTHER = "other"  # 不支持的格式：必须显式报“不支持”，不能静默漏掉


class ParseStatus(StrEnum):
    PENDING = "pending"
    PARSED = "parsed"
    NEEDS_REVIEW = "needs_review"  # 解析了但质量存疑（低质量 OCR、表格错位）
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class ImageSubtype(StrEnum):
    """图片先分类再理解（ARCHITECTURE_OPTIONS §2.1）。由附件线 A2 判定。"""

    QOS_CHART = "qos_chart"  # 监控曲线
    DOCUMENT_COMPOSITE = "document_composite"  # 文档页面/长图拼接
    SITE_PHOTO = "site_photo"  # 现场照片
    TERMINAL_SCREENSHOT = "terminal_screenshot"  # 终端输出截图
    OTHER = "other"


class MaterialOrigin(Model):
    """材料在源系统中的位置，用于溯源和漏件检查。"""

    log_seq: int | None = Field(default=None, ge=1, description="出自处理过程第几条")
    note: str | None = None


class ManifestMaterial(Model):
    """工单包 manifest.json 里声明的一份材料。"""

    id: MaterialId
    kind: MaterialKind
    path: str = Field(description="相对工单包根目录的路径")
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    media_type: str
    origin: MaterialOrigin | None = None
    derived: bool = Field(default=False, description="是否为衍生材料（如源系统生成的 AI 摘要）")
    derived_from: list[MaterialId] = Field(default_factory=list)
    description: str | None = None

    @model_validator(mode="after")
    def _safe_path(self) -> ManifestMaterial:
        parts = self.path.replace("\\", "/").split("/")
        if self.path.startswith("/") or ".." in parts or self.path == "":
            raise ValueError(f"材料路径必须是工单包内的相对路径: {self.path!r}")
        return self


class Material(ManifestMaterial):
    """分析结果中的材料：在 manifest 声明之上附加解析状态。"""

    parse_status: ParseStatus = ParseStatus.PENDING
    subtype: ImageSubtype | None = None
    parser: str | None = Field(default=None, description="实际使用的解析器，如 'a1.ticket_fields@0.1'")
    parse_note: str | None = None


# ---------------------------------------------------------------------------
# 定位器：说明证据在原材料里的位置。点击任何要素都靠它回到原文。
# ---------------------------------------------------------------------------
class _CharRange(Model):
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _range(self):  # type: ignore[no-untyped-def]
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("char_start 和 char_end 必须同时给出")
        if self.char_start is not None and self.char_end < self.char_start:  # type: ignore[operator]
            raise ValueError("char_end 不能小于 char_start")
        return self


class FieldLocator(_CharRange):
    type: Literal["field"] = "field"
    field_key: FieldKey


class LogEntryLocator(_CharRange):
    type: Literal["log_entry"] = "log_entry"
    seq: int = Field(ge=1)


class EmailMessageLocator(_CharRange):
    """邮件按消息边界切分：0 = 当前消息，1 = 第一层引用，以此类推。"""

    type: Literal["email_message"] = "email_message"
    message_index: int = Field(ge=0)
    part: Literal["header", "body", "table", "signature", "disclaimer"] = "body"


class PageLocator(Model):
    """PDF 页（1 起），可选页内区域（PDF 坐标，单位 pt）。"""

    type: Literal["page"] = "page"
    page: int = Field(ge=1)
    bbox: tuple[float, float, float, float] | None = None


class ImageRegionLocator(Model):
    """图片区域（像素坐标 x0, y0, x1, y1）。bbox 为空表示整张图。"""

    type: Literal["image_region"] = "image_region"
    bbox: tuple[int, int, int, int] | None = None


class DocBlockLocator(Model):
    """DOCX 段落或表格单元格（序号均从 0 起）。"""

    type: Literal["doc_block"] = "doc_block"
    paragraph_index: int | None = Field(default=None, ge=0)
    table_index: int | None = Field(default=None, ge=0)
    row: int | None = Field(default=None, ge=0)
    col: int | None = Field(default=None, ge=0)


class TextRangeLocator(_CharRange):
    """纯文本材料中的字符区间。"""

    type: Literal["text_range"] = "text_range"
    line: int | None = Field(default=None, ge=1)


Locator = Annotated[
    FieldLocator
    | LogEntryLocator
    | EmailMessageLocator
    | PageLocator
    | ImageRegionLocator
    | DocBlockLocator
    | TextRangeLocator,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# 结构化读数：附件和表格里的数值不能只留一段描述文字
# ---------------------------------------------------------------------------
class ChartSeriesStat(Model):
    series: str = Field(description="曲线名称/类别，如 QoS 类别 EF")
    max: float | None = None
    avg: float | None = None
    min: float | None = None
    first_nonzero: str | None = Field(default=None, description="首次出现非零值的横轴原文（如 02:12），不等于起障时间")


class ChartReading(Model):
    """监控曲线读数。图例颜色与曲线的绑定由解析器负责，读数按类别分开保存。"""

    type: Literal["chart"] = "chart"
    metric: str = Field(description="指标，如 丢包率")
    unit: str | None = None
    x_start: str | None = Field(default=None, description="横轴起点原文")
    x_end: str | None = Field(default=None, description="横轴终点原文")
    timezone_shown: bool = Field(default=False, description="图上是否标明时区")
    series: list[ChartSeriesStat] = Field(default_factory=list)


class TableReading(Model):
    """表格读数（邮件里的资源映射表、PDF/DOCX 表格、图片中的表格）。"""

    type: Literal["table"] = "table"
    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


Reading = Annotated[ChartReading | TableReading, Field(discriminator="type")]


class SpanRole(StrEnum):
    ORIGINAL = "original"  # 原文正文
    QUOTED = "quoted"  # 邮件历史引用：与原消息重复时不计为独立证据
    SIGNATURE = "signature"  # 签名、免责声明：保留但不参与抽取
    DERIVED_SUMMARY = "derived_summary"  # AI 摘要等衍生内容：引用原始证据优先
    OCR_TEXT = "ocr_text"  # OCR 得到的文字
    VISUAL_OBSERVATION = "visual_observation"  # 视觉模型对图片的描述/读数


class EvidenceSpan(Model):
    """一段带编号、可定位的证据。

    编号规则 <材料编号>/<局部编号>，局部编号由该材料的解析器决定，建议：
      字段 f:<field_key>；处理过程 log:<seq>；邮件 msg:<i>[:part]；
      PDF p<页>[:b<块>]；图片 img[:r<区域>]；DOCX para:<i> / tbl:<i>:<r>:<c>。
    """

    id: EvidenceId
    material_id: MaterialId
    locator: Locator
    text: str = Field(description="原文；OCR/视觉片段为识别出的文字或描述")
    role: SpanRole = SpanRole.ORIGINAL
    extractor: str = Field(description="产出该片段的解析器及版本，如 'a1.email_html@0.1'")
    quality: float | None = Field(default=None, ge=0, le=1, description="OCR/识图质量分")
    needs_review: bool = False
    derived_from: list[EvidenceId] = Field(default_factory=list)
    reading: Reading | None = None
    language: str | None = None

    @model_validator(mode="after")
    def _id_matches_material(self) -> EvidenceSpan:
        if not self.id.startswith(self.material_id + "/"):
            raise ValueError(f"证据编号 {self.id} 必须以所属材料编号 {self.material_id}/ 开头")
        return self
