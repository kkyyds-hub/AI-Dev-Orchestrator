from __future__ import annotations

import json
from pathlib import Path

from app.services.project_director_repo_evidence_service import (
    ProjectDirectorRepoEvidenceService,
)


FORBIDDEN_OUTPUT_TERMS = (
    "api_key",
    "token",
    "secret",
    "raw stdout",
    "raw stderr",
    "raw command",
    "pid",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_evidence_pack_is_built_from_real_project_director_repo_files() -> None:
    pack = ProjectDirectorRepoEvidenceService(repo_root=_repo_root()).build_evidence_pack(
        goal_text=(
            "P10-A readonly repo evidence pack for Project Director evidence-to-agent chain"
        )
    )

    assert pack.origin_main_commit
    assert pack.evidence_pack_id.startswith("p10-a-")
    assert pack.repo_root == str(_repo_root())
    assert pack.product_runtime_git_write_allowed is False
    assert pack.frontend_required is False
    assert pack.related_files
    assert {
        "runtime/orchestrator/app/api/routes/project_director.py",
        "runtime/orchestrator/app/services/project_director_plan_service.py",
        "runtime/orchestrator/app/domain/agent_session.py",
    }.issubset(set(pack.related_files))
    assert "apps/web/**" in pack.forbidden_paths
    assert "docs/superpowers/**" in pack.forbidden_paths
    assert "runtime/orchestrator/app/external_executors/**" in pack.forbidden_paths
    assert "product runtime Git write surfaces" in pack.forbidden_paths
    assert pack.suggested_tests == [
        "runtime/orchestrator/tests/test_project_director_repo_evidence_pack.py"
    ]
    assert pack.unknowns
    assert pack.evidence_refs
    assert pack.source_detail["inspection_mode"] == "readonly_path_and_keyword_scan"
    assert all(Path(_repo_root(), path).exists() for path in pack.related_files)


def test_evidence_pack_output_redacts_runtime_details_and_does_not_write_repo(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "repo"
    marker.mkdir()
    (marker / "runtime").mkdir()
    before_entries = sorted(path.relative_to(marker).as_posix() for path in marker.rglob("*"))

    pack = ProjectDirectorRepoEvidenceService(repo_root=_repo_root()).build_evidence_pack(
        goal_text="confirm safety boundary for P10-A"
    )
    payload = json.dumps(pack.model_dump(mode="json"), ensure_ascii=False).lower()

    for term in FORBIDDEN_OUTPUT_TERMS:
        assert term not in payload
    after_entries = sorted(path.relative_to(marker).as_posix() for path in marker.rglob("*"))
    assert after_entries == before_entries
