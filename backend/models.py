"""Shared helpers and Pydantic request models."""
import json
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row, columns: list) -> dict:
    """Convert an sqlite3.Row to a dict, parsing JSON fields."""
    JSON_FIELDS = {"frames", "generation_spec", "generated_images", "prompt_breakdown", "reference_image_ids", "selected_image_ids", "replicable_mechanics"}
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


class GenerateVideoRequest(BaseModel):
    image_ids: List[str] = []
    edited_prompt: Optional[str] = None
    duration_seconds: Optional[int] = None
