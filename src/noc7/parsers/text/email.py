"""邮件切分的公共函数；A2 的 EML 解析器可以复用，不读取其他材料。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, NavigableString, Tag

from ...schema.evidence import EmailMessageLocator, EvidenceSpan, SpanRole, TableReading

SIGNATURE = re.compile(
    r"(?im)^\s*(?:best regards|kind regards|regards|thanks|此致|顺祝|免责声明|confidentiality notice|this (?:e-?mail|message).{0,70}confidential)\b[,，:：!！]?|本邮件及其附件含保密|如非指定收件人"
)
BOUNDARY = re.compile(
    r"(?im)^\s*(?:[-_]{2,}\s*(?:original message|原始邮件|转发邮件).*$|On .{2,200}wrote:\s*$|在.{2,200}写道[：:]\s*$|From:\s*\S+.*$|发件人[：:].*$)"
)


@dataclass(frozen=True)
class EmailPart:
    message_index: int
    part: str
    text: str
    role: SpanRole
    reading: TableReading | None = None


def split_signature(text: str) -> tuple[str, str]:
    m = SIGNATURE.search(text)
    return (
        (text[: m.start()].rstrip(), text[m.start() :].strip())
        if m
        else (text.strip(), "")
    )


def split_email(text: str, *, is_html: bool = True) -> list[EmailPart]:
    """按 DOM 引用容器或常见纯文本边界切分。保留签名、引用和表格，不执行 HTML。"""
    if not is_html:
        return _plain_parts(text)
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["script", "style", "iframe", "object", "head"]):
        tag.decompose()
    # 用树遍历保留引用容器在正文中的顺序；每个容器获得独立、稳定的消息编号。
    chunks: dict[int, list[str]] = {0: []}
    tables: list[EmailPart] = []
    roles = {0: SpanRole.ORIGINAL}
    next_index = 0

    def walk(node, index):
        nonlocal next_index
        if isinstance(node, NavigableString):
            chunks[index].append(str(node))
            return
        if not isinstance(node, Tag):
            return
        classes = set(node.get("class", []))
        if node.name == "blockquote" or classes & {
            "gmail_quote",
            "yahoo_quoted",
            "quoted",
        }:
            next_index += 1
            index = next_index
            chunks[index] = []
            roles[index] = SpanRole.QUOTED
        if node.name == "table":
            rows = [
                [
                    c.get_text(" ", strip=True)
                    for c in r.find_all(["th", "td"], recursive=False)
                ]
                for r in node.find_all("tr")
            ]
            rows = [r for r in rows if r]
            if rows:
                has_header = bool(node.find("th"))
                reading = TableReading(
                    headers=rows[0] if has_header else [],
                    rows=rows[1:] if has_header else rows,
                )
                tables.append(
                    EmailPart(
                        index,
                        "table",
                        node.get_text(" ", strip=True),
                        roles[index],
                        reading,
                    )
                )
            return
        if node.name in {"p", "div", "br", "pre", "li", "hr"}:
            chunks[index].append("\n")
        for child in node.children:
            walk(child, index)
        if node.name in {"p", "div", "pre", "li"}:
            chunks[index].append("\n")

    walk(soup.body or soup, 0)
    parts: list[EmailPart] = []
    for index, lines in chunks.items():
        raw = re.sub(r"\n[ \t]*\n+", "\n", "".join(lines)).strip()
        header, body = _header(raw)
        if header:
            parts.append(EmailPart(index, "header", header, roles[index]))
        body, signature = split_signature(body)
        if body:
            parts.append(EmailPart(index, "body", body, roles[index]))
        if signature:
            parts.append(EmailPart(index, "signature", signature, SpanRole.SIGNATURE))
        parts.extend(p for p in tables if p.message_index == index)
    # Outlook 的回复正文经常只有分隔线/From 头，没有 blockquote。
    if next_index == 0 and not tables:
        return _plain_parts(re.sub(r"\n[ \t]*\n+", "\n", "".join(chunks[0])).strip())
    return parts


def _header(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    header: list[str] = []
    while lines and re.match(
        r"^\s*(?:From|To|Cc|Date|Sent|Subject|发件人|收件人|发送时间|主题)\s*[:：]",
        lines[0],
        re.I,
    ):
        header.append(lines.pop(0))
    return "\n".join(header), "\n".join(lines).strip()


def _plain_parts(text: str) -> list[EmailPart]:
    # 分隔线和紧随其后的 From 属于同一条引用消息，不能编号两次。
    messages: list[list[str]] = [[]]
    awaiting_header = False
    for line in text.splitlines():
        marker = re.match(
            r"\s*[-_]{2,}.*(?:original message|forwarded message|原始邮件|转发邮件)",
            line,
            re.I,
        ) or re.match(r"\s*(?:On .+wrote:|在.+写道[：:])\s*$", line, re.I)
        if marker:
            if any(x.strip() for x in messages[-1]):
                messages.append([])
            awaiting_header = True
            continue
        is_from = re.match(r"\s*(?:From|发件人)\s*[:：]", line, re.I)
        if is_from and not awaiting_header:
            existing_body = [
                x
                for x in messages[-1]
                if x.strip()
                and not re.match(
                    r"\s*(?:From|To|Cc|Date|Sent|Subject|发件人|收件人|发送时间|主题)\s*[:：]",
                    x,
                    re.I,
                )
            ]
            if existing_body:
                messages.append([])
        messages[-1].append(line)
        if line.strip():
            awaiting_header = False
    parts = []
    for index, lines in enumerate(messages):
        header, body = _header("\n".join(lines).strip())
        role = SpanRole.ORIGINAL if index == 0 else SpanRole.QUOTED
        if header:
            parts.append(EmailPart(index, "header", header, role))
        body, signature = split_signature(body)
        if body:
            parts.append(EmailPart(index, "body", body, role))
        if signature:
            parts.append(EmailPart(index, "signature", signature, SpanRole.SIGNATURE))
    return parts


def email_spans(
    text: str, material_id: str, extractor: str, *, is_html: bool = True
) -> list[EvidenceSpan]:
    """消息编号以当前消息 0 起；同一消息内多个表格用后缀区分。"""
    counts: dict[str, int] = {}
    spans = []
    for p in split_email(text, is_html=is_html):
        local = f"msg:{p.message_index}:{p.part}"
        counts[local] = counts.get(local, 0) + 1
        suffix = f":{counts[local]}" if counts[local] > 1 else ""
        spans.append(
            EvidenceSpan(
                id=f"{material_id}/{local}{suffix}",
                material_id=material_id,
                locator=EmailMessageLocator(message_index=p.message_index, part=p.part),
                text=p.text,
                role=p.role,
                reading=p.reading,
                extractor=extractor,
            )
        )
    return spans
