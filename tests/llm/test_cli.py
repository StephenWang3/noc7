import json
from shutil import copytree

from noc7.cli import main
from noc7.providers.text_prompt import PROMPT_VERSION
from noc7.providers.text_config import load_model_config

from .conftest import BUNDLES, ROOT, qwen_config, write_config


def test_qwen_cli_report_replay_and_provenance(server, tmp_path):
    config = write_config(tmp_path / "qwen.json", qwen_config(server, json_mode=False))
    output, replay = tmp_path / "generated", tmp_path / "replayed"
    assert main(["analyze", str(BUNDLES / "SYN-S01"), "--provider", "llm", "--model-config", config,
                 "--out", str(output), "--save-replay"]) == 0
    target = output / "SYN-S01"
    assert all((target / name).is_file() for name in ["analysis.json", "report.md", "report.html", "report.css", "replay.json"])
    generated = json.loads((target / "analysis.json").read_text())
    assert generated["run"]["provider"].startswith("openai_compatible:qwen:qwen-test:")
    assert generated["run"]["prompt_version"] == PROMPT_VERSION
    assert (target / "replay.json").stat().st_mode & 0o777 == 0o600
    assert main(["analyze", str(BUNDLES / "SYN-S01"), "--provider", "replay", "--replay", str(output),
                 "--out", str(replay)]) == 0
    restored = json.loads((replay / "SYN-S01/analysis.json").read_text())
    assert restored["elements"] == generated["elements"]
    assert restored["events"] == generated["events"] and restored["evidence"] == generated["evidence"]
    assert len(server.requests) == 1


def test_same_cli_switches_services_only_by_config(server, tmp_path, monkeypatch):
    import urllib.request
    native_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    class Transport:
        def open(self, request, timeout):
            # 保留官方请求构造，仅在测试传输层把流量送到本地模拟服务。
            local = urllib.request.Request(server.base_url + "/chat/completions", data=request.data,
                                           headers=dict(request.header_items()))
            return native_opener.open(local, timeout=timeout)

    monkeypatch.setattr("noc7.providers.text_http.urllib.request.build_opener", lambda *args: Transport())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-key")
    configs = [load_model_config(ROOT / "config/models/deepseek.json"), qwen_config(server, json_mode=False)]
    results = []
    for config in configs:
        path = write_config(tmp_path / f"{config.name}.json", config)
        out = tmp_path / config.name
        assert main(["analyze", str(BUNDLES / "SYN-S01"), "--provider", "llm", "--model-config", path,
                     "--out", str(out)]) == 0
        results.append(json.loads((out / "SYN-S01/analysis.json").read_text()))
    assert results[0]["elements"] == results[1]["elements"]
    assert results[0]["run"]["provider"] != results[1]["run"]["provider"]
    assert server.requests[0]["body"]["model"] == "deepseek-flash"
    assert server.requests[1]["body"]["model"] == "qwen-test"
    assert "response_format" not in server.requests[1]["body"]


def test_batch_continues_after_bad_model_response(server, tmp_path, capsys):
    first = copytree(BUNDLES / "SYN-S01", tmp_path / "inputs/first")
    second = copytree(BUNDLES / "SYN-S01", tmp_path / "inputs/second")
    server.replies = [(200, {}, b"PRIVATE_MODEL_RESPONSE")]
    config = write_config(tmp_path / "qwen.json", qwen_config(server))
    out = tmp_path / "generated"
    assert main(["analyze", str(first), str(second), "--provider", "llm", "--model-config", config,
                 "--out", str(out)]) == 1
    assert not (out / "first/report.html").exists()
    assert (out / "second/report.html").exists()
    assert len(server.requests) == 2
    assert "PRIVATE_MODEL_RESPONSE" not in capsys.readouterr().err


def test_cli_saves_sanitized_rejection_without_report(server, sample, tmp_path, capsys):
    from copy import deepcopy
    from .conftest import envelope
    data = deepcopy(sample[1])
    data["quotes"].append({"evidence_id": "M99/private", "quote": "PRIVATE_RESPONSE"})
    server.default = envelope(data)
    config = write_config(tmp_path / "qwen.json", qwen_config(server))
    out = tmp_path / "generated"
    assert main(["analyze", str(BUNDLES / "SYN-S01"), "--provider", "llm", "--model-config", config,
                 "--out", str(out)]) == 1
    target = out / "SYN-S01"
    assert not (target / "report.html").exists()
    record = (target / "analysis-rejected.json").read_text()
    assert "EVIDENCE_REF_MISSING" in record
    assert "PRIVATE_RESPONSE" not in record and "M99/private" not in record
    assert "PRIVATE_RESPONSE" not in capsys.readouterr().err


def test_existing_output_is_rejected_before_http(server, tmp_path):
    config = write_config(tmp_path / "qwen.json", qwen_config(server))
    out = tmp_path / "existing"
    out.mkdir()
    marker = out / "old-report.html"
    marker.write_text("old")
    assert main(["analyze", str(BUNDLES / "SYN-S01"), "--provider", "llm", "--model-config", config,
                 "--out", str(out)]) == 2
    assert marker.read_text() == "old" and not server.requests


def test_real_output_preflight_happens_before_http(server, tmp_path, monkeypatch, capsys):
    from noc7.extract import storage
    source = copytree(BUNDLES / "SYN-S01", tmp_path / "inputs/case")
    path = source / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["data_class"] = "real"
    path.write_text(json.dumps(manifest))
    config = write_config(tmp_path / "qwen.json", qwen_config(server))
    # 临时模拟源码目录边界，不向实际仓库写任何测试工单。
    boundary = tmp_path / "source-repository"
    boundary.mkdir()
    (boundary / "pyproject.toml").write_text("")
    monkeypatch.setattr(storage, "SOURCE_ROOT", boundary)
    assert main(["analyze", str(source), "--provider", "llm", "--model-config", config,
                 "--out", str(boundary / "output")]) == 1
    assert not server.requests and not (boundary / "output").exists()
    assert "仓库外" in capsys.readouterr().err


def test_configuration_errors_are_detected_before_http(server, tmp_path, capsys):
    source = str(BUNDLES / "SYN-S01")
    assert main(["analyze", source, "--provider", "llm"]) == 2
    assert main(["analyze", source, "--model-config", "unused.json"]) == 2
    assert main(["analyze", source, "--provider", "llm", "--model-config",
                 str(ROOT / "config/models/qwen.example.json"), "--out", str(tmp_path / "new")]) == 2
    assert not server.requests
