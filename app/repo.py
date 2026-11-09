"""Data access layer. Functions take an open sqlite3 connection and return plain dicts."""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

JSON_FIELDS = {
    "facts_json", "content_json", "theme_json", "risk_reasons_json", "risk_source_refs_json",
    "source_refs_json", "pose_json", "tags_json", "moderation_flags_json", "input_photo_ids_json",
    "ai_event_json", "input_json", "steps_json", "result_json",
}

# Tables whose rows go through curator moderation, keyed by the name used in admin URLs.
MODERATED_TABLES = {
    "memories": "memories",
    "photos": "photos",
    "poses": "pose_suggestions",
    "scans": "scans",
    "media": "media",
    "reconstructions": "reconstructions",
    "events": "events",
}


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out: dict[str, Any] = {}
    for key in row.keys():
        value = row[key]
        if key in JSON_FIELDS:
            out[key.removesuffix("_json")] = json.loads(value) if value else None
        else:
            out[key] = value
    return out


def _decode_all(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [_decode(r) for r in rows]  # type: ignore[misc]


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


# ---------------------------------------------------------------- sites

def get_site_by_slug(conn: sqlite3.Connection, slug: str) -> dict | None:
    return _decode(conn.execute("SELECT * FROM sites WHERE slug = ?", (slug,)).fetchone())


def get_site(conn: sqlite3.Connection, site_id: int) -> dict | None:
    return _decode(conn.execute("SELECT * FROM sites WHERE id = ?", (site_id,)).fetchone())


def find_site_for_generation(conn: sqlite3.Connection, qid: str | None, source_url: str) -> dict | None:
    if qid:
        row = conn.execute("SELECT * FROM sites WHERE wikidata_qid = ?", (qid,)).fetchone()
        if row:
            return _decode(row)
    return _decode(conn.execute("SELECT * FROM sites WHERE source_url = ?", (source_url,)).fetchone())


def slug_exists(conn: sqlite3.Connection, slug: str) -> bool:
    return conn.execute("SELECT 1 FROM sites WHERE slug = ?", (slug,)).fetchone() is not None


def list_sites(conn: sqlite3.Connection, *, status: str | None = None, query: str | None = None,
               published_only: bool = True) -> list[dict]:
    sql = "SELECT * FROM sites WHERE 1=1"
    params: list[Any] = []
    if published_only:
        sql += " AND is_published = 1"
    if status == "endangered":
        sql += " AND risk_status IN ('watch', 'at_risk', 'critical')"
    elif status:
        sql += " AND risk_status = ?"
        params.append(status)
    if query:
        sql += " AND (title LIKE ? OR native_name LIKE ? OR location_label LIKE ?)"
        like = f"%{query}%"
        params += [like, like, like]
    sql += " ORDER BY updated_at DESC"
    return _decode_all(conn.execute(sql, params).fetchall())


SITE_COLUMNS = (
    "slug", "wikidata_qid", "source_url", "title", "native_name", "location_label", "tagline",
    "latitude", "longitude", "coord_source", "facts_json", "content_json", "theme_json",
    "risk_status", "risk_reasons_json", "risk_summary", "risk_source_refs_json", "risk_updated_at",
    "language", "generation_mode", "is_published",
)


def _site_params(data: dict) -> dict:
    params = {}
    for col in SITE_COLUMNS:
        key = col.removesuffix("_json")
        if key in data:
            params[col] = _dump(data[key]) if col.endswith("_json") else data[key]
    return params


def insert_site(conn: sqlite3.Connection, data: dict) -> int:
    params = _site_params(data)
    cols = ", ".join(params)
    marks = ", ".join(f":{c}" for c in params)
    cur = conn.execute(f"INSERT INTO sites ({cols}) VALUES ({marks})", params)
    return int(cur.lastrowid)


def update_site(conn: sqlite3.Connection, site_id: int, data: dict) -> None:
    params = _site_params(data)
    if not params:
        return
    assignments = ", ".join(f"{c} = :{c}" for c in params)
    params["id"] = site_id
    params["updated_at"] = now_iso()
    conn.execute(f"UPDATE sites SET {assignments}, updated_at = :updated_at WHERE id = :id", params)


def site_counts(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        """SELECT
             (SELECT COUNT(*) FROM sites WHERE is_published = 1) AS sites,
             (SELECT COUNT(*) FROM sites WHERE is_published = 1 AND risk_status IN ('watch','at_risk','critical')) AS endangered,
             (SELECT COUNT(*) FROM sites WHERE is_published = 1 AND risk_status = 'lost') AS lost,
             (SELECT COUNT(*) FROM memories WHERE status = 'approved') AS memories,
             (SELECT COUNT(*) FROM photos WHERE status = 'approved') AS photos"""
    ).fetchone()
    return dict(row)


# ---------------------------------------------------------------- sources

def replace_sources(conn: sqlite3.Connection, site_id: int, sources: list[dict]) -> None:
    conn.execute("DELETE FROM sources WHERE site_id = ?", (site_id,))
    conn.executemany(
        "INSERT INTO sources (site_id, ref, kind, title, url, language) VALUES (?, ?, ?, ?, ?, ?)",
        [(site_id, s["ref"], s["kind"], s.get("title", ""), s.get("url", ""), s.get("language", "")) for s in sources],
    )


def list_sources(conn: sqlite3.Connection, site_id: int) -> list[dict]:
    return _decode_all(conn.execute("SELECT * FROM sources WHERE site_id = ? ORDER BY ref", (site_id,)).fetchall())


def add_source(conn: sqlite3.Connection, site_id: int, kind: str, title: str, url: str, language: str = "") -> int:
    existing = conn.execute("SELECT ref FROM sources WHERE site_id = ? AND url = ? AND url != ''", (site_id, url)).fetchone()
    if existing:
        return int(existing["ref"])
    ref = conn.execute("SELECT COALESCE(MAX(ref), 0) + 1 FROM sources WHERE site_id = ?", (site_id,)).fetchone()[0]
    conn.execute(
        "INSERT INTO sources (site_id, ref, kind, title, url, language) VALUES (?, ?, ?, ?, ?, ?)",
        (site_id, ref, kind, title, url, language),
    )
    return int(ref)


# ---------------------------------------------------------------- events

def insert_event(conn: sqlite3.Connection, site_id: int, event: dict) -> int:
    cur = conn.execute(
        """INSERT INTO events (site_id, year, date_text, title, description, kind, source_refs_json,
                               source_url, source_title, origin, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            site_id, event.get("year"), event.get("date_text", ""), event["title"], event.get("description", ""),
            event.get("kind", "other"), _dump(event.get("source_refs", [])), event.get("source_url", ""),
            event.get("source_title", ""), event.get("origin", "ai"), event.get("status", "approved"),
        ),
    )
    return int(cur.lastrowid)


def delete_generated_events(conn: sqlite3.Connection, site_id: int) -> None:
    """Regeneration replaces AI/Wikidata events but keeps news, curator and seed entries."""
    conn.execute("DELETE FROM events WHERE site_id = ? AND origin IN ('ai', 'wikidata')", (site_id,))


def list_events(conn: sqlite3.Connection, site_id: int, status: str = "approved") -> list[dict]:
    return _decode_all(conn.execute(
        "SELECT * FROM events WHERE site_id = ? AND status = ? ORDER BY year IS NULL, year, id",
        (site_id, status),
    ).fetchall())


# ---------------------------------------------------------------- photos

def upsert_photo_candidate(conn: sqlite3.Connection, site_id: int, photo: dict) -> bool:
    """Insert a discovered photo unless it is already known. Returns True if inserted."""
    cur = conn.execute(
        """INSERT OR IGNORE INTO photos (site_id, provider, provider_id, title, description, author, license,
                                        license_url, source_page_url, image_url, thumb_url, width, height, year,
                                        date_text, year_source, latitude, longitude, relevance_note, status)
           VALUES (:site_id, :provider, :provider_id, :title, :description, :author, :license, :license_url,
                   :source_page_url, :image_url, :thumb_url, :width, :height, :year, :date_text, :year_source,
                   :latitude, :longitude, :relevance_note, :status)""",
        {
            "site_id": site_id, "provider": photo["provider"], "provider_id": photo["provider_id"],
            "title": photo.get("title", ""), "description": photo.get("description", ""),
            "author": photo.get("author", ""), "license": photo.get("license", ""),
            "license_url": photo.get("license_url", ""), "source_page_url": photo.get("source_page_url", ""),
            "image_url": photo.get("image_url", ""), "thumb_url": photo.get("thumb_url", ""),
            "width": photo.get("width"), "height": photo.get("height"), "year": photo.get("year"),
            "date_text": photo.get("date_text", ""), "year_source": photo.get("year_source", ""),
            "latitude": photo.get("latitude"), "longitude": photo.get("longitude"),
            "relevance_note": photo.get("relevance_note", ""), "status": photo.get("status", "pending"),
        },
    )
    return cur.rowcount > 0


def get_photo(conn: sqlite3.Connection, photo_id: int) -> dict | None:
    return _decode(conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone())


def list_photos(conn: sqlite3.Connection, site_id: int, status: str = "approved") -> list[dict]:
    return _decode_all(conn.execute(
        "SELECT * FROM photos WHERE site_id = ? AND status = ? ORDER BY year IS NULL, year, id",
        (site_id, status),
    ).fetchall())


def set_photo_pose(conn: sqlite3.Connection, photo_id: int, pose: dict | None) -> None:
    conn.execute("UPDATE photos SET pose_json = ? WHERE id = ?", (_dump(pose) if pose else None, photo_id))


def insert_pose_suggestion(conn: sqlite3.Connection, photo_id: int, pose: dict, author_name: str) -> int:
    cur = conn.execute(
        "INSERT INTO pose_suggestions (photo_id, pose_json, author_name) VALUES (?, ?, ?)",
        (photo_id, _dump(pose), author_name),
    )
    return int(cur.lastrowid)


def approve_all_photos(conn: sqlite3.Connection, site_id: int) -> int:
    cur = conn.execute("UPDATE photos SET status = 'approved' WHERE site_id = ? AND status = 'pending'", (site_id,))
    return cur.rowcount


# ---------------------------------------------------------------- memories

def insert_memory(conn: sqlite3.Connection, site_id: int, memory: dict) -> int:
    cur = conn.execute(
        """INSERT INTO memories (site_id, kind, author_name, text_original, file_path, mime_type, year_given, license,
                                 ai_status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            site_id, memory["kind"], memory.get("author_name", ""), memory.get("text_original", ""),
            memory.get("file_path", ""), memory.get("mime_type", ""), memory.get("year_given"),
            memory.get("license", "CC BY 4.0"), memory.get("ai_status", "pending"),
        ),
    )
    return int(cur.lastrowid)


def get_memory(conn: sqlite3.Connection, memory_id: int) -> dict | None:
    return _decode(conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone())


def update_memory_ai(conn: sqlite3.Connection, memory_id: int, fields: dict) -> None:
    allowed = {
        "language", "text_en", "transcript", "summary", "photo_description", "year_estimate",
        "year_estimate_reason", "tags", "moderation_flags", "ai_status", "ai_error",
    }
    params = {}
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key in ("tags", "moderation_flags"):
            params[f"{key}_json"] = _dump(value)
        else:
            params[key] = value
    if not params:
        return
    assignments = ", ".join(f"{c} = :{c}" for c in params)
    params["id"] = memory_id
    conn.execute(f"UPDATE memories SET {assignments} WHERE id = :id", params)


def list_memories(conn: sqlite3.Connection, site_id: int, status: str = "approved") -> list[dict]:
    return _decode_all(conn.execute(
        "SELECT * FROM memories WHERE site_id = ? AND status = ? ORDER BY COALESCE(year_given, year_estimate) IS NULL, "
        "COALESCE(year_given, year_estimate), id",
        (site_id, status),
    ).fetchall())


# ---------------------------------------------------------------- media, scans, reconstructions

def insert_media(conn: sqlite3.Connection, site_id: int, item: dict) -> int:
    cur = conn.execute(
        """INSERT INTO media (site_id, kind, title, url, embed_url, year, description, submitted_by, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            site_id, item.get("kind", "video"), item["title"], item["url"], item.get("embed_url", ""),
            item.get("year"), item.get("description", ""), item.get("submitted_by", ""),
            item.get("status", "pending"),
        ),
    )
    return int(cur.lastrowid)


def list_media(conn: sqlite3.Connection, site_id: int, status: str = "approved") -> list[dict]:
    return _decode_all(conn.execute(
        "SELECT * FROM media WHERE site_id = ? AND status = ? ORDER BY year IS NULL, year, id", (site_id, status)
    ).fetchall())


def upsert_scan(conn: sqlite3.Connection, site_id: int, scan: dict) -> bool:
    cur = conn.execute(
        """INSERT OR IGNORE INTO scans (site_id, kind, provider, provider_id, title, author, license, url, embed_url,
                                        thumb_url, file_path, capture_date, notes, status)
           VALUES (:site_id, :kind, :provider, :provider_id, :title, :author, :license, :url, :embed_url, :thumb_url,
                   :file_path, :capture_date, :notes, :status)""",
        {
            "site_id": site_id, "kind": scan["kind"], "provider": scan["provider"],
            "provider_id": scan["provider_id"], "title": scan.get("title", ""), "author": scan.get("author", ""),
            "license": scan.get("license", ""), "url": scan.get("url", ""), "embed_url": scan.get("embed_url", ""),
            "thumb_url": scan.get("thumb_url", ""), "file_path": scan.get("file_path", ""),
            "capture_date": scan.get("capture_date", ""), "notes": scan.get("notes", ""),
            "status": scan.get("status", "pending"),
        },
    )
    return cur.rowcount > 0


def list_scans(conn: sqlite3.Connection, site_id: int, status: str = "approved") -> list[dict]:
    return _decode_all(conn.execute(
        "SELECT * FROM scans WHERE site_id = ? AND status = ? ORDER BY id", (site_id, status)
    ).fetchall())


def insert_reconstruction(conn: sqlite3.Connection, site_id: int, item: dict) -> int:
    cur = conn.execute(
        """INSERT INTO reconstructions (site_id, image_path, focus, target_year, prompt, input_photo_ids_json, model)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            site_id, item["image_path"], item.get("focus", ""), item.get("target_year"), item.get("prompt", ""),
            _dump(item.get("input_photo_ids", [])), item.get("model", ""),
        ),
    )
    return int(cur.lastrowid)


