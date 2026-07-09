"""Shared helpers and Pydantic request models."""
import json
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row, columns: list) -> dict:
    """Convert an sqlite3.Row to a dict, parsing JSON fields."""
    JSON_FIELDS = {
        "frames", "generation_spec", "generated_images", "prompt_breakdown",
        "reference_image_ids", "selected_image_ids", "replicable_mechanics",
        "products_services", "messages", "brief", "hashtags", "sound_reference",
    }
    d = {}
    for i, col in enumerate(columns):
        val = row[i]
        if col in JSON_FIELDS and isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
        d[col] = val
    return d


class IngestVideoRequest(BaseModel):
    tiktok_url: str
    niche: Optional[str] = None


class TrendingSearchRequest(BaseModel):
    """Parameters for keyword-based trending search with location targeting."""
    q: str
    limit: int = 20
    location: Optional[str] = None  # ISO 3166-1 alpha-2 country code (e.g., "US", "GB")
    sort_type: Optional[str] = None  # "RELEVANCE", "MOST_LIKED", "DATE_POSTED"


class MusicSearchRequest(BaseModel):
    """Parameters for music/sound-based video discovery."""
    music_url: str
    limit: int = 25


class CustomizeRequest(BaseModel):
    environment: Optional[str] = ""
    background: Optional[str] = ""
    clothing: Optional[str] = ""
    custom_instructions: Optional[str] = ""


class BrandContextRequest(BaseModel):
    brand_name: str = ""
    brand_goal: str = ""
    brand_details: str = ""
    duration_seconds: int = 30
    use_original_sound: bool = False


class GenerateVideoRequest(BaseModel):
    image_ids: List[str] = []
    edited_prompt: Optional[str] = None
    duration_seconds: Optional[int] = None


class AnalyzeBrandUrlRequest(BaseModel):
    url: str


class BrandProfileUpdateRequest(BaseModel):
    website_url: Optional[str] = None
    brand_name: Optional[str] = None
    brand_description: Optional[str] = None
    niche: Optional[str] = None
    products_services: Optional[List[str]] = None
    target_audience: Optional[str] = None
    ideal_customer_profile: Optional[str] = None
    differentiation: Optional[str] = None
    tone_voice: Optional[str] = None
    raw_extracted_text: Optional[str] = None


class GenerateRemixScriptRequest(BaseModel):
    duration_seconds: int = 30
    use_original_sound: bool = False


class RemixChatMessageRequest(BaseModel):
    """A single user turn in the conversational remix chat for a customization."""
    message: str
