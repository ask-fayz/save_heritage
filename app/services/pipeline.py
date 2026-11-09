"""Long-running workflows: generating a site record (from a URL or place name), enriching it with photos/3D/news, processing memories, and answering AI Keeper questions."""

import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import trafilatura

from app import repo
from app.config import Settings
from app.db import session
from app.models import (
    DEFAULT_TOUR_CAMERAS,
    RISK_STATUSES,
    SUPPORTED_LANGUAGES,
    Card,
    Fact,
    GlossaryTerm,
    OrbitCamera,
    Pose,
    SiteContent,
)
from app.security import is_http_url, sanitize_theme, slugify
from app.services import archives, news, sketchfab, wikidata
from app.services.ai import (
    RECONSTRUCTION_PROMPT,
    AICard,
    AIError,
    AIFact,
    AIRisk,
    AITheme,
    GeminiAI,
    KeeperAnswer,
    SiteExtraction,
    annotate_with_refs,
)
from app.services.http import api_client, fetch_user_url
from app.services.jobs import JobContext
from app.services.storage import write_bytes

log = logging.getLogger(__name__)


class PipelineError(RuntimeError):
    pass


@dataclass
class SourceDoc:
    ref: int
    kind: str
    title: str
    url: str
    language: str = ""
    text: str = ""


# ---------------------------------------------------------------- helpers

def clean_page_title(title: str) -> str:
    """'Sunbeam Theatre - Wikipedia' -> 'Sunbeam Theatre'."""
    return re.split(r"\s+[|\-–—]\s+", title or "")[0].strip()


def normalize_lang(lang: str | None) -> str:
    code = (lang or "en").strip().lower()
    return code if code in SUPPORTED_LANGUAGES else "en"


def valid_refs(refs: list[int], allowed: set[int]) -> list[int]:
    return sorted({r for r in refs if r in allowed})


def collect_refs(value) -> set[int]:
    """All numbers under any 'source_ids' key in a nested structure."""
    found: set[int] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "source_ids" and isinstance(item, list):
                found.update(i for i in item if isinstance(i, int))
            else:
                found |= collect_refs(item)
    elif isinstance(value, list):
        for item in value:
            found |= collect_refs(item)
    return found


def wikidata_summary(facts: wikidata.WikidataFacts) -> str:
    lines = [f"Label: {facts.label}", f"Description: {facts.description}"]
    if facts.native_label:
        lines.append(f"Native label: {facts.native_label}")
    for code in ("ru", "zh"):
        lbl = facts.label_for(code)
        if lbl and lbl != facts.label:
            lines.append(f"Label ({code}): {lbl}")
    if facts.latitude is not None:
        lines.append(f"Coordinates: {facts.latitude}, {facts.longitude}")
    for label, value in (
        ("Instance of", ", ".join(facts.instance_of)), ("Country", ", ".join(facts.country)),
        ("Located in", ", ".join(facts.located_in)), ("Address", facts.address),
        ("Inception year", facts.inception_year), ("Opening year", facts.opening_year),
        ("Demolished/dissolved year", facts.demolished_year), ("Architects", ", ".join(facts.architects)),
        ("Architectural styles", ", ".join(facts.styles)),
        ("State of conservation", ", ".join(facts.conservation_state)), ("Official website", facts.website),
    ):
        if value:
            lines.append(f"{label}: {value}")
    for designation in facts.heritage_designations:
        year = f" (since {designation['year']})" if designation["year"] else ""
        lines.append(f"Heritage designation: {designation['label']}{year}")
    return "\n".join(lines)


def pick_wiki_languages(facts: wikidata.WikidataFacts, submitted_lang: str | None, local_codes: list[str],
                        target_lang: str = "en", max_languages: int = 4) -> list[str]:
    ordered = []
    for code in [target_lang, submitted_lang, "en", *local_codes, "ru", "zh"]:
        if code and code in facts.sitelinks and code not in ordered:
            ordered.append(code)
    return ordered[:max_languages]


def sources_block(docs: list[SourceDoc], research_text: str = "") -> str:
    parts = ["SOURCES"]
    for doc in docs:
        if not doc.text:
            continue
        header = f"[S{doc.ref}] {doc.title} ({doc.kind}{', ' + doc.language if doc.language else ''}) {doc.url}"
        parts.append(f"{header}\n{doc.text}")
    if research_text:
        parts.append(
            "WEB RESEARCH NOTES (grounded in Google Search). Cite the [S#] markers inside these notes, "
            "never the notes themselves. Unmarked sentences here are unsupported and must not be used.\n"
            + research_text
        )
    return "\n\n---\n\n".join(parts)


STOP_SECTIONS = {
    "references", "notes", "external links", "see also", "bibliography", "further reading", "sources",
    "citations", "footnotes", "примечания", "литература", "ссылки", "см. также", "источники",
    "参考文献", "外部链接", "参见", "注释",
}


