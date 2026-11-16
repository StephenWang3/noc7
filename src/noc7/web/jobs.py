"""操作台的分析队列。一律“模型 + 规则”：配好模型就实时调用，没配但保存过这张单的模型结果就回放，
两样都没有就请人先配置模型。进程内一次只分析一张。

演示单（仓库里的合成单、本机挑出的几张真实单）一律回放保存的模型结果，不联网、不花钱。
"""

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
from datetime import datetime, timezone
from pathlib import Path

from ..bundle import BundleError, load_bundle, sha256_file
from ..extract.pipeline import analyze_with_context
from ..providers.gate import EgressBlocked
from ..providers.text_config import TextProviderError, create_text_provider, load_model_config
from ..providers.two_stage import TwoStageTextProvider
from ..providers.two_stage_replay import TwoStageReplayProvider
from ..report import write_reports
from ..report.company import build_company_report
from ..rules import ExtractionRejected
from ..schema import ELEMENT_LABELS_ZH, AnalysisResult
from .models import ModelSettings
from .replays import ReplayIndex

PREPARED = ("SYN-P04", "SYN-S09", "SYN-P01", "SYN-S06", "SYN-S02")
MAX_ZIP_BYTES = 32 * 1024 * 1024
MAX_UNPACKED_BYTES = 64 * 1024 * 1024
MAX_FILES = 200
MAX_BATCH = 50
BUNDLE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
REPLAY_LABEL = "回放已保存的模型结果"
LEGACY_LABELS = {"rules": "仅规则（旧版结果）", "llm": "实时调用 DeepSeek"}
NO_MODEL = ("还没有可用的模型：请点右上角“模型设置”填写密钥，或配置公司本地模型。"
            "这张单也没有保存过的模型结果可以回放。")
REPLAY_MISMATCH = "保存的模型结果和这张单现在的材料对不上，不能回放；请在“模型设置”里配置模型后重新分析。"


class UploadRejected(Exception):
    def __init__(self, status_code: int, problems: list[str]):
        self.status_code = status_code
        self.problems = problems
        super().__init__("；".join(problems))


@dataclass
class Job:
    ref: str
    bundle_dir: Path
    home: Path
    out_dir: Path
    summary: dict
    data_class: str
    sha: str
    source: str  # demo / local / upload
    mode: str  # live / replay
    model_label: str
    status: str = "running"
    finished_at: str | None = None
    result: AnalysisResult | None = None
    issues: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