def list_reconstructions(conn: sqlite3.Connection, site_id: int, status: str = "approved") -> list[dict]:
    return _decode_all(conn.execute(
        "SELECT * FROM reconstructions WHERE site_id = ? AND status = ? ORDER BY id DESC", (site_id, status)
    ).fetchall())


# ---------------------------------------------------------------- news

def insert_news_item(conn: sqlite3.Connection, site_id: int, item: dict) -> int | None:
    cur = conn.execute(
        "INSERT OR IGNORE INTO news_items (site_id, url, title, source_name, published_at) VALUES (?, ?, ?, ?, ?)",
        (site_id, item["url"], item["title"], item.get("source_name", ""), item.get("published_at", "")),
    )
    return int(cur.lastrowid) if cur.rowcount else None


def update_news_ai(conn: sqlite3.Connection, news_id: int, analysis: dict) -> None:
    conn.execute(
        """UPDATE news_items SET ai_relevant = ?, ai_summary = ?, ai_threat_level = ?, ai_suggested_status = ?,
                                 ai_event_json = ?, state = CASE WHEN ? = 0 THEN 'dismissed' ELSE state END
           WHERE id = ?""",
        (
            int(analysis["relevant"]), analysis.get("summary", ""), analysis.get("threat_level", ""),
            analysis.get("suggested_status") or "", _dump(analysis["event"]) if analysis.get("event") else None,
            int(analysis["relevant"]), news_id,
        ),
    )