def shorten_paragraph(paragraph: str, limit: int = 650) -> str:
    """Whole sentences up to about `limit` characters; citation markers like [12] removed."""
    paragraph = re.sub(r"\[\d+\]", "", paragraph)
    sentences: list[str] = []
    for piece in re.split(r"(?<=[.!?。！？])\s*", paragraph):
        if not piece:
            continue
        # A piece that starts in lower case or with a digit continues an abbreviation such as "r. 69".
        if sentences and re.match(r"^[a-zа-яё0-9]", piece):
            sentences[-1] = f"{sentences[-1]} {piece}"
        else:
            sentences.append(piece)
    kept = ""
    for sentence in sentences:
        if kept and len(kept) + len(sentence) > limit:
            break
        kept = f"{kept} {sentence}".strip()
    return kept


DEFAULT_PASSPORT_ACTIONS = {
    "en": [
        ("Document & Share Memories", "Contribute archival photographs, personal stories, or recordings to preserve the public record."),
        ("Monitor Conservation Status", "Track local planning notices, ownership updates, and heritage protection initiatives connected to this site."),
    ],
    "ru": [
        ("Сохранить живую память и фото", "Загрузите семейные фотографии, устные истории или видеозапись, чтобы дополнить открытый архив памятника."),
        ("Следить за охранным статусом", "Отслеживайте градостроительные решения, реставрационные работы и инициативы по защите культурного наследия."),
    ],
    "zh": [
        ("记录与分享档案记忆", "上传老照片、口述历史或录像，共同丰富该遗产地的公共档案。"),
        ("关注保护现状与修缮动态", "持续追踪与该遗址相关的产权变更、修缮计划及文化遗产保护倡议。"),
    ],
}


def basic_extraction(page_title: str, text: str, facts: wikidata.WikidataFacts | None,
                     wikidata_ref: int | None, lang: str = "en", primary_ref: int = 1) -> SiteExtraction:
    """Record without AI: Wikidata facts plus the first paragraph of each section of the submitted page."""
    paragraphs: list[str] = []
    cards = []
    overview_label = {"en": "Overview", "ru": "Обзор", "zh": "概览"}.get(lang, "Overview")
    heading = overview_label
    used_headings: set[str] = set()
    page_name = clean_page_title(page_title).lower()
    for line in (raw.strip() for raw in text.split("\n")):
        if not line or line.startswith(("[", "|", "- ", "* ", "↑")):
            continue  # edit links, tables, lists and reference entries
        if len(line) < 60 and not line.endswith((".", ":", ";", "。")) and re.search(r"[^\W\d_]", line):
            if line.lower() in STOP_SECTIONS:
                break
            heading = overview_label if line.lower() == page_name else line
            continue
        if len(line) <= 180 and not (lang == "zh" and len(line) >= 60):
            continue
        paragraphs.append(line)
        if heading in used_headings or len(cards) >= 4:
            continue
        used_headings.add(heading)
        cards.append({"title": heading, "content": shorten_paragraph(line), "source_ids": [primary_ref]})

    fact_list = []
    ref = [wikidata_ref] if wikidata_ref else ([primary_ref] if primary_ref else [])
    protection_level = ""
    if facts:
        labels_map = {
            "en": ("Opened", "Built", "Address", "Architect", "Style", "Demolished", "Protection"),
            "ru": ("Открыт", "Построен", "Адрес", "Архитектор", "Стиль", "Утрачен", "Охранный статус"),
            "zh": ("开放年份", "建造年份", "地址", "建筑师", "建筑风格", "拆除年份", "保护级别"),
        }.get(lang, ("Opened", "Built", "Address", "Architect", "Style", "Demolished", "Protection"))
        for label, value in (
            (labels_map[0], facts.opening_year), (labels_map[1], facts.inception_year), (labels_map[2], facts.address),
            (labels_map[3], ", ".join(facts.architects)), (labels_map[4], ", ".join(facts.styles)),
            (labels_map[5], facts.demolished_year),
        ):
            if value:
                fact_list.append({"text": f"{label}: {value}", "source_ids": ref})
        for designation in facts.heritage_designations:
            fact_list.append({"text": f"{labels_map[6]}: {designation['label']}", "source_ids": ref})
        if facts.heritage_designations:
            protection_level = ", ".join(d["label"] for d in facts.heritage_designations)

    title = (facts.label_for(lang) if facts else "") or clean_page_title(page_title) or "Untitled site"
    location = ", ".join(([facts.located_in[0]] if facts and facts.located_in else [])
                         + ([facts.country[0]] if facts and facts.country else []))
    description = (facts.description_for(lang) if facts else "") or (paragraphs[0][:160] if paragraphs else "")
    status = "lost" if facts and facts.demolished_year else "unknown"
    default_actions = [
        AICard(title=t, content=c, source_ids=ref)
        for t, c in DEFAULT_PASSPORT_ACTIONS.get(lang, DEFAULT_PASSPORT_ACTIONS["en"])
    ]
    return SiteExtraction(
        title=title, native_name=facts.native_label if facts else "", location_label=location,
        tagline=description[:1].upper() + description[1:] if description else "",
        tour_cards=cards, culture_title="", culture_subtitle="", culture_cards=[], quick_facts=fact_list,
        did_you_know=AIFact(text="", source_ids=[]), timeline=[],
        risk=AIRisk(status=status, reasons=["demolition"] if status == "lost" else [], summary="", source_ids=ref),
        glossary=[], practitioners=[], disputed_points=[],
        protection_level=protection_level,
        preservation_actions=default_actions,
        theme=AITheme(**sanitize_theme({})),
        latitude=None, longitude=None,
    )


