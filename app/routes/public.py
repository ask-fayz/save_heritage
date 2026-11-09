"""Public pages: landing, archive, global map, stories, site pages, AI Keeper, Preservation Passport, and generation jobs."""

import re

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.security import HTTPBasicCredentials

from app import repo
from app.i18n import language, translate
from app.models import RISK_REASONS, RISK_STATUSES, SUPPORTED_LANGUAGES
from app.security import (
    UnsafeURLError,
    basic_auth,
    client_ip,
    credentials_valid,
    rate_limiter,
    validate_public_url,
    verify_csrf,
)
from app.services import pipeline, stories, wikidata, editions
from app.services.http import api_client
from app.services.storage import resolve_upload
from app.web import get_db, render

router = APIRouter()

URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def _req_lang(request: Request, form_lang: str = "") -> str:
    return language(form_lang or request.query_params.get("lang") or request.cookies.get("heritage_lang", "en"))


def _map_sites_payload(sites: list[dict]) -> list[dict]:
    """Compact list of geo-located sites for the interactive heritage map."""
    out = []
    for s in sites:
        if s.get("latitude") is None or s.get("longitude") is None:
            continue
        status = s.get("risk_status", "unknown")
        out.append({
            "slug": s["slug"],
            "title": s["title"],
            "native_name": s.get("native_name") or "",
            "location_label": s.get("location_label") or "",
            "tagline": s.get("tagline") or "",
            "latitude": s["latitude"],
            "longitude": s["longitude"],
            "risk_status": status,
            "risk_label": RISK_STATUSES.get(status, RISK_STATUSES["unknown"])["label"],
            "language": (s.get("language") or "en").upper(),
        })
    return out


@router.get("/")
def home(request: Request, conn=Depends(get_db)):
    sites = repo.list_sites(conn)
    lang = _req_lang(request)
    sites = [editions.localized(conn, site, repo.list_events(conn, site["id"]), lang)[0] for site in sites]
    return render(request, "index.html", {
        "counts": repo.site_counts(conn),
        "recent": sites[:6],
        "endangered": [s for s in sites if s["risk_status"] in ("watch", "at_risk", "critical")][:3],
        "map_sites": _map_sites_payload(sites),
        "public_generation": request.app.state.settings.public_generation,
        "selected_lang": lang,
        "lang": lang,
    })


@router.post("/generate", dependencies=[Depends(verify_csrf)])
def generate(
    request: Request,
    url: str = Form(""),
    lang: str = Form(""),
    direct: str = Form(""),
    conn=Depends(get_db),
    credentials: HTTPBasicCredentials | None = Depends(basic_auth),
):
    settings = request.app.state.settings
    lang = _req_lang(request, lang)
    is_curator = credentials_valid(credentials, settings)
    if not settings.public_generation and not is_curator:
        raise HTTPException(403, "Adding new sites is limited to curators on this server.")
    if not is_curator:
        rate_limiter.hit(f"generate:{client_ip(request, settings)}", settings.generation_rate_per_hour)

    raw = (url or "").strip()
    is_url_like = bool(URL_SCHEME_RE.match(raw) or raw.startswith(("http:", "https:", "ftp:", "file:")))

    if is_url_like:
        try:
            validated_url = validate_public_url(raw, allow_private=settings.allow_private_urls)
        except UnsafeURLError as exc:
            sites = repo.list_sites(conn)
            return render(request, "index.html", {
                "counts": repo.site_counts(conn),
                "recent": sites[:6],
                "error": str(exc),
                "submitted_url": url,
                "selected_lang": lang,
                "lang": lang,
                "endangered": [s for s in sites if s["risk_status"] in ("watch", "at_risk", "critical")][:3],
                "map_sites": _map_sites_payload(sites),
                "public_generation": settings.public_generation,
            }, status_code=400)
        job_id = request.app.state.jobs.submit(
            "generate",
            lambda ctx: stories.generate_story(ctx, validated_url, lang),
            input_data={"url": validated_url, "lang": lang},
        )
        return RedirectResponse(f"/jobs/{job_id}?lang={lang}", status_code=303)

    # Place name input
    if len(raw) < 2 or len(raw) > 200:
        sites = repo.list_sites(conn)
        return render(request, "index.html", {
            "counts": repo.site_counts(conn),
            "recent": sites[:6],
            "error": translate("invalid_input", lang),
            "submitted_url": url,
            "selected_lang": lang,
            "lang": lang,
            "endangered": [s for s in sites if s["risk_status"] in ("watch", "at_risk", "critical")][:3],
            "map_sites": _map_sites_payload(sites),
            "public_generation": settings.public_generation,
        }, status_code=400)

    if direct == "1":
        job_id = request.app.state.jobs.submit(
            "generate",
            lambda ctx: stories.generate_story(ctx, raw, lang),
            input_data={"url": raw, "lang": lang},
        )
        return RedirectResponse(f"/jobs/{job_id}?lang={lang}", status_code=303)

    try:
        with api_client(settings) as client:
            candidates = wikidata.search_places(client, raw, lang)
    except httpx.HTTPError:
        return render(request, "search.html", {
            "query": raw,
            "candidates": [],
            "search_error": translate("search_error", lang),
            "lang": lang,
        }, status_code=503)

    return render(request, "search.html", {
        "query": raw,
        "candidates": candidates,
        "lang": lang,
    })


