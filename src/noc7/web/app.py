"""演示页和工单接口。页面只通过工单号取结果，不从 NOC 拉数。"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..schema import ELEMENT_LABELS_ZH
from .jobs import BUNDLE_ID, PREPARED, JobRunner, UploadRejected

STATIC = Path(__file__).resolve().parent / "static"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def create_app(
    *,
    inbox: Path | None = None,
    bundles: Path | None = None,
    model_config: Path | None = None,
    workbench_origins: str | None = None,
) -> FastAPI:
    inbox = inbox or Path(os.environ.get("NOC7_DEMO_INBOX", "~/.noc7/demo-inbox"))
    bundles = bundles or Path("fixtures/bundles")
    model_config = model_config or Path("config/models/deepseek.json")
    origins = workbench_origins
    if origins is None:
        origins = os.environ.get("NOC7_WORKBENCH_ORIGINS", "")
    runner = JobRunner(inbox, bundles, model_config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runner.start()
        yield
        runner.stop()

    app = FastAPI(title="NOC 工单预处理", lifespan=lifespan)
    app.state.jobs = runner
    app.state.workbench_origins = [p.strip() for p in origins.split(",") if p.strip()]

    @app.get("/api/tickets")
    def list_tickets():
        return {
            "element_labels": {name.value: label for name, label in ELEMENT_LABELS_ZH.items()},
            "workbench_origins": list(app.state.workbench_origins),
            "prepared": list(PREPARED),
            "tickets": runner.list_tickets(),
        }

    @app.get("/api/tickets/{ref}")
    def ticket(ref: str):
        if not BUNDLE_ID.fullmatch(ref):
            return JSONResponse(status_code=404, content={"status": "failed", "problems": ["没有这张工单"]})
        body = runner.detail(ref)
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
    async def upload(bundle: UploadFile = File(...), provider: str = Form("rules")):
        data = await bundle.read()
        try:
            ref = runner.accept_upload(data, provider)
        except UploadRejected as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"status": "failed", "problems": e.problems},
            )
        return JSONResponse(status_code=202, content={"status": "running", "ticket_ref": ref})

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="demo")
    return app


def _report(runner: JobRunner, ref: str, name: str, download: str, media_type: str):
    if not BUNDLE_ID.fullmatch(ref):
        return JSONResponse(status_code=404, content={"status": "failed", "problems": ["没有这张工单"]})
    path = runner.report_file(ref, name)
    if path is None:
        return JSONResponse(status_code=404, content={"status": "failed", "problems": ["报告还没有生成"]})
    return FileResponse(path, media_type=media_type, filename=download)
