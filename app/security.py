"""Input validation and abuse protection: URLs, colours, slugs, uploads, rate limits, CSRF and curator auth."""

import ipaddress
import re
import secrets
import socket
import threading
import time
import unicodedata
from collections import defaultdict, deque
from urllib.parse import parse_qs, urlparse

from fastapi import Depends, Form, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import Settings
from app.models import Theme


class UnsafeURLError(ValueError):
    pass


# ---------------------------------------------------------------- URLs

def validate_public_url(url: str, *, allow_private: bool = False) -> str:
    """Reject anything except http(s) URLs that resolve to public internet addresses (SSRF protection)."""
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeURLError("Only http and https links are supported.")
    if not parsed.hostname:
        raise UnsafeURLError("The link has no host name.")
    if parsed.username or parsed.password:
        raise UnsafeURLError("Links with embedded credentials are not allowed.")
    if allow_private:
        return url
    host_lower = parsed.hostname.lower().strip("[]")
    if host_lower in ("localhost", "localhost.localdomain") or host_lower.endswith(".local"):
        raise UnsafeURLError("Links to private or local network addresses are not allowed.")
    try:
        literal_ip = ipaddress.ip_address(host_lower)
    except ValueError:
        literal_ip = None
    if literal_ip is not None:
        if not literal_ip.is_global or literal_ip.is_multicast:
            raise UnsafeURLError("Links to private or local network addresses are not allowed.")
        return url
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        if re.fullmatch(r"(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}", parsed.hostname):
            return url
        raise UnsafeURLError("The host name could not be resolved.") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global or address.is_multicast:
            raise UnsafeURLError("Links to private or local network addresses are not allowed.")
    return url


def is_http_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


def embed_for_url(url: str) -> tuple[str, str]:
    """Return (embed_url, provider) for known players, or ("", "") if the link can only be shown as a link.

    The embed URL is always rebuilt from a validated ID, never copied from user input.
    """
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    path = parsed.path

    if host in ("youtube.com", "music.youtube.com", "youtube-nocookie.com"):
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        match = re.match(r"^/(?:shorts|embed|live)/([\w-]{6,20})", path)
        if match:
            video_id = match.group(1)
        if re.fullmatch(r"[\w-]{6,20}", video_id or ""):
            return f"https://www.youtube-nocookie.com/embed/{video_id}", "youtube"
    if host == "youtu.be":
        match = re.match(r"^/([\w-]{6,20})", path)
        if match:
            return f"https://www.youtube-nocookie.com/embed/{match.group(1)}", "youtube"
    if host == "vimeo.com":
        match = re.match(r"^/(\d{4,12})", path)
        if match:
            return f"https://player.vimeo.com/video/{match.group(1)}", "vimeo"
    if host == "archive.org":
        match = re.match(r"^/(?:details|embed)/([\w.\-]{2,120})", path)
        if match:
            return f"https://archive.org/embed/{match.group(1)}", "archive.org"
    if host == "bilibili.com":
        match = re.search(r"/video/(BV[0-9A-Za-z]{10})", path)
        if match:
            return f"https://player.bilibili.com/player.html?bvid={match.group(1)}&autoplay=0", "bilibili"
    if host == "sketchfab.com":
        match = re.search(r"(?:/models/|/3d-models/(?:[\w-]*-)?)([0-9a-f]{32})", path)
        if match:
            return f"https://sketchfab.com/models/{match.group(1)}/embed", "sketchfab"
    return "", ""


# ---------------------------------------------------------------- slugs

def slugify(text: str, max_length: int = 60) -> str:
    """Readable URL slug. Keeps Unicode letters (e.g. Cyrillic, Chinese) but drops separators like / ? #."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = re.sub(r"['’`]", "", text)
    text = re.sub(r"[^\w]+", "-", text, flags=re.UNICODE).strip("-_")
    text = re.sub(r"[-_]{2,}", "-", text)
    return (text[:max_length].strip("-") or "site")


# ---------------------------------------------------------------- colours

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def sanitize_theme(raw: dict | None) -> dict:
    """Accept only #RRGGBB colours (they are written into CSS) and keep body text readable."""
    default = Theme()
    raw = raw or {}
    values = {}
    for field in Theme.model_fields:
        value = str(raw.get(field, "")).strip()
        values[field] = value if HEX_COLOR.match(value) else getattr(default, field)
    theme = Theme(**values)
    if contrast_ratio(theme.text_cream, theme.bg) < 4.5 or contrast_ratio(theme.text_cream, theme.card_bg) < 4.5:
        theme.text_cream = default.text_cream
        theme.bg, theme.bg_darker, theme.card_bg, theme.border_color = (
            default.bg, default.bg_darker, default.card_bg, default.border_color,
        )
    return theme.model_dump()


