"""OpenAI 兼容文本模型：过闸门、请求、结构与原文校验，不自动回退。"""

from __future__ import annotations

import http.client
import json
import os
import time
import urllib.error
import urllib.request

from ..extract.types import Extraction, ExtractionContext
from ..rules import ExtractionRejected, issue, validate_extraction
from ..schema.common import DataClass
from .gate import ensure_allowed
from .text_config import TextModelConfig, TextProviderError
from .text_ground import ground_extraction, normalize_model_payload, separate_suggestions
from .text_prompt import PROMPT_VERSION, SYSTEM_PROMPT, prepare_evidence
from .text_audit import AuditStore, grounding_changes


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


USAGE_KEYS = ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens", "prompt_cache_miss_tokens")


def response_usage(raw: bytes) -> dict[str, int]:
    """取远端返回的 token 用量；没有或格式不对时返回空字典，不影响请求结果。"""
    try:
        usage = json.loads(raw).get("usage")
    except (ValueError, AttributeError):
        return {}
    if not isinstance(usage, dict):
        return {}
    out = {k: usage[k] for k in USAGE_KEYS if isinstance(usage.get(k), int) and not isinstance(usage.get(k), bool)}
    details = usage.get("completion_tokens_details")
    if isinstance(details, dict) and isinstance(details.get("reasoning_tokens"), int):
        out["reasoning_tokens"] = details["reasoning_tokens"]
    return out


