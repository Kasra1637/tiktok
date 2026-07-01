"""Shared helpers for Mongo document serialization and Pydantic request models."""
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize_doc(doc: dict) -> dict:
    """Recursively strip Mongo's _id and convert datetime objects to ISO strings."""
    if doc is None:
        return None
    clean = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, datetime):
            clean[k] = v.isoformat()
        elif isinstance(v, dict):
            clean[k] = serialize_doc(v)
        elif isinstance(v, list):
            clean[k] = [serialize_doc(i) if isinstance(i, dict) else i for i in v]
        else:
            clean[k] = v
    return clean


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

