"""统一文本模型配置；配置文件不接收密钥值。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, model_validator

from ..schema.common import DataClass, Model
from .gate import ProviderConfig, ProviderKind

APPROVAL_REF = "docs/decisions/llm-text-providers.md"


class TextProviderError(ValueError):
    """可直接展示的错误，不携带远端正文、凭据或底层异常。"""


class TextModelConfig(Model):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Literal["deepseek", "qwen"]
    base_url: str = Field(min_length=1)
    model: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
    api_key_env: str | None = Field(default=None, pattern=r"^[A-Z_][A-Z0-9_]*$")
    external: bool
    allowed_data: tuple[DataClass, ...] = (DataClass.SYNTHETIC,)
    approval_ref: str | None = None
    json_mode: bool = True
    thinking_mode: Literal["enabled", "disabled"] | None = None
    max_request_bytes: int = Field(ge=1024, le=32 * 1024 * 1024)
    max_tokens: int = Field(ge=1, le=131072)
    max_response_bytes: int = Field(default=4 * 1024 * 1024, ge=1024, le=32 * 1024 * 1024)
    timeout_seconds: float = Field(default=90, gt=0, le=300, allow_inf_nan=False)
    max_retries: int = Field(default=2, ge=0, le=2)

    @model_validator(mode="after")
    def _validate_service(self):
        url = urlsplit(self.base_url)
        if (
            url.scheme not in {"https", "http"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or "?" in self.base_url
            or "#" in self.base_url
            or any(c.isspace() or ord(c) < 32 for c in self.base_url)
        ):
            raise ValueError("模型地址必须是无凭据、无查询参数的 HTTP(S) 基址")
        port = url.port  # 同时校验端口格式。
        if url.path.rstrip("/").endswith("/chat/completions"):
            raise ValueError("请填写基址，不包含 /chat/completions")
        if not self.allowed_data:
            raise ValueError("allowed_data 不能为空")
        if self.name == "deepseek":
            if (
                not self.external
                or url.scheme != "https"
                or url.hostname != "api.deepseek.com"
                or port not in {None, 443}
                or url.path.rstrip("/") not in {"", "/v1"}
                or self.api_key_env != "DEEPSEEK_API_KEY"
            ):
                raise ValueError("DeepSeek 必须使用官方 HTTPS 端点和 DEEPSEEK_API_KEY")
            if DataClass.REAL in self.allowed_data and self.approval_ref != APPROVAL_REF:
                raise ValueError("DeepSeek 真实文本必须引用本项目的批准决策")
        elif self.external or url.hostname == "api.deepseek.com":
            raise ValueError("Qwen 配置仅用于已核实的内网服务")
        self.gate_config()  # 复用共享闸门的配置约束。
        return self

    def gate_config(self) -> ProviderConfig:
        return ProviderConfig(
            name=self.name,
            kind=ProviderKind.OPENAI_COMPATIBLE,
            external=self.external,
            allowed_data=list(self.allowed_data),
            approval_ref=self.approval_ref,
        )

    @property
    def fingerprint(self) -> str:
        raw = json.dumps(self.model_dump(mode="json"), sort_keys=True).encode()
        return hashlib.sha256(raw).hexdigest()[:12]


def load_model_config(path: Path | str) -> TextModelConfig:
    try:
        return TextModelConfig.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        # Pydantic 异常可能回显配置里的误填密钥，不能直接打印。
        raise TextProviderError("无法读取模型配置或配置不完整，请检查配置字段；不要填写密钥值。") from None


def create_text_provider(path: Path | str, *, audit_dir: Path | None = None):
    from .text_http import OpenAICompatibleTextProvider

    return OpenAICompatibleTextProvider(load_model_config(path), audit_dir=audit_dir)
