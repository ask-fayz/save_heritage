import pytest


@pytest.mark.parametrize("lang", ["en", "ru", "zh"])
def test_entry_flow_preserves_language(client, lang):
    home = client.get(f"/?lang={lang}")
    assert home.status_code == 200
    assert f'<html lang="{lang}">' in home.text
    assert f'href="/explore?lang={lang}"' in home.text
    assert 'save-heritage-original.png' in home.text
    explore = client.get(f"/explore?lang={lang}")
    assert explore.status_code == 200 and 'name="csrf_token"' in explore.text
    for path in ("/", "/explore", "/archive", "/team"):
        page = client.get(f"{path}?lang={lang}").text
        assert 'class="language-menu"' in page
        assert f'href="/team?lang={lang}"' in page
        assert '♡' in page
    team = client.get(f"/team?lang={lang}").text
    for name in ("Askar Fayzullin", "Chan Jessica Yin-Yu", "Yoshida Emi"):
        assert name in team
    assert 'https://sa.hkbu.edu.hk/en/lqc/leadership-development/House-of-Scholars.html' in team
    for image in ('askar.jpg', 'jessica.jpg', 'emi.jpg', 'save-heritage-original.png'):
        assert client.get('/static/images/' + image).status_code == 200
