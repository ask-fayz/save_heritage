import json
import pytest
from app import repo
from app.db import session
from app.services import editions
from app.services.ai import AIError
from app.routes.public import build_timeline


def test_timeline_photo_groups_are_bounded():
    rows=[{'id':i,'year':2000} for i in range(30)]+[{'id':40+i,'year':2001} for i in range(10)]
    timeline=build_timeline([],rows,[])
    assert [len(e['item']) for e in timeline]==[3,3]


def test_editions_preserve_original_and_evidence(client,settings,monkeypatch):
    def fake(self,payload,*args):
        data=json.loads(payload)
        return editions.Translation(entries=[editions.Entry(key=k,text='Перевод '+v) for k,v in data.items()])
    monkeypatch.setattr(editions.GeminiAI,'_json',fake)
    class Ctx:
        def step(self,label):pass
    ctx=Ctx();ctx.settings=settings
    editions.prepare(ctx,1,'ru')
    with session(settings.db_path) as conn:
        original=repo.get_site(conn,1);events=repo.list_events(conn,1)
        localized, translated, missing=editions.localized(conn,original,events,'ru')
        assert not missing and localized['title'].startswith('Перевод ')
        assert original['title']=='Sunbeam Theatre'
        assert localized['content']['tour_cards'][0]['source_refs']==original['content']['tour_cards'][0]['source_refs']
        assert translated[0]['year']==events[0]['year']
        assert conn.execute('SELECT COUNT(*) FROM site_editions').fetchone()[0]==2
        original['tagline']='changed'
        assert editions.localized(conn,original,events,'ru')[2]
    assert 'Перевод Sunbeam Theatre' in client.get('/site/sunbeam?lang=ru').text


def test_partial_translation_is_not_saved(client,settings,monkeypatch):
    monkeypatch.setattr(editions.GeminiAI,'_json',lambda *a: editions.Translation(entries=[]))
    class Ctx:
        def step(self,label):pass
    ctx=Ctx();ctx.settings=settings
    with pytest.raises(AIError):editions.prepare(ctx,1)
    with session(settings.db_path) as conn:assert conn.execute('SELECT COUNT(*) FROM site_editions').fetchone()[0]==0


def test_globe_uses_local_assets(client):
    html=client.get('/').text
    assert 'data-globe' in html
    assert 'cartocdn' not in html and 'leaflet' not in html.lower()
    assert client.get('/static/vendor/land-110m.json').status_code==200
