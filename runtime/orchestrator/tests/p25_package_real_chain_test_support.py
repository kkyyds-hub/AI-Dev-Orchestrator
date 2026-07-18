"""Real P25-B integration support with no synthetic P25 messages."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.core.db_tables import ProjectDirectorMessageTable, TaskTable
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_role import ProjectRoleCode
from app.domain.run import (
    RunBudgetPressureLevel,
    RunBudgetStrategyAction,
    RunRoutingScoreItem,
    RunStrategyDecision,
)
from app.repositories.project_director_plan_version_repository import (
    ProjectDirectorPlanVersionRepository,
)
from app.repositories.project_director_repository_binding_config_repository import (
    ProjectDirectorRepositoryBindingConfigRepository,
)
from app.repositories.project_director_skill_binding_config_repository import (
    ProjectDirectorSkillBindingConfigRepository,
)
from app.repositories.project_director_verification_config_repository import (
    ProjectDirectorVerificationConfigRepository,
)
from app.repositories.repository_workspace_repository import RepositoryWorkspaceRepository
from app.services.project_director_bounded_rework_evidence_resolver import (
    ProjectDirectorBoundedReworkEvidenceResolver,
)
from app.services.project_director_bounded_rework_package_preparation_service import (
    ProjectDirectorBoundedReworkPackagePreparationService,
)
from app.services.project_director_protected_transition_dispatch_consumption_preflight_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService,
)
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionService,
)
from app.services.project_director_protected_transition_dispatch_intent_service import (
    ProjectDirectorProtectedTransitionDispatchIntentService,
)
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
)
from app.services.task_readiness_service import TaskReadinessResult
from app.services.task_router_service import TaskRoutingCandidate
from tests.p23_test_support import (
    FakeBudgetGuardService,
    FakeTaskReadinessService,
    FakeTaskStateMachineService,
    ProjectDirectorPostReviewAutomationService,
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService,
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService,
    ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService,
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService,
    _StubDiff,
    _StubHandoff,
    _valid_review_action_d3,
    make_repos,
    make_session_factory,
    make_test_engine,
    seed_base_records,
)


DIFF_SHA256 = hashlib.sha256(b"diff content").hexdigest()
_P25_FALLBACK_WORKSPACE_PATH = "/tmp/test-workspace-p23"


class P25FakeTaskRouterService:
    """P25-local router fixture independent of uncommitted P23 test support."""

    def evaluate_exact_task_for_dispatch(self, *, task):
        return TaskRoutingCandidate(
            task=task,
            readiness=TaskReadinessResult(
                task_id=task.id,
                ready_for_execution=True,
                blocking_signals=[],
                blocking_reasons=[],
                dependency_items=[],
            ),
            ready=True,
            routing_score=1.0,
            route_reason="test",
            routing_score_breakdown=[
                RunRoutingScoreItem(code="test", label="Test", score=1.0, detail="test")
            ],
            execution_attempts=0,
            recent_failure_count=0,
            budget_pressure_level=RunBudgetPressureLevel.NORMAL,
            budget_action=RunBudgetStrategyAction.FULL_SPEED,
            budget_strategy_code="normal",
            budget_score_adjustment=0.0,
            project_stage=None,
            owner_role_code=ProjectRoleCode.ARCHITECT,
            upstream_role_code=None,
            downstream_role_code=None,
            dispatch_status="dispatched",
            handoff_reason="test",
            matched_terms=(),
            model_name="test-model",
            model_tier="standard",
            selected_skill_codes=("test-skill",),
            selected_skill_names=("Test skill",),
            strategy_code="normal",
            strategy_summary="Normal execution",
            strategy_reasons=[],
            strategy_decision=RunStrategyDecision(
                budget_pressure_level=RunBudgetPressureLevel.NORMAL,
                budget_action=RunBudgetStrategyAction.FULL_SPEED,
                strategy_code="normal",
                summary="Normal execution",
                owner_role_code=ProjectRoleCode.ARCHITECT,
                model_name="test-model",
                model_tier="standard",
                selected_skill_codes=("test-skill",),
                selected_skill_names=("Test skill",),
            ),
        )


class _P25EvidenceDiff:
    """Readonly adapter projection matching the persisted P21-C evidence chain."""

    def __init__(self, environment: dict[str, Any]) -> None:
        self._environment = environment

    def build_candidate_diff_from_sources(self, **kw: Any) -> Any:
        source_message = kw.get("source_message")
        initial = getattr(source_message, "id", None) == self._environment[
            "initial_candidate_message_id"
        ]
        diff_text = self._environment["unified_diff"] if initial else "diff content"
        workspace_path = (
            self._environment["workspace_path"].as_posix()
            if initial
            else _P25_FALLBACK_WORKSPACE_PATH
        )
        return type("D", (), {
            "diff_generation_status": "generated",
            "source_candidate_write_verified": True,
            "readonly_real_diff_generated": True,
            "real_diff_generated": True,
            "workspace_path": workspace_path,
            "workspace_path_within_root": True,
            "unified_diff_text": diff_text,
            "diff_entries": [type("E", (), {
                "relative_path": "src/example.py",
                "unified_diff": diff_text,
            })()],
            "diff_bytes": len(diff_text.encode()),
            "diff_file_count": 1,
        })()


class _P25EvidenceHandoff:
    def __init__(self, environment: dict[str, Any]) -> None:
        self._environment = environment

    def build_candidate_diff_review_handoff_from_sources(self, **kw: Any) -> Any:
        source_message = kw.get("source_message")
        initial = getattr(source_message, "id", None) == self._environment[
            "initial_diff_message_id"
        ]
        diff_text = self._environment["unified_diff"] if initial else "diff content"
        return type("H", (), {
            "review_handoff_status": "created",
            "source_diff_verified": True,
            "source_diff_sha256": (
                self._environment["diff_sha256"] if initial else DIFF_SHA256
            ),
            "review_scope_paths": ["src/example.py"],
            "diff_bytes": len(diff_text.encode()),
        })()


def _make_p22_service(
    session,
    msg_repo,
    sess_repo,
    task_repo,
    *,
    candidate_diff_service=None,
    review_handoff_service=None,
):
    """Create a real P22 service with all real sub-services."""
    return ProjectDirectorPostReviewAutomationService(
        session_repository=sess_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        disposition_service=ProjectDirectorSandboxCandidateDiffReviewDispositionService(
            session_repository=sess_repo, message_repository=msg_repo,
        ),
        preflight_service=ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionPreflightService(
            session_repository=sess_repo, message_repository=msg_repo,
        ),
        consumption_service=ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService(
            session_repository=sess_repo, message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=review_handoff_service or _StubHandoff(),
            candidate_diff_service=candidate_diff_service or _StubDiff(),
        ),
        handoff_service=ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffService(
            session_repository=sess_repo, message_repository=msg_repo,
            task_repository=task_repo,
        ),
        human_escalation_package_service=ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService(
            session_repository=sess_repo, message_repository=msg_repo,
            task_repository=task_repo,
        ),
        freshness_service=ProjectDirectorProtectedTransitionEvidenceFreshnessService(
            session_repository=sess_repo, message_repository=msg_repo,
            task_repository=task_repo,
            review_handoff_service=review_handoff_service or _StubHandoff(),
            candidate_diff_service=candidate_diff_service or _StubDiff(),
        ),
    )


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _create_p25_evidence_message(
    msg_repo,
    *,
    session_id: UUID,
    project_id: UUID,
    task_id: UUID,
    intent: str,
    source_detail: str,
    action: dict[str, Any],
    content: str,
) -> ProjectDirectorMessage:
    message = ProjectDirectorMessage(
        session_id=session_id,
        role=ProjectDirectorMessageRole.ASSISTANT,
        content=content,
        sequence_no=msg_repo.get_next_sequence_no(session_id=session_id),
        intent=intent,
        related_project_id=project_id,
        related_task_id=task_id,
        source=ProjectDirectorMessageSource.SYSTEM,
        source_detail=source_detail,
        suggested_actions=[action],
        requires_confirmation=False,
        risk_level=ProjectDirectorMessageRiskLevel.HIGH,
    )
    return msg_repo.create(message)


def _create_p25_repository_and_workspace(tmp_path: Path, session_id: UUID):
    repository_root = tmp_path / "repository"
    workspace_root = tmp_path / "sandbox"
    workspace_path = workspace_root / str(session_id)
    repository_root.mkdir()
    workspace_path.mkdir(parents=True)
    (repository_root / "src").mkdir()
    (repository_root / "src/example.py").write_text("value = 'base'\n", encoding="utf-8")
    for args in (
        ("git", "init"),
        ("git", "config", "user.email", "test@example.invalid"),
        ("git", "config", "user.name", "P25 test"),
        ("git", "add", "src/example.py"),
        ("git", "commit", "-m", "base"),
    ):
        subprocess.run(args, cwd=repository_root, check=True, capture_output=True)
    base_commit_sha = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (workspace_path / "src").mkdir()
    (workspace_path / "src/example.py").write_text(
        "value = 'candidate'\n", encoding="utf-8"
    )
    return {
        "repository_root": repository_root,
        "workspace_root": workspace_root,
        "workspace_path": workspace_path,
        "base_commit_sha": base_commit_sha,
    }


def _persist_minimal_p25_control_plane(
    session,
    *,
    session_id: UUID,
    project_id: UUID,
    task_id: UUID,
    environment: dict[str, Any],
) -> None:
    from app.core.db_tables import TaskTable
    from app.domain.project_director_plan_version import (
        PlanVersionStatus,
        ProjectDirectorPlanVersion,
        ProjectScopeSummary,
    )
    from app.domain.project_director_repository_binding_config import (
        ProjectDirectorRepositoryBindingConfig,
        ProjectDirectorRepositoryBindingConfigItem,
        RepositoryBindingConfigStatus,
    )
    from app.domain.project_director_skill_binding_config import (
        ProjectDirectorSkillBindingConfig,
        ProjectDirectorSkillBindingConfigItem,
        SkillBindingConfigStatus,
    )
    from app.domain.project_director_verification_config import (
        ProjectDirectorVerificationConfig,
        ProjectDirectorVerificationConfigItem,
        VerificationConfigStatus,
    )
    from app.domain.repository_workspace import RepositoryWorkspace
    from app.repositories.project_director_plan_version_repository import (
        ProjectDirectorPlanVersionRepository,
    )
    from app.repositories.project_director_repository_binding_config_repository import (
        ProjectDirectorRepositoryBindingConfigRepository,
    )
    from app.repositories.project_director_skill_binding_config_repository import (
        ProjectDirectorSkillBindingConfigRepository,
    )
    from app.repositories.project_director_verification_config_repository import (
        ProjectDirectorVerificationConfigRepository,
    )
    from app.repositories.repository_workspace_repository import (
        RepositoryWorkspaceRepository,
    )

    now = datetime.now(timezone.utc)
    plan = ProjectDirectorPlanVersion(
        session_id=session_id,
        project_id=project_id,
        version_no=1,
        status=PlanVersionStatus.CONFIRMED,
        plan_summary="P25 bounded rework test plan.",
        acceptance_criteria=["Update src/example.py safely."],
        project_scope=ProjectScopeSummary(in_scope=["src/example.py"]),
        confirmed_at=now,
    )
    ProjectDirectorPlanVersionRepository(session).create(plan)
    locator = f"pdv:{plan.id}:1"
    task_row = session.get(TaskTable, task_id)
    assert task_row is not None
    task_row.source_draft_id = locator
    session.commit()

    repository_root = environment["repository_root"].as_posix()
    ProjectDirectorRepositoryBindingConfigRepository(session).add_no_commit(
        ProjectDirectorRepositoryBindingConfig(
            project_id=project_id,
            plan_version_id=plan.id,
            source_draft_id=locator,
            status=RepositoryBindingConfigStatus.CONFIRMED,
            repository_bindings=[
                ProjectDirectorRepositoryBindingConfigItem(
                    target=repository_root,
                    branch="main",
                    focus_paths=["src/example.py"],
                    usage="Read-only P25 evidence binding.",
                    safety_note="No product runtime Git writes.",
                    review_status="confirmed",
                )
            ],
            confirmed_at=now,
        )
    )
    ProjectDirectorSkillBindingConfigRepository(session).add_no_commit(
        ProjectDirectorSkillBindingConfig(
            project_id=project_id,
            plan_version_id=plan.id,
            source_draft_id=locator,
            status=SkillBindingConfigStatus.CONFIRMED,
            skill_bindings=[
                ProjectDirectorSkillBindingConfigItem(
                    skill_code="test-skill",
                    skill_name="Test skill",
                    owner_role_code="architect",
                    usage="Exercise the bounded rework test.",
                    review_status="confirmed",
                )
            ],
            confirmed_at=now,
        )
    )
    ProjectDirectorVerificationConfigRepository(session).add_no_commit(
        ProjectDirectorVerificationConfig(
            project_id=project_id,
            plan_version_id=plan.id,
            source_draft_id=locator,
            status=VerificationConfigStatus.CONFIRMED,
            verification_mechanisms=[
                ProjectDirectorVerificationConfigItem(
                    name="Target file check",
                    command_or_method="inspect src/example.py",
                    evidence_required="sandbox file changed",
                    owner_role_code="architect",
                    review_status="confirmed",
                )
            ],
            confirmed_at=now,
        )
    )
    session.commit()
    RepositoryWorkspaceRepository(session).upsert(
        RepositoryWorkspace(
            project_id=project_id,
            root_path=repository_root,
            display_name="P25 test repository",
            allowed_workspace_root=environment["repository_root"].parent.as_posix(),
        )
    )


def _seed_real_p20_p21_review_chain(
    msg_repo,
    *,
    session_id: UUID,
    project_id: UUID,
    task_id: UUID,
    environment: dict[str, Any],
) -> UUID:
    from app.domain.project_director_sandbox_candidate_diff import (
        P21_C_SANDBOX_CANDIDATE_DIFF_BASE_CONTENT_SOURCE_EXACT_GIT_COMMIT_OBJECT,
        P21_C_SANDBOX_CANDIDATE_DIFF_BASE_EVIDENCE_SCHEMA_VERSION,
        ProjectDirectorSandboxCandidateDiffResult,
    )
    from app.domain.project_director_sandbox_candidate_file_write import (
        ProjectDirectorSandboxCandidateFileWriteResult,
    )
    from app.domain.project_director_sandbox_operation_manifest_guard import (
        ProjectDirectorSandboxOperationManifestGuardResult,
    )
    from app.domain.project_director_sandbox_workspace_creation import (
        ProjectDirectorSandboxWorkspaceCreationResult,
    )
    from app.domain.project_director_sandbox_workspace_manifest_write import (
        ProjectDirectorSandboxWorkspaceManifestWriteResult,
    )
    from app.domain.project_director_sandbox_write_execution import (
        ProjectDirectorSandboxWriteExecutionResult,
    )
    from app.domain.project_director_sandbox_write_preflight import (
        ProjectDirectorSandboxWritePreflightResult,
    )
    from app.services.project_director_sandbox_candidate_diff_service import (
        P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
        P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
    )
    from app.services.project_director_sandbox_candidate_file_write_service import (
        P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
        P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
    )
    from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
        P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
    )
    from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
        REVIEW_OUTPUT_SCHEMA_VERSION,
    )
    from app.services.project_director_sandbox_operation_manifest_guard_service import (
        P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE,
        P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
        P21_SANDBOX_WRITE_EXECUTION_ACTION_TYPE,
    )
    from app.services.project_director_sandbox_workspace_creation_service import (
        P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
        P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
    )
    from app.services.project_director_sandbox_workspace_manifest_write_service import (
        INTERNAL_MANIFEST_DIR_NAME,
        INTERNAL_MANIFEST_FILE_NAME,
        P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE,
        P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
    )
    from app.services.project_director_sandbox_write_execution_service import (
        P20_SANDBOX_WRITE_PREFLIGHT_ACTION_TYPE,
        P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
    )
    from app.services.project_director_sandbox_write_preflight_service import (
        P20_SANDBOX_WRITE_PREFLIGHT_SOURCE_DETAIL,
    )
    from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
        P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    )

    workspace_path = environment["workspace_path"].as_posix()
    workspace_root = environment["workspace_root"].as_posix()
    repository_root = environment["repository_root"].as_posix()
    manifest_path = (
        environment["workspace_path"]
        / INTERNAL_MANIFEST_DIR_NAME
        / INTERNAL_MANIFEST_FILE_NAME
    )
    base_snapshot_fingerprint = hashlib.sha256(
        (environment["repository_root"] / "src/example.py").read_bytes()
    ).hexdigest()
    common = {"session_id": session_id, "source_task_id": task_id}

    preflight = ProjectDirectorSandboxWritePreflightResult(
        preflight_status="passed",
        source_message_id=uuid4(),
        preflight_message_bound=True,
        checked_operations_count=1,
        allowed_operations_count=1,
        accepted_operations=[{"path": "src/example.py", "operation": "update"}],
        accepted_operation_paths=["src/example.py"],
        recommended_next_step="Execute the sandbox policy plan.",
        **common,
    )
    preflight_message = _create_p25_evidence_message(
        msg_repo, session_id=session_id, project_id=project_id, task_id=task_id,
        intent="sandbox_write_preflight", source_detail=P20_SANDBOX_WRITE_PREFLIGHT_SOURCE_DETAIL,
        action={"type": P20_SANDBOX_WRITE_PREFLIGHT_ACTION_TYPE, **preflight.model_dump(mode="json")},
        content="P20 preflight passed.",
    )
    execution = ProjectDirectorSandboxWriteExecutionResult(
        execution_status="simulated", source_message_id=preflight_message.id,
        source_preflight_status="passed", source_preflight_message_bound=True,
        policy_only_source_verified=True, checked_operations_count=1,
        simulated_operations_count=1, accepted_operation_paths=["src/example.py"],
        execution_summary="P21 execution simulated.", recommended_next_step="Guard the operation manifest.",
        **common,
    )
    execution_message = _create_p25_evidence_message(
        msg_repo, session_id=session_id, project_id=project_id, task_id=task_id,
        intent="sandbox_write_execution", source_detail=P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
        action={"type": P21_SANDBOX_WRITE_EXECUTION_ACTION_TYPE, **execution.model_dump(mode="json")},
        content="P21 execution simulated.",
    )
    operation = ProjectDirectorSandboxOperationManifestGuardResult(
        manifest_status="manifested", source_message_id=uuid4(),
        source_execution_message_id=execution_message.id,
        source_workspace_guard_verified=True, workspace_path_preview=workspace_path,
        workspace_path_within_root=True, operation_manifest_created=True,
        manifest_operations_count=1, manifest_allowed_operations_count=1,
        manifest_operations=[{"operation_id": "update-example", "path": "src/example.py", "operation": "update", "operation_manifest_allowed": True}],
        allowed_operation_paths=["src/example.py"], manifest_summary="One sandbox operation is allowed.",
        recommended_next_step="Create the sandbox workspace.", **common,
    )
    operation_message = _create_p25_evidence_message(
        msg_repo, session_id=session_id, project_id=project_id, task_id=task_id,
        intent="sandbox_operation_manifest_guard", source_detail=P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
        action={"type": P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE, **operation.model_dump(mode="json")},
        content="P21-C operation manifest recorded.",
    )
    creation = ProjectDirectorSandboxWorkspaceCreationResult(
        creation_status="created", source_message_id=operation_message.id,
        source_manifest_message_bound=True, source_manifest_verified=True,
        workspace_path=workspace_path, workspace_root=workspace_root,
        workspace_path_within_root=True, workspace_created=True,
        creation_summary="Sandbox workspace created.", recommended_next_step="Write the internal manifest.",
        **common,
    )
    creation_message = _create_p25_evidence_message(
        msg_repo, session_id=session_id, project_id=project_id, task_id=task_id,
        intent="sandbox_workspace_create", source_detail=P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
        action={"type": P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE, **creation.model_dump(mode="json")},
        content="P21-C workspace created.",
    )
    manifest_payload = {
        "schema_version": "p21-c-d.v1", "session_id": str(session_id),
        "source_task_id": str(task_id), "source_message_id": str(creation_message.id),
        "workspace_path": workspace_path, "workspace_root": workspace_root,
        "manifest_file_path": manifest_path.as_posix(), "internal_manifest_only": True,
        "business_file_write_allowed": False, "git_write_performed": False,
    }
    manifest_path.parent.mkdir(exist_ok=True)
    manifest_path.write_text(json.dumps(manifest_payload, sort_keys=True), encoding="utf-8")
    manifest = ProjectDirectorSandboxWorkspaceManifestWriteResult(
        manifest_write_status="written", source_message_id=creation_message.id,
        source_workspace_creation_verified=True, workspace_path=workspace_path,
        workspace_root=workspace_root, workspace_path_within_root=True,
        manifest_file_path=manifest_path.as_posix(), manifest_file_written=True,
        manifest_write_summary="Internal workspace manifest written.", recommended_next_step="Write the candidate file.",
        **common,
    )
    manifest_message = _create_p25_evidence_message(
        msg_repo, session_id=session_id, project_id=project_id, task_id=task_id,
        intent="sandbox_workspace_manifest_write", source_detail=P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
        action={"type": P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE, **manifest.model_dump(mode="json")},
        content="P21-C workspace manifest written.",
    )
    candidate = ProjectDirectorSandboxCandidateFileWriteResult(
        candidate_write_status="written", source_message_id=manifest_message.id,
        source_manifest_write_status="written", source_manifest_write_message_bound=True,
        source_manifest_write_verified=True, source_workspace_creation_message_id=creation_message.id,
        source_operation_manifest_message_id=operation_message.id, workspace_path=workspace_path,
        workspace_root=workspace_root, workspace_path_within_root=True,
        internal_manifest_file_path=manifest_path.as_posix(), internal_manifest_verified=True,
        candidate_files_requested_count=1, candidate_files_written_count=1,
        candidate_written_files=[{"relative_path": "src/example.py", "workspace_file_path": (environment["workspace_path"] / "src/example.py").as_posix(), "operation": "update", "content_size_bytes": 20}],
        candidate_business_files_written=True, business_file_written=True,
        candidate_write_summary="Candidate file written in sandbox.", recommended_next_step="Generate a readonly diff.",
        **common,
    )
    candidate_message = _create_p25_evidence_message(
        msg_repo, session_id=session_id, project_id=project_id, task_id=task_id,
        intent="sandbox_candidate_files_write", source_detail=P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
        action={"type": P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE, **candidate.model_dump(mode="json")},
        content="P21-C candidate file written.",
    )
    environment["initial_candidate_message_id"] = candidate_message.id
    unified_diff = "--- a/src/example.py\n+++ b/src/example.py\n@@ -1 +1 @@\n-value = 'base'\n+value = 'candidate'\n"
    environment["unified_diff"] = unified_diff
    environment["diff_sha256"] = hashlib.sha256(unified_diff.encode("utf-8")).hexdigest()
    diff = ProjectDirectorSandboxCandidateDiffResult(
        diff_generation_status="generated", source_message_id=candidate_message.id,
        source_candidate_write_status="written", source_candidate_write_message_bound=True,
        source_candidate_write_verified=True, source_workspace_manifest_write_message_id=manifest_message.id,
        source_workspace_creation_message_id=creation_message.id, source_operation_manifest_message_id=operation_message.id,
        workspace_path=workspace_path, workspace_root=workspace_root, workspace_path_within_root=True,
        internal_manifest_file_path=manifest_path.as_posix(), internal_manifest_verified=True,
        repo_root=repository_root, base_evidence_schema_version=P21_C_SANDBOX_CANDIDATE_DIFF_BASE_EVIDENCE_SCHEMA_VERSION,
        base_commit_sha=environment["base_commit_sha"], base_snapshot_fingerprint=base_snapshot_fingerprint,
        base_content_source=P21_C_SANDBOX_CANDIDATE_DIFF_BASE_CONTENT_SOURCE_EXACT_GIT_COMMIT_OBJECT,
        readonly_base_snapshot_verified=True, target_file_content_read=True, candidate_file_content_read=True,
        readonly_real_diff_generated=True, real_diff_generated=True, diff_file_count=1,
        diff_bytes=len(unified_diff.encode()), unified_diff_text=unified_diff,
        diff_entries=[{"relative_path": "src/example.py", "operation": "update", "target_file_path": (environment["repository_root"] / "src/example.py").as_posix(), "candidate_file_path": (environment["workspace_path"] / "src/example.py").as_posix(), "target_file_existed": True, "candidate_file_existed": True, "target_file_content_read": True, "candidate_file_content_read": True, "unified_diff": unified_diff, "diff_bytes": len(unified_diff.encode())}],
        candidate_files_considered_count=1, candidate_files_diffed_count=1,
        diff_generation_summary="Readonly diff generated from the exact base commit.",
        recommended_next_step="Review the readonly diff.",
        **common,
    )
    diff_message = _create_p25_evidence_message(
        msg_repo, session_id=session_id, project_id=project_id, task_id=task_id,
        intent="sandbox_candidate_diff_generate", source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
        action={"type": P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE, **diff.model_dump(mode="json")},
        content="P21-C readonly diff generated.",
    )
    environment["initial_diff_message_id"] = diff_message.id
    diff_sha256 = environment["diff_sha256"]
    review_action = _valid_review_action_d3(
        verdict="changes_required", risk_level="medium", session_id=session_id, task_id=task_id,
    )
    review_action.update({
        "source_preflight_message_id": str(candidate_message.id),
        "source_diff_message_id": str(diff_message.id),
        "source_diff_sha256": diff_sha256, "review_prompt_sha256": _sha("p25-review-prompt"),
        "raw_output_sha256": _sha("p25-review-output"), "review_output_schema_version": REVIEW_OUTPUT_SCHEMA_VERSION,
        "workspace_path": workspace_path, "workspace_path_within_root": True,
        "unified_diff_text": unified_diff, "diff_bytes": len(unified_diff.encode()),
        "diff_entries": [{"relative_path": "src/example.py", "unified_diff": unified_diff, "operation": "update"}],
        "diff_file_count": 1,
    })
    review_message = _create_p25_evidence_message(
        msg_repo, session_id=session_id, project_id=project_id, task_id=task_id,
        intent="sandbox_candidate_diff_readonly_review_execution",
        source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
        action=review_action, content="P21-C readonly review completed.",
    )
    msg_repo.commit()
    return review_message.id



@dataclass(slots=True)
class RealP25AttemptZeroPackageContext:
    engine: object
    session_local: object
    session: object
    msg_repo: object
    environment: dict[str, object]
    session_id: UUID
    project_id: UUID
    task_id: UUID
    run_id: UUID
    source_p23_consumption_message_id: UUID
    package_service: ProjectDirectorBoundedReworkPackagePreparationService
    evidence_resolver: ProjectDirectorBoundedReworkEvidenceResolver

    def close(self) -> None:
        self.session.close()
        self.engine.dispose()


def build_real_p25_attempt_zero_package_context(
    tmp_path: Path,
) -> RealP25AttemptZeroPackageContext:
    """Persist the exact P21-C -> P23 inputs consumed by P25-B."""

    engine = make_test_engine(str(tmp_path / "real-p25-package-chain.db"))
    session_local = make_session_factory(engine)
    session_id, project_id, task_id = uuid4(), uuid4(), uuid4()
    setup_session = session_local()
    seed_base_records(
        setup_session,
        session_id=session_id,
        project_id=project_id,
        task_id=task_id,
        task_status="pending",
    )
    task_row = setup_session.get(TaskTable, task_id)
    assert task_row is not None
    task_row.owner_role_code = "architect"
    setup_session.commit()
    setup_session.close()

    session, msg_repo, session_repo, task_repo, run_repo, _ = make_repos(session_local)
    environment = _create_p25_repository_and_workspace(tmp_path, session_id)
    _persist_minimal_p25_control_plane(
        session,
        session_id=session_id,
        project_id=project_id,
        task_id=task_id,
        environment=environment,
    )
    root_diff_service = _P25EvidenceDiff(environment)
    root_handoff_service = _P25EvidenceHandoff(environment)
    root_p22_service = _make_p22_service(
        session,
        msg_repo,
        session_repo,
        task_repo,
        candidate_diff_service=root_diff_service,
        review_handoff_service=root_handoff_service,
    )
    root_review_message_id = _seed_real_p20_p21_review_chain(
        msg_repo,
        session_id=session_id,
        project_id=project_id,
        task_id=task_id,
        environment=environment,
    )
    root_review_row = session.get(ProjectDirectorMessageTable, root_review_message_id)
    assert root_review_row is not None
    root_review_actions = json.loads(root_review_row.suggested_actions_json)
    assert len(root_review_actions) == 1
    root_review_actions[0]["findings"] = [
        {
            "finding_id": "root-p25-package-finding",
            "severity": "medium",
            "title": "Bounded root review finding",
            "summary": "The reviewed candidate needs one bounded correction.",
            "evidence_paths": ["src/example.py"],
            "recommended_action": "Apply the bounded correction.",
        }
    ]
    root_review_actions[0]["recommended_next_step"] = (
        "Prepare the bounded rework package."
    )
    root_review_row.suggested_actions_json = json.dumps(root_review_actions)
    session.commit()
    root_p22 = root_p22_service.orchestrate_post_review(
        session_id=session_id,
        source_task_id=task_id,
        source_review_message_id=root_review_message_id,
    )
    assert root_p22.message is not None

    root_intent_service = ProjectDirectorProtectedTransitionDispatchIntentService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
    )
    root_intent = root_intent_service.prepare_protected_transition_dispatch_intent(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=root_p22.message.id,
    )
    assert root_intent.message is not None

    freshness_service = ProjectDirectorProtectedTransitionEvidenceFreshnessService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        review_handoff_service=root_handoff_service,
        candidate_diff_service=root_diff_service,
    )
    preflight_service = ProjectDirectorProtectedTransitionDispatchConsumptionPreflightService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        dispatch_intent_service=root_intent_service,
        freshness_service=freshness_service,
        task_readiness_service=FakeTaskReadinessService(),
        task_state_machine_service=FakeTaskStateMachineService(),
        budget_guard_service=FakeBudgetGuardService(session=session),
    )
    consumption_service = ProjectDirectorProtectedTransitionDispatchConsumptionService(
        session_repository=session_repo,
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        preflight_service=preflight_service,
        task_readiness_service=FakeTaskReadinessService(),
        task_state_machine_service=FakeTaskStateMachineService(),
        task_router_service=P25FakeTaskRouterService(),
        budget_guard_service=FakeBudgetGuardService(session=session),
    )
    root_preflight = preflight_service.prepare_protected_transition_dispatch_consumption_preflight(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=root_intent.message.id,
    )
    assert root_preflight.message is not None
    root_consumption = consumption_service.consume_protected_transition_dispatch_preflight(
        session_id=session_id,
        source_task_id=task_id,
        source_message_id=root_preflight.message.id,
    )
    assert root_consumption.message is not None

    evidence_resolver = ProjectDirectorBoundedReworkEvidenceResolver(
        message_repository=msg_repo,
        task_repository=task_repo,
        run_repository=run_repo,
        plan_version_repository=ProjectDirectorPlanVersionRepository(session),
        repository_binding_config_repository=ProjectDirectorRepositoryBindingConfigRepository(session),
        skill_binding_config_repository=ProjectDirectorSkillBindingConfigRepository(session),
        verification_config_repository=ProjectDirectorVerificationConfigRepository(session),
        repository_workspace_repository=RepositoryWorkspaceRepository(session),
        freshness_service=freshness_service,
    )
    package_service = ProjectDirectorBoundedReworkPackagePreparationService(
        message_repository=msg_repo,
        dispatch_consumption_service=consumption_service,
        dispatch_intent_service=root_intent_service,
        evidence_resolver=evidence_resolver,
    )
    return RealP25AttemptZeroPackageContext(
        engine=engine,
        session_local=session_local,
        session=session,
        msg_repo=msg_repo,
        environment=environment,
        session_id=session_id,
        project_id=project_id,
        task_id=task_id,
        run_id=root_consumption.result.run_id,
        source_p23_consumption_message_id=root_consumption.message.id,
        package_service=package_service,
        evidence_resolver=evidence_resolver,
    )
