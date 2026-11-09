"""Public input resolution, translated story caching, and evidence boundaries."""
import json

from app import repo
from app.db import session
from app.services import stories, wikidata
from app.services.ai import AIError
from tests.conftest import csrf_token
import pytest


def test_languages_and_original_story(client):
    for lang, title in [('ru', 'У каждого места есть история.'), ('en', 'Every place has a story.'), ('zh', '每个地方都有故事。')]:
        page = client.get('/?lang=' + lang)
        assert page.status_code == 200 and title in page.text
        assert f'<html lang="{lang}">' in page.text
        assert 'type="text" name="url"' in page.text
        page = client.get('/site/sunbeam/story?lang=' + lang)
        assert page.status_code == 200 and 'data-chapter' in page.text
        assert 'A landmark on King' in page.text
        assert 'story-notice' in page.text
        assert 'https://en.wikipedia.org/wiki/Sunbeam_Theatre' in page.text
    assert '<html lang="en">' in client.get('/?lang=bad').text


def test_name_input_requires_explicit_choice(client, monkeypatch):
    calls = []
    def search(client, query, lang):
        calls.append((query, lang))
        return [{'qid': 'Q123', 'label': 'Большой театр', 'description': 'Москва', 'url': 'https://ru.wikipedia.org/wiki/Большой_театр'}]
    monkeypatch.setattr(wikidata, 'search_places', search)
    token = csrf_token(client, '/?lang=ru')
    response = client.post('/generate?lang=ru', data={'url': ' Большой театр ', 'lang': 'ru', 'csrf_token': token})
    assert response.status_code == 200
    assert 'Какое место вы имели в виду?' in response.text
    assert 'Москва' in response.text
    assert calls == [('Большой театр', 'ru')]


def test_search_empty_and_unavailable(client, monkeypatch):
    token = csrf_token(client, '/')
    monkeypatch.setattr(wikidata, 'search_places', lambda *args: [])
    response = client.post('/generate', data={'url': 'Unknown place', 'csrf_token': token})
    assert 'No places with a Wikipedia article found' in response.text
    import httpx
    def fail(*args):
        raise httpx.ConnectError('offline')
    monkeypatch.setattr(wikidata, 'search_places', fail)
    assert client.post('/generate', data={'url': 'Museum', 'csrf_token': token}).status_code == 503
    assert client.post('/generate', data={'url': 'x', 'csrf_token': token}).status_code == 400


def test_generated_story_redirect_preserves_language(client, monkeypatch):
    monkeypatch.setattr(stories, 'generate_story', lambda ctx, url, lang: {'site_slug': 'sunbeam', 'story': True, 'lang': lang})
    token = csrf_token(client, '/')
    response = client.post('/generate?lang=zh', data={'url': 'https://en.wikipedia.org/wiki/Sunbeam_Theatre', 'lang': 'zh', 'csrf_token': token})
    assert response.status_code == 200
    assert '/site/sunbeam/story?lang=zh' in response.text


def test_cache_and_invalidation(client, settings, monkeypatch):
    deck = stories.Story(title='Театр', chapters=[stories.Chapter(title='Начало', content='История театра.', source_refs=[1])])
    translated = stories.TranslatedStories(en=deck, ru=deck, zh=deck)
    monkeypatch.setattr(stories.GeminiAI, '_json', lambda *args: translated)
    class Context:
        def step(self, label): pass
    ctx = Context()
    ctx.settings = settings
    result = stories.prepare_stories(ctx, 1, 'ru')
    assert result['story']
    page = client.get('/site/sunbeam/story?lang=ru')
    assert 'История театра.' in page.text and 'story-notice' not in page.text
    with session(settings.db_path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM stories').fetchone()[0] == 3
        conn.execute("UPDATE sources SET title='Updated evidence' WHERE site_id=1 AND ref=1")
    page = client.get('/site/sunbeam/story?lang=ru')
    assert 'story-notice' in page.text and 'История театра.' not in page.text


def test_unknown_references_do_not_publish_translations(client, settings, monkeypatch):
    deck = stories.Story(title='Bad', chapters=[stories.Chapter(title='Bad', content='Unsupported', source_refs=[9999])])
    monkeypatch.setattr(stories.GeminiAI, '_json', lambda *args: stories.TranslatedStories(en=deck, ru=deck, zh=deck))
    class Context:
        def step(self, label): pass
    ctx = Context()
    ctx.settings = settings
    with pytest.raises(AIError):
        stories.prepare_stories(ctx, 1, 'ru')
    with session(settings.db_path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM stories').fetchone()[0] == 0


def test_unpublished_story_and_generation_permissions(client, db, settings):
    token = csrf_token(client, '/')
    assert client.post('/site/sunbeam/story', data={'csrf_token': token}).status_code == 503
    settings.public_generation = False
    assert client.post('/generate', data={'url': 'Museum', 'csrf_token': token}).status_code == 403
    assert client.post('/site/sunbeam/story', data={'csrf_token': token}).status_code == 403
    db.execute('UPDATE sites SET is_published=0 WHERE id=1')
    db.commit()
    assert client.get('/site/sunbeam/story').status_code == 404


def test_search_uses_name_script_and_encodes_titles(monkeypatch):
    seen = []
    monkeypatch.setattr(wikidata, 'search_items', lambda client, query, lang, limit: seen.append(lang) or [{'qid': 'Q1', 'label': 'Theatre', 'description': ''}])
    monkeypatch.setattr(wikidata, 'get_entities', lambda *args, **kwargs: {'Q1': {'labels': {}, 'sitelinks': {'ruwiki': {'title': 'Театр ? #'}}}})
    result = wikidata.search_places(None, 'Театр', 'en')
    assert seen == ['ru']
    assert '%3F' in result[0]['url'] and '%23' in result[0]['url']
