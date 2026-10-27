"""材料解析器。A0 只定义接口；文本类解析器由 A1 实现，附件类由 A2 实现。"""

from .base import PARSER_OWNERSHIP, ParseContext, ParseOutput, Parser, ParserRegistry, UnsupportedParser
from .registry import default_registry

__all__ = ["PARSER_OWNERSHIP", "ParseContext", "ParseOutput", "Parser", "ParserRegistry", "UnsupportedParser", "default_registry"]
