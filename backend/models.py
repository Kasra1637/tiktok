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
        # App Profile (brand_profiles) structured fields
        "support_urls", "platforms", "core_features", "primary_use_cases",
        "problems_solved", "icp_segments", "desired_outcomes", "competitors",
        "claims_approved", "claims_review", "claims_banned", "ctas",
        "video_themes", "research_sources", "pending_research",
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


class AppProfileResearchRequest(BaseModel):
    """
    Research a mobile app from its public pages and generate a draft App Profile.

    At least one URL is required. support_urls is capped server-side; notes
    are founder-supplied context passed straight to the research prompt.
    """
    website_url: Optional[str] = None
    appstore_url: Optional[str] = None
    play_url: Optional[str] = None
    support_urls: Optional[List[str]] = None
    notes: Optional[str] = ""


class ApproveAppProfileRequest(BaseModel):
    """
    Approve an App Profile. When a refresh proposal is pending, it is applied
    to the live fields by default (apply_pending=True) and the version bumps.
    Pass apply_pending=False to approve the current fields as-is and keep the
    pending proposal for later review.
    """
    apply_pending: Optional[bool] = True


# Fields shared by App Profile create/update payloads. Lists serialize to JSON
# text columns; the API accepts either a list or a comma-separated string and
# normalizes server-side.
APP_PROFILE_LIST_FIELDS = (
    "support_urls", "platforms", "core_features", "primary_use_cases",
    "problems_solved", "icp_segments", "desired_outcomes", "competitors",
    "products_services", "claims_approved", "claims_review", "claims_banned",
    "ctas", "video_themes",
)

APP_PROFILE_TEXT_FIELDS = (
    "website_url", "appstore_url", "play_url", "notes", "brand_name",
    "brand_description", "niche", "app_category", "target_audience",
    "ideal_customer_profile", "differentiation", "tone_voice",
    "pricing_trial", "known_limitations", "raw_extracted_text",
)

APP_PROFILE_EDITABLE_FIELDS = APP_PROFILE_TEXT_FIELDS + APP_PROFILE_LIST_FIELDS


class BrandProfileCreateRequest(BaseModel):
    """
    Create a brand profile from manually entered fields.

    The website-analysis path is optional — users without a scrapeable site
    (or whose site fails to fetch) need to be able to fill this in by hand.
    """
    website_url: Optional[str] = None
    brand_name: str
    brand_description: Optional[str] = ""
    niche: Optional[str] = ""
    products_services: Optional[List[str]] = None
    target_audience: Optional[str] = ""
    ideal_customer_profile: Optional[str] = ""
    differentiation: Optional[str] = ""
    tone_voice: Optional[str] = ""
    # App Profile extensions — all optional so legacy brand creation is unaffected.
    appstore_url: Optional[str] = None
    play_url: Optional[str] = None
    support_urls: Optional[List[str]] = None
    notes: Optional[str] = ""
    app_category: Optional[str] = ""
    platforms: Optional[List[str]] = None
    pricing_trial: Optional[str] = ""
    core_features: Optional[List[str]] = None
    primary_use_cases: Optional[List[str]] = None
    problems_solved: Optional[List[str]] = None
    icp_segments: Optional[List[str]] = None
    desired_outcomes: Optional[List[str]] = None
    competitors: Optional[List[str]] = None
    known_limitations: Optional[str] = ""
    claims_approved: Optional[List[str]] = None
    claims_review: Optional[List[str]] = None
    claims_banned: Optional[List[str]] = None
    ctas: Optional[List[str]] = None
    video_themes: Optional[List[str]] = None


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
    # App Profile extensions (same semantics as create).
    appstore_url: Optional[str] = None
    play_url: Optional[str] = None
    support_urls: Optional[List[str]] = None
    notes: Optional[str] = None
    app_category: Optional[str] = None
    platforms: Optional[List[str]] = None
    pricing_trial: Optional[str] = None
    core_features: Optional[List[str]] = None
    primary_use_cases: Optional[List[str]] = None
    problems_solved: Optional[List[str]] = None
    icp_segments: Optional[List[str]] = None
    desired_outcomes: Optional[List[str]] = None
    competitors: Optional[List[str]] = None
    known_limitations: Optional[str] = None
    claims_approved: Optional[List[str]] = None
    claims_review: Optional[List[str]] = None
    claims_banned: Optional[List[str]] = None
    ctas: Optional[List[str]] = None
    video_themes: Optional[List[str]] = None


class GenerateRemixScriptRequest(BaseModel):
    duration_seconds: int = 30
    use_original_sound: bool = False


class RemixChatMessageRequest(BaseModel):
    """A single user turn in the conversational remix chat for a customization."""
    message: str


class CreateHookTemplateRequest(BaseModel):
    """Save an analyzed hook as a reusable template (snapshot, no AI calls)."""
    video_id: str
    name: Optional[str] = ""
    category: Optional[str] = ""
    notes: Optional[str] = ""


class UpdateHookTemplateRequest(BaseModel):
    """Rename or recategorize a saved hook template."""
    name: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
