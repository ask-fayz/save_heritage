"""HTTP flows: public pages, contributions, moderation and curator tools."""

from app.security import CSRF_COOKIE
from tests.conftest import ADMIN, PNG_1PX, csrf_token


def test_public_pages_render_seeded_site(client):
    home = client.get("/")
    assert home.status_code == 200 and "Sunbeam Theatre" in home.text
    site = client.get("/site/sunbeam")
    assert site.status_code == 200
    assert "Theatre closes after 52 years" in site.text          # chronicle
    assert 'href="#source-6"' in site.text                        # citations link to sources
    assert "Sources disagree" in site.text                        # disputed points
    assert "GOOGLE_MAPS_API_KEY" not in site.text                     # honest message without a key
    assert client.get("/archive?status=critical").text.count("site-card") == 1
    assert client.get("/archive?status=stable").text.count("site-card") == 0
    assert client.get("/site/does-not-exist", headers={"Accept": "text/html"}).status_code == 404


def test_generate_validates_url_and_csrf(client):
    token = csrf_token(client, "/")
    assert client.post("/generate", data={"url": "https://example.org"}).status_code == 403  # no CSRF token
    response = client.post("/generate", data={"url": "http://169.254.169.254/latest", "csrf_token": token})
    assert response.status_code == 400
    assert "private or local network" in response.text


def test_generation_rate_limit(client, settings):
    settings.generation_rate_per_hour = 2
    token = csrf_token(client, "/")
    for _ in range(2):
        client.post("/generate", data={"url": "ftp://bad", "csrf_token": token})
    assert client.post("/generate", data={"url": "ftp://bad", "csrf_token": token}).status_code == 429


def test_admin_requires_login(client):
    assert client.get("/admin").status_code == 401
    assert client.get("/admin", auth=("admin", "wrong")).status_code == 401
    assert client.get("/admin", auth=ADMIN).status_code == 200


def approve(client, kind, item_id):
    token = csrf_token(client, "/admin/moderation", auth=ADMIN)
    response = client.post(f"/admin/moderate/{kind}/{item_id}/approve", data={"csrf_token": token}, auth=ADMIN)
    assert response.status_code in (200, 303)


def test_story_memory_is_moderated(client, db):
    token = csrf_token(client, "/site/sunbeam/memories/new")
    response = client.post("/site/sunbeam/memories", data={
        "csrf_token": token, "kind": "story", "text": "I watched my first opera here in 1985 with my grandmother.",
        "year": "1985", "author_name": "Mei", "license": "CC BY 4.0", "consent": "yes",
    }, follow_redirects=False)
    assert response.status_code == 303
    memory = db.execute("SELECT * FROM memories").fetchone()
    assert memory["status"] == "pending" and memory["ai_status"] == "skipped"
    assert "my first opera" not in client.get("/site/sunbeam").text

    approve(client, "memories", memory["id"])
    page = client.get("/site/sunbeam").text
    assert "my first opera" in page and "Mei" in page


def test_memory_form_validation(client):
    token = csrf_token(client, "/site/sunbeam/memories/new")
    no_consent = client.post("/site/sunbeam/memories", data={"csrf_token": token, "kind": "story", "text": "x" * 40})
    assert no_consent.status_code == 400 and "agree" in no_consent.text
    bad_file = client.post("/site/sunbeam/memories", data={"csrf_token": token, "kind": "photo", "consent": "yes"},
                           files={"file": ("x.jpg", b"<script>alert(1)</script>", "image/jpeg")})
    assert bad_file.status_code == 400


