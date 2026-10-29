import json
import urllib.error
import urllib.request

import pytest

from noc7.providers.gate import EgressBlocked
from noc7.providers.text_config import TextProviderError, load_model_config
from noc7.providers.text_http import OpenAICompatibleTextProvider
from noc7.schema import DataClass

from .conftest import ROOT, qwen_config


def test_qwen_plain_json_and_optional_bearer(server, sample, monkeypatch):
    config = qwen_config(server, json_mode=False, api_key_env="NOC7_QWEN_API_KEY")
    monkeypatch.setenv("NOC7_QWEN_API_KEY", "synthetic-key")
    provider = OpenAICompatibleTextProvider(config)
    result = provider.extract(sample[0])
    request = server.requests[0]
    assert result.elements.start_time.status == "unknown"  # 本案例起点只有日期
    assert result.elements.start_time.candidates[1].relation is not None
    assert request["path"] == "/v1/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer synthetic-key"
    assert "response_format" not in request["body"] and "thinking" not in request["body"]
    assert request["body"]["stream"] is False
    assert len(request["body"]["messages"]) == 2


def test_deepseek_official_request_through_simulated_transport(server, sample, monkeypatch):
    native_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    urls = []

    class Transport:
        def open(self, request, timeout):
            urls.append(request.full_url)
            local = urllib.request.Request(server.base_url + "/chat/completions", data=request.data,
                                           headers=dict(request.header_items()))
            return native_opener.open(local, timeout=timeout)

    monkeypatch.setattr("noc7.providers.text_http.urllib.request.build_opener", lambda *args: Transport())
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-key")
    provider = OpenAICompatibleTextProvider(load_model_config(ROOT / "config/models/deepseek.json"))
    real_ctx = sample[0].__class__(sample[0].bundle, sample[0].evidence)
    # 仅把合成上下文的分级改成 real，测试授权；不读取真实文件。
    from copy import deepcopy
    real_ctx = deepcopy(real_ctx)
    real_ctx.bundle.manifest.data_class = DataClass.REAL
    provider.extract(real_ctx)
    assert urls == ["https://api.deepseek.com/chat/completions"]
    assert server.requests[0]["body"]["thinking"] == {"type": "enabled"}
    assert "temperature" not in server.requests[0]["body"]
    assert server.requests[0]["body"]["response_format"] == {"type": "json_object"}


def test_gate_runs_before_key_lookup_or_http(server, sample, monkeypatch):
    from copy import deepcopy
    ctx = deepcopy(sample[0])
    ctx.bundle.manifest.data_class = DataClass.REAL
    provider = OpenAICompatibleTextProvider(qwen_config(server, allowed_data=["synthetic"], api_key_env="MISSING_KEY"))
    monkeypatch.delenv("MISSING_KEY", raising=False)
    with pytest.raises(EgressBlocked):
        provider.extract(ctx)
    assert not server.requests


def test_missing_credentials_do_not_send(server, sample, monkeypatch):
    monkeypatch.delenv("NOC7_QWEN_API_KEY", raising=False)
    provider = OpenAICompatibleTextProvider(qwen_config(server, api_key_env="NOC7_QWEN_API_KEY"))
    with pytest.raises(TextProviderError, match="环境变量"):
        provider.extract(sample[0])
    assert not server.requests


@pytest.mark.parametrize("key", ["", "key\nheader", "密钥不能作为请求头", "key value"])
def test_bad_credentials_are_rejected_without_echo(server, sample, monkeypatch, key):
    monkeypatch.setenv("NOC7_QWEN_API_KEY", key)
    provider = OpenAICompatibleTextProvider(qwen_config(server, api_key_env="NOC7_QWEN_API_KEY"))
    with pytest.raises(TextProviderError) as caught:
        provider.extract(sample[0])
    assert not server.requests
    if key:
        assert key not in str(caught.value)


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retry_is_bounded_and_respects_retry_after(server, sample, status):
    server.replies = [(status, {"Retry-After": "3"}, b"PRIVATE_REMOTE_ERROR")] * 4
    waits = []
    provider = OpenAICompatibleTextProvider(qwen_config(server), sleep=waits.append)
    with pytest.raises(TextProviderError) as caught:
        provider.extract(sample[0])
    assert len(server.requests) == 3 and waits == [3, 3]
    assert "PRIVATE_REMOTE_ERROR" not in str(caught.value)


def test_retry_then_success(server, sample):
    server.replies = [(429, {"Retry-After": "0"}, b"")]
    provider = OpenAICompatibleTextProvider(qwen_config(server), sleep=lambda delay: None)
    provider.extract(sample[0])
    assert len(server.requests) == 2


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_permanent_http_errors_do_not_retry_or_leak(server, sample, status):
    server.replies = [(status, {}, b"PRIVATE_REMOTE_ERROR")]
    provider = OpenAICompatibleTextProvider(qwen_config(server))
    with pytest.raises(TextProviderError) as caught:
        provider.extract(sample[0])
    assert len(server.requests) == 1 and "PRIVATE_REMOTE_ERROR" not in str(caught.value)


def test_redirect_is_not_followed(server, sample):
    server.replies = [(307, {"Location": server.base_url + "/should-not-receive"}, b"")]
    provider = OpenAICompatibleTextProvider(qwen_config(server))
    with pytest.raises(TextProviderError, match="HTTP 307"):
        provider.extract(sample[0])
    assert len(server.requests) == 1


def test_timeout_is_bounded_without_echoing_exception(server, sample, monkeypatch):
    calls, waits = [], []

    class Transport:
        def open(self, request, timeout):
            calls.append(timeout)
            raise TimeoutError("SENSITIVE_SOCKET_ERROR")

    monkeypatch.setattr("noc7.providers.text_http.urllib.request.build_opener", lambda *args: Transport())
    provider = OpenAICompatibleTextProvider(qwen_config(server, timeout_seconds=2), sleep=waits.append)
    with pytest.raises(TextProviderError) as caught:
        provider.extract(sample[0])
    assert calls == [2, 2, 2] and waits == [1, 2]
    assert "SENSITIVE_SOCKET_ERROR" not in str(caught.value)


def test_request_limit_is_checked_before_http(server, sample):
    provider = OpenAICompatibleTextProvider(qwen_config(server, max_request_bytes=1024))
    with pytest.raises(TextProviderError, match="未发送"):
        provider.extract(sample[0])
    assert not server.requests


def test_response_limit_is_enforced(server, sample):
    server.replies = [(200, {}, b"x" * 1025)]
    provider = OpenAICompatibleTextProvider(qwen_config(server, max_response_bytes=1024))
    with pytest.raises(TextProviderError, match="响应超过"):
        provider.extract(sample[0])
    assert len(server.requests) == 1
