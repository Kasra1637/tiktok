"""Architecture contracts: domain policy must not boot the application to run."""
import ast
from pathlib import Path
import subprocess
import sys

import pytest

BACKEND = Path(__file__).resolve().parent


@pytest.mark.parametrize("module", ["angle_policy", "template_recommendations", "character_policy", "scene_consistency", "final_beat", "ai_spoken", "ai_strategy", "ai_text", "ai_media", "creative_quality"])
def test_policy_import_does_not_load_http_or_model_adapters(module):
    result = subprocess.run(
        [sys.executable, "-c", (
            f"import {module}; import sys; "
            "forbidden = {'server', 'ai_service', 'auth', 'httpx', 'fastapi', 'aiosqlite'}; "
            "assert not (forbidden & set(sys.modules)), forbidden & set(sys.modules)"
        )], cwd=BACKEND, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_server_reexports_recommendation_policy_for_existing_callers():
    import server
    from template_recommendations import score_template_for_angle, split_shared_notes

    assert server._score_template_for_angle is score_template_for_angle
    assert server._split_shared_notes is split_shared_notes


def test_db_layer_is_owned_by_db_module():
    """The SQLite/Turso primitives live in db.py; server re-exports them."""
    import db
    import server

    assert server.get_db is db.get_db
    assert server._fetch_one is db._fetch_one
    assert server._fetch_all is db._fetch_all
    assert server._execute is db._execute
    assert server.init_db is db.init_db
    assert server._log_model_call is db._log_model_call
    assert server._LibsqlAsyncWrapper is db._LibsqlAsyncWrapper
    assert server._CursorWrapper is db._CursorWrapper


def test_db_module_never_imports_the_composition_root():
    """db.py must not import server; config flows via the _server back-ref."""
    tree = ast.parse((BACKEND / "db.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert "server" not in imports


def test_schema_module_owns_schema_bootstrap():
    """Schema creation/migrations live in schema.py, not inline in server."""
    import schema

    assert callable(schema.apply_schema)
    tree = ast.parse((BACKEND / "schema.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert "server" not in imports


def test_media_router_is_owned_by_routers_media():
    """Signed /api/media/* routes live in routers.media; server re-exports them."""
    import routers.media as media
    import server

    for name in ("serve_frame", "serve_template_thumbnail", "serve_video",
                 "download_video_clip", "serve_poster", "serve_asset",
                 "_parse_byte_range", "_iter_file_range", "_iter_r2_object"):
        assert getattr(server, name) is getattr(media, name), name
    assert server._VIDEO_FILENAME_RE is media._VIDEO_FILENAME_RE
    assert server._POSTER_FILENAME_RE is media._POSTER_FILENAME_RE


def test_media_routes_are_mounted_under_the_api_prefix():
    """Every signed media route answers under /api, where the minted URLs point.

    The routers.media extraction mounted the router on the app with no
    prefix, so /api/media/* fell through to the StaticFiles mount: posters
    404'd unless an eager hook had already written the file (History
    previews rendered black), videos were served as plain static files
    with no byte ranges and no signature check, and the lazy poster and
    cloud-restore paths never ran. The route functions were all correct —
    the direct-call media tests cannot see a mounting bug. This pin reads
    the mounted route table instead.
    """
    import routers.media as media
    import server

    mounted = {getattr(route, "path", "") for route in server.app.routes}
    for route in media.router.routes:
        path = getattr(route, "path", "")
        if not path:
            continue
        assert f"/api{path}" in mounted, path
        assert path not in mounted, path


def test_media_router_never_imports_the_composition_root():
    tree = ast.parse((BACKEND / "routers/media.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert "server" not in imports


def test_brands_router_is_owned_by_routers_brands():
    """Profile/angle/template routes live in routers.brands; server re-exports them."""
    import routers.brands as brands
    import server

    for name in ("create_brand", "list_brands", "get_brand", "update_brand",
                 "research_app_profile", "list_app_profiles", "get_app_profile",
                 "update_app_profile", "approve_app_profile", "list_templates",
                 "template_facets", "ensure_objective_templates",
                 "_normalize_url", "_brand_update_parts", "_cap_page_text",
                 "_approval_gaps", "_serialize_angle_row",
                 "_public_library_template", "_public_template",
                 "_ensure_objective_templates", "_require_profile_for_studio",
                 "_angle_feedback_for_profile", "_with_verdicts"):
        assert getattr(server, name) is getattr(brands, name), name
    for name in ("APP_RESEARCH_CAPS", "CONTENT_ANGLE_TEXT_FIELDS"):
        assert getattr(server, name) is getattr(brands, name), name


def test_studio_router_is_owned_by_routers_studio():
    """Studio project/plan/strategy routes live in routers.studio; server re-exports them."""
    import routers.studio as studio
    import server

    for name in ("list_studio_projects", "create_studio_project", "get_studio_project",
                 "update_studio_project", "suggest_hook_rewrite", "generate_plan",
                 "mark_project_ready", "submit_project_generation",
                 "generate_project_strategy", "list_studio_video_models",
                 "_two_section_repairs", "_public_project", "_project_strategy",
                 "_require_spoken_words_fit", "_require_current_strategy",
                 "_guard_render_scene", "_assert_model_usable",
                 "_assert_resolution_offered", "_assert_within_single_pass_cap",
                 "_require_renderable_project", "_backfill_two_section_projects"):
        assert getattr(server, name) is getattr(studio, name), name


def test_studio_router_never_imports_the_composition_root():
    tree = ast.parse((BACKEND / "routers/studio.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert "server" not in imports


def test_brands_router_never_imports_the_composition_root():
    tree = ast.parse((BACKEND / "routers/brands.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert "server" not in imports


def test_assets_router_is_owned_by_routers_assets():
    """App-Profile library routes live in routers.assets; server re-exports them."""
    import routers.assets as assets
    import server

    for name in ("list_assets", "get_asset_usage", "upload_asset", "update_asset",
                 "delete_asset", "attach_asset_to_project", "detach_asset_from_project",
                 "_public_asset", "_asset_usage_index", "_attach_usage",
                 "_asset_dir", "_ensure_asset_file"):
        assert getattr(server, name) is getattr(assets, name), name
    for name in ("ASSET_MAX_BYTES", "ASSET_IMAGE_TYPES", "ASSET_ALLOWED_EXT",
                 "ASSET_AUDIO_ROLES"):
        assert getattr(server, name) is getattr(assets, name), name


def test_assets_router_never_imports_the_composition_root():
    tree = ast.parse((BACKEND / "routers/assets.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert "server" not in imports


def test_history_router_is_owned_by_routers_history():
    """Generation history routes live in routers.history; server re-exports them."""
    import routers.history as history
    import server

    for name in ("list_generations", "get_generation", "poll_generation",
                 "retry_generation_storage", "_run_storage_repair",
                 "retry_generation", "set_generation_tiktok_link",
                 "set_generation_tiktok_views", "archive_generation",
                 "generation_history", "delete_generation"):
        assert getattr(server, name) is getattr(history, name), name


def test_history_router_never_imports_the_composition_root():
    tree = ast.parse((BACKEND / "routers/history.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert "server" not in imports


def test_history_router_fails_loudly_before_configuration(monkeypatch):
    """An unconfigured router raises instead of silently returning None."""
    import routers.history as history

    monkeypatch.setattr(history, "_server", None)
    with pytest.raises(RuntimeError):
        history._cfg("_fetch_one")



def test_ai_service_reexports_pure_clusters_for_existing_callers():
    """Pure clusters live in ai_* modules; ai_service re-exports them."""
    import ai_media
    import ai_service
    import ai_spoken
    import ai_strategy
    import ai_text

    for name in ("image_to_base64", "image_mime_type", "image_data_uri",
                 "_IMAGE_MIME_BY_SUFFIX"):
        assert getattr(ai_service, name) is getattr(ai_media, name), name
    for name in ("strip_html_to_text", "_html_meta_descriptions",
                 "_html_json_ld_strings", "_html_title", "page_text_with_metadata"):
        assert getattr(ai_service, name) is getattr(ai_text, name), name
    for name in ("spoken_budget", "hook_ceiling", "spoken_targets",
                 "trim_spoken_body", "trim_to_sentence", "strip_leading_hook",
                 "partition_spoken_words", "bind_spoken_words", "strategy_text",
                 "check_spoken_story", "repair_spoken_story",
                 "SPOKEN_CHARS_PER_SECOND", "HOOK_CHARS_PER_SECOND",
                 "HOOK_TARGET_CHARS", "SCRIPT_TARGET_CHARS", "_PROBLEM_MARKERS",
                 "_CONTINUITY_STOPWORDS", "_SCENE_MOMENTS", "_RESOLUTION_MARKERS",
                 "_BARE_LOCATION_NOUNS", "_PAYOFF_VERBS"):
        assert getattr(ai_service, name) is getattr(ai_spoken, name), name
    for name in ("normalize_strategy", "merge_legacy_location",
                 "_enforce_two_sections", "_clean_strategy_text",
                 "GENERATED_SECTIONS", "SECTION_ROLES", "STRATEGY_SCENE_FIELDS",
                 "STRATEGY_PERFORMANCE_FIELDS"):
        assert getattr(ai_service, name) is getattr(ai_strategy, name), name


def test_ai_adapter_reuses_the_same_angle_policy_for_all_briefs():
    import ai_service
    from angle_policy import angle_grounding, duplicate_angle_pairs, normalize_content_angles

    assert ai_service._angle_grounding is angle_grounding
    assert ai_service._duplicate_angle_pairs is duplicate_angle_pairs
    assert ai_service._normalize_content_angles is normalize_content_angles


@pytest.mark.parametrize("module", ["angle_policy", "template_recommendations", "character_policy", "scene_consistency", "final_beat", "ai_spoken", "ai_strategy", "ai_text", "ai_media", "creative_quality"])
def test_policy_never_imports_an_outer_adapter(module):
    tree = ast.parse((BACKEND / f"{module}.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert not (imports & {"server", "ai_service", "auth", "routers", "httpx", "fastapi", "aiosqlite"})
