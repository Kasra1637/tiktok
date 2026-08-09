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


def test_completed_face_swap_persists_backup_before_exposing_result(monkeypatch, tmp_path):
    generated_dir = _use_temporary_generated_dir(monkeypatch, tmp_path)
    provider_png = _png_bytes()

    async def fake_generate_face_swap(**kwargs):
        return provider_png

    monkeypatch.setattr(server, "generate_face_swap", fake_generate_face_swap)
    variant = asyncio.run(
        server._generate_face_swap_variant(
            target_path=Path("target.jpg"),
            source_path=Path("source.png"),
            job_id="job-1",
            variant_index=0,
        )
    )
    asset_bytes = variant["_image_bytes"]
    assert (generated_dir / f"{variant['id']}.png").read_bytes() == asset_bytes

    recorded = []
    database_writes = []

    async def fake_variant(*args, **kwargs):
        return dict(variant)

    async def fake_record(**kwargs):
        recorded.append(kwargs)

    async def fake_execute(query, params=()):
        database_writes.append((query, params))

    monkeypatch.setattr(server, "_generate_face_swap_variant", fake_variant)
    monkeypatch.setattr(server, "_record_generated_image", fake_record)
    monkeypatch.setattr(server, "_execute", fake_execute)

    asyncio.run(
        server._run_face_swap_job(
            job_id="job-1",
            target_path=Path("target.jpg"),
            source_path=Path("source.png"),
            target_image_url="/api/media/frames/video/frame_001.jpg",
            source_face_url="/api/media/uploads/source.png",
            variants=1,
            user_id="user-1",
        )
    )

    assert recorded == [
        {
            "image_id": variant["id"],
            "origin": "face_swap",
            "target_image_url": "/api/media/frames/video/frame_001.jpg",
            "user_id": "user-1",
            "job_id": "job-1",
            "image_bytes": asset_bytes,
        }
    ]
    completed_params = database_writes[-1][1]
    result = json.loads(completed_params[1])
    assert "_image_bytes" not in result["variants"][0]
    assert result["variants"][0]["id"] == variant["id"]
