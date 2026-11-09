import pytest

from app.security import (
    UnsafeURLError,
    contrast_ratio,
    embed_for_url,
    is_http_url,
    sanitize_theme,
    slugify,
    sniff_audio,
    sniff_image,
    sniff_scan,
    validate_public_url,
)
from tests.conftest import PNG_1PX


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://example.com/",
    "http://localhost:8080/",
    "http://127.0.0.1/",
    "http://10.0.0.5/admin",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/",
    "http://user:pass@93.184.216.34/",
    "javascript:alert(1)",
    "https:///no-host",
])
def test_rejects_unsafe_urls(url):
    with pytest.raises(UnsafeURLError):
        validate_public_url(url)


def test_accepts_public_ip_and_private_when_allowed():
    assert validate_public_url("http://93.184.216.34/page") == "http://93.184.216.34/page"
    assert validate_public_url("http://127.0.0.1:9000/", allow_private=True)


@pytest.mark.parametrize("title, slug", [
    ("Sunbeam Theatre", "sunbeam-theatre"),
    ("AC/DC Hall #1?", "ac-dc-hall-1"),
    ("O'Brien's Pub", "obriens-pub"),
    ("Большой театр", "большой-театр"),
    ("新光戲院", "新光戲院"),
    ("///", "site"),
])
def test_slugify(title, slug):
    assert slugify(title) == slug


def test_theme_rejects_css_injection_and_unreadable_text():
    theme = sanitize_theme({"bg": "red; } body { display:none", "text_cream": "#F0EAD6"})
    assert theme["bg"] == "#1A0A0A"
    unreadable = sanitize_theme({"bg": "#111111", "card_bg": "#151515", "text_cream": "#222222"})
    assert contrast_ratio(unreadable["text_cream"], unreadable["bg"]) >= 4.5


@pytest.mark.parametrize("url, embed, provider", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", "youtube"),
    ("https://youtu.be/dQw4w9WgXcQ?t=3", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", "youtube"),
    ("https://sketchfab.com/3d-models/sunbeam-theatre-interior-3b40c02416bf4a09854ab9ee25a3b6bd",
     "https://sketchfab.com/models/3b40c02416bf4a09854ab9ee25a3b6bd/embed", "sketchfab"),
    ("https://archive.org/details/cantonese_opera_1960", "https://archive.org/embed/cantonese_opera_1960", "archive.org"),
    ("https://vimeo.com/123456789", "https://player.vimeo.com/video/123456789", "vimeo"),
    ("https://example.com/video", "", ""),
    ("https://www.youtube.com/watch?v=\"><script>", "", ""),
])
def test_embed_urls_are_rebuilt_from_ids(url, embed, provider):
    assert embed_for_url(url) == (embed, provider)


def test_is_http_url():
    assert is_http_url("https://example.com/x")
    assert not is_http_url("javascript:alert(1)")
    assert not is_http_url("data:text/html,hi")


def test_file_sniffing():
    assert sniff_image(PNG_1PX) == ("image/png", ".png")
    assert sniff_image(b"GIF89a....") is None
    assert sniff_audio(b"\x1a\x45\xdf\xa3rest", "voice.webm") == ("audio/webm", ".webm")
    assert sniff_audio(b"OggS\x00", "x.ogg") == ("audio/ogg", ".ogg")
    assert sniff_audio(b"<html>", "x.mp3") is None
    assert sniff_scan(b"ply\nformat", "scan.ply") == ".ply"
    assert sniff_scan(b"<?php", "scan.ply") is None
    assert sniff_scan(b"\x1f\x8b", "scan.spz") == ".spz"
    assert sniff_scan(b"ply", "scan.exe") is None
