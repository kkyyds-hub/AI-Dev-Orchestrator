"""Readonly P24-D2A2 next-Task instruction package Candidate builder."""

from __future__ import annotations

import posixpath
import re
from pathlib import Path, PurePosixPath
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain.project_director_exact_next_task_routing_snapshot import (
    ProjectDirectorExactNextTaskRoutingResolution,
    ProjectDirectorExactNextTaskRoutingSnapshot,
)
from app.domain.project_director_next_task_instruction_package_candidate import (
    NEXT_TASK_INSTRUCTION_PACKAGE_CANDIDATE_SCHEMA_VERSION,
    AcceptanceCriteriaSource,
    NextTaskInstructionPackageCandidateBlockedReason,
    ProjectDirectorCandidateEvidenceRequirement,
    ProjectDirectorCandidateRepositoryBindingSnapshot,
    ProjectDirectorCandidateSelectedModel,
    ProjectDirectorCandidateSelectedSkill,
    ProjectDirectorCandidateSelectedStrategy,
    ProjectDirectorCandidateTestRequirement,
    ProjectDirectorCandidateVerificationRequirement,
    ProjectDirectorCandidateWorkspaceBindingSnapshot,
    ProjectDirectorConfirmedInstructionScopeSnapshot,
    ProjectDirectorNextTaskInstructionPackageCandidate,
    ProjectDirectorNextTaskInstructionPackageCandidateResolution,
)
from app.domain.project_director_next_task_source_bundle import (
    ProjectDirectorNextTaskSourceBundle,
    ProjectDirectorRepositoryBindingSnapshot,
    ProjectDirectorVerificationMechanismSnapshot,
)
from app.domain.task import Task, TaskHumanStatus, TaskRiskLevel, TaskStatus
from app.repositories.task_repository import TaskRepository
from app.services.project_director_exact_next_task_routing_snapshot_resolver import (
    ProjectDirectorExactNextTaskRoutingSnapshotResolver,
)


_FORBIDDEN_ACTIONS = (
    "product_runtime_git_write",
    "git_add",
    "git_commit",
    "git_push",
    "pull_request_creation",
    "merge",
    "branch_destruction",
    "global_pending_task_scan",
    "next_task_skip",
    "plan_mutation",
    "duplicate_task_creation",
    "task_claim",
    "run_creation",
    "worker_invocation",
    "workspace_write",
    "verification_command_execution",
    "package_persistence",
    "continuation_persistence",
)
_URL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_GLOB_META = frozenset("*?[]{}!")


class _Blocked(Exception):
    def __init__(
        self,
        *reasons: NextTaskInstructionPackageCandidateBlockedReason,
    ) -> None:
        self.reasons = tuple(dict.fromkeys(reasons))
        super().__init__(self.reasons[0] if self.reasons else "candidate blocked")