def build_content(extraction: SiteExtraction, allowed: set[int], previous: dict | None,
                  facts: wikidata.WikidataFacts | None = None, lang: str = "en") -> SiteContent:
    previous_cards = (previous or {}).get("tour_cards", [])

    def card(c, index: int | None = None) -> Card:
        result = Card(title=c.title, content=c.content, source_refs=valid_refs(c.source_ids, allowed))
        if index is not None:
            # Keep camera poses a curator saved for the same tour stop position.
            old = previous_cards[index] if index < len(previous_cards) else {}
            result.pose = Pose(**old["pose"]) if old.get("pose") else None
            result.camera = OrbitCamera(**old["camera"]) if old.get("camera") else DEFAULT_TOUR_CAMERAS[index % len(DEFAULT_TOUR_CAMERAS)]
        return result

    dyk = extraction.did_you_know
    protection = extraction.protection_level.strip()
    if not protection and facts and facts.heritage_designations:
        protection = ", ".join(d["label"] for d in facts.heritage_designations if d.get("label"))

    actions = [card(c) for c in (extraction.preservation_actions or []) if c.content.strip()]
    if not actions:
        fallback_ref = sorted(allowed)[:1]
        actions = [
            Card(title=t, content=c, source_refs=fallback_ref)
            for t, c in DEFAULT_PASSPORT_ACTIONS.get(lang, DEFAULT_PASSPORT_ACTIONS["en"])
        ]

    return SiteContent(
        tour_cards=[card(c, i) for i, c in enumerate(extraction.tour_cards) if c.content.strip()],
        culture_title=extraction.culture_title,
        culture_subtitle=extraction.culture_subtitle,
        culture_cards=[card(c) for c in extraction.culture_cards if c.content.strip()],
        quick_facts=[Fact(text=f.text, source_refs=valid_refs(f.source_ids, allowed)) for f in extraction.quick_facts],
        did_you_know=Fact(text=dyk.text, source_refs=valid_refs(dyk.source_ids, allowed)) if dyk and dyk.text else None,
        glossary=[GlossaryTerm(term=g.term, original=g.original, definition=g.definition,
                               source_refs=valid_refs(g.source_ids, allowed)) for g in extraction.glossary],
        practitioners=[
            {"name": p.name, "role": p.role, "description": p.description,
             "source_refs": valid_refs(p.source_ids, allowed)}
            for p in extraction.practitioners if valid_refs(p.source_ids, allowed)
        ],
        disputed_points=[
            {"topic": d.topic, "versions": [{"claim": v.claim, "source_refs": valid_refs(v.source_ids, allowed)}
                                            for v in d.versions]}
            for d in extraction.disputed_points if len(d.versions) > 1
        ],
        protection_level=protection,
        preservation_actions=actions,
    )


def wikidata_events(facts: wikidata.WikidataFacts, ref: int, ai_years: set[int]) -> list[dict]:
    events = []
    candidates = [
        (facts.inception_year, "built", "Construction or founding"),
        (facts.opening_year, "opened", "Opened"),
        (facts.demolished_year, "demolition", "Demolished or dissolved"),
    ] + [(d["year"], "designation", f"Designated: {d['label']}") for d in facts.heritage_designations]
    for year, kind, title in candidates:
        if year is None or year in ai_years:
            continue
        events.append({"year": year, "date_text": str(year), "title": title, "kind": kind,
                       "source_refs": [ref], "origin": "wikidata"})
    return events


def unique_slug(conn, title: str, site_id: int | None) -> str:
    base = slugify(title)
    slug, n = base, 2
    while True:
        existing = repo.get_site_by_slug(conn, slug)
        if existing is None or existing["id"] == site_id:
            return slug
        slug, n = f"{base}-{n}", n + 1


def _search_wikidata_compatible(client, query: str, lang: str = "en") -> list[dict]:
    """Call wikidata.search_items while staying compatible with 2-arg test monkeypatches."""
    try:
        return wikidata.search_items(client, query, lang=lang)
    except TypeError:
        return wikidata.search_items(client, query)


# ---------------------------------------------------------------- site generation

