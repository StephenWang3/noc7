"""操作台：一律“模型 + 规则”。配好模型就实时调用，没配就回放保存的模型结果；演示单只回放。

单测不访问外网：实时调用打到本机的假 OpenAI 兼容服务（扮演公司本地模型）。
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from noc7.bundle import sha256_file
from noc7.extract.pipeline import analyze, analyze_with_context
from noc7.providers import narrative
from noc7.providers.text_config import create_text_provider
from noc7.report import write_reports
from noc7.schema import AnalysisResult
from noc7.web.app import create_app
from noc7.web.jobs import REPLAY_LABEL, JobRunner
from noc7.web.models import LOCAL_KEY_ENV, ModelSettings
from noc7.web.replays import ReplayIndex
from tests.llm.test_two_stage import FACTS, WRITING

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "fixtures" / "bundles"
DEEPSEEK = ROOT / "config" / "models" / "deepseek.json"
HEADERS = {"X-NOC7-Request": "1"}


def _zip_dir(path: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for item in path.rglob("*"):
            if item.is_file():
                archive.write(item, item.relative_to(path).as_posix())
    return buf.getvalue()


def _copy_as(src: str, ref: str, dest: Path, data_class: str | None = None) -> Path:
    """复制一张合成单并改编号（材料不变，事实引文照样对得上）。"""
    target = dest / ref
    shutil.copytree(BUNDLES / src, target)
    ticket_path = target / "ticket.json"
    ticket = json.loads(ticket_path.read_text(encoding="utf-8"))
    ticket["ticket_ref"] = ref
    ticket_path.write_text(json.dumps(ticket, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    manifest["bundle_id"] = ref
    for material in manifest["materials"]:
        if material["path"] == "ticket.json":
            material["sha256"] = sha256_file(ticket_path)
            material["size_bytes"] = ticket_path.stat().st_size
    if data_class:
        manifest["data_class"] = data_class
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def _wait(client: TestClient, ref: str, timeout: float = 120) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/api/tickets/{ref}")
        assert response.status_code == 200
        last = response.json()
        if last["status"] in {"ready", "failed"}:
            return last
        time.sleep(0.2)
    raise AssertionError(f"{ref} 在 {timeout}s 内没有完成：{last}")


@pytest.fixture(autouse=True)
def no_keys(monkeypatch: pytest.MonkeyPatch):
    """开发机上可能设了真密钥：测试里一律清掉，测试结束后恢复原样。"""
    for env in ("DEEPSEEK_API_KEY", LOCAL_KEY_ENV):
        monkeypatch.setenv(env, "x")
        monkeypatch.delenv(env)


@pytest.fixture
def fake_model():
    """假的公司本地模型：抽事实的请求回 FACTS（SYN-P04 的原文），成文请求回 WRITING。"""
    calls: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            writing = body["messages"][0]["content"] == narrative.INSTRUCTION
            calls.append("writing" if writing else "facts")
            content = json.dumps(WRITING if writing else FACTS, ensure_ascii=False)
            raw = json.dumps({"choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": content}}]},
                             ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1", calls
    httpd.shutdown()
    httpd.server_close()


def _local_fields(base_url: str, **extra) -> dict:
    return {"base_url": base_url, "model": "qwen-test", "max_request_kb": 512, "max_tokens": 4096,
            "json_mode": False, "needs_key": False, **extra}


def _app(tmp_path: Path, **kwargs):
    kwargs.setdefault("replay_patterns", [])
    return create_app(inbox=tmp_path / "inbox", model_config=DEEPSEEK,
                      settings_dir=tmp_path / "models", workbench_origins="", **kwargs)


def test_origin_allowlist():
    node = shutil.which("node")
    assert node, "需要 node 来检查页面里的来源校验"
    script = (ROOT / "src/noc7/web/static/origin.js").read_text(encoding="utf-8")
    script += """
