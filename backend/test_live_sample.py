"""The live sample never runs without explicit consent."""

import os

import live_sample


def test_refuses_without_consent(monkeypatch, tmp_path):
    monkeypatch.delenv("ALLOW_LIVE_SAMPLE", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "funded-key")
    photo = tmp_path / "face.png"
    photo.write_bytes(b"not-a-photo")
    assert live_sample.main(["--photo", str(photo), "--out", str(tmp_path / "out")]) == 2


def test_refuses_without_funded_key(monkeypatch, tmp_path):
    monkeypatch.setenv("ALLOW_LIVE_SAMPLE", "1")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    photo = tmp_path / "face.png"
    photo.write_bytes(b"not-a-photo")
    assert live_sample.main(["--photo", str(photo), "--out", str(tmp_path / "out")]) == 2