def generate_site(ctx: JobContext, url_or_query: str, lang: str = "en") -> dict:
    settings = ctx.settings
    ai = GeminiAI(settings)
    lang = normalize_lang(lang)
    raw_input = (url_or_query or "").strip()
    is_url = is_http_url(raw_input)

    docs: list[SourceDoc] = []
    facts: wikidata.WikidataFacts | None = None
    wikidata_ref: int | None = None
    page_title = ""
    text = ""
    source_url = ""
    wiki_parsed: tuple[str, str] | None = None

    if is_url:
        ctx.step("Reading the submitted page")
        page = fetch_user_url(raw_input, settings)
        source_url = page.url
        doc = trafilatura.bare_extraction(page.text, url=page.url, with_metadata=True, include_comments=False)
        text = (doc.text if doc else "") or ""
        page_title = (doc.title if doc else "") or ""
        if len(text) < 200:
            raise PipelineError("Could not extract enough readable text from this page.")
        ctx.note(clean_page_title(page_title))
        docs.append(SourceDoc(
            ref=1, kind="submitted_url", title=clean_page_title(page_title) or page.url, url=page.url,
            language=(doc.language if doc else "") or "", text=text[:15000],
        ))
        wiki_parsed = wikidata.parse_wikipedia_url(page.url)
    else:
        page_title = raw_input
        ctx.step(f"Searching Wikidata & Wikipedia for '{raw_input}'")

    with api_client(settings) as client:
        if is_url:
            ctx.step("Linking the place to Wikidata")
        try:
            qid = wikidata.qid_for_wikipedia_article(client, *wiki_parsed) if wiki_parsed else None
            if not qid and page_title:
                search_lang = wikidata.detect_query_language(page_title, default=lang)
                candidates = _search_wikidata_compatible(client, clean_page_title(page_title), lang=search_lang)
                if not candidates and search_lang != "en":
                    candidates = _search_wikidata_compatible(client, clean_page_title(page_title), lang="en")
                qid = wikidata.pick_qid_from_search(
                    candidates, clean_page_title(page_title), allow_top_hit=not is_url
                )
            if qid:
                facts = wikidata.fetch_facts(client, qid)
                ctx.note(f"{qid}: {facts.label_for(lang) or facts.label}")
            else:
                ctx.warn("No matching Wikidata item; coordinates will come from the text and need checking.")
        except Exception as exc:  # noqa: BLE001 - enrichment is optional
            ctx.warn(f"Wikidata unavailable: {exc}")

        if facts:
            local: list[str] = []
            try:
                local = wikidata.local_wiki_languages(client, facts.country_qids)
                facts.set_native_label([*local, "ru", "zh", "zh-hant", "zh-hans"])
            except Exception as exc:  # noqa: BLE001
                ctx.warn(f"Could not resolve local languages: {exc}")

            # When generated from a place name (no URL), pull Wikipedia articles first so [S1] is the primary article,
            # or if none exist, use Wikidata + web research.
            ctx.step("Collecting Wikipedia articles in local & target languages")
            try:
                languages = pick_wiki_languages(facts, wiki_parsed[0] if wiki_parsed else None, local, target_lang=lang)
                for wlang in languages:
                    title = facts.sitelinks[wlang]
                    article_url = f"https://{wlang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
                    if wiki_parsed and wlang == wiki_parsed[0]:
                        continue  # already the submitted page
                    body = wikidata.wikipedia_plaintext(client, wlang, title)
                    if body:
                        if not source_url:
                            source_url = article_url
                        if not text:
                            text = body
                        docs.append(SourceDoc(
                            ref=len(docs) + 1, kind="wikipedia", title=f"Wikipedia ({wlang}): {title}",
                            url=article_url, language=wlang, text=body,
                        ))
                ctx.note(", ".join(d.language for d in docs if d.kind == "wikipedia") or "no extra languages")
            except Exception as exc:  # noqa: BLE001
                ctx.warn(f"Could not load extra articles: {exc}")

            wikidata_ref = len(docs) + 1
            wikidata_url = f"https://www.wikidata.org/wiki/{facts.qid}"
            if not source_url:
                source_url = wikidata_url
            # Maintain exact source ordering for URL submissions: [1] submitted_url, [2] wikidata, [3+] wikipedia
            if is_url and len(docs) > 1:
                wiki_docs = docs[1:]
                docs = [
                    docs[0],
                    SourceDoc(ref=2, kind="wikidata", title=f"Wikidata {facts.qid}", url=wikidata_url,
                              text=wikidata_summary(facts)),
                ]
                wikidata_ref = 2
                for wd in wiki_docs:
                    wd.ref = len(docs) + 1
                    docs.append(wd)
            else:
                docs.append(SourceDoc(
                    ref=wikidata_ref, kind="wikidata", title=f"Wikidata {facts.qid}",
                    url=wikidata_url, text=wikidata_summary(facts),
                ))

    research_text = ""
    if ai.enabled and settings.use_search_grounding:
        ctx.step("Searching the web for recent information")
        try:
            location_hint = ", ".join((facts.located_in[:1] + facts.country[:1]) if facts else [])
            search_title = (facts.label_for(lang) or facts.label) if facts else clean_page_title(page_title)
            try:
                research = ai.research(search_title, location_hint, lang=lang)
            except TypeError:
                research = ai.research(search_title, location_hint)
            chunk_refs = {}
            for index, chunk in enumerate(research.chunks):
                if not chunk:
                    continue
                existing = next((d for d in docs if d.url == chunk["url"]), None)
                if existing is None:
                    existing = SourceDoc(ref=len(docs) + 1, kind="web", title=chunk["title"], url=chunk["url"])
                    docs.append(existing)
                chunk_refs[index] = existing.ref
            research_text = annotate_with_refs(research.text, research.supports, chunk_refs)
            if not source_url and research.chunks:
                first_chunk = next((c for c in research.chunks if c and c.get("url")), None)
                if first_chunk:
                    source_url = first_chunk["url"]
            ctx.note(f"{len(chunk_refs)} web sources")
        except AIError as exc:
            ctx.warn(f"Web research skipped: {exc}")

    if not docs and not research_text:
        raise PipelineError(
            f"Could not find enough verified sources for '{raw_input}'. Try pasting a Wikipedia or article URL."
        )

    ctx.step("Writing the record with citations" if ai.enabled else "Building a basic record (AI not configured)")
    if ai.enabled:
        hints = (
            f"TARGET LANGUAGE: {lang} ({SUPPORTED_LANGUAGES[lang]['label']})\n"
            "SITE HINTS\n" + (wikidata_summary(facts) if facts else f"Place query / title: {clean_page_title(page_title)}")
        )
        try:
            extraction = ai.extract_site(sources_block(docs, research_text), hints, lang=lang)
        except TypeError:
            extraction = ai.extract_site(sources_block(docs, research_text), hints)
        mode = "ai"
    else:
        primary_ref = docs[0].ref if docs else 1
        extraction = basic_extraction(page_title, text, facts, wikidata_ref, lang=lang, primary_ref=primary_ref)
        mode = "basic"

    allowed = {d.ref for d in docs}
    cited = collect_refs(extraction.model_dump())

    ctx.step("Saving to the archive")
    with session(settings.db_path) as conn:
        existing = repo.find_site_for_generation(conn, facts.qid if facts else None, source_url or raw_input)
        content = build_content(extraction, allowed, existing["content"] if existing else None, facts=facts, lang=lang)

        latitude = longitude = None
        coord_source = "none"
        if facts and facts.latitude is not None:
            latitude, longitude, coord_source = facts.latitude, facts.longitude, "wikidata"
        elif extraction.latitude is not None and extraction.longitude is not None \
                and -90 <= extraction.latitude <= 90 and -180 <= extraction.longitude <= 180 \
                and not (extraction.latitude == 0 and extraction.longitude == 0):
            latitude, longitude, coord_source = extraction.latitude, extraction.longitude, "ai"

        risk_status = extraction.risk.status if extraction.risk.status in RISK_STATUSES else "unknown"
        resolved_title = extraction.title.strip() or (facts.label_for(lang) if facts else "") or clean_page_title(page_title) or "Untitled site"
        data = {
            "wikidata_qid": facts.qid if facts else None,
            "source_url": source_url,
            "title": resolved_title,
            "native_name": extraction.native_name or (facts.native_label if facts else ""),
            "location_label": extraction.location_label,
            "tagline": extraction.tagline,
            "latitude": latitude, "longitude": longitude, "coord_source": coord_source,
            "facts": facts.to_dict() if facts else {},
            "content": content.model_dump(mode="json"),
            "theme": sanitize_theme(extraction.theme.model_dump()),
            "risk_status": risk_status,
            "risk_reasons": list(dict.fromkeys(extraction.risk.reasons)),
            "risk_summary": extraction.risk.summary,
            "risk_source_refs": valid_refs(extraction.risk.source_ids, allowed),
            "risk_updated_at": repo.now_iso(),
            "language": lang,
            "generation_mode": mode,
        }
        if existing:
            site_id = existing["id"]
            data["slug"] = existing["slug"]
            repo.update_site(conn, site_id, data)
        else:
            slug_seed = (facts.label if facts and facts.label else resolved_title)
            data["slug"] = unique_slug(conn, slug_seed, None)
            site_id = repo.insert_site(conn, data)

        # Uncited web search hits are dropped. Refs are not renumbered, so gaps are possible.
        kept = [d for d in docs if d.ref in cited or d.kind != "web"]
        repo.replace_sources(conn, site_id, [d.__dict__ for d in kept])
        repo.delete_generated_events(conn, site_id)
        ai_years = set()
        for event in extraction.timeline:
            if event.year is not None:
                ai_years.add(event.year)
            repo.insert_event(conn, site_id, {
                "year": event.year, "date_text": event.date_text, "title": event.title,
                "description": event.description, "kind": event.kind,
                "source_refs": valid_refs(event.source_ids, allowed), "origin": "ai",
            })
        if facts and wikidata_ref:
            for event in wikidata_events(facts, wikidata_ref, ai_years):
                repo.insert_event(conn, site_id, event)
        slug = data["slug"]
    ctx.set_site(site_id)

    # Enrichment steps never fail the whole job.
    for label, fn in (("Finding archive photographs", refresh_photos), 
                      ("Checking the news", check_news)):
        ctx.step(label)
        try:
            summary = fn(settings, site_id)
            ctx.note(summary)
        except Exception as exc:  # noqa: BLE001
            ctx.warn(f"Skipped: {exc}")

    return {"site_slug": slug, "mode": mode}


