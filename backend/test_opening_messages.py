"""Opening text: exact 20-message contract and app ownership at the HTTP boundary."""
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_service


MESSAGES = [f"Focus timer opening idea number {i}" for i in range(20)]
PROFILE = {"id": "app-1", "brand_name": "FocusTimer", "status": "approved",
           "core_features": ["Focus timer"], "claims_banned": ["cures ADHD"]}


def test_generator_requests_twenty_grounded_messages(monkeypatch):
    chat = AsyncMock(return_value={"messages": MESSAGES})
    monkeypatch.setattr(ai_service, "_chat_json", chat)
    assert asyncio.run(ai_service.generate_opening_messages(PROFILE, ["Old opening"])) == MESSAGES
    args = chat.call_args.kwargs
    assert "FocusTimer" in args["prompt"] and "Old opening" in args["prompt"]
    assert args["json_schema"]["properties"]["messages"]["maxItems"] == 20


@pytest.mark.parametrize("messages", [MESSAGES[:10], ["same"] * 20,
    MESSAGES[:19] + [""], MESSAGES[:19] + ["x" * 121],
    MESSAGES[:19] + ["Old opening"], MESSAGES[:19] + ["This cures ADHD"]])
def test_generator_rejects_incomplete_repeated_or_unsafe_copy(monkeypatch, messages):
    monkeypatch.setattr(ai_service, "_chat_json", AsyncMock(return_value={"messages": messages}))
    with pytest.raises(RuntimeError):
        asyncio.run(ai_service.generate_opening_messages(PROFILE, ["Old opening"]))


def test_http_app_scoping_active_app_and_failures(monkeypatch):
    import server
    from auth import get_current_user_id

    fetch = AsyncMock(return_value=PROFILE)
    active = AsyncMock(return_value=PROFILE)
    generate = AsyncMock(return_value=MESSAGES)
    async def logged(operation, modality, model, call, user_id, **refs):
        assert operation == "opening_messages" and user_id == "owner"
        return await call()
    monkeypatch.setattr(server, "_fetch_one", fetch)
    monkeypatch.setattr(server, "_fetch_active_brand", active)
    monkeypatch.setattr(server, "_log_model_call", logged)
    monkeypatch.setattr(ai_service, "generate_opening_messages", generate)
    monkeypatch.setattr(ai_service, "OPENROUTER_API_KEY", "test-key")
    server.app.dependency_overrides[get_current_user_id] = lambda: "owner"

    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=server.app), base_url="http://test") as client:
            response = await client.post("/api/demo-cta/opening-messages", json={"profile_id": "app-1", "previous": ["Old"]})
            assert response.status_code == 200 and response.json()["messages"] == MESSAGES
            assert fetch.call_args.args[1] == ("app-1", "owner")
            generate.assert_awaited_with(PROFILE, ["Old"])
            response = await client.post("/api/demo-cta/opening-messages", json={})
            assert response.status_code == 200
            active.assert_awaited_once_with("owner")
            fetch.return_value = None
            response = await client.post("/api/demo-cta/opening-messages", json={"profile_id": "someone-elses-app"})
            assert response.status_code == 404
            fetch.return_value = {**PROFILE, "status": "draft"}
            response = await client.post("/api/demo-cta/opening-messages", json={"profile_id": "app-1"})
            assert response.status_code == 409
            fetch.return_value = PROFILE
            generate.side_effect = RuntimeError("provider unavailable")
            response = await client.post("/api/demo-cta/opening-messages", json={"profile_id": "app-1"})
            assert response.status_code == 502 and "Try Surprise me again" in response.json()["detail"]
            response = await client.post("/api/demo-cta/opening-messages", json={"previous": ["a"] * 21})
            assert response.status_code == 422
            monkeypatch.setattr(ai_service, "OPENROUTER_API_KEY", "")
            response = await client.post("/api/demo-cta/opening-messages", json={"profile_id": "app-1"})
            assert response.status_code == 503 and "OPENROUTER_API_KEY" in response.json()["detail"]
    try:
        asyncio.run(exercise())
    finally:
        server.app.dependency_overrides.pop(get_current_user_id, None)
