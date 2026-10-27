"""文本链路公共入口。"""

from .baseline import RulesProvider
from .types import Extraction, ExtractionContext, TextProvider


# pipeline 依赖 rules；避免导入提供方时引入环。
def analyze(*args, **kwargs):
    from .pipeline import analyze as run

    return run(*args, **kwargs)


__all__ = [
    "analyze",
    "RulesProvider",
    "Extraction",
    "ExtractionContext",
    "TextProvider",
]
