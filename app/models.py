"""Domain models and vocabularies shared by the pipeline, the database layer and templates."""

from typing import Literal

from pydantic import BaseModel, Field

RiskStatus = Literal["unknown", "stable", "watch", "at_risk", "critical", "lost"]
SiteLanguage = Literal["en", "ru", "zh"]

SUPPORTED_LANGUAGES: dict[str, dict[str, str]] = {
    "en": {"label": "English", "short": "EN", "speech_lang": "en-US", "wiki": "en"},
    "ru": {"label": "Русский", "short": "RU", "speech_lang": "ru-RU", "wiki": "ru"},
    "zh": {"label": "中文", "short": "中文", "speech_lang": "zh-CN", "wiki": "zh"},
}

RISK_STATUSES: dict[str, dict[str, str]] = {
    "unknown": {"label": "Not assessed", "description": "No reliable information about threats yet."},
    "stable": {"label": "Stable", "description": "Protected, maintained and in use."},
    "watch": {"label": "Watch", "description": "Early warning signs: ownership changes, disputes, neglect."},
    "at_risk": {"label": "At risk", "description": "A concrete threat: planned redevelopment, lease expiry, damage."},
    "critical": {"label": "Critical", "description": "Loss is imminent or already under way."},
    "lost": {"label": "Lost or closed", "description": "Demolished, destroyed, or its heritage use has ended."},
}

RISK_REASONS: dict[str, str] = {
    "demolition": "Demolition or redevelopment",
    "ownership": "Ownership change or lease expiry",
    "neglect": "Neglect and decay",
    "funding": "Lack of funding or audiences",
    "climate": "Climate and natural hazards",
    "disaster": "Fire, flood or other disaster",
    "conflict": "Armed conflict or vandalism",
    "tourism": "Tourism pressure",
    "policy": "Loss of legal protection",
    "knowledge": "Loss of practitioners or know-how",
    "other": "Other",
}

EVENT_KINDS: dict[str, str] = {
    "built": "Built",
    "opened": "Opened",
    "designation": "Protection status",
    "alteration": "Alteration",
    "restoration": "Restoration",
    "damage": "Damage",
    "change_of_use": "Change of use",
    "ownership": "Ownership",
    "threat": "Threat",
    "closure": "Closure",
    "reopening": "Reopening",
    "demolition": "Demolition",
    "cultural": "Cultural moment",
    "other": "Other",
}

MODERATION_STATUSES = ("pending", "approved", "rejected")


class OrbitCamera(BaseModel):
    """Camera orbiting the site's coordinates. Used before a curator saves an exact pose."""

    heading: float = 0.0
    pitch: float = -30.0
    range: float = 300.0


class Pose(BaseModel):
    """Absolute camera pose in degrees/metres, as captured from the 3D viewer."""

    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    height: float = Field(ge=-500, le=100000)
    heading: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0
    fov: float = Field(default=60.0, ge=5, le=120)
    aspect: float | None = Field(default=None, ge=0.2, le=5)


class Card(BaseModel):
    title: str
    content: str
    source_refs: list[int] = []
    camera: OrbitCamera | None = None
    pose: Pose | None = None


class Fact(BaseModel):
    text: str
    source_refs: list[int] = []


class GlossaryTerm(BaseModel):
    term: str
    original: str = ""
    definition: str
    source_refs: list[int] = []


class Practitioner(BaseModel):
    name: str
    role: str = ""
    description: str = ""
    source_refs: list[int] = []


class DisputedVersion(BaseModel):
    claim: str
    source_refs: list[int] = []


class DisputedPoint(BaseModel):
    topic: str
    versions: list[DisputedVersion] = []


class SiteContent(BaseModel):
    tour_cards: list[Card] = []
    culture_title: str = ""
    culture_subtitle: str = ""
    culture_cards: list[Card] = []
    quick_facts: list[Fact] = []
    did_you_know: Fact | None = None
    glossary: list[GlossaryTerm] = []
    practitioners: list[Practitioner] = []
    disputed_points: list[DisputedPoint] = []
    protection_level: str = ""
    preservation_actions: list[Card] = []


class Theme(BaseModel):
    bg: str = "#1A0A0A"
    bg_darker: str = "#0D0505"
    accent_red: str = "#C8102E"
    accent_gold: str = "#D4A843"
    text_cream: str = "#F0EAD6"
    card_bg: str = "#2A1010"
    border_color: str = "#3D1515"


DEFAULT_TOUR_CAMERAS = [
    OrbitCamera(heading=20, pitch=-35, range=420),
    OrbitCamera(heading=110, pitch=-25, range=260),
    OrbitCamera(heading=200, pitch=-45, range=180),
    OrbitCamera(heading=290, pitch=-30, range=320),
    OrbitCamera(heading=340, pitch=-55, range=500),
    OrbitCamera(heading=60, pitch=-20, range=220),
]
