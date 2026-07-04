"""Readonly real diff review handoff service for Project Director P21-C-G."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_handoff import (
    ProjectDirectorSandboxCandidateDiffReviewHandoffResult,
    SandboxCandidateDiffReviewExecutor,
    SandboxCandidateDiffReviewHandoffMode,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_workspace_guard_service import (
    ProjectDirectorSandboxWorkspaceGuardService,
)


P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL = (
    "p21_c_sandbox_candidate_diff_review_handoff_created"
)
P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_ACTION_TYPE = (
    "p21_c_sandbox_candidate_diff_review_handoff_record"
)

REQUIRED_PRECONDITIONS = [
    "p21_c_candidate_diff_generated_required",
    "source_diff_message_binding_required",
    "source_diff_integrity_check_required",
    "source_diff_sha256_required",
    "safe_dry_run_task_required",
    "user_confirmation_required",
    "readonly_real_diff_review_handoff_only",
    "no_reviewer_start_required",
    "no_review_verdict_required",
    "no_patch_apply_required",
    "no_git_worktree_required",
    "no_product_runtime_git_write_required",
    "future_readonly_reviewer_execution_required",
]

ALLOWED_FUTURE_REVIEW_SCOPE = [
    "current step may only create a readonly diff review handoff record",
    "future readonly reviewer execution must be a separate step",
    "future reviewer must verify source_diff_sha256 before review",
    "future reviewer may only review the diff evidence",
    "future reviewer may produce findings and verdict but may not modify code",
    "future patch apply must be separate and user-confirmed",
    "future cleanup must be separate",
    "product runtime Git operations remain forbidden",
]

FORBIDDEN_HANDOFF_ACTIONS = [
    "no_reviewer_start_in_handoff",
    "no_review_execution_in_handoff",
    "no_review_findings_in_handoff",
    "no_review_verdict_in_handoff",
    "no_main_project_file_write",
    "no_sandbox_file_write",
    "no_manifest_file_write",
    "no_diff_file_write",
    "no_patch_apply",
    "no_git_worktree_creation",
    "no_product_runtime_git_write",
    "no_worker_dispatch",
    "no_task_creation",
    "no_run_creation",
    "no_executor_start",
    "no_automatic_commit",
    "no_push",
    "no_pr",
    "no_merge",
    "no_cleanup_in_handoff",
]

SOURCE_DIFF_FALSE_FLAGS = (
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "patch_applied",
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

REQUIRED_DIFF_ENTRY_FIELDS = (
    "relative_path",
    "operation",
    "target_file_path",
    "candidate_file_path",
    "target_file_existed",
    "candidate_file_existed",
    "target_file_content_read",
    "candidate_file_content_read",
    "unified_diff",
    "diff_bytes",
)


@dataclass(frozen=True, slots=True)
class ConfirmedSandboxCandidateDiffReviewHandoff:
    """P21-C-G handoff result and optional persisted message."""

    result: ProjectDirectorSandboxCandidateDiffReviewHandoffResult
    message: ProjectDirectorMessage | None


class ProjectDirectorSandboxCandidateDiffReviewHandoffService:
    """Create a readonly reviewer handoff record without starting review."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository | None = None,
        message_repository: ProjectDirectorMessageRepository | None = None,
        task_repository: TaskRepository | None = None,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository

    def confirm_candidate_diff_review_handoff(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        handoff_mode: SandboxCandidateDiffReviewHandoffMode = (
            "readonly_real_diff_review"
        ),
        requested_reviewer_executor: SandboxCandidateDiffReviewExecutor = "codex",
    ) -> ConfirmedSandboxCandidateDiffReviewHandoff:
        """Validate P21-C-F evidence and persist a readonly review handoff."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("sandbox candidate diff handoff repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        source_message = self._message_repository.get_by_id(source_message_id)

        result = self.build_candidate_diff_review_handoff_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            handoff_mode=handoff_mode,
            requested_reviewer_executor=requested_reviewer_executor,
        )
        if result.review_handoff_status == "blocked":
            return ConfirmedSandboxCandidateDiffReviewHandoff(
                result=result,
                message=None,
            )

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已创建 readonly real diff reviewer handoff record。"
                    "尚未启动 reviewer。尚未执行审查。尚未生成 findings。"
                    "尚未生成 verdict。没有应用 patch。没有写主项目文件。"
                    "没有执行 Git 写。AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_review_handoff",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL
                ),
                suggested_actions=[self._review_handoff_action(result)],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=list(FORBIDDEN_HANDOFF_ACTIONS),
            )
        )
        self._message_repository.commit()
        return ConfirmedSandboxCandidateDiffReviewHandoff(
            result=result,
            message=message,
        )

    def build_candidate_diff_review_handoff_from_sources(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        handoff_mode: SandboxCandidateDiffReviewHandoffMode = (
            "readonly_real_diff_review"
        ),
        requested_reviewer_executor: SandboxCandidateDiffReviewExecutor = "codex",
    ) -> ProjectDirectorSandboxCandidateDiffReviewHandoffResult:
        """Validate P21-C-F diff evidence without rereading files."""

        blocked_reasons: list[str] = []
        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        elif not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_not_safe_dry_run")
        if source_message is None:
            blocked_reasons.append("source_message_missing")
        if handoff_mode != "readonly_real_diff_review":
            blocked_reasons.append("handoff_mode_not_allowed")
        if requested_reviewer_executor not in ("codex", "claude-code"):
            blocked_reasons.append("requested_reviewer_executor_not_allowed")

        source_action = self._candidate_diff_action(
            source_message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )

        source_diff_message_bound = (
            source_action is not None
            and source_action.get("source_task_id") == str(source_task_id)
            and source_message is not None
            and source_message.session_id == session_id
            and source_message.source_detail == P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL
        )

        diff_entries = self._diff_entries(source_action, blocked_reasons)
        unified_diff_text = self._unified_diff_text(source_action, blocked_reasons)
        diff_file_count = self._int_action_value(source_action, "diff_file_count")
        diff_bytes = self._int_action_value(source_action, "diff_bytes")

        if source_action is not None:
            if source_action.get("diff_generation_status") != "generated":
                blocked_reasons.append("source_diff_not_generated")
            if source_action.get("readonly_real_diff_generated") is not True:
                blocked_reasons.append("source_diff_not_readonly")
            if source_action.get("real_diff_generated") is not True:
                blocked_reasons.append("source_diff_not_readonly")
            if diff_file_count <= 0 or diff_bytes <= 0 or not unified_diff_text:
                blocked_reasons.append("source_diff_not_generated")
            if source_action.get("workspace_path_within_root") is not True:
                blocked_reasons.append("source_diff_not_generated")
            if not self._source_diff_action_has_no_write_or_execute(source_action):
                blocked_reasons.append("source_diff_write_boundary_violated")
            if source_action.get("ai_project_director_total_loop") != "Partial":
                blocked_reasons.append("source_diff_write_boundary_violated")

        review_scope_paths = self._review_scope_paths(diff_entries)
        if source_action is not None and diff_entries:
            if diff_file_count != len(diff_entries):
                blocked_reasons.append("source_diff_file_count_mismatch")
            recalculated_diff_bytes = len(unified_diff_text.encode("utf-8"))
            if diff_bytes != recalculated_diff_bytes:
                blocked_reasons.append("source_diff_bytes_mismatch")
            entry_diff_text_parts: list[str] = []
            for entry in diff_entries:
                if not self._diff_entry_is_valid(entry):
                    blocked_reasons.append("source_diff_entry_invalid")
                    continue
                entry_diff = entry.get("unified_diff")
                entry_diff_text_parts.append(entry_diff)
                entry_diff_bytes = entry.get("diff_bytes")
                if not isinstance(entry_diff_bytes, int) or entry_diff_bytes != len(
                    entry_diff.encode("utf-8")
                ):
                    blocked_reasons.append("source_diff_entry_bytes_mismatch")
            if "".join(entry_diff_text_parts) != unified_diff_text:
                blocked_reasons.append("source_diff_aggregation_mismatch")

        blocked_reasons = self._dedupe(blocked_reasons)
        source_diff_verified = (
            not blocked_reasons
            and source_action is not None
            and source_diff_message_bound
            and bool(diff_entries)
        )
        review_handoff_status = "created" if source_diff_verified else "blocked"
        source_diff_sha256 = (
            hashlib.sha256(unified_diff_text.encode("utf-8")).hexdigest()
            if source_diff_verified
            else ""
        )
        cleanup_required = bool(
            source_action is not None and source_action.get("cleanup_required") is True
        )

        return ProjectDirectorSandboxCandidateDiffReviewHandoffResult(
            review_handoff_status=review_handoff_status,
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            source_diff_message_id=source_message_id,
            handoff_mode=handoff_mode,
            requested_reviewer_executor=requested_reviewer_executor,
            source_diff_message_bound=source_diff_message_bound,
            source_diff_verified=source_diff_verified,
            source_diff_sha256=source_diff_sha256,
            diff_file_count=diff_file_count if source_diff_verified else 0,
            diff_bytes=diff_bytes if source_diff_verified else 0,
            review_scope_paths=review_scope_paths if source_diff_verified else [],
            target_file_content_read=bool(
                source_action is not None
                and source_action.get("target_file_content_read") is True
            ),
            candidate_file_content_read=bool(
                source_action is not None
                and source_action.get("candidate_file_content_read") is True
            ),
            readonly_real_diff_generated=bool(
                source_action is not None
                and source_action.get("readonly_real_diff_generated") is True
            ),
            real_diff_generated=bool(
                source_action is not None
                and source_action.get("real_diff_generated") is True
            ),
            cleanup_required=cleanup_required,
            cleanup_hint=self._cleanup_hint(cleanup_required=cleanup_required),
            required_preconditions=list(REQUIRED_PRECONDITIONS),
            allowed_future_review_scope=list(ALLOWED_FUTURE_REVIEW_SCOPE),
            forbidden_handoff_actions=list(FORBIDDEN_HANDOFF_ACTIONS),
            blocked_reasons=blocked_reasons,
            risks=[
                "handoff is not a review verdict",
                "future reviewer must verify the source diff hash before review",
                "product runtime Git writes remain forbidden",
            ],
            unknowns=[
                "readonly reviewer execution remains future work",
                "review findings remain future work",
                "review verdict remains future work",
            ],
            review_handoff_summary=self._review_handoff_summary(
                review_handoff_status=review_handoff_status
            ),
            recommended_next_step=(
                "Run a separate readonly real diff reviewer step that first verifies "
                "source_diff_sha256, then reviews only the diff evidence without patch, "
                "worktree, Worker, Task, Run, cleanup, or product runtime Git writes."
            ),
        )

    def _candidate_diff_action(
        self,
        *,
        source_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_message is None:
            return None
        if (
            source_message.session_id != session_id
            or source_message.source_detail != P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL
        ):
            blocked_reasons.append(
                "source_message_is_not_p21_c_candidate_diff_generated"
            )
        action = self._first_action(
            source_message,
            expected_type=P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("p21_c_candidate_diff_generate_record_missing")
            return None
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_task_not_bound_to_candidate_diff")
        return action

    @staticmethod
    def _diff_entries(
        action: dict[str, Any] | None,
        blocked_reasons: list[str],
    ) -> list[dict[str, Any]]:
        if action is None:
            return []
        raw_entries = action.get("diff_entries")
        if not isinstance(raw_entries, list) or not raw_entries:
            blocked_reasons.append("source_diff_entries_missing")
            return []
        entries: list[dict[str, Any]] = []
        for item in raw_entries:
            if isinstance(item, dict):
                entries.append(item)
            else:
                blocked_reasons.append("source_diff_entry_invalid")
        return entries

    @staticmethod
    def _unified_diff_text(
        action: dict[str, Any] | None,
        blocked_reasons: list[str],
    ) -> str:
        if action is None:
            return ""
        value = action.get("unified_diff_text")
        if not isinstance(value, str) or not value:
            blocked_reasons.append("source_diff_not_generated")
            return ""
        return value

    @staticmethod
    def _int_action_value(action: dict[str, Any] | None, key: str) -> int:
        if action is None:
            return 0
        value = action.get(key)
        return value if isinstance(value, int) else 0

    @staticmethod
    def _diff_entry_is_valid(entry: dict[str, Any]) -> bool:
        if any(field not in entry for field in REQUIRED_DIFF_ENTRY_FIELDS):
            return False
        operation = entry.get("operation")
        if operation not in ("create", "update"):
            return False
        if entry.get("candidate_file_existed") is not True:
            return False
        if entry.get("candidate_file_content_read") is not True:
            return False
        if not isinstance(entry.get("relative_path"), str) or not entry["relative_path"]:
            return False
        if not isinstance(entry.get("target_file_path"), str):
            return False
        if not isinstance(entry.get("candidate_file_path"), str):
            return False
        if not isinstance(entry.get("unified_diff"), str) or not entry["unified_diff"]:
            return False
        if not isinstance(entry.get("diff_bytes"), int):
            return False
        if operation == "create":
            return (
                entry.get("target_file_existed") is False
                and entry.get("target_file_content_read") is False
            )
        return (
            entry.get("target_file_existed") is True
            and entry.get("target_file_content_read") is True
        )

    @staticmethod
    def _review_scope_paths(diff_entries: list[dict[str, Any]]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for entry in diff_entries:
            value = entry.get("relative_path")
            if not isinstance(value, str) or not value or value in seen:
                continue
            result.append(value)
            seen.add(value)
        return result

    @staticmethod
    def _source_diff_action_has_no_write_or_execute(action: dict[str, Any]) -> bool:
        return all(action.get(flag) is False for flag in SOURCE_DIFF_FALSE_FLAGS)

    @staticmethod
    def _is_safe_dry_run_task(task: Task) -> bool:
        return ProjectDirectorSandboxWorkspaceGuardService._is_safe_dry_run_task(task)

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
    def _cleanup_hint(*, cleanup_required: bool) -> str:
        if cleanup_required:
            return (
                "cleanup_required=true is inherited from readonly diff generation; "
                "no cleanup was performed in review handoff."
            )
        return (
            "cleanup_required=false because the source diff generation did not "
            "require cleanup; no cleanup was performed in review handoff."
        )

    @staticmethod
    def _review_handoff_summary(*, review_handoff_status: str) -> str:
        if review_handoff_status == "created":
            return (
                "P21-C-G created a readonly real diff reviewer handoff record. "
                "It did not start a reviewer, execute review, produce findings or "
                "verdict, write files, apply patches, create worktrees, create "
                "Tasks/Runs, clean up, or perform Git writes."
            )
        return (
            "P21-C-G readonly real diff reviewer handoff was blocked before message "
            "creation, reviewer start, review execution, findings, verdict, file "
            "write, patch, worktree, Task, Run, cleanup, or Git side effect."
        )

    @staticmethod
    def _review_handoff_action(
        result: ProjectDirectorSandboxCandidateDiffReviewHandoffResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_ACTION_TYPE,
            "review_handoff_status": result.review_handoff_status,
            "source_task_id": (
                str(result.source_task_id)
                if result.source_task_id is not None
                else None
            ),
            "source_message_id": (
                str(result.source_message_id)
                if result.source_message_id is not None
                else None
            ),
            "source_diff_message_id": (
                str(result.source_diff_message_id)
                if result.source_diff_message_id is not None
                else None
            ),
            "handoff_mode": result.handoff_mode,
            "requested_reviewer_executor": result.requested_reviewer_executor,
            "source_diff_sha256": result.source_diff_sha256,
            "diff_file_count": result.diff_file_count,
            "diff_bytes": result.diff_bytes,
            "review_scope_paths": list(result.review_scope_paths),
            "reviewer_started": False,
            "review_executed": False,
            "review_verdict_generated": False,
            "review_findings_generated": False,
            "main_project_file_written": False,
            "sandbox_file_written": False,
            "manifest_file_written": False,
            "diff_file_written": False,
            "patch_applied": False,
            "product_runtime_git_write_allowed": False,
            "main_worktree_write_allowed": False,
            "worktree_write_allowed": False,
            "file_write_allowed": False,
            "actual_patch_applied": False,
            "real_code_modified": False,
            "git_write_performed": False,
            "native_executor_started": False,
            "codex_started": False,
            "claude_code_started": False,
            "worker_started": False,
            "task_created": False,
            "run_created": False,
            "worktree_created": False,
            "worktree_cleaned_up": False,
            "rollback_snapshot_created": False,
            "cleanup_required": result.cleanup_required,
            "cleanup_hint": result.cleanup_hint,
            "ai_project_director_total_loop": "Partial",
        }

    @staticmethod
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
    "ConfirmedSandboxCandidateDiffReviewHandoff",
    "P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_ACTION_TYPE",
    "P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL",
    "ProjectDirectorSandboxCandidateDiffReviewHandoffService",
)
