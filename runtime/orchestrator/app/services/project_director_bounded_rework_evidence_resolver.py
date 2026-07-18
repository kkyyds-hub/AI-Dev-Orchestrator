"""Readonly evidence reconstruction for P25 bounded rework preparation."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Literal
from uuid import UUID

from pydantic import ValidationError

from app.domain.project_director_bounded_rework_contract import (
    ProjectDirectorBoundedReworkModelSelection,
    ProjectDirectorBoundedReworkRepositoryBinding,
    ProjectDirectorBoundedReworkRoleSelection,
    ProjectDirectorBoundedReworkSkillSelection,
    ProjectDirectorBoundedReworkVerificationRequirement,
    ProjectDirectorBoundedReworkWorkspaceBinding,
    compute_p25_contract_sha256,
    validate_repository_relative_path,
)
from app.domain.project_director_bounded_rework_candidate_diff import (
    ProjectDirectorBoundedReworkCandidateDiff,
)
from app.domain.project_director_protected_transition_dispatch_intent import (
    ProjectDirectorProtectedTransitionDispatchIntentResult,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
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
from app.domain.project_director_sandbox_candidate_diff_review_output import (
    ProjectDirectorSandboxCandidateDiffValidatedReviewOutput,
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
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
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
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.repositories.run_repository import RunRepository
from app.repositories.task_repository import TaskRepository
from app.services.project_director_protected_transition_evidence_freshness_service import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessService,
)
from app.services.project_director_bounded_rework_review_outcome_evidence_adapter import (
    P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
    ProjectDirectorBoundedReworkReviewOutcomeEvidenceAdapter,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_file_write_service import (
    P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
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


_LOWER_HEX_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PLAN_LOCATOR = re.compile(
    r"^pdv:(?P<plan_id>[0-9a-fA-F-]{36}):(?P<version_no>[1-9][0-9]*)$"
)

EvidenceResolutionStatus = Literal["resolved", "blocked"]
RepositoryHeadReader = Callable[[str], str]


@dataclass(frozen=True, slots=True)
class ProjectDirectorBoundedReworkEvidenceSnapshot:
    """Immutable, fully revalidated evidence consumed by package preparation."""

    session_id: UUID
    project_id: UUID
    source_task_id: UUID
    source_run_id: UUID
    source_review_message_id: UUID
    source_review_fingerprint: str
    source_review_semantic_fingerprint: str
    root_review_message_id: UUID
    root_review_fingerprint: str
    root_review_semantic_fingerprint: str
    source_freshness_message_id: UUID

    review_output: ProjectDirectorSandboxCandidateDiffValidatedReviewOutput
    review_scope_paths: tuple[str, ...]
    repository_binding: ProjectDirectorBoundedReworkRepositoryBinding
    repository_root: str
    repository_binding_fingerprint: str
    repository_allowed_paths: tuple[str, ...]
    workspace_binding: ProjectDirectorBoundedReworkWorkspaceBinding
    workspace_root: str
    workspace_path: str
    workspace_binding_fingerprint: str
    workspace_manifest_allowed_paths: tuple[str, ...]
    task_plan_allowed_paths: tuple[str, ...]
    trusted_forbidden_paths: tuple[str, ...]

    base_commit_sha: str
    base_snapshot_fingerprint: str
    source_candidate_diff_message_id: UUID
    source_candidate_diff_sha256: str
    source_candidate_diff_fingerprint: str
    source_candidate_diff_paths: tuple[str, ...]

    confirmed_acceptance_criteria: tuple[str, ...]
    verification_requirements: tuple[
        ProjectDirectorBoundedReworkVerificationRequirement,
        ...,
    ]
    selected_model: ProjectDirectorBoundedReworkModelSelection
    selected_skills: tuple[ProjectDirectorBoundedReworkSkillSelection, ...]
    selected_role: ProjectDirectorBoundedReworkRoleSelection
    snapshot_fingerprint: str


@dataclass(frozen=True, slots=True)
class ProjectDirectorBoundedReworkEvidenceResolution:
    status: EvidenceResolutionStatus
    snapshot: ProjectDirectorBoundedReworkEvidenceSnapshot | None
    blocked_reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PersistedBaseCommitSource:
    record_identity: str
    source_fingerprint: str
    expected_base_commit_sha: str
    persisted_source_base_snapshot_fingerprint: str


class _Blocked(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorBoundedReworkEvidenceResolver:
    """Resolve repository, workspace, diff, plan, and execution facts read-only."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        task_repository: TaskRepository,
        run_repository: RunRepository,
        plan_version_repository: ProjectDirectorPlanVersionRepository,
        repository_binding_config_repository: (
            ProjectDirectorRepositoryBindingConfigRepository
        ),
        skill_binding_config_repository: ProjectDirectorSkillBindingConfigRepository,
        verification_config_repository: ProjectDirectorVerificationConfigRepository,
        repository_workspace_repository: RepositoryWorkspaceRepository,
        freshness_service: ProjectDirectorProtectedTransitionEvidenceFreshnessService,
        repository_head_reader: RepositoryHeadReader | None = None,
    ) -> None:
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._run_repository = run_repository
        self._plan_version_repository = plan_version_repository
        self._repository_binding_config_repository = (
            repository_binding_config_repository
        )
        self._skill_binding_config_repository = skill_binding_config_repository
        self._verification_config_repository = verification_config_repository
        self._repository_workspace_repository = repository_workspace_repository
        self._freshness_service = freshness_service
        self._repository_head_reader = (
            repository_head_reader or self._read_repository_head
        )

    def resolve_bounded_rework_evidence_snapshot(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
        source_review_message_id: UUID,
        source_review_fingerprint: str,
        source_review_semantic_fingerprint: str,
        source_freshness_message_id: UUID,
        source_diff_message_id: UUID,
    ) -> ProjectDirectorBoundedReworkEvidenceResolution:
        """Build one safe immutable snapshot without performing DB writes."""

        caller_had_transaction = self._message_repository._session.in_transaction()
        try:
            snapshot = self._resolve(
                session_id=session_id,
                project_id=project_id,
                source_task_id=source_task_id,
                source_run_id=source_run_id,
                source_review_message_id=source_review_message_id,
                source_review_fingerprint=source_review_fingerprint,
                source_review_semantic_fingerprint=(
                    source_review_semantic_fingerprint
                ),
                source_freshness_message_id=source_freshness_message_id,
                source_diff_message_id=source_diff_message_id,
            )
        except _Blocked as exc:
            return ProjectDirectorBoundedReworkEvidenceResolution(
                status="blocked",
                snapshot=None,
                blocked_reasons=(exc.reason,),
            )
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return ProjectDirectorBoundedReworkEvidenceResolution(
                status="blocked",
                snapshot=None,
                blocked_reasons=("workspace_invalid",),
            )
        else:
            return ProjectDirectorBoundedReworkEvidenceResolution(
                status="resolved",
                snapshot=snapshot,
                blocked_reasons=(),
            )
        finally:
            if (
                not caller_had_transaction
                and self._message_repository._session.in_transaction()
            ):
                self._message_repository._session.rollback()

    def revalidate_bounded_rework_evidence_snapshot(
        self,
        snapshot: ProjectDirectorBoundedReworkEvidenceSnapshot,
    ) -> ProjectDirectorBoundedReworkEvidenceResolution:
        """Rebuild a snapshot and require byte-stable semantic identity."""

        resolution = self.resolve_bounded_rework_evidence_snapshot(
            session_id=snapshot.session_id,
            project_id=snapshot.project_id,
            source_task_id=snapshot.source_task_id,
            source_run_id=snapshot.source_run_id,
            source_review_message_id=snapshot.source_review_message_id,
            source_review_fingerprint=snapshot.source_review_fingerprint,
            source_review_semantic_fingerprint=(
                snapshot.source_review_semantic_fingerprint
            ),
            source_freshness_message_id=snapshot.source_freshness_message_id,
            source_diff_message_id=snapshot.source_candidate_diff_message_id,
        )
        if resolution.snapshot is None or resolution.blocked_reasons:
            return resolution
        if (
            resolution.snapshot.snapshot_fingerprint
            != snapshot.snapshot_fingerprint
            or resolution.snapshot != snapshot
        ):
            return ProjectDirectorBoundedReworkEvidenceResolution(
                status="blocked",
                snapshot=None,
                blocked_reasons=("source_diff_mismatch",),
            )
        return resolution

    def _resolve(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
        source_review_message_id: UUID,
        source_review_fingerprint: str,
        source_review_semantic_fingerprint: str,
        source_freshness_message_id: UUID,
        source_diff_message_id: UUID,
    ) -> ProjectDirectorBoundedReworkEvidenceSnapshot:
        review_message = self._message_repository.get_by_id(source_review_message_id)
        if (
            review_message is not None
            and review_message.intent == P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT
        ):
            return self._resolve_p25_h_review_outcome(
                session_id=session_id,
                project_id=project_id,
                source_task_id=source_task_id,
                source_run_id=source_run_id,
                source_review_message_id=source_review_message_id,
                source_review_fingerprint=source_review_fingerprint,
                source_review_semantic_fingerprint=source_review_semantic_fingerprint,
                source_freshness_message_id=source_freshness_message_id,
                source_diff_message_id=source_diff_message_id,
            )

        task = self._task_repository.get_by_id(source_task_id)
        run = self._run_repository.get_by_id(source_run_id)
        if (
            task is None
            or task.project_id != project_id
            or run is None
            or run.task_id != source_task_id
            or run.strategy_decision is None
        ):
            raise _Blocked("authority_invalid")

        review_action = self._exact_action(
            review_message,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            intent="sandbox_candidate_diff_readonly_review_execution",
            source_detail=(
                P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL
            ),
            action_type=(
                P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE
            ),
        )
        review_revalidation = ProjectDirectorSandboxCandidateDiffReviewDispositionService.revalidate_persisted_review_result_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=source_review_message_id,
            source_review_message=review_message,
        )
        if (
            review_revalidation.blocked_reasons
            or review_revalidation.review_result_fingerprint
            != source_review_fingerprint
            or review_revalidation.source_diff_message_id != source_diff_message_id
        ):
            raise _Blocked("authority_invalid")
        review_output = self._review_output(review_action)
        if review_output.verdict != "changes_required":
            raise _Blocked("review_findings_invalid")

        freshness = self._freshness_service.revalidate_current_automatic_transition_evidence_from_persisted_freshness(
            session_id=session_id,
            source_task_id=source_task_id,
            source_freshness_message_id=source_freshness_message_id,
        )
        if (
            freshness.freshness_status != "ready"
            or freshness.blocked_reasons
            or freshness.source_review_message_id != source_review_message_id
            or freshness.source_diff_message_id != source_diff_message_id
            or freshness.review_result_fingerprint != source_review_fingerprint
            or freshness.reviewed_diff_sha256 != freshness.current_diff_sha256
            or freshness.reviewed_scope_paths != freshness.current_scope_paths
            or not freshness.workspace_path_within_root
        ):
            raise _Blocked("source_diff_mismatch")

        diff_message = self._message_repository.get_by_id(source_diff_message_id)
        diff_action = self._exact_action(
            diff_message,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            intent="sandbox_candidate_diff_generate",
            source_detail=P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
            action_type=P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
        )
        diff = self._domain_from_action(
            ProjectDirectorSandboxCandidateDiffResult,
            diff_action,
        )
        diff_sha = hashlib.sha256(diff.unified_diff_text.encode("utf-8")).hexdigest()
        diff_paths = self._normalized_paths(
            tuple(entry.relative_path for entry in diff.diff_entries),
            allow_empty=False,
        )
        review_scope = self._normalized_paths(
            tuple(review_revalidation.review_scope_paths or ()),
            allow_empty=False,
        )
        if (
            diff.diff_generation_status != "generated"
            or not diff.readonly_real_diff_generated
            or not diff.real_diff_generated
            or not diff.source_candidate_write_message_bound
            or not diff.source_candidate_write_verified
            or not diff.internal_manifest_verified
            or diff.source_task_id != source_task_id
            or diff.workspace_path != freshness.workspace_path
            or not diff.workspace_path_within_root
            or diff_sha != review_revalidation.source_diff_sha256
            or diff_sha != freshness.reviewed_diff_sha256
            or diff_paths != review_scope
        ):
            raise _Blocked("source_diff_mismatch")

        evidence = self._workspace_evidence_chain(
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            diff=diff,
        )
        (
            workspace_creation_message,
            workspace_creation,
            manifest_message,
            manifest_write,
            operation_manifest,
            preflight,
        ) = evidence

        plan, locator = self._confirmed_plan(task.source_draft_id, session_id, project_id)
        repository_binding_config = (
            self._repository_binding_config_repository.get_by_plan_version_id(
                plan.id
            )
        )
        skill_config = self._skill_binding_config_repository.get_by_plan_version_id(
            plan.id
        )
        verification_config = (
            self._verification_config_repository.get_by_plan_version_id(plan.id)
        )
        repository_workspace = (
            self._repository_workspace_repository.get_by_project_id(project_id)
        )
        if (
            repository_binding_config is None
            or repository_binding_config.status != "confirmed"
            or repository_binding_config.project_id != project_id
            or repository_binding_config.source_draft_id != locator
            or repository_binding_config.confirmed_at is None
            or len(repository_binding_config.repository_bindings) != 1
            or skill_config is None
            or skill_config.status != "confirmed"
            or skill_config.project_id != project_id
            or skill_config.source_draft_id != locator
            or skill_config.confirmed_at is None
            or verification_config is None
            or verification_config.status != "confirmed"
            or verification_config.project_id != project_id
            or verification_config.source_draft_id != locator
            or verification_config.confirmed_at is None
            or repository_workspace is None
            or repository_workspace.project_id != project_id
        ):
            raise _Blocked("authority_invalid")

        binding = repository_binding_config.repository_bindings[0]
        repository_root = self._absolute_path(binding.target)
        if repository_root != self._absolute_path(repository_workspace.root_path):
            raise _Blocked("workspace_invalid")
        repository_allowed = self._normalized_paths(
            tuple(binding.focus_paths),
            allow_empty=False,
        )
        repository_binding_fingerprint = compute_p25_contract_sha256(
            {
                "binding_config_id": repository_binding_config.id,
                "plan_version_id": plan.id,
                "project_id": project_id,
                "binding": binding,
                "repository_workspace_id": repository_workspace.id,
                "repository_root": repository_root,
                "repository_allowed_paths": repository_allowed,
            }
        )
        repository_binding = ProjectDirectorBoundedReworkRepositoryBinding(
            repository_binding_id=repository_binding_config.id,
            project_id=project_id,
            repository_root=repository_root,
            repository_binding_fingerprint=repository_binding_fingerprint,
        )

        workspace_path = self._absolute_path(workspace_creation.workspace_path)
        workspace_root = self._absolute_path(workspace_creation.workspace_root)
        if (
            workspace_path != self._absolute_path(diff.workspace_path)
            or workspace_path != self._absolute_path(manifest_write.workspace_path)
            or workspace_root != self._absolute_path(manifest_write.workspace_root)
            or PurePosixPath(workspace_root) not in PurePosixPath(workspace_path).parents
        ):
            raise _Blocked("workspace_invalid")
        manifest_content_fingerprint = self._validate_manifest_file(
            manifest_write=manifest_write,
            session_id=session_id,
            source_task_id=source_task_id,
            workspace_creation_message_id=workspace_creation_message.id,
            workspace_path=workspace_path,
            workspace_root=workspace_root,
        )
        manifest_allowed_paths = self._normalized_paths(
            tuple(operation_manifest.allowed_operation_paths),
            allow_empty=False,
        )
        task_plan_allowed_paths = self._normalized_paths(
            tuple(preflight.accepted_operation_paths),
            allow_empty=False,
        )
        if manifest_allowed_paths != diff_paths:
            raise _Blocked("scope_invalid")
        workspace_binding_fingerprint = compute_p25_contract_sha256(
            {
                "workspace_creation_message_id": workspace_creation_message.id,
                "workspace_creation": workspace_creation,
                "workspace_manifest_message_id": manifest_message.id,
                "workspace_manifest": manifest_write,
                "workspace_manifest_content_fingerprint": (
                    manifest_content_fingerprint
                ),
                "operation_manifest": operation_manifest,
                "workspace_path": workspace_path,
                "workspace_root": workspace_root,
            }
        )
        workspace_binding = ProjectDirectorBoundedReworkWorkspaceBinding(
            workspace_binding_id=workspace_creation_message.id,
            project_id=project_id,
            workspace_path=workspace_path,
            workspace_root=workspace_root,
            workspace_binding_fingerprint=workspace_binding_fingerprint,
        )

        source_diff_fingerprint = compute_p25_contract_sha256(
            {
                "message_id": source_diff_message_id,
                "message_sequence_no": diff_message.sequence_no if diff_message else None,
                "action": diff_action,
                "source_candidate_diff_sha256": diff_sha,
                "source_candidate_diff_paths": diff_paths,
            }
        )
        persisted_base = self._persisted_base_commit_source(
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            source_run_id=source_run_id,
            repository_workspace_id=repository_workspace.id,
            repository_root=repository_root,
            workspace_creation_message_id=workspace_creation_message.id,
            workspace_manifest_message_id=manifest_message.id,
            operation_manifest_message_id=diff.source_operation_manifest_message_id,
            workspace_path=workspace_path,
            source_candidate_diff_message=diff_message,
            source_candidate_diff_action=diff_action,
            source_candidate_diff=diff,
            source_candidate_diff_message_id=source_diff_message_id,
            source_candidate_diff_fingerprint=source_diff_fingerprint,
        )
        base_commit_sha = persisted_base.expected_base_commit_sha
        if (
            not persisted_base.record_identity
            or persisted_base.record_identity != persisted_base.record_identity.strip()
            or not _LOWER_HEX_SHA256.fullmatch(persisted_base.source_fingerprint)
            or not _LOWER_HEX_GIT_COMMIT.fullmatch(base_commit_sha)
        ):
            raise _Blocked("authority_invalid")
        try:
            current_head = self._repository_head_reader(repository_root).strip()
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            raise _Blocked("base_commit_mismatch") from exc
        if (
            not _LOWER_HEX_GIT_COMMIT.fullmatch(current_head)
            or current_head != base_commit_sha
        ):
            raise _Blocked("base_commit_mismatch")
        base_snapshot_fingerprint = compute_p25_contract_sha256(
            {
                "persisted_base_commit_source_record_identity": (
                    persisted_base.record_identity
                ),
                "persisted_base_commit_source_fingerprint": (
                    persisted_base.source_fingerprint
                ),
                "persisted_source_base_snapshot_fingerprint": (
                    persisted_base.persisted_source_base_snapshot_fingerprint
                ),
                "expected_base_commit_sha": base_commit_sha,
                "repository_binding_fingerprint": repository_binding_fingerprint,
                "source_candidate_diff_fingerprint": source_diff_fingerprint,
            }
        )

        selected_model, selected_skills, selected_role = self._execution_config(
            run=run,
            task=task,
            skill_config=skill_config,
        )
        acceptance_criteria = tuple(
            task.acceptance_criteria or plan.acceptance_criteria
        )
        if (
            not acceptance_criteria
            or len(acceptance_criteria) != len(set(acceptance_criteria))
            or any(not item.strip() or item != item.strip() for item in acceptance_criteria)
        ):
            raise _Blocked("authority_invalid")
        verification_requirements = self._verification_requirements(
            verification_config=verification_config,
            owner_role_code=selected_role.role_code,
        )
        trusted_forbidden_paths = self._trusted_forbidden_paths(
            plan_out_of_scope=tuple(plan.project_scope.out_of_scope),
            repository_ignores=tuple(repository_workspace.ignore_rule_summary),
            preflight_blocked=tuple(preflight.blocked_operation_paths),
            manifest_blocked=tuple(operation_manifest.blocked_operation_paths),
        )

        payload: dict[str, Any] = {
            "session_id": session_id,
            "project_id": project_id,
            "source_task_id": source_task_id,
            "source_run_id": source_run_id,
            "source_review_message_id": source_review_message_id,
            "source_review_fingerprint": source_review_fingerprint,
            "source_review_semantic_fingerprint": source_review_semantic_fingerprint,
            "root_review_message_id": source_review_message_id,
            "root_review_fingerprint": source_review_fingerprint,
            "root_review_semantic_fingerprint": source_review_semantic_fingerprint,
            "source_freshness_message_id": source_freshness_message_id,
            "review_output": review_output,
            "review_scope_paths": review_scope,
            "repository_binding": repository_binding,
            "repository_root": repository_root,
            "repository_binding_fingerprint": repository_binding_fingerprint,
            "repository_allowed_paths": repository_allowed,
            "workspace_binding": workspace_binding,
            "workspace_root": workspace_root,
            "workspace_path": workspace_path,
            "workspace_binding_fingerprint": workspace_binding_fingerprint,
            "workspace_manifest_allowed_paths": manifest_allowed_paths,
            "task_plan_allowed_paths": task_plan_allowed_paths,
            "trusted_forbidden_paths": trusted_forbidden_paths,
            "base_commit_sha": base_commit_sha,
            "base_snapshot_fingerprint": base_snapshot_fingerprint,
            "source_candidate_diff_message_id": source_diff_message_id,
            "source_candidate_diff_sha256": diff_sha,
            "source_candidate_diff_fingerprint": source_diff_fingerprint,
            "source_candidate_diff_paths": diff_paths,
            "confirmed_acceptance_criteria": acceptance_criteria,
            "verification_requirements": verification_requirements,
            "selected_model": selected_model,
            "selected_skills": selected_skills,
            "selected_role": selected_role,
        }
        return ProjectDirectorBoundedReworkEvidenceSnapshot(
            **payload,
            snapshot_fingerprint=compute_p25_contract_sha256(payload),
        )

    def _resolve_p25_h_review_outcome(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
        source_review_message_id: UUID,
        source_review_fingerprint: str,
        source_review_semantic_fingerprint: str,
        source_freshness_message_id: UUID,
        source_diff_message_id: UUID,
    ) -> ProjectDirectorBoundedReworkEvidenceSnapshot:
        """Keep P25-H current evidence while rebuilding immutable P21-C facts."""

        current = ProjectDirectorBoundedReworkReviewOutcomeEvidenceAdapter(
            message_repository=self._message_repository
        ).load_validated_outcome(
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            source_review_outcome_message_id=source_review_message_id,
        )
        outcome = current.outcome
        if (
            outcome is None
            or current.message is None
            or outcome.review_outcome_id != source_review_message_id
            or outcome.review_result_fingerprint != source_review_fingerprint
            or outcome.review_semantic_fingerprint != source_review_semantic_fingerprint
            or outcome.exact_run_id != source_run_id
            or outcome.authority.session_id != session_id
            or outcome.authority.project_id != project_id
            or outcome.authority.source_task_id != source_task_id
            or outcome.rework_attempt_limit != 3
        ):
            raise _Blocked("authority_invalid")

        self._revalidate_current_p25_freshness(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=source_review_message_id,
            source_review_fingerprint=source_review_fingerprint,
            source_freshness_message_id=source_freshness_message_id,
            source_diff_message_id=source_diff_message_id,
        )
        candidate_diff = self._load_p25_candidate_diff(
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            source_candidate_diff_message_id=source_diff_message_id,
            outcome=outcome,
        )
        parent_intent = self._load_parent_p23_intent(
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            source_intent_message_id=outcome.authority.source_p23_dispatch_intent_id,
        )
        if (
            parent_intent.source_review_message_id
            != outcome.authority.source_review_message_id
            or parent_intent.review_result_fingerprint
            != outcome.authority.source_review_fingerprint
            or parent_intent.review_semantic_fingerprint
            != outcome.authority.source_review_semantic_fingerprint
            or parent_intent.source_freshness_message_id is None
        ):
            raise _Blocked("history_invalid")

        root = self._resolve(
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            source_run_id=outcome.authority.source_run_id,
            source_review_message_id=outcome.authority.source_review_message_id,
            source_review_fingerprint=outcome.authority.source_review_fingerprint,
            source_review_semantic_fingerprint=(
                outcome.authority.source_review_semantic_fingerprint
            ),
            source_freshness_message_id=parent_intent.source_freshness_message_id,
            source_diff_message_id=parent_intent.source_p25_candidate_diff_message_id
            or self._review_source_diff_message_id(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=outcome.authority.source_review_message_id,
            ),
        )
        adapter = outcome.adapter_result
        if adapter is None:
            raise _Blocked("review_findings_invalid")
        review_output = ProjectDirectorSandboxCandidateDiffValidatedReviewOutput(
            review_status=adapter.review_status,
            verdict=adapter.verdict,
            risk_level=adapter.risk_level,
            summary=adapter.summary,
            findings=adapter.findings,
            recommended_next_step=adapter.recommended_next_step,
        )
        payload = {
            **{
                name: getattr(root, name)
                for name in ProjectDirectorBoundedReworkEvidenceSnapshot.__dataclass_fields__
            },
            "source_review_message_id": source_review_message_id,
            "source_review_fingerprint": source_review_fingerprint,
            "source_review_semantic_fingerprint": source_review_semantic_fingerprint,
            "source_freshness_message_id": source_freshness_message_id,
            "review_output": review_output,
            "review_scope_paths": tuple(outcome.review_scope_paths),
            "source_candidate_diff_message_id": candidate_diff.candidate_diff_id,
            "source_candidate_diff_sha256": candidate_diff.new_diff_sha256,
            "source_candidate_diff_fingerprint": candidate_diff.candidate_diff_fingerprint,
            "source_candidate_diff_paths": tuple(candidate_diff.scope_paths),
        }
        payload.pop("snapshot_fingerprint")
        return ProjectDirectorBoundedReworkEvidenceSnapshot(
            **payload,
            snapshot_fingerprint=compute_p25_contract_sha256(payload),
        )

    def _revalidate_current_p25_freshness(self, **values: Any) -> None:
        freshness = self._freshness_service.revalidate_current_automatic_transition_evidence_from_persisted_freshness(
            session_id=values["session_id"],
            source_task_id=values["source_task_id"],
            source_freshness_message_id=values["source_freshness_message_id"],
        )
        if (
            freshness.freshness_status != "ready"
            or freshness.blocked_reasons
            or freshness.source_review_message_id != values["source_review_message_id"]
            or freshness.source_diff_message_id != values["source_diff_message_id"]
            or freshness.review_result_fingerprint != values["source_review_fingerprint"]
        ):
            raise _Blocked("source_diff_mismatch")

    def _load_p25_candidate_diff(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        source_candidate_diff_message_id: UUID,
        outcome: Any,
    ) -> ProjectDirectorBoundedReworkCandidateDiff:
        message = self._message_repository.get_by_id(source_candidate_diff_message_id)
        action = self._exact_action(
            message,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            intent="bounded_rework_candidate_diff",
            source_detail="p25_g_candidate_diff_generated",
            action_type="p25_bounded_rework_candidate_diff_record",
        )
        diff = self._domain_from_action(ProjectDirectorBoundedReworkCandidateDiff, action)
        if (
            diff.candidate_diff_id != source_candidate_diff_message_id
            or diff.diff_status != "generated"
            or diff.candidate_diff_fingerprint != outcome.source_candidate_diff_fingerprint
            or diff.new_diff_sha256 != outcome.source_candidate_diff_sha256
            or diff.source_package_id != outcome.source_package_id
            or diff.source_attempt_id != outcome.source_attempt_id
            or diff.source_outcome_id != outcome.source_executor_outcome_id
            or diff.authority != outcome.authority
            or diff.exact_task_id != outcome.exact_task_id
            or diff.exact_run_id != outcome.exact_run_id
            or diff.rework_attempt_index != outcome.rework_attempt_index
            or diff.rework_attempt_limit != outcome.rework_attempt_limit
        ):
            raise _Blocked("history_invalid")
        return diff

    def _load_parent_p23_intent(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        source_intent_message_id: UUID,
    ) -> ProjectDirectorProtectedTransitionDispatchIntentResult:
        action = self._exact_action(
            self._message_repository.get_by_id(source_intent_message_id),
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            intent="protected_transition_dispatch_intent",
            source_detail="p23_protected_transition_dispatch_intent_prepared",
            action_type="p23_protected_transition_dispatch_intent_record",
        )
        return self._domain_from_action(
            ProjectDirectorProtectedTransitionDispatchIntentResult, action
        )

    def _review_source_diff_message_id(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_review_message_id: UUID,
    ) -> UUID:
        review = ProjectDirectorSandboxCandidateDiffReviewDispositionService.revalidate_persisted_review_result_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=source_review_message_id,
            source_review_message=self._message_repository.get_by_id(source_review_message_id),
        )
        if review.blocked_reasons or review.source_diff_message_id is None:
            raise _Blocked("history_invalid")
        return review.source_diff_message_id

    def _workspace_evidence_chain(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        diff: ProjectDirectorSandboxCandidateDiffResult,
    ) -> tuple[
        ProjectDirectorMessage,
        ProjectDirectorSandboxWorkspaceCreationResult,
        ProjectDirectorMessage,
        ProjectDirectorSandboxWorkspaceManifestWriteResult,
        ProjectDirectorSandboxOperationManifestGuardResult,
        ProjectDirectorSandboxWritePreflightResult,
    ]:
        required_ids = (
            diff.source_message_id,
            diff.source_workspace_creation_message_id,
            diff.source_workspace_manifest_write_message_id,
            diff.source_operation_manifest_message_id,
        )
        if any(value is None for value in required_ids):
            raise _Blocked("workspace_invalid")
        (
            candidate_write_id,
            workspace_creation_id,
            manifest_write_id,
            operation_manifest_id,
        ) = required_ids
        assert candidate_write_id is not None
        assert workspace_creation_id is not None
        assert manifest_write_id is not None
        assert operation_manifest_id is not None

        candidate_write = self._load_domain_message(
            candidate_write_id,
            ProjectDirectorSandboxCandidateFileWriteResult,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            intent="sandbox_candidate_files_write",
            source_detail=P21_C_SANDBOX_CANDIDATE_FILES_WRITE_SOURCE_DETAIL,
            action_type=P21_C_SANDBOX_CANDIDATE_FILES_WRITE_ACTION_TYPE,
        )[1]
        workspace_creation_message, workspace_creation = self._load_domain_message(
            workspace_creation_id,
            ProjectDirectorSandboxWorkspaceCreationResult,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            intent="sandbox_workspace_create",
            source_detail=P21_C_SANDBOX_WORKSPACE_CREATE_SOURCE_DETAIL,
            action_type=P21_C_SANDBOX_WORKSPACE_CREATE_ACTION_TYPE,
        )
        manifest_message, manifest_write = self._load_domain_message(
            manifest_write_id,
            ProjectDirectorSandboxWorkspaceManifestWriteResult,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            intent="sandbox_workspace_manifest_write",
            source_detail=P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_SOURCE_DETAIL,
            action_type=P21_C_SANDBOX_WORKSPACE_MANIFEST_WRITE_ACTION_TYPE,
        )
        _, operation_manifest = self._load_domain_message(
            operation_manifest_id,
            ProjectDirectorSandboxOperationManifestGuardResult,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            intent="sandbox_operation_manifest_guard",
            source_detail=P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_SOURCE_DETAIL,
            action_type=P21_C_SANDBOX_OPERATION_MANIFEST_GUARD_ACTION_TYPE,
        )
        execution_id = operation_manifest.source_execution_message_id
        if execution_id is None:
            raise _Blocked("workspace_invalid")
        _, execution = self._load_domain_message(
            execution_id,
            ProjectDirectorSandboxWriteExecutionResult,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            intent="sandbox_write_execution",
            source_detail=P21_SANDBOX_WRITE_EXECUTION_SOURCE_DETAIL,
            action_type=P21_SANDBOX_WRITE_EXECUTION_ACTION_TYPE,
        )
        preflight_id = execution.source_message_id
        if preflight_id is None:
            raise _Blocked("scope_invalid")
        _, preflight = self._load_domain_message(
            preflight_id,
            ProjectDirectorSandboxWritePreflightResult,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            intent="sandbox_write_preflight",
            source_detail=P20_SANDBOX_WRITE_PREFLIGHT_SOURCE_DETAIL,
            action_type=P20_SANDBOX_WRITE_PREFLIGHT_ACTION_TYPE,
        )

        allowed = tuple(operation_manifest.allowed_operation_paths)
        if (
            candidate_write.candidate_write_status != "written"
            or not candidate_write.source_manifest_write_verified
            or candidate_write.source_message_id != manifest_write_id
            or candidate_write.source_workspace_creation_message_id
            != workspace_creation_id
            or candidate_write.source_operation_manifest_message_id
            != operation_manifest_id
            or workspace_creation.creation_status not in {"created", "already_exists"}
            or workspace_creation.source_message_id != operation_manifest_id
            or not workspace_creation.source_manifest_message_bound
            or not workspace_creation.source_manifest_verified
            or not workspace_creation.workspace_path_within_root
            or workspace_creation.workspace_path
            != operation_manifest.workspace_path_preview
            or manifest_write.manifest_write_status not in {"written", "overwritten"}
            or manifest_write.source_message_id != workspace_creation_id
            or not manifest_write.source_workspace_creation_verified
            or operation_manifest.manifest_status != "manifested"
            or not operation_manifest.source_workspace_guard_verified
            or execution.execution_status not in {"planned", "simulated"}
            or not execution.source_preflight_message_bound
            or not execution.policy_only_source_verified
            or not execution.no_write_execution
            or execution.blocked_reasons
            or preflight.preflight_status != "passed"
            or not preflight.preflight_message_bound
            or tuple(execution.accepted_operation_paths) != allowed
            or tuple(preflight.accepted_operation_paths) != allowed
        ):
            raise _Blocked("workspace_invalid")
        return (
            workspace_creation_message,
            workspace_creation,
            manifest_message,
            manifest_write,
            operation_manifest,
            preflight,
        )

    def _load_domain_message(
        self,
        message_id: UUID,
        model: type[Any],
        **metadata: Any,
    ) -> tuple[ProjectDirectorMessage, Any]:
        message = self._message_repository.get_by_id(message_id)
        action = self._exact_action(message, **metadata)
        if message is None:
            raise _Blocked("history_invalid")
        return message, self._domain_from_action(model, action)

    @staticmethod
    def _domain_from_action(model: type[Any], action: dict[str, Any]) -> Any:
        try:
            return model.model_validate(
                {name: action.get(name) for name in model.model_fields}
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("history_invalid") from exc

    @staticmethod
    def _review_output(
        action: dict[str, Any],
    ) -> ProjectDirectorSandboxCandidateDiffValidatedReviewOutput:
        try:
            return ProjectDirectorSandboxCandidateDiffValidatedReviewOutput.model_validate(
                {
                    name: action.get(name)
                    for name in ProjectDirectorSandboxCandidateDiffValidatedReviewOutput.model_fields
                }
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("review_findings_invalid") from exc

    @staticmethod
    def _exact_action(
        message: ProjectDirectorMessage | None,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        intent: str,
        source_detail: str,
        action_type: str,
    ) -> dict[str, Any]:
        if (
            message is None
            or message.session_id != session_id
            or message.related_project_id != project_id
            or message.related_task_id != source_task_id
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != intent
            or message.source_detail != source_detail
            or message.requires_confirmation is not False
            or message.token_count is not None
            or message.estimated_cost is not None
            or len(message.suggested_actions) != 1
            or not isinstance(message.suggested_actions[0], dict)
            or message.suggested_actions[0].get("type") != action_type
        ):
            raise _Blocked("history_invalid")
        return message.suggested_actions[0]

    def _confirmed_plan(
        self,
        source_draft_id: str | None,
        session_id: UUID,
        project_id: UUID,
    ) -> tuple[Any, str]:
        match = _PLAN_LOCATOR.fullmatch(source_draft_id or "")
        if match is None:
            raise _Blocked("authority_invalid")
        plan_id = UUID(match.group("plan_id"))
        plan = self._plan_version_repository.get_by_id(plan_id)
        locator = f"pdv:{plan_id}:{match.group('version_no')}"
        if (
            plan is None
            or plan.status != "confirmed"
            or plan.confirmed_at is None
            or plan.session_id != session_id
            or plan.project_id != project_id
            or plan.version_no != int(match.group("version_no"))
        ):
            raise _Blocked("authority_invalid")
        return plan, locator

    @staticmethod
    def _execution_config(
        *,
        run: Any,
        task: Any,
        skill_config: Any,
    ) -> tuple[
        ProjectDirectorBoundedReworkModelSelection,
        tuple[ProjectDirectorBoundedReworkSkillSelection, ...],
        ProjectDirectorBoundedReworkRoleSelection,
    ]:
        decision = run.strategy_decision
        role_code = task.owner_role_code.value if task.owner_role_code else None
        if (
            decision is None
            or role_code is None
            or decision.owner_role_code != task.owner_role_code
            or run.owner_role_code != task.owner_role_code
            or not decision.model_name
            or not decision.model_tier
            or run.model_name != decision.model_name
            or not decision.selected_skill_codes
            or len(decision.selected_skill_codes)
            != len(decision.selected_skill_names)
        ):
            raise _Blocked("authority_invalid")
        confirmed = {
            (item.skill_code, item.skill_name)
            for item in skill_config.skill_bindings
            if item.owner_role_code == role_code
        }
        pairs = tuple(
            zip(
                decision.selected_skill_codes,
                decision.selected_skill_names,
                strict=True,
            )
        )
        if (
            len(pairs) != len(set(pairs))
            or any(pair not in confirmed for pair in pairs)
        ):
            raise _Blocked("authority_invalid")
        return (
            ProjectDirectorBoundedReworkModelSelection(
                model_name=decision.model_name,
                model_tier=decision.model_tier,
            ),
            tuple(
                ProjectDirectorBoundedReworkSkillSelection(
                    skill_code=code,
                    skill_name=name,
                )
                for code, name in pairs
            ),
            ProjectDirectorBoundedReworkRoleSelection(role_code=role_code),
        )

    @staticmethod
    def _verification_requirements(
        *,
        verification_config: Any,
        owner_role_code: str,
    ) -> tuple[ProjectDirectorBoundedReworkVerificationRequirement, ...]:
        mechanisms = tuple(
            item
            for item in verification_config.verification_mechanisms
            if item.owner_role_code in {owner_role_code, "reviewer"}
        )
        if not mechanisms:
            raise _Blocked("authority_invalid")
        requirements: list[ProjectDirectorBoundedReworkVerificationRequirement] = []
        for item in mechanisms:
            if item.review_status == "pending_confirmation":
                raise _Blocked("authority_invalid")
            digest = hashlib.sha256(
                json.dumps(
                    item.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest()[:24]
            description = (
                f"{item.name}: {item.command_or_method}; evidence: "
                f"{item.evidence_required}"
            )
            if len(description) > 1_000:
                raise _Blocked("authority_invalid")
            requirements.append(
                ProjectDirectorBoundedReworkVerificationRequirement(
                    requirement_id=f"verification-{digest}",
                    description=description,
                )
            )
        if len({item.requirement_id for item in requirements}) != len(requirements):
            raise _Blocked("authority_invalid")
        return tuple(requirements)

    @classmethod
    def _trusted_forbidden_paths(
        cls,
        *,
        plan_out_of_scope: tuple[str, ...],
        repository_ignores: tuple[str, ...],
        preflight_blocked: tuple[str, ...],
        manifest_blocked: tuple[str, ...],
    ) -> tuple[str, ...]:
        path_markers = tuple(
            item[len("path:") :]
            for item in (*plan_out_of_scope, *repository_ignores)
            if item.startswith("path:")
        )
        return cls._normalized_paths(
            (*path_markers, *preflight_blocked, *manifest_blocked),
            allow_empty=True,
        )

    @staticmethod
    def _normalized_paths(
        values: tuple[str, ...],
        *,
        allow_empty: bool,
    ) -> tuple[str, ...]:
        normalized: set[str] = set()
        for raw in values:
            if not isinstance(raw, str) or raw != raw.strip():
                raise _Blocked("scope_invalid")
            value = PurePosixPath(raw).as_posix()
            try:
                validate_repository_relative_path(value)
            except ValueError as exc:
                raise _Blocked("scope_invalid") from exc
            normalized.add(value)
        result = tuple(sorted(normalized))
        if not allow_empty and not result:
            raise _Blocked("scope_invalid")
        return result

    @staticmethod
    def _absolute_path(value: str | None) -> str:
        if not isinstance(value, str) or not value or value != value.strip():
            raise _Blocked("workspace_invalid")
        path = PurePosixPath(value)
        if not path.is_absolute() or path.as_posix() != value or ".." in path.parts:
            raise _Blocked("workspace_invalid")
        return value

    @staticmethod
    def _validate_manifest_file(
        *,
        manifest_write: ProjectDirectorSandboxWorkspaceManifestWriteResult,
        session_id: UUID,
        source_task_id: UUID,
        workspace_creation_message_id: UUID,
        workspace_path: str,
        workspace_root: str,
    ) -> str:
        manifest_path = manifest_write.manifest_file_path
        if manifest_path is None:
            raise _Blocked("workspace_invalid")
        try:
            raw = Path(manifest_path).read_bytes()
            payload = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _Blocked("workspace_invalid") from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != "p21-c-d.v1"
            or payload.get("session_id") != str(session_id)
            or payload.get("source_task_id") != str(source_task_id)
            or payload.get("source_message_id")
            != str(workspace_creation_message_id)
            or payload.get("workspace_path") != workspace_path
            or payload.get("workspace_root") != workspace_root
            or payload.get("manifest_file_path") != manifest_path
            or payload.get("internal_manifest_only") is not True
            or payload.get("business_file_write_allowed") is not False
            or payload.get("git_write_performed") is not False
        ):
            raise _Blocked("workspace_invalid")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _persisted_base_commit_source(
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
        repository_workspace_id: UUID,
        repository_root: str,
        workspace_creation_message_id: UUID,
        workspace_manifest_message_id: UUID,
        operation_manifest_message_id: UUID | None,
        workspace_path: str,
        source_candidate_diff_message: ProjectDirectorMessage | None,
        source_candidate_diff_action: dict[str, Any],
        source_candidate_diff: ProjectDirectorSandboxCandidateDiffResult,
        source_candidate_diff_message_id: UUID,
        source_candidate_diff_fingerprint: str,
    ) -> _PersistedBaseCommitSource:
        """Resolve only an exact persisted base source for the P21 diff lineage."""

        message = source_candidate_diff_message
        diff = source_candidate_diff
        if (
            message is None
            or message.id != source_candidate_diff_message_id
            or message.session_id != session_id
            or message.related_project_id != project_id
            or message.related_task_id != source_task_id
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != "sandbox_candidate_diff_generate"
            or message.source_detail != P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL
            or message.requires_confirmation is not False
            or message.token_count is not None
            or message.estimated_cost is not None
            or len(message.suggested_actions) != 1
            or message.suggested_actions[0] != source_candidate_diff_action
            or operation_manifest_message_id is None
        ):
            raise _Blocked("authority_invalid")

        if (
            diff.diff_generation_status != "generated"
            or diff.source_task_id != source_task_id
            or diff.source_message_id is None
            or diff.source_workspace_creation_message_id != workspace_creation_message_id
            or diff.source_workspace_manifest_write_message_id
            != workspace_manifest_message_id
            or diff.source_operation_manifest_message_id
            != operation_manifest_message_id
            or diff.workspace_path != workspace_path
            or not diff.workspace_path_within_root
            or diff.repo_root != repository_root
            or not diff.internal_manifest_verified
            or not diff.source_candidate_write_message_bound
            or not diff.source_candidate_write_verified
            or not diff.readonly_real_diff_generated
            or not diff.real_diff_generated
            or diff.base_evidence_schema_version
            != P21_C_SANDBOX_CANDIDATE_DIFF_BASE_EVIDENCE_SCHEMA_VERSION
            or diff.base_content_source
            != (
                P21_C_SANDBOX_CANDIDATE_DIFF_BASE_CONTENT_SOURCE_EXACT_GIT_COMMIT_OBJECT
            )
            or diff.readonly_base_snapshot_verified is not True
            or diff.product_runtime_git_write_allowed is not False
            or diff.main_worktree_write_allowed is not False
            or diff.worktree_write_allowed is not False
            or diff.git_write_performed is not False
            or diff.file_write_allowed is not False
            or diff.main_project_file_written is not False
            or diff.sandbox_file_written is not False
            or diff.manifest_file_written is not False
            or diff.patch_applied is not False
            or diff.actual_patch_applied is not False
            or diff.real_code_modified is not False
        ):
            raise _Blocked("authority_invalid")

        base_commit_sha = diff.base_commit_sha
        persisted_base_snapshot_fingerprint = diff.base_snapshot_fingerprint
        if (
            not _LOWER_HEX_SHA256.fullmatch(source_candidate_diff_fingerprint)
            or base_commit_sha is None
            or not _LOWER_HEX_GIT_COMMIT.fullmatch(base_commit_sha)
            or persisted_base_snapshot_fingerprint is None
            or not _LOWER_HEX_SHA256.fullmatch(
                persisted_base_snapshot_fingerprint
            )
        ):
            raise _Blocked("authority_invalid")

        record_identity = f"project_director_message:{source_candidate_diff_message_id}"
        source_fingerprint = compute_p25_contract_sha256(
            {
                "schema_version": "p25-c.persisted-base-source.v1",
                "record_identity": record_identity,
                "session_id": session_id,
                "project_id": project_id,
                "source_task_id": source_task_id,
                "source_run_id": source_run_id,
                "repository_workspace_id": repository_workspace_id,
                "repository_root": repository_root,
                "workspace_creation_message_id": workspace_creation_message_id,
                "workspace_manifest_message_id": workspace_manifest_message_id,
                "operation_manifest_message_id": operation_manifest_message_id,
                "workspace_path": workspace_path,
                "source_candidate_diff_message_id": source_candidate_diff_message_id,
                "source_candidate_diff_message_sequence_no": message.sequence_no,
                "source_candidate_diff_message_intent": message.intent,
                "source_candidate_diff_message_source_detail": (
                    message.source_detail
                ),
                "source_candidate_diff_action": source_candidate_diff_action,
                "source_candidate_diff_fingerprint": source_candidate_diff_fingerprint,
                "base_evidence_schema_version": (
                    diff.base_evidence_schema_version
                ),
                "base_commit_sha": base_commit_sha,
                "persisted_source_base_snapshot_fingerprint": (
                    persisted_base_snapshot_fingerprint
                ),
                "base_content_source": diff.base_content_source,
                "readonly_base_snapshot_verified": (
                    diff.readonly_base_snapshot_verified
                ),
            }
        )
        return _PersistedBaseCommitSource(
            record_identity=record_identity,
            source_fingerprint=source_fingerprint,
            expected_base_commit_sha=base_commit_sha,
            persisted_source_base_snapshot_fingerprint=(
                persisted_base_snapshot_fingerprint
            ),
        )

    @staticmethod
    def _read_repository_head(repository_root: str) -> str:
        try:
            completed = subprocess.run(
                ("git", "rev-parse", "--verify", "HEAD"),
                cwd=repository_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise _Blocked("base_commit_mismatch") from exc
        value = completed.stdout.strip()
        if completed.returncode != 0 or not _LOWER_HEX_GIT_COMMIT.fullmatch(value):
            raise _Blocked("base_commit_mismatch")
        return value


__all__ = (
    "ProjectDirectorBoundedReworkEvidenceResolution",
    "ProjectDirectorBoundedReworkEvidenceResolver",
    "ProjectDirectorBoundedReworkEvidenceSnapshot",
)
