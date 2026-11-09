"""Curator area: moderation queues, site editing, tour cameras, news triage and AI hypotheses."""

import time

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import ValidationError

from app import repo
from app.models import EVENT_KINDS, RISK_REASONS, RISK_STATUSES, Pose
from app.security import is_http_url, require_admin, verify_csrf
from app.services import pipeline
from app.services.storage import resolve_upload
from app.web import get_db, render, year_or_none

router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])


def _site_or_404(conn, slug: str) -> dict:
    site = repo.get_site_by_slug(conn, slug)
    if not site:
        raise HTTPException(404, "Site not found.")
    return site


def _back(request: Request, fallback: str) -> RedirectResponse:
    referer = request.headers.get("referer", "")
    host = request.headers.get("host", "")
    target = referer if host and f"//{host}/admin" in referer else fallback
    return RedirectResponse(target, status_code=303)


@router.get("")
def dashboard(request: Request, conn=Depends(get_db)):
    settings = request.app.state.settings
    return render(request, "admin/dashboard.html", {
        "pending": repo.pending_counts(conn),
        "sites": repo.list_sites(conn, published_only=False),
        "jobs": repo.list_jobs(conn),
        "config": {
            "Gemini AI": settings.ai_enabled,
            "Google Search grounding": settings.ai_enabled and settings.use_search_grounding,
            "Google Maps 3D tiles": bool(settings.google_maps_api_key),
            "Europeana archive": bool(settings.europeana_api_key),
            "Sketchfab search": settings.sketchfab_enabled,
            f"News monitor ({settings.news_provider})": settings.news_provider != "none",
            "Public site generation": settings.public_generation,
        },
    })


@router.get("/moderation")
def moderation(request: Request, conn=Depends(get_db)):
    return render(request, "admin/moderation.html", {"pending": repo.pending_items(conn)})


@router.post("/moderate/{kind}/{item_id}/{decision}", dependencies=[Depends(verify_csrf)])
def moderate(request: Request, kind: str, item_id: int, decision: str, conn=Depends(get_db)):
    if kind not in repo.MODERATED_TABLES or decision not in ("approve", "reject"):
        raise HTTPException(404, "Unknown moderation action.")
    item = repo.get_moderated(conn, kind, item_id)
    if not item:
        raise HTTPException(404, "Item not found.")
    status = "approved" if decision == "approve" else "rejected"
    repo.set_status(conn, kind, item_id, status)

    if status == "approved" and kind == "poses":
        repo.set_photo_pose(conn, item["photo_id"], item["pose"])
    if kind == "memories" and item["kind"] == "photo" and item["file_path"]:
        # Approved family photos with a date join the "Through time" gallery and can be aligned in 3D.
        year = item["year_given"] or item["year_estimate"]
        repo.upsert_photo_candidate(conn, item["site_id"], {
            "provider": "community", "provider_id": f"memory-{item_id}",
            "title": item["summary"] or f"Photo shared by {item['author_name'] or 'a visitor'}",
            "description": item["photo_description"] or item["text_en"] or item["text_original"],
            "author": item["author_name"] or "Community contributor", "license": item["license"],
            "image_url": f"/media/{item['file_path']}", "thumb_url": f"/media/{item['file_path']}",
            "year": year, "date_text": str(year) if year else "",
            "year_source": "contributor" if item["year_given"] else ("ai_estimate" if year else ""),
            "status": "approved",
        })
        conn.execute("UPDATE photos SET status = ? WHERE site_id = ? AND provider = 'community' AND provider_id = ?",
                     (status, item["site_id"], f"memory-{item_id}"))
    return _back(request, "/admin/moderation")


@router.get("/media/{bucket}/{filename}")
def private_media(request: Request, bucket: str, filename: str):
    path = resolve_upload(request.app.state.settings.uploads_dir, bucket, filename)
    if not path:
        raise HTTPException(404, "File not found.")
    return FileResponse(path, headers={"Cache-Control": "private, no-store"})


# ---------------------------------------------------------------- sites

