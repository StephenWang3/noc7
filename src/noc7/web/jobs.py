"""进程内一次只分析一张工单。预先放好的五张用规则；导入的包可选规则或模型。"""

from __future__ import annotations

import io
import json
import os
import queue
import re
import shutil
import stat
import threading
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from ..bundle import BundleError, load_bundle
from ..extract.pipeline import analyze, analyze_with_context
from ..providers.gate import EgressBlocked
from ..providers.text_config import TextProviderError, create_text_provider
from ..report import write_reports
from ..report.company import ReportProfile, build_company_report
from ..rules import ExtractionRejected
from ..schema import ELEMENT_LABELS_ZH, AnalysisResult

PREPARED = ("SYN-P04", "SYN-S09", "SYN-P01", "SYN-S06", "SYN-S02")
MAX_ZIP_BYTES = 32 * 1024 * 1024
MAX_UNPACKED_BYTES = 64 * 1024 * 1024
MAX_FILES = 200
BUNDLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
NO_PROFILE = ReportProfile()


class UploadRejected(Exception):
    def __init__(self, status_code: int, problems: list[str]):
        self.status_code = status_code
        self.problems = problems
        super().__init__("；".join(problems))


@dataclass
class Job:
    ref: str
    provider: str
    bundle_dir: Path
    home: Path
    out_dir: Path
    summary: dict
    data_class: str
    prepared: bool
    status: str = "running"
    result: AnalysisResult | None = None
    issues: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


