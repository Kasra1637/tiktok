"""
Cross-tenant regressions.

Every App Profile route added since the studio rewrite has carried an
`AND user_id = ?` predicate. Three did not, and they are grouped here because
the failure mode is the same in all three: one founder's request reads or
rewrites another founder's row.

These are not exotic. `analyze-url` fires on the App Profile entry path, so two
founders researching the same product would collide in normal use.

The HTTP fetch and the AI extraction in analyze-url are mocked. What is under
test is the ownership predicate, not the crawl.
"""
import asyncio
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"
OTHER_USER = "other-user"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-tenant-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _a_profile(api, name, user_id):
    """A profile carrying the fields approval requires.

    _approval_gaps in server.py refuses to approve a profile with no
    description, no core features, nothing describing what the app is used
    for, and no outcome statement linking a feature to its benefit. Test
    profiles need the same, or every test that approves one is asserting the
    gap check rather than what it meant to check.
    """
    from models import BrandProfileCreateRequest
    return _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name,
        brand_description=f"{name} description",
        core_features=["One-tap logging"],
        usage_moments=["Logging a shift without paperwork"],
        outcome_statements=[{
            "outcome": "Walking out on time",
            "who_feels_it": "nurses on rotating shifts",
            "from_feature": "One-tap logging",
            "how_it_helps": "One tap logs the whole shift so handover writes itself",
        }],
    ), user_id=user_id))


class TestLegacyBrandEndpointsAreScoped:
    """
    GET/PATCH /brand/{brand_id} predate the App Profile routes and looked rows up
    by id alone. The read leaked the whole row including raw_extracted_text; the
    write let any authenticated user overwrite another founder's profile.
    """

    def test_another_users_profile_is_not_readable(self, api):
        theirs = _a_profile(api, "Theirs Read", OTHER_USER)
        with pytest.raises(HTTPException) as err:
            _run(api.get_brand(theirs["id"], ANON))
        assert err.value.status_code == 404

    def test_another_users_profile_is_not_writable(self, api):
        from models import BrandProfileUpdateRequest
        theirs = _a_profile(api, "Theirs Write", OTHER_USER)
        with pytest.raises(HTTPException) as err:
            _run(api.update_brand(
                theirs["id"],
                payload=BrandProfileUpdateRequest(brand_name="Hijacked"),
                user_id=ANON,
            ))
        assert err.value.status_code == 404
        # And the row is untouched, not merely hidden from the response.
        still = _run(api.get_brand(theirs["id"], OTHER_USER))
        assert still["brand_name"] == "Theirs Write"

    def test_the_owner_can_still_read_and_write(self, api):
        from models import BrandProfileUpdateRequest
        mine = _a_profile(api, "Mine", ANON)
        read = _run(api.get_brand(mine["id"], ANON))
        assert read["brand_name"] == "Mine"

        _run(api.update_brand(
            mine["id"],
            payload=BrandProfileUpdateRequest(brand_name="Mine Renamed"),
            user_id=ANON,
        ))
        # The UPDATE carries the predicate too, so the write must actually land.
        assert _run(api.get_brand(mine["id"], ANON))["brand_name"] == "Mine Renamed"


class TestApprovalNeedsAProfileWorthApproving:
    """
    Approval is the only thing between unreviewed research and a render, so
    it used to be too cheap to mean anything: a bare POST flipped the status.

    The harm landed later, at generation time, where nothing on screen said the
    gaps existed -- AppProfileDetail renders only fields that have values, so
    "never researched" and "intentionally blank" are the same empty space.
    """

    def _bare(self, api, name="Hollow App"):
        from models import BrandProfileCreateRequest
        return _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name=name), user_id=ANON))

    def _approve(self, api, profile_id):
        from models import ApproveAppProfileRequest
        return _run(api.approve_app_profile(
            profile_id=profile_id, payload=ApproveAppProfileRequest(), user_id=ANON))

    def test_an_empty_profile_cannot_be_approved(self, api):
        profile = self._bare(api)
        with pytest.raises(HTTPException) as err:
            self._approve(api, profile["id"])
        assert err.value.status_code == 409
        # It stays a draft, so nothing downstream can render from it.
        assert _run(api.get_app_profile(profile["id"], ANON))["status"] == "draft"

    def test_the_refusal_names_what_is_missing(self, api):
        """
        "Cannot approve" with no list is a dead end. The founder has to know
        which fields to fill, and the message has to be the same one the fix
        produces rather than a generic failure.
        """
        profile = self._bare(api)
        with pytest.raises(HTTPException) as err:
            self._approve(api, profile["id"])
        detail = str(err.value.detail)
        assert "description" in detail
        assert "core feature" in detail

    def test_a_profile_with_the_basics_is_approvable(self, api):
        profile = _a_profile(api, "Complete App", ANON)
        assert self._approve(api, profile["id"])["status"] == "approved"

    def test_usage_may_be_described_by_any_of_its_three_fields(self, api):
        """
        The research fills usage_moments, but a founder writing the profile by
        hand describes what an app is for under primary_use_cases or
        problems_solved just as naturally. Refusing those would train people to
        type filler into the one field the check happened to read.
        """
        from models import (ApproveAppProfileRequest, BrandProfileCreateRequest)
        for field in ("usage_moments", "primary_use_cases", "problems_solved"):
            profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
                brand_name=f"Described by {field}",
                brand_description="Shift logging for healthcare workers.",
                core_features=["One-tap shift logging"],
                outcome_statements=[{
                    "outcome": "Walking out on time",
                    "who_feels_it": "nurses on rotating shifts",
                    "from_feature": "One-tap shift logging",
                    "how_it_helps": "One tap logs the whole shift so handover writes itself",
                }],
                **{field: ["Clocking on and off"]},
            ), user_id=ANON))
            assert _run(api.approve_app_profile(
                profile_id=profile["id"],
                payload=ApproveAppProfileRequest(),
                user_id=ANON,
            ))["status"] == "approved", field

    def test_a_sparse_but_honest_profile_is_still_approvable(self, api):
        """
        Not everything is required. An app with no proof moment is a real
        profile, and demanding filler for those would make the gate something
        founders learn to bypass.
        """
        from models import ApproveAppProfileRequest, BrandProfileCreateRequest
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="Honest And Sparse",
            brand_description="A timer.",
            core_features=["One timer"],
            problems_solved=["Starting late"],
            outcome_statements=[{
                "outcome": "Starting without stalling",
                "who_feels_it": "people who start late",
                "from_feature": "One timer",
                "how_it_helps": "One tap starts it so there is nothing to set up",
            }],
        ), user_id=ANON))
        assert _run(api.approve_app_profile(
            profile_id=profile["id"],
            payload=ApproveAppProfileRequest(),
            user_id=ANON,
        ))["status"] == "approved"
