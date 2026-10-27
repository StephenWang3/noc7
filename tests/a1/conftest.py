from pathlib import Path

import pytest

from noc7.extract import analyze
from noc7.parsers import ParserRegistry
from noc7.parsers.text import PARSERS

BUNDLES = Path(__file__).resolve().parents[2] / "fixtures" / "bundles"


def text_registry():
    """固定 A1 测试边界，A2 合入后仍可独立做文本消融回归。"""
    reg = ParserRegistry()
    for parser in PARSERS:
        reg.register(parser)
    return reg


@pytest.fixture(scope="session")
def results():
    return {
        p.name: analyze(p, registry=text_registry()) for p in sorted(BUNDLES.iterdir())
    }