class JobRunner:
    def __init__(self, inbox: Path, bundles: Path, model_config: Path):
        self.inbox = inbox.expanduser().resolve()
        self.bundles = bundles
        self.model_config = model_config
        self.jobs: dict[str, Job] = {}
        self.order: list[str] = []
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._started = False

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self.inbox.mkdir(parents=True, mode=0o700, exist_ok=True)
            for ref in PREPARED:
                bundle = self.bundles / ref
                home = self.inbox / "prepared" / ref
                home.mkdir(parents=True, mode=0o700, exist_ok=True)
                self._add(self._make(ref, "rules", bundle, home, prepared=True))
                self._queue.put(ref)
            self._restore_uploads()
            self._thread = threading.Thread(target=self._loop, name="noc7-demo", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=5)

    def list_tickets(self) -> list[dict]:
        with self._lock:
            return [self._public(self.jobs[ref]) for ref in self.order if ref in self.jobs]

    def detail(self, ref: str) -> dict | None:
        with self._lock:
            job = self.jobs.get(ref)
            if job is None:
                return None
            body = {"status": job.status, "ticket": dict(job.summary)}
            if job.status == "failed":
                body["issues"] = list(job.issues)
                body["problems"] = list(job.problems)
                return body
            if job.status != "ready" or job.result is None:
                return body
            result = job.result
        body["analysis"] = result.model_dump(mode="json")
        body["company_report"] = _company_payload(result)
        body["downloads"] = {
            "docx": f"/api/tickets/{ref}/company-report.docx",
            "html": f"/api/tickets/{ref}/company-report.html",
        }
        return body

    def report_file(self, ref: str, name: str) -> Path | None:
        with self._lock:
            job = self.jobs.get(ref)
            if job is None or job.status != "ready":
                return None
            path = (job.out_dir / name).resolve()
            root = job.out_dir.resolve()
        if not path.is_file() or root not in path.parents:
            return None
        return path

    def accept_upload(self, data: bytes, provider: str) -> str:
        if provider not in {"rules", "llm"}:
            raise UploadRejected(400, ["provider 只能是 rules 或 llm"])
        if len(data) > MAX_ZIP_BYTES:
            raise UploadRejected(400, ["压缩包超过 32 MiB"])
        tmp = self.inbox / "tmp" / uuid.uuid4().hex
        try:
            root = _extract_zip(data, tmp)
            try:
                bundle = load_bundle(root)
            except BundleError as e:
                raise UploadRejected(400, list(e.problems)) from None
            ref = bundle.manifest.bundle_id
            if not BUNDLE_ID.fullmatch(ref):
                raise UploadRejected(400, ["工单包编号只能包含字母、数字、点、下划线和连字符，且不超过 64 个字符"])
            if ref in PREPARED:
                raise UploadRejected(409, ["这个编号是预先放好的合成单，不能覆盖"])
            with self._lock:
                current = self.jobs.get(ref)
                if current is not None and current.status == "running":
                    raise UploadRejected(409, ["这张工单正在分析"])
            if provider == "llm":
                self._preflight(bundle.manifest.data_class)
            home = self.inbox / "upload" / ref
            if home.exists():
                shutil.rmtree(home)
            home.mkdir(parents=True, mode=0o700)
            shutil.copytree(root, home / "bundle")
            (home / "meta.json").write_text(
                json.dumps({"provider": provider}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.chmod(home / "meta.json", 0o600)
            job = self._make(ref, provider, home / "bundle", home, prepared=False)
            with self._lock:
                if ref in self.order:
                    self.order.remove(ref)
                self._add(job)
                self._queue.put(ref)
            return ref
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _preflight(self, data_class) -> None:
        try:
            create_text_provider(self.model_config).preflight(data_class)
        except (EgressBlocked, TextProviderError) as e:
            raise UploadRejected(400, [str(e)]) from None

    def _restore_uploads(self) -> None:
        root = self.inbox / "upload"
        if not root.is_dir():
            return
        for home in sorted(p for p in root.iterdir() if p.is_dir()):
            bundle_dir = home / "bundle"
            meta_path = home / "meta.json"
            if not (bundle_dir / "manifest.json").is_file() or not meta_path.is_file():
                continue
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                provider = meta.get("provider") if meta.get("provider") in {"rules", "llm"} else "rules"
                bundle = load_bundle(bundle_dir)
            except (OSError, json.JSONDecodeError, BundleError, ValueError):
                continue
            ref = bundle.manifest.bundle_id
            if ref in PREPARED or ref in self.jobs or not BUNDLE_ID.fullmatch(ref):
                continue
            job = self._make(ref, provider, bundle_dir, home, prepared=False)
            if self._restore_terminal(job, bundle.manifest_sha256):
                self._add(job)
                continue
            if provider == "llm":
                try:
                    self._preflight(bundle.manifest.data_class)
                except UploadRejected as e:
                    job.status = "failed"
                    job.problems = list(e.problems)
                    self._add(job)
                    continue
            self._add(job)
            self._queue.put(ref)

    def _restore_terminal(self, job: Job, sha: str) -> bool:
        """模型单已有终态就装回来。没有终态（请求中途退出）返回 False，由调用方重新入队。"""
        if job.provider != "llm":
            return False
        ready = _load_ready(job.out_dir / "analysis.json", sha)
        if ready is not None:
            job.result = ready
            job.status = "ready"
            job.issues = []
            job.problems = []
            return True
        failed = _load_failure(job.home / "failure.json")
        if failed is None:
            return False
        job.result = None
        job.status = "failed"
        job.issues = failed["issues"]
        job.problems = failed["problems"] or [item["message"] for item in failed["issues"]]
        return True

    def _make(self, ref: str, provider: str, bundle_dir: Path, home: Path, *, prepared: bool) -> Job:
        summary = _summary(bundle_dir, ref)
        data_class = "synthetic"
        try:
            manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
            data_class = manifest.get("data_class") or data_class
        except (OSError, json.JSONDecodeError):
            pass
        return Job(
            ref=ref,
            provider=provider,
            bundle_dir=bundle_dir,
            home=home,
            out_dir=home / "out",
            summary=summary,
            data_class=data_class,
            prepared=prepared,
        )

    def _add(self, job: Job) -> None:
        self.jobs[job.ref] = job
        if job.ref not in self.order:
            self.order.append(job.ref)

    def _public(self, job: Job) -> dict:
        item = dict(job.summary)
        item["status"] = job.status
        item["data_class"] = job.data_class
        item["provider"] = job.provider
        if job.status == "ready" and job.result is not None:
            elements = job.result.model_dump(mode="json")["elements"]
            item["element_status"] = {
                name.value: elements[name.value]["status"] for name in ELEMENT_LABELS_ZH
            }
            item["open_issues"] = sum(1 for i in job.result.issues if i.severity != "info")
        if job.status == "failed":
            item["problems"] = list(job.problems) or [i["message"] for i in job.issues]
            item["issues"] = list(job.issues)
        return item

    def _loop(self) -> None:
        while True:
            ref = self._queue.get()
            if ref is None:
                return
            with self._lock:
                job = self.jobs.get(ref)
                if job is None or job.status != "running":
                    continue
            self._execute(job)

    def _execute(self, job: Job) -> None:
        try:
            if job.out_dir.exists():
                shutil.rmtree(job.out_dir)
            if job.provider == "llm":
                audit = job.home / "audit" / uuid.uuid4().hex
                provider = create_text_provider(self.model_config, audit_dir=audit)
                result, _, _ = analyze_with_context(job.bundle_dir, provider)
            else:
                result = analyze(job.bundle_dir)
            write_reports(result, job.out_dir, profile=NO_PROFILE)
            html_path = job.out_dir / "company_report.html"
            html_path.write_text(
                html_path.read_text(encoding="utf-8").replace(
                    'href="report.html"', 'href="review-report.html"'
                ),
                encoding="utf-8",
            )
            _clear_failure(job.home / "failure.json")
        except ExtractionRejected as e:
            self._fail(job, issues=[
                {"code": i.code.value, "severity": i.severity.value, "message": i.message}
                for i in e.issues
            ])
            return
        except (TextProviderError, EgressBlocked, BundleError) as e:
            problems = list(e.problems) if isinstance(e, BundleError) else [str(e)]
            self._fail(job, problems=problems)
            return
        except Exception:
            self._fail(job, problems=["分析没有完成，没有生成报告。"])
            return
        with self._lock:
            job.result = result
            job.status = "ready"
            job.issues = []
            job.problems = []

    def _fail(self, job: Job, *, issues: list[dict] | None = None, problems: list[str] | None = None) -> None:
        recorded_issues = issues or []
        recorded_problems = problems or [i["message"] for i in recorded_issues]
        if job.out_dir.exists():
            shutil.rmtree(job.out_dir, ignore_errors=True)
        if job.provider == "llm":
            _write_failure(job.home / "failure.json", recorded_issues, recorded_problems)
        with self._lock:
            job.result = None
            job.status = "failed"
            job.issues = recorded_issues
            job.problems = recorded_problems


def _load_ready(path: Path, sha: str) -> AnalysisResult | None:
    if not path.is_file():
        return None
    try:
        result = AnalysisResult.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if result.run.bundle_sha256 != sha:
        return None
    return result


def _load_failure(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    raw_issues = data.get("issues") if isinstance(data.get("issues"), list) else []
    raw_problems = data.get("problems") if isinstance(data.get("problems"), list) else []
    issues = [
        item for item in raw_issues
        if isinstance(item, dict) and isinstance(item.get("message"), str) and item["message"]
    ]
    problems = [item for item in raw_problems if isinstance(item, str) and item]
    if not issues and not problems:
        return None
    return {"issues": issues, "problems": problems}


def _write_failure(path: Path, issues: list[dict], problems: list[str]) -> None:
    path.write_text(
        json.dumps({"issues": issues, "problems": problems}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.chmod(path, 0o600)


def _clear_failure(path: Path) -> None:
    if path.is_file():
        path.unlink()


def _summary(bundle_dir: Path, ref: str) -> dict:
    title, category, list_status = ref, None, ""
    try:
        ticket = json.loads((bundle_dir / "ticket.json").read_text(encoding="utf-8"))
        title = ticket.get("title") or ref
        category = ticket.get("category")
        list_status = (ticket.get("status") or {}).get("list_status") or ""
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return {
        "ticket_ref": ref,
        "title": title,
        "category": category,
        "list_status": list_status,
    }


def _company_payload(result: AnalysisResult) -> dict:
    report = build_company_report(result)
    return {
        "ticket_ref": report.ticket_ref,
        "report_date": report.report_date,
        "synthetic": report.synthetic,
        "cells": [
            {
                "row": cell.row,
                "col": cell.col,
                "rowspan": cell.rowspan,
                "colspan": cell.colspan,
                "label": cell.label,
                "lines": [
                    [{"text": part.text, "pending": part.pending} for part in line]
                    for line in cell.lines
                ],
            }
            for cell in report.grid()
        ],
    }


def _extract_zip(data: bytes, dest: Path) -> Path:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise UploadRejected(400, ["不是有效的 zip"]) from None
    infos = archive.infolist()
    if len(infos) > MAX_FILES:
        raise UploadRejected(400, ["压缩包内文件过多"])
    total = 0
    dest.mkdir(parents=True, mode=0o700)
    for info in infos:
        name = info.filename.replace("\\", "/")
        parts = Path(name).parts
        if not name or name.startswith("/") or ".." in parts:
            raise UploadRejected(400, ["压缩包路径不安全"])
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise UploadRejected(400, ["压缩包内不允许符号链接"])
        if info.is_dir():
            continue
        total += info.file_size
        if total > MAX_UNPACKED_BYTES:
            raise UploadRejected(400, ["解压后超过大小限制"])
        target = (dest / name).resolve()
        if dest.resolve() not in target.parents:
            raise UploadRejected(400, ["压缩包路径不安全"])
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as src, target.open("wb") as out:
            shutil.copyfileobj(src, out)
    manifests = [
        path for path in dest.rglob("manifest.json")
        if path.is_file() and not path.is_symlink()
    ]
    if len(manifests) != 1:
        raise UploadRejected(400, ["压缩包里必须恰好有一份工单包（一份 manifest.json）"])
    return manifests[0].parent
