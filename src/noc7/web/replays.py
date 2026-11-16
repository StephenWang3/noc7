"""已保存的模型结果索引：按工单包的清单哈希找诊断记录，用来不联网回放“模型 + 规则”的分析。

记录来源：以前试跑的诊断目录、操作台自己实时调用时留下的诊断、仓库里合成演示单的记录。
启动时只读每份记录开头的几百字节取哈希和提示词版本，用到时才完整读取。
"""

from __future__ import annotations

import json
import re
import threading
from pathlib import Path

HEAD = re.compile(r'"bundle_sha256"\s*:\s*"([0-9a-f]{64})".*?"prompt_version"\s*:\s*"([^"]*)"', re.S)


class ReplayIndex:
    def __init__(self, patterns: list[tuple[Path, str]]):
        """patterns：(目录, glob) 列表，如 (~/.noc7, "two-stage-trial-*/*/audit/*.json")。"""
        self.patterns = [(root.expanduser(), glob) for root, glob in patterns]
        self._by_sha: dict[str, list[tuple[float, str, Path]]] = {}
        self._lock = threading.Lock()

    def scan(self) -> None:
        found: dict[str, list[tuple[float, str, Path]]] = {}
        for root, glob in self.patterns:
            if not root.is_dir():
                continue
            for path in root.glob(glob):
                entry = _head(path)
                if entry:
                    found.setdefault(entry[0], []).append((path.stat().st_mtime, entry[1], path))
        with self._lock:
            self._by_sha = found

    def add(self, path: Path) -> None:
        entry = _head(path)
        if not entry:
            return
        with self._lock:
            self._by_sha.setdefault(entry[0], []).append((path.stat().st_mtime, entry[1], path))

    def has(self, sha: str) -> bool:
        with self._lock:
            return bool(self._by_sha.get(sha))

    def candidates(self, sha: str, prompt_version: str | None = None) -> list[Path]:
        """当前提示词版本的记录优先，其次按时间从新到旧。"""
        with self._lock:
            items = list(self._by_sha.get(sha, ()))
        items.sort(key=lambda x: (x[1] == prompt_version, x[0]), reverse=True)
        return [p for _, _, p in items]

    def load(self, path: Path) -> dict | None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or data.get("outcome") != "accepted":
            return None
        return data


def _head(path: Path) -> tuple[str, str] | None:
    try:
        if not path.is_file() or path.is_symlink():
            return None
        with path.open("r", encoding="utf-8", errors="replace") as f:
            text = f.read(2048)
    except OSError:
        return None
    m = HEAD.search(text)
    return (m.group(1), m.group(2)) if m else None