@router.get("/sites/{slug}")
def edit_site(request: Request, slug: str, conn=Depends(get_db)):
    site = _site_or_404(conn, slug)
    settings = request.app.state.settings
    content = site["content"] or {}
    return render(request, "admin/site_edit.html", {
        "site": site,
        "content": content,
        "events": repo.list_events(conn, site["id"]),
        "photos": repo.list_photos(conn, site["id"]),
        "pending_photos": repo.list_photos(conn, site["id"], status="pending"),
        "hidden_photos": repo.list_photos(conn, site["id"], status="rejected"),
        "scans": repo.list_scans(conn, site["id"]) + repo.list_scans(conn, site["id"], status="pending"),
        "news": repo.list_news(conn, site_id=site["id"], state=None)[:30],
        "viewer": {
            "latitude": site["latitude"], "longitude": site["longitude"], "mapsKey": settings.google_maps_api_key,
            "tour": [{"camera": c.get("camera"), "pose": c.get("pose")} for c in content.get("tour_cards", [])],
        },
    })


@router.post("/sites/{slug}", dependencies=[Depends(verify_csrf)])
async def update_site(request: Request, slug: str, conn=Depends(get_db)):
    site = _site_or_404(conn, slug)
    form = await request.form()
    data: dict = {
        "title": str(form.get("title", site["title"])).strip()[:200] or site["title"],
        "native_name": str(form.get("native_name", "")).strip()[:200],
        "location_label": str(form.get("location_label", "")).strip()[:200],
        "tagline": str(form.get("tagline", "")).strip()[:500],
        "is_published": 1 if form.get("is_published") == "yes" else 0,
    }
    status = str(form.get("risk_status", site["risk_status"]))
    reasons = [r for r in form.getlist("risk_reasons") if r in RISK_REASONS]
    summary = str(form.get("risk_summary", "")).strip()[:2000]
    if status in RISK_STATUSES and (status, reasons, summary) != (site["risk_status"], site["risk_reasons"], site["risk_summary"]):
        data.update(risk_status=status, risk_reasons=reasons, risk_summary=summary, risk_updated_at=repo.now_iso())
    try:
        lat_raw, lon_raw = str(form.get("latitude", "")).strip(), str(form.get("longitude", "")).strip()
        if lat_raw and lon_raw:
            lat, lon = float(lat_raw), float(lon_raw)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError
            if (lat, lon) != (site["latitude"], site["longitude"]):
                data.update(latitude=lat, longitude=lon, coord_source="manual")
    except ValueError as exc:
        raise HTTPException(400, "Coordinates must be decimal degrees.") from exc
    repo.update_site(conn, site["id"], data)
    return RedirectResponse(f"/admin/sites/{slug}?saved=1", status_code=303)






@router.post("/sites/{slug}/photos/approve-all", dependencies=[Depends(verify_csrf)])
def approve_all_photos(slug: str, conn=Depends(get_db)):
    site = _site_or_404(conn, slug)
    repo.approve_all_photos(conn, site["id"])
    return RedirectResponse(f"/admin/sites/{slug}#photos", status_code=303)




@router.post("/sites/{slug}/events", dependencies=[Depends(verify_csrf)])
def add_event(
    slug: str,
    title: str = Form(...), year: str = Form(""), date_text: str = Form(""), description: str = Form(""),
    kind: str = Form("other"), source_url: str = Form(""), source_title: str = Form(""),
    conn=Depends(get_db),
):
    site = _site_or_404(conn, slug)
    if source_url and not is_http_url(source_url):
        raise HTTPException(400, "The source must be an http(s) link.")
    repo.insert_event(conn, site["id"], {
        "year": year_or_none(year), "date_text": date_text.strip()[:80] or year.strip(), "title": title.strip()[:200],
        "description": description.strip()[:1000], "kind": kind if kind in EVENT_KINDS else "other",
        "source_url": source_url.strip(), "source_title": source_title.strip()[:300], "origin": "curator",
    })
    return RedirectResponse(f"/admin/sites/{slug}#events", status_code=303)


@router.post("/events/{event_id}/delete", dependencies=[Depends(verify_csrf)])
def delete_event(request: Request, event_id: int, conn=Depends(get_db)):
    conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
    return _back(request, "/admin")


ACTIONS = {
    "photos": ("refresh_photos", "Finding archive photographs"),
    "news": ("check_news", "Checking the news"),
}


