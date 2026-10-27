import io
import json
import urllib.error

from PIL import Image
import pytest

from noc7.ocr import ImageObservation, LayoutResult
from noc7.providers import EgressBlocked, ProviderConfig, ProviderKind
from noc7.providers.attachment_models import ReplayAttachmentProvider, describe_image, image_digest, read_layout
from noc7.providers.vision_http import BatchLimiter, OpenAICompatibleAttachmentProvider
from noc7.schema.common import DataClass


class Spy:
    name = "test.external"

    def __init__(self, *, approved=False):
        self.calls = 0
        self.config = ProviderConfig(name=self.name, kind=ProviderKind.OPENAI_COMPATIBLE, external=True,
                                     allowed_data=[DataClass.SYNTHETIC, DataClass.REAL] if approved else [DataClass.SYNTHETIC],
                                     approval_ref="test-explicit-reference" if approved else None)

    def read(self, image, data_class):
        self.calls += 1
        return LayoutResult()

    def describe(self, image, data_class):
        self.calls += 1
        return ImageObservation(subtype="other")


@pytest.mark.parametrize("approved", [False, True])
@pytest.mark.parametrize("fn", [read_layout, describe_image])
def test_real_never_reaches_external_provider(approved, fn):
    provider = Spy(approved=approved)
    with pytest.raises(EgressBlocked):
        fn(provider, Image.new("RGB", (10, 10)), DataClass.REAL)
    assert provider.calls == 0


def test_synthetic_passes_gate_and_output_bounds_are_checked():
    provider = Spy()
    assert read_layout(provider, Image.new("RGB", (10, 10)), DataClass.SYNTHETIC).blocks == []
    provider.read = lambda *args: LayoutResult(blocks=[{"text": "x", "bbox": (0, 0, 20, 20), "quality": 1}])
    with pytest.raises(ValueError, match="超出"):
        read_layout(provider, Image.new("RGB", (10, 10)), DataClass.SYNTHETIC)


def test_replay_bound_to_pixels_and_validated(tmp_path):
    image = Image.new("RGB", (40, 40), "white")
    content = LayoutResult(blocks=[{"text": "合成回放", "bbox": (1, 2, 30, 20), "quality": .9}])
    (tmp_path / f"{image_digest(image)}.ocr.json").write_text(content.model_dump_json(), encoding="utf-8")
    provider = ReplayAttachmentProvider(tmp_path)
    assert read_layout(provider, image, DataClass.SYNTHETIC) == content
    with pytest.raises(FileNotFoundError):
        read_layout(provider, Image.new("RGB", (40, 40), "black"), DataClass.SYNTHETIC)
    with pytest.raises(EgressBlocked):
        provider.read(image, DataClass.REAL)


def test_vision_impossible_statistics_rejected():
    provider = Spy()
    provider.describe = lambda *args: {"subtype": "qos_chart", "regions": [{"text": "合成错误读数", "bbox": [0, 0, 10, 10],
        "quality": 1, "reading": {"type": "chart", "metric": "丢包率", "unit": "%", "series": [{"series": "BE", "max": 2, "min": 3}]}}]}
    with pytest.raises(ValueError, match="统计"):
        describe_image(provider, Image.new("RGB", (20, 20)), DataClass.SYNTHETIC)


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, duration):
        self.sleeps.append(duration)
        self.now += duration


def test_batch_spacing_measured_after_tenth_completion():
    clock = FakeTime()
    limiter = BatchLimiter(clock=clock.clock, sleep=clock.sleep)
    for _ in range(10):
        limiter.acquire()
        clock.now += 5
        limiter.completed()
    limiter.acquire()
    assert clock.now == 80
    assert clock.sleeps == [30]
    limiter.limited()
    limiter.acquire()
    assert clock.sleeps == [30, 300]


class Response(io.BytesIO):
    pass


def mock_http(monkeypatch, response, *, limited=0):
    class Opener:
        def __init__(self):
            self.calls = []

        def open(self, request, timeout):
            self.calls.append(request)
            if len(self.calls) <= limited:
                raise urllib.error.HTTPError(request.full_url, 429, "limited", {}, None)
            return Response(json.dumps({"choices": [{"message": {"content": json.dumps(response)}}]}).encode())
    opener = Opener()
    monkeypatch.setattr("noc7.providers.vision_http.urllib.request.build_opener", lambda *args: opener)
    monkeypatch.setenv("NOC7_VISION_API_KEY", "synthetic-test-key")
    return opener


def test_http_429_cooldown_and_retry(monkeypatch):
    opener = mock_http(monkeypatch, {"blocks": []}, limited=1)
    clock = FakeTime()
    provider = OpenAICompatibleAttachmentProvider("https://vision.example/v1", "synthetic-model",
        limiter=BatchLimiter(clock=clock.clock, sleep=clock.sleep))
    assert provider.read(Image.new("RGB", (10, 10)), DataClass.SYNTHETIC).blocks == []
    assert len(opener.calls) == 2 and clock.sleeps == [300]
    request_body = json.loads(opener.calls[0].data)
    assert request_body["model"] == "synthetic-model"
    assert "schema" in request_body["messages"][0]["content"]


def test_http_real_blocked_before_key_lookup_or_request(monkeypatch):
    opener = mock_http(monkeypatch, {"blocks": []})
    monkeypatch.delenv("NOC7_VISION_API_KEY")
    provider = OpenAICompatibleAttachmentProvider("https://vision.example/v1", "synthetic-model")
    with pytest.raises(EgressBlocked):
        provider.read(Image.new("RGB", (10, 10)), DataClass.REAL)
    assert not opener.calls


def test_http_retry_is_bounded(monkeypatch):
    opener = mock_http(monkeypatch, {"blocks": []}, limited=5)
    clock = FakeTime()
    provider = OpenAICompatibleAttachmentProvider("https://vision.example/v1", "synthetic-model",
        limiter=BatchLimiter(clock=clock.clock, sleep=clock.sleep))
    with pytest.raises(RuntimeError, match="HTTP 429"):
        provider.read(Image.new("RGB", (10, 10)), DataClass.SYNTHETIC)
    assert len(opener.calls) == 2 and clock.sleeps == [300]


def test_http_vision_always_needs_review(monkeypatch):
    mock_http(monkeypatch, {"subtype": "site_photo", "regions": [{"text": "合成照片", "bbox": [0, 0, 8, 8],
              "quality": 1, "needs_review": False}]})
    provider = OpenAICompatibleAttachmentProvider("https://vision.example/v1", "synthetic-model")
    result = describe_image(provider, Image.new("RGB", (10, 10)), DataClass.SYNTHETIC)
    assert result.regions[0].needs_review


@pytest.mark.parametrize("url", ["http://vision.example", "https://key@vision.example", "https://vision.example?key=token"])
def test_external_url_not_allowed_to_carry_credentials(url):
    with pytest.raises(ValueError):
        OpenAICompatibleAttachmentProvider(url, "test")
