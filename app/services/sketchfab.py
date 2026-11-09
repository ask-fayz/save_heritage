"""Find existing 3D scans of a site on Sketchfab (museums and heritage bodies publish many there)."""

import re

import httpx

SEARCH_URL = "https://api.sketchfab.com/v3/search"


def _tokens(text: str) -> set[str]:
    stop = {"the", "of", "and", "a", "de", "la", "le", "in", "at", "3d", "model", "scan"}
    return {t for t in re.findall(r"\w+", text.lower()) if t not in stop and len(t) > 1}


def title_similarity(site_title: str, model_name: str) -> float:
    wanted = _tokens(site_title)
    if not wanted:
        return 0.0
    return len(wanted & _tokens(model_name)) / len(wanted)


def search_models(client: httpx.Client, site_title: str, limit: int = 24, min_similarity: float = 0.6) -> list[dict]:
    response = client.get(SEARCH_URL, params={"type": "models", "q": site_title, "count": limit})
    response.raise_for_status()
    models = []
    for result in response.json().get("results", []):
        name = result.get("name", "")
        if title_similarity(site_title, name) < min_similarity or result.get("isAgeRestricted"):
            continue
        thumbs = sorted(result.get("thumbnails", {}).get("images", []), key=lambda i: abs(i.get("width", 0) - 480))
        license_info = result.get("license") or {}
        uid = result["uid"]
        models.append({
            "kind": "embed",
            "provider": "sketchfab",
            "provider_id": uid,
            "title": name,
            "author": (result.get("user") or {}).get("displayName") or (result.get("user") or {}).get("username", ""),
            "license": license_info.get("label", "Standard Sketchfab license"),
            "url": f"https://sketchfab.com/3d-models/{uid}",
            "embed_url": f"https://sketchfab.com/models/{uid}/embed",
            "thumb_url": thumbs[0]["url"] if thumbs else "",
            "notes": (result.get("description") or "")[:300],
        })
    return models