# ---------------------------------------------------------------- AI Keeper ("Ask the Archive")

def _build_keeper_context(site: dict, sources: list[dict], events: list[dict], memories: list[dict]) -> str:
    content = site.get("content") or {}
    lines = [
        f"SITE: {site['title']} ({site.get('native_name', '')}) — {site.get('location_label', '')}",
        f"TAGLINE: {site.get('tagline', '')}",
        f"RISK STATUS: {site.get('risk_status', 'unknown')} — {site.get('risk_summary', '')} "
        f"{''.join(f'[S{r}]' for r in (site.get('risk_source_refs') or []))}",
    ]
    if content.get("protection_level"):
        lines.append(f"PROTECTION STATUS: {content['protection_level']}")
    lines.append("\nTOUR STOPS:")
    for card in content.get("tour_cards", []):
        refs = "".join(f"[S{r}]" for r in card.get("source_refs", []))
        lines.append(f"- {card['title']}: {card['content']} {refs}")
    lines.append("\nLIVING HERITAGE:")
    for card in content.get("culture_cards", []):
        refs = "".join(f"[S{r}]" for r in card.get("source_refs", []))
        lines.append(f"- {card['title']}: {card['content']} {refs}")
    lines.append("\nQUICK FACTS:")
    for fact in content.get("quick_facts", []):
        refs = "".join(f"[S{r}]" for r in fact.get("source_refs", []))
        lines.append(f"- {fact['text']} {refs}")
    if content.get("did_you_know") and content["did_you_know"].get("text"):
        dyk = content["did_you_know"]
        refs = "".join(f"[S{r}]" for r in dyk.get("source_refs", []))
        lines.append(f"- Did you know: {dyk['text']} {refs}")
    lines.append("\nCHRONICLE EVENTS:")
    for ev in events[:25]:
        refs = "".join(f"[S{r}]" for r in ev.get("source_refs", []))
        lines.append(f"- {ev.get('date_text') or ev.get('year') or '—'}: {ev['title']} — {ev.get('description', '')} {refs}")
    if memories:
        lines.append("\nVISITOR MEMORIES:")
        for mem in memories[:10]:
            yr = mem.get("year_given") or mem.get("year_estimate") or ""
            txt = mem.get("text_en") or mem.get("transcript") or mem.get("text_original") or ""
            lines.append(f"- ({mem.get('author_name') or 'Visitor'}, {yr}): {txt[:240]}")
    lines.append("\nSOURCES:")
    for src in sources:
        lines.append(f"- [S{src['ref']}] {src.get('title', '')} ({src.get('url', '')})")
    return "\n".join(lines)


