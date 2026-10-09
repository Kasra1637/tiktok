"""Regression tests for durable face-swap assets used by video generation."""
import asyncio
import io
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image

import server


IMAGE_ID = "12345678-1234-1234-1234-123456789abc"


def _png_bytes(color=(18, 52, 86)):
    output = io.BytesIO()
    Image.new("RGB", (3, 4), color).save(output, format="PNG")
    return output.getvalue()


def _use_temporary_generated_dir(monkeypatch, tmp_path):
    generated_dir = tmp_path / "generated"
    generated_dir.mkdir()
    monkeypatch.setattr(server.pipeline, "GENERATED_DIR", generated_dir)
    return generated_dir


def _provenance_row(image_bytes):
    return {
        "id": IMAGE_ID,
        "target_image_url": "/api/media/frames/video/frame_001.jpg",
        "image_bytes": image_bytes,
    }


def test_video_generation_restores_missing_generated_asset_from_durable_backup(monkeypatch, tmp_path):
    generated_dir = _use_temporary_generated_dir(monkeypatch, tmp_path)
    durable_png = _png_bytes()

    async def fake_fetch_one(query, params):
        assert params == (IMAGE_ID,)
        return _provenance_row(durable_png)

    monkeypatch.setattr(server, "_fetch_one", fake_fetch_one)

    image_path = asyncio.run(server.require_frame_derived_image(IMAGE_ID))

    assert image_path == generated_dir / f"{IMAGE_ID}.png"
    assert image_path.read_bytes() == durable_png


def test_missing_legacy_asset_returns_actionable_expiry_error(monkeypatch, tmp_path):
    _use_temporary_generated_dir(monkeypatch, tmp_path)

    async def fake_fetch_one(query, params):
        return _provenance_row(None)

    monkeypatch.setattr(server, "_fetch_one", fake_fetch_one)

    with pytest.raises(HTTPException) as error:
        asyncio.run(server.require_frame_derived_image(IMAGE_ID))

    assert error.value.status_code == 410
    assert "generate a new face swap" in error.value.detail.lower()


def test_recovery_keeps_provenance_gate_before_restoring_local_file(monkeypatch, tmp_path):
    generated_dir = _use_temporary_generated_dir(monkeypatch, tmp_path)

    async def fake_fetch_one(query, params):
        return {
            "id": IMAGE_ID,
            "target_image_url": "/api/media/uploads/user-image.png",
            "image_bytes": _png_bytes(),
        }

    monkeypatch.setattr(server, "_fetch_one", fake_fetch_one)

    with pytest.raises(HTTPException) as error:
        asyncio.run(server.require_frame_derived_image(IMAGE_ID))

    assert error.value.status_code == 400
    assert not (generated_dir / f"{IMAGE_ID}.png").exists()


