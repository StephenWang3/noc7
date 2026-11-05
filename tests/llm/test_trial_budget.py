"""试跑预算保护全用本地桩，不请求模型、不建立网络连接。"""
import json
import urllib.error

import pytest

from noc7.providers.text_config import TextModelConfig, TextProviderError
from noc7.providers.text_http import OpenAICompatibleTextProvider


@pytest.fixture
def trial(monkeypatch):
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts'))
    import run_responsibility_location_trial
    return run_responsibility_location_trial


@pytest.mark.parametrize('statuses,expected,stop', [
    ([402, 200], 1, 'http_402'),
    ([503, 503, 503, 200], 3, 'three_consecutive_503_or_invalid_responses'),
    ([503, 'invalid', 503, 200], 3, 'three_consecutive_503_or_invalid_responses'),
    (['invalid', 'invalid', 'invalid', 200], 3, 'three_consecutive_503_or_invalid_responses'),
    ([503, 200, 503, 200], 4, None),
    ([200] * 22, 22, None),
])
def test_serial_budget_stop_does_not_submit_later_cases(trial, statuses, expected, stop):
    called, checkpoints = [], []
    def run(i):
        assert len(called) == len(checkpoints)  # 先落盘／检查，再处理下一单。
        called.append(i)
        s = statuses[i]
        return dict(request_count=1, http_status=s if isinstance(s, int) else None,
                    invalid_response=s == 'invalid', status='ok' if s == 200 else 'failed')
    rows, reason = trial.run_serial(range(len(statuses)), run, lambda rows, reason: checkpoints.append(len(rows)))
    assert called == list(range(expected))
    assert len(rows) == expected and reason == stop
    assert sum(r['request_count'] for r in rows) == expected


@pytest.mark.parametrize('status', [402, 503])
def test_zero_retry_provider_records_exactly_one_attempt_without_network(sample, tmp_path, monkeypatch, status):
    calls = []
    class Opener:
        def open(self, request, **kwargs):
            calls.append(1)
            raise urllib.error.HTTPError(request.full_url, status, 'stub', {}, None)
    monkeypatch.setattr('urllib.request.build_opener', lambda *a: Opener())
    config = TextModelConfig(name='qwen', base_url='http://synthetic.invalid/v1', model='synthetic',
                            external=False, max_request_bytes=4194304, max_tokens=1024, max_retries=0)
    provider = OpenAICompatibleTextProvider(config, audit_dir=tmp_path / 'audit',
                                           sleep=lambda _: pytest.fail('不允许重试等待'))
    with pytest.raises(TextProviderError): provider.extract(sample[0])
    assert len(calls) == 1
    records = list((tmp_path / 'audit').glob('*.json'))
    assert len(records) == 1
    trace = json.loads(records[0].read_text())
    assert trace['request_attempts'] == 1 and trace['http_status'] == status


@pytest.mark.parametrize('status,audits,expected', [
    ('failed', [{'outcome':'response_too_large'}], True),
    ('rejected', [{'raw_response':'invalid JSON'}], True),
    ('failed', [{'outcome':'transport_error'}], False),
    ('ok', [{'raw_response':'saved JSON'}], False),
])
def test_invalid_content_includes_oversize_but_not_transport_failure(trial, status, audits, expected):
    assert trial.invalid_response(status,audits) is expected
