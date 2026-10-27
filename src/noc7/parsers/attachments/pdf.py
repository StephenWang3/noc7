from __future__ import annotations

from PIL import Image
import pymupdf

from ...ocr import RapidOCRLayout
from ...providers.attachment_models import read_layout
from ...schema.evidence import MaterialKind, PageLocator, SpanRole, TableReading
from ...schema.issues import IssueCode
from ..base import ParseContext
from .common import QUALITY_THRESHOLD, finish, issue, read_limited, span


class PDFParser:
    name = "a2.pdf@0.1"
    kinds = frozenset({MaterialKind.PDF})

    def __init__(self, ocr=None):
        self.ocr = ocr if ocr is not None else RapidOCRLayout()

    def parse(self, ctx: ParseContext):
        spans, issues = [], []
        review = False
        with pymupdf.open(stream=read_limited(ctx), filetype="pdf") as doc:
            if doc.needs_pass:
                raise ValueError("PDF 已加密，需要在本地解密后重新导入")
            if len(doc) > 100:
                raise ValueError("PDF 超过 100 页本地解析上限")
            for index, page in enumerate(doc):
                p = index + 1
                if page.rect.width * page.rect.height * (150 / 72) ** 2 > 25_000_000:
                    raise ValueError(f"PDF 第 {p} 页渲染尺寸超过上限")
                blocks = [b for b in page.get_text("blocks", sort=True) if b[6] == 0 and b[4].strip()]
                for i, b in enumerate(blocks):
                    spans.append(span(ctx, f"p{p}:b{i}", b[4].strip(), PageLocator(page=p, bbox=tuple(b[:4])), self.name))
                # 即使有少量文本层（如页码），含栅格图的页面也补 OCR，避免漏掉扫描正文。
                needs_ocr = not blocks or bool(page.get_images())
                if needs_ocr:
                    pix = page.get_pixmap(dpi=150, colorspace=pymupdf.csRGB, alpha=False)
                    image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                    try:
                        layout = read_layout(self.ocr, image, ctx.bundle.manifest.data_class)
                        count = 0
                        # 用实际 pixmap 尺寸反投影到可见 PDF 页坐标（单位 pt）。
                        sx, sy = page.rect.width / pix.width, page.rect.height / pix.height
                        for i, b in enumerate(layout.blocks):
                            rendered = pymupdf.Rect(b.bbox[0] * sx, b.bbox[1] * sy, b.bbox[2] * sx, b.bbox[3] * sy)
                            bbox = tuple(rendered * page.derotation_matrix)
                            # 文本层已覆盖的内容不重复当成独立来源。
                            if any(b.text.strip() in text[4] and pymupdf.Rect(bbox).intersects(pymupdf.Rect(text[:4])) for text in blocks):
                                continue
                            count += 1
                            spans.append(span(ctx, f"p{p}:ocr:{i}", b.text, PageLocator(page=p, bbox=bbox), self.ocr.name,
                                              role=SpanRole.OCR_TEXT, quality=b.quality,
                                              needs_review=b.quality < QUALITY_THRESHOLD))
                        if not count and not blocks:
                            review = True
                            issues.append(issue(IssueCode.MATERIAL_LOW_QUALITY, f"PDF 第 {p} 页未识别到文字，可能为空白或扫描质量不足"))
                        if blocks and page.get_images():
                            review = True  # 图像区域可能还包含无法由 OCR 表达的照片/曲线。
                    except Exception as exc:
                        review = True
                        issues.append(issue(IssueCode.MATERIAL_PARSE_FAILED, f"PDF 第 {p} 页 OCR 失败：{type(exc).__name__}，其他页证据已保留"))
                try:
                    tables = page.find_tables().tables
                    for i, table in enumerate(tables):
                        matrix = [[cell or "" for cell in row] for row in table.extract()]
                        if matrix:
                            spans.append(span(ctx, f"p{p}:tbl:{i}", "\n".join(" | ".join(row) for row in matrix),
                                              PageLocator(page=p, bbox=tuple(table.bbox)), self.name,
                                              reading=TableReading(headers=matrix[0], rows=matrix[1:])))
                except Exception as exc:
                    review = True
                    issues.append(issue(IssueCode.MATERIAL_PARSE_FAILED, f"PDF 第 {p} 页表格检测失败：{type(exc).__name__}"))
        return finish(ctx, self.name, spans, issues=issues, review=review,
                      note="页码从 1 起，bbox 为 PDF 页坐标 pt；扫描/OCR 不能证明照片内容。")
