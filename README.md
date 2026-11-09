# SAVE Heritage

**Smart Archive for Virtual Exploration of Heritage.**

Wikipedia tells you *what* a place is. SAVE Heritage shows **how it looked, what it means to people, and what we
could lose**, with every statement linked to its source.

Paste a link to an article about a heritage site. SAVE links it to Wikidata, reads Wikipedia in the local languages,
searches the web for recent news, and builds a cited record. On top of that record sit three layers:

| Layer | What it adds | Where it comes from |
|---|---|---|
| **01 · Time** | Chronicle of changes, dated photographs, "windows to the past" (old photos aligned with today's 3D view) | Wikidata, AI extraction with citations, Wikimedia Commons, Europeana, community alignment |
| **02 · People** | Stories, family photos and voice recordings; transcribed and translated | Visitors, moderated by curators; Gemini for transcription/translation/dating |
| **03 · Risk** | Status (stable → lost), reasons, news monitoring, curator-confirmed changes | Sources + Google News / GDELT, triaged by Gemini |

### Honest 3D

We don't generate buildings from nothing. Each 3D layer states how much it can be trusted:

| Level | Source | Confidence |
|---|---|---|
| Today, outside | Google Photorealistic 3D Tiles (CesiumJS) | High |
| Existing scans | Sketchfab (searched automatically, approved by curators) | High |
| Community scans | Gaussian splats from a 30–60 s phone video (Scaniverse, Polycam, Luma), viewed with Spark | High |
| The past | Historical photos aligned with the 3D camera | Documentary |
| Hypothesis | Gemini image model, only from documentary photos, always labelled "AI hypothesis" | Low, labelled |

The demo record, **Sunbeam Theatre** (`/site/sunbeam`), shows why the risk layer matters: the original prototype
called it "Hong Kong's last standing opera venue", but it closed in March 2025 after its building was sold.

---

## Quick start

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # add your keys, set ADMIN_PASSWORD
python main.py                       # http://127.0.0.1:8080
```

The app starts without any keys: it seeds the Sunbeam Theatre record, and new records are built from Wikidata and the
article text only. To pull archive photos, 3D scan candidates and news for the demo site:

```bash
python -m app.cli refresh sunbeam
```

Development: `uvicorn main:app --reload --port 8080`. Tests: `pip install -r requirements-dev.txt && pytest`.

## Configuration

All settings are environment variables (or `.env`). See [.env.example](.env.example).

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Enables cited extraction, web research with Google Search grounding, memory transcription/translation, photo relevance, news triage and AI hypotheses. Get one at [Google AI Studio](https://aistudio.google.com/). |
| `GEMINI_MODEL`, `GEMINI_IMAGE_MODEL` | Text and image models (defaults: `gemini-2.5-flash`, `gemini-2.5-flash-image`). |
| `USE_SEARCH_GROUNDING` | Adds the web research step (billed separately by Google). |
| `GOOGLE_MAPS_API_KEY` | Photorealistic 3D Tiles. Enable the **Map Tiles API**. The key is used in the browser: **restrict it by HTTP referrer and API**. |
| `EUROPEANA_API_KEY` | Optional second photo archive ([free key](https://pro.europeana.eu/page/get-api)). |
| `NEWS_PROVIDER` | `google_news` (RSS; Google allows it for personal, non-commercial use only), `gdelt` (free, rate limited) or `none`. Use `gdelt` for a public deployment. |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Curator area at `/admin` (HTTP Basic auth). Empty password disables it. |
| `PUBLIC_GENERATION` | If `false`, only curators can add new sites. |
| `GENERATION_RATE_PER_HOUR`, `CONTRIBUTION_RATE_PER_HOUR` | Per-IP limits. |
| `DATA_DIR` | SQLite database and uploads (default `./data`). Back this folder up. |
| `MAX_PHOTO_MB`, `MAX_AUDIO_MB`, `MAX_SCAN_MB` | Upload limits. |

Voice memories recorded in the browser (WebM/MP4) are converted to WAV for Gemini when `ffmpeg` is installed.

## How it works

```
URL ─▶ safe fetch + trafilatura ─▶ Wikidata item (coordinates, dates, protection, Commons category)
                                   └▶ Wikipedia in English + the country's official languages
      ─▶ Gemini + Google Search grounding (recent facts, real web URLs)
      ─▶ Gemini structured extraction: every card/fact/event cites [S#] sources; conflicts → "Sources disagree"
      ─▶ SQLite record ─▶ enrichment jobs: Commons/Europeana photos · Sketchfab scans · news
```

Long work runs as background jobs with a progress page (`/jobs/<id>`). Without `GEMINI_API_KEY` the pipeline builds a
**basic** record from Wikidata facts and the article's opening paragraphs.

### Curator workflow (`/admin`)

- **Moderation**: memories (with AI transcript, translation, date estimate and flags), photos, photo alignments,
  3D scans, recordings, AI hypotheses and news-proposed events. Nothing from the community is public before approval;
  uploaded files are served only after their item is approved.
- **Site editor**: risk status and reasons, coordinates, chronicle events, publishing, hidden photos, and **tour
  cameras** (preview a stop, move the 3D camera, save the view).
- **News**: add an article to the chronicle, apply the suggested risk status (the article becomes a source), or dismiss.
- **Actions**: regenerate a record (keeps curator events, photos, memories and saved cameras), find photos, find 3D
  scans, check news. Schedule news checks with cron: `python -m app.cli refresh --what news`.

### Project layout

```
main.py                 entry point (uvicorn main:app)
app/
  main.py               app factory, middleware, error pages
  config.py             settings
  schema.sql, db.py     SQLite schema and connections
  repo.py               data access
  models.py             domain models and vocabularies (risk statuses, event kinds)
  security.py           SSRF guard, CSRF, rate limiting, slugs, colour and upload validation, curator auth
  routes/               public.py · contribute.py · admin.py
  services/
    pipeline.py         generation and enrichment workflows
    ai.py               Gemini: schemas, prompts, grounding, memory/news/photo analysis, image hypotheses
    wikidata.py         Wikidata + Wikipedia
    archives.py         Wikimedia Commons + Europeana
    sketchfab.py        existing 3D scans
    news.py             Google News RSS + GDELT
    http.py, storage.py, jobs.py
  templates/, static/   Jinja templates, CSS, CesiumJS tour, Spark splat viewer, voice recorder
  seed/sunbeam.json     hand-checked demo record with sources
  cli.py                seed · refresh · import-legacy
tests/                  pytest suite (no network, Gemini faked)
```

## Upgrading from the first prototype

The prototype stored generated sites in `archive_data.json`. Import them (they have no sources yet, so regenerate
them from `/admin` afterwards):

```bash
python -m app.cli import-legacy archive_data.json
```

`/site/sunbeam` keeps its old URL.

## Deploying

- Run behind HTTPS (the CSRF cookie becomes `Secure` automatically) with a strong `ADMIN_PASSWORD`.
- Set the reverse proxy's body size limit to at least `MAX_SCAN_MB`.
- Restrict the Google Maps key by referrer; set a Gemini budget alert.
- The job runner and rate limiter are in-process: run a single worker (`uvicorn main:app --workers 1`).
- Back up `DATA_DIR`.

## Licences and attribution

- Photos from Wikimedia Commons and Europeana are shown with author, licence and a link to the source page.
- Google 3D Tiles attributions are displayed by CesiumJS, as required by Google's terms.
- Community contributions are published under the licence the contributor chooses (CC BY 4.0, CC BY-NC 4.0 or
  all rights reserved), after they confirm consent.

---

Created by House of Scholars.