class OpenAICompatibleTextProvider:
    prompt_version = PROMPT_VERSION

    def __init__(self, config: TextModelConfig, *, sleep=time.sleep, audit_dir=None):
        self.config = config
        self.name = f"openai_compatible:{config.name}:{config.model}:{config.fingerprint}"
        self.url = config.base_url.rstrip("/") + "/chat/completions"
        self.sleep = sleep
        self.audit = AuditStore(audit_dir) if audit_dir is not None else None
        # 每次成功请求的用量（远端 usage 字段原样取数字），用于统计成本；不含任何正文。
        self.usage: list[dict[str, int]] = []

    def preflight(self, data_class: DataClass) -> str | None:
        """先检查分级，再读取凭据；调用 CLI 与直接使用提供方均受保护。"""
        from .recovery_policy import initial_selection
        try:
            initial_selection()
        except ValueError as exc:
            raise TextProviderError(str(exc)) from None
        ensure_allowed(self.config.gate_config(), data_class)
        if self.config.api_key_env is None:
            return None
        key = os.environ.get(self.config.api_key_env, "")
        if not key.strip() or not key.isascii() or any(c.isspace() or ord(c) < 32 for c in key):
            raise TextProviderError(f"缺少有效的环境变量 {self.config.api_key_env}，请通过团队密钥配置。")
        return key

    def extract(self, ctx: ExtractionContext) -> Extraction:
        clean_ctx, evidence = prepare_evidence(ctx)
        audit = self.audit.begin(clean_ctx, evidence, PROMPT_VERSION) if self.audit else None
        raw = self._post(SYSTEM_PROMPT, evidence, ctx.bundle.manifest.data_class, audit)
        return self._decode(raw, clean_ctx, audit)

    def _post(self, system: str, user: dict, data_class: DataClass, audit=None) -> bytes:
        """一次模型请求：过闸门、限字节、只对 429／5xx／连接错误重试。"""
        key = self.preflight(data_class)
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
            ],
            "temperature": 0,
            "max_tokens": self.config.max_tokens,
            "stream": False,
        }
        if self.config.json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self.config.thinking_mode is not None:
            payload["thinking"] = {"type": self.config.thinking_mode}
            if self.config.thinking_mode == "enabled":
                payload.pop("temperature")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(body) > self.config.max_request_bytes:
            raise TextProviderError("模型输入超过配置的字节上限；未截断、未发送，请调整容量配置或缩小输入。")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if key is not None:
            headers["Authorization"] = f"Bearer {key}"
        # 内网请求不沿用外部代理环境，避免把内网材料交给代理。
        handlers = [_NoRedirect()]
        if not self.config.external:
            handlers.append(urllib.request.ProxyHandler({}))
        opener = urllib.request.build_opener(*handlers)
        for attempt in range(self.config.max_retries + 1):
            ensure_allowed(self.config.gate_config(), data_class)
            request = urllib.request.Request(self.url, data=body, headers=headers)
            delay = min(2 ** attempt, 30)
            if audit:
                audit.record(outcome="request_started", request_attempts=attempt + 1)
            try:
                with opener.open(request, timeout=self.config.timeout_seconds) as response:
                    raw = response.read(self.config.max_response_bytes + 1)
            except urllib.error.HTTPError as exc:
                status = exc.code
                try:
                    retry_after = float(exc.headers.get("Retry-After", delay))
                    if 0 <= retry_after <= 30:
                        delay = retry_after
                except (TypeError, ValueError):
                    pass
                finally:
                    exc.close()
                if (status == 429 or 500 <= status <= 599) and attempt < self.config.max_retries:
                    self.sleep(delay)
                    continue
                if audit:
                    audit.record(outcome="http_error", http_status=status)
                raise TextProviderError(f"文本模型 HTTP {status}。") from None
            except (urllib.error.URLError, OSError, http.client.HTTPException):
                if attempt < self.config.max_retries:
                    self.sleep(delay)
                    continue
                if audit:
                    audit.record(outcome="transport_error")
                raise TextProviderError("文本模型连接失败或超时，重试次数已耗尽。") from None
            else:
                # 诊断写入／输出校验失败不能触发再次请求模型。
                if len(raw) > self.config.max_response_bytes:
                    if audit:
                        audit.record(outcome="response_too_large")
                    raise TextProviderError("模型响应超过配置的字节上限，已拒绝。")
                self.usage.append(response_usage(raw))
                if audit:
                    audit.record(usage=list(self.usage))
                return raw
        raise TextProviderError("文本模型重试次数已耗尽。")

    @staticmethod
    def _decode(raw: bytes, ctx: ExtractionContext, audit=None) -> Extraction:
        if audit:
            audit.record(raw_response=raw.decode("utf-8", errors="replace"), outcome="response_received")
        try:
            result = OpenAICompatibleTextProvider._decode_payload(raw, ctx, audit)
        except (TextProviderError, ExtractionRejected) as exc:
            if audit:
                audit.record(outcome="rejected", error_type=type(exc).__name__,
                             issue_codes=[i.code.value for i in exc.issues] if isinstance(exc, ExtractionRejected) else [])
            raise
        if audit:
            audit.record(outcome="accepted")
        return result

    @staticmethod
    def _content(raw: bytes):
        """取出模型返回的 JSON 对象；结构不合格统一拒绝，不回显远端正文。"""
        try:
            response = json.loads(raw)
            choices = response["choices"]
            if len(choices) != 1 or choices[0]["finish_reason"] != "stop":
                raise TextProviderError("模型输出未正常结束或被截断，已拒绝。")
            message = choices[0]["message"]
            content = message["content"]
            if message.get("tool_calls") or not isinstance(content, str) or not content.strip():
                raise TextProviderError("模型未返回非空的文本 JSON，已拒绝。")
        except TextProviderError:
            raise
        except (ValueError, TypeError, KeyError, IndexError, RecursionError):
            raise TextProviderError("模型 HTTP 响应结构不合格，已拒绝。") from None
        try:
            parsed = json.loads(content)
        except (ValueError, RecursionError):
            raise TextProviderError("模型输出不是有效 JSON，已拒绝。") from None
        return parsed

    @staticmethod
    def _decode_payload(raw: bytes, ctx: ExtractionContext, audit=None, *, legacy_recovery=False) -> Extraction:
        return OpenAICompatibleTextProvider._decode_parsed(
            OpenAICompatibleTextProvider._content(raw), ctx, audit, legacy_recovery=legacy_recovery)

    @staticmethod
    def _decode_parsed(parsed, ctx: ExtractionContext, audit=None, *, legacy_recovery=False,
                       adjudication="model_selected", extra_original=None) -> Extraction:
        try:
            separated, suggestions = separate_suggestions(parsed)
            normalized = normalize_model_payload(
                separated, ctx.bundle.manifest.default_timezone, ctx.evidence
            )
            if audit:
                audit.record(normalized=normalized)
            data = Extraction.model_validate(normalized)
            data.suggestions = suggestions
            from copy import deepcopy
            from ..schema.relations import SemanticAssessment
            from .responsibility_location import build_coverage
            from .recovery_policy import initial_selection
            data.semantic_assessment = SemanticAssessment(recovery_selection=None if legacy_recovery else initial_selection(), original={
                **{key: deepcopy(parsed["elements"].get(key))
                   for key in ("start_time", "end_time", "cause", "responsible_party", "location")},
                **(extra_original or {}),
            }, adjudication=adjudication, business_coverage=build_coverage(ctx))
        except TextProviderError:
            raise
        except (ValueError, TypeError, RecursionError):
            raise TextProviderError("模型七要素结构不合格，已拒绝。") from None
        before = data.model_dump(mode="json")
        if audit:
            audit.record(before_grounding=before)
        # 两栏建议独立保存；时间和原因只验证模型关系，其余沿用既有处理。
        data = ground_extraction(ctx, data)
        if audit:
            after = data.model_dump(mode="json")
            audit.record(after_grounding=after, changes=grounding_changes(before, after))
        try:
            validate_extraction(ctx, data)
        except ExtractionRejected as exc:
            # 输出仅保留受控问题码，不回显模型伪造的证据编号和文字。
            raise ExtractionRejected([
                issue(i.code, "模型结果未通过证据校验。", element=i.element) for i in exc.issues
            ]) from None
        except ValueError:
            raise TextProviderError("模型不能提交人工审核记录，已拒绝。") from None
        return data
