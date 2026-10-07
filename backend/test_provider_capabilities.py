"""
Tests for the provider capability drift check.

The point of the module is that two providers reached this studio which could
not render anything, and both were discovered by spending a founder's money
rather than by reading a listing. Both failures were visible in the free,
unauthenticated model list beforehand, so these tests pin the comparisons that
would have surfaced them.

compare_catalog_to_live is pure: every case here runs against a fixture, never
the network. Only the fetch wrapper touches OpenRouter, and it is asserted to
return None rather than raise so a boot is never blocked by it.
"""
import asyncio

import pytest

import provider_capabilities as pc
import video_providers as vp


def _healthy_records() -> dict:
    """
    A live record per studio-eligible model, all currently matching.

    compare_catalog_to_live walks every eligible model, so a fixture supplying
    only one of them would report the others as withdrawn and drown the case
    under test. Tests override exactly the one model they are about.
    """
    return {
        "minimax/hailuo-3": {
            "id": "minimax/hailuo-3",
            "supported_resolutions": ["2K"],
            "supported_durations": list(range(5, 16)),
            "supported_frame_images": ["first_frame", "last_frame"],
            "generate_audio": True,
            "allowed_passthrough_parameters": ["aigc_watermark"],
        },
        "minimax/hailuo-3-max": {
            "id": "minimax/hailuo-3-max",
            "supported_resolutions": ["768p", "480p"],
            "supported_durations": list(range(5, 16)),
            "supported_frame_images": ["first_frame", "last_frame"],
            "generate_audio": False,
            "allowed_passthrough_parameters": ["aigc_watermark"],
        },
        "x-ai/grok-imagine-video": {
            "id": "x-ai/grok-imagine-video",
            "supported_resolutions": ["480p", "720p"],
            "supported_durations": list(range(1, 16)),
            "supported_frame_images": ["first_frame"],
            "generate_audio": None,
            "allowed_passthrough_parameters": [],
        },
        "x-ai/grok-imagine-video-1.5-lite": {
            "id": "x-ai/grok-imagine-video-1.5-lite",
            "supported_resolutions": ["480p", "720p", "1080p"],
            "supported_durations": list(range(1, 16)),
            "supported_frame_images": ["first_frame"],
            "generate_audio": None,
            "allowed_passthrough_parameters": [],
        },
    }


def _live(**overrides) -> dict:
    """Healthy fixture with one model's fields overridden."""
    live = _healthy_records()
    live["x-ai/grok-imagine-video"].update(overrides)
    return live


