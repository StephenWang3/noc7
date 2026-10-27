"""分析产物也遵守真实材料不入库约束。"""

from pathlib import Path

from ..schema import DataClass

SOURCE_ROOT = Path(__file__).resolve().parents[3]


def ensure_output_allowed(data_class: DataClass, path: Path) -> None:
    if data_class == DataClass.REAL and (SOURCE_ROOT / "pyproject.toml").exists():
        if path.resolve().is_relative_to(SOURCE_ROOT):
            raise ValueError(
                "真实工单的分析产物必须写入仓库外目录，例如 ~/.noc7/real-reports/。"
            )
