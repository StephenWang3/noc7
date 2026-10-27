"""附件 OCR / 视觉接口；原点统一为图片左上角，坐标单位为像素。"""

from .base import LayoutBlock, LayoutResult, OCRLayout, VisionLLM, VisualRegion, ImageObservation
from .local import RapidOCRLayout, TesseractLayout

__all__ = ["LayoutBlock", "LayoutResult", "OCRLayout", "VisionLLM", "VisualRegion",
           "ImageObservation", "RapidOCRLayout", "TesseractLayout"]
