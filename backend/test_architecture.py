"""Architecture contracts: domain policy must not boot the application to run."""
import ast
from pathlib import Path
import subprocess
import sys

import pytest

BACKEND = Path(__file__).resolve().parent


@pytest.mark.parametrize("module", ["angle_policy", "template_recommendations", "character_policy", "scene_consistency", "final_beat"])
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


def test_ai_adapter_reuses_the_same_angle_policy_for_all_briefs():
    import ai_service
    from angle_policy import angle_grounding, duplicate_angle_pairs, normalize_content_angles

    assert ai_service._angle_grounding is angle_grounding
    assert ai_service._duplicate_angle_pairs is duplicate_angle_pairs
    assert ai_service._normalize_content_angles is normalize_content_angles


@pytest.mark.parametrize("module", ["angle_policy", "template_recommendations", "character_policy", "scene_consistency", "final_beat"])
def test_policy_never_imports_an_outer_adapter(module):
    tree = ast.parse((BACKEND / f"{module}.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert not (imports & {"server", "ai_service", "auth", "routers", "httpx", "fastapi", "aiosqlite"})
