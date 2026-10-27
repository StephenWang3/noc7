"""A2 自动注册入口，与 A1 只通过 EvidenceSpan 交换数据。"""
from ...ocr import RapidOCRLayout
from ..base import UnsupportedParser
from ...schema.evidence import MaterialKind
from .docx import DOCXParser
from .eml import EMLParser
from .image import ImageParser
from .pdf import PDFParser

_ocr = RapidOCRLayout()


class OtherParser(UnsupportedParser):
    name = "a2.other@0.1"
    kinds = frozenset({MaterialKind.OTHER})


PARSERS = [ImageParser(ocr=_ocr), PDFParser(ocr=_ocr), DOCXParser(), EMLParser(), OtherParser()]
