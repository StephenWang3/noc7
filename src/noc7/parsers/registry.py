"""默认解析器注册表。

A1 在 noc7/parsers/text/ 包里导出 PARSERS 列表，A2 在 noc7/parsers/attachments/ 包里导出 PARSERS 列表。
两条线都不需要修改本文件，也不会改到同一个文件；某个包还不存在时，它负责的材料类型由
UnsupportedParser 兜底，显示为“不支持/待实现”。
"""

from __future__ import annotations

import importlib

from .base import ParserRegistry

PARSER_PACKAGES = (
    "noc7.parsers.text",  # A1：ticket_fields、process_log、email_html、text
    "noc7.parsers.attachments",  # A2：image、pdf、docx、email_eml、other
)


def default_registry() -> ParserRegistry:
    reg = ParserRegistry()
    for name in PARSER_PACKAGES:
        try:
            mod = importlib.import_module(name)
        except ModuleNotFoundError as e:
            if e.name == name:
                continue  # 该开发线尚未交付
            raise
        for parser in mod.PARSERS:
            reg.register(parser)
    return reg
