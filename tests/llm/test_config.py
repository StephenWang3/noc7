import json

import pytest
from pydantic import ValidationError

from noc7.providers.text_config import APPROVAL_REF, TextModelConfig, TextProviderError, load_model_config
from noc7.providers.gate import ensure_allowed
from noc7.schema import DataClass

from .conftest import ROOT, qwen_config


def test_committed_profiles_and_approval():
    config = load_model_config(ROOT / "config/models/deepseek.json")
    assert config.api_key_env == "DEEPSEEK_API_KEY" and config.approval_ref == APPROVAL_REF
    ensure_allowed(config.gate_config(), DataClass.REAL)
    with pytest.raises(TextProviderError, match="配置不完整"):
        load_model_config(ROOT / "config/models/qwen.example.json")


@pytest.mark.parametrize("changes", [
    {"external": False}, {"base_url": "https://proxy.example/v1"},
    {"base_url": "https://api.deepseek.com.evil/v1"}, {"base_url": "http://api.deepseek.com"},
    {"base_url": "https://key@api.deepseek.com"}, {"base_url": "https://api.deepseek.com?key=secret"},
    {"base_url": "https://api.deepseek.com/#secret"}, {"base_url": "https://api.deepseek.com:8443"},
    {"base_url": "https://api.deepseek.com?"}, {"base_url": "https://api.deepseek.com#"},
    {"base_url": "https://api.deepseek.com/chat/completions"}, {"api_key_env": None},
    {"approval_ref": None}, {"approval_ref": "unrelated-approval"}, {"max_retries": 3},
])
def test_deepseek_cannot_expand_approved_scope(changes):
    data = json.loads((ROOT / "config/models/deepseek.json").read_text())
    data.update(changes)
    with pytest.raises(ValidationError):
        TextModelConfig.model_validate(data)


@pytest.mark.parametrize("changes", [
    {"external": True}, {"base_url": "https://api.deepseek.com"},
    {"base_url": "http://internal:bad/v1"}, {"base_url": "http://internal/v1\n"},
    {"api_key_env": "raw-token-value"}, {"allowed_data": []},
])
def test_qwen_configuration_constraints(server, changes):
    with pytest.raises(ValidationError):
        qwen_config(server, **changes)


def test_loader_never_echoes_bad_config_or_inline_key(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"api_key": "SENSITIVE_INLINE_SECRET"}')
    with pytest.raises(TextProviderError) as caught:
        load_model_config(path)
    assert "SENSITIVE_INLINE_SECRET" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_config_is_immutable_and_fingerprint_tracks_model(server):
    first = qwen_config(server)
    second = qwen_config(server, model="qwen-other")
    assert first.fingerprint != second.fingerprint
    with pytest.raises(ValidationError):
        first.external = True