def get_news_item(conn: sqlite3.Connection, news_id: int) -> dict | None:
    return _decode(conn.execute("SELECT * FROM news_items WHERE id = ?", (news_id,)).fetchone())


def list_news(conn: sqlite3.Connection, *, site_id: int | None = None, state: str | None = "new") -> list[dict]:
    sql = """SELECT n.*, s.slug AS site_slug, s.title AS site_title, s.risk_status AS site_risk_status
             FROM news_items n JOIN sites s ON s.id = n.site_id WHERE 1=1"""
    params: list[Any] = []
    if site_id is not None:
        sql += " AND n.site_id = ?"
        params.append(site_id)
    if state:
        sql += " AND n.state = ?"
        params.append(state)
    sql += " ORDER BY n.published_at DESC, n.id DESC"
    return _decode_all(conn.execute(sql, params).fetchall())


def set_news_state(conn: sqlite3.Connection, news_id: int, state: str) -> None:
    conn.execute("UPDATE news_items SET state = ? WHERE id = ?", (state, news_id))


# ---------------------------------------------------------------- moderation

def set_status(conn: sqlite3.Connection, kind: str, item_id: int, status: str) -> dict | None:
    table = MODERATED_TABLES[kind]
    conn.execute(f"UPDATE {table} SET status = ? WHERE id = ?", (status, item_id))
    return _decode(conn.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,)).fetchone())


