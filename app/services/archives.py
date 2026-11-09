"""Open photo archives for the "Through time" layer: Wikimedia Commons and (optionally) Europeana."""

import html
import re
from datetime import date

import httpx

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
EUROPEANA_API = "https://api.europeana.eu/record/v2/search.json"
ALLOWED_MIMES = {"image/jpeg", "image/png", "image/tiff", "image/webp"}


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def parse_photo_year(text: str) -> tuple[int | None, str]:
    """Pull a plausible year out of free-form archive dates: '1965-03-01', 'circa 1930s', '12 May 1901'."""
    clean = strip_html(text)
    match = re.search(r"\b(1[6-9]\d{2}|20\d{2})s?\b", clean)
    if not match:
        return None, clean[:60]
    year = int(match.group(1))
    if year > date.today().year:
        return None, clean[:60]
    return year, clean[:60]


def _commons_thumb(url: str, width: int) -> str:
    """Commons serves thumbnails at standard widths (250, 330, 500, 960, 1280, 1920)."""
    url = url.split("?", 1)[0]
    return re.sub(r"/\d+px-", f"/{width}px-", url) if "/thumb/" in url else url


def _commons_imageinfo(client: httpx.Client, titles: list[str]) -> list[dict]:
    photos = []
    for start in range(0, len(titles), 40):
        response = client.get(COMMONS_API, params={
            "action": "query", "titles": "|".join(titles[start:start + 40]), "prop": "imageinfo",
            "iiprop": "url|extmetadata|size|mime", "iiurlwidth": 1920, "format": "json",
        })
        response.raise_for_status()
        for page in response.json().get("query", {}).get("pages", {}).values():
            info = (page.get("imageinfo") or [None])[0]
            if not info or info.get("mime") not in ALLOWED_MIMES:
                continue
            meta = {k: v.get("value", "") for k, v in info.get("extmetadata", {}).items()}
            year, date_text = parse_photo_year(meta.get("DateTimeOriginal", ""))
            image_url = (info.get("thumburl") or info.get("url", "")).split("?", 1)[0]
            title = re.sub(r"\.(jpe?g|png|tiff?|webp)$", "", page["title"].removeprefix("File:"), flags=re.I)
            lat, lon = meta.get("GPSLatitude"), meta.get("GPSLongitude")
            photos.append({
                "provider": "commons",
                "provider_id": page["title"],
                "title": title.replace("_", " "),
                "description": strip_html(meta.get("ImageDescription", ""))[:500],
                "author": strip_html(meta.get("Artist", ""))[:200],
                "license": meta.get("LicenseShortName", ""),
                "license_url": meta.get("LicenseUrl", ""),
                "source_page_url": info.get("descriptionurl", ""),
                "image_url": image_url,
                "thumb_url": _commons_thumb(image_url, 500),
                "width": info.get("thumbwidth") or info.get("width"),
                "height": info.get("thumbheight") or info.get("height"),
                "year": year,
                "date_text": date_text,
                "year_source": "metadata" if year else "",
                "latitude": float(lat) if _is_float(lat) else None,
                "longitude": float(lon) if _is_float(lon) else None,
            })
    return photos


def _is_float(value) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def commons_category_photos(client: httpx.Client, category: str, limit: int = 60) -> list[dict]:
    response = client.get(COMMONS_API, params={
        "action": "query", "list": "categorymembers", "cmtitle": f"Category:{category}", "cmtype": "file",
        "cmlimit": limit, "format": "json",
    })
    response.raise_for_status()
    titles = [m["title"] for m in response.json().get("query", {}).get("categorymembers", [])]
    return _commons_imageinfo(client, titles) if titles else []


def commons_nearby_photos(client: httpx.Client, lat: float, lon: float, radius_m: int = 150, limit: int = 40) -> list[dict]:
    response = client.get(COMMONS_API, params={
        "action": "query", "list": "geosearch", "gscoord": f"{lat}|{lon}", "gsradius": radius_m,
        "gsnamespace": 6, "gslimit": limit, "format": "json",
    })
    response.raise_for_status()
    titles = [m["title"] for m in response.json().get("query", {}).get("geosearch", [])]
    return _commons_imageinfo(client, titles) if titles else []


def europeana_photos(client: httpx.Client, api_key: str, query: str, limit: int = 30) -> list[dict]:
    response = client.get(EUROPEANA_API, params={
        "wskey": api_key, "query": f'"{query}"', "qf": "TYPE:IMAGE", "reusability": "open", "media": "true",
        "thumbnail": "true", "rows": limit, "profile": "rich",
    })
    response.raise_for_status()
    photos = []
    for item in response.json().get("items", []):
        preview = (item.get("edmPreview") or [""])[0]
        full = (item.get("edmIsShownBy") or [preview])[0]
        if not preview:
            continue
        year_values = item.get("year") or []
        year, date_text = parse_photo_year(year_values[0]) if year_values else (None, "")
        rights = (item.get("rights") or [""])[0]
        photos.append({
            "provider": "europeana",
            "provider_id": item.get("id", ""),
            "title": strip_html((item.get("title") or [""])[0])[:200],
            "description": strip_html((item.get("dcDescription") or [""])[0])[:500],
            "author": strip_html((item.get("dcCreator") or item.get("dataProvider") or [""])[0])[:200],
            "license": _rights_label(rights),
            "license_url": rights,
            "source_page_url": item.get("guid", ""),
            "image_url": full,
            "thumb_url": preview,
            "year": year,
            "date_text": date_text,
            "year_source": "metadata" if year else "",
            "latitude": _first_float(item.get("edmPlaceLatitude")),
            "longitude": _first_float(item.get("edmPlaceLongitude")),
        })
    return photos


def _first_float(values) -> float | None:
    if values and _is_float(values[0]):
        return float(values[0])
    return None


def _rights_label(url: str) -> str:
    if "publicdomain/mark" in url:
        return "Public Domain"
    if "publicdomain/zero" in url:
        return "CC0"
    match = re.search(r"licenses/([a-z\-]+)/", url)
    return f"CC {match.group(1).upper()}" if match else "See source"
