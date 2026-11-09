"""Parsing of open-data responses (no network)."""

from app.services import archives, news, sketchfab, wikidata
from app.services.ai import annotate_with_refs

ENTITY = {
    "id": "Q2113185",
    "labels": {"en": {"value": "Sunbeam Theatre"}, "zh-hant": {"value": "新光戲院"}, "fr": {"value": "Théâtre Sunbeam"}},
    "descriptions": {"en": {"value": "theatre and opera house in Hong Kong"}},
    "claims": {
        "P625": [{"mainsnak": {"datavalue": {"value": {"latitude": 22.2913, "longitude": 114.2}}}, "rank": "normal"}],
        "P1619": [{"mainsnak": {"datavalue": {"value": {"time": "+1972-00-00T00:00:00Z"}}}, "rank": "normal"}],
        "P576": [{"mainsnak": {"datavalue": {"value": {"time": "-0070-00-00T00:00:00Z"}}}, "rank": "deprecated"}],
        "P17": [{"mainsnak": {"datavalue": {"value": {"id": "Q148"}}}, "rank": "normal"}],
        "P1435": [{"mainsnak": {"datavalue": {"value": {"id": "Q1"}}}, "rank": "normal",
                   "qualifiers": {"P580": [{"datavalue": {"value": {"time": "+2009-09-30T00:00:00Z"}}}]}}],
        "P373": [{"mainsnak": {"datavalue": {"value": "Sunbeam Theatre"}}, "rank": "normal"}],
    },
    "sitelinks": {"enwiki": {"title": "Sunbeam Theatre"}, "zh_yuewiki": {"title": "新光戲院"},
                  "commonswiki": {"title": "Category:Sunbeam Theatre"}},
}


def test_parse_entity():
    facts = wikidata.parse_entity(ENTITY, {"Q148": "People's Republic of China", "Q1": "Grade I historic building"})
    assert (facts.latitude, facts.longitude) == (22.2913, 114.2)
    assert facts.opening_year == 1972
    assert facts.demolished_year is None  # deprecated statements are ignored
    assert facts.country == ["People's Republic of China"]
    assert facts.heritage_designations == [{"label": "Grade I historic building", "year": 2009}]
    assert facts.commons_category == "Sunbeam Theatre"
    assert facts.sitelinks == {"en": "Sunbeam Theatre", "zh-yue": "新光戲院"}
    facts.set_native_label(["zh-hant", "en"])
    assert facts.native_label == "新光戲院"


def test_wikidata_helpers():
    assert wikidata.parse_year({"time": "-0070-00-00T00:00:00Z"}) == -70
    assert wikidata.parse_wikipedia_url("https://en.m.wikipedia.org/wiki/Sunbeam_Theatre") == ("en", "Sunbeam Theatre")
    assert wikidata.parse_wikipedia_url("https://example.com/wiki/X") is None
    candidates = [{"qid": "Q1", "label": "Sunbeam"}, {"qid": "Q2", "label": "Sunbeam Theatre"}]
    assert wikidata.pick_qid_from_search(candidates, "Sunbeam Theatre") == "Q2"
    assert wikidata.pick_qid_from_search([{"qid": "Q3", "label": "Theatre"}], "Opera House") is None


def test_photo_year_parsing():
    assert archives.parse_photo_year("1965-03-01 10:00")[0] == 1965
    assert archives.parse_photo_year("circa 1930s")[0] == 1930
    assert archives.parse_photo_year("<span>unknown</span>")[0] is None
    assert archives.parse_photo_year("2999")[0] is None


def test_sketchfab_similarity():
    assert sketchfab.title_similarity("Sunbeam Theatre", "Sunbeam Theatre Interior") == 1.0
    assert sketchfab.title_similarity("Sunbeam Theatre", "Random chair") == 0.0


def test_google_news_parsing():
    class Response:
        content = b"""<?xml version="1.0"?><rss><channel>
          <item><title>Theatre closes - Example Post</title><link>https://news.example/1</link>
          <pubDate>Mon, 03 Mar 2025 08:00:00 GMT</pubDate><source url="https://example">Example Post</source></item>
        </channel></rss>"""

        def raise_for_status(self):
            pass

    class Client:
        def get(self, url):
            return Response()

    items = news.google_news(Client(), '"Sunbeam Theatre"')
    assert items == [{"title": "Theatre closes", "url": "https://news.example/1", "source_name": "Example Post",
                      "published_at": "2025-03-03"}]


def test_annotate_with_refs_inserts_markers_after_segments():
    text = "It opened in 1972. It closed in 2025."
    supports = [{"text": "It opened in 1972.", "chunks": [0]}, {"text": "It closed in 2025.", "chunks": [1, 0]},
                {"text": "Not in text", "chunks": [0]}]
    annotated = annotate_with_refs(text, supports, {0: 4, 1: 5})
    assert annotated == "It opened in 1972. [S4] It closed in 2025. [S4][S5]"