def get_moderated(conn: sqlite3.Connection, kind: str, item_id: int) -> dict | None:
    table = MODERATED_TABLES[kind]
    return _decode(conn.execute(f"SELECT * FROM {table} WHERE id = ?", (item_id,)).fetchone())


def pending_items(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    def q(sql: str) -> list[dict]:
        return _decode_all(conn.execute(sql).fetchall())

    return {
        "memories": q("""SELECT m.*, s.slug AS site_slug, s.title AS site_title FROM memories m
                         JOIN sites s ON s.id = m.site_id WHERE m.status = 'pending' ORDER BY m.id"""),
        "photos": q("""SELECT p.*, s.slug AS site_slug, s.title AS site_title FROM photos p
                       JOIN sites s ON s.id = p.site_id WHERE p.status = 'pending' ORDER BY p.site_id, p.id"""),
        "poses": q("""SELECT ps.*, p.title AS photo_title, p.thumb_url, p.image_url, p.site_id, s.slug AS site_slug,
                             s.title AS site_title
                      FROM pose_suggestions ps JOIN photos p ON p.id = ps.photo_id JOIN sites s ON s.id = p.site_id
                      WHERE ps.status = 'pending' ORDER BY ps.id"""),
        "scans": q("""SELECT sc.*, s.slug AS site_slug, s.title AS site_title FROM scans sc
                      JOIN sites s ON s.id = sc.site_id WHERE sc.status = 'pending' ORDER BY sc.id"""),
        "media": q("""SELECT md.*, s.slug AS site_slug, s.title AS site_title FROM media md
                      JOIN sites s ON s.id = md.site_id WHERE md.status = 'pending' ORDER BY md.id"""),
        "reconstructions": q("""SELECT r.*, s.slug AS site_slug, s.title AS site_title FROM reconstructions r
                                JOIN sites s ON s.id = r.site_id WHERE r.status = 'pending' ORDER BY r.id"""),
        "events": q("""SELECT e.*, s.slug AS site_slug, s.title AS site_title FROM events e
                       JOIN sites s ON s.id = e.site_id WHERE e.status = 'pending' ORDER BY e.id"""),
    }


def pending_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts = {}
    for kind, table in MODERATED_TABLES.items():
        counts[kind] = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE status = 'pending'").fetchone()[0]
    counts["news"] = conn.execute("SELECT COUNT(*) FROM news_items WHERE state = 'new'").fetchone()[0]
    return counts


def file_is_public(conn: sqlite3.Connection, relative_path: str) -> bool:
    """Uploaded files are only served publicly once the item that owns them is approved."""
    if relative_path.startswith("recordings/"):
        return conn.execute("SELECT 1 FROM media JOIN sites ON sites.id=media.site_id WHERE media.url=? AND media.kind='uploaded_video' AND media.status='approved' AND sites.is_published=1",
                            ("/media/" + relative_path,)).fetchone() is not None
    checks = (
        "SELECT 1 FROM memories WHERE file_path = ? AND status = 'approved'",
        "SELECT 1 FROM scans WHERE file_path = ? AND status = 'approved'",
        "SELECT 1 FROM reconstructions WHERE image_path = ? AND status = 'approved'",
    )
    return any(conn.execute(sql, (relative_path,)).fetchone() for sql in checks)


# ---------------------------------------------------------------- jobs

def insert_job(conn: sqlite3.Connection, job_id: str, kind: str, site_id: int | None, input_data: dict) -> None:
    conn.execute(
        "INSERT INTO jobs (id, kind, site_id, input_json) VALUES (?, ?, ?, ?)",
        (job_id, kind, site_id, _dump(input_data)),
    )


def update_job(conn: sqlite3.Connection, job_id: str, **fields: Any) -> None:
    params = {}
    for key, value in fields.items():
        if key in ("steps", "result"):
            params[f"{key}_json"] = _dump(value)
        else:
            params[key] = value
    params["updated_at"] = now_iso()
    assignments = ", ".join(f"{c} = :{c}" for c in params)
    params["id"] = job_id
    conn.execute(f"UPDATE jobs SET {assignments} WHERE id = :id", params)


def get_job(conn: sqlite3.Connection, job_id: str) -> dict | None:
    return _decode(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone())


def list_jobs(conn: sqlite3.Connection, limit: int = 20) -> list[dict]:
    return _decode_all(conn.execute(
        """SELECT j.*, s.slug AS site_slug, s.title AS site_title FROM jobs j
           LEFT JOIN sites s ON s.id = j.site_id ORDER BY j.created_at DESC LIMIT ?""",
        (limit,),
    ).fetchall())


def fail_interrupted_jobs(conn: sqlite3.Connection) -> None:
    conn.execute(
        "UPDATE jobs SET status = 'failed', error = 'Interrupted by a server restart.' "
        "WHERE status IN ('queued', 'running')"
    )
