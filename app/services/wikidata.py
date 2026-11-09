"""Wikidata and Wikipedia: the structured backbone (coordinates, dates, protection status) and multilingual texts."""

import re
from dataclasses import dataclass, field
from urllib.parse import quote, unquote, urlparse

import httpx

WIKIDATA_API = "https://www.wikidata.org/w/api.php"

# Properties we read. Labels are resolved in one batch request.
P_INSTANCE_OF = "P31"
P_COUNTRY = "P17"
P_LOCATED_IN = "P131"
P_COORDINATES = "P625"
P_INCEPTION = "P571"
P_OPENING = "P1619"
P_DEMOLISHED = "P576"  # "dissolved, abolished or demolished date"
P_HERITAGE = "P1435"
P_ARCHITECT = "P84"
P_STYLE = "P149"
P_COMMONS_CATEGORY = "P373"
P_IMAGE = "P18"
P_WEBSITE = "P856"
P_ADDRESS = "P6375"
P_CONSERVATION = "P5816"
P_START_TIME = "P580"
P_OFFICIAL_LANGUAGE = "P37"
P_WIKIMEDIA_LANG_CODE = "P424"

NON_WIKIPEDIA_SITES = {"commonswiki", "specieswiki", "metawiki", "wikidatawiki", "mediawikiwiki", "sourceswiki",
                       "outreachwiki", "wikimaniawiki", "incubatorwiki", "foundationwiki", "wikifunctionswiki"}


@dataclass
class WikidataFacts:
    qid: str
    label: str = ""
    native_label: str = ""
    description: str = ""
    latitude: float | None = None
    longitude: float | None = None
    inception_year: int | None = None
    opening_year: int | None = None
    demolished_year: int | None = None
    instance_of: list[str] = field(default_factory=list)
    country: list[str] = field(default_factory=list)
    country_qids: list[str] = field(default_factory=list)
    located_in: list[str] = field(default_factory=list)
    heritage_designations: list[dict] = field(default_factory=list)  # {"label", "year"}
    architects: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    conservation_state: list[str] = field(default_factory=list)
    address: str = ""
    website: str = ""
    commons_category: str = ""
    image: str = ""
    sitelinks: dict[str, str] = field(default_factory=dict)  # wiki language code -> article title
    all_labels: dict[str, str] = field(default_factory=dict)  # language code -> label
    all_descriptions: dict[str, str] = field(default_factory=dict)  # language code -> description

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if k not in ("sitelinks", "all_labels", "all_descriptions")}

    def label_for(self, lang: str = "en") -> str:
        """Return label in preferred language, falling back to English or any available label."""
        if lang == "zh":
            for code in ("zh", "zh-hans", "zh-cn", "zh-hant", "zh-hk", "zh-tw"):
                if self.all_labels.get(code):
                    return self.all_labels[code]
        return self.all_labels.get(lang) or self.label

    def description_for(self, lang: str = "en") -> str:
        if lang == "zh":
            for code in ("zh", "zh-hans", "zh-cn", "zh-hant", "zh-hk"):
                if self.all_descriptions.get(code):
                    return self.all_descriptions[code]
        return self.all_descriptions.get(lang) or self.description

    def set_native_label(self, language_codes: list[str]) -> None:
        """Pick the label in the first local language that differs from the primary name."""
        for code in language_codes:
            label = self.all_labels.get(code) or self.all_labels.get(code.split("-")[0], "")
            if label and label != self.label:
                self.native_label = label
                return


def parse_wikipedia_url(url: str) -> tuple[str, str] | None:
    """Return (language, article title) for a Wikipedia article URL."""
    parsed = urlparse(url)
    match = re.fullmatch(r"([a-z0-9\-]+)(?:\.m)?\.wikipedia\.org", parsed.hostname or "")
    if not match or not parsed.path.startswith("/wiki/"):
        return None
    title = unquote(parsed.path[len("/wiki/"):]).replace("_", " ")
    return (match.group(1), title) if title else None


def qid_for_wikipedia_article(client: httpx.Client, lang: str, title: str) -> str | None:
    response = client.get(f"https://{lang}.wikipedia.org/w/api.php", params={
        "action": "query", "prop": "pageprops", "titles": title, "redirects": 1, "format": "json",
    })
    response.raise_for_status()
    for page in response.json().get("query", {}).get("pages", {}).values():
        qid = page.get("pageprops", {}).get("wikibase_item")
        if qid:
            return qid
    return None


def search_items(client: httpx.Client, query: str, lang: str = "en", limit: int = 5) -> list[dict]:
    response = client.get(WIKIDATA_API, params={
        "action": "wbsearchentities", "search": query, "language": lang, "uselang": lang, "type": "item",
        "limit": limit, "format": "json",
    })
    response.raise_for_status()
    return [{"qid": r["id"], "label": r.get("label", ""), "description": r.get("description", "")}
            for r in response.json().get("search", [])]


