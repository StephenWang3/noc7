import json
from copy import deepcopy
from pathlib import Path

import pytest

from noc7.providers.text_audit import AuditRecord
from noc7.providers.text_config import TextProviderError
from noc7.providers.text_http import OpenAICompatibleTextProvider
from noc7.rules import ExtractionRejected

from .conftest import envelope, qwen_config
from .test_evidence import empty_extraction
from .test_fact_recall import context


def test_audit_preserves_raw_suggestions_without_request_headers(server, sample, tmp_path, monkeypatch):
    monkeypatch.setenv("NOC_TEST_KEY", "PRIVATE_TEST_CREDENTIAL")
    ctx = context(sample, "告警位置在 SYN-机房。")
    data = empty_extraction()
    data["elements"]["location"]["candidates"] = [dict(
        id="C1", description="SYN-机房", role="located_fault_point", attribution="unknown",
        evidence_refs=[ctx.evidence[0].id])]
    server.default = envelope(data)
    root = tmp_path / "audit"
    result = OpenAICompatibleTextProvider(qwen_config(server, api_key_env="NOC_TEST_KEY"), audit_dir=root).extract(ctx)
    assert result.elements.location.candidates == []
    f = next(root.glob("*.json"))
    raw = f.read_text()
    trace = json.loads(raw)
    assert "PRIVATE_TEST_CREDENTIAL" not in raw and "Authorization" not in raw
    assert trace["outcome"] == "accepted" and trace["raw_response"] == server.default.decode()
    assert trace["before_grounding"]["suggestions"][1]["original"] == data["elements"]["location"]
    assert trace["after_grounding"]["elements"]["location"]["candidates"] == []
    assert not any(c["action"] == "candidate_removed" and c["element"] == "location" for c in trace["changes"])
    assert result.suggestions[1].original == data["elements"]["location"]
    assert root.stat().st_mode & 0o777 == 0o700
    assert f.stat().st_mode & 0o777 == 0o600


def test_rejected_answer_is_traced_but_not_returned(server, sample, tmp_path):
    data = deepcopy(sample[1])
    data["quotes"].append(dict(evidence_id="M99/missing", quote="合成不存在的证据"))
    server.default = envelope(data)
    with pytest.raises(ExtractionRejected):
        OpenAICompatibleTextProvider(qwen_config(server), audit_dir=tmp_path / "audit").extract(sample[0])
    trace = json.loads(next((tmp_path / "audit").glob("*.json")).read_text())
    assert trace["outcome"] == "rejected" and "EVIDENCE_REF_MISSING" in trace["issue_codes"]
    assert "raw_response" in trace and len(server.requests) == 1


def test_invalid_json_and_truncation_keep_diagnostic_response(server, sample, tmp_path):
    server.default = envelope(empty_extraction(), finish="length")
    with pytest.raises(TextProviderError):
        OpenAICompatibleTextProvider(qwen_config(server), audit_dir=tmp_path / "audit").extract(sample[0])
    trace = json.loads(next((tmp_path / "audit").glob("*.json")).read_text())
    assert trace["outcome"] == "rejected" and "raw_response" in trace
    assert "before_grounding" not in trace


def test_audit_path_checks_happen_before_network(server, tmp_path):
    for path in [Path.cwd() / "var/audit", tmp_path]:
        with pytest.raises(TextProviderError):
            OpenAICompatibleTextProvider(qwen_config(server), audit_dir=path)
    link = tmp_path / "linked"
    link.symlink_to(Path.cwd(), target_is_directory=True)
    with pytest.raises(TextProviderError):
        OpenAICompatibleTextProvider(qwen_config(server), audit_dir=link / "audit")
    assert server.requests == []


def test_audit_io_error_after_response_does_not_repeat_model_request(server, sample, tmp_path, monkeypatch):
    original = AuditRecord.record
    def fail(self, **values):
        if "raw_response" in values:
            raise OSError("模拟写入失败")
        return original(self, **values)
    monkeypatch.setattr(AuditRecord, "record", fail)
    with pytest.raises(OSError):
        OpenAICompatibleTextProvider(qwen_config(server), audit_dir=tmp_path / "audit").extract(sample[0])
    assert len(server.requests) == 1


def test_cli_audit_is_opt_in_and_llm_only(server, tmp_path):
    from noc7.cli import main
    from .conftest import BUNDLES, write_config

    config = write_config(tmp_path / "model.json", qwen_config(server))
    assert main(["analyze", str(BUNDLES / "SYN-S01"), "--provider", "llm",
                 "--model-config", config, "--model-audit-dir", str(tmp_path / "audit"),
                 "--out", str(tmp_path / "results")]) == 0
    assert len(list((tmp_path / "audit").glob("*.json"))) == 1
    assert (tmp_path / "results/SYN-S01/analysis.json").is_file()
    assert main(["analyze", str(BUNDLES / "SYN-S01"), "--model-audit-dir", str(tmp_path / "unused")]) == 2
    assert not (tmp_path / "unused").exists()
