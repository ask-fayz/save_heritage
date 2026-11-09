def test_3d_unconfigured_is_not_claimed_missing_coverage(client):
    response = client.get('/site/sunbeam?lang=en')
    assert response.status_code == 200
    assert 'The 3D view is not connected yet' in response.text
    assert 'exterior-load' not in response.text
    assert '/site/sunbeam/memories/new?kind=photo&amp;lang=en' in response.text or '/site/sunbeam/memories/new?kind=photo&lang=en' in response.text


def test_maps_key_enables_lazy_view(client, settings):
    settings.google_maps_api_key = 'test-browser-maps-key'
    html = client.get('/site/sunbeam?lang=en').text
    assert 'data-key="test-browser-maps-key"' in html
    assert 'exterior-load' in html
    assert '<script src="https://maps.googleapis.com' not in html
    assert 'not a historical reconstruction' in html
