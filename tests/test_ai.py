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
