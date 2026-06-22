from __future__ import annotations

import json
from pathlib import Path

from app.services.project_director_agent_assignment_service import (
    ProjectDirectorAgentAssignmentService,
)
from app.services.project_director_evidence_task_composer_service import (
    ProjectDirectorEvidenceTaskComposerService,
)
from app.services.project_director_repo_evidence_service import (
    ProjectDirectorRepoEvidenceService,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _composition_result():
    evidence_pack = ProjectDirectorRepoEvidenceService(
        repo_root=_repo_root()
    ).build_evidence_pack(goal_text="P10-C agent assignment")
    return ProjectDirectorEvidenceTaskComposerService().compose_tasks(
        evidence_pack=evidence_pack,
        user_goal="Assign evidence-grounded programmer and reviewer agents",
    )


def test_agent_assignment_binds_programmer_and_readonly_reviewer_to_tasks() -> None:
    composition = _composition_result()
    assignment = ProjectDirectorAgentAssignmentService().assign_agents(
        task_composition=composition
    )

    assert assignment.assignment_status == "assigned"
    assert assignment.assignment_id.startswith("p10-c-")
    assert assignment.source_evidence_pack_id == composition.source_evidence_pack_id
    assert assignment.source_task_ids
    assert assignment.director_role == "planner_reviewer_dispatcher"
    assert assignment.programmer_agent.role == "programmer"
    assert assignment.programmer_agent.executor_backed is True
    assert assignment.programmer_executor_backed is True
    assert assignment.reviewer_agent.role == "reviewer"
    assert assignment.reviewer_agent.executor_backed is True
    assert assignment.reviewer_agent.readonly is True
    assert assignment.reviewer_executor_backed is True
    assert assignment.readonly_review_required is True
    assert assignment.director_permanent_executor is False
    assert assignment.product_runtime_git_write_allowed is False
    assert assignment.frontend_required is False
    assert assignment.native_executor_started is False
    assert assignment.codex_started is False
    assert assignment.claude_code_started is False


def test_agent_assignment_blocks_without_composed_tasks() -> None:
    composition = _composition_result().model_copy(
        update={"composition_status": "blocked", "composed_tasks": []}
    )

    assignment = ProjectDirectorAgentAssignmentService().assign_agents(
        task_composition=composition
    )

    assert assignment.assignment_status == "blocked"
    assert "composed_tasks_required" in assignment.blocked_reasons
    assert assignment.source_task_ids == []
    assert assignment.product_runtime_git_write_allowed is False


def test_agent_assignment_output_hides_runtime_details() -> None:
    assignment = ProjectDirectorAgentAssignmentService().assign_agents(
        task_composition=_composition_result()
    )
    payload = json.dumps(assignment.model_dump(mode="json"), ensure_ascii=False).lower()

    for forbidden in (
        "api_key",
        "token",
        "secret",
        "pid",
        "raw command",
        "stdout",
        "stderr",
    ):
        assert forbidden not in payload