@router.post("/sites/{slug}/actions/{action}", dependencies=[Depends(verify_csrf)])
def run_action(request: Request, slug: str, action: str, conn=Depends(get_db)):
    site = _site_or_404(conn, slug)
    settings = request.app.state.settings
    jobs = request.app.state.jobs
    if action == "regenerate":
        if not site["source_url"]:
            raise HTTPException(400, "This site has no source URL to regenerate from.")
        url = site["source_url"]
        job_id = jobs.submit("generate", lambda ctx: pipeline.generate_site(ctx, url), site_id=site["id"],
                             input_data={"url": url})
    elif action in ACTIONS:
        fn_name, label = ACTIONS[action]
        fn = getattr(pipeline, fn_name)
        site_id = site["id"]

        def task(ctx):
            ctx.step(label)
            ctx.note(fn(settings, site_id))
            return {"site_slug": slug}

        job_id = jobs.submit(action, task, site_id=site_id)
    else:
        raise HTTPException(404, "Unknown action.")
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)




# ---------------------------------------------------------------- news

@router.get("/news")
def news_queue(request: Request, show: str = "relevant", conn=Depends(get_db)):
    items = repo.list_news(conn, state="new")
    if show == "relevant":
        items = [i for i in items if i["ai_relevant"] != 0]
    return render(request, "admin/news.html", {"items": items, "show": show})


@router.post("/news/check-all", dependencies=[Depends(verify_csrf)])
def check_all_news(request: Request, conn=Depends(get_db)):
    settings = request.app.state.settings
    site_ids = [s["id"] for s in repo.list_sites(conn, published_only=False)]

    def task(ctx):
        for site_id in site_ids:
            ctx.step(f"Site #{site_id}")
            try:
                ctx.note(pipeline.check_news(settings, site_id))
            except Exception as exc:  # noqa: BLE001
                ctx.warn(str(exc))
            if settings.news_provider == "gdelt":
                time.sleep(6)
        return {}

    job_id = request.app.state.jobs.submit("news_all", task)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


def _news_or_404(conn, news_id: int) -> dict:
    item = repo.get_news_item(conn, news_id)
    if not item:
        raise HTTPException(404, "News item not found.")
    return item


@router.post("/news/{news_id}/add-event", dependencies=[Depends(verify_csrf)])
def news_to_event(request: Request, news_id: int, conn=Depends(get_db)):
    item = _news_or_404(conn, news_id)
    proposed = item["ai_event"] or {}
    year = proposed.get("year") or year_or_none((item["published_at"] or "")[:4])
    repo.insert_event(conn, item["site_id"], {
        "year": year, "date_text": proposed.get("date_text") or item["published_at"],
        "title": proposed.get("title") or item["title"], "description": proposed.get("description") or item["ai_summary"],
        "kind": proposed.get("kind") if proposed.get("kind") in EVENT_KINDS else "other",
        "source_url": item["url"], "source_title": f"{item['source_name']}: {item['title']}".strip(": "),
        "origin": "news",
    })
    repo.set_news_state(conn, news_id, "added")
    return _back(request, "/admin/news")


@router.post("/news/{news_id}/apply-status", dependencies=[Depends(verify_csrf)])
def news_apply_status(request: Request, news_id: int, conn=Depends(get_db)):
    item = _news_or_404(conn, news_id)
    status = item["ai_suggested_status"]
    if status not in RISK_STATUSES:
        raise HTTPException(400, "This article has no suggested status.")
    site = repo.get_site(conn, item["site_id"])
    ref = repo.add_source(conn, site["id"], "news", f"{item['source_name']}, {item['published_at']}: {item['title']}",
                          item["url"], "en")
    repo.update_site(conn, site["id"], {
        "risk_status": status,
        "risk_summary": item["ai_summary"] or site["risk_summary"],
        "risk_source_refs": sorted(set(site["risk_source_refs"] or []) | {ref}),
        "risk_updated_at": repo.now_iso(),
    })
    repo.set_news_state(conn, news_id, "added")
    return _back(request, "/admin/news")


@router.post("/news/{news_id}/dismiss", dependencies=[Depends(verify_csrf)])
def news_dismiss(request: Request, news_id: int, conn=Depends(get_db)):
    _news_or_404(conn, news_id)
    repo.set_news_state(conn, news_id, "dismissed")
    return _back(request, "/admin/news")