def _fallback_keeper_answer(site: dict, sources: list[dict], events: list[dict], memories: list[dict],
                            question: str, mode: str, lang: str) -> dict:
    """Deterministic source-grounded answer when GEMINI_API_KEY is not configured."""
    content = site.get("content") or {}
    q_words = {w.lower() for w in re.findall(r"\w{3,}", question.lower())}
    allowed_refs = {s["ref"] for s in sources}

    candidates: list[tuple[int, str, list[int]]] = []
    for card in content.get("tour_cards", []) + content.get("culture_cards", []):
        text = f"{card.get('title', '')}: {card.get('content', '')}"
        score = sum(1 for w in q_words if w in text.lower())
        candidates.append((score, card.get("content", ""), card.get("source_refs", [])))
    for ev in events:
        text = f"{ev.get('date_text') or ev.get('year') or ''} {ev.get('title', '')}: {ev.get('description', '')}".strip()
        score = sum(1 for w in q_words if w in text.lower())
        candidates.append((score, text, ev.get("source_refs", [])))
    if site.get("risk_summary"):
        score = sum(1 for w in q_words if w in site["risk_summary"].lower() or w in ("risk", "status", "closed", "threat", "риск", "статус", "угроз", "закрыт", "风险", "现状"))
        candidates.append((score + (2 if score else 0), site["risk_summary"], site.get("risk_source_refs", [])))

    candidates.sort(key=lambda item: item[0], reverse=True)
    chosen = [c for c in candidates if c[0] > 0][:2] or candidates[:2]
    cited: list[int] = []
    snippets: list[str] = []
    for _, text, refs in chosen:
        valid = [r for r in refs if r in allowed_refs]
        for r in valid:
            if r not in cited:
                cited.append(r)
        marker = " " + "".join(f"[S{r}]" for r in valid) if valid else ""
        snippets.append(f"{text}{marker}")

    body = " ".join(snippets).strip() or site.get("tagline", "")
    if mode == "voice":
        prefix = {
            "ru": f"Я — {site['title']}. Из моей хроники: ",
            "zh": f"我是{site['title']}。根据我的档案记载：",
            "en": f"I am {site['title']}. From my recorded chronicle: ",
        }.get(lang, f"I am {site['title']}. From my recorded chronicle: ")
        body = prefix + body

    follow_ups = {
        "ru": [
            f"Какие главные угрозы для «{site['title']}» сегодня?",
            "Какие ключевые даты изменили историю этого места?",
            "Как можно помочь сохранению памятника?",
        ],
        "zh": [
            f"{site['title']}目前面临哪些主要风险？",
            "有哪些关键历史节点改变了这里？",
            "公众可以如何参与保护与记录？",
        ],
        "en": [
            f"What are the main risks facing {site['title']} today?",
            "Which key dates shaped the history of this place?",
            "How can visitors help preserve this heritage?",
        ],
    }.get(lang, [
        f"What are the main risks facing {site['title']} today?",
        "Which key dates shaped the history of this place?",
        "How can visitors help preserve this heritage?",
    ])
    return {"answer": body, "cited_refs": sorted(cited), "follow_up_questions": follow_ups, "mode": mode}


