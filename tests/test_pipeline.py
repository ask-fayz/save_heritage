"""Site generation with network and Gemini replaced by fakes."""

import pytest

from app import repo
from app.db import init_db, session
from app.services import pipeline, wikidata
from app.services.ai import AICard, AIEvent, AIFact, AIRisk, AITheme, GeminiAI, ResearchResult, SiteExtraction
from app.services.http import FetchedPage
from app.services.jobs import JobRunner

ARTICLE = "<html><head><title>Old Mill - Wikipedia</title></head><body><article>" + "".join(
    f"<p>Paragraph {i}: the Old Mill is a watermill on the river, built in 1820 by the Smith family and used for "
    f"grinding grain for more than a century before it became a museum of rural life (part {i}).</p>"
    for i in range(6)
) + "</article></body></html>"


def fake_facts() -> wikidata.WikidataFacts:
    return wikidata.WikidataFacts(
        qid="Q42", label="Old Mill", description="watermill museum", latitude=51.5, longitude=-0.12,
        inception_year=1820, country=["United Kingdom"], country_qids=["Q145"], located_in=["Somerset"],
        commons_category="Old Mill", sitelinks={"en": "Old Mill"}, all_labels={"en": "Old Mill"},
    )


class FakeAI:
    enabled = True
    last_sources_block = ""

    def __init__(self, settings):
        pass

    def research(self, title, location):
        return ResearchResult(
            text="The mill closed in 2024.",
            chunks=[{"url": "https://news.example/mill", "title": "news.example"}, None],
            supports=[{"text": "The mill closed in 2024.", "chunks": [0]}],
        )

    def extract_site(self, sources_block, hints):
        FakeAI.last_sources_block = sources_block
        return SiteExtraction(
            title="Old Mill", native_name="", location_label="Somerset, United Kingdom",
            tagline="A watermill that fed a village for a century.",
            tour_cards=[AICard(title="The wheel", content="Built in 1820.", source_ids=[1, 99]),
                        AICard(title="Today", content="Closed in 2024.", source_ids=[4])],
            culture_title="Milling", culture_subtitle="",
            culture_cards=[AICard(title="Grain", content="Grain was ground here.", source_ids=[1])],
            quick_facts=[AIFact(text="Built 1820", source_ids=[2])],
            did_you_know=AIFact(text="It became a museum.", source_ids=[1]),
            timeline=[AIEvent(year=1820, date_text="1820", title="Built", description="", kind="built", source_ids=[1]),
                      AIEvent(year=2024, date_text="2024", title="Closed", description="", kind="closure", source_ids=[4])],
            risk=AIRisk(status="lost", reasons=["funding"], summary="Closed in 2024.", source_ids=[4]),
            glossary=[], practitioners=[], disputed_points=[],
            theme=AITheme(bg="#101010", bg_darker="#050505", accent_red="#aa2222", accent_gold="#ccaa33",
                          text_cream="url(javascript:1)", card_bg="#202020", border_color="#303030"),
            latitude=0.0, longitude=0.0,
        )


@pytest.fixture
def patched(monkeypatch, settings):
    init_db(settings.db_path)
    monkeypatch.setattr(pipeline, "fetch_user_url",
                        lambda url, s: FetchedPage(url="https://example.org/old-mill", content_type="text/html", text=ARTICLE))
    monkeypatch.setattr(wikidata, "search_items", lambda client, q: [{"qid": "Q42", "label": "Old Mill"}])
    monkeypatch.setattr(wikidata, "fetch_facts", lambda client, qid: fake_facts())
    monkeypatch.setattr(wikidata, "local_wiki_languages", lambda client, qids: ["en"])
    monkeypatch.setattr(wikidata, "wikipedia_plaintext", lambda client, lang, title: "The Old Mill article text.")
    for name in ("refresh_photos", "find_models", "check_news"):
        monkeypatch.setattr(pipeline, name, lambda s, site_id: "skipped in tests")
    monkeypatch.setattr(pipeline, "GeminiAI", FakeAI)
    settings.gemini_api_key = "test"
    return settings


def run(settings, url="https://example.org/old-mill"):
    runner = JobRunner(settings, synchronous=True)
    job_id = runner.submit("generate", lambda ctx: pipeline.generate_site(ctx, url))
    with session(settings.db_path) as conn:
        return repo.get_job(conn, job_id)


