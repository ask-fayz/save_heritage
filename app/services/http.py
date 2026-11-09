"""HTTP helpers: a shared client for well-known open-data APIs and a guarded fetcher for user-submitted URLs."""

from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from app.config import Settings
from app.security import UnsafeURLError, validate_public_url

MAX_PAGE_BYTES = 5 * 1024 * 1024


def api_client(settings: Settings, timeout: float = 20.0) -> httpx.Client:
    """Client for fixed public APIs (Wikidata, Commons, Sketchfab, news feeds)."""
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": settings.http_user_agent, "Accept-Encoding": "gzip"},
    )


@dataclass
class FetchedPage:
    url: str
    content_type: str
    text: str


def fetch_user_url(url: str, settings: Settings, *, max_redirects: int = 5) -> FetchedPage:
    """Fetch a user-submitted page. Every redirect hop is re-validated and the body size is capped."""
    current = validate_public_url(url, allow_private=settings.allow_private_urls)
    with httpx.Client(timeout=20.0, follow_redirects=False,
                      headers={"User-Agent": settings.http_user_agent, "Accept": "text/html,*/*;q=0.5"}) as client:
        for _ in range(max_redirects + 1):
            with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location", "")
                    current = validate_public_url(urljoin(current, location), allow_private=settings.allow_private_urls)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if not any(t in content_type for t in ("text/html", "application/xhtml", "text/plain")):
                    raise UnsafeURLError("The link does not point to a web page.")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_PAGE_BYTES:
                        raise UnsafeURLError("The page is too large to process.")
                encoding = response.encoding or "utf-8"
                return FetchedPage(url=current, content_type=content_type,
                                   text=bytes(body).decode(encoding, errors="replace"))
    raise UnsafeURLError("Too many redirects.")