def detect_query_language(text: str, default: str = "en") -> str:
    """Infer search language ('ru', 'zh', 'en') from script characters in a user query."""
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[\u0400-\u04ff]", text):
        return "ru"
    return default if default in ("en", "ru", "zh") else "en"


def search_places(client: httpx.Client, query: str, lang: str = "en") -> list[dict]:
    """Search Wikidata for places that have a Wikipedia article, returning URL-encoded Wikipedia links."""
    search_lang = detect_query_language(query, default=lang)
    items = search_items(client, query, search_lang, 8)
    if not items:
        return []
    entities = get_entities(
        client,
        [i["qid"] for i in items],
        props="labels|descriptions|sitelinks",
        languages=f"{lang}|{search_lang}|en|ru|zh",
    )
    results = []
    for item in items:
        qid = item["qid"]
        entity = entities.get(qid, {})
        sitelinks = entity.get("sitelinks", {})
        chosen_lang = None
        chosen_title = None
        for code in (search_lang, lang, "en", "ru", "zh"):
            key = f"{code.replace('-', '_')}wiki"
            if key in sitelinks and sitelinks[key].get("title"):
                chosen_lang = code
                chosen_title = sitelinks[key]["title"]
                break
        if not chosen_title:
            for key, link in sitelinks.items():
                slang = sitelink_language(key)
                if slang and link.get("title"):
                    chosen_lang = slang
                    chosen_title = link["title"]
                    break
        if not chosen_lang or not chosen_title:
            continue
        labels = entity.get("labels", {})
        descriptions = entity.get("descriptions", {})
        label = (
            labels.get(lang, {}).get("value")
            or labels.get(search_lang, {}).get("value")
            or item.get("label")
            or chosen_title
        )
        description = (
            descriptions.get(lang, {}).get("value")
            or descriptions.get(search_lang, {}).get("value")
            or item.get("description")
            or ""
        )
        encoded_title = quote(chosen_title.replace(" ", "_"), safe="")
        results.append({
            "qid": qid,
            "label": label,
            "description": description,
            "url": f"https://{chosen_lang}.wikipedia.org/wiki/{encoded_title}",
        })
    return results


def get_entities(client: httpx.Client, qids: list[str], props: str = "labels|descriptions|claims|sitelinks",
                 languages: str | None = "en") -> dict:
    entities: dict = {}
    for start in range(0, len(qids), 50):
        batch = qids[start:start + 50]
        params = {"action": "wbgetentities", "ids": "|".join(batch), "props": props, "format": "json"}
        if languages:
            params["languages"] = languages
        response = client.get(WIKIDATA_API, params=params)
        response.raise_for_status()
        entities.update(response.json().get("entities", {}))
    return entities


def _claims(entity: dict, prop: str) -> list[dict]:
    return [c for c in entity.get("claims", {}).get(prop, []) if c.get("rank") != "deprecated"]


def _value(claim: dict):
    return claim.get("mainsnak", {}).get("datavalue", {}).get("value")


def parse_year(time_value: dict | None) -> int | None:
    """Wikidata time '+1972-00-00T00:00:00Z' -> 1972; precision coarser than a year (decade etc.) still yields a year."""
    if not time_value or "time" not in time_value:
        return None
    match = re.match(r"^([+-])0*(\d+)-", time_value["time"])
    if not match:
        return None
    year = int(match.group(2))
    return -year if match.group(1) == "-" else year


def _item_ids(entity: dict, prop: str) -> list[str]:
    ids = []
    for claim in _claims(entity, prop):
        value = _value(claim)
        if isinstance(value, dict) and value.get("id"):
            ids.append(value["id"])
    return ids


def _label(entity: dict, lang: str = "en") -> str:
    labels = entity.get("labels", {})
    if lang in labels:
        return labels[lang]["value"]
    return next(iter(labels.values()), {}).get("value", "")


def sitelink_language(site_key: str) -> str | None:
    """'zh_yuewiki' -> 'zh-yue'; returns None for non-Wikipedia projects."""
    if site_key in NON_WIKIPEDIA_SITES or not re.fullmatch(r"[a-z_]+wiki", site_key):
        return None
    return site_key[:-4].replace("_", "-")


