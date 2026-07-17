"""Fresh disposition consumption gate for Project Director P21-D-C2."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition import (
    ReviewDispositionType,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition_consumption import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_preflight_service import (
    DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
    RevalidatedPersistedReviewResultFingerprint,
)
from app.services.project_director_sandbox_candidate_diff_review_execution_preflight_service import (
    REVIEW_OUTPUT_SCHEMA_VERSION,
)
from app.services.project_director_post_review_source_evidence_resolver import (
    ProjectDirectorPostReviewSourceEvidenceResolver,
    ResolvedProjectDirectorPostReviewSourceEvidence,
)
from app.services.project_director_sandbox_candidate_diff_review_handoff_service import (
    ProjectDirectorSandboxCandidateDiffReviewHandoffService,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    ProjectDirectorSandboxCandidateDiffService,
)


P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL = (
    "p21_d_sandbox_candidate_diff_review_disposition_consumed_fresh"
)
P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE = (
    "p21_d_sandbox_candidate_diff_review_disposition_consumption_record"
)
DISPOSITION_CONSUMPTION_SCHEMA_VERSION = "p21-d-c2.v1"

_LOWER_HEX_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_VALID_REVIEWER_EXECUTORS = ("codex", "claude-code")
_VALID_REVIEW_VERDICTS = (
    "no_blocking_findings",
    "non_blocking_findings",
    "changes_required",
)
_VALID_REVIEW_RISK_LEVELS = ("low", "medium", "high")
_C1_FALSE_FLAGS = (
    "continuation_started",
    "rework_started",
    "disposition_consumed",
    "human_escalation_package_created",
    "human_decision_recorded",
    "main_project_file_written",
    "sandbox_file_written",
    "manifest_file_written",
    "diff_file_written",
    "patch_applied",
    "git_write_performed",
    "worktree_created",
    "worker_started",
    "task_created",
    "run_created",
    "gate_allows_write",
)


@dataclass(frozen=True, slots=True)
class PreparedSandboxCandidateDiffReviewDispositionConsumption:
    """P21-D-C2 result and optional append-only consumption message."""

    result: ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class _ValidatedC1Evidence:
    source_disposition_message_id: UUID
    source_review_message_id: UUID
    source_preflight_message_id: UUID
    source_diff_message_id: UUID
    disposition_id: UUID
    disposition_type: ReviewDispositionType
    disposition_reason: str
    review_result_fingerprint: str
    revalidated_review_result_fingerprint: str
    source_diff_sha256: str
    review_prompt_sha256: str
    review_scope_paths: list[str]
    review_output_schema_version: str
    source_review_verdict: str
    source_review_risk_level: str


class ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService:
    """Consume one fresh automatic disposition without starting its handoff."""

    def __init__(
        self,
        *,
        session_repository: ProjectDirectorSessionRepository | None = None,
        message_repository: ProjectDirectorMessageRepository | None = None,
        task_repository: TaskRepository | None = None,
        review_handoff_service: (
            ProjectDirectorSandboxCandidateDiffReviewHandoffService | None
        ) = None,
        candidate_diff_service: ProjectDirectorSandboxCandidateDiffService | None = None,
        source_evidence_resolver: ProjectDirectorPostReviewSourceEvidenceResolver | None = None,
    ) -> None:
        self._session_repository = session_repository
        self._message_repository = message_repository
        self._task_repository = task_repository
        self._review_handoff_service = review_handoff_service
        self._candidate_diff_service = candidate_diff_service
        self._source_evidence_resolver = source_evidence_resolver

    def prepare_candidate_diff_review_disposition_consumption(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedSandboxCandidateDiffReviewDispositionConsumption:
        """Validate freshness and append one audit-only consumption record."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
            or self._review_handoff_service is None
            or self._candidate_diff_service is None
        ):
            raise ValueError("disposition consumption dependencies are required")

        with self._message_repository.sqlite_immediate_transaction():
            return self._prepare_candidate_diff_review_disposition_consumption(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
            )

    def _prepare_candidate_diff_review_disposition_consumption(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
    ) -> PreparedSandboxCandidateDiffReviewDispositionConsumption:
        blocked_reasons: list[str] = []
        c1_evidence: _ValidatedC1Evidence | None = None
        revalidation: RevalidatedPersistedReviewResultFingerprint | None = None
        persisted_source_diff_sha256 = ""
        persisted_source_scope_paths: list[str] = []
        current_diff_sha256 = ""
        current_scope_paths: list[str] = []
        workspace_path = ""
        workspace_path_within_root = False
        source_diff_revalidated = False
        current_diff_regenerated = False
        replay_check_completed = False
        prior_consumption_detected = False

        def blocked_result() -> PreparedSandboxCandidateDiffReviewDispositionConsumption:
            return PreparedSandboxCandidateDiffReviewDispositionConsumption(
                result=self._blocked_result(
                    source_consumption_preflight_message_id=source_message_id,
                    evidence=c1_evidence,
                    revalidation=revalidation,
                    persisted_source_diff_sha256=persisted_source_diff_sha256,
                    persisted_source_scope_paths=persisted_source_scope_paths,
                    current_diff_sha256=current_diff_sha256,
                    current_scope_paths=current_scope_paths,
                    workspace_path=workspace_path,
                    workspace_path_within_root=workspace_path_within_root,
                    source_diff_revalidated=source_diff_revalidated,
                    current_diff_regenerated=current_diff_regenerated,
                    replay_check_completed=replay_check_completed,
                    prior_consumption_detected=prior_consumption_detected,
                    blocked_reasons=blocked_reasons,
                ),
                message=None,
            )

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            blocked_reasons.append("session_missing")

        source_c1_message = self._message_repository.get_by_id(source_message_id)
        c1_action = self._source_c1_action(
            source_c1_message=source_c1_message,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        c1_evidence = self._validated_c1_evidence(
            c1_action,
            session_id=session_id,
            source_task_id=source_task_id,
            blocked_reasons=blocked_reasons,
        )
        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons or c1_evidence is None or session_obj is None:
            return blocked_result()

        if self._source_evidence_resolver is not None:
            p25_evidence = self._source_evidence_resolver.resolve(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=c1_evidence.source_review_message_id,
            )
            if p25_evidence.source_review_kind == "p25_h":
                return self._prepare_p25_h_consumption(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_consumption_preflight_message_id=source_message_id,
                    session_project_id=session_obj.project_id,
                    evidence=c1_evidence,
                    resolved=p25_evidence,
                )

        source_review_message = self._message_repository.get_by_id(
            c1_evidence.source_review_message_id
        )
        revalidation = ProjectDirectorSandboxCandidateDiffReviewDispositionService.revalidate_persisted_review_result_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=c1_evidence.source_review_message_id,
            source_review_message=source_review_message,
        )
        blocked_reasons.extend(revalidation.blocked_reasons)
        if not revalidation.blocked_reasons:
            if (
                revalidation.review_result_fingerprint
                != c1_evidence.review_result_fingerprint
            ):
                blocked_reasons.append("review_result_fingerprint_mismatch")
            if not self._review_source_binding_matches(c1_evidence, revalidation):
                blocked_reasons.append("review_source_binding_mismatch")
        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return blocked_result()

        source_task = self._task_repository.get_by_id(source_task_id)
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        source_diff_message = self._message_repository.get_by_id(
            c1_evidence.source_diff_message_id
        )
        if source_diff_message is None:
            blocked_reasons.append("source_diff_message_missing")
        if blocked_reasons:
            return blocked_result()

        persisted_diff = self._review_handoff_service.build_candidate_diff_review_handoff_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=c1_evidence.source_diff_message_id,
            source_task=source_task,
            source_message=source_diff_message,
            user_confirmed=True,
            handoff_mode="readonly_real_diff_review",
            requested_reviewer_executor=revalidation.requested_reviewer_executor,
        )
        if (
            persisted_diff.review_handoff_status != "created"
            or not persisted_diff.source_diff_verified
        ):
            blocked_reasons.extend(
                ["source_diff_validation_failed", "review_evidence_stale"]
            )
            return blocked_result()

        persisted_source_diff_sha256 = persisted_diff.source_diff_sha256
        persisted_source_scope_paths = list(persisted_diff.review_scope_paths)
        source_diff_revalidated = True
        if persisted_source_diff_sha256 != c1_evidence.source_diff_sha256:
            blocked_reasons.extend(
                ["source_diff_sha256_mismatch", "review_evidence_stale"]
            )
        if persisted_source_scope_paths != c1_evidence.review_scope_paths:
            blocked_reasons.extend(
                ["review_scope_paths_mismatch", "review_evidence_stale"]
            )
        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return blocked_result()

        source_diff_action = source_diff_message.suggested_actions[0]
        source_candidate_write_message_id = self._uuid_from_action(
            source_diff_action,
            "source_message_id",
        )
        persisted_workspace_path = source_diff_action.get("workspace_path")
        if source_candidate_write_message_id is None:
            blocked_reasons.append("source_candidate_write_binding_invalid")
        source_candidate_write_message = (
            self._message_repository.get_by_id(source_candidate_write_message_id)
            if source_candidate_write_message_id is not None
            else None
        )
        if source_candidate_write_message is None:
            blocked_reasons.append("source_candidate_write_message_missing")
        elif (
            source_candidate_write_message.session_id != session_id
            or source_candidate_write_message.related_task_id != source_task_id
        ):
            blocked_reasons.append("source_candidate_write_binding_invalid")
        if not isinstance(persisted_workspace_path, str) or not persisted_workspace_path:
            blocked_reasons.append("trusted_workspace_invalid")
        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return blocked_result()

        current_diff = self._candidate_diff_service.build_candidate_diff_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=source_candidate_write_message_id,
            source_task=source_task,
            source_message=source_candidate_write_message,
            user_confirmed=True,
            diff_mode="readonly_unified_diff",
            max_diff_bytes=persisted_diff.diff_bytes,
        )
        workspace_path = current_diff.workspace_path or ""
        workspace_path_within_root = current_diff.workspace_path_within_root
        if (
            current_diff.diff_generation_status != "generated"
            or not current_diff.readonly_real_diff_generated
            or not current_diff.real_diff_generated
            or not current_diff.source_candidate_write_verified
        ):
            if not current_diff.workspace_path_within_root:
                blocked_reasons.append("trusted_workspace_invalid")
            blocked_reasons.extend(
                ["current_diff_regeneration_failed", "review_evidence_stale"]
            )
            blocked_reasons = self._dedupe(blocked_reasons)
            return blocked_result()
        current_diff_regenerated = True

        if (
            current_diff.workspace_path != persisted_workspace_path
            or not current_diff.workspace_path_within_root
        ):
            blocked_reasons.extend(
                ["trusted_workspace_invalid", "review_evidence_stale"]
            )

        current_diff_sha256 = hashlib.sha256(
            current_diff.unified_diff_text.encode("utf-8")
        ).hexdigest()
        current_scope_paths = [
            entry.relative_path for entry in current_diff.diff_entries
        ]
        if not (
            current_diff_sha256
            == persisted_source_diff_sha256
            == c1_evidence.source_diff_sha256
        ):
            blocked_reasons.extend(["current_diff_mismatch", "review_evidence_stale"])
        if not (
            current_scope_paths
            == persisted_source_scope_paths
            == c1_evidence.review_scope_paths
        ):
            blocked_reasons.extend(
                ["review_scope_paths_mismatch", "review_evidence_stale"]
            )
        blocked_reasons = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return blocked_result()

        prior_consumption_detected = self._prior_consumption_exists(
            session_id=session_id,
            source_consumption_preflight_message_id=source_message_id,
        )
        replay_check_completed = True
        if prior_consumption_detected:
            blocked_reasons.append("disposition_already_consumed")
            return blocked_result()

        consumption_id = uuid4()
        consumed_at = datetime.now(timezone.utc)
        result = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
            consumption_status="consumed",
            consumption_id=consumption_id,
            source_consumption_preflight_message_id=source_message_id,
            source_disposition_message_id=(
                c1_evidence.source_disposition_message_id
            ),
            source_review_message_id=c1_evidence.source_review_message_id,
            source_diff_message_id=c1_evidence.source_diff_message_id,
            disposition_id=c1_evidence.disposition_id,
            disposition_type=c1_evidence.disposition_type,
            review_result_fingerprint=c1_evidence.review_result_fingerprint,
            revalidated_review_result_fingerprint=(
                revalidation.review_result_fingerprint
            ),
            reviewed_diff_sha256=c1_evidence.source_diff_sha256,
            persisted_source_diff_sha256=persisted_source_diff_sha256,
            current_diff_sha256=current_diff_sha256,
            reviewed_scope_paths=list(c1_evidence.review_scope_paths),
            persisted_source_scope_paths=persisted_source_scope_paths,
            current_scope_paths=current_scope_paths,
            workspace_path=workspace_path,
            workspace_path_within_root=True,
            source_diff_revalidated=True,
            current_diff_regenerated=True,
            evidence_fresh=True,
            disposition_consumed=True,
            continuation_eligible=(
                c1_evidence.disposition_type == "AUTO_CONTINUE"
            ),
            rework_eligible=c1_evidence.disposition_type == "AUTO_REWORK",
            replay_check_completed=True,
            prior_consumption_detected=False,
            consumed_at=consumed_at,
        )
        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "A fresh automatic review disposition was consumed for a future "
                    "bounded handoff. No continuation or rework was started, no file "
                    "was written, and no Git write was authorized. AI Project "
                    "Director total loop remains Partial."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="sandbox_candidate_diff_review_disposition_consumption",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=(
                    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL
                ),
                suggested_actions=[
                    self._consumption_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        source_consumption_preflight_message_id=source_message_id,
                        evidence=c1_evidence,
                        result=result,
                    )
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=[
                    "no_continuation_start",
                    "no_rework_start",
                    "no_human_escalation_package",
                    "no_human_decision",
                    "no_workspace_write",
                    "no_main_project_file_write",
                    "no_manifest_write",
                    "no_diff_file_write",
                    "no_patch_apply",
                    "no_product_runtime_git_write",
                    "no_worker_dispatch",
                    "no_task_creation",
                    "no_run_creation",
                    "no_worktree_creation",
                ],
                created_at=consumed_at,
            )
        )
        return PreparedSandboxCandidateDiffReviewDispositionConsumption(
            result=result,
            message=message,
        )

    def _prepare_p25_h_consumption(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_consumption_preflight_message_id: UUID,
        session_project_id: UUID,
        evidence: _ValidatedC1Evidence,
        resolved: ResolvedProjectDirectorPostReviewSourceEvidence,
    ) -> PreparedSandboxCandidateDiffReviewDispositionConsumption:
        if (
            resolved.blocked_reasons
            or resolved.source_preflight_message_id != evidence.source_preflight_message_id
            or resolved.source_diff_message_id != evidence.source_diff_message_id
            or resolved.source_diff_sha256 != evidence.source_diff_sha256
            or resolved.review_result_fingerprint != evidence.review_result_fingerprint
            or resolved.review_prompt_sha256 != evidence.review_prompt_sha256
            or list(resolved.review_scope_paths) != evidence.review_scope_paths
            or resolved.review_output_schema_version != evidence.review_output_schema_version
            or resolved.source_review_verdict != evidence.source_review_verdict
            or resolved.source_review_risk_level != evidence.source_review_risk_level
            or resolved.exact_task_id != source_task_id
            or not resolved.workspace_path
        ):
            return PreparedSandboxCandidateDiffReviewDispositionConsumption(
                result=self._blocked_result(
                    source_consumption_preflight_message_id=source_consumption_preflight_message_id,
                    evidence=evidence,
                    revalidation=None,
                    persisted_source_diff_sha256="",
                    persisted_source_scope_paths=[],
                    current_diff_sha256="",
                    current_scope_paths=[],
                    workspace_path="",
                    workspace_path_within_root=False,
                    source_diff_revalidated=False,
                    current_diff_regenerated=False,
                    replay_check_completed=True,
                    prior_consumption_detected=False,
                    blocked_reasons=list(resolved.blocked_reasons)
                    or ["review_source_binding_mismatch"],
                ),
                message=None,
            )
        if self._prior_consumption_exists(
            session_id=session_id,
            source_consumption_preflight_message_id=source_consumption_preflight_message_id,
        ):
            return PreparedSandboxCandidateDiffReviewDispositionConsumption(
                result=self._blocked_result(
                    source_consumption_preflight_message_id=source_consumption_preflight_message_id,
                    evidence=evidence,
                    revalidation=None,
                    persisted_source_diff_sha256=resolved.source_diff_sha256,
                    persisted_source_scope_paths=list(resolved.review_scope_paths),
                    current_diff_sha256=resolved.source_diff_sha256,
                    current_scope_paths=list(resolved.review_scope_paths),
                    workspace_path=resolved.workspace_path,
                    workspace_path_within_root=True,
                    source_diff_revalidated=True,
                    current_diff_regenerated=True,
                    replay_check_completed=True,
                    prior_consumption_detected=True,
                    blocked_reasons=["disposition_already_consumed"],
                ),
                message=None,
            )
        consumed_at = datetime.now(timezone.utc)
        result = ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
            consumption_status="consumed",
            consumption_id=uuid4(),
            source_consumption_preflight_message_id=source_consumption_preflight_message_id,
            source_disposition_message_id=evidence.source_disposition_message_id,
            source_review_message_id=evidence.source_review_message_id,
            source_diff_message_id=evidence.source_diff_message_id,
            disposition_id=evidence.disposition_id,
            disposition_type=evidence.disposition_type,
            review_result_fingerprint=evidence.review_result_fingerprint,
            revalidated_review_result_fingerprint=resolved.review_result_fingerprint,
            reviewed_diff_sha256=resolved.source_diff_sha256,
            persisted_source_diff_sha256=resolved.source_diff_sha256,
            current_diff_sha256=resolved.source_diff_sha256,
            reviewed_scope_paths=list(resolved.review_scope_paths),
            persisted_source_scope_paths=list(resolved.review_scope_paths),
            current_scope_paths=list(resolved.review_scope_paths),
            workspace_path=resolved.workspace_path,
            workspace_path_within_root=True,
            source_diff_revalidated=True,
            current_diff_regenerated=True,
            evidence_fresh=True,
            disposition_consumed=True,
            continuation_eligible=evidence.disposition_type == "AUTO_CONTINUE",
            rework_eligible=evidence.disposition_type == "AUTO_REWORK",
            replay_check_completed=True,
            prior_consumption_detected=False,
            consumed_at=consumed_at,
        )
        message = self._message_repository.create(ProjectDirectorMessage(
            session_id=session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content="A fresh automatic review disposition was consumed for a future bounded handoff.",
            sequence_no=self._message_repository.get_next_sequence_no(session_id=session_id),
            intent="sandbox_candidate_diff_review_disposition_consumption",
            related_project_id=session_project_id,
            related_task_id=source_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
            suggested_actions=[self._consumption_action(
                session_id=session_id,
                source_task_id=source_task_id,
                source_consumption_preflight_message_id=source_consumption_preflight_message_id,
                evidence=evidence,
                result=result,
            )],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=["no_continuation_start", "no_rework_start", "no_product_runtime_git_write"],
            created_at=consumed_at,
        ))
        return PreparedSandboxCandidateDiffReviewDispositionConsumption(result=result, message=message)

    @staticmethod
    def _source_c1_action(
        *,
        source_c1_message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if source_c1_message is None:
            blocked_reasons.append("source_consumption_preflight_message_missing")
            return None
        if source_c1_message.session_id != session_id:
            blocked_reasons.append("source_consumption_preflight_session_mismatch")
        if source_c1_message.related_task_id != source_task_id:
            blocked_reasons.append("source_consumption_preflight_task_mismatch")
        if source_c1_message.source != ProjectDirectorMessageSource.SYSTEM:
            blocked_reasons.append("source_consumption_preflight_source_invalid")
        if source_c1_message.requires_confirmation is not False:
            blocked_reasons.append(
                "source_consumption_preflight_confirmation_contract_invalid"
            )
        if (
            source_c1_message.source_detail
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_SOURCE_DETAIL
        ):
            blocked_reasons.append("source_message_is_not_p21_d_c1_ready_preflight")
        if not source_c1_message.suggested_actions:
            blocked_reasons.append("p21_d_c1_ready_preflight_record_missing")
            return None
        first_action = source_c1_message.suggested_actions[0]
        if (
            not isinstance(first_action, dict)
            or first_action.get("type")
            != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_PREFLIGHT_ACTION_TYPE
        ):
            blocked_reasons.append("p21_d_c1_ready_preflight_record_missing")
            return None
        return first_action

    @classmethod
    def _validated_c1_evidence(
        cls,
        action: dict[str, Any] | None,
        *,
        session_id: UUID,
        source_task_id: UUID,
        blocked_reasons: list[str],
    ) -> _ValidatedC1Evidence | None:
        if action is None:
            return None
        if (
            action.get("schema_version")
            != DISPOSITION_CONSUMPTION_PREFLIGHT_SCHEMA_VERSION
        ):
            blocked_reasons.append("c1_schema_version_mismatch")
        if action.get("preflight_status") != "ready":
            blocked_reasons.append("c1_preflight_status_not_ready")
        if (
            action.get("blocked_reasons") != []
            or action.get("replay_check_completed") is not True
            or action.get("prior_preflight_detected") is not False
        ):
            blocked_reasons.append("c1_preflight_not_clean")
        if (
            action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
        ):
            blocked_reasons.append("c1_binding_invalid")

        source_disposition_message_id = cls._uuid_from_action(
            action, "source_disposition_message_id"
        )
        source_review_message_id = cls._uuid_from_action(
            action, "source_review_message_id"
        )
        source_preflight_message_id = cls._uuid_from_action(
            action, "source_preflight_message_id"
        )
        source_diff_message_id = cls._uuid_from_action(
            action, "source_diff_message_id"
        )
        disposition_id = cls._uuid_from_action(action, "disposition_id")
        if any(
            value is None
            for value in (
                source_disposition_message_id,
                source_review_message_id,
                source_preflight_message_id,
                source_diff_message_id,
                disposition_id,
            )
        ):
            blocked_reasons.append("c1_binding_invalid")

        review_result_fingerprint = action.get("review_result_fingerprint")
        revalidated_review_result_fingerprint = action.get(
            "revalidated_review_result_fingerprint"
        )
        source_diff_sha256 = action.get("source_diff_sha256")
        review_prompt_sha256 = action.get("review_prompt_sha256")
        if not all(
            cls._is_sha256(value)
            for value in (
                review_result_fingerprint,
                revalidated_review_result_fingerprint,
                source_diff_sha256,
                review_prompt_sha256,
            )
        ):
            blocked_reasons.append("c1_fingerprint_invalid")
        if review_result_fingerprint != revalidated_review_result_fingerprint:
            blocked_reasons.append("c1_review_fingerprint_mismatch")

        review_scope_paths = cls._review_scope_paths(action)
        if review_scope_paths is None:
            blocked_reasons.append("c1_scope_invalid")
        review_output_schema_version = action.get("review_output_schema_version")
        source_review_verdict = action.get("source_review_verdict")
        source_review_risk_level = action.get("source_review_risk_level")
        disposition_reason = action.get("disposition_reason")
        if (
            review_output_schema_version != REVIEW_OUTPUT_SCHEMA_VERSION
            or source_review_verdict not in _VALID_REVIEW_VERDICTS
            or source_review_risk_level not in _VALID_REVIEW_RISK_LEVELS
            or not isinstance(disposition_reason, str)
            or not disposition_reason
        ):
            blocked_reasons.append("c1_binding_invalid")

        disposition_type = action.get("disposition_type")
        eligibility = (
            action.get("continuation_eligible"),
            action.get("rework_eligible"),
        )
        expected_eligibility = (
            disposition_type == "AUTO_CONTINUE",
            disposition_type == "AUTO_REWORK",
        )
        if (
            disposition_type not in ("AUTO_CONTINUE", "AUTO_REWORK")
            or eligibility != expected_eligibility
        ):
            blocked_reasons.append("c1_eligibility_invalid")
        if not all(action.get(flag) is False for flag in _C1_FALSE_FLAGS):
            blocked_reasons.append("c1_write_boundary_violated")
        if action.get("ai_project_director_total_loop") != "Partial":
            blocked_reasons.append("c1_write_boundary_violated")

        if blocked_reasons:
            return None
        if (
            source_disposition_message_id is None
            or source_review_message_id is None
            or source_preflight_message_id is None
            or source_diff_message_id is None
            or disposition_id is None
            or review_scope_paths is None
        ):
            return None
        return _ValidatedC1Evidence(
            source_disposition_message_id=source_disposition_message_id,
            source_review_message_id=source_review_message_id,
            source_preflight_message_id=source_preflight_message_id,
            source_diff_message_id=source_diff_message_id,
            disposition_id=disposition_id,
            disposition_type=disposition_type,
            disposition_reason=disposition_reason,
            review_result_fingerprint=review_result_fingerprint,
            revalidated_review_result_fingerprint=(
                revalidated_review_result_fingerprint
            ),
            source_diff_sha256=source_diff_sha256,
            review_prompt_sha256=review_prompt_sha256,
            review_scope_paths=review_scope_paths,
            review_output_schema_version=review_output_schema_version,
            source_review_verdict=source_review_verdict,
            source_review_risk_level=source_review_risk_level,
        )

    def _prior_consumption_exists(
        self,
        *,
        session_id: UUID,
        source_consumption_preflight_message_id: UUID,
    ) -> bool:
        before_message_id: UUID | None = None
        while True:
            messages, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=100,
                before_message_id=before_message_id,
            )
            for message in messages:
                if (
                    message.source_detail
                    != P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL
                    or not message.suggested_actions
                ):
                    continue
                first_action = message.suggested_actions[0]
                if (
                    isinstance(first_action, dict)
                    and first_action.get("type")
                    == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE
                    and first_action.get("source_consumption_preflight_message_id")
                    == str(source_consumption_preflight_message_id)
                ):
                    return True
            if not has_more:
                return False
            if not messages:
                return False
            before_message_id = messages[0].id

    @staticmethod
    def _review_source_binding_matches(
        evidence: _ValidatedC1Evidence,
        revalidation: RevalidatedPersistedReviewResultFingerprint,
    ) -> bool:
        return (
            evidence.source_preflight_message_id
            == revalidation.source_preflight_message_id
            and evidence.source_diff_message_id == revalidation.source_diff_message_id
            and revalidation.requested_reviewer_executor
            in _VALID_REVIEWER_EXECUTORS
            and evidence.source_diff_sha256 == revalidation.source_diff_sha256
            and evidence.review_prompt_sha256 == revalidation.review_prompt_sha256
            and evidence.review_scope_paths == (revalidation.review_scope_paths or [])
            and evidence.review_output_schema_version
            == revalidation.review_output_schema_version
            and evidence.source_review_verdict == revalidation.verdict
            and evidence.source_review_risk_level == revalidation.risk_level
        )

    @staticmethod
    def _consumption_action(
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_consumption_preflight_message_id: UUID,
        evidence: _ValidatedC1Evidence,
        result: ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult,
    ) -> dict[str, Any]:
        return {
            "type": P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE,
            "schema_version": DISPOSITION_CONSUMPTION_SCHEMA_VERSION,
            "consumption_status": result.consumption_status,
            "consumption_id": str(result.consumption_id),
            "consumed_at": result.consumed_at.isoformat(),
            "session_id": str(session_id),
            "source_task_id": str(source_task_id),
            "source_consumption_preflight_message_id": str(
                source_consumption_preflight_message_id
            ),
            "source_disposition_message_id": str(
                evidence.source_disposition_message_id
            ),
            "source_review_message_id": str(evidence.source_review_message_id),
            "source_preflight_message_id": str(
                evidence.source_preflight_message_id
            ),
            "source_diff_message_id": str(evidence.source_diff_message_id),
            "disposition_id": str(evidence.disposition_id),
            "disposition_type": evidence.disposition_type,
            "disposition_reason": evidence.disposition_reason,
            "review_result_fingerprint": result.review_result_fingerprint,
            "revalidated_review_result_fingerprint": (
                result.revalidated_review_result_fingerprint
            ),
            "reviewed_diff_sha256": result.reviewed_diff_sha256,
            "persisted_source_diff_sha256": result.persisted_source_diff_sha256,
            "current_diff_sha256": result.current_diff_sha256,
            "review_prompt_sha256": evidence.review_prompt_sha256,
            "reviewed_scope_paths": list(result.reviewed_scope_paths),
            "persisted_source_scope_paths": list(
                result.persisted_source_scope_paths
            ),
            "current_scope_paths": list(result.current_scope_paths),
            "review_output_schema_version": evidence.review_output_schema_version,
            "source_review_verdict": evidence.source_review_verdict,
            "source_review_risk_level": evidence.source_review_risk_level,
            "workspace_path": result.workspace_path,
            "workspace_path_within_root": result.workspace_path_within_root,
            "source_diff_revalidated": result.source_diff_revalidated,
            "current_diff_regenerated": result.current_diff_regenerated,
            "evidence_fresh": result.evidence_fresh,
            "disposition_consumed": result.disposition_consumed,
            "continuation_eligible": result.continuation_eligible,
            "rework_eligible": result.rework_eligible,
            "replay_check_completed": result.replay_check_completed,
            "prior_consumption_detected": result.prior_consumption_detected,
            "blocked_reasons": list(result.blocked_reasons),
            "continuation_started": False,
            "rework_started": False,
            "human_escalation_package_created": False,
            "human_decision_recorded": False,
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
            "gate_allows_write": False,
            "ai_project_director_total_loop": "Partial",
        }

    @staticmethod
    def _blocked_result(
        *,
        source_consumption_preflight_message_id: UUID,
        evidence: _ValidatedC1Evidence | None,
        revalidation: RevalidatedPersistedReviewResultFingerprint | None,
        persisted_source_diff_sha256: str,
        persisted_source_scope_paths: list[str],
        current_diff_sha256: str,
        current_scope_paths: list[str],
        workspace_path: str,
        workspace_path_within_root: bool,
        source_diff_revalidated: bool,
        current_diff_regenerated: bool,
        replay_check_completed: bool,
        prior_consumption_detected: bool,
        blocked_reasons: list[str],
    ) -> ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult:
        return ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult(
            consumption_status="blocked",
            source_consumption_preflight_message_id=(
                source_consumption_preflight_message_id
            ),
            source_disposition_message_id=(
                evidence.source_disposition_message_id
                if evidence is not None
                else None
            ),
            source_review_message_id=(
                evidence.source_review_message_id if evidence is not None else None
            ),
            source_diff_message_id=(
                evidence.source_diff_message_id if evidence is not None else None
            ),
            disposition_id=evidence.disposition_id if evidence is not None else None,
            disposition_type=(
                evidence.disposition_type if evidence is not None else None
            ),
            review_result_fingerprint=(
                evidence.review_result_fingerprint if evidence is not None else ""
            ),
            revalidated_review_result_fingerprint=(
                revalidation.review_result_fingerprint
                if revalidation is not None
                else ""
            ),
            reviewed_diff_sha256=(
                evidence.source_diff_sha256 if evidence is not None else ""
            ),
            persisted_source_diff_sha256=persisted_source_diff_sha256,
            current_diff_sha256=current_diff_sha256,
            reviewed_scope_paths=(
                list(evidence.review_scope_paths) if evidence is not None else []
            ),
            persisted_source_scope_paths=list(persisted_source_scope_paths),
            current_scope_paths=list(current_scope_paths),
            workspace_path=workspace_path,
            workspace_path_within_root=workspace_path_within_root,
            source_diff_revalidated=source_diff_revalidated,
            current_diff_regenerated=current_diff_regenerated,
            replay_check_completed=replay_check_completed,
            prior_consumption_detected=prior_consumption_detected,
            blocked_reasons=ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService._dedupe(
                blocked_reasons
            ),
        )

    @staticmethod
    def _review_scope_paths(action: dict[str, Any]) -> list[str] | None:
        raw_paths = action.get("review_scope_paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            return None
        if any(not isinstance(path, str) or not path for path in raw_paths):
            return None
        if len(set(raw_paths)) != len(raw_paths):
            return None
        return list(raw_paths)

    @staticmethod
    def _uuid_from_action(action: dict[str, Any], key: str) -> UUID | None:
        raw_value = action.get(key)
        if not isinstance(raw_value, str) or not raw_value:
            return None
        try:
            return UUID(raw_value)
        except ValueError:
            return None

    @staticmethod
    def _is_sha256(value: Any) -> bool:
        return isinstance(value, str) and _LOWER_HEX_SHA256.match(value) is not None

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
    "DISPOSITION_CONSUMPTION_SCHEMA_VERSION",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL",
    "P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE",
    "PreparedSandboxCandidateDiffReviewDispositionConsumption",
    "ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionService",
)