class JobRunner:
    def __init__(self, inbox: Path, bundles: Path, models: ModelSettings, replays: ReplayIndex, *,
                 replay_config: Path, local_roots: list[Path] = (), demos: list[Path] = ()):
        self.inbox = inbox.expanduser().resolve()
        self.bundles = bundles
        self.models = models
        self.replays = replays
        self.replay_config = replay_config
        self.local_roots = [r.expanduser() for r in local_roots]
        self.demo_dirs = [*(bundles / ref for ref in PREPARED), *(d.expanduser() for d in demos)]
        self.jobs: dict[str, Job] = {}
        self.order: list[str] = []
        self.demo_refs: set[str] = set()
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._started = False

    # ── 启停 ──
    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
        self.inbox.mkdir(parents=True, mode=0o700, exist_ok=True)
        self.replays.scan()
        for bundle_dir in self.demo_dirs:
            self._load_demo(bundle_dir)
        self._restore_uploads()
        self._thread = threading.Thread(target=self._loop, name="noc7-platform", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _load_demo(self, bundle_dir: Path) -> None:
        manifest = _manifest(bundle_dir)
        if manifest is None:
            return
        ref = manifest.get("bundle_id")
        if not isinstance(ref, str) or not BUNDLE_ID.fullmatch(ref) or ref in self.jobs:
            return
        home = self.inbox / "demo" / ref
        home.mkdir(parents=True, mode=0o700, exist_ok=True)
        job = self._make(ref, bundle_dir, home, source="demo", mode="replay", label=REPLAY_LABEL)
        meta = _read_meta(home)
        job.finished_at = meta.get("finished_at") if isinstance(meta.get("finished_at"), str) else None
        with self._lock:
            self.demo_refs.add(ref)
            self._add(job)
        ready = _load_ready(job.out_dir / "analysis.json", job.sha)
        if ready is not None:  # 演示单只恢复成功的结果；失败的每次启动重试（可能已补了记录）
            job.result, job.status = ready, "ready"
            return
        if not self.replays.has(job.sha):
            self._fail(job, problems=["这张演示单还没有保存的模型结果。合成演示单请按使用说明运行 "
                                      "scripts/record_demo_replays.py 生成一次。"])
            return
        self._queue.put(ref)

    # ── 查询 ──
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

    def list_local(self) -> dict:
        """本机导出目录下的工单包，按目录分组；只读清单和工单字段，分析时才完整校验。"""
        groups, seen = [], set()
        for i, root in enumerate(self.local_roots):
            if not root.is_dir():
                continue
            items = []
            for path in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
                manifest = _manifest(path)
                ref = manifest.get("bundle_id") if manifest else None
                if not isinstance(ref, str) or not BUNDLE_ID.fullmatch(ref) or not BUNDLE_ID.fullmatch(path.name):
                    continue
                if ref in seen:
                    continue
                seen.add(ref)
                item = _summary(path, ref) | {"key": f"{i}/{path.name}", "captured_at": manifest.get("captured_at"),
                                              "has_replay": self.replays.has(sha256_file(path / "manifest.json")),
                                              "demo": ref in self.demo_refs}
                with self._lock:
                    job = self.jobs.get(ref)
                    item["status"] = job.status if job else "new"
                items.append(item)
            groups.append({"root": _display(root), "bundles": items})
        return {"available": bool(groups), "groups": groups}

    # ── 入队 ──
    def accept_upload(self, data: bytes) -> str:
        if len(data) > MAX_ZIP_BYTES:
            raise UploadRejected(400, ["压缩包超过 32 MiB"])
        tmp = self.inbox / "tmp" / uuid.uuid4().hex
        try:
            return self._accept(_extract_zip(data, tmp), "upload")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def accept_local(self, keys: list[str]) -> dict:
        """按“目录序号/目录名”把本机工单排进队列。逐张返回结果，一张出错不影响其他。"""
        if not self.local_roots:
            raise UploadRejected(400, ["没有配置本机工单目录"])
        if not keys or len(keys) > MAX_BATCH or not all(isinstance(k, str) for k in keys):
            raise UploadRejected(400, [f"一次选 1 到 {MAX_BATCH} 张工单"])
        accepted, rejected = [], []
        for key in dict.fromkeys(keys):
            index, _, name = key.partition("/")
            path = None
            if index.isdigit() and int(index) < len(self.local_roots) and BUNDLE_ID.fullmatch(name):
                root = self.local_roots[int(index)].resolve()
                candidate = (root / name).resolve()
                path = candidate if candidate.parent == root and candidate.is_dir() else None
            if path is None:
                rejected.append({"key": key, "problems": ["本机工单目录里没有这张工单"]})
                continue
            try:
                accepted.append(self._accept(path, "local"))
            except UploadRejected as e:
                rejected.append({"key": key, "problems": e.problems})
        return {"accepted": accepted, "rejected": rejected}

    def _accept(self, root: Path, source: str) -> str:
        try:
            bundle = load_bundle(root)
        except BundleError as e:
            raise UploadRejected(400, list(e.problems)) from None
        ref = bundle.manifest.bundle_id
        if not BUNDLE_ID.fullmatch(ref):
            raise UploadRejected(400, ["工单包编号只能包含字母、数字、点、下划线和连字符，且不超过 64 个字符"])
        with self._lock:
            if ref in self.demo_refs:
                raise UploadRejected(409, ["这是演示单，直接在“演示单”里查看"])
            current = self.jobs.get(ref)
            if current is not None and current.status == "running":
                raise UploadRejected(409, ["这张工单正在分析"])
        mode, label = self._choose(bundle.manifest_sha256, bundle.manifest.data_class)
        home = self.inbox / "upload" / ref
        home.mkdir(parents=True, mode=0o700, exist_ok=True)
        for old in home.iterdir():  # 清掉上次的包和报告；audit/ 是以前的模型结果，留着以后回放
            if old.name == "audit":
                continue
            if old.is_dir() and not old.is_symlink():
                shutil.rmtree(old)
            else:
                old.unlink()
        shutil.copytree(root, home / "bundle")
        _write_meta(home, {"source": source, "mode": mode, "model_label": label})
        job = self._make(ref, home / "bundle", home, source=source, mode=mode, label=label)
        with self._lock:
            if ref in self.order:
                self.order.remove(ref)
            self._add(job)
            self._queue.put(ref)
        return ref

    def _choose(self, sha: str, data_class) -> tuple[str, str]:
        """配好模型就实时调用；否则有保存的模型结果就回放；都没有就拒绝。"""
        path = self.models.active_path()
        if path is not None:
            try:
                create_text_provider(path).preflight(data_class)
            except (EgressBlocked, TextProviderError) as e:
                raise UploadRejected(400, [str(e)]) from None
            return "live", f"实时调用 {self.models.label()}"
        if self.replays.has(sha):
            return "replay", REPLAY_LABEL
        raise UploadRejected(400, [NO_MODEL])

    def _restore_uploads(self) -> None:
        root = self.inbox / "upload"
        if not root.is_dir():
            return
        for home in sorted(p for p in root.iterdir() if p.is_dir()):
            bundle_dir = home / "bundle"
            manifest = _manifest(bundle_dir)
            meta = _read_meta(home)
            ref = manifest.get("bundle_id") if manifest else None
            if not isinstance(ref, str) or not BUNDLE_ID.fullmatch(ref) or ref in self.jobs:
                continue
            mode = meta.get("mode") if meta.get("mode") in {"live", "replay"} else "replay"
            source = meta.get("source") if meta.get("source") in {"local", "upload"} else "upload"
            label = meta.get("model_label") if isinstance(meta.get("model_label"), str) else REPLAY_LABEL
            if "mode" not in meta and meta.get("provider") in LEGACY_LABELS:  # 旧版操作台留下的结果
                label = LEGACY_LABELS[meta["provider"]]
            job = self._make(ref, bundle_dir, home, source=source, mode=mode, label=label)
            job.finished_at = meta.get("finished_at") if isinstance(meta.get("finished_at"), str) else None
            with self._lock:
                self._add(job)
            if self._restore_terminal(job):
                continue
            try:  # 上次没算完：按现在的模型设置重新决定实时还是回放
                job.mode, job.model_label = self._choose(job.sha, job.data_class)
            except UploadRejected as e:
                self._fail(job, problems=e.problems)
                continue
            self._queue.put(ref)

    def _restore_terminal(self, job: Job) -> bool:
        ready = _load_ready(job.out_dir / "analysis.json", job.sha)
        if ready is not None:
            job.result, job.status, job.issues, job.problems = ready, "ready", [], []
            return True
        failed = _load_failure(job.home / "failure.json")
        if failed is None:
            return False
        job.result, job.status = None, "failed"
        job.issues = failed["issues"]
        job.problems = failed["problems"] or [item["message"] for item in failed["issues"]]
        return True

    def _make(self, ref: str, bundle_dir: Path, home: Path, *, source: str, mode: str, label: str) -> Job:
        manifest = _manifest(bundle_dir) or {}
        try:
            sha = sha256_file(bundle_dir / "manifest.json")
        except OSError:
            sha = ""
        return Job(ref=ref, bundle_dir=bundle_dir, home=home, out_dir=home / "out",
                   summary=_summary(bundle_dir, ref), data_class=manifest.get("data_class") or "synthetic",
                   sha=sha, source=source, mode=mode, model_label=label)

    def _add(self, job: Job) -> None:
        self.jobs[job.ref] = job
        if job.ref not in self.order:
            self.order.append(job.ref)

    def _public(self, job: Job) -> dict:
        item = dict(job.summary)
        item.update(status=job.status, data_class=job.data_class, source=job.source, mode=job.mode,
                    model_label=job.model_label, finished_at=job.finished_at)
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

    # ── 执行 ──
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
            result = self._live(job) if job.mode == "live" else self._replay(job)
            write_reports(result, job.out_dir, report_type="closure")
            html_path = job.out_dir / "company_report.html"
            html_path.write_text(
                html_path.read_text(encoding="utf-8").replace('href="report.html"', 'href="review-report.html"'),
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
        self._finish(job)
        with self._lock:
            job.result, job.status, job.issues, job.problems = result, "ready", [], []

    def _live(self, job: Job) -> AnalysisResult:
        path = self.models.active_path()
        if path is None:
            raise TextProviderError("模型设置变了（密钥被清除或模型未配置），没有调用模型。")
        audit = job.home / "audit" / uuid.uuid4().hex
        provider = create_text_provider(path, audit_dir=audit)
        try:
            result, _, _ = analyze_with_context(job.bundle_dir, provider)
        finally:
            for record in audit.glob("*.json") if audit.is_dir() else ():
                self.replays.add(record)  # 以后不联网也能回放这次的模型结果
        return result

    def _replay(self, job: Job) -> AnalysisResult:
        config = load_model_config(self.replay_config)
        for path in self.replays.candidates(job.sha, TwoStageTextProvider.prompt_version):
            record = self.replays.load(path)
            if record is None:
                continue
            try:
                provider = TwoStageReplayProvider(config, record)
                result, _, _ = analyze_with_context(job.bundle_dir, provider)
            except TextProviderError:
                continue
            return result
        raise TextProviderError(REPLAY_MISMATCH)

    def _finish(self, job: Job) -> None:
        """记下完成时刻并写进 meta.json，重启后分析记录里还能看到。"""
        job.finished_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        meta = _read_meta(job.home)
        _write_meta(job.home, meta | {"finished_at": job.finished_at})

    def _fail(self, job: Job, *, issues: list[dict] | None = None, problems: list[str] | None = None) -> None:
        recorded_issues = issues or []
        recorded_problems = problems or [i["message"] for i in recorded_issues]
        if job.out_dir.exists():
            shutil.rmtree(job.out_dir, ignore_errors=True)
        job.home.mkdir(parents=True, mode=0o700, exist_ok=True)
        _write_failure(job.home / "failure.json", recorded_issues, recorded_problems)
        self._finish(job)
        with self._lock:
            job.result, job.status = None, "failed"
            job.issues, job.problems = recorded_issues, recorded_problems


def _manifest(bundle_dir: Path) -> dict | None:
    try:
        data = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _read_meta(home: Path) -> dict:
    try:
        data = json.loads((home / "meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _display(path: Path) -> str:
    """页面上显示的目录：家目录写成 ~，不把用户名放到页面上。"""
    try:
        return "~/" + path.resolve().relative_to(Path.home().resolve()).as_posix()
    except ValueError:
        return path.name


def _write_meta(home: Path, meta: dict) -> None:
    path = home / "meta.json"
    path.write_text(json.dumps(meta, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


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
