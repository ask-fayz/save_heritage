"""News monitoring feeds for the "Heritage at risk" layer."""

import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import httpx


def google_news(client: httpx.Client, query: str, limit: int = 40) -> list[dict]:
    """Google News RSS search. Google allows this feed for personal, non-commercial use only; see README."""
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    response = client.get(url)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    items = []
    for node in root.iter("item"):
        title = node.findtext("title", "").strip()
        link = node.findtext("link", "").strip()
        if not title or not link:
            continue
        source = node.find("source")
        source_name = source.text.strip() if source is not None and source.text else ""
        if source_name and title.endswith(f" - {source_name}"):
            title = title[: -len(f" - {source_name}")]
        items.append({
            "title": title,
            "url": link,
            "source_name": source_name,
            "published_at": _iso_date(node.findtext("pubDate", "")),
        })
    return sorted(items, key=lambda i: i["published_at"], reverse=True)[:limit]


def gdelt(client: httpx.Client, query: str, limit: int = 40) -> list[dict]:
    """GDELT DOC API. Free, no key, but limited to roughly one request every five seconds."""
    response = client.get("https://api.gdeltproject.org/api/v2/doc/doc", params={
        "query": query, "mode": "artlist", "format": "json", "maxrecords": limit, "sort": "datedesc",
    })
    response.raise_for_status()
    try:
        articles = response.json().get("articles", [])
    except ValueError:  # GDELT answers rate-limit errors with plain text
        return []
    return [{
        "title": a.get("title", ""),
        "url": a.get("url", ""),
        "source_name": a.get("domain", ""),
        "published_at": _gdelt_date(a.get("seendate", "")),
    } for a in articles if a.get("url")]


def fetch_news(client: httpx.Client, provider: str, query: str) -> list[dict]:
    if provider == "google_news":
        return google_news(client, query)
    if provider == "gdelt":
        return gdelt(client, query)
    return []


def _iso_date(rfc822: str) -> str:
    try:
        return parsedate_to_datetime(rfc822).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def _gdelt_date(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}" if len(value) >= 8 else ""
