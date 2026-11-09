"""Google Gemini: source-grounded extraction, research, memory processing, news triage, AI Keeper and labelled hypotheses."""

import logging
from dataclasses import dataclass
from typing import Literal, TypeVar

from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.models import EVENT_KINDS, RISK_REASONS, SUPPORTED_LANGUAGES, RiskStatus

log = logging.getLogger(__name__)

EventKind = Literal[tuple(EVENT_KINDS)]  # type: ignore[valid-type]
RiskReason = Literal[tuple(RISK_REASONS)]  # type: ignore[valid-type]
T = TypeVar("T", bound=BaseModel)

LANGUAGE_INSTRUCTIONS = {
    "en": "Write all text fields in English. Translate sources in other languages faithfully.",
    "ru": (
        "Write all text fields in Russian (на русском языке: заголовки, описание, карточки тура, "
        "культуру, факты, хронологию, статус риска, глоссарий, людей и паспорт сохранения). "
        "Translate sources from other languages into fluent, museum-grade Russian faithfully."
    ),
    "zh": (
        "Write all text fields in Simplified Chinese (使用简体中文撰写所有标题、简介、导览卡片、文化传承、"
        "速览事实、时间轴事件、风险评估、术语表、传承人及保护行动指南). "
        "Translate sources from other languages into accurate, museum-grade Simplified Chinese."
    ),
}


class AIError(RuntimeError):
    pass


# ---------------------------------------------------------------- response schemas

class AICard(BaseModel):
    title: str
    content: str = Field(description="2-4 sentences, only facts supported by the cited sources.")
    source_ids: list[int] = Field(description="IDs of the sources ([S#]) that support this text.")


class AIFact(BaseModel):
    text: str
    source_ids: list[int]


class AIEvent(BaseModel):
    year: int | None = Field(description="Year of the event; negative for BCE; null if unknown.")
    date_text: str = Field(description="Human readable date as precise as the sources allow, e.g. 'March 2025'.")
    title: str
    description: str
    kind: EventKind
    source_ids: list[int]


class AIRisk(BaseModel):
    status: RiskStatus = Field(description=(
        "unknown: no information; stable: protected and in use; watch: early warning signs; "
        "at_risk: a concrete threat; critical: loss imminent or under way; "
        "lost: demolished/destroyed or its heritage use has ended."))
    reasons: list[RiskReason]
    summary: str = Field(description="2-3 sentences explaining the status, citing the most recent information.")
    source_ids: list[int]


class AIGlossaryTerm(BaseModel):
    term: str
    original: str = Field(description="Term in the original language/script, if any.")
    definition: str
    source_ids: list[int]


class AIPractitioner(BaseModel):
    name: str
    role: str
    description: str
    source_ids: list[int]


class AIDisputedVersion(BaseModel):
    claim: str
    source_ids: list[int]


class AIDisputedPoint(BaseModel):
    topic: str
    versions: list[AIDisputedVersion]


class AITheme(BaseModel):
    bg: str = Field(description="Dark background, #RRGGBB")
    bg_darker: str = Field(description="Even darker background, #RRGGBB")
    accent_red: str = Field(description="Primary bright accent, #RRGGBB")
    accent_gold: str = Field(description="Secondary accent for headings, #RRGGBB")
    text_cream: str = Field(description="Light body text with strong contrast on bg, #RRGGBB")
    card_bg: str = Field(description="Card background slightly lighter than bg, #RRGGBB")
    border_color: str = Field(description="Subtle border, #RRGGBB")


class SiteExtraction(BaseModel):
    title: str = Field(description="Name of the site in the requested output language.")
    native_name: str = Field(description="Name in the local language/script, or empty.")
    location_label: str = Field(description="'District, City, Country' style label in the requested output language.")
    tagline: str = Field(description="One sentence on why the place matters today.")
    tour_cards: list[AICard] = Field(description=(
        "4-6 stops of a virtual tour: what a visitor sees and why it matters (exterior, setting, interior, "
        "details, use). Visitor-friendly, cited."))
    culture_title: str = Field(description="Heading for the intangible heritage connected to the site.")
    culture_subtitle: str = Field(description="The same heading in the original language/script, or empty.")
    culture_cards: list[AICard] = Field(description="3-4 cards about living practices, crafts, rituals, art forms.")
    quick_facts: list[AIFact] = Field(description="5-7 short facts.")
    did_you_know: AIFact
    timeline: list[AIEvent] = Field(description="Chronicle of what happened to the place, oldest first, including the most recent changes.")
    risk: AIRisk
    glossary: list[AIGlossaryTerm] = Field(description="Up to 8 terms a visitor would not know.")
    practitioners: list[AIPractitioner] = Field(description="Up to 6 people or groups who keep the heritage alive, only if named in sources.")
    disputed_points: list[AIDisputedPoint] = Field(description="Points where sources disagree. Empty if none.")
    protection_level: str = Field(default="", description="Official heritage designation or protection status if stated in sources, else empty.")
    preservation_actions: list[AICard] = Field(
        default_factory=list,
        description="2-3 concrete preservation, documentation or community support actions relevant to this site, grounded in sources.",
    )
    theme: AITheme
    latitude: float | None = Field(description="Decimal degrees if stated in the sources, else null.")
    longitude: float | None = Field(description="Decimal degrees if stated in the sources, else null.")


