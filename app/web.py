"""Template rendering and request-scoped helpers shared by all routers."""

from collections.abc import Iterator
from hashlib import sha256
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.config import Settings
from app.i18n import LANGUAGES, language, translate
from app.db import session
from app.models import EVENT_KINDS, RISK_REASONS, RISK_STATUSES, SUPPORTED_LANGUAGES
from app.security import csrf_token_for

TEMPLATES_DIR = Path(__file__).parent / "templates"
# Change asset URLs whenever shipped CSS or JavaScript changes.
_STATIC_DIR = Path(__file__).parent / "static"
_asset_hash = sha256()
for _asset in sorted(_STATIC_DIR.rglob("*")):
    if _asset.is_file() and _asset.suffix in {".css", ".js"}:
        _asset_hash.update(_asset.relative_to(_STATIC_DIR).as_posix().encode())
        _asset_hash.update(_asset.read_bytes())
STATIC_VERSION = _asset_hash.hexdigest()[:16]


def _context(request: Request) -> dict:
    settings: Settings = request.app.state.settings
    lang = language(request.query_params.get("lang", request.cookies.get("heritage_lang", "en")))
    return {
        "lang": lang,
        "languages": LANGUAGES,
        "t": lambda key: translate(key, lang),
        "language_urls": {code: str(request.url.replace_query_params(lang=code)) for code in LANGUAGES},
        "csrf_token": csrf_token_for(request),
        "ai_enabled": settings.ai_enabled,
        "maps_enabled": bool(settings.google_maps_api_key),
        "maps_browser_key": settings.google_maps_api_key,
        "static_version": STATIC_VERSION,
    }


templates = Jinja2Templates(directory=TEMPLATES_DIR, context_processors=[_context])
templates.env.globals.update(
    RISK_STATUSES=RISK_STATUSES,
    RISK_REASONS=RISK_REASONS,
    EVENT_KINDS=EVENT_KINDS,
    SUPPORTED_LANGUAGES=SUPPORTED_LANGUAGES,
)


def render(request: Request, name: str, context: dict | None = None, status_code: int = 200):
    context = dict(context or {})
    if "lang" in context:
        lang = language(context["lang"])
        context.update(lang=lang, t=lambda key: translate(key, lang))
    return templates.TemplateResponse(request, name, context, status_code=status_code)


def get_db(request: Request) -> Iterator:
    with session(request.app.state.settings.db_path) as conn:
        yield conn


def year_or_none(value: str | int | None, *, low: int = -3000, high: int = 2100) -> int | None:
    try:
        year = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return year if low <= year <= high else None