# ---------------------------------------------------------------- uploads

IMAGE_SIGNATURES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
}
AUDIO_EXTENSIONS = {".webm": "audio/webm", ".ogg": "audio/ogg", ".oga": "audio/ogg", ".mp3": "audio/mpeg",
                    ".m4a": "audio/mp4", ".mp4": "audio/mp4", ".wav": "audio/wav", ".aac": "audio/aac",
                    ".flac": "audio/flac"}
SCAN_EXTENSIONS = {".ply", ".spz", ".splat", ".ksplat", ".sog"}


def sniff_image(head: bytes) -> tuple[str, str] | None:
    """Return (mime, extension) for JPEG/PNG/WebP, else None."""
    if head.startswith(IMAGE_SIGNATURES["image/jpeg"]):
        return "image/jpeg", ".jpg"
    if head.startswith(IMAGE_SIGNATURES["image/png"]):
        return "image/png", ".png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def sniff_audio(head: bytes, filename: str) -> tuple[str, str] | None:
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm", ".webm"
    if head.startswith(b"OggS"):
        return "audio/ogg", ".ogg"
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return "audio/mpeg", ".mp3"
    if head[4:8] == b"ftyp":
        return "audio/mp4", ".m4a"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav", ".wav"
    if head.startswith(b"fLaC"):
        return "audio/flac", ".flac"
    if ext == ".aac" and len(head) > 1 and head[0] == 0xFF and (head[1] & 0xF6) == 0xF0:
        return "audio/aac", ".aac"
    return None


def sniff_scan(head: bytes, filename: str) -> str | None:
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in SCAN_EXTENSIONS:
        return None
    if ext == ".ply" and not head.startswith(b"ply"):
        return None
    if ext == ".sog" and not head.startswith(b"PK"):
        return None
    return ext


# ---------------------------------------------------------------- rate limiting

class RateLimiter:
    """In-memory sliding window limiter. Good enough for a single-process deployment."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int = 3600) -> None:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests. Please try again later.")
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = RateLimiter()


def client_ip(request: Request, settings: Settings) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------- CSRF (double-submit cookie)

CSRF_COOKIE = "save_csrf"


def csrf_token_for(request: Request) -> str:
    token = getattr(request.state, "csrf_token", None)
    if not token:
        token = request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)
        request.state.csrf_token = token
    return token


def verify_csrf(request: Request, csrf_token: str = Form("")) -> None:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not cookie or not csrf_token or not secrets.compare_digest(cookie, csrf_token):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "The form expired. Reload the page and try again.")


# ---------------------------------------------------------------- curator auth

basic_auth = HTTPBasic(auto_error=False, realm="SAVE Heritage curators")


def credentials_valid(credentials: HTTPBasicCredentials | None, settings: Settings) -> bool:
    if not settings.admin_enabled or credentials is None:
        return False
    user_ok = secrets.compare_digest(credentials.username.encode(), settings.admin_username.encode())
    pass_ok = secrets.compare_digest(credentials.password.encode(), settings.admin_password.encode())
    return user_ok and pass_ok


def require_admin(request: Request, credentials: HTTPBasicCredentials | None = Depends(basic_auth)) -> str:
    settings: Settings = request.app.state.settings
    if not settings.admin_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Curator area is disabled: set ADMIN_PASSWORD.")
    if not credentials_valid(credentials, settings):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Curator login required.",
            headers={"WWW-Authenticate": 'Basic realm="SAVE Heritage curators"'},
        )
    return credentials.username  # type: ignore[union-attr]
