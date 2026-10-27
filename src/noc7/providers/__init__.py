"""模型与 OCR 提供方。A0 只定义外发闸门；TextLLM 由 A1 定义，VisionLLM / OCRLayout 由 A2 定义。"""

from .gate import EgressBlocked, ProviderConfig, ProviderKind, ensure_allowed

__all__ = ["EgressBlocked", "ProviderConfig", "ProviderKind", "ensure_allowed"]