@router.get("/site/{slug}/story")
def site_story_page(request: Request, slug: str, conn=Depends(get_db)):
    site = repo.get_site_by_slug(conn, slug)
    if not site or not site["is_published"]:
        raise HTTPException(404, "This site is not in the archive.")
    lang = _req_lang(request)
    deck, fallback, _ = stories.get_story(conn, site, lang)
    return render(request, "story.html", {
        "site": site,
        "deck": deck,
        "fallback": fallback,
        "sources": {s["ref"]: s for s in repo.list_sources(conn, site["id"])},
        "photos": {p["id"]: p for p in repo.list_photos(conn, site["id"])},
        "public_generation": request.app.state.settings.public_generation,
        "lang": lang,
    })


@router.post("/site/{slug}/story", dependencies=[Depends(verify_csrf)])
def prepare_site_story(
    request: Request,
    slug: str,
    lang: str = Form(""),
    conn=Depends(get_db),
    credentials: HTTPBasicCredentials | None = Depends(basic_auth),
):
    site = repo.get_site_by_slug(conn, slug)
    if not site or not site["is_published"]:
        raise HTTPException(404, "This site is not in the archive.")
    settings = request.app.state.settings
    lang = _req_lang(request, lang)
    is_curator = credentials_valid(credentials, settings)
    if not settings.public_generation and not is_curator:
        raise HTTPException(403, translate("disabled", lang))
    if not settings.ai_enabled:
        raise HTTPException(503, translate("basic", lang))
    if not is_curator:
        rate_limiter.hit(f"generate:{client_ip(request, settings)}", settings.generation_rate_per_hour)
    job_id = request.app.state.jobs.submit(
        "story",
        lambda ctx: stories.prepare_stories(ctx, site["id"], lang),
        site_id=site["id"],
        input_data={"site_slug": slug, "lang": lang},
    )
    return RedirectResponse(f"/jobs/{job_id}?lang={lang}", status_code=303)


@router.post("/site/{slug}/translate", dependencies=[Depends(verify_csrf)])
def translate_site(
    request: Request,
    slug: str,
    lang: str = Form("en"),
    conn=Depends(get_db),
    credentials: HTTPBasicCredentials | None = Depends(basic_auth),
):
    site = repo.get_site_by_slug(conn, slug)
    if not site or not site["is_published"]:
        raise HTTPException(404, "This site is not in the archive.")
    settings = request.app.state.settings
    lang = pipeline.normalize_lang(lang)
    is_curator = credentials_valid(credentials, settings)
    if not settings.public_generation and not is_curator:
        raise HTTPException(403, "Regenerating sites is limited to curators on this server.")
    if not is_curator:
        rate_limiter.hit(f"generate:{client_ip(request, settings)}", settings.generation_rate_per_hour)
    if not settings.ai_enabled:
        raise HTTPException(503, translate("basic", lang))
    job_id = request.app.state.jobs.submit(
        "story", lambda ctx: editions.prepare(ctx, site["id"], lang),
        site_id=site["id"], input_data={"lang": lang},
    )
    return RedirectResponse(f"/jobs/{job_id}?lang={lang}", status_code=303)




@router.get("/site/{slug}/passport.json")
def site_passport_json(slug: str, conn=Depends(get_db)):
    site = repo.get_site_by_slug(conn, slug)
    if not site or not site["is_published"]:
        raise HTTPException(404, "This site is not in the archive.")
    site_id = site["id"]
    content = site["content"] or {}
    sources = repo.list_sources(conn, site_id)
    events = repo.list_events(conn, site_id)
    status = site.get("risk_status", "unknown")
    passport = {
        "schema": "save-heritage-passport/v1",
        "slug": site["slug"],
        "title": site["title"],
        "native_name": site.get("native_name") or "",
        "language": site.get("language") or "en",
        "wikidata_qid": site.get("wikidata_qid"),
        "location_label": site.get("location_label") or "",
        "coordinates": (
            {"latitude": site["latitude"], "longitude": site["longitude"], "source": site.get("coord_source")}
            if site.get("latitude") is not None
            else None
        ),
        "tagline": site.get("tagline") or "",
        "protection_level": content.get("protection_level") or "",
        "risk": {
            "status": status,
            "label": RISK_STATUSES.get(status, RISK_STATUSES["unknown"])["label"],
            "reasons": [RISK_REASONS.get(r, r) for r in (site.get("risk_reasons") or [])],
            "summary": site.get("risk_summary") or "",
            "updated_at": site.get("risk_updated_at"),
        },
        "preservation_actions": content.get("preservation_actions") or [],
        "quick_facts": content.get("quick_facts") or [],
        "chronicle": [
            {"year": e["year"], "date_text": e["date_text"], "title": e["title"], "description": e["description"], "kind": e["kind"]}
            for e in events
        ],
        "sources": [
            {"ref": s["ref"], "kind": s["kind"], "title": s["title"], "url": s["url"], "language": s["language"]}
            for s in sources
        ],
    }
    return JSONResponse(
        passport,
        headers={"Content-Disposition": f'attachment; filename="{site["slug"]}-passport.json"'},
    )


