"""数据外发闸门（ARCHITECTURE_OPTIONS §5.2）。

A1 的文本模型、A2 的视觉模型和 OCR 都要过这一道检查，所以放在 A0 统一定义：
- 每个工单包带数据分级（synthetic / real）；
- 每个服务提供方声明 allowed_data；外部服务要放行 real 数据，必须写明批准依据（approval_ref）；
- 调用前 ensure_allowed() 检查，不通过直接抛 EgressBlocked。没有“临时绕过”开关。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from ..schema.common import DataClass, Model


class ProviderKind(StrEnum):
    RULES = "rules"  # 纯规则基线，不调用任何模型
    REPLAY = "replay"  # 读取录制好的响应
    LOCAL = "local"  # 本机模型/OCR
    OPENAI_COMPATIBLE = "openai_compatible"  # 兼容 OpenAI 接口的服务（公司内网或外部，如 MiniMax）


class ProviderConfig(Model):
    name: str
    kind: ProviderKind
    external: bool = Field(description="数据是否会离开本机")
    allowed_data: list[DataClass] = Field(default_factory=lambda: [DataClass.SYNTHETIC])
    approval_ref: str | None = Field(
        default=None, description="外部服务放行真实数据的批准依据，如 docs/decisions/00xx-*.md"
    )

    @model_validator(mode="after")
    def _check(self) -> ProviderConfig:
        if self.external and self.kind in (ProviderKind.RULES, ProviderKind.REPLAY):
            raise ValueError("rules / replay 不访问网络，不能声明为 external")
        if self.external and DataClass.REAL in self.allowed_data and not self.approval_ref:
            raise ValueError(f"外部服务 {self.name} 放行真实数据必须填写 approval_ref（批准依据）")
        return self


class EgressBlocked(PermissionError):
    pass


def ensure_allowed(provider: ProviderConfig, data_class: DataClass) -> None:
    """在把任何材料交给 provider 之前调用。"""
    if data_class not in provider.allowed_data:
        raise EgressBlocked(
            f"禁止把 {data_class} 数据交给 {provider.name}"
            f"（{'外部' if provider.external else '本机'}服务，允许范围 {[d.value for d in provider.allowed_data]}）"
        )
