"""Readonly review execution orchestration from persisted P21-C-H-A preflight."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_readonly_reviewer_adapter import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
)
from app.external_executors.readonly_reviewer_transport import (
    ReadonlyReviewerTransportProtocol,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_readonly_reviewer_adapter_service import (
    ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL,
    REVIEW_OUTPUT_SCHEMA_VERSION,
    ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
)


P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL = (
    "p21_c_sandbox_candidate_diff_readonly_review_executed"
)
P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE = (
    "p21_c_sandbox_candidate_diff_readonly_review_execution_record"
)

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_SOURCE_DIFF_FALSE_FLAGS = (
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "patch_applied",
    "controlled_sandbox_write_enabled",
    "sandbox_write_allowed",
    "product_runtime_git_write_allowed",
    "main_worktree_write_allowed",
    "worktree_write_allowed",
    "file_write_allowed",
    "actual_patch_applied",
    "real_code_modified",
    "git_write_performed",
    "native_executor_started",
    "codex_started",
    "claude_code_started",
    "worker_started",
    "task_created",
    "run_created",
    "worktree_created",
    "worktree_cleaned_up",
    "rollback_snapshot_created",
)

_PREFLIGHT_FALSE_FLAGS = (
    "reviewer_started",
    "review_executed",
    "review_findings_generated",
    "review_verdict_generated",
    "provider_called",
    "native_executor_started",
    "codex_started",
    "claude_code_started",
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
    "product_runtime_git_write_allowed",
    "git_write_performed",
    "worktree_created",
    "worker_started",
    "task_created",
    "run_created",
)


@dataclass(frozen=True, slots=True)
class ConfirmedSandboxCandidateDiffReadonlyReviewExecution:
    """P21-C-H-C1 readonly review execution result and optional persisted message."""

    result: ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class _PersistedPreflightEvidence:
    requested_reviewer_executor: str
    source_diff_message_id: UUID
    source_diff_sha256: str
    review_scope_paths: list[str]
    review_prompt_sha256: str
    review_prompt_bytes: int
    review_output_schema_version: str


class ReadonlyReviewerTransportResolverProtocol(Protocol):
    """Resolve a readonly reviewer transport after executor evidence is validated."""

    def __call__(
        self,
        requested_reviewer_executor: str,
    ) -> ReadonlyReviewerTransportProtocol:
        ...


class ReadonlyReviewerTransportResolverFactoryProtocol(Protocol):
    """Create a resolver only after trusted workspace evidence is recovered."""

    def __call__(
        self,
        workspace_path: str,
    ) -> ReadonlyReviewerTransportResolverProtocol:
        ...


class ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService:
    """Execute readonly review only after persisted evidence revalidation."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository | None = None,
        message_repository: ProjectDirectorMessageRepository | None = None,
        task_repository: TaskRepository | None = None,
        adapter_service: ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService
        | None = None,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._adapter_service = (
            adapter_service
            or ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterService()
        )

    def execute_candidate_diff_readonly_review_from_preflight(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        transport: ReadonlyReviewerTransportProtocol,
    ) -> ConfirmedSandboxCandidateDiffReadonlyReviewExecution:
        """Legacy path: execute with a caller-provided transport."""

        return self._execute_candidate_diff_readonly_review_from_preflight(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            transport=transport,
            transport_resolver=None,
            transport_resolver_factory=None,
        )

    def execute_candidate_diff_readonly_review_from_preflight_with_transport_resolver(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        transport_resolver: ReadonlyReviewerTransportResolverProtocol,
    ) -> ConfirmedSandboxCandidateDiffReadonlyReviewExecution:
        """Resolve transport only after persisted evidence and prompt are verified."""

        return self._execute_candidate_diff_readonly_review_from_preflight(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            transport=None,
            transport_resolver=transport_resolver,
            transport_resolver_factory=None,
        )

    def execute_candidate_diff_readonly_review_from_preflight_with_transport_resolver_factory(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        transport_resolver_factory: ReadonlyReviewerTransportResolverFactoryProtocol,
    ) -> ConfirmedSandboxCandidateDiffReadonlyReviewExecution:
        """Create a workspace-bound resolver after evidence is verified."""

        return self._execute_candidate_diff_readonly_review_from_preflight(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            transport=None,
            transport_resolver=None,
            transport_resolver_factory=transport_resolver_factory,
        )

    def _execute_candidate_diff_readonly_review_from_preflight(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        transport: ReadonlyReviewerTransportProtocol | None,
        transport_resolver: ReadonlyReviewerTransportResolverProtocol | None,
        transport_resolver_factory: ReadonlyReviewerTransportResolverFactoryProtocol
        | None,
    ) -> ConfirmedSandboxCandidateDiffReadonlyReviewExecution:
        """Rebuild preflight evidence, invoke adapter once, and persist validated output."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("readonly review execution repositories are required")

        blocked_reasons: list[str] = []
        session_obj = self._session_repository.get_by_id(session_id)
        source_task = self._task_repository.get_by_id(source_task_id)
        source_preflight_message = self._message_repository.get_by_id(source_message_id)

        if session_obj is None:
            blocked_reasons.append("session_missing")
        if source_task is None:
            blocked_reasons.append("source_task_missing")

        preflight_action = self._preflight_action(
            source_preflight_message=source_preflight_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        preflight_evidence = self._preflight_evidence(
            preflight_action,
            blocked_reasons=blocked_reasons,
        )

        source_diff_message = None
        if preflight_evidence is not None:
            source_diff_message = self._message_repository.get_by_id(
                preflight_evidence.source_diff_message_id
            )

        source_diff_action = self._source_diff_action(
            source_diff_message=source_diff_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        unified_diff_text = self._validated_unified_diff_text(
            source_diff_action,
            preflight_evidence=preflight_evidence,
            blocked_reasons=blocked_reasons,
        )
        review_prompt_text = self._reconstructed_review_prompt(
            preflight_evidence=preflight_evidence,
            unified_diff_text=unified_diff_text,
            blocked_reasons=blocked_reasons,
        )

        if blocked_reasons or preflight_evidence is None or not review_prompt_text:
            return ConfirmedSandboxCandidateDiffReadonlyReviewExecution(
                result=self._blocked_result(
                    requested_reviewer_executor=(
                        preflight_evidence.requested_reviewer_executor
                        if preflight_evidence is not None
                        else ""
                    ),
                    review_scope_paths=(
                        preflight_evidence.review_scope_paths
                        if preflight_evidence is not None
                        else []
                    ),
                    review_output_schema_version=(
                        preflight_evidence.review_output_schema_version
                        if preflight_evidence is not None
                        else REVIEW_OUTPUT_SCHEMA_VERSION
                    ),
                    blocked_reasons=blocked_reasons,
                ),
                message=None,
            )

        resolved_transport = transport
        if resolved_transport is None:
            if (
                transport_resolver is None
                and transport_resolver_factory is not None
            ):
                workspace_path = self._trusted_source_diff_workspace_path(
                    source_diff_action,
                    blocked_reasons=blocked_reasons,
                )
                if blocked_reasons or not workspace_path:
                    return ConfirmedSandboxCandidateDiffReadonlyReviewExecution(
                        result=self._blocked_result(
                            requested_reviewer_executor=(
                                preflight_evidence.requested_reviewer_executor
                            ),
                            review_scope_paths=preflight_evidence.review_scope_paths,
                            review_output_schema_version=(
                                preflight_evidence.review_output_schema_version
                            ),
                            blocked_reasons=blocked_reasons,
                        ),
                        message=None,
                    )
                try:
                    transport_resolver = transport_resolver_factory(workspace_path)
                except Exception:
                    return ConfirmedSandboxCandidateDiffReadonlyReviewExecution(
                        result=self._blocked_result(
                            requested_reviewer_executor=(
                                preflight_evidence.requested_reviewer_executor
                            ),
                            review_scope_paths=preflight_evidence.review_scope_paths,
                            review_output_schema_version=(
                                preflight_evidence.review_output_schema_version
                            ),
                            blocked_reasons=[
                                "readonly_reviewer_transport_resolution_failed"
                            ],
                        ),
                        message=None,
                    )
            if transport_resolver is None:
                return ConfirmedSandboxCandidateDiffReadonlyReviewExecution(
                    result=self._blocked_result(
                        requested_reviewer_executor=(
                            preflight_evidence.requested_reviewer_executor
                        ),
                        review_scope_paths=preflight_evidence.review_scope_paths,
                        review_output_schema_version=(
                            preflight_evidence.review_output_schema_version
                        ),
                        blocked_reasons=[
                            "readonly_reviewer_transport_resolution_failed"
                        ],
                    ),
                    message=None,
                )
            try:
                resolved_transport = transport_resolver(
                    preflight_evidence.requested_reviewer_executor
                )
            except Exception:
                return ConfirmedSandboxCandidateDiffReadonlyReviewExecution(
                    result=self._blocked_result(
                        requested_reviewer_executor=(
                            preflight_evidence.requested_reviewer_executor
                        ),
                        review_scope_paths=preflight_evidence.review_scope_paths,
                        review_output_schema_version=(
                            preflight_evidence.review_output_schema_version
                        ),
                        blocked_reasons=[
                            "readonly_reviewer_transport_resolution_failed"
                        ],
                    ),
                    message=None,
                )
            if not isinstance(resolved_transport, ReadonlyReviewerTransportProtocol):
                return ConfirmedSandboxCandidateDiffReadonlyReviewExecution(
                    result=self._blocked_result(
                        requested_reviewer_executor=(
                            preflight_evidence.requested_reviewer_executor
                        ),
                        review_scope_paths=preflight_evidence.review_scope_paths,
                        review_output_schema_version=(
                            preflight_evidence.review_output_schema_version
                        ),
                        blocked_reasons=[
                            "readonly_reviewer_transport_resolution_failed"
                        ],
                    ),
                    message=None,
                )

        adapter_result = self._adapter_service.validate_review_output_through_transport(
            requested_reviewer_executor=preflight_evidence.requested_reviewer_executor,
            review_prompt_text=review_prompt_text,
            expected_review_prompt_sha256=preflight_evidence.review_prompt_sha256,
            expected_review_prompt_bytes=preflight_evidence.review_prompt_bytes,
            review_scope_paths=preflight_evidence.review_scope_paths,
            review_output_schema_version=preflight_evidence.review_output_schema_version,
            transport=resolved_transport,
        )
        if adapter_result.adapter_status == "blocked":
            return ConfirmedSandboxCandidateDiffReadonlyReviewExecution(
                result=adapter_result,
                message=None,
            )

        if session_obj is None:
            return ConfirmedSandboxCandidateDiffReadonlyReviewExecution(
                result=self._blocked_result(
                    requested_reviewer_executor=(
                        preflight_evidence.requested_reviewer_executor
                    ),
                    review_scope_paths=preflight_evidence.review_scope_paths,
                    review_output_schema_version=(
                        preflight_evidence.review_output_schema_version
                    ),
                    blocked_reasons=["session_missing"],
                ),
                message=None,
            )

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "Readonly review execution 已完成。Review output 已通过 "
                    "strict validation。verdict 是 reviewer verdict，不是 human "
                    "approval，不是 Git write authorization。没有应用 patch。"
                    "没有执行 Git 写。AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_readonly_review_execution",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL
                ),
                suggested_actions=[
                    self._readonly_review_execution_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        source_preflight_message_id=source_message_id,
                        preflight_evidence=preflight_evidence,
                        adapter_result=adapter_result,
                    )
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=[
                    "no_human_approval_recorded",
                    "no_patch_apply",
                    "no_product_runtime_git_write",
                    "no_worker_dispatch",
                    "no_task_creation",
                    "no_run_creation",
                ],
            )
        )
        self._message_repository.commit()
        return ConfirmedSandboxCandidateDiffReadonlyReviewExecution(
            result=adapter_result,
            message=message,
        )

    @staticmethod
    def _preflight_action(
        *,
        source_preflight_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_preflight_message is None:
            blocked_reasons.append("source_preflight_message_missing")
            return None
        if source_preflight_message.session_id != session_id:
            blocked_reasons.append("source_preflight_message_session_mismatch")
        if source_preflight_message.related_task_id != source_task_id:
            blocked_reasons.append("source_preflight_message_task_mismatch")
        if (
            source_preflight_message.source_detail
            != P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_message_is_not_p21_c_review_preflight")
        action = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService._first_action(
            source_preflight_message,
            expected_type=(
                P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_ACTION_TYPE
            ),
        )
        if action is None:
            blocked_reasons.append("p21_c_review_execution_preflight_record_missing")
            return None
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_task_not_bound_to_review_preflight")
        if action.get("review_execution_preflight_status") != "ready":
            blocked_reasons.append("source_preflight_not_ready")
        if not all(action.get(flag) is False for flag in _PREFLIGHT_FALSE_FLAGS):
            blocked_reasons.append("source_preflight_write_boundary_violated")
        if action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("source_preflight_write_boundary_violated")
        return action

    @classmethod
    def _preflight_evidence(
        cls,
        action: dict[str, Any] | None,
        *,
        blocked_reasons: list[str],
    ) -> _PersistedPreflightEvidence | None:
        if action is None:
            return None

        requested_reviewer_executor = action.get("requested_reviewer_executor")
        if requested_reviewer_executor not in ("codex", "claude-code"):
            blocked_reasons.append("requested_reviewer_executor_invalid")
            requested_reviewer_executor = ""

        source_diff_message_id = cls._uuid_from_action(
            action,
            "source_diff_message_id",
            blocked_reason="source_diff_message_id_missing",
            blocked_reasons=blocked_reasons,
        )
        source_diff_sha256 = cls._sha256_from_action(
            action,
            "source_diff_sha256",
            "source_diff_sha256_invalid",
            blocked_reasons=blocked_reasons,
        )
        review_prompt_sha256 = cls._sha256_from_action(
            action,
            "review_prompt_sha256",
            "review_prompt_sha256_invalid",
            blocked_reasons=blocked_reasons,
        )
        review_prompt_bytes = action.get("review_prompt_bytes")
        if not isinstance(review_prompt_bytes, int) or review_prompt_bytes <= 0:
            blocked_reasons.append("review_prompt_bytes_invalid")
            review_prompt_bytes = 0

        review_scope_paths = cls._review_scope_paths(
            action,
            blocked_reasons=blocked_reasons,
        )

        review_output_schema_version = action.get("review_output_schema_version")
        if review_output_schema_version != REVIEW_OUTPUT_SCHEMA_VERSION:
            blocked_reasons.append("review_output_schema_version_mismatch")
            review_output_schema_version = REVIEW_OUTPUT_SCHEMA_VERSION

        if source_diff_message_id is None:
            return None
        return _PersistedPreflightEvidence(
            requested_reviewer_executor=requested_reviewer_executor,
            source_diff_message_id=source_diff_message_id,
            source_diff_sha256=source_diff_sha256,
            review_scope_paths=review_scope_paths,
            review_prompt_sha256=review_prompt_sha256,
            review_prompt_bytes=review_prompt_bytes,
            review_output_schema_version=review_output_schema_version,
        )

    @staticmethod
    def _source_diff_action(
        *,
        source_diff_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_diff_message is None:
            blocked_reasons.append("source_diff_message_missing")
            return None
        if source_diff_message.session_id != session_id:
            blocked_reasons.append("source_diff_message_session_mismatch")
        if source_diff_message.related_task_id != source_task_id:
            blocked_reasons.append("source_diff_message_task_mismatch")
        if source_diff_message.source_detail != P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL:
            blocked_reasons.append(
                "source_diff_message_is_not_p21_c_candidate_diff_generated"
            )
        action = ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService._first_action(
            source_diff_message,
            expected_type=P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("p21_c_candidate_diff_generate_record_missing")
            return None
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_task_not_bound_to_candidate_diff")
        return action

    @classmethod
    def _validated_unified_diff_text(
        cls,
        action: dict[str, Any] | None,
        *,
        preflight_evidence: _PersistedPreflightEvidence | None,
        blocked_reasons: list[str],
    ) -> str:
        if action is None or preflight_evidence is None:
            return ""

        if action.get("diff_generation_status") != "generated":
            blocked_reasons.append("source_diff_not_generated")
        if action.get("readonly_real_diff_generated") is not True:
            blocked_reasons.append("source_diff_not_generated")
        if action.get("real_diff_generated") is not True:
            blocked_reasons.append("source_diff_not_generated")
        if not all(action.get(flag) is False for flag in _SOURCE_DIFF_FALSE_FLAGS):
            blocked_reasons.append("source_diff_write_boundary_violated")
        if action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("source_diff_write_boundary_violated")

        unified_diff_text = action.get("unified_diff_text")
        if not isinstance(unified_diff_text, str) or not unified_diff_text:
            blocked_reasons.append("source_diff_not_generated")
            return ""

        diff_bytes = action.get("diff_bytes")
        actual_diff_bytes = len(unified_diff_text.encode("utf-8"))
        if diff_bytes != actual_diff_bytes:
            blocked_reasons.append("source_diff_bytes_mismatch")

        actual_source_diff_sha256 = hashlib.sha256(
            unified_diff_text.encode("utf-8")
        ).hexdigest()
        if actual_source_diff_sha256 != preflight_evidence.source_diff_sha256:
            blocked_reasons.append("source_diff_sha256_mismatch")

        diff_entries = action.get("diff_entries")
        if not isinstance(diff_entries, list) or not diff_entries:
            blocked_reasons.append("source_diff_entries_missing")
            diff_entries = []
        diff_file_count = action.get("diff_file_count")
        if diff_file_count != len(diff_entries):
            blocked_reasons.append("source_diff_file_count_mismatch")

        entry_scope_paths: list[str] = []
        seen_paths: set[str] = set()
        for entry in diff_entries:
            if not isinstance(entry, dict):
                blocked_reasons.append("source_diff_entries_invalid")
                continue
            relative_path = entry.get("relative_path")
            entry_diff = entry.get("unified_diff")
            entry_bytes = entry.get("diff_bytes")
            if not isinstance(relative_path, str) or not relative_path:
                blocked_reasons.append("source_diff_entries_invalid")
                continue
            if not isinstance(entry_diff, str) or not entry_diff:
                blocked_reasons.append("source_diff_entries_invalid")
                continue
            if not isinstance(entry_bytes, int) or entry_bytes != len(
                entry_diff.encode("utf-8")
            ):
                blocked_reasons.append("source_diff_entries_invalid")
            if relative_path not in seen_paths:
                entry_scope_paths.append(relative_path)
                seen_paths.add(relative_path)

        if entry_scope_paths != preflight_evidence.review_scope_paths:
            blocked_reasons.append("review_scope_paths_mismatch")

        return unified_diff_text

    @staticmethod
    def _reconstructed_review_prompt(
        *,
        preflight_evidence: _PersistedPreflightEvidence | None,
        unified_diff_text: str,
        blocked_reasons: list[str],
    ) -> str:
        if preflight_evidence is None or not unified_diff_text:
            return ""
        try:
            review_prompt_text = (
                ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService
                .build_readonly_review_prompt(
                    requested_reviewer_executor=(
                        preflight_evidence.requested_reviewer_executor
                    ),
                    source_diff_sha256=preflight_evidence.source_diff_sha256,
                    review_scope_paths=preflight_evidence.review_scope_paths,
                    unified_diff_text=unified_diff_text,
                    review_output_schema_version=(
                        preflight_evidence.review_output_schema_version
                    ),
                )
            )
        except (TypeError, ValueError):
            blocked_reasons.append("review_prompt_build_failed")
            return ""

        review_prompt_bytes = len(review_prompt_text.encode("utf-8"))
        review_prompt_sha256 = hashlib.sha256(
            review_prompt_text.encode("utf-8")
        ).hexdigest()
        if review_prompt_sha256 != preflight_evidence.review_prompt_sha256:
            blocked_reasons.append("review_prompt_sha256_mismatch")
        if review_prompt_bytes != preflight_evidence.review_prompt_bytes:
            blocked_reasons.append("review_prompt_bytes_mismatch")
        return review_prompt_text

    @staticmethod
    def _trusted_source_diff_workspace_path(
        source_diff_action: dict[str, Any] | None,
        *,
        blocked_reasons: list[str],
    ) -> str:
        if source_diff_action is None:
            blocked_reasons.append("source_diff_workspace_evidence_missing")
            return ""
        workspace_path = source_diff_action.get("workspace_path")
        if not isinstance(workspace_path, str) or not workspace_path.strip():
            blocked_reasons.append("source_diff_workspace_path_missing")
            return ""
        if source_diff_action.get("workspace_path_within_root") is not True:
            blocked_reasons.append("source_diff_workspace_path_not_within_root")
            return ""
        return workspace_path

    @staticmethod
    def _readonly_review_execution_action(
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_preflight_message_id: UUID,
        preflight_evidence: _PersistedPreflightEvidence,
        adapter_result: ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult,
    ) -> dict[str, Any]:
        action = {
            "type": P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_preflight_message_id": str(source_preflight_message_id),
            "source_diff_message_id": str(preflight_evidence.source_diff_message_id),
            "requested_reviewer_executor": (
                preflight_evidence.requested_reviewer_executor
            ),
            "source_diff_sha256": preflight_evidence.source_diff_sha256,
            "review_prompt_sha256": preflight_evidence.review_prompt_sha256,
            "review_prompt_bytes": preflight_evidence.review_prompt_bytes,
            "review_scope_paths": list(preflight_evidence.review_scope_paths),
            "review_output_schema_version": (
                preflight_evidence.review_output_schema_version
            ),
            "adapter_status": adapter_result.adapter_status,
            "execution_mode": adapter_result.execution_mode,
            "transport_status": adapter_result.transport_status,
            "transport_error_code": adapter_result.transport_error_code,
            "output_validation_status": adapter_result.output_validation_status,
            "raw_output_sha256": adapter_result.raw_output_sha256,
            "raw_output_bytes": adapter_result.raw_output_bytes,
            "strict_json_valid": adapter_result.strict_json_valid,
            "schema_valid": adapter_result.schema_valid,
            "semantics_valid": adapter_result.semantics_valid,
            "evidence_scope_valid": adapter_result.evidence_scope_valid,
            "review_status": adapter_result.review_status,
            "verdict": adapter_result.verdict,
            "risk_level": adapter_result.risk_level,
            "summary": adapter_result.summary,
            "findings": adapter_result.findings,
            "recommended_next_step": adapter_result.recommended_next_step,
            "real_reviewer_started": adapter_result.real_reviewer_started,
            "real_reviewer_executed": adapter_result.real_reviewer_executed,
            "native_process_started": adapter_result.native_process_started,
            "provider_called": adapter_result.provider_called,
            "codex_started": adapter_result.codex_started,
            "claude_code_started": adapter_result.claude_code_started,
            "main_project_file_written": False,
            "sandbox_file_written": False,
            "manifest_file_written": False,
            "diff_file_written": False,
            "patch_applied": False,
            "git_write_performed": False,
            "worktree_created": False,
            "worker_started": False,
            "task_created": False,
            "run_created": False,
            "ai_project_director_total_loop": "Partial",
        }
        return _json_safe(action)

    @staticmethod
    def _blocked_result(
        *,
        requested_reviewer_executor: str,
        review_scope_paths: list[str],
        review_output_schema_version: str,
        blocked_reasons: list[str],
    ) -> ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult:
        return ProjectDirectorSandboxCandidateDiffReadonlyReviewerAdapterResult(
            adapter_status="blocked",
            requested_reviewer_executor=requested_reviewer_executor,
            review_scope_paths=list(review_scope_paths),
            review_output_schema_version=review_output_schema_version,
            blocked_reasons=_dedupe(blocked_reasons),
        )

    @staticmethod
    def _first_action(
        source_message: ProjectDirectorMessage,
        *,
        expected_type: str,
    ) -> dict[str, Any] | None:
        if not source_message.suggested_actions:
            return None
        first_action = source_message.suggested_actions[0]
        if not isinstance(first_action, dict):
            return None
        if first_action.get("type") != expected_type:
            return None
        return first_action

    @staticmethod
    def _review_scope_paths(
        action: dict[str, Any],
        *,
        blocked_reasons: list[str],
    ) -> list[str]:
        raw_paths = action.get("review_scope_paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            blocked_reasons.append("review_scope_paths_missing")
            return []
        paths: list[str] = []
        seen_paths: set[str] = set()
        for raw_path in raw_paths:
            if not isinstance(raw_path, str) or not raw_path:
                blocked_reasons.append("review_scope_paths_invalid")
                continue
            if raw_path in seen_paths:
                blocked_reasons.append("review_scope_paths_invalid")
                continue
            paths.append(raw_path)
            seen_paths.add(raw_path)
        return paths

    @staticmethod
    def _uuid_from_action(
        action: dict[str, Any],
        key: str,
        *,
        blocked_reason: str,
        blocked_reasons: list[str],
    ) -> UUID | None:
        raw_value = action.get(key)
        if not isinstance(raw_value, str) or not raw_value:
            blocked_reasons.append(blocked_reason)
            return None
        try:
            return UUID(raw_value)
        except ValueError:
            blocked_reasons.append(blocked_reason)
            return None

    @staticmethod
    def _sha256_from_action(
        action: dict[str, Any],
        key: str,
        blocked_reason: str,
        *,
        blocked_reasons: list[str],
    ) -> str:
        value = action.get(key)
        if not isinstance(value, str) or not _LOWER_HEX_SHA256.match(value):
            blocked_reasons.append(blocked_reason)
            return ""
        return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        result.append(value)
        seen.add(value)
    return result


__all__ = (
    "ConfirmedSandboxCandidateDiffReadonlyReviewExecution",
    "P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE",
    "P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL",
    "ProjectDirectorSandboxCandidateDiffReadonlyReviewExecutionService",
    "ReadonlyReviewerTransportResolverFactoryProtocol",
    "ReadonlyReviewerTransportResolverProtocol",
)
