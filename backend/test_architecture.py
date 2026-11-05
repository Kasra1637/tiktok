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
