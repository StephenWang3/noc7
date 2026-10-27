from __future__ import annotations

from typing import Protocol

from PIL import Image
from pydantic import Field, model_validator

from ..providers import ProviderConfig
from ..schema.common import DataClass, Model
from ..schema.evidence import ImageSubtype, Reading


class LayoutBlock(Model):
    text: str
    bbox: tuple[int, int, int, int]
    quality: float = Field(ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def _box(self):
        x0, y0, x1, y1 = self.bbox
        if not (0 <= x0 < x1 and 0 <= y0 < y1):
            raise ValueError("区域必须是左上原点的有效像素矩形")
        return self


class LayoutResult(Model):
    blocks: list[LayoutBlock] = Field(default_factory=list)


class VisualRegion(LayoutBlock):
    reading: Reading | None = None
    needs_review: bool = True


class ImageObservation(Model):
    subtype: ImageSubtype
    regions: list[VisualRegion] = Field(default_factory=list)


class OCRLayout(Protocol):
    config: ProviderConfig
    name: str

    def read(self, image: Image.Image, data_class: DataClass) -> LayoutResult: ...


class VisionLLM(Protocol):
    config: ProviderConfig
    name: str

    def describe(self, image: Image.Image, data_class: DataClass) -> ImageObservation: ...