class TestCompareCatalogToLive:
    def test_a_matching_provider_produces_no_warning(self):
        """
        The control case, and the one that decides whether anyone trusts this:
        a check that fires on a healthy catalog is a check nobody reads.
        """
        assert pc.compare_catalog_to_live(_healthy_records()) == []

    def test_a_known_optional_passthrough_is_not_reported(self):
        """
        aigc_watermark has been advertised by both Hailuo entries all along and
        is never sent; both render fine. Reporting it every boot would mark the
        two working models as broken and train everyone to ignore the output.
        """
        assert "aigc_watermark" in pc._KNOWN_OPTIONAL_PASSTHROUGH
        assert pc.compare_catalog_to_live(_healthy_records()) == []

    def test_an_unlisted_resolution_is_reported(self):
        """
        The expensive one: an unlisted resolution 400s on every attempt, so the
        founder pays for the attempt and gets nothing.
        """
        problems = pc.compare_catalog_to_live(_live(supported_resolutions=["480p"]))
        assert any("720p" in p and "grok" in p for p in problems)

    def test_a_withdrawn_model_is_reported(self):
        """
        A provider quietly retiring a model is the case nothing else catches:
        it stays selectable in the dropdown and every render is refused.
        """
        live = _healthy_records()
        del live["x-ai/grok-imagine-video"]
        problems = pc.compare_catalog_to_live(live)
        assert any("no longer listed" in p for p in problems)

    def test_a_withdrawn_lite_model_is_reported(self):
        """
        Same retirement tripwire for the fourth entry: withdrawing the lite
        model must name it, not pass silent because the sibling still matches.
        """
        live = _healthy_records()
        del live["x-ai/grok-imagine-video-1.5-lite"]
        problems = pc.compare_catalog_to_live(live)
        assert any("1.5-lite" in p and "no longer listed" in p for p in problems)

    def test_empty_durations_is_reported(self):
        """
        This is the Avatar IV signature. Its listing declared NO supported
        durations, which is what a text-driven-only provider looks like from
        here -- and the studio always renders from the approved script, so such a
        model can never work.
        """
        problems = pc.compare_catalog_to_live(_live(supported_durations=[]))
        assert any("NO supported durations" in p for p in problems)

    def test_a_first_frame_we_send_to_a_model_with_none_is_reported(self):
        """
        The Hailuo 3 Max failure in a different field: OpenRouter listed the
        field, the provider refused it live, and the only evidence was a 400.
        """
        problems = pc.compare_catalog_to_live(_live(supported_frame_images=[]))
        assert any("first_frame" in p for p in problems)

    def test_a_duration_beyond_the_provider_ceiling_is_reported(self):
        live = _healthy_records()
        live["x-ai/grok-imagine-video"]["supported_durations"] = list(range(1, 11))
        problems = pc.compare_catalog_to_live(live)
        assert any("longest is 10s" in p for p in problems)

    def test_claiming_audio_the_provider_does_not_list_is_reported(self):
        """
        generate_audio is null when the field is not accepted at all. Our Grok
        entry correctly declares supports_native_audio False, so the matching
        case is silent -- and a model that DID list audio while we claimed it
        could not happen here, because we never send the field for Grok.
        """
        # Consistent: provider says unlisted, catalog declines audio.
        assert pc.compare_catalog_to_live(_live(generate_audio=None)) == []
        # Also consistent: provider starts accepting audio, we still decline,
        # so the studio keeps omitting the field and nothing breaks.
        assert pc.compare_catalog_to_live(_live(generate_audio=True)) == []

    def test_a_new_required_passthrough_is_reported(self):
        """
        The one free warning available against the Avatar IV shape: a parameter
        the studio does not send appearing in the allowed list.
        """
        problems = pc.compare_catalog_to_live(
            _live(allowed_passthrough_parameters=["voice_id"])
        )
        assert any("voice_id" in p for p in problems)


class TestFetchIsNeverFatal:
    def test_a_network_failure_returns_none_rather_than_raising(self, monkeypatch):
        """
        This runs on the boot path. A DNS failure or a hung provider must not be
        able to delay or take down startup, and must not be reported as drift.
        """

        class Boom:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url):
                raise OSError("network unreachable")

        monkeypatch.setattr(pc.httpx, "AsyncClient", lambda **k: Boom())
        assert asyncio.run(pc.fetch_live_models()) is None
        assert asyncio.run(pc.check_provider_drift()) == []

    def test_a_non_200_returns_none(self, monkeypatch):
        class Resp:
            status_code = 503

        class Client:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def get(self, url):
                return Resp()

        monkeypatch.setattr(pc.httpx, "AsyncClient", lambda **k: Client())
        assert asyncio.run(pc.fetch_live_models()) is None


class TestCatalogIsSelfConsistent:
    def test_every_studio_model_has_capability_notes(self):
        """
        A key in STUDIO_ELIGIBLE with no notes falls back to _FALLBACK_NOTES,
        which is deliberately conservative and would understate the model.
        """
        for key in vp.STUDIO_ELIGIBLE:
            assert key in vp._CAPABILITY_NOTES, f"{key} has no capability notes"

    def test_the_live_endpoint_is_reachable_without_a_key(self):
        """
        The whole premise of the check: it must cost nothing to run and need no
        credential, or it would not run on every boot.
        """
        assert pc._MODELS_URL.endswith("/v1/videos/models")
        assert "openrouter.ai" in pc._MODELS_URL
        # No Authorization header is constructed anywhere in the module.
        source = open(pc.__file__, encoding="utf-8").read()
        assert "Authorization" not in source
        assert "OPENROUTER_API_KEY" not in source