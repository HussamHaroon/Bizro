"""Adapter selection (MOCK_MODE + OCR_MODEL) and the exact wire payload the
real adapters send — asserted against a fake transport, no network."""

from __future__ import annotations

import json

import pytest

from tests.fixtures import standard_fixtures
from vision_agent.adapters import (
    MockOcrAdapter,
    OcrConfigError,
    Qwen35OcrAdapter,
    QwenVlOcrAdapter,
    both_real_adapters,
    get_adapter,
)
from vision_agent.config import Settings
from vision_agent.dashscope_client import DashScopeOcrClient, ImageError, image_to_data_url

VALID_OCR_ANSWER = """```json
{
  "is_receipt": true,
  "supplier_name": "Al-Madina Kiryana Store",
  "items": [{"item": "chai patti", "qty": 2, "unit": "packet", "unit_price": 350}],
  "stated_total": 700,
  "unclear_parts": [],
  "self_confidence": 0.9
}
```"""


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {
            "choices": [{"message": {"role": "assistant", "content": VALID_OCR_ANSWER}}]
        }

    def json(self):
        return self._payload


class TestGetAdapter:
    def test_auto_without_key_yields_mock(self):
        assert isinstance(get_adapter(Settings()), MockOcrAdapter)

    def test_auto_with_key_yields_selected_real(self):
        vl = get_adapter(Settings(dashscope_api_key="sk-test", ocr_model="vl"))
        new = get_adapter(Settings(dashscope_api_key="sk-test", ocr_model="new"))
        assert isinstance(vl, QwenVlOcrAdapter) and vl.model == "qwen-vl-ocr"
        assert isinstance(new, Qwen35OcrAdapter) and new.model == "qwen3.5-ocr"

    def test_always_mock_even_with_key(self):
        assert isinstance(
            get_adapter(Settings(dashscope_api_key="sk-test", mock_mode="always")), MockOcrAdapter
        )

    def test_never_without_key_is_config_error(self):
        with pytest.raises(OcrConfigError):
            get_adapter(Settings(mock_mode="never"))

    def test_both_real_adapters_always_available(self):
        adapters = both_real_adapters(Settings(dashscope_api_key="sk-test"))
        assert [a.name for a in adapters] == ["vl", "new"]


class TestMockAdapter:
    def test_routes_by_filename(self, tmp_path):
        images = standard_fixtures(tmp_path)
        adapter = MockOcrAdapter(Settings())
        assert adapter.extract(images["blurry"]).extra["scenario"] == "blurry"
        assert adapter.extract(images["not_receipt"]).extra["scenario"] == "not_receipt"

    def test_unknown_filename_defaults_to_clean(self, tmp_path):
        images = standard_fixtures(tmp_path)
        result = MockOcrAdapter(Settings()).extract(images["clean"])
        assert result.mock is True
        assert result.model == "mock:qwen-vl-ocr"
        assert result.extraction.supplier_name == "Al-Madina Kiryana Store"

    def test_explicit_scenario_overrides(self, tmp_path):
        images = standard_fixtures(tmp_path)
        result = MockOcrAdapter(Settings(), scenario="wrong_price").extract(images["clean"])
        assert result.extraction.items[0].unit_price == 3500


class TestRealAdapterWireFormat:
    def _adapter_with_spy(self, settings):
        adapter = QwenVlOcrAdapter(settings)
        captured = {}

        def transport(url, headers, json_body, timeout):
            captured.update(
                url=url, headers=headers, body=json_body, timeout=timeout
            )
            return FakeResponse()

        adapter._client = DashScopeOcrClient(settings, transport=transport, sleep=lambda _: None)
        return adapter, captured

    def test_payload_matches_documented_api(self, tmp_path):
        settings = Settings(dashscope_api_key="sk-test")
        adapter, captured = self._adapter_with_spy(settings)
        image = standard_fixtures(tmp_path)["clean"]

        result = adapter.extract(image)

        # endpoint: OpenAI-compatible chat/completions on the configured base
        assert captured["url"] == settings.dashscope_base_url + "/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer sk-test"
        body = captured["body"]
        assert body["model"] == "qwen-vl-ocr"
        content = body["messages"][0]["content"]
        # documented multimodal shape: [image_url, text] (notes.md §2)
        assert content[0]["type"] == "image_url"
        assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")
        assert content[1]["type"] == "text"
        assert "NEVER guess a digit" in content[1]["text"]
        # full round trip through the parser
        assert result.mock is False
        assert result.extraction.stated_total == 700
        assert result.model == "qwen-vl-ocr"
        assert result.raw_text == VALID_OCR_ANSWER

    def test_auth_failure_is_typed(self, tmp_path):
        settings = Settings(dashscope_api_key="sk-bad")
        adapter = QwenVlOcrAdapter(settings)

        def transport(url, headers, json_body, timeout):
            return FakeResponse(status_code=401, payload={"error": {"message": "bad key"}})

        adapter._client = DashScopeOcrClient(settings, transport=transport, sleep=lambda _: None)
        from vision_agent.dashscope_client import DashScopeAuthError

        with pytest.raises(DashScopeAuthError):
            adapter.extract(standard_fixtures(tmp_path)["clean"])

    def test_unparseable_model_output_degrades_to_unreadable(self, tmp_path):
        settings = Settings(dashscope_api_key="sk-test", ocr_repair_retries=1)
        adapter = QwenVlOcrAdapter(settings)
        answers = iter(["I cannot read this", "still not json"])

        def transport(url, headers, json_body, timeout):
            return FakeResponse(payload={"choices": [{"message": {"content": next(answers)}}]})

        adapter._client = DashScopeOcrClient(settings, transport=transport, sleep=lambda _: None)
        result = adapter.extract(standard_fixtures(tmp_path)["clean"])
        assert result.error is not None and "parse failed" in result.error
        assert result.extraction.items == []          # nothing guessed
        assert result.extraction.self_confidence == 0.0


class TestImageHandling:
    def test_missing_file_raises(self):
        with pytest.raises(ImageError):
            image_to_data_url("no/such/file.png", max_bytes=10**6)

    def test_unsupported_suffix_raises(self, tmp_path):
        path = tmp_path / "receipt.txt"
        path.write_text("not an image")
        with pytest.raises(ImageError):
            image_to_data_url(path, max_bytes=10**6)

    def test_oversize_raises(self, tmp_path):
        image = standard_fixtures(tmp_path)["clean"]
        with pytest.raises(ImageError):
            image_to_data_url(image, max_bytes=16)

    def test_data_url_format(self, tmp_path):
        image = standard_fixtures(tmp_path)["clean"]
        url = image_to_data_url(image, max_bytes=10**6)
        header, _, b64 = url.partition(",")
        assert header == "data:image/png;base64"
        assert len(b64) > 100
        json.dumps({"url": url})  # must be JSON-serializable for the wire
