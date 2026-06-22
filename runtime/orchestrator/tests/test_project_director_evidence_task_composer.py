from __future__ import annotations

import json
from pathlib import Path

from app.domain.project_director_evidence_pack import ProjectDirectorRepoEvidencePack
from app.services.project_director_evidence_task_composer_service import (
    ProjectDirectorEvidenceTaskComposerService,
)
from app.services.project_director_repo_evidence_service import (
    ProjectDirectorRepoEvidenceService,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _evidence_pack() -> ProjectDirectorRepoEvidencePack:
    return ProjectDirectorRepoEvidenceService(repo_root=_repo_root()).build_evidence_pack(
        goal_text="P10-B compose evidence grounded Project Director tasks"
    )


def test_composer_generates_tasks_grounded_in_evidence_pack() -> None:
    pack = _evidence_pack()
    result = ProjectDirectorEvidenceTaskComposerService().compose_tasks(
        evidence_pack=pack,
        user_goal="Build the P10 evidence-to-agent dry-run chain",
    )

    assert result.composition_status == "composed"
    assert result.source_evidence_pack_id == pack.evidence_pack_id
    assert result.product_runtime_git_write_allowed is False
    assert result.user_confirmation_required is True
    assert result.composed_tasks
    assert result.allowed_files
    assert result.forbidden_files
    assert result.required_reading
    assert result.targeted_tests
    assert result.risk_notes
    assert result.unknowns

    for task in result.composed_tasks:
        assert task.source_evidence_pack_id == pack.evidence_pack_id
        assert task.evidence_refs
        assert task.allowed_files
        assert task.forbidden_files
        assert task.required_reading
        assert task.targeted_tests
        assert task.risk_notes
        assert task.unknowns
        assert task.user_confirmation_required is True
        assert task.product_runtime_git_write_allowed is False


def test_composer_blocks_when_evidence_pack_has_no_repository_facts() -> None:
    pack = _evidence_pack().model_copy(
        update={"related_files": [], "evidence_refs": []}
    )

    result = ProjectDirectorEvidenceTaskComposerService().compose_tasks(
        evidence_pack=pack,
        user_goal="one sentence without repo evidence",
    )

    assert result.composition_status == "blocked"
    assert "evidence_refs_required" in result.blocked_reasons
    assert result.composed_tasks == []
    assert result.product_runtime_git_write_allowed is False


def test_composer_output_does_not_claim_execution_or_delivery() -> None:
    result = ProjectDirectorEvidenceTaskComposerService().compose_tasks(
        evidence_pack=_evidence_pack(),
        user_goal="draft tasks only",
    )
    payload = json.dumps(result.model_dump(mode="json"), ensure_ascii=False).lower()

    for forbidden in (
        "已提交",
        "已推送",
        "已完成执行",
        "created pr",
        "git push completed",
    ):
        assert forbidden not in payload
