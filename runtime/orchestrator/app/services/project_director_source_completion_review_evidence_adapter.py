"""Readonly adapter for exact P21-C/P21-D completion-review evidence."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.domain._base import ensure_utc_datetime
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_source_completion_review_evidence import (
    ProjectDirectorSourceCompletionReviewEvidence,
    SOURCE_COMPLETION_REVIEW_EVIDENCE_KIND,
    SourceCompletionReviewBlockedReason,
    SourceCompletionReviewEvidenceResolution,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_sandbox_candidate_diff_readonly_review_execution_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE,
    P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL,
)


_PASSING_VERDICTS = {"no_blocking_findings", "non_blocking_findings"}
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
_FORBIDDEN_ACTIONS = [
    "no_review_execution",
    "no_disposition_computation",
    "no_continuation_start",
    "no_rework_start",
    "no_human_escalation",
    "no_task_run_or_agent_session_write",
    "no_product_runtime_git_write",
]


class ProjectDirectorSourceCompletionReviewEvidenceAdapter:
    """Reconstruct exact declared review evidence without selecting session history."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        review_disposition_service: ProjectDirectorSandboxCandidateDiffReviewDispositionService,
    ) -> None:
        self._message_repository = message_repository
        self._review_disposition_service = review_disposition_service
        if review_disposition_service._message_repository is not message_repository:
            raise ValueError("completion review dependencies must share one session")

    def resolve_required_completion_review(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
        source_run_finished_at: datetime,
        declared_review_evidence_ids: list[UUID],
        allowed_review_terminal_results: list[str],
    ) -> SourceCompletionReviewEvidenceResolution:
        """Resolve an exact post-Run validated review plus AUTO_CONTINUE record."""

        del source_run_id  # Review messages have no Run field; timeline binds the Run.
        allowed_results = list(allowed_review_terminal_results)
        if (
            not allowed_results
            or len(allowed_results) != len(set(allowed_results))
            or any(result not in _PASSING_VERDICTS for result in allowed_results)
        ):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_terminal_result_unsupported"
            )
        if (
            len(declared_review_evidence_ids) != 2
            or any(not isinstance(value, UUID) for value in declared_review_evidence_ids)
            or (
                all(isinstance(value, UUID) for value in declared_review_evidence_ids)
                and len(set(declared_review_evidence_ids)) != 2
            )
        ):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_evidence_id_invalid"
            )

        messages = [
            self._message_repository.get_by_id(message_id)
            for message_id in declared_review_evidence_ids
        ]
        if any(message is None for message in messages):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_evidence_missing"
            )
        typed_messages = [message for message in messages if message is not None]
        review_messages = [
            message for message in typed_messages if self._is_review_message(message)
        ]
        disposition_messages = [
            message
            for message in typed_messages
            if self._is_disposition_message(message)
        ]
        if len(review_messages) != 1 or len(disposition_messages) != 1:
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_evidence_conflict"
            )
        review_message = review_messages[0]
        disposition_message = disposition_messages[0]

        if not self._review_message_metadata_valid(
            review_message,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
        ):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_message_invalid"
            )
        review_revalidation = (
            ProjectDirectorSandboxCandidateDiffReviewDispositionService
            .revalidate_persisted_review_result_fingerprint(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=review_message.id,
                source_review_message=review_message,
            )
        )
        if review_revalidation.blocked_reasons:
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_message_invalid"
            )
        if review_revalidation.verdict == "changes_required":
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_changes_required"
            )
        if review_revalidation.verdict not in allowed_results:
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_verdict_not_allowed"
            )
        if (
            review_revalidation.source_diff_message_id is None
            or review_revalidation.source_preflight_message_id is None
        ):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_diff_invalid"
            )

        source_diff_message = self._message_repository.get_by_id(
            review_revalidation.source_diff_message_id
        )
        if not self._source_diff_valid(
            source_diff_message,
            session_id=session_id,
            project_id=project_id,
            source_task_id=source_task_id,
            expected_sha256=review_revalidation.source_diff_sha256,
            expected_scope_paths=list(review_revalidation.review_scope_paths or []),
        ):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_diff_invalid"
            )

        disposition = (
            self._review_disposition_service.revalidate_persisted_review_disposition(
                session_id=session_id,
                project_id=project_id,
                source_task_id=source_task_id,
                source_disposition_message_id=disposition_message.id,
                source_review_message=review_message,
            )
        )
        if disposition.blocked_reasons:
            reason: SourceCompletionReviewBlockedReason = (
                "source_completion_review_disposition_missing"
                if "review_disposition_message_missing" in disposition.blocked_reasons
                else "source_completion_review_disposition_invalid"
            )
            return SourceCompletionReviewEvidenceResolution.blocked(reason)
        if (
            disposition.source_review_message_id != review_message.id
            or disposition.source_preflight_message_id
            != review_revalidation.source_preflight_message_id
            or disposition.source_diff_message_id
            != review_revalidation.source_diff_message_id
            or disposition.source_diff_sha256 != review_revalidation.source_diff_sha256
            or disposition.review_output_schema_version
            != review_revalidation.review_output_schema_version
            or disposition.source_review_verdict != review_revalidation.verdict
            or disposition.source_review_risk_level != review_revalidation.risk_level
        ):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_disposition_invalid"
            )
        if (
            disposition.review_result_fingerprint
            != review_revalidation.review_result_fingerprint
        ):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_disposition_fingerprint_mismatch"
            )
        if (
            disposition.disposition_status != "computed"
            or disposition.disposition_type != "AUTO_CONTINUE"
        ):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_disposition_not_continue"
            )
        if (
            disposition.disposition_id is None
            or disposition.disposition_message_created_at is None
        ):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_disposition_invalid"
            )

        run_finished_at = ensure_utc_datetime(source_run_finished_at)
        diff_created_at = ensure_utc_datetime(source_diff_message.created_at)
        review_created_at = ensure_utc_datetime(review_message.created_at)
        disposition_created_at = ensure_utc_datetime(
            disposition.disposition_message_created_at
        )
        if (
            run_finished_at is None
            or diff_created_at is None
            or review_created_at is None
            or disposition_created_at is None
        ):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_timeline_invalid"
            )
        if diff_created_at < run_finished_at or review_created_at < run_finished_at:
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_stale_for_run"
            )
        if (
            review_created_at < diff_created_at
            or disposition_created_at < review_created_at
        ):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_timeline_invalid"
            )

        try:
            snapshot = ProjectDirectorSourceCompletionReviewEvidence(
                review_evidence_kind=SOURCE_COMPLETION_REVIEW_EVIDENCE_KIND,
                review_message_id=review_message.id,
                review_result_fingerprint=(
                    review_revalidation.review_result_fingerprint
                ),
                review_session_id=session_id,
                review_project_id=project_id,
                review_task_id=source_task_id,
                source_preflight_message_id=(
                    review_revalidation.source_preflight_message_id
                ),
                source_diff_message_id=review_revalidation.source_diff_message_id,
                source_diff_sha256=review_revalidation.source_diff_sha256,
                review_output_schema_version=(
                    review_revalidation.review_output_schema_version
                ),
                review_status="reviewed",
                review_verdict=review_revalidation.verdict,
                review_risk_level=review_revalidation.risk_level,
                disposition_message_id=disposition_message.id,
                disposition_id=disposition.disposition_id,
                disposition_status="computed",
                disposition_type="AUTO_CONTINUE",
                disposition_review_result_fingerprint=(
                    disposition.review_result_fingerprint
                ),
                review_message_created_at=review_created_at,
                source_diff_message_created_at=diff_created_at,
                disposition_message_created_at=disposition_created_at,
                product_runtime_git_write_allowed=False,
                forbidden_actions=list(_FORBIDDEN_ACTIONS),
            )
        except (TypeError, ValueError, ValidationError):
            return SourceCompletionReviewEvidenceResolution.blocked(
                "source_completion_review_message_invalid"
            )
        return SourceCompletionReviewEvidenceResolution(
            status="resolved",
            snapshot=snapshot,
        )

    @staticmethod
    def _single_action(message: ProjectDirectorMessage) -> dict[str, Any] | None:
        if len(message.suggested_actions) != 1:
            return None
        action = message.suggested_actions[0]
        return action if isinstance(action, dict) else None

    @classmethod
    def _is_review_message(cls, message: ProjectDirectorMessage) -> bool:
        action = cls._single_action(message)
        return (
            message.source_detail
            == P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_SOURCE_DETAIL
            and action is not None
            and action.get("type")
            == P21_C_SANDBOX_CANDIDATE_DIFF_READONLY_REVIEW_EXECUTION_ACTION_TYPE
        )

    @classmethod
    def _is_disposition_message(cls, message: ProjectDirectorMessage) -> bool:
        action = cls._single_action(message)
        return (
            message.source_detail
            == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_SOURCE_DETAIL
            and action is not None
            and action.get("type")
            == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_ACTION_TYPE
        )

    @classmethod
    def _review_message_metadata_valid(
        cls,
        message: ProjectDirectorMessage,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
    ) -> bool:
        return (
            message.session_id == session_id
            and message.related_project_id == project_id
            and message.related_task_id == source_task_id
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == "sandbox_candidate_diff_readonly_review_execution"
            and not message.requires_confirmation
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
            and cls._is_review_message(message)
        )

    @classmethod
    def _source_diff_valid(
        cls,
        message: ProjectDirectorMessage | None,
        *,
        session_id: UUID,
        project_id: UUID,
        source_task_id: UUID,
        expected_sha256: str,
        expected_scope_paths: list[str],
    ) -> bool:
        if message is None:
            return False
        action = cls._single_action(message)
        if (
            message.session_id != session_id
            or message.related_project_id != project_id
            or message.related_task_id != source_task_id
            or message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != "sandbox_candidate_diff_generate"
            or message.source_detail != P21_C_SANDBOX_CANDIDATE_DIFF_SOURCE_DETAIL
            or message.requires_confirmation
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or action is None
            or action.get("type") != P21_C_SANDBOX_CANDIDATE_DIFF_ACTION_TYPE
            or action.get("source_task_id") != str(source_task_id)
            or action.get("diff_generation_status") != "generated"
            or action.get("readonly_real_diff_generated") is not True
            or action.get("real_diff_generated") is not True
            or action.get("workspace_path_within_root") is not True
            or action.get("ai_project_director_total_loop") != "Partial"
            or not all(action.get(flag) is False for flag in _SOURCE_DIFF_FALSE_FLAGS)
        ):
            return False
        unified_diff_text = action.get("unified_diff_text")
        diff_entries = action.get("diff_entries")
        if (
            not isinstance(unified_diff_text, str)
            or not unified_diff_text
            or action.get("diff_bytes") != len(unified_diff_text.encode("utf-8"))
            or not isinstance(diff_entries, list)
            or not diff_entries
            or action.get("diff_file_count") != len(diff_entries)
        ):
            return False
        if any(
            not isinstance(entry, dict)
            or not isinstance(entry.get("relative_path"), str)
            or not entry.get("relative_path")
            or not isinstance(entry.get("unified_diff"), str)
            or not entry.get("unified_diff")
            or entry.get("diff_bytes")
            != len(entry.get("unified_diff", "").encode("utf-8"))
            for entry in diff_entries
        ):
            return False
        entry_scope_paths = [entry["relative_path"] for entry in diff_entries]
        if (
            len(entry_scope_paths) != len(set(entry_scope_paths))
            or entry_scope_paths != expected_scope_paths
        ):
            return False
        if "".join(entry["unified_diff"] for entry in diff_entries) != unified_diff_text:
            return False
        return (
            hashlib.sha256(unified_diff_text.encode("utf-8")).hexdigest()
            == expected_sha256
        )


__all__ = ("ProjectDirectorSourceCompletionReviewEvidenceAdapter",)
