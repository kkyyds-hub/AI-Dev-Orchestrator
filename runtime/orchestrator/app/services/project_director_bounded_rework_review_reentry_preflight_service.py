"""Atomic P25-H review re-entry preflight and Claim persistence."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid5

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.project_director_bounded_rework_candidate_diff import (
    ProjectDirectorBoundedReworkCandidateDiff,
    ProjectDirectorBoundedReworkCandidateManifest,
)
from app.domain.project_director_bounded_rework_contract import (
    BoundedReworkBlockedReason,
)
from app.domain.project_director_bounded_rework_instruction_package import (
    ProjectDirectorBoundedReworkInstructionPackage,
)
from app.domain.project_director_bounded_rework_review_reentry import (
    P25_BOUNDED_REWORK_REVIEW_CLAIM_NAMESPACE,
    P25_BOUNDED_REWORK_REVIEW_CLAIM_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION,
    P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_NAMESPACE,
    P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SCHEMA_VERSION,
    BoundedReworkReviewerExecutor,
    ProjectDirectorBoundedReworkReviewInvocationClaim,
    ProjectDirectorBoundedReworkReviewReentryPreflight,
)
from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.services.project_director_bounded_rework_candidate_diff_service import (
    ProjectDirectorBoundedReworkCandidateDiffService,
    RevalidatedProjectDirectorBoundedReworkCandidateDiff,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService,
)


P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SOURCE_DETAIL = (
    "p25_h_bounded_rework_review_preflight_ready"
)
P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_ACTION_TYPE = (
    "p25_h_bounded_rework_review_preflight_record"
)
P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_INTENT = (
    "bounded_rework_review_reentry_preflight"
)

P25_BOUNDED_REWORK_REVIEW_CLAIM_SOURCE_DETAIL = (
    "p25_h_bounded_rework_review_invocation_claimed"
)
P25_BOUNDED_REWORK_REVIEW_CLAIM_ACTION_TYPE = (
    "p25_h_bounded_rework_review_invocation_claim_record"
)
P25_BOUNDED_REWORK_REVIEW_CLAIM_INTENT = (
    "bounded_rework_review_reentry_invocation_claim"
)

_P25_H_PREFLIGHT_FALSE_BOUNDARIES = (
    "reviewer_attempted=false",
    "reviewer_started=false",
    "reviewer_returned=false",
    "reviewer_raised=false",
    "review_output_persisted=false",
    "provider_called=false",
    "main_project_write_allowed=false",
    "product_runtime_git_write_allowed=false",
    "patch_apply_allowed=false",
    "git_write_allowed=false",
    "task_created=false",
    "run_created=false",
)

_P25_H_CLAIM_FALSE_BOUNDARIES = (
    "reviewer_call_attempted=false",
    "reviewer_started=false",
    "reviewer_returned=false",
    "reviewer_raised=false",
    "review_success_evidence_present=false",
    "provider_called_by_claim=false",
    "product_runtime_git_write_allowed=false",
    "main_project_write_allowed=false",
    "patch_apply_allowed=false",
    "git_write_allowed=false",
    "task_created=false",
    "run_created=false",
)

_PAGE_SIZE = 200

ReviewReentryPreparationStatus = Literal[
    "review_preflight_claimed",
    "review_preflight_replayed",
    "blocked",
]


@dataclass(frozen=True, slots=True)
class PreparedProjectDirectorBoundedReworkReviewReentry:
    status: ReviewReentryPreparationStatus
    preflight: ProjectDirectorBoundedReworkReviewReentryPreflight | None
    preflight_message: ProjectDirectorMessage | None
    review_claim: ProjectDirectorBoundedReworkReviewInvocationClaim | None
    review_claim_message: ProjectDirectorMessage | None
    blocked_reasons: tuple[BoundedReworkBlockedReason, ...]


@dataclass(frozen=True, slots=True)
class _PersistedReviewReentryHistory:
    preflights: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorBoundedReworkReviewReentryPreflight],
        ...,
    ]
    claims: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorBoundedReworkReviewInvocationClaim],
        ...,
    ]


@dataclass(frozen=True, slots=True)
class _TrustedOldReviewEvidence:
    message_id: UUID
    fingerprint: str
    semantic_fingerprint: str
    source_diff_message_id: UUID
    source_diff_sha256: str
    review_prompt_sha256: str
    requested_reviewer_executor: BoundedReworkReviewerExecutor
    review_output_schema_version: str


class _Blocked(RuntimeError):
    def __init__(self, reason: BoundedReworkBlockedReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorBoundedReworkReviewReentryPreflightService:
    """Prepare or replay one fresh P25-H review preflight plus invocation Claim."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        candidate_diff_service: ProjectDirectorBoundedReworkCandidateDiffService,
    ) -> None:
        self._message_repository = message_repository
        self._candidate_diff_service = candidate_diff_service
        if candidate_diff_service._message_repository is not message_repository:
            raise ValueError("P25-H dependencies must share one message repository")

    def prepare_review_reentry_preflight_and_claim(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_candidate_diff_message_id: UUID,
    ) -> PreparedProjectDirectorBoundedReworkReviewReentry:
        """Persist or replay one fresh readonly review preflight and Claim."""

        try:
            initial = self._candidate_diff_service.revalidate_persisted_candidate_diff_for_review_reentry(
                session_id=session_id,
                source_task_id=source_task_id,
                source_candidate_diff_message_id=source_candidate_diff_message_id,
            )
            if initial.blocked_reasons:
                raise _Blocked(initial.blocked_reasons[0])

            old_review = self._recover_trusted_old_review(initial)
            review_prompt_sha256, review_prompt_bytes = self._build_fresh_prompt_projection(
                initial=initial,
                old_review=old_review,
            )
            preflight = self._build_preflight(
                current=initial,
                old_review=old_review,
                review_prompt_sha256=review_prompt_sha256,
                review_prompt_bytes=review_prompt_bytes,
            )

            self._rollback_read_transaction()
            with self._message_repository.sqlite_immediate_transaction():
                current = self._candidate_diff_service.revalidate_persisted_candidate_diff_lineage_for_review_persistence(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_candidate_diff_message_id=source_candidate_diff_message_id,
                )
                if current.blocked_reasons:
                    raise _Blocked(current.blocked_reasons[0])
                if not self._message_repository._session.in_transaction():
                    raise _Blocked("persistence_failed")
                if not self._same_lineage(initial, current):
                    raise _Blocked("history_invalid")
                current_old_review = self._recover_trusted_old_review(current)
                if current_old_review != old_review:
                    raise _Blocked("review_reentry_failed")
                history = self._load_history(session_id)
                return self._prepare_or_replay(
                    history=history,
                    preflight=preflight,
                )
        except _Blocked as exc:
            return self._blocked(exc.reason)
        except SQLAlchemyError:
            return self._blocked("persistence_failed")
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return self._blocked("history_invalid")
        finally:
            self._rollback_read_transaction()

    def _recover_trusted_old_review(
        self,
        current: RevalidatedProjectDirectorBoundedReworkCandidateDiff,
    ) -> _TrustedOldReviewEvidence:
        package = current.package
        if package is None or package.authority is None:
            raise _Blocked("history_invalid")
        review_message = self._message_repository.get_by_id(
            package.authority.source_review_message_id
        )
        review = (
            ProjectDirectorSandboxCandidateDiffReviewDispositionService.revalidate_persisted_review_result_fingerprint(
                session_id=package.authority.session_id,
                source_task_id=package.authority.source_task_id,
                source_review_message_id=package.authority.source_review_message_id,
                source_review_message=review_message,
            )
        )
        if (
            review.blocked_reasons
            or review.review_result_fingerprint
            != package.authority.source_review_fingerprint
            or review.source_diff_message_id is None
            or review.requested_reviewer_executor not in {"codex", "claude-code"}
            or not review.source_diff_sha256
            or not review.review_prompt_sha256
            or review.review_output_schema_version
            != P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION
        ):
            raise _Blocked("review_reentry_failed")
        return _TrustedOldReviewEvidence(
            message_id=package.authority.source_review_message_id,
            fingerprint=package.authority.source_review_fingerprint,
            semantic_fingerprint=package.authority.source_review_semantic_fingerprint,
            source_diff_message_id=review.source_diff_message_id,
            source_diff_sha256=review.source_diff_sha256,
            review_prompt_sha256=review.review_prompt_sha256,
            requested_reviewer_executor=review.requested_reviewer_executor,
            review_output_schema_version=review.review_output_schema_version,
        )

    def _build_fresh_prompt_projection(
        self,
        *,
        initial: RevalidatedProjectDirectorBoundedReworkCandidateDiff,
        old_review: _TrustedOldReviewEvidence,
    ) -> tuple[str, int]:
        candidate_diff = initial.candidate_diff
        if candidate_diff is None:
            raise _Blocked("history_invalid")
        if (
            candidate_diff.candidate_diff_id == old_review.source_diff_message_id
            or candidate_diff.new_diff_sha256 == old_review.source_diff_sha256
        ):
            raise _Blocked("non_convergence")
        try:
            prompt = ProjectDirectorSandboxCandidateDiffReviewExecutionPreflightService.build_readonly_review_prompt(
                requested_reviewer_executor=old_review.requested_reviewer_executor,
                source_diff_sha256=candidate_diff.new_diff_sha256,
                review_scope_paths=list(candidate_diff.scope_paths),
                unified_diff_text=candidate_diff.unified_diff_text,
                review_output_schema_version=(
                    P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION
                ),
            )
        except ValueError as exc:
            raise _Blocked("review_reentry_failed") from exc
        prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if prompt_sha256 == old_review.review_prompt_sha256:
            raise _Blocked("non_convergence")
        return prompt_sha256, len(prompt.encode("utf-8"))

    def _build_preflight(
        self,
        *,
        current: RevalidatedProjectDirectorBoundedReworkCandidateDiff,
        old_review: _TrustedOldReviewEvidence,
        review_prompt_sha256: str,
        review_prompt_bytes: int,
    ) -> ProjectDirectorBoundedReworkReviewReentryPreflight:
        package = self._require_package(current.package)
        manifest = self._require_manifest(current.candidate_manifest)
        candidate_diff = self._require_diff(current.candidate_diff)
        values = {
            "preflight_id": uuid5(
                P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_NAMESPACE,
                candidate_diff.candidate_diff_replay_key,
            ),
            "preflight_replay_key": (
                ProjectDirectorBoundedReworkReviewReentryPreflight.compute_preflight_replay_key(
                    source_candidate_diff_replay_key=(
                        candidate_diff.candidate_diff_replay_key
                    )
                )
            ),
            "created_at": utc_now(),
            "preflight_status": "ready",
            "source_candidate_diff_message_id": candidate_diff.candidate_diff_id,
            "source_candidate_diff_id": candidate_diff.candidate_diff_id,
            "source_candidate_diff_fingerprint": (
                candidate_diff.candidate_diff_fingerprint
            ),
            "source_candidate_diff_replay_key": (
                candidate_diff.candidate_diff_replay_key
            ),
            "source_candidate_diff_sha256": candidate_diff.new_diff_sha256,
            "source_candidate_manifest_id": manifest.candidate_manifest_id,
            "source_candidate_manifest_fingerprint": (
                manifest.candidate_manifest_fingerprint
            ),
            "source_outcome_id": candidate_diff.source_outcome_id,
            "source_outcome_fingerprint": candidate_diff.source_outcome_fingerprint,
            "source_claim_id": candidate_diff.source_claim_id,
            "source_reservation_id": candidate_diff.source_reservation_id,
            "source_package_id": candidate_diff.source_package_id,
            "source_attempt_id": candidate_diff.source_attempt_id,
            "rework_attempt_index": candidate_diff.rework_attempt_index,
            "rework_attempt_limit": candidate_diff.rework_attempt_limit,
            "old_review_message_id": old_review.message_id,
            "old_review_fingerprint": old_review.fingerprint,
            "old_review_semantic_fingerprint": old_review.semantic_fingerprint,
            "old_review_prompt_sha256": old_review.review_prompt_sha256,
            "old_review_source_diff_message_id": old_review.source_diff_message_id,
            "old_review_source_diff_sha256": old_review.source_diff_sha256,
            "authority": candidate_diff.authority,
            "exact_task_id": candidate_diff.exact_task_id,
            "exact_run_id": candidate_diff.exact_run_id,
            "base_commit_sha": candidate_diff.base_commit_sha,
            "base_snapshot_fingerprint": candidate_diff.base_snapshot_fingerprint,
            "workspace_binding_id": package.workspace_binding.workspace_binding_id,
            "workspace_binding_fingerprint": (
                package.workspace_binding.workspace_binding_fingerprint
            ),
            "workspace_path": package.workspace_binding.workspace_path,
            "workspace_business_manifest_fingerprint": (
                manifest.workspace_business_manifest_fingerprint
            ),
            "workspace_business_content_fingerprint": (
                manifest.workspace_business_content_fingerprint
            ),
            "requested_reviewer_executor": old_review.requested_reviewer_executor,
            "review_input_schema_version": (
                P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SCHEMA_VERSION
            ),
            "review_output_schema_version": (
                P25_BOUNDED_REWORK_REVIEW_OUTPUT_SCHEMA_VERSION
            ),
            "review_scope_paths": candidate_diff.scope_paths,
            "review_prompt_sha256": review_prompt_sha256,
            "review_prompt_bytes": review_prompt_bytes,
            "reviewer_attempted": False,
            "reviewer_started": False,
            "reviewer_returned": False,
            "reviewer_raised": False,
            "review_output_persisted": False,
            "provider_called": False,
            "main_project_write_allowed": False,
            "product_runtime_git_write_allowed": False,
            "patch_apply_allowed": False,
            "git_write_allowed": False,
            "task_created": False,
            "run_created": False,
        }
        draft = ProjectDirectorBoundedReworkReviewReentryPreflight.model_construct(
            **values,
            preflight_fingerprint="0" * 64,
        )
        return ProjectDirectorBoundedReworkReviewReentryPreflight(
            **values,
            preflight_fingerprint=draft.compute_fingerprint(),
        )

    def _prepare_or_replay(
        self,
        *,
        history: _PersistedReviewReentryHistory,
        preflight: ProjectDirectorBoundedReworkReviewReentryPreflight,
    ) -> PreparedProjectDirectorBoundedReworkReviewReentry:
        matches = [
            item
            for item in history.preflights
            if item[1].source_candidate_diff_message_id
            == preflight.source_candidate_diff_message_id
        ]
        if len(matches) > 1:
            raise _Blocked("history_invalid")
        if matches:
            preflight_message, existing_preflight = matches[0]
            if (
                existing_preflight.preflight_replay_key
                != preflight.preflight_replay_key
                or self._semantic_preflight_payload(existing_preflight)
                != self._semantic_preflight_payload(preflight)
            ):
                raise _Blocked("history_invalid")
            claims = [
                item
                for item in history.claims
                if item[1].preflight_id == existing_preflight.preflight_id
            ]
            if len(claims) != 1:
                raise _Blocked("history_invalid")
            claim_message, claim = claims[0]
            if not self._claim_binds_preflight(claim=claim, preflight=existing_preflight):
                raise _Blocked("history_invalid")
            return PreparedProjectDirectorBoundedReworkReviewReentry(
                status="review_preflight_replayed",
                preflight=existing_preflight,
                preflight_message=preflight_message,
                review_claim=claim,
                review_claim_message=claim_message,
                blocked_reasons=(),
            )

        orphan_claims = [
            item
            for item in history.claims
            if item[1].source_candidate_diff_message_id
            == preflight.source_candidate_diff_message_id
            or item[1].preflight_replay_key == preflight.preflight_replay_key
            or (
                item[1].source_attempt_id == preflight.source_attempt_id
                and item[1].source_candidate_diff_message_id
                == preflight.source_candidate_diff_message_id
            )
        ]
        if orphan_claims:
            raise _Blocked("history_invalid")

        claim = self._build_review_claim(preflight)
        preflight_message = self._build_preflight_message(preflight)
        persisted_preflight = self._message_repository.create(preflight_message)
        if persisted_preflight != preflight_message:
            raise _Blocked("persistence_failed")
        claim_message = self._build_claim_message(claim)
        persisted_claim = self._message_repository.create(claim_message)
        if persisted_claim != claim_message:
            raise _Blocked("persistence_failed")
        return PreparedProjectDirectorBoundedReworkReviewReentry(
            status="review_preflight_claimed",
            preflight=preflight,
            preflight_message=persisted_preflight,
            review_claim=claim,
            review_claim_message=persisted_claim,
            blocked_reasons=(),
        )

    def _build_review_claim(
        self,
        preflight: ProjectDirectorBoundedReworkReviewReentryPreflight,
    ) -> ProjectDirectorBoundedReworkReviewInvocationClaim:
        values = {
            "review_claim_id": uuid5(
                P25_BOUNDED_REWORK_REVIEW_CLAIM_NAMESPACE,
                preflight.preflight_replay_key,
            ),
            "review_claim_replay_key": (
                ProjectDirectorBoundedReworkReviewInvocationClaim.compute_claim_replay_key(
                    preflight_replay_key=preflight.preflight_replay_key,
                    invocation_ordinal=0,
                )
            ),
            "review_claim_token": secrets.token_hex(32),
            "created_at": utc_now(),
            "claim_status": "claimed",
            "preflight_id": preflight.preflight_id,
            "preflight_fingerprint": preflight.preflight_fingerprint,
            "preflight_replay_key": preflight.preflight_replay_key,
            "source_candidate_diff_message_id": (
                preflight.source_candidate_diff_message_id
            ),
            "source_candidate_diff_sha256": preflight.source_candidate_diff_sha256,
            "source_outcome_id": preflight.source_outcome_id,
            "source_attempt_id": preflight.source_attempt_id,
            "source_package_id": preflight.source_package_id,
            "authority": preflight.authority,
            "exact_task_id": preflight.exact_task_id,
            "exact_run_id": preflight.exact_run_id,
            "rework_attempt_index": preflight.rework_attempt_index,
            "rework_attempt_limit": preflight.rework_attempt_limit,
            "requested_reviewer_executor": preflight.requested_reviewer_executor,
            "review_prompt_sha256": preflight.review_prompt_sha256,
            "review_prompt_bytes": preflight.review_prompt_bytes,
            "review_output_schema_version": preflight.review_output_schema_version,
            "invocation_ordinal": 0,
            "reviewer_call_attempted": False,
            "reviewer_started": False,
            "reviewer_returned": False,
            "reviewer_raised": False,
            "review_success_evidence_present": False,
            "provider_called_by_claim": False,
            "product_runtime_git_write_allowed": False,
            "main_project_write_allowed": False,
            "patch_apply_allowed": False,
            "git_write_allowed": False,
            "task_created": False,
            "run_created": False,
        }
        draft = ProjectDirectorBoundedReworkReviewInvocationClaim.model_construct(
            **values,
            review_claim_fingerprint="0" * 64,
        )
        return ProjectDirectorBoundedReworkReviewInvocationClaim(
            **values,
            review_claim_fingerprint=draft.compute_fingerprint(),
        )

    def _load_history(self, session_id: UUID) -> _PersistedReviewReentryHistory:
        preflights: list[
            tuple[ProjectDirectorMessage, ProjectDirectorBoundedReworkReviewReentryPreflight]
        ] = []
        claims: list[
            tuple[ProjectDirectorMessage, ProjectDirectorBoundedReworkReviewInvocationClaim]
        ] = []
        for message in self._iter_session_messages(session_id):
            action = self._p25_h_action(message)
            if action is None:
                continue
            schema_version = action.get("schema_version")
            payload = dict(action)
            payload.pop("type", None)
            try:
                if schema_version == P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SCHEMA_VERSION:
                    preflight = (
                        ProjectDirectorBoundedReworkReviewReentryPreflight.model_validate(
                            payload
                        )
                    )
                    if not self._preflight_message_valid(message, preflight):
                        raise _Blocked("history_invalid")
                    preflights.append((message, preflight))
                elif schema_version == P25_BOUNDED_REWORK_REVIEW_CLAIM_SCHEMA_VERSION:
                    claim = ProjectDirectorBoundedReworkReviewInvocationClaim.model_validate(
                        payload
                    )
                    if not self._claim_message_valid(message, claim):
                        raise _Blocked("history_invalid")
                    claims.append((message, claim))
                else:
                    raise _Blocked("history_invalid")
            except _Blocked:
                raise
            except (TypeError, ValueError, ValidationError) as exc:
                raise _Blocked("history_invalid") from exc
        history = _PersistedReviewReentryHistory(
            preflights=tuple(preflights),
            claims=tuple(claims),
        )
        self._validate_history(history)
        return history

    def _iter_session_messages(self, session_id: UUID) -> list[ProjectDirectorMessage]:
        messages: list[ProjectDirectorMessage] = []
        before_message_id: UUID | None = None
        while True:
            page, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=_PAGE_SIZE,
                before_message_id=before_message_id,
            )
            messages.extend(page)
            if not has_more:
                return sorted(messages, key=lambda item: item.sequence_no)
            if not page:
                raise _Blocked("history_invalid")
            before_message_id = page[0].id

    @staticmethod
    def _p25_h_action(message: ProjectDirectorMessage) -> dict[str, Any] | None:
        preflight_marked = (
            message.intent == P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_INTENT
            or message.source_detail
            == P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SOURCE_DETAIL
            or any(
                isinstance(action, dict)
                and (
                    action.get("type")
                    == P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_ACTION_TYPE
                    or action.get("schema_version")
                    == P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SCHEMA_VERSION
                )
                for action in message.suggested_actions
            )
        )
        claim_marked = (
            message.intent == P25_BOUNDED_REWORK_REVIEW_CLAIM_INTENT
            or message.source_detail == P25_BOUNDED_REWORK_REVIEW_CLAIM_SOURCE_DETAIL
            or any(
                isinstance(action, dict)
                and (
                    action.get("type") == P25_BOUNDED_REWORK_REVIEW_CLAIM_ACTION_TYPE
                    or action.get("schema_version")
                    == P25_BOUNDED_REWORK_REVIEW_CLAIM_SCHEMA_VERSION
                )
                for action in message.suggested_actions
            )
        )
        if not preflight_marked and not claim_marked:
            return None
        if preflight_marked and claim_marked:
            raise _Blocked("history_invalid")
        if (
            message.role != ProjectDirectorMessageRole.ASSISTANT
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or message.token_count is not None
            or message.estimated_cost is not None
            or len(message.suggested_actions) != 1
            or not isinstance(message.suggested_actions[0], dict)
        ):
            raise _Blocked("history_invalid")
        action = message.suggested_actions[0]
        if preflight_marked:
            if (
                message.intent != P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_INTENT
                or message.source_detail
                != P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SOURCE_DETAIL
                or action.get("type")
                != P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_ACTION_TYPE
                or action.get("schema_version")
                != P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SCHEMA_VERSION
            ):
                raise _Blocked("history_invalid")
            return action
        if (
            message.intent != P25_BOUNDED_REWORK_REVIEW_CLAIM_INTENT
            or message.source_detail != P25_BOUNDED_REWORK_REVIEW_CLAIM_SOURCE_DETAIL
            or action.get("type") != P25_BOUNDED_REWORK_REVIEW_CLAIM_ACTION_TYPE
            or action.get("schema_version")
            != P25_BOUNDED_REWORK_REVIEW_CLAIM_SCHEMA_VERSION
        ):
            raise _Blocked("history_invalid")
        return action

    @staticmethod
    def _validate_history(history: _PersistedReviewReentryHistory) -> None:
        preflight_ids = [item[1].preflight_id for item in history.preflights]
        preflight_replay_keys = [item[1].preflight_replay_key for item in history.preflights]
        preflight_diff_ids = [
            item[1].source_candidate_diff_message_id for item in history.preflights
        ]
        claim_ids = [item[1].review_claim_id for item in history.claims]
        claim_replay_keys = [item[1].review_claim_replay_key for item in history.claims]
        claim_preflight_ids = [item[1].preflight_id for item in history.claims]
        claim_diff_ids = [
            item[1].source_candidate_diff_message_id for item in history.claims
        ]
        claim_attempt_diff_ids = [
            (item[1].source_attempt_id, item[1].source_candidate_diff_message_id)
            for item in history.claims
        ]
        groups = (
            preflight_ids,
            preflight_replay_keys,
            preflight_diff_ids,
            claim_ids,
            claim_replay_keys,
            claim_preflight_ids,
            claim_diff_ids,
            claim_attempt_diff_ids,
        )
        if any(len(values) != len(set(values)) for values in groups):
            raise _Blocked("history_invalid")

        preflights = {item[1].preflight_id: item[1] for item in history.preflights}
        for _, claim in history.claims:
            preflight = preflights.get(claim.preflight_id)
            if preflight is None or not ProjectDirectorBoundedReworkReviewReentryPreflightService._claim_binds_preflight(
                claim=claim,
                preflight=preflight,
            ):
                raise _Blocked("history_invalid")

    @staticmethod
    def _claim_binds_preflight(
        *,
        claim: ProjectDirectorBoundedReworkReviewInvocationClaim,
        preflight: ProjectDirectorBoundedReworkReviewReentryPreflight,
    ) -> bool:
        return bool(
            claim.preflight_fingerprint == preflight.preflight_fingerprint
            and claim.preflight_replay_key == preflight.preflight_replay_key
            and claim.source_candidate_diff_message_id
            == preflight.source_candidate_diff_message_id
            and claim.source_candidate_diff_sha256
            == preflight.source_candidate_diff_sha256
            and claim.source_outcome_id == preflight.source_outcome_id
            and claim.source_attempt_id == preflight.source_attempt_id
            and claim.source_package_id == preflight.source_package_id
            and claim.authority == preflight.authority
            and claim.exact_task_id == preflight.exact_task_id
            and claim.exact_run_id == preflight.exact_run_id
            and claim.rework_attempt_index == preflight.rework_attempt_index
            and claim.rework_attempt_limit == preflight.rework_attempt_limit
            and claim.requested_reviewer_executor
            == preflight.requested_reviewer_executor
            and claim.review_prompt_sha256 == preflight.review_prompt_sha256
            and claim.review_prompt_bytes == preflight.review_prompt_bytes
            and claim.review_output_schema_version
            == preflight.review_output_schema_version
            and claim.invocation_ordinal == 0
        )

    def _build_preflight_message(
        self,
        preflight: ProjectDirectorBoundedReworkReviewReentryPreflight,
    ) -> ProjectDirectorMessage:
        return ProjectDirectorMessage(
            id=preflight.preflight_id,
            session_id=preflight.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=(
                "P25 bounded rework review preflight ready: "
                f"{preflight.preflight_id} source diff {preflight.source_candidate_diff_id} "
                "reviewer_attempted=false reviewer_started=false provider_called=false"
            ),
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=preflight.authority.session_id
            ),
            intent=P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_INTENT,
            related_project_id=preflight.authority.project_id,
            related_task_id=preflight.exact_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_ACTION_TYPE,
                    **preflight.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_P25_H_PREFLIGHT_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=preflight.created_at,
        )

    def _build_claim_message(
        self,
        claim: ProjectDirectorBoundedReworkReviewInvocationClaim,
    ) -> ProjectDirectorMessage:
        return ProjectDirectorMessage(
            id=claim.review_claim_id,
            session_id=claim.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=(
                "P25 bounded rework review claim claimed: "
                f"{claim.review_claim_id} preflight {claim.preflight_id} claimed"
            ),
            sequence_no=self._message_repository.get_next_sequence_no(
                session_id=claim.authority.session_id
            ),
            intent=P25_BOUNDED_REWORK_REVIEW_CLAIM_INTENT,
            related_project_id=claim.authority.project_id,
            related_task_id=claim.exact_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_REVIEW_CLAIM_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_REVIEW_CLAIM_ACTION_TYPE,
                    **claim.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_P25_H_CLAIM_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=claim.created_at,
        )

    @staticmethod
    def _preflight_message_valid(
        message: ProjectDirectorMessage,
        preflight: ProjectDirectorBoundedReworkReviewReentryPreflight,
    ) -> bool:
        expected_action = {
            "type": P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_ACTION_TYPE,
            **preflight.model_dump(mode="json"),
        }
        return bool(
            message.id == preflight.preflight_id
            and message.created_at == preflight.created_at
            and message.session_id == preflight.authority.session_id
            and message.related_project_id == preflight.authority.project_id
            and message.related_task_id == preflight.exact_task_id
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_INTENT
            and message.source_detail
            == P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SOURCE_DETAIL
            and message.content
            == (
                "P25 bounded rework review preflight ready: "
                f"{preflight.preflight_id} source diff {preflight.source_candidate_diff_id} "
                "reviewer_attempted=false reviewer_started=false provider_called=false"
            )
            and message.suggested_actions == [expected_action]
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
            and tuple(message.forbidden_actions_detected)
            == _P25_H_PREFLIGHT_FALSE_BOUNDARIES
            and message.token_count is None
            and message.estimated_cost is None
        )

    @staticmethod
    def _claim_message_valid(
        message: ProjectDirectorMessage,
        claim: ProjectDirectorBoundedReworkReviewInvocationClaim,
    ) -> bool:
        expected_action = {
            "type": P25_BOUNDED_REWORK_REVIEW_CLAIM_ACTION_TYPE,
            **claim.model_dump(mode="json"),
        }
        return bool(
            message.id == claim.review_claim_id
            and message.created_at == claim.created_at
            and message.session_id == claim.authority.session_id
            and message.related_project_id == claim.authority.project_id
            and message.related_task_id == claim.exact_task_id
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent == P25_BOUNDED_REWORK_REVIEW_CLAIM_INTENT
            and message.source_detail == P25_BOUNDED_REWORK_REVIEW_CLAIM_SOURCE_DETAIL
            and message.content
            == (
                "P25 bounded rework review claim claimed: "
                f"{claim.review_claim_id} preflight {claim.preflight_id} claimed"
            )
            and message.suggested_actions == [expected_action]
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
            and tuple(message.forbidden_actions_detected)
            == _P25_H_CLAIM_FALSE_BOUNDARIES
            and message.token_count is None
            and message.estimated_cost is None
            and claim.review_claim_token not in message.content
        )

    @staticmethod
    def _semantic_preflight_payload(
        preflight: ProjectDirectorBoundedReworkReviewReentryPreflight,
    ) -> dict[str, Any]:
        return preflight.model_dump(
            mode="python",
            exclude={"preflight_id", "preflight_fingerprint", "created_at"},
        )

    @staticmethod
    def _same_lineage(
        left: RevalidatedProjectDirectorBoundedReworkCandidateDiff,
        right: RevalidatedProjectDirectorBoundedReworkCandidateDiff,
    ) -> bool:
        return bool(
            left.package == right.package
            and left.reservation == right.reservation
            and left.invocation_claim == right.invocation_claim
            and left.invocation_outcome == right.invocation_outcome
            and left.candidate_manifest == right.candidate_manifest
            and left.candidate_diff == right.candidate_diff
        )

    @staticmethod
    def _require_package(
        package: ProjectDirectorBoundedReworkInstructionPackage | None,
    ) -> ProjectDirectorBoundedReworkInstructionPackage:
        if package is None or package.workspace_binding is None:
            raise _Blocked("history_invalid")
        return package

    @staticmethod
    def _require_manifest(
        manifest: ProjectDirectorBoundedReworkCandidateManifest | None,
    ) -> ProjectDirectorBoundedReworkCandidateManifest:
        if manifest is None:
            raise _Blocked("history_invalid")
        return manifest

    @staticmethod
    def _require_diff(
        candidate_diff: ProjectDirectorBoundedReworkCandidateDiff | None,
    ) -> ProjectDirectorBoundedReworkCandidateDiff:
        if candidate_diff is None:
            raise _Blocked("history_invalid")
        return candidate_diff

    def _rollback_read_transaction(self) -> None:
        if self._message_repository._session.in_transaction():
            self._message_repository._session.rollback()

    @staticmethod
    def _blocked(
        reason: BoundedReworkBlockedReason,
    ) -> PreparedProjectDirectorBoundedReworkReviewReentry:
        return PreparedProjectDirectorBoundedReworkReviewReentry(
            status="blocked",
            preflight=None,
            preflight_message=None,
            review_claim=None,
            review_claim_message=None,
            blocked_reasons=(reason,),
        )


__all__ = (
    "P25_BOUNDED_REWORK_REVIEW_CLAIM_ACTION_TYPE",
    "P25_BOUNDED_REWORK_REVIEW_CLAIM_INTENT",
    "P25_BOUNDED_REWORK_REVIEW_CLAIM_SOURCE_DETAIL",
    "P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_ACTION_TYPE",
    "P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_INTENT",
    "P25_BOUNDED_REWORK_REVIEW_PREFLIGHT_SOURCE_DETAIL",
    "PreparedProjectDirectorBoundedReworkReviewReentry",
    "ProjectDirectorBoundedReworkReviewReentryPreflightService",
)