def answer_keeper_question(settings: Settings, site_id: int, question: str, mode: str = "archivist",
                           lang: str | None = None) -> dict:
    ai = GeminiAI(settings)
    with session(settings.db_path) as conn:
        site = repo.get_site(conn, site_id)
        if not site:
            raise PipelineError("Site not found.")
        sources = repo.list_sources(conn, site_id)
        events = repo.list_events(conn, site_id)
        memories = repo.list_memories(conn, site_id)

    effective_lang = normalize_lang(lang or wikidata.detect_query_language(question, default=site.get("language", "en")))
    mode = "voice" if mode == "voice" else "archivist"
    allowed_refs = {s["ref"] for s in sources}

    if ai.enabled:
        try:
            ctx_text = _build_keeper_context(site, sources, events, memories)
            res: KeeperAnswer = ai.ask_keeper(
                site_context=ctx_text, question=question, mode=mode, lang=effective_lang
            )
            refs = valid_refs(res.cited_refs, allowed_refs)
            for m in re.findall(r"\[S(\d+)\]", res.answer):
                num = int(m)
                if num in allowed_refs and num not in refs:
                    refs.append(num)
            return {
                "answer": res.answer,
                "cited_refs": sorted(refs),
                "follow_up_questions": res.follow_up_questions[:3],
                "mode": mode,
            }
        except AIError as exc:
            log.warning("AI Keeper fallback triggered: %s", exc)

    return _fallback_keeper_answer(site, sources, events, memories, question, mode, effective_lang)


# ---------------------------------------------------------------- enrichment

def refresh_photos(settings: Settings, site_id: int) -> str:
    ai = GeminiAI(settings)
    with session(settings.db_path) as conn:
        site = repo.get_site(conn, site_id)
    if not site:
        raise PipelineError("Site not found.")
    facts = site["facts"] or {}
    candidates: dict[str, dict] = {}
    with api_client(settings) as client:
        providers = []
        if facts.get("image"):
            providers.append(lambda: archives._commons_imageinfo(client, ["File:" + facts["image"].removeprefix("File:")]))
        if facts.get("commons_category"):
            providers.append(lambda: archives.commons_category_photos(client, facts["commons_category"]))
        if site["latitude"] is not None:
            providers.append(lambda: archives.commons_nearby_photos(client, site["latitude"], site["longitude"]))
        if settings.europeana_api_key:
            providers.append(lambda: archives.europeana_photos(client, settings.europeana_api_key, site["title"]))
        for fetch in providers:
            try:
                for photo in fetch():
                    candidates.setdefault(photo["provider_id"], photo)
            except Exception as exc:
                log.warning("Archive photo source unavailable: %s", exc)
    photos = list(candidates.values())[:120]
    if not photos:
        return "No photographs found."

    if ai.enabled:
        for start in range(0, len(photos), 40):
            batch = photos[start:start + 40]
            try:
                ranking = ai.rank_photos(site["title"], site["location_label"], batch)
            except AIError as exc:
                log.warning("photo ranking failed: %s", exc)
                continue
            for verdict in ranking.verdicts:
                if 0 <= verdict.index < len(batch):
                    photo = batch[verdict.index]
                    photo["status"] = "approved" if verdict.relevant else "rejected"
                    photo["relevance_note"] = f"AI: {verdict.reason}"
                    if photo.get("year") is None and verdict.year:
                        photo["year"], photo["year_source"] = verdict.year, "ai_estimate"
    else:
        # Without AI, only photos that name the site are published straight away; the rest wait for a curator.
        names = [n.lower() for n in (site["title"], site["native_name"], facts.get("label", "")) if n and len(n) > 1]
        for photo in photos:
            haystack = f"{photo.get('title', '')} {photo.get('description', '')}".lower()
            if any(name in haystack for name in names):
                photo["status"] = "approved"
                photo["relevance_note"] = "Matched by site name"

    inserted = 0
    with session(settings.db_path) as conn:
        for photo in photos:
            inserted += repo.upsert_photo_candidate(conn, site_id, photo)
    approved = sum(1 for p in photos if p.get("status") == "approved")
    return f"{inserted} new photos, {approved} matched automatically, the rest wait for review"


def find_models(settings: Settings, site_id: int) -> str:
    if not settings.sketchfab_enabled:
        return "Sketchfab search disabled."
    with session(settings.db_path) as conn:
        site = repo.get_site(conn, site_id)
    facts = (site or {}).get("facts") or {}
    search_title = facts.get("label") or site["title"]
    with api_client(settings) as client:
        models = sketchfab.search_models(client, search_title)
    inserted = 0
    with session(settings.db_path) as conn:
        for model in models:
            inserted += repo.upsert_scan(conn, site_id, model)
    return f"{inserted} candidate scans for review"


