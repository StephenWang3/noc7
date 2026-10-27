from __future__ import annotations

import io
import zipfile

from docx import Document

from ...schema.evidence import DocBlockLocator, MaterialKind, TableReading
from ...schema.issues import IssueCode
from ..base import ParseContext
from .common import finish, issue, read_limited, span


class DOCXParser:
    name = "a2.docx@0.1"
    kinds = frozenset({MaterialKind.DOCX})

    def parse(self, ctx: ParseContext):
        data = read_limited(ctx)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 5000 or sum(e.file_size for e in entries) > 100 * 1024 * 1024:
                raise ValueError("DOCX 解压尺寸超过本地解析上限")
            embedded = any(e.filename.startswith(("word/media/", "word/embeddings/")) for e in entries)
            # 暂未实现的页眉、文本框、脚注等明确披露，不能无声漏掉。
            extra = any(e.filename.startswith(("word/header", "word/footer", "word/footnotes", "word/endnotes")) for e in entries)
            xml = archive.read("word/document.xml")
            extra = extra or b"txbxContent" in xml
        document = Document(io.BytesIO(data))
        spans, issues = [], []
        for i, paragraph in enumerate(document.paragraphs):
            if paragraph.text.strip():
                spans.append(span(ctx, f"para:{i}", paragraph.text, DocBlockLocator(paragraph_index=i), self.name))
        nested = False
        for i, table in enumerate(document.tables):
            matrix = [[cell.text for cell in row.cells] for row in table.rows]
            for r, row in enumerate(table.rows):
                for c, cell in enumerate(row.cells):
                    nested = nested or bool(cell.tables)
                    if cell.text.strip():
                        spans.append(span(ctx, f"tbl:{i}:{r}:{c}", cell.text,
                                          DocBlockLocator(table_index=i, row=r, col=c), self.name))
            if matrix:
                spans.append(span(ctx, f"tbl:{i}", "\n".join(" | ".join(row) for row in matrix),
                                  DocBlockLocator(table_index=i), self.name,
                                  reading=TableReading(headers=matrix[0], rows=matrix[1:])))
        if embedded or extra or nested:
            issues.append(issue(IssueCode.MATERIAL_UNSUPPORTED,
                                "DOCX 含嵌入图片/对象、页眉页脚/文本框/脚注或嵌套表格，当前只解析顶层正文段落与表格，请复核未覆盖区域"))
        return finish(ctx, self.name, spans, issues=issues, review=embedded or extra or nested,
                      note="段落/表格/行列索引从 0 起；DOCX 无稳定页码，定位使用文档块。")
