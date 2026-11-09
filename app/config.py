"""Application settings, loaded from environment variables and an optional .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    # --- AI (Google Gemini) ---
    gemini_api_key: str = Field(default="", validation_alias=AliasChoices("GEMINI_API_KEY", "GOOGLE_API_KEY"))
    gemini_model: str = "gemini-2.5-flash"
    gemini_image_model: str = "gemini-2.5-flash-image"
    # Adds a Google Search grounded research step so facts can cite web pages beyond the submitted URL.
    use_search_grounding: bool = True

    # --- Maps & open data ---
    google_maps_api_key: str = ""
    europeana_api_key: str = ""
    sketchfab_enabled: bool = True
    news_provider: Literal["google_news", "gdelt", "none"] = "google_news"
    http_user_agent: str = "SAVE-Heritage/1.0 (+https://github.com/fur1aa/Preservation-Platform)"

    # --- Curator access ---
    admin_username: str = "admin"
    admin_password: str = ""

    # --- Storage ---
    data_dir: Path = BASE_DIR / "data"

    # --- Abuse protection ---
    public_generation: bool = True
    generation_rate_per_hour: int = 5
    contribution_rate_per_hour: int = 20
    trust_proxy_headers: bool = False
    # Only for local development/tests: lets /generate fetch localhost and private network URLs.
    allow_private_urls: bool = False

    # --- Upload limits (megabytes) ---
    max_photo_mb: int = 15
    max_audio_mb: int = 20
    max_scan_mb: int = 300
    max_video_mb: int = 50

    seed_demo: bool = True

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def admin_enabled(self) -> bool:
        return bool(self.admin_password)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "save.db"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
