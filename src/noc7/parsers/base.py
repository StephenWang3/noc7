"""解析器接口：文本线（A1）与附件线（A2）并行开发的接缝。

约定（详见 docs/CONTRACTS.md）：
1. 每种材料类型只归一条开发线负责，见 PARSER_OWNERSHIP；注册时同一类型重复注册直接报错。
2. 解析器输入一份材料，输出 ParseOutput：状态 + 证据片段 + 问题。不读其他材料，不调用其他解析器。
3. 证据编号必须以本材料编号开头（M03/...），局部编号由解析器自定，同一输入多次解析必须得到相同编号。
4. 解析失败返回 FAILED 状态和 MATERIAL_PARSE_FAILED 问题，不抛异常拖垮整单。
5. 还没实现的类型由 UnsupportedParser 兜底：明确报“不支持/待实现”，任务显示“材料不完整”。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import Field, model_validator

from ..bundle import Bundle
from ..schema.common import MaterialId, Model
from ..schema.evidence import EvidenceSpan, ImageSubtype, ManifestMaterial, MaterialKind, ParseStatus
from ..schema.issues import DEFAULT_SEVERITY, IssueCode, ValidationIssue

# 材料类型归属：A1 文本链路 / A2 附件处理
PARSER_OWNERSHIP: dict[MaterialKind, str] = {
    MaterialKind.TICKET_FIELDS: "A1",
    MaterialKind.PROCESS_LOG: "A1",
    MaterialKind.EMAIL_HTML: "A1",
    MaterialKind.TEXT: "A1",
    MaterialKind.IMAGE: "A2",
    MaterialKind.PDF: "A2",
    MaterialKind.DOCX: "A2",
    MaterialKind.EMAIL_EML: "A2",
    MaterialKind.OTHER: "A2",
}


@dataclass(frozen=True)
class ParseContext:
    bundle: Bundle
    material: ManifestMaterial

    @property
    def default_offset(self) -> str | None:
        return self.bundle.manifest.default_timezone

    def read_bytes(self) -> bytes:
        return self.bundle.path_of(self.material).read_bytes()


class ParseOutput(Model):
    material_id: MaterialId
    parser: str = Field(description="解析器名称及版本，如 'a2.image@0.1'")
    status: ParseStatus
    subtype: ImageSubtype | None = None
    spans: list[EvidenceSpan] = Field(default_factory=list)
    issues: list[ValidationIssue] = Field(default_factory=list)
    note: str | None = None

    @model_validator(mode="after")
    def _own_material_only(self) -> ParseOutput:
        ids = [s.id for s in self.spans]
        if len(ids) != len(set(ids)):
            raise ValueError("同一材料内证据编号重复")
        foreign = [s.id for s in self.spans if s.material_id != self.material_id]
        if foreign:
            raise ValueError(f"解析器只能产出本材料的证据片段，越界: {foreign}")
        if self.status is ParseStatus.PARSED and not self.spans:
            raise ValueError("状态为 parsed 却没有任何证据片段")
        return self


@runtime_checkable
class Parser(Protocol):
    name: str
    kinds: frozenset[MaterialKind]

    def parse(self, ctx: ParseContext) -> ParseOutput: ...


class UnsupportedParser:
    """兜底解析器：对尚未实现或不支持的类型明确报出，而不是静默跳过。"""

    name = "a0.unsupported@0.1"
    kinds: frozenset[MaterialKind] = frozenset(MaterialKind)

    def parse(self, ctx: ParseContext) -> ParseOutput:
        m = ctx.material
        return ParseOutput(
            material_id=m.id,
            parser=self.name,
            status=ParseStatus.UNSUPPORTED,
            issues=[
                ValidationIssue(
                    code=IssueCode.MATERIAL_UNSUPPORTED,
                    severity=DEFAULT_SEVERITY[IssueCode.MATERIAL_UNSUPPORTED],
                    message=f"材料 {m.id}（{m.kind}，{m.path}）暂无可用解析器，相关要素可能不完整",
                )
            ],
        )


class ParserRegistry:
    def __init__(self) -> None:
        self._by_kind: dict[MaterialKind, Parser] = {}
        self._fallback = UnsupportedParser()

    def register(self, parser: Parser) -> None:
        for kind in parser.kinds:
            if kind in self._by_kind:
                raise ValueError(f"材料类型 {kind} 已由 {self._by_kind[kind].name} 负责，不能重复注册")
        for kind in parser.kinds:
            self._by_kind[kind] = parser

    def for_kind(self, kind: MaterialKind) -> Parser:
        return self._by_kind.get(kind, self._fallback)

    def parse(self, ctx: ParseContext) -> ParseOutput:
        """调用解析器；解析器抛出的异常转成 FAILED，不影响同一工单的其他材料。"""
        parser = self.for_kind(ctx.material.kind)
        try:
            out = parser.parse(ctx)
        except Exception as e:  # noqa: BLE001 —— 单个材料失败不能拖垮整单
            return ParseOutput(
                material_id=ctx.material.id,
                parser=parser.name,
                status=ParseStatus.FAILED,
                issues=[
                    ValidationIssue(
                        code=IssueCode.MATERIAL_PARSE_FAILED,
                        severity=DEFAULT_SEVERITY[IssueCode.MATERIAL_PARSE_FAILED],
                        message=f"材料 {ctx.material.id} 解析失败：{type(e).__name__}: {e}",
                    )
                ],
            )
        if out.material_id != ctx.material.id:
            raise ValueError(f"{parser.name} 返回了错误的材料编号 {out.material_id}")
        return out
