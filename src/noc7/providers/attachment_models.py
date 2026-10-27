"""A2 提供方边界：本地、回放、外部 OCR/视觉都先检查外发策略。"""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image

from ..ocr.base import ImageObservation, LayoutResult
from ..schema.common import DataClass
from ..schema.evidence import ChartReading
from .gate import EgressBlocked, ProviderConfig, ProviderKind, ensure_allowed


def ensure_attachment_allowed(config: ProviderConfig, data_class: DataClass) -> None:
    ensure_allowed(config, data_class)
    # 当前用户决定比 A0 通用配置更严格：即使填了 approval_ref，真实附件也一律不外发。
    if config.external and DataClass(data_class) is DataClass.REAL:
        raise EgressBlocked("当前项目禁止向外部服务发送真实附件")


def _bounds(blocks, image: Image.Image) -> None:
    if any(b.bbox[2] > image.width or b.bbox[3] > image.height for b in blocks):
        raise ValueError("提供方返回的区域超出图片边界")
    for block in blocks:
        reading = getattr(block, "reading", None)
        if isinstance(reading, ChartReading):
            names = [s.series for s in reading.series]
            if len(names) != len(set(names)):
                raise ValueError("曲线类别重复")
            for series in reading.series:
                values = [v for v in (series.min, series.avg, series.max) if v is not None]
                if any(not math.isfinite(v) for v in values) or values != sorted(values):
                    raise ValueError("曲线统计不满足 min <= avg <= max 或包含非有限数值")
                if reading.unit == "%" and any(not 0 <= v <= 100 for v in values):
                    raise ValueError("百分比读数超出 0 到 100")


def read_layout(provider, image: Image.Image, data_class: DataClass) -> LayoutResult:
    ensure_attachment_allowed(provider.config, data_class)
    result = LayoutResult.model_validate(provider.read(image, data_class))
    _bounds(result.blocks, image)
    return result


def describe_image(provider, image: Image.Image, data_class: DataClass) -> ImageObservation:
    ensure_attachment_allowed(provider.config, data_class)
    result = ImageObservation.model_validate(provider.describe(image, data_class))
    _bounds(result.regions, image)
    return result


def image_digest(image: Image.Image) -> str:
    rgb = image.convert("RGB")
    return hashlib.sha256(f"{rgb.width}x{rgb.height}:RGB:".encode() + rgb.tobytes()).hexdigest()


class ReplayAttachmentProvider:
    """按像素哈希命中，不根据文件名或工单编号猜响应；缺录制立即报错。"""
    name = "replay.attachment@0.1"

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.config = ProviderConfig(name=self.name, kind=ProviderKind.REPLAY, external=False)

    def _load(self, image: Image.Image, data_class: DataClass, kind: str):
        ensure_attachment_allowed(self.config, data_class)
        return json.loads((self.root / f"{image_digest(image)}.{kind}.json").read_text(encoding="utf-8"))

    def read(self, image: Image.Image, data_class: DataClass) -> LayoutResult:
        return LayoutResult.model_validate(self._load(image, data_class, "ocr"))

    def describe(self, image: Image.Image, data_class: DataClass) -> ImageObservation:
        return ImageObservation.model_validate(self._load(image, data_class, "vision"))


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()