class KeeperAnswer(BaseModel):
    answer: str = Field(description="2-5 sentences answering the visitor's question strictly from the site's archive, with [S#] citations inline.")
    cited_refs: list[int] = Field(description="Source reference numbers ([S#]) used in the answer.")
    follow_up_questions: list[str] = Field(description="2-3 short suggested follow-up questions in the same language.")


class MemoryAnalysis(BaseModel):
    language: str = Field(description="BCP-47 code of the original text or speech, e.g. 'en', 'yue', 'zh', 'ru'.")
    transcript: str = Field(description="Verbatim transcription for audio in the original language; empty otherwise.")
    text_en: str = Field(description="Faithful English translation of the story or transcript. Do not embellish.")
    summary: str = Field(description="One neutral sentence summarising the memory.")
    photo_description: str = Field(description="For photos: what is visible, neutral and factual. Empty otherwise.")
    tags: list[str] = Field(description="Up to 6 short lowercase topic tags.")
    year_estimate: int | None = Field(description="Best estimate of the year the memory/photo refers to, or null.")
    year_estimate_reason: str = Field(description="Short explanation of the clues used for the estimate.")
    moderation_flags: list[Literal["spam", "offensive", "unrelated", "personal_data", "copyright"]]


class PhotoVerdict(BaseModel):
    index: int
    relevant: bool = Field(description="True only if the photo most likely shows the site itself or its immediate surroundings.")
    year: int | None
    reason: str


class PhotoRanking(BaseModel):
    verdicts: list[PhotoVerdict]


class NewsEvent(BaseModel):
    year: int | None
    date_text: str
    title: str
    description: str
    kind: EventKind


class NewsVerdict(BaseModel):
    index: int
    relevant: bool = Field(description="True only if the article is about this specific site.")
    summary: str
    threat_level: Literal["none", "low", "medium", "high"]
    suggested_status: Literal["no_change", "unknown", "stable", "watch", "at_risk", "critical", "lost"]
    event: NewsEvent | None = Field(description="A chronicle entry if the article reports a concrete change, else null.")


class NewsTriage(BaseModel):
    verdicts: list[NewsVerdict]


# ---------------------------------------------------------------- prompts

EXTRACTION_SYSTEM = """You are the lead editor of SAVE Heritage, a Smart Archive for Virtual Exploration of Heritage.
You turn a set of numbered sources into a structured, trustworthy record of a heritage site.

Rules:
1. Follow the requested output language instruction carefully. Translate sources in other languages faithfully.
2. Use ONLY information found in the sources. Never invent names, dates, numbers or events.
3. Every card, fact, event, glossary term, practitioner and preservation action must list the [S#] source IDs that support it.
   If nothing supports a statement, leave the statement out.
4. Prefer the most recent information about the site's condition, ownership and use. If a place closed,
   was demolished or changed use, say so plainly, with the date.
5. When sources disagree (dates, numbers, attributions), record the disagreement in disputed_points
   instead of silently picking one version.
6. Tone: warm, precise, museum-label quality. No marketing language, no speculation.
7. Theme colours: a dark, atmospheric palette inspired by the place (materials, signage, costumes), with
   readable light text."""

RESEARCH_PROMPT = """Research the heritage site "{title}" ({location}) using web search.
Report verified facts in {lang_label}, as plain paragraphs (max 600 words), covering:
- history and key dates;
- architecture and physical condition;
- cultural significance and the living practices connected to it;
- the CURRENT situation: ownership, use, closures, redevelopment, damage, protection status, and the most recent news.
Do not speculate. If information is uncertain, say so."""

