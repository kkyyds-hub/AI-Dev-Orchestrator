"""Readonly reviewer execution preflight service for Project Director P21-C-H-A."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_execution_preflight import (
    ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightResult,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_review_handoff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_workspace_guard_service import (
    ProjectDirectorSandboxWorkspaceGuardService,
)


P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL = (
    "p21_c_sandbox_candidate_diff_review_execution_preflight_ready"
)
P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_ACTION_TYPE = (
    "p21_c_sandbox_candidate_diff_review_execution_preflight_record"
)
REVIEW_INPUT_SCHEMA_VERSION = "p21-c-h-a.v1"
REVIEW_OUTPUT_SCHEMA_VERSION = "p21-c-h-review-output.v1"

REQUIRED_PRECONDITIONS = [
    "p21_c_review_handoff_required",
    "source_handoff_message_binding_required",
    "source_diff_message_binding_required",
    "source_diff_integrity_revalidation_required",
    "review_scope_paths_required",
    "safe_dry_run_task_required",
    "user_confirmation_required",
    "deterministic_review_prompt_required",
    "strict_json_output_contract_required",
    "no_reviewer_start_in_preflight",
    "no_provider_call_in_preflight",
    "no_findings_or_verdict_in_preflight",
    "no_patch_apply_required",
    "no_git_worktree_required",
    "no_product_runtime_git_write_required",
]

ALLOWED_FUTURE_REVIEW_EXECUTION_SCOPE = [
    "current step may only lock readonly reviewer execution input",
    "future H-B may reconstruct the same prompt from P21-C-F evidence",
    "future H-B must verify review_prompt_sha256 before execution",
    "future reviewer may only review the supplied unified diff",
    "future reviewer output must be one JSON object matching the locked contract",
    "future reviewer may produce findings and verdict but may not modify code",
    "future patch apply must be separate and user-confirmed",
    "product runtime Git operations remain forbidden",
]

FORBIDDEN_PREFLIGHT_ACTIONS = [
    "no_reviewer_start_in_preflight",
    "no_review_execution_in_preflight",
    "no_review_findings_in_preflight",
    "no_review_verdict_in_preflight",
    "no_provider_call_in_preflight",
    "no_native_executor_start",
    "no_codex_start",
    "no_claude_code_start",
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
]

HANDOFF_FALSE_FLAGS = (
    "reviewer_started",
    "review_executed",
    "review_findings_generated",
    "review_verdict_generated",
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
    "git_write_performed",
    "native_executor_started",
    "codex_started",
    "claude_code_started",
    "worker_started",
    "task_created",
    "run_created",
    "worktree_created",
)

SOURCE_DIFF_FALSE_FLAGS = (
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

SOURCE_DIFF_ENTRY_REQUIRED_FIELDS = (
    "relative_path",
    "unified_diff",
    "diff_bytes",
)

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ConfirmedSandboxCandidateDiffReviewExecutionPreflight:
    """P21-C-H-A preflight result and optional persisted message."""

    result: ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightResult
    message: ProjectDirectorMessage | None


class ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService:
    """Lock readonly reviewer execution input without starting a reviewer."""

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

    def confirm_candidate_diff_review_execution_preflight(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
    ) -> ConfirmedSandboxCandidateDiffReviewExecutionPreflight:
        """Validate P21-C-G/F evidence and persist a ready preflight record."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("sandbox diff review preflight repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        source_handoff_message = self._message_repository.get_by_id(source_message_id)

        result = self.build_candidate_diff_review_execution_preflight_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            source_task=source_task,
            source_handoff_message=source_handoff_message,
            user_confirmed=user_confirmed,
        )
        if result.review_execution_preflight_status == "blocked":
            return ConfirmedSandboxCandidateDiffReviewExecutionPreflight(
                result=result,
                message=None,
            )

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "Reviewer execution input 已锁定。Source diff SHA256 已重新验证。"
                    "Review prompt SHA256 已记录。尚未启动 reviewer。尚未执行 review。"
                    "尚未生成 findings。尚未生成 verdict。没有应用 patch。"
                    "没有执行 Git 写。未调用 Provider。未启动 Codex / Claude。"
                    "AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_review_execution_preflight",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL
                ),
                suggested_actions=[self._review_execution_preflight_action(result)],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=list(FORBIDDEN_PREFLIGHT_ACTIONS),
            )
        )
        self._message_repository.commit()
        return ConfirmedSandboxCandidateDiffReviewExecutionPreflight(
            result=result,
            message=message,
        )

    def build_candidate_diff_review_execution_preflight_from_sources(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        source_task: Task | None,
        source_handoff_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
    ) -> ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightResult:
        """Validate G handoff and F diff message evidence only."""

        blocked_reasons: list[str] = []
        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        elif not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_not_safe_dry_run")

        handoff_action = self._review_handoff_action(
            source_handoff_message=source_handoff_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        requested_reviewer_executor = self._requested_reviewer_executor(
            handoff_action,
            blocked_reasons=blocked_reasons,
        )
        source_diff_sha256 = self._source_diff_sha256(
            handoff_action,
            blocked_reasons=blocked_reasons,
        )
        review_scope_paths = self._review_scope_paths(
            handoff_action,
            blocked_reasons=blocked_reasons,
        )
        source_diff_message_id = self._uuid_from_action(
            handoff_action,
            "source_diff_message_id",
            blocked_reason="source_diff_message_id_missing",
            blocked_reasons=blocked_reasons,
        )
        source_diff_message = (
            self._message_repository.get_by_id(source_diff_message_id)
            if self._message_repository is not None
            and source_diff_message_id is not None
            else None
        )
        diff_action = self._source_diff_action(
            source_diff_message=source_diff_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        unified_diff_text = self._unified_diff_text(
            diff_action,
            blocked_reasons=blocked_reasons,
        )

        self._validate_handoff_action(
            handoff_action=handoff_action,
            blocked_reasons=blocked_reasons,
        )
        self._validate_source_diff_action(
            diff_action=diff_action,
            source_diff_sha256=source_diff_sha256,
            review_scope_paths=review_scope_paths,
            unified_diff_text=unified_diff_text,
            blocked_reasons=blocked_reasons,
        )

        source_handoff_verified = (
            handoff_action is not None
            and not any(
                reason
                in blocked_reasons
                for reason in (
                    "source_handoff_message_missing",
                    "source_message_is_not_p21_c_review_handoff",
                    "p21_c_review_handoff_record_missing",
                    "source_task_not_bound_to_review_handoff",
                    "source_handoff_not_created",
                    "source_handoff_not_verified",
                    "source_handoff_write_boundary_violated",
                    "source_diff_sha256_invalid",
                    "review_scope_paths_missing",
                )
            )
        )
        source_diff_verified = (
            diff_action is not None
            and not any(
                reason
                in blocked_reasons
                for reason in (
                    "source_diff_message_missing",
                    "source_diff_message_is_not_p21_c_candidate_diff_generated",
                    "p21_c_candidate_diff_generate_record_missing",
                    "source_diff_not_generated",
                    "source_diff_write_boundary_violated",
                    "source_diff_sha256_mismatch",
                )
            )
        )

        review_prompt_text = ""
        review_prompt_sha256 = ""
        review_prompt_bytes = 0
        if not blocked_reasons:
            try:
                review_prompt_text = self.build_readonly_review_prompt(
                    requested_reviewer_executor=requested_reviewer_executor,
                    source_diff_sha256=source_diff_sha256,
                    review_scope_paths=review_scope_paths,
                    unified_diff_text=unified_diff_text,
                    review_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
                )
                review_prompt_bytes = len(review_prompt_text.encode("utf-8"))
                review_prompt_sha256 = hashlib.sha256(
                    review_prompt_text.encode("utf-8")
                ).hexdigest()
            except (TypeError, ValueError):
                blocked_reasons.append("review_prompt_build_failed")

        blocked_reasons = self._dedupe(blocked_reasons)
        status = "ready" if not blocked_reasons else "blocked"

        return ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightResult(
            review_execution_preflight_status=status,
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            source_handoff_message_id=source_message_id,
            source_diff_message_id=source_diff_message_id,
            requested_reviewer_executor=requested_reviewer_executor,
            source_handoff_verified=source_handoff_verified and status == "ready",
            source_diff_verified=source_diff_verified and status == "ready",
            source_diff_sha256=source_diff_sha256 if status == "ready" else "",
            review_input_schema_version=REVIEW_INPUT_SCHEMA_VERSION,
            review_output_schema_version=REVIEW_OUTPUT_SCHEMA_VERSION,
            review_prompt_sha256=review_prompt_sha256 if status == "ready" else "",
            review_prompt_bytes=review_prompt_bytes if status == "ready" else 0,
            review_scope_paths=review_scope_paths if status == "ready" else [],
            required_preconditions=list(REQUIRED_PRECONDITIONS),
            allowed_future_review_execution_scope=(
                list(ALLOWED_FUTURE_REVIEW_EXECUTION_SCOPE)
            ),
            forbidden_preflight_actions=list(FORBIDDEN_PREFLIGHT_ACTIONS),
            blocked_reasons=blocked_reasons,
            risks=[
                "preflight locks input but is not a review verdict",
                "future reviewer must rebuild and verify the prompt fingerprint",
                "product runtime Git writes remain forbidden",
            ],
            unknowns=[
                "readonly reviewer execution remains future work",
                "review findings remain future work",
                "review verdict remains future work",
            ],
            review_execution_preflight_summary=self._preflight_summary(status=status),
            recommended_next_step=(
                "P21-C-H-B may reconstruct the readonly reviewer prompt from the "
                "same P21-C-F diff evidence, verify review_prompt_sha256, and only "
                "then run readonly review execution without patch, worktree, Worker, "
                "Task, Run, or product runtime Git writes."
            ),
        )

    @staticmethod
    def build_readonly_review_prompt(
        *,
        requested_reviewer_executor: str,
        source_diff_sha256: str,
        review_scope_paths: list[str],
        unified_diff_text: str,
        review_output_schema_version: str = REVIEW_OUTPUT_SCHEMA_VERSION,
    ) -> str:
        """Build a deterministic readonly reviewer prompt from persisted evidence."""

        if requested_reviewer_executor not in ("codex", "claude-code"):
            raise ValueError("requested_reviewer_executor_not_allowed")
        if not _LOWER_HEX_SHA256.match(source_diff_sha256):
            raise ValueError("source_diff_sha256_invalid")
        if not review_scope_paths or any(not path for path in review_scope_paths):
            raise ValueError("review_scope_paths_missing")
        if not unified_diff_text:
            raise ValueError("source_diff_not_generated")

        scope_lines = "\n".join(f"- {path}" for path in review_scope_paths)
        return "\n".join(
            [
                "[System Role]",
                "You are a readonly code reviewer.",
                f"requested_reviewer_executor={requested_reviewer_executor}",
                "You may only review the unified diff provided below.",
                "You must not read files.",
                "You must not request more files.",
                "You must not use shell.",
                "You must not use Git.",
                "You must not modify code.",
                "You must not apply patches.",
                "You must not create worktrees.",
                "You must not commit, push, open PRs, or merge.",
                "You must not treat the review verdict as human approval or merge authorization.",
                "",
                "[Review Scope]",
                scope_lines,
                "",
                "[Source Diff Integrity]",
                f"source_diff_sha256={source_diff_sha256}",
                "",
                "[Review Instructions]",
                "Check only issues supported by evidence in the diff.",
                "Focus on correctness, regression risk, security risk, data loss risk, exception handling, boundary violations, and test gaps.",
                "Do not create low-value findings for speculative optimizations.",
                "",
                "[Unified Diff]",
                unified_diff_text,
                "",
                "[Required JSON Output]",
                f"review_output_schema_version={review_output_schema_version}",
                "Return exactly one JSON object.",
                "Do not use Markdown code fences.",
                "Do not add explanatory text before or after the JSON.",
                "Do not output XML or YAML.",
                "The object must match this contract:",
                "{",
                '  "review_status": "reviewed",',
                '  "verdict": "no_blocking_findings | non_blocking_findings | changes_required",',
                '  "risk_level": "low | medium | high",',
                '  "summary": "string",',
                '  "findings": [',
                "    {",
                '      "finding_id": "string",',
                '      "severity": "low | medium | high",',
                '      "title": "string",',
                '      "summary": "string",',
                '      "evidence_paths": ["relative/path.py"],',
                '      "recommended_action": "string"',
                "    }",
                "  ],",
                '  "recommended_next_step": "string"',
                "}",
                "findings must contain at most 20 items.",
                "evidence_paths must be selected from Review Scope paths.",
                "findings may be empty only when verdict is no_blocking_findings.",
                "changes_required requires at least one medium or high severity finding.",
                "Do not output patches.",
                "Do not output modified full files.",
                "Do not output Git commands.",
                "Do not claim the change is approved to merge.",
            ]
        )

    def _review_handoff_action(
        self,
        *,
        source_handoff_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_handoff_message is None:
            blocked_reasons.append("source_handoff_message_missing")
            return None
        if (
            source_handoff_message.session_id != session_id
            or source_handoff_message.source_detail
            != P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_message_is_not_p21_c_review_handoff")
        action = self._first_action(
            source_handoff_message,
            expected_type=P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_HANDOFF_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("p21_c_review_handoff_record_missing")
            return None
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_task_not_bound_to_review_handoff")
        return action

    def _source_diff_action(
        self,
        *,
        source_diff_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_diff_message is None:
            blocked_reasons.append("source_diff_message_missing")
            return None
        if (
            source_diff_message.session_id != session_id
            or source_diff_message.source_detail
            != P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL
        ):
            blocked_reasons.append(
                "source_diff_message_is_not_p21_c_candidate_diff_generated"
            )
        action = self._first_action(
            source_diff_message,
            expected_type=P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
        )
        if action is None:
            blocked_reasons.append("p21_c_candidate_diff_generate_record_missing")
            return None
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("source_task_not_bound_to_review_handoff")
        return action

    @staticmethod
    def _validate_handoff_action(
        *,
        handoff_action: dict[str, Any] | None,
        blocked_reasons: list[str],
    ) -> None:
        if handoff_action is None:
            return
        if handoff_action.get("review_handoff_status") != "created":
            blocked_reasons.append("source_handoff_not_created")
        if (
            "source_diff_verified" in handoff_action
            and handoff_action.get("source_diff_verified") is not True
        ):
            blocked_reasons.append("source_handoff_not_verified")
        if (
            "source_diff_message_bound" in handoff_action
            and handoff_action.get("source_diff_message_bound") is not True
        ):
            blocked_reasons.append("source_handoff_not_verified")
        diff_file_count = handoff_action.get("diff_file_count")
        diff_bytes = handoff_action.get("diff_bytes")
        if not isinstance(diff_file_count, int) or diff_file_count <= 0:
            blocked_reasons.append("source_handoff_not_verified")
        if not isinstance(diff_bytes, int) or diff_bytes <= 0:
            blocked_reasons.append("source_handoff_not_verified")
        if not all(handoff_action.get(flag) is False for flag in HANDOFF_FALSE_FLAGS):
            blocked_reasons.append("source_handoff_write_boundary_violated")
        if handoff_action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("source_handoff_write_boundary_violated")

    @staticmethod
    def _validate_source_diff_action(
        *,
        diff_action: dict[str, Any] | None,
        source_diff_sha256: str,
        review_scope_paths: list[str],
        unified_diff_text: str,
        blocked_reasons: list[str],
    ) -> None:
        if diff_action is None:
            return
        if diff_action.get("diff_generation_status") != "generated":
            blocked_reasons.append("source_diff_not_generated")
        if diff_action.get("readonly_real_diff_generated") is not True:
            blocked_reasons.append("source_diff_not_generated")
        if diff_action.get("real_diff_generated") is not True:
            blocked_reasons.append("source_diff_not_generated")
        diff_entries = diff_action.get("diff_entries")
        if not isinstance(diff_entries, list) or not diff_entries:
            blocked_reasons.append("source_diff_not_generated")
            diff_entries = []
        diff_file_count = diff_action.get("diff_file_count")
        diff_bytes = diff_action.get("diff_bytes")
        if not isinstance(diff_file_count, int) or diff_file_count <= 0:
            blocked_reasons.append("source_diff_not_generated")
        if not isinstance(diff_bytes, int) or diff_bytes <= 0:
            blocked_reasons.append("source_diff_not_generated")
        if unified_diff_text:
            recalculated_sha = hashlib.sha256(
                unified_diff_text.encode("utf-8")
            ).hexdigest()
            if recalculated_sha != source_diff_sha256:
                blocked_reasons.append("source_diff_sha256_mismatch")
            if diff_bytes != len(unified_diff_text.encode("utf-8")):
                blocked_reasons.append("source_diff_not_generated")
        else:
            blocked_reasons.append("source_diff_not_generated")
        if diff_file_count != len(diff_entries):
            blocked_reasons.append("source_diff_not_generated")
        if not all(diff_action.get(flag) is False for flag in SOURCE_DIFF_FALSE_FLAGS):
            blocked_reasons.append("source_diff_write_boundary_violated")
        if diff_action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("source_diff_write_boundary_violated")
        entry_scope_paths: list[str] = []
        seen_entry_paths: set[str] = set()
        for entry in diff_entries:
            if not isinstance(entry, dict) or any(
                field not in entry for field in SOURCE_DIFF_ENTRY_REQUIRED_FIELDS
            ):
                blocked_reasons.append("source_diff_not_generated")
                continue
            relative_path = entry.get("relative_path")
            entry_diff = entry.get("unified_diff")
            entry_bytes = entry.get("diff_bytes")
            if not isinstance(relative_path, str) or not relative_path:
                blocked_reasons.append("source_diff_not_generated")
                continue
            if not isinstance(entry_diff, str) or not entry_diff:
                blocked_reasons.append("source_diff_not_generated")
                continue
            if not isinstance(entry_bytes, int) or entry_bytes != len(
                entry_diff.encode("utf-8")
            ):
                blocked_reasons.append("source_diff_not_generated")
            if relative_path not in seen_entry_paths:
                entry_scope_paths.append(relative_path)
                seen_entry_paths.add(relative_path)
        if review_scope_paths != entry_scope_paths:
            blocked_reasons.append("review_scope_paths_missing")

    @staticmethod
    def _requested_reviewer_executor(
        action: dict[str, Any] | None,
        *,
        blocked_reasons: list[str],
    ) -> str:
        if action is None:
            return "codex"
        value = action.get("requested_reviewer_executor")
        if value not in ("codex", "claude-code"):
            blocked_reasons.append("source_handoff_not_verified")
            return "codex"
        return value

    @staticmethod
    def _source_diff_sha256(
        action: dict[str, Any] | None,
        *,
        blocked_reasons: list[str],
    ) -> str:
        if action is None:
            return ""
        value = action.get("source_diff_sha256")
        if not isinstance(value, str) or not _LOWER_HEX_SHA256.match(value):
            blocked_reasons.append("source_diff_sha256_invalid")
            return ""
        return value

    @staticmethod
    def _review_scope_paths(
        action: dict[str, Any] | None,
        *,
        blocked_reasons: list[str],
    ) -> list[str]:
        if action is None:
            return []
        raw_paths = action.get("review_scope_paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            blocked_reasons.append("review_scope_paths_missing")
            return []
        paths: list[str] = []
        for raw_path in raw_paths:
            if not isinstance(raw_path, str) or not raw_path:
                blocked_reasons.append("review_scope_paths_missing")
                continue
            paths.append(raw_path)
        return paths

    @staticmethod
    def _unified_diff_text(
        action: dict[str, Any] | None,
        *,
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
    def _uuid_from_action(
        action: dict[str, Any] | None,
        key: str,
        *,
        blocked_reason: str,
        blocked_reasons: list[str],
    ) -> UUID | None:
        if action is None:
            blocked_reasons.append(blocked_reason)
            return None
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
    def _is_safe_dry_run_task(task: Task) -> bool:
        return ProjectDirectorSandboxWorkspaceGuardService._is_safe_dry_run_task(task)

    @staticmethod
    def _preflight_summary(*, status: str) -> str:
        if status == "ready":
            return (
                "P21-C-H-A locked deterministic readonly reviewer execution input, "
                "reverified the P21-C-F diff SHA256 through the P21-C-G handoff, "
                "and recorded only prompt fingerprint metadata. It did not start a "
                "reviewer, call a provider, produce findings or verdict, write files, "
                "apply patches, create worktrees, create Tasks/Runs, or perform Git "
                "writes."
            )
        return (
            "P21-C-H-A readonly reviewer execution preflight was blocked before "
            "message creation, reviewer start, provider call, review execution, "
            "findings, verdict, file write, patch, worktree, Task, Run, or Git side "
            "effect."
        )

    @staticmethod
    def _review_execution_preflight_action(
        result: ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightResult,
    ) -> dict[str, Any]:
        return {
            "type": (
                P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_ACTION_TYPE
            ),
            "review_execution_preflight_status": (
                result.review_execution_preflight_status
            ),
            "source_task_id": (
                str(result.source_task_id)
                if result.source_task_id is not None
                else None
            ),
            "source_handoff_message_id": (
                str(result.source_handoff_message_id)
                if result.source_handoff_message_id is not None
                else None
            ),
            "source_diff_message_id": (
                str(result.source_diff_message_id)
                if result.source_diff_message_id is not None
                else None
            ),
            "requested_reviewer_executor": result.requested_reviewer_executor,
            "source_diff_sha256": result.source_diff_sha256,
            "review_prompt_sha256": result.review_prompt_sha256,
            "review_prompt_bytes": result.review_prompt_bytes,
            "review_input_schema_version": result.review_input_schema_version,
            "review_output_schema_version": result.review_output_schema_version,
            "review_scope_paths": list(result.review_scope_paths),
            "reviewer_started": False,
            "review_executed": False,
            "review_findings_generated": False,
            "review_verdict_generated": False,
            "provider_called": False,
            "native_executor_started": False,
            "codex_started": False,
            "claude_code_started": False,
            "main_project_file_written": False,
            "sandbox_file_written": False,
            "manifest_file_written": False,
            "diff_file_written": False,
            "patch_applied": False,
            "product_runtime_git_write_allowed": False,
            "git_write_performed": False,
            "worktree_created": False,
            "worker_started": False,
            "task_created": False,
            "run_created": False,
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
    "ConfirmedSandboxCandidateDiffReviewExecutionPreflight",
    "P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_ACTION_TYPE",
    "P21_C_SANDBOX_CANDIDATE_DIFF_REVIEW_EXECUTION_PREFLIGHT_SOURCE_DETAIL",
    "ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService",
)
