from tests.conftest import csrf_token, ADMIN


def test_main_experience_is_simplified(client):
    home = client.get('/explore').text
    assert 'language-menu' in home and 'lang-picker' not in home
    assert 'heritage-map-data' in home
    page = client.get('/site/sunbeam').text
    for removed in ('Virtual tour', 'AI Keeper', '3D archive', '3D scan', 'Cesium', 'data-viewer', 'splat-viewer', '#keeper', '#tour'):
        assert removed not in page
    assert 'Preservation Passport' in page and 'id="contribute"' in page
    assert 'editorial-image' in page and 'Chong Fat' in page
    assert client.get('/site/sunbeam/passport.json').status_code == 200
    for url in ('/site/sunbeam/scans/new', '/site/sunbeam/photos/1/align'):
        assert client.get(url).status_code == 404
    assert client.post('/site/sunbeam/ask').status_code == 404
    for url in ('/admin/sites/sunbeam', '/admin/moderation'):
        response = client.get(url, auth=ADMIN)
        assert response.status_code == 200
        assert '3D' not in response.text and 'Tour cameras' not in response.text


def test_video_waits_for_approval(client, db):
    token = csrf_token(client, '/site/sunbeam/media/new')
    mp4 = b'\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isommp42'
    data = {'csrf_token': token, 'title': 'Family recording', 'consent': 'yes'}
    response = client.post('/site/sunbeam/media', data=data, files={'file': ('family.mp4',mp4,'video/mp4')})
    assert response.status_code == 200 and 'waiting for review' in response.text
    item = db.execute("SELECT * FROM media WHERE kind='uploaded_video'").fetchone()
    assert item['status'] == 'pending'
    assert client.get(item['url']).status_code == 404
    assert item['url'] not in client.get('/site/sunbeam').text
    assert client.get(item['url'].replace('/media/', '/admin/media/',1),auth=ADMIN).status_code == 200
    token = csrf_token(client, '/admin/moderation', auth=ADMIN)
    client.post(f"/admin/moderate/media/{item['id']}/approve",data={'csrf_token':token},auth=ADMIN)
    assert client.get(item['url']).status_code == 200
    assert '<video controls' in client.get('/site/sunbeam').text
    db.execute('UPDATE sites SET is_published=0 WHERE id=1'); db.commit()
    assert client.get(item['url']).status_code == 404


def test_video_validation(client, settings, db):
    token = csrf_token(client, '/site/sunbeam/media/new')
    data={'csrf_token': token,'title':'Recording','consent':'yes'}
    assert client.post('/site/sunbeam/media',data=data,files={'file':('bad.mp4',b'<script>bad</script>','video/mp4')}).status_code == 400
    assert client.post('/site/sunbeam/media',data={**data,'consent':''},files={'file':('test.mp4',b'\x00\x00\x00\x18ftypisom','video/mp4')}).status_code == 400
    settings.max_video_mb=0
    assert client.post('/site/sunbeam/media',data=data,files={'file':('test.mp4',b'\x00\x00\x00\x18ftypisom','video/mp4')}).status_code in (400,413)
    assert db.execute('SELECT COUNT(*) FROM media').fetchone()[0] == 0


def test_photo_entry_selects_photo(client):
    assert 'value="photo" checked' in client.get('/site/sunbeam/memories/new?kind=photo').text


def test_passport_has_no_export_or_print_controls(client):
    page = client.get('/site/sunbeam').text
    assert 'Preservation Passport' in page
    assert 'Download JSON' not in page
    assert 'data-print-passport' not in page
    assert 'window.print' not in client.get('/static/js/site.js').text