KEEPER_SYSTEM = """You are the AI Keeper of SAVE Heritage, an archival guide for a specific cultural heritage site.
Rules:
1. Answer ONLY using the provided archive record (tour cards, timeline events, quick facts, risk status, community memories, and numbered sources [S#]).
2. Include inline [S#] markers (e.g. [S1], [S2]) right after facts supported by those sources.
3. If the archive record does not contain the answer, state honestly what is not yet in the archive and invite the visitor to contribute a source or memory.
4. Reply in the language requested by the user (or the language of the user's question: English, Russian, or Chinese).
5. Persona mode:
   - If mode is 'archivist': speak as a knowledgeable, warm museum curator and archivist.
   - If mode is 'voice': speak in the first person ("I", "Я", "我") as the living memory and voice of the heritage site itself, looking back across its chronicle and the people who knew it, while still citing [S#] strictly."""

MEMORY_SYSTEM = """You help curators of SAVE Heritage process community memories about a heritage site.
Be faithful: transcribe and translate exactly, never add details. Estimate dates only from visible or stated clues.
Flag content that is spam, offensive, unrelated to the site, exposes private data of third parties
(phone numbers, addresses, ID numbers), or appears to be copied professional media."""

NEWS_SYSTEM = """You triage news for SAVE Heritage's "heritage at risk" monitor.
Decide if each article is about the specific site (not a namesake), summarise it neutrally, rate the threat it
describes, and propose a chronicle event only for concrete changes (sale, closure, demolition, protection, damage,
reopening, restoration). Suggest a new risk status only if the article clearly justifies it."""

PHOTO_SYSTEM = """You check archive photos for SAVE Heritage. From the title, description and date metadata,
decide whether each photo shows the given heritage site or its immediate surroundings. Photos of events,
people or unrelated places that merely share a category are NOT relevant. Give the year if the metadata states it."""


# ---------------------------------------------------------------- client

@dataclass
class ResearchResult:
    text: str
    chunks: list[dict]      # {"url", "title"} in grounding-chunk order (None for non-web chunks)
    supports: list[dict]    # {"text": segment text, "chunks": [chunk indices]}


def annotate_with_refs(text: str, supports: list[dict], chunk_refs: dict[int, int]) -> str:
    """Insert [S#] markers after grounded segments so the extraction step can cite the real web pages."""
    insertions: list[tuple[int, str]] = []
    cursor = 0
    for support in supports:
        segment = support.get("text") or ""
        refs = sorted({chunk_refs[i] for i in support.get("chunks", []) if i in chunk_refs})
        if not segment or not refs:
            continue
        position = text.find(segment, cursor)
        if position < 0:
            position = text.find(segment)
        if position < 0:
            continue
        end = position + len(segment)
        cursor = end
        insertions.append((end, " " + "".join(f"[S{r}]" for r in refs)))
    for end, marker in sorted(insertions, reverse=True):
        text = text[:end] + marker + text[end:]
    return text