if (!noc7AcceptOrigin("http://127.0.0.1:8765", "http://127.0.0.1:8765", "")) process.exit(1);
if (noc7AcceptOrigin("http://evil.example", "http://127.0.0.1:8765", "")) process.exit(2);
if (!noc7AcceptOrigin("http://wb.example", "http://127.0.0.1:8765", "http://wb.example")) process.exit(3);
if (noc7AcceptOrigin("http://other.example", "http://127.0.0.1:8765", " http://wb.example ")) process.exit(4);
"""
    result = subprocess.run([node, "-e", script], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_page_script_parses():
    node = shutil.which("node")
    assert node
    result = subprocess.run([node, "--check", str(ROOT / "src/noc7/web/static/app.js")],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_writes_need_the_page_header(tmp_path: Path):
    with TestClient(_app(tmp_path)) as http:
        assert http.post("/api/model/active", json={"profile": "deepseek"}).status_code == 403
        assert http.post("/api/tickets", files={"bundle": ("a.zip", b"x", "application/zip")}).status_code == 403
        assert http.post("/api/model/active", json={"profile": "deepseek"}, headers=HEADERS).status_code == 200
        assert http.get("/api/model").status_code == 200


def test_replay_saved_model_results(tmp_path: Path, fake_model):
    base_url, calls = fake_model
    # 先真实调用一次（假模型），把 SYN-P04 的诊断记录存下来，当作以前分析留下的记录。
    config = tmp_path / "qwen.json"
    config.write_text(json.dumps({"name": "qwen", "base_url": base_url, "model": "qwen-test", "external": False,
                                  "allowed_data": ["synthetic"], "max_request_bytes": 524288, "max_tokens": 4096,
                                  "pipeline": "two_stage", "fact_passes": 2}), encoding="utf-8")
    records = tmp_path / "records"
    live, _, _ = analyze_with_context(BUNDLES / "SYN-P04", create_text_provider(config, audit_dir=records))
    assert calls == ["facts", "facts", "writing"]

    roots = [BUNDLES / "SYN-P04", BUNDLES / "SYN-S09"]  # 每项可以直接是一个工单包
    with TestClient(_app(tmp_path, replay_patterns=[(records, "*.json")], local_roots=roots)) as http:
        listed = http.get("/api/tickets").json()
        assert listed["tickets"] == []  # 启动时不自动分析任何单
        assert listed["element_labels"]["location"] == "故障地点"
        bundles = http.get("/api/local-bundles").json()["bundles"]
        assert [(b["key"], b["has_replay"]) for b in bundles] == [("0/SYN-P04", True), ("1/SYN-S09", False)]
        assert all(str(BUNDLES) not in json.dumps(b) for b in bundles)

        # 没有模型：不能选“调用模型”；没有记录的单不能回放；有记录的回放成功。
        live_refused = http.post("/api/local-bundles/analyze", headers=HEADERS,
                                 json={"keys": ["0/SYN-P04"], "mode": "live"})
        assert live_refused.status_code == 400 and "模型设置" in live_refused.json()["problems"][0]
        assert http.post("/api/local-bundles/analyze", headers=HEADERS,
                         json={"keys": ["0/SYN-P04"], "mode": "nope"}).status_code == 400
        res = http.post("/api/local-bundles/analyze", headers=HEADERS,
                        json={"keys": ["0/SYN-P04", "1/SYN-S09", "0/SYN-P02"], "mode": "replay"}).json()
        assert res["accepted"] == ["SYN-P04"]
        assert [r["key"] for r in res["rejected"]] == ["1/SYN-S09", "0/SYN-P02"]
        assert "不能回放" in res["rejected"][0]["problems"][0]
        done = _wait(http, "SYN-P04")
        assert done["status"] == "ready"
        replayed = AnalysisResult.model_validate(done["analysis"])
        assert replayed.elements.cause.value == live.elements.cause.value == "市政道路施工挖断 24 芯光缆"
        assert replayed.run.provider.startswith("replay:")
        ticket = next(t for t in http.get("/api/tickets").json()["tickets"] if t["ticket_ref"] == "SYN-P04")
        assert ticket["source"] == "local"
        assert ticket["mode"] == "replay" and ticket["model_label"] == REPLAY_LABEL and ticket["finished_at"]
        docx = http.get("/api/tickets/SYN-P04/company-report.docx")
        assert docx.status_code == 200 and docx.content.startswith(b"PK")
        html = http.get("/api/tickets/SYN-P04/company-report.html")
        assert 'href="review-report.html"' in html.text
        assert http.get("/api/tickets/SYN-P04/review-report.html").status_code == 200
    assert calls == ["facts", "facts", "writing"]  # 回放不联网


def test_upload_without_model_or_saved_result_is_refused(tmp_path: Path):
    with TestClient(_app(tmp_path)) as http:
        assert http.get("/api/model").json()["usable"] is False
        bad = http.post("/api/tickets", headers=HEADERS, files={"bundle": ("e.zip", b"not-a-zip", "application/zip")})
        assert bad.status_code == 400 and bad.json()["status"] == "failed"
        refused = http.post("/api/tickets", headers=HEADERS,
                            files={"bundle": ("SYN-S01.zip", _zip_dir(BUNDLES / "SYN-S01"), "application/zip")})
        assert refused.status_code == 400
        assert "模型设置" in refused.json()["problems"][0]
        assert "SYN-S01" not in [t["ticket_ref"] for t in http.get("/api/tickets").json()["tickets"]]


def test_live_analysis_with_company_local_model(tmp_path: Path, fake_model):
    base_url, calls = fake_model
    bundle = _copy_as("SYN-P04", "SYN-X04", tmp_path / "src")
    with TestClient(_app(tmp_path)) as http:
        bad = http.post("/api/model/local", headers=HEADERS, json=_local_fields("ftp://nowhere"))
        assert bad.status_code == 400
        saved = http.post("/api/model/local", headers=HEADERS, json=_local_fields(base_url))
        assert saved.status_code == 200 and saved.json()["local"]["model"] == "qwen-test"
        state = http.post("/api/model/active", headers=HEADERS, json={"profile": "local"}).json()
        assert state["active"] == "local" and state["usable"] is True and state["label"] == "公司本地模型"

        res = http.post("/api/tickets", headers=HEADERS,
                        files={"bundle": ("SYN-X04.zip", _zip_dir(bundle), "application/zip")})
        assert res.status_code == 202
        done = _wait(http, "SYN-X04")
        assert done["status"] == "ready"
        result = AnalysisResult.model_validate(done["analysis"])
        assert result.elements.cause.value == "市政道路施工挖断 24 芯光缆"
        ticket = next(t for t in http.get("/api/tickets").json()["tickets"] if t["ticket_ref"] == "SYN-X04")
        assert ticket["mode"] == "live" and ticket["model_label"] == "实时调用 公司本地模型"
    assert calls == ["facts", "facts", "writing"]
    local = json.loads((tmp_path / "models" / "local.json").read_text(encoding="utf-8"))
    assert local["external"] is False and local["api_key_env"] is None
    assert (tmp_path / "models" / "local.json").stat().st_mode & 0o077 == 0

    # 换回没有密钥的 DeepSeek：这张单刚才的模型结果已存下，重新分析时回放，不再调用模型。
    (tmp_path / "models" / "settings.json").write_text('{"active": "deepseek"}', encoding="utf-8")
    with TestClient(_app(tmp_path)) as http:
        assert http.get("/api/model").json()["usable"] is False
        res = http.post("/api/tickets", headers=HEADERS,
                        files={"bundle": ("SYN-X04.zip", _zip_dir(bundle), "application/zip")})
        assert res.status_code == 202
        done = _wait(http, "SYN-X04")
        assert done["status"] == "ready", done.get("problems")
        assert AnalysisResult.model_validate(done["analysis"]).elements.cause.value == "市政道路施工挖断 24 芯光缆"
    assert calls == ["facts", "facts", "writing"]


def test_keys_stay_in_memory_and_are_never_echoed(tmp_path: Path):
    secret = "sk-test-0123456789abcdef"
    with TestClient(_app(tmp_path)) as http:
        assert http.post("/api/model/key", headers=HEADERS, json={"profile": "deepseek", "key": "has space"}).status_code == 400
        assert http.post("/api/model/key", headers=HEADERS, json={"profile": "nope", "key": secret}).status_code == 400
        res = http.post("/api/model/key", headers=HEADERS, json={"profile": "deepseek", "key": secret})
        assert res.status_code == 200 and secret not in res.text
        body = res.json()
        assert body["deepseek"]["key_set"] is True and body["usable"] is True and body["label"] == "DeepSeek"
        assert secret not in http.get("/api/model").text
        cleared = http.post("/api/model/key/clear", headers=HEADERS, json={"profile": "deepseek"}).json()
        assert cleared["deepseek"]["key_set"] is False and cleared["usable"] is False
        assert http.post("/api/model/active", headers=HEADERS, json={"profile": "local"}).status_code == 400
    for path in (tmp_path / "models").rglob("*") if (tmp_path / "models").exists() else ():
        assert secret not in path.read_text(encoding="utf-8")


def test_real_ticket_is_not_sent_to_a_model_that_does_not_allow_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    config = tmp_path / "synthetic-only.json"
    data = json.loads(DEEPSEEK.read_text(encoding="utf-8")) | {"allowed_data": ["synthetic"]}
    config.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-not-used")
    real = _copy_as("SYN-S01", "REAL01", tmp_path / "src", data_class="real")
    app = create_app(inbox=tmp_path / "inbox", model_config=config, settings_dir=tmp_path / "models",
                     replay_patterns=[], workbench_origins="")
    with TestClient(app) as http:
        blocked = http.post("/api/tickets", headers=HEADERS,
                            files={"bundle": ("REAL01.zip", _zip_dir(real), "application/zip")})
        assert blocked.status_code == 400
        assert any("real" in item for item in blocked.json()["problems"])
        assert "REAL01" not in [t["ticket_ref"] for t in http.get("/api/tickets").json()["tickets"]]
    assert not (tmp_path / "inbox" / "upload" / "REAL01").exists()


def test_restart_restores_results_without_calling_the_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def boom(*_args, **_kwargs):
        calls.append("analyze_with_context")
        raise AssertionError("重启后不应再次分析")

    monkeypatch.setattr("noc7.web.jobs.analyze_with_context", boom)
    inbox = tmp_path / "inbox"
    ready_home = inbox / "upload" / "SYN-S01"
    shutil.copytree(BUNDLES / "SYN-S01", ready_home / "bundle")
    (ready_home / "meta.json").write_text(json.dumps({"source": "local", "mode": "live", "model_label": "实时调用 DeepSeek",
                                                      "finished_at": "2026-11-16T10:00:00+08:00"}), encoding="utf-8")
    write_reports(analyze(ready_home / "bundle"), ready_home / "out")
    failed_home = inbox / "upload" / "SYN-S03"
    shutil.copytree(BUNDLES / "SYN-S03", failed_home / "bundle")
    (failed_home / "meta.json").write_text(json.dumps({"source": "upload", "mode": "live"}), encoding="utf-8")
    (failed_home / "failure.json").write_text(json.dumps(
        {"issues": [{"code": "quote_not_found", "severity": "error", "message": "引文对不上"}], "problems": ["引文对不上"]},
        ensure_ascii=False), encoding="utf-8")

    def run_once() -> JobRunner:
        runner = JobRunner(inbox, ModelSettings(DEEPSEEK, tmp_path / "models"),
                           ReplayIndex([]), replay_config=DEEPSEEK)
        runner.start()
        return runner

    run_once().stop()
    second = run_once()
    try:
        ready, failed = second.jobs["SYN-S01"], second.jobs["SYN-S03"]
        assert ready.status == "ready" and ready.result is not None
        assert ready.source == "local" and ready.model_label == "实时调用 DeepSeek"
        assert ready.finished_at == "2026-11-16T10:00:00+08:00"
        assert failed.status == "failed" and failed.problems == ["引文对不上"]
        assert calls == []
    finally:
        second.stop()


def test_local_bundles_listed_in_order(tmp_path: Path, fake_model):
    base_url, calls = fake_model
    first, second = tmp_path / "real", tmp_path / "batch2"
    _copy_as("SYN-P04", "SYN-X04", first)
    _copy_as("SYN-P04", "SYN-Y04", first)
    (first / "not-a-bundle").mkdir()
    _copy_as("SYN-P04", "SYN-X04", second)  # 同一编号在后面的目录里重复：只列一次
    _copy_as("SYN-P04", "SYN-Z04", second)
    app = _app(tmp_path, local_roots=[first, second, tmp_path / "nowhere"])
    with TestClient(app) as http:
        listing = http.get("/api/local-bundles").json()
        assert [b["key"] for b in listing["bundles"]] == ["0/SYN-X04", "0/SYN-Y04", "1/SYN-Z04"]
        assert str(tmp_path) not in json.dumps(listing)
        assert not any(b["has_replay"] for b in listing["bundles"])

        assert http.post("/api/local-bundles/analyze", headers=HEADERS, json={"keys": [], "mode": "live"}).status_code == 400
        none = http.post("/api/local-bundles/analyze", headers=HEADERS, json={"keys": ["0/SYN-X04"], "mode": "replay"}).json()
        assert none["accepted"] == [] and "不能回放" in none["rejected"][0]["problems"][0]

        http.post("/api/model/local", headers=HEADERS, json=_local_fields(base_url))
        http.post("/api/model/active", headers=HEADERS, json={"profile": "local"})
        res = http.post("/api/local-bundles/analyze", headers=HEADERS,
                        json={"keys": ["0/SYN-X04", "1/SYN-Z04", "0/../SYN-X04", "9/SYN-X04", "0/missing", "2/SYN-X04"],
                              "mode": "live"})
        assert res.status_code == 202
        body = res.json()
        assert body["accepted"] == ["SYN-X04", "SYN-Z04"]
        assert [r["key"] for r in body["rejected"]] == ["0/../SYN-X04", "9/SYN-X04", "0/missing", "2/SYN-X04"]
        for ref in body["accepted"]:
            assert _wait(http, ref)["status"] == "ready"
        tickets = {t["ticket_ref"]: t for t in http.get("/api/tickets").json()["tickets"]}
        assert tickets["SYN-X04"]["source"] == "local" and tickets["SYN-X04"]["mode"] == "live"
        status = {b["key"]: (b["status"], b["has_replay"]) for b in http.get("/api/local-bundles").json()["bundles"]}
        assert status == {"0/SYN-X04": ("ready", True), "0/SYN-Y04": ("new", False), "1/SYN-Z04": ("ready", True)}
        assert calls.count("writing") == 2

        # 模型还配着，也可以选回放：用刚存下的结果，不再调用模型；选实时则再调用一次。
        again = http.post("/api/local-bundles/analyze", headers=HEADERS, json={"keys": ["0/SYN-X04"], "mode": "replay"})
        assert again.json()["accepted"] == ["SYN-X04"]
        assert _wait(http, "SYN-X04")["status"] == "ready"
        ticket = next(t for t in http.get("/api/tickets").json()["tickets"] if t["ticket_ref"] == "SYN-X04")
        assert ticket["mode"] == "replay" and ticket["model_label"] == REPLAY_LABEL
        assert calls.count("writing") == 2
        http.post("/api/local-bundles/analyze", headers=HEADERS, json={"keys": ["0/SYN-X04"], "mode": "live"})
        assert _wait(http, "SYN-X04")["status"] == "ready"
    assert calls.count("writing") == 3