def test_photo_memory_files_are_private_until_approved(client, db):
    token = csrf_token(client, "/site/sunbeam/memories/new")
    client.post("/site/sunbeam/memories", data={"csrf_token": token, "kind": "photo", "year": "1978", "consent": "yes"},
                files={"file": ("family.png", PNG_1PX, "image/png")})
    memory = db.execute("SELECT * FROM memories").fetchone()
    assert memory["file_path"].startswith("memories/") and memory["file_path"].endswith(".png")
    assert client.get(f"/media/{memory['file_path']}").status_code == 404
    assert client.get(f"/admin/media/{memory['file_path']}", auth=ADMIN).status_code == 200

    approve(client, "memories", memory["id"])
    assert client.get(f"/media/{memory['file_path']}").status_code == 200
    photo = db.execute("SELECT * FROM photos WHERE provider = 'community'").fetchone()
    assert photo["status"] == "approved" and photo["year"] == 1978  # joins the "Through time" gallery


def test_media_path_traversal_is_refused(client):
    assert client.get("/media/memories/..%2F..%2Fsave.db").status_code == 404
    assert client.get("/media/secrets/file.txt").status_code == 404




def test_recording_link_is_embedded_after_approval(client, db):
    token = csrf_token(client, "/site/sunbeam/media/new")
    client.post("/site/sunbeam/media", data={"csrf_token": token, "url": "https://youtu.be/dQw4w9WgXcQ",
                                             "title": "Rehearsal, 1993", "year": "1993"})
    item = db.execute("SELECT * FROM media").fetchone()
    assert item["embed_url"] == "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
    approve(client, "media", item["id"])
    assert "youtube-nocookie.com/embed/dQw4w9WgXcQ" in client.get("/site/sunbeam").text




def test_curator_edits_risk_and_news(client, db):
    token = csrf_token(client, "/admin/sites/sunbeam", auth=ADMIN)
    response = client.post("/admin/sites/sunbeam", auth=ADMIN, data={
        "csrf_token": token, "title": "Sunbeam Theatre", "risk_status": "lost", "risk_reasons": ["ownership", "funding"],
        "risk_summary": "Closed.", "latitude": "22.2913", "longitude": "114.2", "is_published": "yes",
    })
    assert response.status_code in (200, 303)
    site = db.execute("SELECT risk_status, risk_reasons_json FROM sites WHERE slug = 'sunbeam'").fetchone()
    assert site["risk_status"] == "lost" and "funding" in site["risk_reasons_json"]

    db.execute("""INSERT INTO news_items (site_id, url, title, source_name, published_at, ai_relevant, ai_summary,
                                          ai_suggested_status, ai_event_json)
                  VALUES (1, 'https://news.example/a', 'Theatre reopens', 'Example', '2028-02-01', 1, 'It reopened.',
                          'watch', '{"year": 2028, "date_text": "February 2028", "title": "Reopened", "description": "", "kind": "reopening"}')""")
    db.commit()
    client.post("/admin/news/1/add-event", data={"csrf_token": token}, auth=ADMIN)
    client.post("/admin/news/1/apply-status", data={"csrf_token": token}, auth=ADMIN)
    event = db.execute("SELECT * FROM events WHERE origin = 'news'").fetchone()
    assert event["title"] == "Reopened" and event["source_url"] == "https://news.example/a"
    site = db.execute("SELECT risk_status FROM sites WHERE slug = 'sunbeam'").fetchone()
    assert site["risk_status"] == "watch"
    assert db.execute("SELECT state FROM news_items WHERE id = 1").fetchone()[0] == "added"


def test_csrf_cookie_is_http_only(client):
    response = client.get("/site/sunbeam/memories/new")
    cookie = response.headers.get("set-cookie", "")
    assert CSRF_COOKIE in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie


def test_interactive_map_and_preservation_passport(client):
    home = client.get("/")
    assert home.status_code == 200
    assert 'id="heritage-map"' in home.text
    assert '"slug": "sunbeam"' in home.text

    archive = client.get("/archive")
    assert archive.status_code == 200
    assert 'id="heritage-map"' in archive.text

    passport = client.get("/site/sunbeam/passport.json")
    assert passport.status_code == 200
    data = passport.json()
    assert data["schema"] == "save-heritage-passport/v1"
    assert data["slug"] == "sunbeam"
    assert data["wikidata_qid"] == "Q2113185"
    assert data["risk"]["status"] == "critical"
    assert len(data["preservation_actions"]) >= 1


