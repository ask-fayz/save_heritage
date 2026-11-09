"""Demo data: a hand-checked Sunbeam Theatre record so a fresh install has something real to explore."""

import json
import sqlite3
from pathlib import Path

from app import repo

SEED_DIR = Path(__file__).parent


def seed_demo_data(conn: sqlite3.Connection) -> bool:
    """Insert the demo site into an empty archive. Returns True if something was inserted."""
    if conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]:
        return False
    data = json.loads((SEED_DIR / "sunbeam.json").read_text(encoding="utf-8"))
    site = dict(data["site"])
    site["risk_updated_at"] = repo.now_iso()
    site_id = repo.insert_site(conn, site)
    repo.replace_sources(conn, site_id, data["sources"])
    for event in data["events"]:
        repo.insert_event(conn, site_id, event)
    photos = json.loads((SEED_DIR / "sunbeam_photos.json").read_text(encoding="utf-8"))
    for photo in photos:
        repo.upsert_photo_candidate(conn, site_id, photo)
    return True
