import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

from noc7.extract.pipeline import analyze_with_context
from noc7.providers.text_config import TextModelConfig
from tests.a1.conftest import text_registry

ROOT = Path(__file__).resolve().parents[2]
BUNDLES = ROOT / "fixtures/bundles"


def envelope(data, *, finish="stop"):
    return json.dumps({"choices": [{"finish_reason": finish, "message": {
        "role": "assistant", "content": json.dumps(data, ensure_ascii=False)
    }}]}, ensure_ascii=False).encode()


@pytest.fixture(scope="session")
def sample():
    _, ctx, extraction = analyze_with_context(BUNDLES / "SYN-S01", registry=text_registry())
    data = extraction.model_dump(mode="json")
    refs = set(extraction.elements.iter_evidence_refs())
    refs.update(r for event in extraction.events for r in event.evidence_refs)
    if extraction.service_identity:
        refs.update(r for ident in extraction.service_identity.identifiers for r in ident.evidence_refs)
    data["quotes"] = [
        {"evidence_id": span.id, "quote": span.text} for span in ctx.evidence if span.id in refs
    ]
    return ctx, data


@pytest.fixture
def server(sample):
    state = SimpleNamespace(requests=[], replies=[], default=envelope(sample[1]))

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            state.requests.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(body)})
            status, headers, raw = state.replies.pop(0) if state.replies else (200, {}, state.default)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    state.base_url = f"http://127.0.0.1:{httpd.server_port}/v1"
    yield state
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=1)


def qwen_config(server, **updates):
    data = dict(name="qwen", base_url=server.base_url, model="qwen-test", external=False,
                allowed_data=["synthetic", "real"], max_request_bytes=524288, max_tokens=16384)
    data.update(updates)
    return TextModelConfig.model_validate(data)


def write_config(path, config):
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    return str(path)
