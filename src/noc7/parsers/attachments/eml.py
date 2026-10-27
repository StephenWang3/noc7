"""EML 在内存拆 MIME；不落地附件、不请求 HTML 里的远程资源。"""
from __future__ import annotations

import re
from email import policy
from email.parser import BytesParser

from bs4 import BeautifulSoup, Comment

from ...schema.evidence import EmailMessageLocator, MaterialKind, SpanRole, TableReading
from ...schema.issues import IssueCode
from ..base import ParseContext
from .common import finish, issue, read_limited, span


def _quote_key(node):
    quotes = node.find_parents("blockquote")
    return id(quotes[-1]) if quotes else None


def _message_groups(lines):
    # 单独出现 From: 是正文；至少两个不同的连续转发头（且包含发件人）才标引用。
    header = re.compile(r"\s*(From|To|Cc|Date|Sent|Subject|发件人|收件人|抄送|日期|发送时间|主题)[：:]", re.I)
    forwarded = set()
    run, fields = [], set()
    for i, (line, html_quote) in enumerate([*lines, ("", None)]):
        match = header.match(line) if html_quote is None else None
        if match:
            run.append(i)
            fields.add(match[1].lower())
        else:
            if len(fields) >= 2 and fields & {"from", "发件人"}:
                forwarded.update(run)
            run, fields = [], set()
    signature = re.compile(r"\s*(?:--|Best regards[,，]?|Kind regards[,，]?|Regards[,，]?|免责声明|Disclaimer)\s*", re.I)
    groups, quote_indices = [], {}
    previous_key = None
    for i, (line, html_quote) in enumerate(lines):
        role = SpanRole.ORIGINAL
        key = None
        if html_quote is not None:
            role, key = SpanRole.QUOTED, ("html", html_quote)
        elif re.match(r"\s*>|\s*(?:On .+wrote:|-----Original Message-----)\s*$", line, re.I) or i in forwarded:
            role = SpanRole.QUOTED
            key = previous_key if previous_key and previous_key[0] == "text" else ("text", i)
        elif signature.fullmatch(line):
            role = SpanRole.SIGNATURE
        if role is SpanRole.QUOTED:
            if key not in quote_indices:
                quote_indices[key] = len(quote_indices) + 1
            message_index = quote_indices[key]
        else:
            message_index = 0
        previous_key = key
        if groups and groups[-1][:2] == (role, message_index):
            groups[-1][2].append(line)
        else:
            groups.append((role, message_index, [line]))
    return groups, quote_indices


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
        uncertain_message = review or bool(message.defects)
        header = "\n".join(f"{key}: {message[key]}" for key in ("From", "To", "Cc", "Subject", "Date", "Message-ID") if message[key])
        if not header:
            raise ValueError("没有可识别邮件头，不是有效 EML")
        spans.append(span(ctx, "msg:0:header", header, EmailMessageLocator(message_index=0, part="header"), self.name))
        # get_body 优先纯文本，避免 multipart/alternative 的 HTML 副本算成另一份证据。
        body = message.get_body(preferencelist=("plain", "html"))
        uncertain_body = False
        if body is not None:
            try:
                text = body.get_content()
            except (LookupError, UnicodeError):
                text = body.get_payload(decode=True).decode("utf-8", errors="replace")
                review = True
                uncertain_body = True
            if "\ufffd" in text:
                review = True
                uncertain_body = True
            uncertain_body = uncertain_body or bool(body.defects)
            lines = [(line, None) for line in text.splitlines()]
            tables = []
            if body.get_content_type() == "text/html":
                soup = BeautifulSoup(text, "html.parser")
                for node in soup(["script", "style", "iframe", "object"]):
                    node.decompose()
                for i, table in enumerate(soup.find_all("table")):
                    matrix = [[cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"], recursive=False)]
                              for row in table.find_all("tr")]
                    matrix = [r for r in matrix if r]
                    if matrix and any(cell.strip() for row in matrix for cell in row):
                        tables.append((i, _quote_key(table), table.get_text(" ", strip=True), matrix))
                # 保留 HTML 引用归属，正文与表格共享同一引用分组；不靠添加 > 猜分组。
                lines = [(line, _quote_key(node)) for node in soup.find_all(string=True)
                         if not isinstance(node, Comment) for line in str(node).splitlines() if line.strip()]
            # 消息正文按引用、签名边界切分，保留 Date 原文，不猜测时区。
            groups, quote_indices = _message_groups(lines)
            for i, quote, content, matrix in tables:
                message_index = 0 if quote is None else quote_indices[("html", quote)]
                spans.append(span(ctx, f"msg:{message_index}:tbl:{i}", content,
                                  EmailMessageLocator(message_index=message_index, part="table"), self.name,
                                  role=SpanRole.ORIGINAL if quote is None else SpanRole.QUOTED,
                                  reading=TableReading(headers=matrix[0], rows=matrix[1:])))
            for i, (role, message_index, group_lines) in enumerate(groups):
                content = "\n".join(group_lines)
                if not content.strip():
                    continue
                spans.append(span(ctx, f"msg:{message_index}:body:{i}", content.strip(),
                                  EmailMessageLocator(message_index=message_index,
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
        if uncertain_message or uncertain_body:
            review = True
            spans = [s.model_copy(update={"needs_review": True}) if uncertain_message or
                     (s.locator.part in {"body", "table", "signature"}) else s for s in spans]
        return finish(ctx, self.name, spans, issues=issues, review=review,
                      note="保留邮件日期与编码头；alternative 正文只取一种；MIME 附件不写出、不执行，未覆盖部件需复核。")
