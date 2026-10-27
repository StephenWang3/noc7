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