class GeminiAI:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None

    @property
    def enabled(self) -> bool:
        return self.settings.ai_enabled

    @property
    def client(self):
        if not self.enabled:
            raise AIError("GEMINI_API_KEY is not configured.")
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self.settings.gemini_api_key)
        return self._client

    def _json(self, contents, schema: type[T], system: str, temperature: float = 0.2) -> T:
        from google.genai import errors, types

        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=temperature,
        )
        last_error: Exception | None = None
        for _ in range(2):
            try:
                response = self.client.models.generate_content(
                    model=self.settings.gemini_model, contents=contents, config=config
                )
                if isinstance(response.parsed, schema):
                    return response.parsed
                return schema.model_validate_json(response.text or "")
            except (ValidationError, ValueError) as exc:
                last_error = exc
                log.warning("Gemini returned invalid JSON for %s: %s", schema.__name__, exc)
            except errors.APIError as exc:
                raise AIError(f"Gemini API error: {exc}") from exc
        raise AIError(f"Gemini did not return valid {schema.__name__}: {last_error}")

    # --- site generation

    def research(self, title: str, location: str, lang: str = "en") -> ResearchResult:
        from google.genai import errors, types

        lang_label = SUPPORTED_LANGUAGES.get(lang, SUPPORTED_LANGUAGES["en"])["label"]
        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_model,
                contents=RESEARCH_PROMPT.format(
                    title=title,
                    location=location or "location unknown",
                    lang_label=lang_label,
                ),
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.2
                ),
            )
        except errors.APIError as exc:
            raise AIError(f"Gemini search grounding failed: {exc}") from exc
        text = response.text or ""
        chunks: list[dict] = []
        supports: list[dict] = []
        metadata = response.candidates[0].grounding_metadata if response.candidates else None
        if metadata:
            for chunk in metadata.grounding_chunks or []:
                web = chunk.web
                chunks.append({"url": web.uri, "title": web.title or web.domain or web.uri} if web and web.uri else None)
            for support in metadata.grounding_supports or []:
                supports.append({
                    "text": support.segment.text if support.segment else "",
                    "chunks": list(support.grounding_chunk_indices or []),
                })
        return ResearchResult(text=text, chunks=chunks, supports=supports)

    def extract_site(self, sources_block: str, hints: str, lang: str = "en") -> SiteExtraction:
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["en"])
        prompt = f"OUTPUT LANGUAGE REQUIREMENT: {lang_instruction}\n\n{hints}\n\n{sources_block}\n\nProduce the structured record now."
        return self._json(prompt, SiteExtraction, EXTRACTION_SYSTEM, temperature=0.3)

    def ask_keeper(self, *, site_context: str, question: str, mode: str = "archivist", lang: str = "en") -> KeeperAnswer:
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["en"])
        prompt = (
            f"Persona mode: {mode}\n"
            f"Preferred language: {lang} ({lang_instruction})\n\n"
            f"ARCHIVE RECORD:\n{site_context}\n\n"
            f"VISITOR QUESTION:\n{question}"
        )
        return self._json(prompt, KeeperAnswer, KEEPER_SYSTEM, temperature=0.25)

    def rank_photos(self, site_title: str, location: str, photos: list[dict]) -> PhotoRanking:
        lines = [
            f"{i}. title: {p.get('title', '')} | description: {p.get('description', '')[:200]} | "
            f"date: {p.get('date_text', '')}"
            for i, p in enumerate(photos)
        ]
        prompt = f"Heritage site: {site_title} ({location})\n\nPhotos:\n" + "\n".join(lines)
        return self._json(prompt, PhotoRanking, PHOTO_SYSTEM, temperature=0.0)

    # --- community memories

    def analyse_memory(self, *, site_title: str, kind: str, text: str, media: tuple[bytes, str] | None,
                       year_given: int | None) -> MemoryAnalysis:
        from google.genai import types

        prompt = (
            f"Heritage site: {site_title}\nMemory type: {kind}\n"
            f"Year given by contributor: {year_given or 'not given'}\n"
            f"Contributor's text:\n{text or '(none)'}"
        )
        contents: list = [prompt]
        if media:
            data, mime = media
            contents.insert(0, types.Part.from_bytes(data=data, mime_type=mime))
        return self._json(contents, MemoryAnalysis, MEMORY_SYSTEM, temperature=0.1)

    # --- news monitoring

    def triage_news(self, *, site_title: str, location: str, current_status: str, items: list[dict]) -> NewsTriage:
        lines = [f"{i}. [{it.get('published_at', '')}] {it['title']} — {it.get('source_name', '')}"
                 for i, it in enumerate(items)]
        prompt = (
            f"Site: {site_title} ({location})\nCurrent risk status: {current_status}\n\n"
            "Articles (headline, date, publisher):\n" + "\n".join(lines)
        )
        return self._json(prompt, NewsTriage, NEWS_SYSTEM, temperature=0.0)

    # --- labelled hypotheses

    def reconstruct_image(self, images: list[tuple[bytes, str]], prompt: str) -> tuple[bytes, str]:
        from google.genai import errors, types

        contents: list = [types.Part.from_bytes(data=data, mime_type=mime) for data, mime in images]
        contents.append(prompt)
        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_image_model,
                contents=contents,
                config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
            )
        except errors.APIError as exc:
            raise AIError(f"Gemini image generation failed: {exc}") from exc
        for candidate in response.candidates or []:
            for part in (candidate.content.parts if candidate.content else None) or []:
                if part.inline_data and part.inline_data.data:
                    return part.inline_data.data, part.inline_data.mime_type or "image/png"
        raise AIError("The image model returned no image.")


RECONSTRUCTION_PROMPT = """You are assisting heritage researchers. Using ONLY the attached documentary photograph(s) of
{title} ({location}), create a speculative visualisation of {focus}{year_clause}.
- Preserve the geometry, proportions, materials and details that are visible in the photographs.
- Where information is missing, keep it plain and neutral rather than inventing ornament, signage or text.
- Photorealistic, daylight, eye-level, no people, no watermarks, no captions.
This image will be published with a clear "AI hypothesis" label next to the source photographs."""