def parse_entity(entity: dict, labels: dict[str, str]) -> WikidataFacts:
    facts = WikidataFacts(qid=entity["id"], label=_label(entity),
                          description=entity.get("descriptions", {}).get("en", {}).get("value", ""))
    facts.all_labels = {code: item["value"] for code, item in entity.get("labels", {}).items()}
    facts.all_descriptions = {code: item["value"] for code, item in entity.get("descriptions", {}).items()}

    for claim in _claims(entity, P_COORDINATES)[:1]:
        value = _value(claim)
        if isinstance(value, dict):
            facts.latitude, facts.longitude = value.get("latitude"), value.get("longitude")

    for prop, attr in ((P_INCEPTION, "inception_year"), (P_OPENING, "opening_year"), (P_DEMOLISHED, "demolished_year")):
        for claim in _claims(entity, prop)[:1]:
            setattr(facts, attr, parse_year(_value(claim)))

    def names(prop: str) -> list[str]:
        return [labels.get(qid, qid) for qid in _item_ids(entity, prop)]

    facts.instance_of = names(P_INSTANCE_OF)
    facts.country_qids = _item_ids(entity, P_COUNTRY)
    facts.country = names(P_COUNTRY)
    facts.located_in = names(P_LOCATED_IN)
    facts.architects = names(P_ARCHITECT)
    facts.styles = names(P_STYLE)
    facts.conservation_state = names(P_CONSERVATION)

    for claim in _claims(entity, P_HERITAGE):
        value = _value(claim)
        if not isinstance(value, dict):
            continue
        start = claim.get("qualifiers", {}).get(P_START_TIME, [{}])[0].get("datavalue", {}).get("value")
        facts.heritage_designations.append({"label": labels.get(value["id"], value["id"]), "year": parse_year(start)})

    for claim in _claims(entity, P_ADDRESS)[:1]:
        value = _value(claim)
        facts.address = value.get("text", "") if isinstance(value, dict) else ""
    for claim in _claims(entity, P_WEBSITE)[:1]:
        facts.website = _value(claim) or ""
    for claim in _claims(entity, P_COMMONS_CATEGORY)[:1]:
        facts.commons_category = _value(claim) or ""
    for claim in _claims(entity, P_IMAGE)[:1]:
        facts.image = _value(claim) or ""

    for key, link in entity.get("sitelinks", {}).items():
        lang = sitelink_language(key)
        if lang:
            facts.sitelinks[lang] = link["title"]
    return facts


def referenced_item_ids(entity: dict) -> list[str]:
    ids: set[str] = set()
    for prop in (P_INSTANCE_OF, P_COUNTRY, P_LOCATED_IN, P_ARCHITECT, P_STYLE, P_CONSERVATION, P_HERITAGE):
        ids.update(_item_ids(entity, prop))
    return sorted(ids)


def fetch_facts(client: httpx.Client, qid: str) -> WikidataFacts:
    entity = get_entities(client, [qid], languages=None)[qid]
    ref_ids = referenced_item_ids(entity)
    labels = {}
    if ref_ids:
        labels = {k: _label(v) for k, v in get_entities(client, ref_ids, props="labels").items()}
    return parse_entity(entity, labels)


def local_wiki_languages(client: httpx.Client, country_qids: list[str]) -> list[str]:
    """Wikipedia language codes of the countries' official languages (country -> P37 -> P424)."""
    if not country_qids:
        return []
    countries = get_entities(client, country_qids, props="claims")
    language_ids = sorted({lid for c in countries.values() for lid in _item_ids(c, P_OFFICIAL_LANGUAGE)})
    if not language_ids:
        return []
    languages = get_entities(client, language_ids, props="claims")
    codes = []
    for language in languages.values():
        for claim in _claims(language, P_WIKIMEDIA_LANG_CODE)[:1]:
            code = _value(claim)
            if isinstance(code, str) and code not in codes:
                codes.append(code)
    return codes


def wikipedia_plaintext(client: httpx.Client, lang: str, title: str, max_chars: int = 12000) -> str:
    response = client.get(f"https://{lang}.wikipedia.org/w/api.php", params={
        "action": "query", "prop": "extracts", "explaintext": 1, "exsectionformat": "plain",
        "titles": title, "redirects": 1, "format": "json",
    })
    response.raise_for_status()
    for page in response.json().get("query", {}).get("pages", {}).values():
        text = page.get("extract", "")
        if text:
            return text[:max_chars]
    return ""


def pick_qid_from_search(candidates: list[dict], page_title: str, *, allow_top_hit: bool = False) -> str | None:
    """Only accept a search hit whose label matches the page title closely; a wrong item is worse than none.
    When `allow_top_hit=True` (direct place name search by user), fall back to the top Wikidata hit if available."""
    def norm(text: str) -> str:
        return re.sub(r"\W+", " ", text.lower()).strip()

    wanted = norm(page_title)
    labels = [(norm(c["label"]), c["qid"]) for c in candidates if c.get("qid")]
    for label, qid in labels:
        if label and label == wanted:
            return qid
    for label, qid in labels:
        if len(label) > 5 and wanted.startswith(label + " "):
            return qid
    for label, qid in labels:
        if wanted and len(wanted) >= 3 and (wanted in label or label in wanted):
            return qid
    if allow_top_hit and labels:
        return labels[0][1]
    return None
