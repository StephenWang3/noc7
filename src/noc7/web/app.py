"""操作台页面和接口。只监听本机；改动类接口要求自定义请求头，别的网站无法跨站调用。"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..schema import ELEMENT_LABELS_ZH
from .jobs import BUNDLE_ID, JobRunner, UploadRejected
from .models import ModelSettings, SettingsRejected
from .replays import ReplayIndex

STATIC = Path(__file__).resolve().parent / "static"
DEMO_REPLAYS = Path(__file__).resolve().parents[3] / "fixtures" / "demo-replays"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
WRITE_HEADER = "x-noc7-request"


def load_platform_config(path: Path) -> dict:
    """~/.noc7/platform.json：本机工单目录和真实演示单，只放在仓库外。"""
    try:
        data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def create_app(
    *,
    inbox: Path | None = None,
    bundles: Path | None = None,
    model_config: Path | None = None,
    settings_dir: Path | None = None,
    local_roots: list[Path] | None = None,
    demos: list[Path] | None = None,
    replay_patterns: list[tuple[Path, str]] | None = None,
    workbench_origins: str | None = None,
) -> FastAPI:
    inbox = (inbox or Path(os.environ.get("NOC7_DEMO_INBOX", "~/.noc7/demo-inbox"))).expanduser()
    bundles = bundles or Path("fixtures/bundles")
    model_config = model_config or Path("config/models/deepseek.json")
    models = ModelSettings(model_config, settings_dir or Path("~/.noc7/models"))
    if replay_patterns is None:
        replay_patterns = [(Path("~/.noc7"), "two-stage-trial-*/*/audit/*.json"),  # 以前的试跑
                           (Path("~/.noc7"), "audit-*/*.json"),  # 命令行 --model-audit-dir ~/.noc7/audit-<日期>
                           (DEMO_REPLAYS, "*.json")]
    replays = ReplayIndex([*replay_patterns, (inbox, "upload/*/audit/*/*.json")])
    runner = JobRunner(inbox, bundles, models, replays, replay_config=model_config,
                       local_roots=list(local_roots or ()), demos=list(demos or ()))
    origins = workbench_origins if workbench_origins is not None else os.environ.get("NOC7_WORKBENCH_ORIGINS", "")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runner.start()
        yield
        runner.stop()

    app = FastAPI(title="NOC 故障报告操作台", lifespan=lifespan)
    app.state.jobs = runner
    app.state.models = models
    app.state.workbench_origins = [p.strip() for p in origins.split(",") if p.strip()]

    @app.middleware("http")
    async def require_write_header(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get(WRITE_HEADER) != "1":
            return JSONResponse(status_code=403, content={"status": "failed", "problems": ["请从操作台页面操作"]})
        return await call_next(request)

    @app.get("/api/tickets")
    def list_tickets():
        return {
            "element_labels": {name.value: label for name, label in ELEMENT_LABELS_ZH.items()},
            "workbench_origins": list(app.state.workbench_origins),
            "tickets": runner.list_tickets(),
        }

    @app.get("/api/tickets/{ref}")
    def ticket(ref: str):
        body = runner.detail(ref) if BUNDLE_ID.fullmatch(ref) else None
        if body is None:
            return JSONResponse(status_code=404, content={"status": "failed", "problems": ["没有这张工单"]})
        return body

    @app.get("/api/tickets/{ref}/company-report.docx")
    def company_docx(ref: str):
        return _report(runner, ref, "company_report.docx", f"{ref}-company-report.docx", DOCX_TYPE)

    @app.get("/api/tickets/{ref}/company-report.html")
    def company_html(ref: str):
        return _report(runner, ref, "company_report.html", f"{ref}-company-report.html", "text/html; charset=utf-8")

    @app.get("/api/tickets/{ref}/review-report.html")
    def review_html(ref: str):
        return _report(runner, ref, "report.html", f"{ref}-review-report.html", "text/html; charset=utf-8")

    @app.post("/api/tickets")
    async def upload(bundle: UploadFile = File(...)):
        data = await bundle.read()
        try:
            ref = runner.accept_upload(data)
        except UploadRejected as e:
            return _rejected(e.status_code, e.problems)
        return JSONResponse(status_code=202, content={"status": "running", "ticket_ref": ref})

    @app.get("/api/local-bundles")
    def local_bundles():
        return runner.list_local()

    @app.post("/api/local-bundles/analyze")
    def analyze_local(body: dict = Body(...)):
        try:
            result = runner.accept_local(body.get("keys") or [])
        except UploadRejected as e:
            return _rejected(e.status_code, e.problems)
        return JSONResponse(status_code=202, content=result)

    @app.get("/api/model")
    def model_state():
        return models.public()

    @app.post("/api/model/key")
    def model_key(body: dict = Body(...)):
        return _settings(models, lambda: models.set_key(str(body.get("profile")), str(body.get("key") or "")))

    @app.post("/api/model/key/clear")
    def model_key_clear(body: dict = Body(...)):
        return _settings(models, lambda: models.clear_key(str(body.get("profile"))))

    @app.post("/api/model/local")
    def model_local(body: dict = Body(...)):
        return _settings(models, lambda: models.save_local(body))

    @app.post("/api/model/active")
    def model_active(body: dict = Body(...)):
        return _settings(models, lambda: models.set_active(str(body.get("profile"))))

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="platform")
    return app


def _settings(models: ModelSettings, action):
    try:
        action()
    except SettingsRejected as e:
        return _rejected(400, [str(e)])
    return models.public()


def _rejected(status: int, problems: list[str]):
    return JSONResponse(status_code=status, content={"status": "failed", "problems": problems})


def _report(runner: JobRunner, ref: str, name: str, download: str, media_type: str):
    if not BUNDLE_ID.fullmatch(ref):
        return _rejected(404, ["没有这张工单"])
    path = runner.report_file(ref, name)
    if path is None:
        return _rejected(404, ["报告还没有生成"])
    return FileResponse(path, media_type=media_type, filename=download)