class ProjectDirectorNextTaskInstructionPackageCandidateBuilder:
    """Build one deterministic Candidate exclusively from D2A1 and exact Task."""

    def __init__(
        self,
        *,
        routing_snapshot_resolver: (
            ProjectDirectorExactNextTaskRoutingSnapshotResolver
        ),
        task_repository: TaskRepository,
    ) -> None:
        self._routing_snapshot_resolver = routing_snapshot_resolver
        self._task_repository = task_repository
        self._session = routing_snapshot_resolver._session
        self._require_shared_session()

    def build_next_task_instruction_package_candidate(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> ProjectDirectorNextTaskInstructionPackageCandidateResolution:
        """Restore authority and build a readonly, non-persisted Candidate."""

        self._require_shared_session()
        with self._session.no_autoflush:
            try:
                routing_resolution = (
                    self._routing_snapshot_resolver.resolve_exact_next_task_routing_snapshot(
                        session_id=session_id,
                        project_id=project_id,
                        source_completion_evidence_id=(
                            source_completion_evidence_id
                        ),
                        source_task_id=source_task_id,
                        source_run_id=source_run_id,
                    )
                )
            except (TypeError, ValueError, ValidationError, SQLAlchemyError):
                routing_resolution = (
                    ProjectDirectorExactNextTaskRoutingResolution.blocked(
                        "next_task_source_bundle_invalid"
                    )
                )

            if routing_resolution.status == "plan_queue_exhausted":
                if (
                    routing_resolution.source_bundle is not None
                    or routing_resolution.authority_lineage is not None
                    or routing_resolution.routing_snapshot is not None
                    or routing_resolution.blocked_reasons
                    or routing_resolution.routing_blocker_codes
                ):
                    return self._blocked(
                        routing_resolution,
                        "instruction_candidate_routing_invalid",
                    )
                return ProjectDirectorNextTaskInstructionPackageCandidateResolution(
                    status="plan_queue_exhausted",
                    routing_resolution=routing_resolution,
                    candidate=None,
                    blocked_reasons=(),
                )

            if routing_resolution.status != "routing_snapshot_resolved":
                return self._blocked(
                    routing_resolution,
                    "instruction_candidate_routing_invalid",
                )

            try:
                source_bundle, routing_snapshot = self._validate_routing_authority(
                    routing_resolution=routing_resolution,
                    session_id=session_id,
                    project_id=project_id,
                    source_completion_evidence_id=(
                        source_completion_evidence_id
                    ),
                    source_task_id=source_task_id,
                    source_run_id=source_run_id,
                )
            except _Blocked as exc:
                return self._blocked(routing_resolution, *exc.reasons)
            except (TypeError, ValueError, ValidationError):
                return self._blocked(
                    routing_resolution,
                    "instruction_candidate_routing_invalid",
                )

            try:
                exact_task = self._task_repository.get_by_id(
                    routing_snapshot.next_task_id
                )
            except (TypeError, ValueError, SQLAlchemyError):
                return self._blocked(
                    routing_resolution,
                    "instruction_candidate_task_missing",
                )
            if exact_task is None:
                return self._blocked(
                    routing_resolution,
                    "instruction_candidate_task_missing",
                )

            try:
                self._validate_exact_task(
                    task=exact_task,
                    source_bundle=source_bundle,
                    routing_snapshot=routing_snapshot,
                )
                candidate = self._build_candidate(
                    exact_task=exact_task,
                    source_bundle=source_bundle,
                    routing_resolution=routing_resolution,
                    routing_snapshot=routing_snapshot,
                )
            except _Blocked as exc:
                return self._blocked(routing_resolution, *exc.reasons)
            except (
                OSError,
                RuntimeError,
                TypeError,
                ValueError,
                ValidationError,
            ):
                return self._blocked(
                    routing_resolution,
                    "instruction_candidate_invalid",
                )

            return ProjectDirectorNextTaskInstructionPackageCandidateResolution(
                status="package_candidate_ready",
                routing_resolution=routing_resolution,
                candidate=candidate,
                blocked_reasons=(),
            )

    @staticmethod
    def _validate_routing_authority(
        *,
        routing_resolution: ProjectDirectorExactNextTaskRoutingResolution,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> tuple[
        ProjectDirectorNextTaskSourceBundle,
        ProjectDirectorExactNextTaskRoutingSnapshot,
    ]:
        source_bundle = routing_resolution.source_bundle
        authority_lineage = routing_resolution.authority_lineage
        routing_snapshot = routing_resolution.routing_snapshot
        if (
            source_bundle is None
            or authority_lineage is None
            or routing_snapshot is None
            or routing_resolution.blocked_reasons
            or routing_resolution.routing_blocker_codes
            or routing_resolution.product_runtime_git_write_allowed is not False
            or source_bundle.product_runtime_git_write_allowed is not False
            or routing_snapshot.product_runtime_git_write_allowed is not False
        ):
            raise _Blocked("instruction_candidate_routing_invalid")

        if (
            source_bundle.source_bundle_fingerprint
            != source_bundle.compute_fingerprint()
            or authority_lineage.authority_lineage_fingerprint
            != authority_lineage.compute_fingerprint()
            or routing_snapshot.routing_snapshot_fingerprint
            != routing_snapshot.compute_fingerprint()
        ):
            raise _Blocked("instruction_candidate_source_conflict")

        if (
            routing_snapshot.source_bundle_fingerprint
            != source_bundle.source_bundle_fingerprint
            or routing_snapshot.authority_lineage_fingerprint
            != authority_lineage.authority_lineage_fingerprint
            or authority_lineage.source_completion_evidence_id
            != source_bundle.source_completion_evidence_id
            or authority_lineage.source_completion_evidence_fingerprint
            != source_bundle.source_completion_evidence_fingerprint
        ):
            raise _Blocked("instruction_candidate_source_conflict")

        if (
            source_bundle.session_id != session_id
            or routing_snapshot.session_id != session_id
            or source_bundle.project_id != project_id
            or routing_snapshot.project_id != project_id
            or source_bundle.plan_version_id != routing_snapshot.plan_version_id
            or source_bundle.task_creation_record_id
            != routing_snapshot.task_creation_record_id
            or source_bundle.source_task_id != source_task_id
            or routing_snapshot.source_task_id != source_task_id
            or source_bundle.source_run_id != source_run_id
            or routing_snapshot.source_run_id != source_run_id
            or source_bundle.source_completion_evidence_id
            != source_completion_evidence_id
            or routing_snapshot.source_completion_evidence_id
            != source_completion_evidence_id
            or authority_lineage.source_completion_evidence_id
            != source_completion_evidence_id
            or source_bundle.next_task_id != routing_snapshot.next_task_id
            or source_bundle.next_task_index != routing_snapshot.next_task_index
            or source_bundle.task_count != routing_snapshot.task_count
            or source_bundle.next_task_owner_role_code
            != routing_snapshot.owner_role_code
            or source_bundle.next_task_owner_role_code
            != routing_snapshot.task_owner_role_code
        ):
            raise _Blocked("instruction_candidate_source_conflict")

        if (
            routing_snapshot.ready is not True
            or routing_snapshot.readiness_ready is not True
            or routing_snapshot.readiness_blocking_codes
            or routing_snapshot.human_confirmation_required is not False
            or routing_snapshot.human_confirmation_evidence_id is not None
        ):
            raise _Blocked("instruction_candidate_routing_snapshot_invalid")
        return source_bundle, routing_snapshot

    @staticmethod
    def _validate_exact_task(
        *,
        task: Task,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
        routing_snapshot: ProjectDirectorExactNextTaskRoutingSnapshot,
    ) -> None:
        expected_locator = (
            f"pdv:{source_bundle.plan_version_id}:{source_bundle.plan_version_no}"
        )
        if (
            task.id != source_bundle.next_task_id
            or task.id != routing_snapshot.next_task_id
            or task.project_id != source_bundle.project_id
            or task.project_id != routing_snapshot.project_id
            or task.title != source_bundle.next_task_title
            or task.input_summary != source_bundle.next_task_input_summary
            or task.owner_role_code != source_bundle.next_task_owner_role_code
            or task.owner_role_code != routing_snapshot.task_owner_role_code
            or task.priority != source_bundle.next_task_priority
            or task.priority != routing_snapshot.task_priority
            or task.risk_level != source_bundle.next_task_risk_level
            or task.risk_level != routing_snapshot.task_risk_level
            or tuple(task.depends_on_task_ids)
            != source_bundle.next_task_dependency_ids
            or tuple(task.depends_on_task_ids)
            != routing_snapshot.task_dependency_ids
            or task.source_draft_id != expected_locator
        ):
            raise _Blocked("instruction_candidate_task_conflict")
        if (
            task.status != TaskStatus.PENDING
            or task.status != routing_snapshot.task_status
            or task.human_status != routing_snapshot.task_human_status
            or task.human_status
            in {TaskHumanStatus.REQUESTED, TaskHumanStatus.IN_PROGRESS}
            or task.paused_reason is not None
            or routing_snapshot.task_paused_reason_absent is not True
        ):
            raise _Blocked("instruction_candidate_task_state_conflict")

    def _build_candidate(
        self,
        *,
        exact_task: Task,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
        routing_resolution: ProjectDirectorExactNextTaskRoutingResolution,
        routing_snapshot: ProjectDirectorExactNextTaskRoutingSnapshot,
    ) -> ProjectDirectorNextTaskInstructionPackageCandidate:
        authority_lineage = routing_resolution.authority_lineage
        if authority_lineage is None:
            raise _Blocked("instruction_candidate_routing_invalid")

        confirmed_scope = self._build_confirmed_scope(source_bundle)
        repository_binding = self._require_repository_binding(source_bundle)
        (
            candidate_repository_binding,
            candidate_workspace_binding,
            allowed_paths,
        ) = self._build_repository_authority(
            source_bundle=source_bundle,
            binding=repository_binding,
        )
        forbidden_paths = self._build_forbidden_paths(
            source_bundle=source_bundle,
            workspace_root=source_bundle.repository_workspace.root_path,
            allowed_workspace_root=(
                source_bundle.repository_workspace.allowed_workspace_root
            ),
        )
        self._validate_path_policy(
            allowed_paths=allowed_paths,
            forbidden_paths=forbidden_paths,
        )
        acceptance_source, acceptance_criteria = self._select_acceptance_criteria(
            exact_task=exact_task,
            source_bundle=source_bundle,
        )
        (
            verification_requirements,
            test_requirements,
            evidence_requirements,
        ) = self._build_verification_requirements(
            exact_task=exact_task,
            source_bundle=source_bundle,
        )
        self._validate_human_confirmation(
            exact_task=exact_task,
            source_bundle=source_bundle,
            relevant_mechanisms=tuple(
                mechanism
                for mechanism in source_bundle.all_verification_mechanisms
                if mechanism.owner_role_code
                in {exact_task.owner_role_code.value, "reviewer"}
            ),
        )
        selected_strategy = self._build_selected_strategy(routing_snapshot)
        selected_model = self._build_selected_model(routing_snapshot)
        selected_skills = self._build_selected_skills(
            source_bundle=source_bundle,
            routing_snapshot=routing_snapshot,
        )

        payload = {
            "schema_version": (
                NEXT_TASK_INSTRUCTION_PACKAGE_CANDIDATE_SCHEMA_VERSION
            ),
            "source_bundle_fingerprint": (
                source_bundle.source_bundle_fingerprint
            ),
            "authority_lineage_fingerprint": (
                authority_lineage.authority_lineage_fingerprint
            ),
            "routing_snapshot_fingerprint": (
                routing_snapshot.routing_snapshot_fingerprint
            ),
            "session_id": source_bundle.session_id,
            "project_id": source_bundle.project_id,
            "plan_version_id": source_bundle.plan_version_id,
            "plan_version_no": source_bundle.plan_version_no,
            "task_creation_record_id": source_bundle.task_creation_record_id,
            "source_task_id": source_bundle.source_task_id,
            "source_run_id": source_bundle.source_run_id,
            "source_completion_evidence_id": (
                source_bundle.source_completion_evidence_id
            ),
            "source_authority_lineage": authority_lineage,
            "next_task_id": source_bundle.next_task_id,
            "next_task_index": source_bundle.next_task_index,
            "task_count": source_bundle.task_count,
            "task_title": exact_task.title,
            "task_input_summary": exact_task.input_summary,
            "owner_role_code": exact_task.owner_role_code,
            "priority": exact_task.priority,
            "risk_level": exact_task.risk_level,
            "depends_on_task_ids": tuple(exact_task.depends_on_task_ids),
            "confirmed_scope": confirmed_scope,
            "repository_binding": candidate_repository_binding,
            "workspace_binding": candidate_workspace_binding,
            "allowed_paths": allowed_paths,
            "forbidden_scope_entries": tuple(
                source_bundle.project_scope.out_of_scope
            ),
            "workspace_ignore_rule_summary": tuple(
                source_bundle.repository_workspace.ignore_rule_summary
            ),
            "forbidden_paths": forbidden_paths,
            "acceptance_criteria_source": acceptance_source,
            "acceptance_criteria": acceptance_criteria,
            "verification_requirements": verification_requirements,
            "test_requirements": test_requirements,
            "evidence_requirements": evidence_requirements,
            "selected_strategy": selected_strategy,
            "selected_model": selected_model,
            "selected_skills": selected_skills,
            "human_confirmation_required": False,
            "human_confirmation_evidence_id": None,
            "product_runtime_git_write_allowed": False,
            "forbidden_actions": _FORBIDDEN_ACTIONS,
        }
        fingerprint = ProjectDirectorNextTaskInstructionPackageCandidate.fingerprint_payload(
            payload
        )
        return ProjectDirectorNextTaskInstructionPackageCandidate(
            **payload,
            candidate_fingerprint=fingerprint,
        )

    @classmethod
    def _build_confirmed_scope(
        cls,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
    ) -> ProjectDirectorConfirmedInstructionScopeSnapshot:
        scope = source_bundle.project_scope
        cls._require_text_collection(
            scope.in_scope,
            "instruction_candidate_scope_invalid",
        )
        cls._require_text_collection(
            scope.out_of_scope,
            "instruction_candidate_scope_invalid",
        )
        cls._require_text_collection(
            scope.assumptions,
            "instruction_candidate_scope_invalid",
        )
        if (
            not source_bundle.proposed_task_title.strip()
            or not source_bundle.proposed_task_description.strip()
            or not source_bundle.proposed_task_priority_hint.strip()
        ):
            raise _Blocked("instruction_candidate_scope_invalid")

        in_scope_normalized = {
            cls._normalize_scope_text(item) for item in scope.in_scope
        }
        out_scope_normalized = {
            cls._normalize_scope_text(item) for item in scope.out_of_scope
        }
        if in_scope_normalized & out_scope_normalized:
            raise _Blocked("instruction_candidate_scope_conflict")

        boundaries = source_bundle.deliverable_boundaries
        for boundary in boundaries:
            if any(
                not value.strip()
                for value in (
                    boundary.name,
                    boundary.description,
                    boundary.done_definition,
                    boundary.acceptance_signal,
                )
            ) or any(not item.strip() for item in boundary.required_contents):
                raise _Blocked("instruction_candidate_scope_invalid")
        if (
            not any(item.strip() for item in scope.in_scope)
            and not boundaries
            and not source_bundle.proposed_task_description.strip()
        ):
            raise _Blocked("instruction_candidate_scope_invalid")

        return ProjectDirectorConfirmedInstructionScopeSnapshot(
            project_in_scope=tuple(scope.in_scope),
            project_out_of_scope=tuple(scope.out_of_scope),
            project_assumptions=tuple(scope.assumptions),
            next_proposed_task_title=source_bundle.proposed_task_title,
            next_proposed_task_description=(
                source_bundle.proposed_task_description
            ),
            next_proposed_task_role_code=source_bundle.proposed_task_role_code,
            next_proposed_task_priority_hint=(
                source_bundle.proposed_task_priority_hint
            ),
            deliverable_boundaries=tuple(boundaries),
        )

    @staticmethod
    def _require_repository_binding(
        source_bundle: ProjectDirectorNextTaskSourceBundle,
    ) -> ProjectDirectorRepositoryBindingSnapshot:
        bindings = source_bundle.confirmed_repository_bindings
        if not bindings:
            raise _Blocked("instruction_candidate_repository_binding_missing")
        if len(bindings) != 1:
            raise _Blocked("instruction_candidate_repository_binding_ambiguous")
        return bindings[0]

    @classmethod
    def _build_repository_authority(
        cls,
        *,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
        binding: ProjectDirectorRepositoryBindingSnapshot,
    ) -> tuple[
        ProjectDirectorCandidateRepositoryBindingSnapshot,
        ProjectDirectorCandidateWorkspaceBindingSnapshot,
        tuple[str, ...],
    ]:
        workspace = source_bundle.repository_workspace
        target_lexical, target_resolved = cls._absolute_local_path(
            binding.target,
            "instruction_candidate_repository_target_invalid",
        )
        root_lexical, root_resolved = cls._absolute_local_path(
            workspace.root_path,
            "instruction_candidate_workspace_root_conflict",
        )
        allowed_lexical, allowed_resolved = cls._absolute_local_path(
            workspace.allowed_workspace_root,
            "instruction_candidate_workspace_root_conflict",
        )
        if target_lexical != root_lexical or target_resolved != root_resolved:
            raise _Blocked("instruction_candidate_workspace_root_conflict")
        if not cls._contained(root_lexical, allowed_lexical) or not cls._contained(
            root_resolved,
            allowed_resolved,
        ):
            raise _Blocked("instruction_candidate_workspace_escape")

        configured_branch = binding.branch
        default_branch = workspace.default_base_branch
        if not configured_branch.strip() or not default_branch.strip():
            raise _Blocked("instruction_candidate_branch_conflict")
        if configured_branch == "未指定":
            effective_branch = default_branch
        elif configured_branch == default_branch:
            effective_branch = configured_branch
        else:
            raise _Blocked("instruction_candidate_branch_conflict")

        allowed_paths = cls._validate_path_collection(
            binding.focus_paths,
            workspace_root=root_lexical,
            allowed_workspace_root=allowed_lexical,
            workspace_root_resolved=root_resolved,
            allowed_workspace_root_resolved=allowed_resolved,
            invalid_reason="instruction_candidate_allowed_path_invalid",
            duplicate_reason="instruction_candidate_allowed_path_duplicate",
            dot_reason="instruction_candidate_workspace_root_scope_unconfirmed",
            require_nonempty=True,
        )
        repository_snapshot = ProjectDirectorCandidateRepositoryBindingSnapshot(
            binding_type=binding.binding_type,
            binding_mode=binding.binding_mode,
            target=binding.target,
            configured_branch=configured_branch,
            effective_branch=effective_branch,
            focus_paths=allowed_paths,
            usage=binding.usage,
            safety_note=binding.safety_note,
            review_status=binding.review_status,
        )
        workspace_snapshot = ProjectDirectorCandidateWorkspaceBindingSnapshot(
            workspace_id=workspace.id,
            project_id=workspace.project_id,
            root_path=workspace.root_path,
            allowed_workspace_root=workspace.allowed_workspace_root,
            display_name=workspace.display_name,
            access_mode=workspace.access_mode,
            default_base_branch=workspace.default_base_branch,
            ignore_rule_summary=tuple(workspace.ignore_rule_summary),
        )
        return repository_snapshot, workspace_snapshot, allowed_paths

    @classmethod
    def _build_forbidden_paths(
        cls,
        *,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
        workspace_root: str,
        allowed_workspace_root: str,
    ) -> tuple[str, ...]:
        root_lexical, root_resolved = cls._absolute_local_path(
            workspace_root,
            "instruction_candidate_workspace_root_conflict",
        )
        allowed_lexical, allowed_resolved = cls._absolute_local_path(
            allowed_workspace_root,
            "instruction_candidate_workspace_root_conflict",
        )
        path_entries = tuple(
            item[len("path:") :]
            for item in (
                *source_bundle.project_scope.out_of_scope,
                *source_bundle.repository_workspace.ignore_rule_summary,
            )
            if item.startswith("path:")
        )
        return cls._validate_path_collection(
            path_entries,
            workspace_root=root_lexical,
            allowed_workspace_root=allowed_lexical,
            workspace_root_resolved=root_resolved,
            allowed_workspace_root_resolved=allowed_resolved,
            invalid_reason="instruction_candidate_forbidden_path_invalid",
            duplicate_reason="instruction_candidate_forbidden_path_duplicate",
            dot_reason="instruction_candidate_forbidden_path_invalid",
            require_nonempty=False,
        )

    @classmethod
    def _validate_path_collection(
        cls,
        values: tuple[str, ...],
        *,
        workspace_root: str,
        allowed_workspace_root: str,
        workspace_root_resolved: str,
        allowed_workspace_root_resolved: str,
        invalid_reason: NextTaskInstructionPackageCandidateBlockedReason,
        duplicate_reason: NextTaskInstructionPackageCandidateBlockedReason,
        dot_reason: NextTaskInstructionPackageCandidateBlockedReason,
        require_nonempty: bool,
    ) -> tuple[str, ...]:
        if require_nonempty and not values:
            raise _Blocked(invalid_reason)
        normalized: list[str] = []
        seen: set[str] = set()
        for raw_value in values:
            value = cls._relative_posix_path(
                raw_value,
                invalid_reason=invalid_reason,
                dot_reason=dot_reason,
            )
            if value in seen:
                raise _Blocked(duplicate_reason)
            seen.add(value)

            lexical_target = str(PurePosixPath(workspace_root) / value)
            try:
                resolved_target = str(
                    (
                        Path(workspace_root)
                        / Path(*PurePosixPath(value).parts)
                    ).resolve(strict=False)
                )
            except (OSError, RuntimeError) as exc:
                raise _Blocked(invalid_reason) from exc
            if (
                not cls._contained(lexical_target, workspace_root)
                or not cls._contained(lexical_target, allowed_workspace_root)
                or not cls._contained(resolved_target, workspace_root_resolved)
                or not cls._contained(
                    resolved_target,
                    allowed_workspace_root_resolved,
                )
            ):
                raise _Blocked(invalid_reason)
            normalized.append(value)
        return tuple(normalized)

    @staticmethod
    def _relative_posix_path(
        raw_value: str,
        *,
        invalid_reason: NextTaskInstructionPackageCandidateBlockedReason,
        dot_reason: NextTaskInstructionPackageCandidateBlockedReason,
    ) -> str:
        if (
            not isinstance(raw_value, str)
            or not raw_value
            or raw_value != raw_value.strip()
            or "\x00" in raw_value
            or "\\" in raw_value
            or _URL_SCHEME.match(raw_value)
            or any(character in raw_value for character in _GLOB_META)
        ):
            raise _Blocked(invalid_reason)
        if raw_value == ".":
            raise _Blocked(dot_reason)
        parts = raw_value.split("/")
        if any(not part or part in {".", ".."} for part in parts):
            raise _Blocked(invalid_reason)
        path = PurePosixPath(raw_value)
        if path.is_absolute() or str(path) != raw_value:
            raise _Blocked(invalid_reason)
        return str(path)

    @staticmethod
    def _absolute_local_path(
        raw_value: str,
        invalid_reason: NextTaskInstructionPackageCandidateBlockedReason,
    ) -> tuple[str, str]:
        if (
            not isinstance(raw_value, str)
            or not raw_value
            or raw_value != raw_value.strip()
            or "\x00" in raw_value
            or "~" in raw_value
            or "$" in raw_value
            or "`" in raw_value
            or "\\" in raw_value
            or _URL_SCHEME.match(raw_value)
            or any(character in raw_value for character in _GLOB_META)
        ):
            raise _Blocked(invalid_reason)
        path = PurePosixPath(raw_value)
        if not path.is_absolute():
            raise _Blocked(invalid_reason)
        lexical = posixpath.normpath(raw_value)
        try:
            resolved = str(Path(raw_value).resolve(strict=False))
        except (OSError, RuntimeError) as exc:
            raise _Blocked(invalid_reason) from exc
        return lexical, resolved

    @staticmethod
    def _contained(candidate: str, root: str) -> bool:
        candidate_path = PurePosixPath(candidate)
        root_path = PurePosixPath(root)
        return candidate_path == root_path or root_path in candidate_path.parents

    @staticmethod
    def _validate_path_policy(
        *,
        allowed_paths: tuple[str, ...],
        forbidden_paths: tuple[str, ...],
    ) -> None:
        for allowed in allowed_paths:
            allowed_path = PurePosixPath(allowed)
            for forbidden in forbidden_paths:
                forbidden_path = PurePosixPath(forbidden)
                if (
                    allowed_path == forbidden_path
                    or allowed_path in forbidden_path.parents
                    or forbidden_path in allowed_path.parents
                ):
                    raise _Blocked("instruction_candidate_path_policy_conflict")

    @classmethod
    def _select_acceptance_criteria(
        cls,
        *,
        exact_task: Task,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
    ) -> tuple[AcceptanceCriteriaSource, tuple[str, ...]]:
        if exact_task.acceptance_criteria:
            source: AcceptanceCriteriaSource = "task"
            values = tuple(exact_task.acceptance_criteria)
        else:
            source = "confirmed_plan"
            values = tuple(source_bundle.plan_acceptance_criteria)
        if not values:
            raise _Blocked("instruction_candidate_acceptance_criteria_missing")
        cls._require_text_collection(
            values,
            "instruction_candidate_acceptance_criteria_missing",
        )
        if len(values) != len(set(values)):
            raise _Blocked("instruction_candidate_acceptance_criteria_missing")
        return source, values

    @classmethod
    def _build_verification_requirements(
        cls,
        *,
        exact_task: Task,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
    ) -> tuple[
        tuple[ProjectDirectorCandidateVerificationRequirement, ...],
        tuple[ProjectDirectorCandidateTestRequirement, ...],
        tuple[ProjectDirectorCandidateEvidenceRequirement, ...],
    ]:
        verification_config = source_bundle.verification_config
        expected_locator = (
            f"pdv:{source_bundle.plan_version_id}:{source_bundle.plan_version_no}"
        )
        if (
            verification_config.status != "confirmed"
            or verification_config.project_id != source_bundle.project_id
            or verification_config.plan_version_id
            != source_bundle.plan_version_id
            or verification_config.source_draft_id != expected_locator
        ):
            raise _Blocked(
                "instruction_candidate_verification_requirement_unconfirmed"
            )
        if exact_task.owner_role_code is None:
            raise _Blocked("instruction_candidate_task_conflict")
        relevant = tuple(
            mechanism
            for mechanism in source_bundle.all_verification_mechanisms
            if mechanism.owner_role_code
            in {exact_task.owner_role_code.value, "reviewer"}
        )
        if not relevant:
            raise _Blocked(
                "instruction_candidate_verification_requirements_missing"
            )
        names: set[str] = set()
        for mechanism in relevant:
            if (
                not mechanism.name.strip()
                or not mechanism.command_or_method.strip()
                or not mechanism.evidence_required.strip()
                or not mechanism.owner_role_code.strip()
                or not mechanism.risk_level.strip()
            ):
                raise _Blocked(
                    "instruction_candidate_verification_requirements_missing"
                )
            if (
                not isinstance(mechanism.review_status, str)
                or not mechanism.review_status.strip()
            ):
                raise _Blocked(
                    "instruction_candidate_verification_requirement_unconfirmed"
                )
            if mechanism.name in names:
                raise _Blocked(
                    "instruction_candidate_verification_requirements_missing"
                )
            names.add(mechanism.name)

        verification = tuple(
            ProjectDirectorCandidateVerificationRequirement(
                name=mechanism.name,
                purpose=mechanism.purpose,
                owner_role_code=mechanism.owner_role_code,
                risk_level=mechanism.risk_level,
                requires_user_confirmation=(
                    mechanism.requires_user_confirmation
                ),
                review_status=mechanism.review_status,
            )
            for mechanism in relevant
        )
        tests = tuple(
            ProjectDirectorCandidateTestRequirement(
                mechanism_name=mechanism.name,
                command_or_method=mechanism.command_or_method,
            )
            for mechanism in relevant
        )
        evidence = tuple(
            ProjectDirectorCandidateEvidenceRequirement(
                mechanism_name=mechanism.name,
                evidence_required=mechanism.evidence_required,
            )
            for mechanism in relevant
        )
        return verification, tests, evidence

    @staticmethod
    def _validate_human_confirmation(
        *,
        exact_task: Task,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
        relevant_mechanisms: tuple[
            ProjectDirectorVerificationMechanismSnapshot, ...
        ],
    ) -> None:
        if (
            exact_task.risk_level == TaskRiskLevel.HIGH
            or source_bundle.human_confirmation_mechanisms
            or any(
                mechanism.requires_user_confirmation
                for mechanism in relevant_mechanisms
            )
        ):
            raise _Blocked(
                "instruction_candidate_human_confirmation_required"
            )

    @staticmethod
    def _build_selected_strategy(
        routing_snapshot: ProjectDirectorExactNextTaskRoutingSnapshot,
    ) -> ProjectDirectorCandidateSelectedStrategy:
        if (
            not routing_snapshot.strategy_code.strip()
            or not routing_snapshot.strategy_summary.strip()
            or not routing_snapshot.route_reason.strip()
            or not routing_snapshot.budget_strategy_code.strip()
            or not routing_snapshot.dispatch_status.strip()
            or not routing_snapshot.handoff_reason.strip()
            or routing_snapshot.strategy_decision.strategy_code
            != routing_snapshot.strategy_code
            or routing_snapshot.strategy_decision.summary
            != routing_snapshot.strategy_summary
            or routing_snapshot.strategy_decision.owner_role_code
            != routing_snapshot.owner_role_code
        ):
            raise _Blocked("instruction_candidate_routing_snapshot_invalid")
        return ProjectDirectorCandidateSelectedStrategy(
            strategy_code=routing_snapshot.strategy_code,
            strategy_summary=routing_snapshot.strategy_summary,
            strategy_reasons=tuple(routing_snapshot.strategy_reasons),
            strategy_decision=routing_snapshot.strategy_decision,
            routing_score=routing_snapshot.routing_score,
            routing_score_breakdown=tuple(
                routing_snapshot.routing_score_breakdown
            ),
            route_reason=routing_snapshot.route_reason,
            execution_attempts=routing_snapshot.execution_attempts,
            recent_failure_count=routing_snapshot.recent_failure_count,
            budget_pressure_level=routing_snapshot.budget_pressure_level,
            budget_action=routing_snapshot.budget_action,
            budget_strategy_code=routing_snapshot.budget_strategy_code,
            budget_score_adjustment=routing_snapshot.budget_score_adjustment,
            dispatch_status=routing_snapshot.dispatch_status,
            handoff_reason=routing_snapshot.handoff_reason,
            matched_terms=tuple(routing_snapshot.matched_terms),
            project_stage=routing_snapshot.project_stage,
            owner_role_code=routing_snapshot.owner_role_code,
            upstream_role_code=routing_snapshot.upstream_role_code,
            downstream_role_code=routing_snapshot.downstream_role_code,
        )

    @staticmethod
    def _build_selected_model(
        routing_snapshot: ProjectDirectorExactNextTaskRoutingSnapshot,
    ) -> ProjectDirectorCandidateSelectedModel:
        if (
            not routing_snapshot.model_name.strip()
            or not routing_snapshot.model_tier.strip()
            or routing_snapshot.strategy_decision.model_name
            != routing_snapshot.model_name
            or routing_snapshot.strategy_decision.model_tier
            != routing_snapshot.model_tier
        ):
            raise _Blocked("instruction_candidate_model_invalid")
        return ProjectDirectorCandidateSelectedModel(
            model_name=routing_snapshot.model_name,
            model_tier=routing_snapshot.model_tier,
        )

    @staticmethod
    def _build_selected_skills(
        *,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
        routing_snapshot: ProjectDirectorExactNextTaskRoutingSnapshot,
    ) -> tuple[ProjectDirectorCandidateSelectedSkill, ...]:
        codes = routing_snapshot.selected_skill_codes
        names = routing_snapshot.selected_skill_names
        if (
            not codes
            or len(codes) != len(names)
            or any(not code.strip() for code in codes)
            or any(not name.strip() for name in names)
            or len(codes) != len(set(codes))
            or len(names) != len(set(names))
        ):
            raise _Blocked("instruction_candidate_skill_conflict")
        owner_code = routing_snapshot.owner_role_code.value
        confirmed = {
            (binding.skill_code, binding.skill_name)
            for binding in source_bundle.owner_confirmed_skill_bindings
            if binding.owner_role_code == owner_code
        }
        pairs = tuple(zip(codes, names, strict=True))
        if any(pair not in confirmed for pair in pairs):
            raise _Blocked("instruction_candidate_skill_conflict")
        return tuple(
            ProjectDirectorCandidateSelectedSkill(
                skill_code=code,
                skill_name=name,
            )
            for code, name in pairs
        )

    @staticmethod
    def _normalize_scope_text(value: str) -> str:
        return " ".join(value.split()).casefold()

    @staticmethod
    def _require_text_collection(
        values: tuple[str, ...] | list[str],
        reason: NextTaskInstructionPackageCandidateBlockedReason,
    ) -> None:
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise _Blocked(reason)

    def _require_shared_session(self) -> None:
        if self._task_repository.session is not self._session:
            raise ValueError(
                "P24-D2A2 dependencies must share one SQLAlchemy session"
            )

    @staticmethod
    def _blocked(
        routing_resolution: ProjectDirectorExactNextTaskRoutingResolution,
        *reasons: NextTaskInstructionPackageCandidateBlockedReason,
    ) -> ProjectDirectorNextTaskInstructionPackageCandidateResolution:
        return ProjectDirectorNextTaskInstructionPackageCandidateResolution.blocked(
            routing_resolution,
            *reasons,
        )


__all__ = ("ProjectDirectorNextTaskInstructionPackageCandidateBuilder",)
