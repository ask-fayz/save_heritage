import re
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security import rate_limiter

ADMIN = ("admin", "secret")
PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        admin_password="secret",
        gemini_api_key="",
        google_maps_api_key="",
        news_provider="none",
        sketchfab_enabled=False,
        seed_demo=True,
    )


@pytest.fixture
def client(settings):
    rate_limiter.reset()
    app = create_app(settings, synchronous_jobs=True)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db(settings):
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def csrf_token(client: TestClient, path: str, auth=None) -> str:
    response = client.get(path, auth=auth)
    assert response.status_code == 200, response.text
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)
