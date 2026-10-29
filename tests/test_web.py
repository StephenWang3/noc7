"""演示服务：五张合成单、工单包上传、闸门拒绝。单测不访问网络。"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from noc7.extract.pipeline import analyze
from noc7.schema import AnalysisResult
from noc7.web.app import create_app
from noc7.web.jobs import PREPARED

ROOT = Path(__file__).resolve().parents[1]
BUNDLES = ROOT / "fixtures" / "bundles"
SYNTHETIC_MODEL = {
    "name": "deepseek",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-flash",
    "api_key_env": "DEEPSEEK_API_KEY",
    "external": True,
    "allowed_data": ["synthetic"],
    "json_mode": True,
    "thinking_mode": "disabled",
    "max_request_bytes": 524288,
    "max_tokens": 1024,
    "timeout_seconds": 30,
    "max_retries": 0,
}


def _zip_dir(path: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        for item in path.rglob("*"):
            if item.is_file():
                archive.write(item, item.relative_to(path).as_posix())
    return buf.getvalue()


def _wait(client: TestClient, ref: str, timeout: float = 240) -> dict:
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/api/tickets/{ref}")
        assert response.status_code == 200
        last = response.json()
        if last["status"] in {"ready", "failed"}:
            return last
        time.sleep(0.4)
    raise AssertionError(f"{ref} 在 {timeout}s 内没有完成：{last}")


@pytest.fixture
def client(tmp_path: Path):
    config = tmp_path / "model.json"
    config.write_text(json.dumps(SYNTHETIC_MODEL), encoding="utf-8")
    app = create_app(
        inbox=tmp_path / "inbox",
        bundles=BUNDLES,
        model_config=config,
        workbench_origins="",
    )
    with TestClient(app) as http:
        yield http


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


def test_demo_service(client: TestClient, tmp_path: Path):
    listed = client.get("/api/tickets")
    assert listed.status_code == 200
    body = listed.json()
    assert [item["ticket_ref"] for item in body["tickets"]] == list(PREPARED)
    assert body["element_labels"]["location"] == "故障地点"

    missing = client.post(
        "/api/tickets",
        files={"bundle": ("empty.zip", io.BytesIO(b"not-a-zip"), "application/zip")},
        data={"provider": "rules"},
    )
    assert missing.status_code == 400
    assert missing.json()["status"] == "failed"
    assert [item["ticket_ref"] for item in client.get("/api/tickets").json()["tickets"]] == list(PREPARED)

    reserved = client.post(
        "/api/tickets",
        files={"bundle": ("SYN-S09.zip", _zip_dir(BUNDLES / "SYN-S09"), "application/zip")},
        data={"provider": "rules"},
    )
    assert reserved.status_code == 409

    prepared = _wait(client, "SYN-P04")
    assert prepared["status"] == "ready"
    direct = analyze(BUNDLES / "SYN-P04")
    assert prepared["analysis"]["elements"]["location"]["status"] == direct.elements.location.status.value
    assert prepared["analysis"]["elements"]["location"]["status"] == "conflicted"
    AnalysisResult.model_validate(prepared["analysis"])

    uploaded = client.post(
        "/api/tickets",
        files={"bundle": ("SYN-S01.zip", _zip_dir(BUNDLES / "SYN-S01"), "application/zip")},
        data={"provider": "rules"},
    )
    assert uploaded.status_code == 202
    assert uploaded.json()["ticket_ref"] == "SYN-S01"
    done = _wait(client, "SYN-S01")
    assert done["status"] == "ready"
    result = AnalysisResult.model_validate(done["analysis"])
    assert result.run.provider == "rules"
    assert result.suggestions == []
    docx = client.get("/api/tickets/SYN-S01/company-report.docx")
    assert docx.status_code == 200
    assert docx.content.startswith(b"PK")
    html = client.get("/api/tickets/SYN-S01/company-report.html")
    assert html.status_code == 200
    assert 'href="review-report.html"' in html.text
    assert client.get("/api/tickets/SYN-S01/review-report.html").status_code == 200

    real_dir = tmp_path / "REAL01"
    shutil.copytree(BUNDLES / "SYN-S01", real_dir)
    manifest_path = real_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["bundle_id"] = "REAL01"
    manifest["data_class"] = "real"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    blocked = client.post(
        "/api/tickets",
        files={"bundle": ("REAL01.zip", _zip_dir(real_dir), "application/zip")},
        data={"provider": "llm"},
    )
    assert blocked.status_code == 400
    blocked_body = blocked.json()
    assert blocked_body["status"] == "failed"
    assert any("real" in item for item in blocked_body["problems"])
    refs = [item["ticket_ref"] for item in client.get("/api/tickets").json()["tickets"]]
    assert "REAL01" not in refs
    assert not (tmp_path / "inbox" / "upload" / "REAL01" / "out").exists()
