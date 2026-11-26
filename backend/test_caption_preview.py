"""The HookSnap caption preview's generator (ADR 0353).

The claims under test:
  * The preview is ONE caption written from the hook line — the
    project's script, when the row carries one, never reaches the
    prompt: the preview is grounded in the hook alone, because on
    HookSnap the hook is the whole spoken piece.
  * The caption carries the post kit's own rules (ADR 0100 as
    amended): 50 to 80 characters including the final '?', ending
    in its question, no content word twice (ADR 0346). A reply
    outside the rules fails loudly — the preview never repairs a
    bad caption into a plausible one.
  * A project with no hook line has nothing to preview from.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_service

CAPTION = "I quit replaying the whole day in my head and said it out loud instead — you?"
assert 50 <= len(CAPTION) <= 80 and CAPTION.endswith("?")

HOOK = "I'm trying to clear my head before bed but my thoughts race."
SCRIPT_MARKER = "SCRIPTONLYMARKER the middle nobody should read"

PROJECT = {
    "hook_line": HOOK,
    "script": SCRIPT_MARKER,
    "cta": "Speak one entry tonight.",
    "objective": "address_user_problem",
    "audience": "people too tired to write at night",
}
PROFILE = {
    "id": "app-1",
    "brand_name": "Vocolens",
    "status": "approved",
    "brand_description": "Speak your journal entry instead of writing it.",
    "app_category": "Wellness",
    "target_audience": ["people too tired to write at night"],
    "core_features": ["Voice entries"],
}


def _patch_chat(monkeypatch, reply):
    chat = AsyncMock(return_value=reply)
    monkeypatch.setattr(ai_service, "_chat_json", chat)
    return chat


def test_preview_returns_the_caption_under_the_kit_rules(monkeypatch):
    _patch_chat(monkeypatch, {"caption": CAPTION})
    out = asyncio.run(ai_service.generate_caption_preview(PROJECT, PROFILE))
    assert out == {"caption": CAPTION}


def test_preview_is_grounded_in_the_hook_only(monkeypatch):
    chat = _patch_chat(monkeypatch, {"caption": CAPTION})
    asyncio.run(ai_service.generate_caption_preview(PROJECT, PROFILE))
    prompt = chat.call_args.kwargs["prompt"]
    assert HOOK in prompt
    # Hook-only grounding: the project's script is not material for
    # the preview, so its words never reach the model.
    assert "SCRIPTONLYMARKER" not in prompt


def test_preview_requires_a_hook_line(monkeypatch):
    _patch_chat(monkeypatch, {"caption": CAPTION})
    with pytest.raises(RuntimeError):
        asyncio.run(ai_service.generate_caption_preview(
            {**PROJECT, "hook_line": ""}, PROFILE))


@pytest.mark.parametrize("bad", [
    "Too short — you?",                                        # under 50
    "I quit replaying the whole day in my head and said it out loud instead at bedtime every single night — you?",  # over 80
    "I quit replaying the whole day in my head and said it out loud instead.",   # no closing question
    "",
])
def test_preview_refuses_a_caption_outside_the_window(monkeypatch, bad):
    _patch_chat(monkeypatch, {"caption": bad})
    with pytest.raises(RuntimeError):
        asyncio.run(ai_service.generate_caption_preview(PROJECT, PROFILE))