def check_news(settings: Settings, site_id: int) -> str:
    if settings.news_provider == "none":
        return "News monitoring disabled."
    ai = GeminiAI(settings)
    with session(settings.db_path) as conn:
        site = repo.get_site(conn, site_id)
    with api_client(settings) as client:
        items = news.fetch_news(client, settings.news_provider, f'"{site["title"]}"')
    new_items = []
    with session(settings.db_path) as conn:
        for item in items:
            news_id = repo.insert_news_item(conn, site_id, item)
            if news_id:
                new_items.append({**item, "id": news_id})
    if not new_items:
        return "No new articles."
    if ai.enabled:
        for start in range(0, len(new_items), 25):
            batch = new_items[start:start + 25]
            triage = ai.triage_news(site_title=site["title"], location=site["location_label"],
                                    current_status=site["risk_status"], items=batch)
            with session(settings.db_path) as conn:
                for verdict in triage.verdicts:
                    if 0 <= verdict.index < len(batch):
                        analysis = verdict.model_dump()
                        if analysis["suggested_status"] == "no_change":
                            analysis["suggested_status"] = ""
                        repo.update_news_ai(conn, batch[verdict.index]["id"], analysis)
    return f"{len(new_items)} new articles"


# ---------------------------------------------------------------- community memories

def _audio_for_ai(path: Path, mime: str) -> tuple[bytes, str]:
    """Gemini reads WAV/MP3/OGG/FLAC/AAC. Browser recordings (WebM/MP4) are converted with ffmpeg when available."""
    if mime in ("audio/wav", "audio/mpeg", "audio/ogg", "audio/flac", "audio/aac"):
        return path.read_bytes(), mime
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return path.read_bytes(), mime
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "audio.wav"
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", "16000", str(out)],
                       check=True, timeout=120)
        return out.read_bytes(), "audio/wav"


def process_memory(settings: Settings, memory_id: int) -> str:
    ai = GeminiAI(settings)
    with session(settings.db_path) as conn:
        memory = repo.get_memory(conn, memory_id)
        site = repo.get_site(conn, memory["site_id"]) if memory else None
    if not memory or not site:
        raise PipelineError("Memory not found.")
    if not ai.enabled:
        with session(settings.db_path) as conn:
            repo.update_memory_ai(conn, memory_id, {"ai_status": "skipped"})
        return "AI not configured; curators will review the original."

    media = None
    if memory["file_path"]:
        path = settings.uploads_dir / memory["file_path"]
        media = _audio_for_ai(path, memory["mime_type"]) if memory["kind"] == "audio" else (path.read_bytes(), memory["mime_type"])
    try:
        analysis = ai.analyse_memory(site_title=site["title"], kind=memory["kind"], text=memory["text_original"],
                                     media=media, year_given=memory["year_given"])
    except (AIError, subprocess.SubprocessError) as exc:
        with session(settings.db_path) as conn:
            repo.update_memory_ai(conn, memory_id, {"ai_status": "failed", "ai_error": str(exc)[:500]})
        raise
    fields = analysis.model_dump()
    fields["ai_status"] = "done"
    with session(settings.db_path) as conn:
        repo.update_memory_ai(conn, memory_id, fields)
    return "Transcribed, translated and tagged."


# ---------------------------------------------------------------- AI hypothesis

def generate_reconstruction(settings: Settings, site_id: int, photo_ids: list[int], focus: str,
                            target_year: int | None) -> str:
    ai = GeminiAI(settings)
    if not ai.enabled:
        raise PipelineError("GEMINI_API_KEY is required for AI hypotheses.")
    with session(settings.db_path) as conn:
        site = repo.get_site(conn, site_id)
        photos = [p for p in (repo.get_photo(conn, pid) for pid in photo_ids[:3]) if p and p["site_id"] == site_id]
    if not photos:
        raise PipelineError("Select at least one approved photograph of this site.")

    images = []
    with api_client(settings, timeout=60) as client:
        for photo in photos:
            if photo["image_url"].startswith("/media/"):
                path = settings.uploads_dir / photo["image_url"].removeprefix("/media/")
                data = path.read_bytes()
            else:
                response = client.get(photo["image_url"])
                response.raise_for_status()
                data = response.content
            mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
            images.append((data[:7 * 1024 * 1024], mime))

    prompt = RECONSTRUCTION_PROMPT.format(
        title=site["title"], location=site["location_label"], focus=focus or "the site as it originally stood",
        year_clause=f" around {target_year}" if target_year else "",
    )
    data, mime = ai.reconstruct_image(images, prompt)
    ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".png")
    relative = write_bytes(settings.uploads_dir, "reconstructions", data, ext)
    with session(settings.db_path) as conn:
        repo.insert_reconstruction(conn, site_id, {
            "image_path": relative, "focus": focus, "target_year": target_year, "prompt": prompt,
            "input_photo_ids": [p["id"] for p in photos], "model": settings.gemini_image_model,
        })
    return "Hypothesis generated and waiting for curator review."
