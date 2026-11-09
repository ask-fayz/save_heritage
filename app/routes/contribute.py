"""Community contributions: memories, 3D scans, recordings and photo alignments. Everything waits for moderation."""

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app import repo
from app.models import Pose
from app.security import client_ip, embed_for_url, is_http_url, rate_limiter, verify_csrf
from app.services import pipeline
from app.services.storage import save_upload
from app.web import get_db, render, year_or_none

router = APIRouter()

LICENSES = {
    "CC BY 4.0": "CC BY 4.0: anyone may reuse with credit",
    "CC BY-NC 4.0": "CC BY-NC 4.0: reuse with credit, non-commercial only",
    "All rights reserved": "All rights reserved: show on SAVE Heritage only",
}


def _site_or_404(conn, slug: str) -> dict:
    site = repo.get_site_by_slug(conn, slug)
    if not site or not site["is_published"]:
        raise HTTPException(404, "This site is not in the archive.")
    return site


def _limit(request: Request) -> None:
    settings = request.app.state.settings
    rate_limiter.hit(f"contribute:{client_ip(request, settings)}", settings.contribution_rate_per_hour)


def _check_length(request: Request, max_mb: int) -> None:
    """Reject oversized uploads before the body is spooled to disk."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > (max_mb + 1) * 1024 * 1024:
        raise HTTPException(413, f"The upload is larger than {max_mb} MB.")


def _clean(text: str, limit: int) -> str:
    return (text or "").strip()[:limit]


# ---------------------------------------------------------------- memories

@router.get("/site/{slug}/memories/new")
def memory_form(request: Request, slug: str, conn=Depends(get_db)):
    site = _site_or_404(conn, slug)
    return render(request, "contribute/memory.html", {"site": site, "licenses": LICENSES, "form": {"kind": "photo" if request.query_params.get("kind") == "photo" else "story"}})


@router.post("/site/{slug}/memories", dependencies=[Depends(verify_csrf)])
def submit_memory(
    request: Request,
    slug: str,
    kind: str = Form("story"),
    text: str = Form(""),
    author_name: str = Form(""),
    year: str = Form(""),
    license: str = Form("CC BY 4.0"),
    consent: str = Form(""),
    file: UploadFile | None = File(None),
    conn=Depends(get_db),
):
    settings = request.app.state.settings
    site = _site_or_404(conn, slug)
    _check_length(request, max(settings.max_photo_mb, settings.max_audio_mb))
    form = {"kind": kind, "text": text, "author_name": author_name, "year": year, "license": license}

    def fail(message: str):
        return render(request, "contribute/memory.html",
                      {"site": site, "licenses": LICENSES, "form": form, "error": message}, status_code=400)

    if kind not in ("story", "photo", "audio"):
        return fail("Choose what you are sharing.")
    if consent != "yes":
        return fail("Please confirm that you agree to publish this memory.")
    if license not in LICENSES:
        return fail("Choose a licence.")
    text = _clean(text, 8000)
    if kind == "story" and len(text) < 20:
        return fail("Tell us a little more (at least a couple of sentences).")
    has_file = file is not None and bool(file.filename)
    if kind in ("photo", "audio") and not has_file:
        return fail("Attach a photo." if kind == "photo" else "Record or attach an audio file.")
    year_given = year_or_none(year, low=1800, high=date.today().year) if year else None
    if year and year_given is None:
        return fail("The year should look like 1985.")

    _limit(request)
    stored = None
    if has_file and kind != "story":
        if kind == "photo":
            stored = save_upload(file, settings.uploads_dir, "memories", "image", settings.max_photo_mb)
        else:
            stored = save_upload(file, settings.uploads_dir, "memories", "audio", settings.max_audio_mb)

    memory_id = repo.insert_memory(conn, site["id"], {
        "kind": kind, "author_name": _clean(author_name, 120), "text_original": text,
        "file_path": stored.relative_path if stored else "", "mime_type": stored.mime_type if stored else "",
        "year_given": year_given, "license": license,
        "ai_status": "pending" if settings.ai_enabled else "skipped",
    })
    conn.commit()
    if settings.ai_enabled:
        request.app.state.jobs.submit(
            "memory_ai", lambda ctx: {"message": pipeline.process_memory(settings, memory_id)},
            site_id=site["id"], input_data={"memory_id": memory_id},
        )
    return RedirectResponse(f"/site/{slug}/thanks?what=memory", status_code=303)


# ---------------------------------------------------------------- 3D scans





# ---------------------------------------------------------------- recordings and links

@router.get("/site/{slug}/media/new")
def media_form(request: Request, slug: str, conn=Depends(get_db)):
    site = _site_or_404(conn, slug)
    return render(request, "contribute/media.html", {"site": site, "form": {}})


@router.post("/site/{slug}/media", dependencies=[Depends(verify_csrf)])
def submit_media(
    request: Request,
    slug: str,
    url: str = Form(""),
    title: str = Form(""),
    year: str = Form(""),
    description: str = Form(""),
    author_name: str = Form(""),
    file: UploadFile | None = File(None),
    consent: str = Form(""),
    conn=Depends(get_db),
):
    site = _site_or_404(conn, slug)
    form = {"url": url, "title": title, "year": year, "description": description, "author_name": author_name}

    def fail(message: str):
        return render(request, "contribute/media.html", {"site": site, "form": form, "error": message},
                      status_code=400)

    settings = request.app.state.settings
    _check_length(request, settings.max_video_mb)
    has_file = file is not None and bool(file.filename)
    if has_file and consent != "yes":
        return fail("Please confirm you have the right to share this recording.")
    if has_file and url.strip():
        return fail("Choose a video file or a link, not both.")
    url = url.strip()
    if not has_file and not is_http_url(url):
        return fail("Paste a full link that starts with https://")
    if len(title.strip()) < 3:
        return fail("Give the recording a short title.")
    year_value = year_or_none(year, low=1850, high=date.today().year) if year else None
    if year and year_value is None:
        return fail("The year should look like 1985.")
    _limit(request)
    if has_file:
        stored = save_upload(file, settings.uploads_dir, "recordings", "video", settings.max_video_mb)
        url, embed_url, kind = "/media/" + stored.relative_path, "", "uploaded_video"
    else:
        embed_url, provider = embed_for_url(url)
        kind = "video" if provider in ("youtube", "vimeo", "bilibili", "archive.org") else "link"
    repo.insert_media(conn, site["id"], {
        "kind": kind, "title": _clean(title, 160), "url": url[:1000], "embed_url": embed_url, "year": year_value,
        "description": _clean(description, 1000), "submitted_by": _clean(author_name, 120),
    })
    return RedirectResponse(f"/site/{slug}/thanks?what=media", status_code=303)


# ---------------------------------------------------------------- photo alignment ("window to the past")







@router.get("/site/{slug}/thanks")
def thanks(request: Request, slug: str, what: str = "memory", conn=Depends(get_db)):
    site = _site_or_404(conn, slug)
    return render(request, "contribute/thanks.html", {"site": site, "what": what})
