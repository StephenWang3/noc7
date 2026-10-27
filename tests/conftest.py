from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "fixtures" / "bundles"
GOLD = ROOT / "evals" / "gold"


def bundle_dirs() -> list[Path]:
    return sorted(d for d in BUNDLES.iterdir() if (d / "manifest.json").exists())


@pytest.fixture
def root() -> Path:
    return ROOT


@pytest.fixture(autouse=True)
def _no_local_report_profile(tmp_path_factory, monkeypatch):
    """公司格式页眉配置在本机仓库外；测试一律指向空目录，不读真实公司名和 logo。"""
    monkeypatch.setenv("NOC7_REPORT_PROFILE", str(tmp_path_factory.mktemp("no-profile")))