def test_generate_site_with_citations(patched):
    job = run(patched)
    assert job["status"] == "done", job["error"]
    assert job["result"] == {"site_slug": "old-mill", "mode": "ai"}
    with session(patched.db_path) as conn:
        site = repo.get_site_by_slug(conn, "old-mill")
        sources = repo.list_sources(conn, site["id"])
        events = repo.list_events(conn, site["id"])

    # Submitted page [1], Wikidata [2], English Wikipedia [3], cited web result [4].
    assert [s["kind"] for s in sources] == ["submitted_url", "wikidata", "wikipedia", "web"]
    assert "[S4]" in FakeAI.last_sources_block
    assert site["wikidata_qid"] == "Q42"
    assert (site["latitude"], site["longitude"], site["coord_source"]) == (51.5, -0.12, "wikidata")
    assert site["content"]["tour_cards"][0]["source_refs"] == [1]  # unknown ref 99 dropped
    assert site["content"]["tour_cards"][0]["camera"]["range"] > 0
    assert site["theme"]["text_cream"].startswith("#")  # injected CSS value replaced
    assert site["risk_status"] == "lost" and site["risk_source_refs"] == [4]
    assert [(e["year"], e["origin"]) for e in events] == [(1820, "ai"), (2024, "ai")]  # Wikidata 1820 deduplicated


def test_regeneration_updates_same_site_and_keeps_curator_work(patched):
    assert run(patched)["status"] == "done"
    with session(patched.db_path) as conn:
        site = repo.get_site_by_slug(conn, "old-mill")
        repo.insert_event(conn, site["id"], {"year": 1900, "title": "Curator note", "origin": "curator"})
        content = site["content"]
        content["tour_cards"][0]["pose"] = {"longitude": -0.12, "latitude": 51.5, "height": 80, "heading": 10,
                                            "pitch": -20, "roll": 0, "fov": 50, "aspect": None}
        repo.update_site(conn, site["id"], {"content": content})

    assert run(patched)["status"] == "done"
    with session(patched.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0] == 1
        site = repo.get_site_by_slug(conn, "old-mill")
        origins = [e["origin"] for e in repo.list_events(conn, site["id"])]
    assert origins.count("curator") == 1 and origins.count("ai") == 2
    assert site["content"]["tour_cards"][0]["pose"]["height"] == 80


def test_basic_mode_without_ai(patched, monkeypatch):
    patched.gemini_api_key = ""
    monkeypatch.setattr(pipeline, "GeminiAI", GeminiAI)
    job = run(patched)
    assert job["status"] == "done", job["error"]
    with session(patched.db_path) as conn:
        site = repo.get_site_by_slug(conn, "old-mill")
        events = repo.list_events(conn, site["id"])
    assert site["generation_mode"] == "basic"
    assert site["content"]["tour_cards"], "opening paragraphs become tour stops"
    assert [(e["year"], e["origin"]) for e in events] == [(1820, "wikidata")]


def test_unreadable_page_fails_cleanly(patched, monkeypatch):
    monkeypatch.setattr(pipeline, "fetch_user_url",
                        lambda url, s: FetchedPage(url=url, content_type="text/html", text="<html><body>hi</body></html>"))
    job = run(patched)
    assert job["status"] == "failed"
    assert "readable text" in job["error"]


def test_basic_cards_use_section_headings_and_whole_sentences():
    text = "\n".join([
        "Old Mill",
        "The Old Mill (r. 1820) is a watermill on the river. It ground grain for a century. " * 8,
        "History",
        "[edit]",
        "| Built | 1820 |",
        "In 1900 the wheel was replaced after a flood destroyed the original mechanism and most of the sluice gates. " * 3,
        "References",
        "Some reference entry that is long enough to look like a paragraph but must never become a tour stop at all.",
    ])
    cards = pipeline.basic_extraction("Old Mill - Wikipedia", text, None, None).tour_cards
    assert [c.title for c in cards] == ["Overview", "History"]
    assert cards[0].content.endswith(".") and "(r. 1820)" in cards[0].content
    assert len(cards[0].content) <= 700


def test_generate_site_by_place_name_and_language(patched):
    runner = JobRunner(patched, synchronous=True)
    job_id = runner.submit("generate", lambda ctx: pipeline.generate_site(ctx, "Old Mill", lang="ru"))
    with session(patched.db_path) as conn:
        job = repo.get_job(conn, job_id)
        site = repo.get_site_by_slug(conn, "old-mill")
    assert job["status"] == "done", job["error"]
    assert site is not None
    assert site["language"] == "ru"
    assert site["wikidata_qid"] == "Q42"
    assert site["content"]["preservation_actions"], "Preservation Passport actions populated"


def test_generated_place_persists_and_appears_on_map_after_restart(patched):
    import json
    import re
    from fastapi.testclient import TestClient
    from app.main import create_app

    job = run(patched)
    assert job['status'] == 'done'
    for _ in range(2):
        with TestClient(create_app(patched, synchronous_jobs=True)) as client:
            home = client.get('/')
            payload = re.search(r'<script id="heritage-map-data" type="application/json">(.*?)</script>', home.text, re.S)
            markers = json.loads(payload.group(1))
            assert any(m['slug'] == 'old-mill' and m['latitude'] == 51.5 for m in markers)
            assert client.get('/site/old-mill').status_code == 200
            assert 'Old Mill' in client.get('/archive').text
