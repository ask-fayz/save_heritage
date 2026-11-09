-- SAVE Heritage database schema (SQLite).
-- Every community or automatically discovered item carries a moderation `status`:
-- 'pending' until a curator reviews it, then 'approved' or 'rejected'.

CREATE TABLE IF NOT EXISTS sites (
    id                   INTEGER PRIMARY KEY,
    slug                 TEXT NOT NULL UNIQUE,
    wikidata_qid         TEXT UNIQUE,
    source_url           TEXT NOT NULL DEFAULT '',
    title                TEXT NOT NULL,
    native_name          TEXT NOT NULL DEFAULT '',
    location_label       TEXT NOT NULL DEFAULT '',
    tagline              TEXT NOT NULL DEFAULT '',
    latitude             REAL,
    longitude            REAL,
    coord_source         TEXT NOT NULL DEFAULT 'none',      -- wikidata | ai | manual | none
    facts_json           TEXT NOT NULL DEFAULT '{}',        -- structured facts from Wikidata
    content_json         TEXT NOT NULL DEFAULT '{}',        -- tour cards, culture, glossary, ... (SiteContent)
    theme_json           TEXT NOT NULL DEFAULT '{}',
    risk_status          TEXT NOT NULL DEFAULT 'unknown',
    risk_reasons_json    TEXT NOT NULL DEFAULT '[]',
    risk_summary         TEXT NOT NULL DEFAULT '',
    risk_source_refs_json TEXT NOT NULL DEFAULT '[]',
    risk_updated_at      TEXT,
    language             TEXT NOT NULL DEFAULT 'en',        -- en | ru | zh
    generation_mode      TEXT NOT NULL DEFAULT 'ai',        -- ai | basic | manual | legacy
    is_published         INTEGER NOT NULL DEFAULT 1,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Numbered references shown next to facts as [1], [2], ...
CREATE TABLE IF NOT EXISTS sources (
    id           INTEGER PRIMARY KEY,
    site_id      INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    ref          INTEGER NOT NULL,
    kind         TEXT NOT NULL,          -- submitted_url | wikipedia | wikidata | web | news | other
    title        TEXT NOT NULL DEFAULT '',
    url          TEXT NOT NULL DEFAULT '',
    language     TEXT NOT NULL DEFAULT '',
    retrieved_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (site_id, ref)
);

-- Chronicle: what happened to the place over time.
CREATE TABLE IF NOT EXISTS events (
    id               INTEGER PRIMARY KEY,
    site_id          INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    year             INTEGER,
    date_text        TEXT NOT NULL DEFAULT '',
    title            TEXT NOT NULL,
    description      TEXT NOT NULL DEFAULT '',
    kind             TEXT NOT NULL DEFAULT 'other',
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    source_url       TEXT NOT NULL DEFAULT '',
    source_title     TEXT NOT NULL DEFAULT '',
    origin           TEXT NOT NULL DEFAULT 'ai',   -- ai | wikidata | news | curator | seed
    status           TEXT NOT NULL DEFAULT 'approved',
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Historical and community photographs ("Through time" layer).
CREATE TABLE IF NOT EXISTS photos (
    id              INTEGER PRIMARY KEY,
    site_id         INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL,        -- commons | europeana | community | curator
    provider_id     TEXT NOT NULL,
    title           TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    author          TEXT NOT NULL DEFAULT '',
    license         TEXT NOT NULL DEFAULT '',
    license_url     TEXT NOT NULL DEFAULT '',
    source_page_url TEXT NOT NULL DEFAULT '',
    image_url       TEXT NOT NULL DEFAULT '',
    thumb_url       TEXT NOT NULL DEFAULT '',
    width           INTEGER,
    height          INTEGER,
    year            INTEGER,
    date_text       TEXT NOT NULL DEFAULT '',
    year_source     TEXT NOT NULL DEFAULT '',   -- metadata | ai_estimate | contributor
    latitude        REAL,
    longitude       REAL,
    pose_json       TEXT,                       -- camera pose for the "window to the past" overlay
    relevance_note  TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (site_id, provider, provider_id)
);

-- Community suggestions for aligning a photo with the 3D view.
CREATE TABLE IF NOT EXISTS pose_suggestions (
    id          INTEGER PRIMARY KEY,
    photo_id    INTEGER NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
    pose_json   TEXT NOT NULL,
    author_name TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Living memory: stories, family photos and voice recordings from people.
CREATE TABLE IF NOT EXISTS memories (
    id                   INTEGER PRIMARY KEY,
    site_id              INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    kind                 TEXT NOT NULL,             -- story | photo | audio
    author_name          TEXT NOT NULL DEFAULT '',
    text_original        TEXT NOT NULL DEFAULT '',
    language             TEXT NOT NULL DEFAULT '',
    text_en              TEXT NOT NULL DEFAULT '',
    transcript           TEXT NOT NULL DEFAULT '',
    summary              TEXT NOT NULL DEFAULT '',
    photo_description    TEXT NOT NULL DEFAULT '',
    file_path            TEXT NOT NULL DEFAULT '',  -- relative to uploads dir
    mime_type            TEXT NOT NULL DEFAULT '',
    year_given           INTEGER,
    year_estimate        INTEGER,
    year_estimate_reason TEXT NOT NULL DEFAULT '',
    tags_json            TEXT NOT NULL DEFAULT '[]',
    moderation_flags_json TEXT NOT NULL DEFAULT '[]',
    license              TEXT NOT NULL DEFAULT 'CC BY 4.0',
    ai_status            TEXT NOT NULL DEFAULT 'pending',  -- pending | done | failed | skipped
    ai_error             TEXT NOT NULL DEFAULT '',
    status               TEXT NOT NULL DEFAULT 'pending',
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Recordings and links about intangible heritage (performances, interviews, crafts).
CREATE TABLE IF NOT EXISTS media (
    id           INTEGER PRIMARY KEY,
    site_id      INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL DEFAULT 'video',   -- video | audio | link
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    embed_url    TEXT NOT NULL DEFAULT '',
    year         INTEGER,
    description  TEXT NOT NULL DEFAULT '',
    submitted_by TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 3D: existing scans (Sketchfab), community Gaussian splats and external captures.
CREATE TABLE IF NOT EXISTS scans (
    id           INTEGER PRIMARY KEY,
    site_id      INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,           -- splat_file | embed | external_link
    provider     TEXT NOT NULL,           -- community | sketchfab | curator
    provider_id  TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    author       TEXT NOT NULL DEFAULT '',
    license      TEXT NOT NULL DEFAULT '',
    url          TEXT NOT NULL DEFAULT '',
    embed_url    TEXT NOT NULL DEFAULT '',
    thumb_url    TEXT NOT NULL DEFAULT '',
    file_path    TEXT NOT NULL DEFAULT '',
    capture_date TEXT NOT NULL DEFAULT '',
    notes        TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'pending',
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (site_id, provider, provider_id)
);

-- Clearly labelled AI hypotheses (lowest level of the 3D confidence ladder).
CREATE TABLE IF NOT EXISTS reconstructions (
    id                  INTEGER PRIMARY KEY,
    site_id             INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    image_path          TEXT NOT NULL,
    focus               TEXT NOT NULL DEFAULT '',
    target_year         INTEGER,
    prompt              TEXT NOT NULL DEFAULT '',
    input_photo_ids_json TEXT NOT NULL DEFAULT '[]',
    model               TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL DEFAULT 'pending',
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- News monitoring for the "Heritage at risk" layer.
CREATE TABLE IF NOT EXISTS news_items (
    id                  INTEGER PRIMARY KEY,
    site_id             INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    url                 TEXT NOT NULL,
    title               TEXT NOT NULL,
    source_name         TEXT NOT NULL DEFAULT '',
    published_at        TEXT NOT NULL DEFAULT '',
    ai_relevant         INTEGER,
    ai_summary          TEXT NOT NULL DEFAULT '',
    ai_threat_level     TEXT NOT NULL DEFAULT '',
    ai_suggested_status TEXT NOT NULL DEFAULT '',
    ai_event_json       TEXT,
    state               TEXT NOT NULL DEFAULT 'new',   -- new | added | dismissed
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (site_id, url)
);

CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL,
    site_id       INTEGER REFERENCES sites(id) ON DELETE SET NULL,
    input_json    TEXT NOT NULL DEFAULT '{}',
    status        TEXT NOT NULL DEFAULT 'queued',   -- queued | running | done | failed
    steps_json    TEXT NOT NULL DEFAULT '[]',
    result_json   TEXT NOT NULL DEFAULT '{}',
    error         TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_events_site ON events(site_id, status);
CREATE INDEX IF NOT EXISTS idx_photos_site ON photos(site_id, status);
CREATE INDEX IF NOT EXISTS idx_memories_site ON memories(site_id, status);
CREATE INDEX IF NOT EXISTS idx_media_site ON media(site_id, status);
CREATE INDEX IF NOT EXISTS idx_scans_site ON scans(site_id, status);
CREATE INDEX IF NOT EXISTS idx_news_site ON news_items(site_id, state);

-- Cached stories are separate from canonical records and invalidated when their evidence changes.
CREATE TABLE IF NOT EXISTS stories (
    site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    language TEXT NOT NULL CHECK(language IN ('en', 'ru', 'zh')),
    fingerprint TEXT NOT NULL,
    content_json TEXT NOT NULL,
    PRIMARY KEY(site_id, language)
);

CREATE TABLE IF NOT EXISTS site_editions (
    site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    language TEXT NOT NULL CHECK(language IN ('en','ru','zh')),
    fingerprint TEXT NOT NULL,
    text_json TEXT NOT NULL,
    PRIMARY KEY(site_id,language)
);
