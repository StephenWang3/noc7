from dataclasses import replace
import hashlib

import pytest

from noc7.bundle import load_bundle
from noc7.parsers import ParseContext
from noc7.schema.evidence import MaterialKind
from tests.conftest import BUNDLES


@pytest.fixture
def make_ctx(tmp_path):
    def make(data: bytes, kind: MaterialKind, name="input.bin"):
        bundle = load_bundle(BUNDLES / "SYN-P04")
        (tmp_path / name).write_bytes(data)
        material = bundle.manifest.material("M03").model_copy(update={
            "path": name, "kind": kind, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        return ParseContext(replace(bundle, root=tmp_path), material)
    return make


def fixture_ctx(name, mid):
    bundle = load_bundle(BUNDLES / name)
    return ParseContext(bundle, bundle.manifest.material(mid))
