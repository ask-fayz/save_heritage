"""Gemini wrapper with the SDK client replaced by a fake that returns real response objects."""

import pytest
from google.genai import types

from app.services.ai import AIError, GeminiAI, MemoryAnalysis


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self.responses.pop(0)


def make_ai(settings, responses) -> tuple[GeminiAI, FakeModels]:
    settings.gemini_api_key = "test"
    ai = GeminiAI(settings)
    models = FakeModels(responses)
    ai._client = type("Client", (), {"models": models})()
    return ai, models


def text_response(text: str, metadata: types.GroundingMetadata | None = None) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[types.Part(text=text)]), grounding_metadata=metadata,
    )])


MEMORY_JSON = """{"language": "yue", "transcript": "我細個喺度睇大戲", "text_en": "As a child I watched opera here.",
 "summary": "Childhood visits to the opera.", "photo_description": "", "tags": ["childhood"], "year_estimate": 1975,
 "year_estimate_reason": "Mentions childhood in the 1970s.", "moderation_flags": []}"""


def test_json_call_sends_schema_and_media(settings):
    ai, models = make_ai(settings, [text_response(MEMORY_JSON)])
    result = ai.analyse_memory(site_title="Sunbeam Theatre", kind="audio", text="", media=(b"RIFF....WAVE", "audio/wav"),
                               year_given=None)
    assert isinstance(result, MemoryAnalysis) and result.year_estimate == 1975
    call = models.calls[0]
    assert call["config"].response_schema is MemoryAnalysis
    assert call["contents"][0].inline_data.mime_type == "audio/wav"


def test_invalid_json_is_retried_then_reported(settings):
    ai, models = make_ai(settings, [text_response("not json"), text_response("{}")])
    with pytest.raises(AIError):
        ai.analyse_memory(site_title="X", kind="story", text="hello", media=None, year_given=None)
    assert len(models.calls) == 2


def test_research_reads_grounding_metadata(settings):
    metadata = types.GroundingMetadata(
        grounding_chunks=[types.GroundingChunk(web=types.GroundingChunkWeb(uri="https://a.example/1", title="a.example"))],
        grounding_supports=[types.GroundingSupport(segment=types.Segment(text="It closed in 2025."),
                                                   grounding_chunk_indices=[0])],
    )
    ai, models = make_ai(settings, [text_response("It closed in 2025.", metadata)])
    research = ai.research("Sunbeam Theatre", "Hong Kong")
    assert research.chunks == [{"url": "https://a.example/1", "title": "a.example"}]
    assert research.supports == [{"text": "It closed in 2025.", "chunks": [0]}]
    assert models.calls[0]["config"].tools[0].google_search is not None


def test_reconstruct_image_returns_inline_bytes(settings):
    response = types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role="model", parts=[
        types.Part(text="Here is a hypothesis."),
        types.Part(inline_data=types.Blob(data=b"\x89PNGfake", mime_type="image/png")),
    ]))])
    ai, _ = make_ai(settings, [response])
    assert ai.reconstruct_image([(b"\xff\xd8\xff", "image/jpeg")], "prompt") == (b"\x89PNGfake", "image/png")


def test_disabled_without_key(settings):
    ai = GeminiAI(settings)
    assert not ai.enabled
    with pytest.raises(AIError):
        _ = ai.client


@pytest.mark.parametrize("code", [500, 502, 503, 504])
def test_transient_api_failure_recovers(settings, monkeypatch, code):
    from google.genai import errors
    from unittest.mock import Mock

    ai, models = make_ai(settings, [])
    models.generate_content = Mock(side_effect=[
        errors.APIError(code, {"error": {"code": code, "message": "busy"}}),
        text_response(MEMORY_JSON),
    ])
    sleep = Mock()
    monkeypatch.setattr("app.services.ai.time.sleep", sleep)
    assert ai._json("test", MemoryAnalysis, "test").language == "yue"
    assert models.generate_content.call_count == 2
    sleep.assert_called_once()


@pytest.mark.parametrize("code", [400, 403, 429, 503])
def test_errors_are_bounded_and_do_not_expose_provider_payload(settings, monkeypatch, code):
    from google.genai import errors
    from unittest.mock import Mock

    ai, models = make_ai(settings, [])
    models.generate_content = Mock(side_effect=errors.APIError(code, {
        "error": {"code": code, "message": "sensitive-provider-payload"},
    }))
    monkeypatch.setattr("app.services.ai.time.sleep", Mock())
    with pytest.raises(AIError) as caught:
        ai.research("Test", "Test")
    assert "sensitive-provider-payload" not in str(caught.value)
    assert models.generate_content.call_count == (3 if code == 503 else 1)


@pytest.mark.parametrize("quota_id,quota_value,delay,expected_calls", [
    ("RequestsPerMinute", "10", "2s", 2),
    ("RequestsPerDay", "20", "2s", 1),
    ("RequestsPerMinute", "0", "2s", 1),
    ("RequestsPerMinute", "10", "60s", 1),
])
def test_quota_retry_respects_provider_delay(settings, monkeypatch, quota_id, quota_value, delay, expected_calls):
    from google.genai import errors
    from unittest.mock import Mock

    ai, models = make_ai(settings, [])
    models.generate_content = Mock(side_effect=[errors.APIError(429, {"error": {
        "code": 429, "message": "quota", "details": [
            {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay},
            {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
                {"quotaId": quota_id, "quotaValue": quota_value},
            ]},
        ],
    }}), text_response("Research")])
    sleep = Mock()
    monkeypatch.setattr("app.services.ai.time.sleep", sleep)
    if expected_calls == 2:
        assert ai.research("Test", "Test").text == "Research"
        sleep.assert_called_once_with(2.0)
    else:
        with pytest.raises(AIError, match="quota"):
            ai.research("Test", "Test")
        sleep.assert_not_called()
    assert models.generate_content.call_count == expected_calls


def test_search_model_override(settings):
    settings.gemini_search_model = "test-search-model"
    ai, models = make_ai(settings, [text_response("Research")])
    ai.research("Test", "Test")
    assert models.calls[0]["model"] == "test-search-model"


def test_client_retry_and_timeout_settings(settings):
    settings.gemini_api_key = "test"
    ai = GeminiAI(settings)
    assert ai.client is not None
    ai.client.close()