@router.get("/jobs/{job_id}")
def job_page(request: Request, job_id: str, conn=Depends(get_db)):
    job = repo.get_job(conn, job_id)
    if not job:
        raise HTTPException(404, "This job does not exist.")
    lang = _req_lang(request, (job.get("input") or {}).get("lang", ""))
    return render(request, "job.html", {"job": job, "lang": lang})


@router.get("/api/jobs/{job_id}")
def job_status(job_id: str, conn=Depends(get_db)):
    job = repo.get_job(conn, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JSONResponse({k: job[k] for k in ("id", "kind", "status", "steps", "result", "error")})


@router.get("/archive")
def archive(request: Request, status: str = "", q: str = "", conn=Depends(get_db)):
    status = status if status in RISK_STATUSES or status == "endangered" else ""
    sites = repo.list_sites(conn, status=status or None, query=q.strip() or None)
    sites = [editions.localized(conn, site, repo.list_events(conn, site["id"]), _req_lang(request))[0] for site in sites]
    return render(request, "archive.html", {
        "sites": sites,
        "map_sites": _map_sites_payload(sites),
        "status": status, "q": q, "counts": repo.site_counts(conn),
    })


def build_timeline(events: list[dict], photos: list[dict], memories: list[dict]) -> list[dict]:
    """Events and memories one by one; dated photos grouped into one gallery row per year."""
    items = []
    for event in events:
        items.append({"type": "event", "year": event["year"], "item": event})
    photos_by_year: dict[int, list[dict]] = {}
    for photo in photos:
        if photo["year"] is not None:
            photos_by_year.setdefault(photo["year"], []).append(photo)
    for year, group in photos_by_year.items():
        items.append({"type": "photos", "year": year, "item": group[:3]})
    for memory in memories:
        year = memory["year_given"] or memory["year_estimate"]
        if year is not None:
            items.append({"type": "memory", "year": year, "item": memory})
    order = {"event": 0, "photos": 1, "memory": 2}
    return sorted(items, key=lambda i: (i["year"] is None, i["year"] or 0, order[i["type"]]))


@router.get("/site/{slug}")
def site_page(request: Request, slug: str, conn=Depends(get_db)):
    site = repo.get_site_by_slug(conn, slug)
    if not site or not site["is_published"]:
        raise HTTPException(404, "This site is not in the archive.")
    settings = request.app.state.settings
    site_id = site["id"]
    events = repo.list_events(conn, site_id)
    site, events, translation_missing = editions.localized(conn, site, events, _req_lang(request))
    content = site["content"] or {}
    photos = repo.list_photos(conn, site_id)
    memories = repo.list_memories(conn, site_id)
    timeline = build_timeline(events, photos, memories)
    decades = sorted({(i["year"] // 10) * 10 for i in timeline if i["year"] is not None})
    story_chapters = [{**card, "photo": photos[i] if i < min(3, len(photos)) else None}
                      for i, card in enumerate(content.get("tour_cards", []))]
    return render(request, "site.html", {
        "site": site,
        "content": content,
        "theme": site["theme"] or {},
        "sources": {s["ref"]: s for s in repo.list_sources(conn, site_id)},
        "events": events,
        "photos": photos,
        "undated_photos": [p for p in photos if p["year"] is None][:3],
        "memories": memories,
        "media": repo.list_media(conn, site_id),
        "news": repo.list_news(conn, site_id=site_id, state="added")[:6],
        "timeline": timeline,
        "decades": decades,
        "story_chapters": story_chapters,
        "translation_missing": translation_missing,
        "public_generation": settings.public_generation,
    })


@router.get("/media/{bucket}/{filename}")
def media_file(request: Request, bucket: str, filename: str, conn=Depends(get_db)):
    uploads_dir = request.app.state.settings.uploads_dir
    path = resolve_upload(uploads_dir, bucket, filename)
    if not path or not repo.file_is_public(conn, f"{bucket}/{filename}"):
        raise HTTPException(404, "File not found.")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})
