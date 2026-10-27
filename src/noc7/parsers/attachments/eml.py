"""EML 在内存拆 MIME；不落地附件、不请求 HTML 里的远程资源。"""
from __future__ import annotations

import re
from email import policy
from email.parser import BytesParser

from bs4 import BeautifulSoup

from ...schema.evidence import EmailMessageLocator, MaterialKind, SpanRole, TableReading
from ...schema.issues import IssueCode
from ..base import ParseContext
from .common import finish, issue, read_limited, span


class EMLParser:
    name = "a2.eml@0.1"
    kinds = frozenset({MaterialKind.EMAIL_EML})

    def parse(self, ctx: ParseContext):
        data = read_limited(ctx)
        issues, spans = [], []
        review = False
        if b"\\r\\n\\r\\n" in data and b"\r\n\r\n" not in data and b"\n\n" not in data:
            data = data.replace(b"\\r\\n", b"\r\n")
            review = True
            issues.append(issue(IssueCode.MATERIAL_LOW_QUALITY, "EML 使用字面量转义换行，兼容解码后读取；原文件未修改，请复核"))
        message = BytesParser(policy=policy.default).parsebytes(data)
        header = "\n".join(f"{key}: {message[key]}" for key in ("From", "To", "Cc", "Subject", "Date", "Message-ID") if message[key])
        if not header:
            raise ValueError("没有可识别邮件头，不是有效 EML")
        spans.append(span(ctx, "msg:0:header", header, EmailMessageLocator(message_index=0, part="header"), self.name))
        # get_body 优先纯文本，避免 multipart/alternative 的 HTML 副本算成另一份证据。
        body = message.get_body(preferencelist=("plain", "html"))
        if body is not None:
            try:
                text = body.get_content()
            except (LookupError, UnicodeError):
                text = body.get_payload(decode=True).decode("utf-8", errors="replace")
                review = True
            if "\ufffd" in text:
                review = True
            if body.get_content_type() == "text/html":
                soup = BeautifulSoup(text, "html.parser")
                for node in soup(["script", "style", "iframe", "object"]):
                    node.decompose()
                for i, table in enumerate(soup.find_all("table")):
                    matrix = [[cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"], recursive=False)]
                              for row in table.find_all("tr")]
                    matrix = [r for r in matrix if r]
                    if matrix:
                        quoted = table.find_parent("blockquote") is not None
                        spans.append(span(ctx, f"msg:0:tbl:{i}", table.get_text(" ", strip=True),
                                          EmailMessageLocator(message_index=0, part="table"), self.name,
                                          role=SpanRole.QUOTED if quoted else SpanRole.ORIGINAL,
                                          reading=TableReading(headers=matrix[0], rows=matrix[1:])))
                for quote in soup.find_all("blockquote"):
                    quote.replace_with("\n" + "\n".join("> " + line for line in quote.get_text("\n", strip=True).splitlines()) + "\n")
                text = soup.get_text("\n", strip=True)
            # 消息正文按引用、签名边界切分，保留 Date 原文，不猜测时区。
            groups = []
            current, current_role = [], SpanRole.ORIGINAL
            for line in text.splitlines():
                role = current_role
                if re.match(r"\s*>|\s*(?:On .+wrote:|-----Original Message-----|From:|发件人[：:])", line, re.I):
                    role = SpanRole.QUOTED
                elif re.match(r"\s*(?:--\s*$|Best regards|Kind regards|Regards[,，]?\s*$|免责声明|Disclaimer)", line, re.I):
                    role = SpanRole.SIGNATURE
                if role is not current_role and current:
                    groups.append((current_role, "\n".join(current)))
                    current = []
                current_role = role
                current.append(line)
            if current:
                groups.append((current_role, "\n".join(current)))
            quote_index = 0
            for i, (role, content) in enumerate(groups):
                if not content.strip():
                    continue
                if role is SpanRole.QUOTED:
                    quote_index += 1
                spans.append(span(ctx, f"msg:{quote_index}:body:{i}", content.strip(),
                                  EmailMessageLocator(message_index=quote_index,
                                                      part="signature" if role is SpanRole.SIGNATURE else "body"),
                                  self.name, role=role))
        else:
            review = True
            issues.append(issue(IssueCode.MATERIAL_LOW_QUALITY, "EML 没有可读正文"))
        leaves = list(message.walk())
        if len(leaves) > 1000:
            raise ValueError("EML MIME 部件超过 1000 个")
        alternatives = {id(child) for parent in leaves if parent.get_content_type() == "multipart/alternative"
                        and any(child is body for child in parent.walk()) for child in parent.walk()
                        if child.get_content_maintype() == "text"}
        for i, part in enumerate(leaves):
            if part.defects:
                review = True
            if part is message or part is body:
                continue
            if (part.get_content_disposition() == "attachment" or part.get_filename()
                    or part.get_content_maintype() != "text" or id(part) not in alternatives):
                if part.is_multipart() and part.get_content_type() != "message/rfc822" and not part.get_filename() and part.get_content_disposition() != "attachment":
                    continue
                review = True
                # 公共定位器没有 MIME 附件页码/bbox；不能假装它是可独立定位的材料。
                # 在所属 EML 证据中列明部件路径，要求导入时登记为独立材料，再由对应解析器解析。
                description = f"MIME 部件 {i}：{part.get_filename() or '(无文件名)'}；{part.get_content_type()}；尚未登记为独立材料"
                s = span(ctx, f"msg:0:mime:{i}", description, EmailMessageLocator(message_index=0), self.name,
                         role=SpanRole.DERIVED_SUMMARY, needs_review=True)
                spans.append(s)
                issues.append(issue(IssueCode.MATERIAL_UNSUPPORTED, "EML 内嵌附件需登记到工单包后单独解析：" + description, [s.id]))
        return finish(ctx, self.name, spans, issues=issues, review=review,
                      note="保留邮件日期与编码头；alternative 正文只取一种；MIME 附件不写出、不执行。PDF/EML 验证样本均为合成。")
