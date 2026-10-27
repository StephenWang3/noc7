import json
import re
import shutil

import pytest

import noc7.bundle as bundle_mod
from noc7.bundle import BundleError, load_bundle, rehash_bundle
from noc7.goldcheck import check_gold, load_gold
from noc7.schema import DataClass, ElementName
from noc7.timeparse import parse_time

from .conftest import BUNDLES, GOLD, bundle_dirs


def test_have_10_to_15_synthetic_bundles():
    assert 10 <= len(bundle_dirs()) <= 15


@pytest.mark.parametrize("d", bundle_dirs(), ids=lambda d: d.name)
def test_bundle_loads_and_is_synthetic(d):
    b = load_bundle(d)
    assert b.manifest.data_class is DataClass.SYNTHETIC
    assert b.manifest.bundle_id == d.name == b.ticket.ticket_ref
    assert "合成" in b.manifest.synthetic_notice


@pytest.mark.parametrize("d", bundle_dirs(), ids=lambda d: d.name)
def test_bundle_text_has_no_real_identifiers(d):
    """合成数据只能用文档保留的 IP 段和 example 域名，编号以 SYN- 开头。"""
    for p in d.rglob("*"):
        if p.suffix not in {".json", ".html", ".eml"}:
            continue
        text = p.read_text(encoding="utf-8")
        for ip in re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text):
            assert ip.startswith(("192.0.2.", "198.51.100.", "203.0.113.")), f"{p}: 非文档保留 IP {ip}"
        for domain in re.findall(r"@([A-Za-z][\w.-]*[A-Za-z])", text):
            assert re.search(r"(^|\.)example(\.(com|net|org))?$", domain), f"{p}: 非示例域名 {domain}"


@pytest.mark.parametrize("d", bundle_dirs(), ids=lambda d: d.name)
def test_every_bundle_has_valid_gold(d):
    g = load_gold(GOLD / f"{d.name}.json")
    assert check_gold(g, load_bundle(d)) == []


@pytest.mark.parametrize("d", bundle_dirs(), ids=lambda d: d.name)
def test_gold_field_times_agree_with_bundle(d):
    """标准答案里引用单个字段的时间候选，必须与该字段按系统口径解析出的时间一致（防止标注笔误）。"""
    b, g = load_bundle(d), load_gold(GOLD / f"{d.name}.json")
    for name in (ElementName.START_TIME, ElementName.END_TIME):
        for c in g.elements[name].required_candidates:
            key = c.evidence[0].field_key if len(c.evidence) == 1 else None
            if c.time is None or key is None or not key.endswith(("_at", "_time")):
                continue
            raw = b.ticket.field(key).value
            assert c.time.matches(parse_time(raw, b.manifest.default_timezone)), f"{name}: {raw} vs {c.time.iso}"


def test_coverage_of_statuses_and_issue_codes():
    """标准答案集要同时覆盖“有值”和“必须留空”，否则评测会偏向一边。"""
    golds = [load_gold(p) for p in GOLD.glob("*.json")]
    statuses = {s for g in golds for el in g.elements.values() for s in el.status_in}
    assert {"documented", "confirmed", "unknown", "conflicted"} <= {s.value for s in statuses}
    codes = {i.code.value for g in golds for i in g.expected_issues}
    for must in ["TIME_ORDER_INVERTED", "TIME_PLACEHOLDER", "EMBEDDED_INSTRUCTION", "DERIVED_SOURCE_DUPLICATE",
                 "SERVICE_IDENTITY_UNVERIFIED", "CAUSE_CANDIDATE_LIST", "TICKET_CANCELLED"]:
        assert must in codes


def _copy(tmp_path, name="SYN-S10"):
    dst = tmp_path / name
    shutil.copytree(BUNDLES / name, dst)
    return dst


def test_tampered_material_is_rejected(tmp_path):
    d = _copy(tmp_path)
    p = d / "ticket.json"
    p.write_text(p.read_text(encoding="utf-8").replace("线路已拆机", "光缆中断"), encoding="utf-8")
    with pytest.raises(BundleError, match="sha256"):
        load_bundle(d)
    rehash_bundle(d)
    load_bundle(d)


def test_unlisted_file_is_rejected(tmp_path):
    d = _copy(tmp_path)
    (d / "attachments" / "extra.png").write_bytes(b"\x89PNG")
    with pytest.raises(BundleError, match="清单未声明"):
        load_bundle(d)


def test_missing_material_is_rejected(tmp_path):
    d = _copy(tmp_path)
    (d / "attachments" / "M04-wan-loss-chart.png").unlink()
    with pytest.raises(BundleError, match="不存在"):
        load_bundle(d)


def test_attachment_flag_mismatch_is_a_warning():
    b = load_bundle(BUNDLES / "SYN-S10")
    assert any("附件标志" in w for w in b.warnings)


def test_real_bundle_inside_repo_is_rejected(tmp_path, monkeypatch):
    d = _copy(tmp_path)
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    m["data_class"] = "real"
    (d / "manifest.json").write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(bundle_mod, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(bundle_mod, "_IS_SOURCE_CHECKOUT", True)
    with pytest.raises(BundleError, match="真实工单包不能放在源码仓库"):
        load_bundle(d)
