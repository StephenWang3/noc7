"""操作台的模型设置：用哪个模型、密钥、公司本地模型的地址。

密钥只放在本服务进程的内存（进程环境变量）里，不写文件、不回显、不进日志；服务停了就没了。
模型地址等非敏感设置写在仓库外的 ~/.noc7/models/。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from ..providers.text_config import TextModelConfig, TextProviderError, load_model_config

DEEPSEEK = "deepseek"
LOCAL = "local"
PROFILES = (DEEPSEEK, LOCAL)
LABELS = {DEEPSEEK: "DeepSeek", LOCAL: "公司本地模型"}
LOCAL_KEY_ENV = "NOC7_LOCAL_MODEL_KEY"
MAX_KEY_LENGTH = 512


class SettingsRejected(ValueError):
    pass


class ModelSettings:
    def __init__(self, deepseek_config: Path, settings_dir: Path):
        self.deepseek_config = deepseek_config
        self.dir = settings_dir.expanduser()
        self._lock = threading.Lock()
        self.active = self._read_settings().get("active", DEEPSEEK)
        if self.active not in PROFILES:
            self.active = DEEPSEEK

    # ── 读 ──
    @property
    def local_config(self) -> Path:
        return self.dir / "local.json"

    def config_path(self, profile: str) -> Path:
        return self.deepseek_config if profile == DEEPSEEK else self.local_config

    def config(self, profile: str) -> TextModelConfig | None:
        path = self.config_path(profile)
        if not path.is_file():
            return None
        try:
            return load_model_config(path)
        except TextProviderError:
            return None

    def key_set(self, profile: str) -> bool:
        config = self.config(profile)
        env = config.api_key_env if config else (LOCAL_KEY_ENV if profile == LOCAL else "DEEPSEEK_API_KEY")
        return bool(env and os.environ.get(env, "").strip())

    def usable(self, profile: str | None = None) -> bool:
        profile = profile or self.active
        config = self.config(profile)
        if config is None or config.pipeline != "two_stage":
            return False
        return config.api_key_env is None or self.key_set(profile)

    def active_path(self) -> Path | None:
        return self.config_path(self.active) if self.usable() else None

    def label(self, profile: str | None = None) -> str:
        return LABELS[profile or self.active]

    def public(self) -> dict:
        local = self.config(LOCAL)
        deepseek = self.config(DEEPSEEK)
        return {
            "active": self.active,
            "usable": self.usable(),
            "label": self.label(),
            "deepseek": {
                "configured": deepseek is not None,
                "model": deepseek.model if deepseek else None,
                "key_set": self.key_set(DEEPSEEK),
            },
            "local": {
                "configured": local is not None,
                "base_url": local.base_url if local else "",
                "model": local.model if local else "",
                "needs_key": bool(local and local.api_key_env),
                "key_set": self.key_set(LOCAL),
                "max_request_kb": (local.max_request_bytes // 1024) if local else 512,
                "max_tokens": local.max_tokens if local else 8192,
                "json_mode": local.json_mode if local else False,
            },
        }

    # ── 写 ──
    def set_key(self, profile: str, key: str) -> None:
        if profile not in PROFILES:
            raise SettingsRejected("没有这个模型")
        key = (key or "").strip()
        if not key or len(key) > MAX_KEY_LENGTH or any(c.isspace() or ord(c) < 33 for c in key):
            raise SettingsRejected("密钥格式不对")
        config = self.config(profile)
        env = config.api_key_env if config else None
        if profile == LOCAL:
            env = LOCAL_KEY_ENV
        if not env:
            raise SettingsRejected("这个模型不需要密钥")
        os.environ[env] = key

    def clear_key(self, profile: str) -> None:
        if profile not in PROFILES:
            raise SettingsRejected("没有这个模型")
        env = "DEEPSEEK_API_KEY" if profile == DEEPSEEK else LOCAL_KEY_ENV
        os.environ.pop(env, None)

    def set_active(self, profile: str) -> None:
        if profile not in PROFILES:
            raise SettingsRejected("没有这个模型")
        if self.config(profile) is None:
            raise SettingsRejected("这个模型还没有配置")
        with self._lock:
            self.active = profile
            self._write_settings({"active": profile})

    def save_local(self, fields: dict) -> None:
        """公司本地模型（内网 OpenAI 兼容服务）。密钥不进这份配置，只记是否需要。"""
        try:
            kb = int(fields.get("max_request_kb") or 0)
            tokens = int(fields.get("max_tokens") or 0)
        except (TypeError, ValueError):
            raise SettingsRejected("请求上限和输出上限要填数字") from None
        data = {
            "name": "qwen",
            "base_url": str(fields.get("base_url") or "").strip().rstrip("/"),
            "model": str(fields.get("model") or "").strip(),
            "api_key_env": LOCAL_KEY_ENV if fields.get("needs_key") else None,
            "external": False,
            "allowed_data": ["synthetic", "real"],
            "json_mode": bool(fields.get("json_mode")),
            "thinking_mode": None,
            "max_request_bytes": kb * 1024,
            "max_tokens": tokens,
            "timeout_seconds": 180,
            "max_retries": 2,
            "pipeline": "two_stage",
            "fact_passes": 2,
        }
        try:
            TextModelConfig.model_validate(data)
        except ValueError:
            raise SettingsRejected(
                "配置不完整或不合法：地址填内网 http(s) 基址（不含 /chat/completions），"
                "模型名按服务实际注册的写，请求上限 1 KB 以上，输出上限 1 以上。"
            ) from None
        self.dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        tmp = self.local_config.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(self.local_config)

    def _read_settings(self) -> dict:
        try:
            data = json.loads((self.dir / "settings.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_settings(self, data: dict) -> None:
        self.dir.mkdir(parents=True, mode=0o700, exist_ok=True)
        path = self.dir / "settings.json"
        path.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
