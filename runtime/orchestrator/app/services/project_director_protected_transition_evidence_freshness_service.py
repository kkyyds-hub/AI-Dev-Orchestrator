"""Unified protected-transition evidence freshness gate for P21-D-E."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import ValidationError

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_protected_transition_evidence_freshness import (
    ProjectDirectorProtectedTransitionEvidenceFreshnessResult,
    ProtectedTransitionAuthority,
    ProtectedTransitionKind,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition_consumption import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_disposition_handoff import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_decision_consumption import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_decision_lifecycle import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult,
)
from app.domain.project_director_sandbox_candidate_diff_review_human_escalation_package import (
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult,
)
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_sandbox_candidate_diff_review_disposition_consumption_service import (
    DISPOSITION_CONSUMPTION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_handoff_service import (
    DISPOSITION_HANDOFF_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL,
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
)
from app.services.project_director_sandbox_candidate_diff_review_handoff_service import (
    ProjectDirectorSandboxCandidateDiffReviewHandoffService,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_consumption_service import (
    HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_lifecycle_service import (
    HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_decision_service import (
    HUMAN_ESCALATION_DECISION_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService,
)
from app.services.project_director_sandbox_candidate_diff_review_human_escalation_package_service import (
    HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE,
    P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL,
    ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService,
)
from app.services.project_director_sandbox_candidate_diff_service import (
    ProjectDirectorSandboxCandidateDiffService,
)


P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL = (
    "p21_d_protected_transition_evidence_freshness_validated"
)
P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE = (
    "p21_d_protected_transition_evidence_freshness_record"
)
PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION = "p21-d-e.v1"

_VALID_REVIEWER_EXECUTORS = ("codex", "claude-code")
_VALID_REVIEW_VERDICTS = (
    "no_blocking_findings",
    "non_blocking_findings",
    "changes_required",
)
_VALID_REVIEW_RISK_LEVELS = ("low", "medium", "high")


@dataclass(frozen=True, slots=True)
class PreparedProjectDirectorProtectedTransitionEvidenceFreshness:
    result: ProjectDirectorProtectedTransitionEvidenceFreshnessResult
    message: ProjectDirectorMessage | None


@dataclass(frozen=True, slots=True)
class RevalidatedPersistedProtectedTransitionFreshnessFingerprint:
    freshness_evidence_fingerprint: str
    blocked_reasons: list[str]
    source_freshness_message_id: UUID | None = None
    freshness_validation_id: UUID | None = None
    source_transition_message_id: UUID | None = None
    source_transition_record_id: UUID | None = None
    transition_authority: ProtectedTransitionAuthority | None = None
    transition_kind: ProtectedTransitionKind | None = None
    source_review_message_id: UUID | None = None
    source_diff_message_id: UUID | None = None
    validated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RevalidatedCurrentProtectedTransitionEvidenceFreshness:
    """从 exact persisted E 证据重新计算当前只读 freshness。"""

    freshness_status: Literal["ready", "blocked"]
    source_freshness_message_id: UUID
    source_transition_message_id: UUID | None
    source_review_message_id: UUID | None
    source_diff_message_id: UUID | None
    persisted_freshness_evidence_fingerprint: str
    current_freshness_fingerprint: str
    reviewed_diff_sha256: str
    current_diff_sha256: str
    reviewed_scope_paths: list[str]
    current_scope_paths: list[str]
    workspace_path: str
    workspace_path_within_root: bool
    review_result_fingerprint: str
    validated_at: datetime
    blocked_reasons: list[str]


@dataclass(frozen=True, slots=True)
class _TransitionEvidence:
    authority: ProtectedTransitionAuthority
    transition_kind: ProtectedTransitionKind
    source_transition_record_id: UUID
    source_review_message_id: UUID
    source_review_preflight_message_id: UUID
    source_diff_message_id: UUID
    review_result_fingerprint: str
    reviewed_diff_sha256: str
    reviewed_scope_paths: list[str]
    review_prompt_sha256: str
    review_output_schema_version: str
    source_review_verdict: str
    source_review_risk_level: str
    requested_reviewer_executor: str
    source_handoff_message_id: UUID | None = None
    handoff_id: UUID | None = None
    source_disposition_consumption_message_id: UUID | None = None
    disposition_consumption_id: UUID | None = None
    source_disposition_message_id: UUID | None = None
    disposition_id: UUID | None = None
    disposition_type: str | None = None
    source_human_consumption_message_id: UUID | None = None
    human_consumption_id: UUID | None = None
    source_decision_message_id: UUID | None = None
    decision_id: UUID | None = None
    source_package_message_id: UUID | None = None
    escalation_package_id: UUID | None = None
    decision_action: str | None = None
    decision_expires_at: datetime | None = None
    aggregate_evidence_fingerprint: str = ""
    revalidated_aggregate_evidence_fingerprint: str = ""
    decision_confirmation_fingerprint: str = ""
    revalidated_decision_confirmation_fingerprint: str = ""
    decision_consumption_evidence_fingerprint: str = ""
    revalidated_decision_consumption_evidence_fingerprint: str = ""


@dataclass(frozen=True, slots=True)
class _FreshnessHistory:
    prior_freshness_validation_detected: bool = False
    decision_consumption_count: int = 0
    decision_revoked_after_consumption: bool = False


class ProjectDirectorProtectedTransitionEvidenceFreshnessService:
    """Revalidate automatic or human transition evidence without executing it."""

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

    def prepare_protected_transition_evidence_freshness_gate(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        validated_at: datetime | None = None,
    ) -> PreparedProjectDirectorProtectedTransitionEvidenceFreshness:
        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
            or self._review_handoff_service is None
            or self._candidate_diff_service is None
        ):
            raise ValueError("protected transition freshness dependencies required")
        with self._message_repository.sqlite_immediate_transaction():
            return self._prepare_protected_transition_evidence_freshness_gate(
                session_id=session_id,
                source_task_id=source_task_id,
                source_message_id=source_message_id,
                validated_at=validated_at,
            )

    @classmethod
    def revalidate_persisted_protected_transition_freshness_fingerprint(
        cls,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_freshness_message_id: UUID,
        source_freshness_action: dict[str, Any],
    ) -> RevalidatedPersistedProtectedTransitionFreshnessFingerprint:
        blocked_reasons: list[str] = []
        action = source_freshness_action
        if action.get("type") != P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE:
            blocked_reasons.append("protected_transition_freshness_action_type_invalid")
        if action.get("schema_version") != PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION:
            blocked_reasons.append("protected_transition_freshness_schema_version_mismatch")
        if action.get("session_id") != str(session_id):
            blocked_reasons.append("protected_transition_freshness_session_mismatch")
        if action.get("source_task_id") != str(source_task_id):
            blocked_reasons.append("protected_transition_freshness_task_mismatch")
        try:
            result = cls._domain_from_action(
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult,
                action,
            )
        except ValidationError:
            result = None
            blocked_reasons.append("protected_transition_freshness_domain_invalid")
        if result is not None and result.freshness_status != "ready":
            blocked_reasons.append("protected_transition_freshness_domain_invalid")
        if blocked_reasons or result is None:
            return RevalidatedPersistedProtectedTransitionFreshnessFingerprint(
                freshness_evidence_fingerprint="",
                blocked_reasons=cls._dedupe(blocked_reasons),
                source_freshness_message_id=source_freshness_message_id,
            )
        payload = cls._freshness_evidence_canonical_payload(
            session_id=session_id,
            result=result,
        )
        return RevalidatedPersistedProtectedTransitionFreshnessFingerprint(
            freshness_evidence_fingerprint=cls._canonical_payload_fingerprint(payload),
            blocked_reasons=[],
            source_freshness_message_id=source_freshness_message_id,
            freshness_validation_id=result.freshness_validation_id,
            source_transition_message_id=result.source_transition_message_id,
            source_transition_record_id=result.source_transition_record_id,
            transition_authority=result.transition_authority,
            transition_kind=result.transition_kind,
            source_review_message_id=result.source_review_message_id,
            source_diff_message_id=result.source_diff_message_id,
            validated_at=result.validated_at,
        )

    def revalidate_current_automatic_transition_evidence_from_persisted_freshness(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_freshness_message_id: UUID,
    ) -> RevalidatedCurrentProtectedTransitionEvidenceFreshness:
        """不持久化地重建 E 证据，并重新生成当前 readonly diff。"""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
            or self._review_handoff_service is None
            or self._candidate_diff_service is None
        ):
            raise ValueError("protected transition freshness dependencies required")

        validated_at = datetime.now(timezone.utc)
        blocked_reasons: list[str] = []
        persisted: ProjectDirectorProtectedTransitionEvidenceFreshnessResult | None = None
        evidence: _TransitionEvidence | None = None
        persisted_fingerprint = ""
        reviewed_diff_sha256 = ""
        current_diff_sha256 = ""
        reviewed_scope_paths: list[str] = []
        current_scope_paths: list[str] = []
        workspace_path = ""
        workspace_path_within_root = False
        review_result_fingerprint = ""

        session_obj = self._session_repository.get_by_id(session_id)
        source_task = self._task_repository.get_by_id(source_task_id)
        freshness_message = self._message_repository.get_by_id(
            source_freshness_message_id
        )
        if session_obj is None or source_task is None:
            blocked_reasons.append("source_freshness_invalid")
        elif source_task.project_id != session_obj.project_id:
            blocked_reasons.append("source_freshness_invalid")

        freshness_action: dict[str, Any] | None = None
        if session_obj is not None and source_task is not None:
            freshness_action = self._exact_action(
                message=freshness_message,
                session_id=session_id,
                source_task_id=source_task_id,
                source_project_id=session_obj.project_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                intent="protected_transition_evidence_freshness",
                source_detail=P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL,
                action_type=P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE,
                schema_version=PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION,
                expected_requires_confirmation=False,
                blocked_reason="source_freshness_invalid",
                blocked_reasons=blocked_reasons,
            )
        if freshness_action is not None:
            try:
                persisted = self._domain_from_action(
                    ProjectDirectorProtectedTransitionEvidenceFreshnessResult,
                    freshness_action,
                )
            except ValidationError:
                blocked_reasons.append("source_freshness_invalid")
            revalidation = self.revalidate_persisted_protected_transition_freshness_fingerprint(
                session_id=session_id,
                source_task_id=source_task_id,
                source_freshness_message_id=source_freshness_message_id,
                source_freshness_action=freshness_action,
            )
            blocked_reasons.extend(revalidation.blocked_reasons)
            persisted_fingerprint = revalidation.freshness_evidence_fingerprint

        if persisted is not None:
            reviewed_diff_sha256 = persisted.reviewed_diff_sha256
            reviewed_scope_paths = list(persisted.reviewed_scope_paths)
            workspace_path = persisted.workspace_path
            workspace_path_within_root = persisted.workspace_path_within_root
            review_result_fingerprint = persisted.review_result_fingerprint
            if (
                persisted.freshness_status != "ready"
                or persisted.transition_authority != "AUTOMATED_DISPOSITION"
                or persisted.transition_kind
                not in ("CONTINUE_GUARDRAIL", "BOUNDED_REWORK_GUARDRAIL")
                or persisted.freshness_evidence_fingerprint
                != persisted_fingerprint
                or not persisted.evidence_fresh
                or not persisted.gate_allows_protected_transition_guardrail
                or persisted.gate_allows_write
            ):
                blocked_reasons.append("source_freshness_invalid")

        transition_message = None
        if persisted is not None:
            transition_message = self._message_repository.get_by_id(
                persisted.source_transition_message_id
            )
        if (
            persisted is not None
            and session_obj is not None
            and transition_message is not None
        ):
            evidence = self._automatic_transition_evidence(
                source_message=transition_message,
                session_id=session_id,
                source_task_id=source_task_id,
                source_project_id=session_obj.project_id,
                blocked_reasons=blocked_reasons,
            )
        elif persisted is not None:
            blocked_reasons.append("source_freshness_invalid")

        if persisted is not None and evidence is not None:
            exact_bindings = (
                (persisted.source_transition_record_id, evidence.source_transition_record_id),
                (persisted.transition_authority, evidence.authority),
                (persisted.transition_kind, evidence.transition_kind),
                (persisted.source_review_message_id, evidence.source_review_message_id),
                (persisted.source_diff_message_id, evidence.source_diff_message_id),
                (persisted.source_handoff_message_id, evidence.source_handoff_message_id),
                (persisted.handoff_id, evidence.handoff_id),
                (
                    persisted.source_disposition_consumption_message_id,
                    evidence.source_disposition_consumption_message_id,
                ),
                (persisted.disposition_consumption_id, evidence.disposition_consumption_id),
                (persisted.source_disposition_message_id, evidence.source_disposition_message_id),
                (persisted.disposition_id, evidence.disposition_id),
                (persisted.disposition_type, evidence.disposition_type),
                (persisted.review_result_fingerprint, evidence.review_result_fingerprint),
                (persisted.reviewed_diff_sha256, evidence.reviewed_diff_sha256),
                (persisted.reviewed_scope_paths, evidence.reviewed_scope_paths),
            )
            if any(left != right for left, right in exact_bindings):
                blocked_reasons.append("source_freshness_invalid")

        review_revalidation: RevalidatedPersistedReviewResultFingerprint | None = None
        source_review_message = None
        if evidence is not None:
            source_review_message = self._message_repository.get_by_id(
                evidence.source_review_message_id
            )
            if not self._review_message_metadata_valid(
                message=source_review_message,
                session_id=session_id,
                source_task_id=source_task_id,
                source_project_id=session_obj.project_id if session_obj else None,
            ):
                blocked_reasons.append("source_freshness_invalid")
            review_revalidation = ProjectDirectorSandboxCandidateDiffReviewDispositionService.revalidate_persisted_review_result_fingerprint(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=evidence.source_review_message_id,
                source_review_message=source_review_message,
            )
            blocked_reasons.extend(review_revalidation.blocked_reasons)
            if (
                review_revalidation.review_result_fingerprint
                != evidence.review_result_fingerprint
                or not self._review_binding_matches(evidence, review_revalidation)
            ):
                blocked_reasons.append("source_freshness_invalid")

        persisted_diff = None
        source_diff_message = None
        if evidence is not None and source_task is not None and review_revalidation is not None:
            source_diff_message = self._message_repository.get_by_id(
                evidence.source_diff_message_id
            )
            if (
                source_diff_message is None
                or source_diff_message.session_id != session_id
                or source_diff_message.related_project_id != source_task.project_id
                or source_diff_message.related_task_id != source_task_id
            ):
                blocked_reasons.append("source_freshness_invalid")
            else:
                persisted_diff = self._review_handoff_service.build_candidate_diff_review_handoff_from_sources(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_message_id=evidence.source_diff_message_id,
                    source_task=source_task,
                    source_message=source_diff_message,
                    user_confirmed=True,
                    handoff_mode="readonly_real_diff_review",
                    requested_reviewer_executor=review_revalidation.requested_reviewer_executor,
                )
                if (
                    persisted_diff.review_handoff_status != "created"
                    or not persisted_diff.source_diff_verified
                    or persisted_diff.source_diff_sha256 != reviewed_diff_sha256
                    or list(persisted_diff.review_scope_paths) != reviewed_scope_paths
                ):
                    blocked_reasons.append("source_freshness_invalid")

        if persisted_diff is not None and source_diff_message is not None and source_task is not None:
            source_diff_action = source_diff_message.suggested_actions[0]
            source_candidate_write_message_id = self._uuid_from_action(
                source_diff_action,
                "source_message_id",
            )
            persisted_workspace_path = source_diff_action.get("workspace_path")
            candidate_write_message = (
                self._message_repository.get_by_id(source_candidate_write_message_id)
                if source_candidate_write_message_id is not None
                else None
            )
            if (
                source_candidate_write_message_id is None
                or candidate_write_message is None
                or candidate_write_message.session_id != session_id
                or candidate_write_message.related_task_id != source_task_id
                or candidate_write_message.related_project_id != source_task.project_id
            ):
                blocked_reasons.append("source_freshness_invalid")
            else:
                current_diff = self._candidate_diff_service.build_candidate_diff_from_sources(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_message_id=source_candidate_write_message_id,
                    source_task=source_task,
                    source_message=candidate_write_message,
                    user_confirmed=True,
                    diff_mode="readonly_unified_diff",
                    max_diff_bytes=persisted_diff.diff_bytes,
                )
                workspace_path = current_diff.workspace_path or ""
                workspace_path_within_root = current_diff.workspace_path_within_root
                current_diff_sha256 = hashlib.sha256(
                    current_diff.unified_diff_text.encode("utf-8")
                ).hexdigest()
                current_scope_paths = [
                    entry.relative_path for entry in current_diff.diff_entries
                ]
                if (
                    current_diff.diff_generation_status != "generated"
                    or not current_diff.readonly_real_diff_generated
                    or not current_diff.real_diff_generated
                    or not current_diff.source_candidate_write_verified
                    or current_diff.workspace_path != persisted_workspace_path
                    or current_diff.workspace_path != persisted.workspace_path
                    or not current_diff.workspace_path_within_root
                ):
                    blocked_reasons.append("current_workspace_invalid")
                if current_diff_sha256 != reviewed_diff_sha256:
                    blocked_reasons.append("current_diff_mismatch")
                if current_scope_paths != reviewed_scope_paths:
                    blocked_reasons.append("current_scope_mismatch")

        blocked_reasons = self._dedupe(blocked_reasons)
        current_fingerprint = self._canonical_payload_fingerprint(
            {
                "session_id": str(session_id),
                "source_task_id": str(source_task_id),
                "source_freshness_message_id": str(source_freshness_message_id),
                "source_transition_message_id": str(
                    persisted.source_transition_message_id if persisted else None
                ),
                "source_review_message_id": str(
                    persisted.source_review_message_id if persisted else None
                ),
                "source_diff_message_id": str(
                    persisted.source_diff_message_id if persisted else None
                ),
                "transition_kind": persisted.transition_kind if persisted else None,
                "transition_authority": (
                    persisted.transition_authority if persisted else None
                ),
                "review_result_fingerprint": review_result_fingerprint,
                "persisted_freshness_evidence_fingerprint": persisted_fingerprint,
                "reviewed_diff_sha256": reviewed_diff_sha256,
                "current_diff_sha256": current_diff_sha256,
                "reviewed_scope_paths": reviewed_scope_paths,
                "current_scope_paths": current_scope_paths,
                "workspace_path": workspace_path,
                "workspace_path_within_root": workspace_path_within_root,
            }
        )
        return RevalidatedCurrentProtectedTransitionEvidenceFreshness(
            freshness_status="blocked" if blocked_reasons else "ready",
            source_freshness_message_id=source_freshness_message_id,
            source_transition_message_id=(
                persisted.source_transition_message_id if persisted else None
            ),
            source_review_message_id=(
                persisted.source_review_message_id if persisted else None
            ),
            source_diff_message_id=(
                persisted.source_diff_message_id if persisted else None
            ),
            persisted_freshness_evidence_fingerprint=persisted_fingerprint,
            current_freshness_fingerprint=current_fingerprint,
            reviewed_diff_sha256=reviewed_diff_sha256,
            current_diff_sha256=current_diff_sha256,
            reviewed_scope_paths=reviewed_scope_paths,
            current_scope_paths=current_scope_paths,
            workspace_path=workspace_path,
            workspace_path_within_root=workspace_path_within_root,
            review_result_fingerprint=review_result_fingerprint,
            validated_at=validated_at,
            blocked_reasons=blocked_reasons,
        )

    def _prepare_protected_transition_evidence_freshness_gate(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        validated_at: datetime | None,
    ) -> PreparedProjectDirectorProtectedTransitionEvidenceFreshness:
        blocked_reasons: list[str] = []
        evidence: _TransitionEvidence | None = None
        history = _FreshnessHistory()
        revalidated_review_fingerprint = ""
        persisted_source_diff_sha256 = ""
        persisted_source_scope_paths: list[str] = []
        current_diff_sha256 = ""
        current_scope_paths: list[str] = []
        workspace_path = ""
        workspace_path_within_root = False
        source_review_validated = False
        review_fingerprint_revalidated = False
        source_diff_revalidated = False
        current_workspace_revalidated = False
        current_diff_regenerated = False
        ordered_scope_revalidated = False
        normalized_validated_at = validated_at or datetime.now(timezone.utc)
        if not self._timezone_aware_datetime(normalized_validated_at):
            blocked_reasons.append("protected_transition_validated_at_invalid")
            normalized_validated_at = None

        session_obj = self._session_repository.get_by_id(session_id)
        source_task = self._task_repository.get_by_id(source_task_id)
        source_message = self._message_repository.get_by_id(source_message_id)
        if session_obj is None:
            blocked_reasons.append("session_missing")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        if (
            session_obj is not None
            and source_task is not None
            and source_task.project_id != session_obj.project_id
        ):
            blocked_reasons.append("source_task_project_mismatch")
        if blocked_reasons or session_obj is None or source_task is None:
            return self._blocked_result(
                source_message_id=source_message_id,
                source_task_id=source_task_id,
                validated_at=normalized_validated_at,
                evidence=evidence,
                history=history,
                revalidated_review_fingerprint=revalidated_review_fingerprint,
                persisted_source_diff_sha256=persisted_source_diff_sha256,
                persisted_source_scope_paths=persisted_source_scope_paths,
                current_diff_sha256=current_diff_sha256,
                current_scope_paths=current_scope_paths,
                workspace_path=workspace_path,
                workspace_path_within_root=workspace_path_within_root,
                source_review_validated=source_review_validated,
                review_fingerprint_revalidated=review_fingerprint_revalidated,
                source_diff_revalidated=source_diff_revalidated,
                current_workspace_revalidated=current_workspace_revalidated,
                current_diff_regenerated=current_diff_regenerated,
                ordered_scope_revalidated=ordered_scope_revalidated,
                replay_check_completed=False,
                blocked_reasons=blocked_reasons,
            )

        if source_message is None:
            blocked_reasons.append("source_transition_message_missing")
        elif source_message.source_detail == (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL
        ):
            evidence = self._automatic_transition_evidence(
                source_message=source_message,
                session_id=session_id,
                source_task_id=source_task_id,
                source_project_id=session_obj.project_id,
                blocked_reasons=blocked_reasons,
            )
        elif source_message.source_detail == (
            P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL
        ):
            evidence = self._human_transition_evidence(
                source_message=source_message,
                session_id=session_id,
                source_task_id=source_task_id,
                source_project_id=session_obj.project_id,
                validated_at=normalized_validated_at,
                blocked_reasons=blocked_reasons,
            )
        else:
            blocked_reasons.append("source_transition_type_not_allowed")
        if blocked_reasons or evidence is None:
            return self._blocked_result(
                source_message_id=source_message_id,
                source_task_id=source_task_id,
                validated_at=normalized_validated_at,
                evidence=evidence,
                history=history,
                revalidated_review_fingerprint=revalidated_review_fingerprint,
                persisted_source_diff_sha256=persisted_source_diff_sha256,
                persisted_source_scope_paths=persisted_source_scope_paths,
                current_diff_sha256=current_diff_sha256,
                current_scope_paths=current_scope_paths,
                workspace_path=workspace_path,
                workspace_path_within_root=workspace_path_within_root,
                source_review_validated=False,
                review_fingerprint_revalidated=False,
                source_diff_revalidated=False,
                current_workspace_revalidated=False,
                current_diff_regenerated=False,
                ordered_scope_revalidated=False,
                replay_check_completed=False,
                blocked_reasons=blocked_reasons,
            )

        history = self._scan_history(
            session_id=session_id,
            source_project_id=session_obj.project_id,
            source_transition_message=source_message,
            evidence=evidence,
            blocked_reasons=blocked_reasons,
        )
        if history.prior_freshness_validation_detected:
            blocked_reasons.append("protected_transition_freshness_already_validated")
        if evidence.authority == "HUMAN_ESCALATION_DECISION":
            if history.decision_revoked_after_consumption:
                blocked_reasons.append(
                    "human_escalation_decision_revoked_after_consumption"
                )
            if history.decision_consumption_count == 0:
                blocked_reasons.append(
                    "human_escalation_decision_consumption_replay_invalid"
                )
            elif history.decision_consumption_count > 1:
                blocked_reasons.append("human_escalation_decision_consumption_duplicate")
        blocked_reasons[:] = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return self._blocked_result(
                source_message_id=source_message_id,
                source_task_id=source_task_id,
                validated_at=normalized_validated_at,
                evidence=evidence,
                history=history,
                revalidated_review_fingerprint=revalidated_review_fingerprint,
                persisted_source_diff_sha256=persisted_source_diff_sha256,
                persisted_source_scope_paths=persisted_source_scope_paths,
                current_diff_sha256=current_diff_sha256,
                current_scope_paths=current_scope_paths,
                workspace_path=workspace_path,
                workspace_path_within_root=workspace_path_within_root,
                source_review_validated=False,
                review_fingerprint_revalidated=False,
                source_diff_revalidated=False,
                current_workspace_revalidated=False,
                current_diff_regenerated=False,
                ordered_scope_revalidated=False,
                replay_check_completed=True,
                blocked_reasons=blocked_reasons,
            )

        if self._source_evidence_resolver is not None:
            resolved = self._source_evidence_resolver.resolve(
                session_id=session_id,
                source_task_id=source_task_id,
                source_review_message_id=evidence.source_review_message_id,
            )
            if resolved.source_review_kind == "p25_h":
                if (
                    resolved.blocked_reasons
                    or resolved.source_preflight_message_id
                    != evidence.source_review_preflight_message_id
                    or resolved.source_diff_message_id != evidence.source_diff_message_id
                    or resolved.source_diff_sha256 != evidence.reviewed_diff_sha256
                    or resolved.review_result_fingerprint
                    != evidence.review_result_fingerprint
                    or resolved.review_prompt_sha256 != evidence.review_prompt_sha256
                    or list(resolved.review_scope_paths)
                    != evidence.reviewed_scope_paths
                    or resolved.review_output_schema_version
                    != evidence.review_output_schema_version
                    or resolved.source_review_verdict != evidence.source_review_verdict
                    or resolved.source_review_risk_level
                    != evidence.source_review_risk_level
                    or resolved.exact_task_id != source_task_id
                    or not resolved.workspace_path
                ):
                    blocked_reasons.extend(resolved.blocked_reasons or ("review_source_binding_mismatch",))
                    return self._blocked_result(
                        source_message_id=source_message_id,
                        source_task_id=source_task_id,
                        validated_at=normalized_validated_at,
                        evidence=evidence,
                        history=history,
                        revalidated_review_fingerprint="",
                        persisted_source_diff_sha256="",
                        persisted_source_scope_paths=[],
                        current_diff_sha256="",
                        current_scope_paths=[],
                        workspace_path="",
                        workspace_path_within_root=False,
                        source_review_validated=False,
                        review_fingerprint_revalidated=False,
                        source_diff_revalidated=False,
                        current_workspace_revalidated=False,
                        current_diff_regenerated=False,
                        ordered_scope_revalidated=False,
                        replay_check_completed=True,
                        blocked_reasons=blocked_reasons,
                    )
                result_values = self._ready_result_values(
                    freshness_validation_id=uuid4(),
                    source_message_id=source_message_id,
                    source_task_id=source_task_id,
                    validated_at=normalized_validated_at,
                    evidence=evidence,
                    history=history,
                    revalidated_review_fingerprint=resolved.review_result_fingerprint,
                    persisted_source_diff_sha256=resolved.source_diff_sha256,
                    persisted_source_scope_paths=list(resolved.review_scope_paths),
                    current_diff_sha256=resolved.source_diff_sha256,
                    current_scope_paths=list(resolved.review_scope_paths),
                    workspace_path=resolved.workspace_path,
                )
                fingerprint_basis = ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
                    freshness_evidence_fingerprint="0" * 64,
                    **result_values,
                )
                result = ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
                    freshness_evidence_fingerprint=self._canonical_payload_fingerprint(
                        self._freshness_evidence_canonical_payload(
                            session_id=session_id,
                            result=fingerprint_basis,
                        )
                    ),
                    **result_values,
                )
                message = self._message_repository.create(ProjectDirectorMessage(
                    session_id=session_id,
                    role=ProjectDirectorMessageRole.ASSISTANT,
                    content="P25-H/P25-G evidence was revalidated for a future protected transition guardrail.",
                    sequence_no=self._message_repository.get_next_sequence_no(session_id=session_id),
                    intent="protected_transition_evidence_freshness",
                    related_project_id=session_obj.project_id,
                    related_task_id=source_task_id,
                    source=ProjectDirectorMessageSource.SYSTEM,
                    source_detail=P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL,
                    suggested_actions=[self._freshness_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        result=result,
                    )],
                    requires_confirmation=False,
                    risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                    forbidden_actions_detected=self._forbidden_actions(),
                    created_at=normalized_validated_at,
                ))
                return PreparedProjectDirectorProtectedTransitionEvidenceFreshness(
                    result=result,
                    message=message,
                )
            if resolved.source_review_kind == "invalid":
                blocked_reasons.extend(
                    resolved.blocked_reasons or ("p25_h_marker_invalid",)
                )
                return self._blocked_result(
                    source_message_id=source_message_id,
                    source_task_id=source_task_id,
                    validated_at=normalized_validated_at,
                    evidence=evidence,
                    history=history,
                    revalidated_review_fingerprint="",
                    persisted_source_diff_sha256="",
                    persisted_source_scope_paths=[],
                    current_diff_sha256="",
                    current_scope_paths=[],
                    workspace_path="",
                    workspace_path_within_root=False,
                    source_review_validated=False,
                    review_fingerprint_revalidated=False,
                    source_diff_revalidated=False,
                    current_workspace_revalidated=False,
                    current_diff_regenerated=False,
                    ordered_scope_revalidated=False,
                    replay_check_completed=True,
                    blocked_reasons=blocked_reasons,
                )

        source_review_message = self._message_repository.get_by_id(
            evidence.source_review_message_id
        )
        if not self._review_message_metadata_valid(
            message=source_review_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=session_obj.project_id,
        ):
            blocked_reasons.append("source_review_message_metadata_invalid")
        review_revalidation = ProjectDirectorSandboxCandidateDiffReviewDispositionService.revalidate_persisted_review_result_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=evidence.source_review_message_id,
            source_review_message=source_review_message,
        )
        blocked_reasons.extend(review_revalidation.blocked_reasons)
        revalidated_review_fingerprint = review_revalidation.review_result_fingerprint
        if not review_revalidation.blocked_reasons:
            source_review_validated = True
            if evidence.review_result_fingerprint != revalidated_review_fingerprint:
                blocked_reasons.append("review_result_fingerprint_mismatch")
            elif not self._review_binding_matches(evidence, review_revalidation):
                blocked_reasons.append("review_source_binding_mismatch")
            else:
                review_fingerprint_revalidated = True
        blocked_reasons[:] = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return self._blocked_result(
                source_message_id=source_message_id,
                source_task_id=source_task_id,
                validated_at=normalized_validated_at,
                evidence=evidence,
                history=history,
                revalidated_review_fingerprint=revalidated_review_fingerprint,
                persisted_source_diff_sha256=persisted_source_diff_sha256,
                persisted_source_scope_paths=persisted_source_scope_paths,
                current_diff_sha256=current_diff_sha256,
                current_scope_paths=current_scope_paths,
                workspace_path=workspace_path,
                workspace_path_within_root=workspace_path_within_root,
                source_review_validated=source_review_validated,
                review_fingerprint_revalidated=review_fingerprint_revalidated,
                source_diff_revalidated=False,
                current_workspace_revalidated=False,
                current_diff_regenerated=False,
                ordered_scope_revalidated=False,
                replay_check_completed=True,
                blocked_reasons=blocked_reasons,
            )

        source_diff_message = self._message_repository.get_by_id(
            evidence.source_diff_message_id
        )
        if source_diff_message is None:
            blocked_reasons.append("source_diff_message_missing")
        elif (
            source_diff_message.session_id != session_id
            or source_diff_message.related_project_id != session_obj.project_id
            or source_diff_message.related_task_id != source_task_id
        ):
            blocked_reasons.append("source_diff_message_binding_invalid")
        persisted_diff = self._review_handoff_service.build_candidate_diff_review_handoff_from_sources(
            session_id=session_id,
            source_task_id=source_task_id,
            source_message_id=evidence.source_diff_message_id,
            source_task=source_task,
            source_message=source_diff_message,
            user_confirmed=True,
            handoff_mode="readonly_real_diff_review",
            requested_reviewer_executor=review_revalidation.requested_reviewer_executor,
        )
        if (
            persisted_diff.review_handoff_status != "created"
            or not persisted_diff.source_diff_verified
        ):
            blocked_reasons.extend(
                ["source_diff_validation_failed", "review_evidence_stale"]
            )
        else:
            source_diff_revalidated = True
            persisted_source_diff_sha256 = persisted_diff.source_diff_sha256
            persisted_source_scope_paths = list(persisted_diff.review_scope_paths)
            if persisted_source_diff_sha256 != evidence.reviewed_diff_sha256:
                blocked_reasons.extend(
                    ["source_diff_sha256_mismatch", "review_evidence_stale"]
                )
            if persisted_source_scope_paths != evidence.reviewed_scope_paths:
                blocked_reasons.extend(
                    ["review_scope_paths_mismatch", "review_evidence_stale"]
                )
        if blocked_reasons:
            return self._blocked_result(
                source_message_id=source_message_id,
                source_task_id=source_task_id,
                validated_at=normalized_validated_at,
                evidence=evidence,
                history=history,
                revalidated_review_fingerprint=revalidated_review_fingerprint,
                persisted_source_diff_sha256=persisted_source_diff_sha256,
                persisted_source_scope_paths=persisted_source_scope_paths,
                current_diff_sha256=current_diff_sha256,
                current_scope_paths=current_scope_paths,
                workspace_path=workspace_path,
                workspace_path_within_root=workspace_path_within_root,
                source_review_validated=source_review_validated,
                review_fingerprint_revalidated=review_fingerprint_revalidated,
                source_diff_revalidated=source_diff_revalidated,
                current_workspace_revalidated=False,
                current_diff_regenerated=False,
                ordered_scope_revalidated=False,
                replay_check_completed=True,
                blocked_reasons=blocked_reasons,
            )

        source_diff_action = source_diff_message.suggested_actions[0]
        source_candidate_write_message_id = self._uuid_from_action(
            source_diff_action,
            "source_message_id",
        )
        persisted_workspace_path = source_diff_action.get("workspace_path")
        source_candidate_write_message = (
            self._message_repository.get_by_id(source_candidate_write_message_id)
            if source_candidate_write_message_id is not None
            else None
        )
        if source_candidate_write_message_id is None:
            blocked_reasons.append("source_candidate_write_binding_invalid")
        if source_candidate_write_message is None:
            blocked_reasons.append("source_candidate_write_message_missing")
        elif (
            source_candidate_write_message.session_id != session_id
            or source_candidate_write_message.related_task_id != source_task_id
            or source_candidate_write_message.related_project_id
            != session_obj.project_id
        ):
            blocked_reasons.append("source_candidate_write_binding_invalid")
        if not isinstance(persisted_workspace_path, str) or not persisted_workspace_path:
            blocked_reasons.append("trusted_workspace_invalid")
        if blocked_reasons:
            return self._blocked_result(
                source_message_id=source_message_id,
                source_task_id=source_task_id,
                validated_at=normalized_validated_at,
                evidence=evidence,
                history=history,
                revalidated_review_fingerprint=revalidated_review_fingerprint,
                persisted_source_diff_sha256=persisted_source_diff_sha256,
                persisted_source_scope_paths=persisted_source_scope_paths,
                current_diff_sha256=current_diff_sha256,
                current_scope_paths=current_scope_paths,
                workspace_path=workspace_path,
                workspace_path_within_root=workspace_path_within_root,
                source_review_validated=source_review_validated,
                review_fingerprint_revalidated=review_fingerprint_revalidated,
                source_diff_revalidated=source_diff_revalidated,
                current_workspace_revalidated=False,
                current_diff_regenerated=False,
                ordered_scope_revalidated=False,
                replay_check_completed=True,
                blocked_reasons=blocked_reasons,
            )

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
        else:
            current_diff_regenerated = True
        if (
            current_diff.workspace_path != persisted_workspace_path
            or not current_diff.workspace_path_within_root
        ):
            blocked_reasons.extend(["trusted_workspace_invalid", "review_evidence_stale"])
        else:
            current_workspace_revalidated = True
        current_diff_sha256 = hashlib.sha256(
            current_diff.unified_diff_text.encode("utf-8")
        ).hexdigest()
        current_scope_paths = [entry.relative_path for entry in current_diff.diff_entries]
        if not (
            evidence.reviewed_diff_sha256
            == persisted_source_diff_sha256
            == current_diff_sha256
        ):
            blocked_reasons.extend(["current_diff_mismatch", "review_evidence_stale"])
        if not (
            evidence.reviewed_scope_paths
            == persisted_source_scope_paths
            == current_scope_paths
        ):
            blocked_reasons.extend(
                ["review_scope_paths_mismatch", "review_evidence_stale"]
            )
        else:
            ordered_scope_revalidated = True
        blocked_reasons[:] = self._dedupe(blocked_reasons)
        if blocked_reasons:
            return self._blocked_result(
                source_message_id=source_message_id,
                source_task_id=source_task_id,
                validated_at=normalized_validated_at,
                evidence=evidence,
                history=history,
                revalidated_review_fingerprint=revalidated_review_fingerprint,
                persisted_source_diff_sha256=persisted_source_diff_sha256,
                persisted_source_scope_paths=persisted_source_scope_paths,
                current_diff_sha256=current_diff_sha256,
                current_scope_paths=current_scope_paths,
                workspace_path=workspace_path,
                workspace_path_within_root=workspace_path_within_root,
                source_review_validated=source_review_validated,
                review_fingerprint_revalidated=review_fingerprint_revalidated,
                source_diff_revalidated=source_diff_revalidated,
                current_workspace_revalidated=current_workspace_revalidated,
                current_diff_regenerated=current_diff_regenerated,
                ordered_scope_revalidated=ordered_scope_revalidated,
                replay_check_completed=True,
                blocked_reasons=blocked_reasons,
            )

        freshness_validation_id = uuid4()
        result_values = self._ready_result_values(
            freshness_validation_id=freshness_validation_id,
            source_message_id=source_message_id,
            source_task_id=source_task_id,
            validated_at=normalized_validated_at,
            evidence=evidence,
            history=history,
            revalidated_review_fingerprint=revalidated_review_fingerprint,
            persisted_source_diff_sha256=persisted_source_diff_sha256,
            persisted_source_scope_paths=persisted_source_scope_paths,
            current_diff_sha256=current_diff_sha256,
            current_scope_paths=current_scope_paths,
            workspace_path=workspace_path,
        )
        fingerprint_basis = ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
            freshness_evidence_fingerprint="0" * 64,
            **result_values,
        )
        result = ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
            freshness_evidence_fingerprint=self._canonical_payload_fingerprint(
                self._freshness_evidence_canonical_payload(
                    session_id=session_id,
                    result=fingerprint_basis,
                )
            ),
            **result_values,
        )
        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "All persisted transition evidence was reloaded, the review "
                    "fingerprint and trusted workspace were revalidated, and the "
                    "current readonly diff was regenerated with the same SHA and "
                    "ordered scope. Only the next protected transition guardrail is "
                    "allowed. No continuation or rework started; no Task, Run, "
                    "Worker, worktree, file write, patch, or Git write was authorized. "
                    "AI Project Director total loop remains Partial."
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="protected_transition_evidence_freshness",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL,
                suggested_actions=[
                    self._freshness_action(
                        session_id=session_id,
                        source_task_id=source_task_id,
                        result=result,
                    )
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.HIGH,
                forbidden_actions_detected=self._forbidden_actions(),
                created_at=normalized_validated_at,
            )
        )
        return PreparedProjectDirectorProtectedTransitionEvidenceFreshness(
            result=result,
            message=message,
        )

    def _automatic_transition_evidence(
        self,
        *,
        source_message: ProjectDirectorMessage,
        session_id: UUID,
        source_task_id: UUID,
        source_project_id: UUID | None,
        blocked_reasons: list[str],
    ) -> _TransitionEvidence | None:
        action = self._exact_action(
            message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=source_project_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="sandbox_candidate_diff_review_disposition_handoff",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_SOURCE_DETAIL,
            action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_HANDOFF_ACTION_TYPE,
            schema_version=DISPOSITION_HANDOFF_SCHEMA_VERSION,
            expected_requires_confirmation=False,
            blocked_reason="source_automatic_handoff_invalid",
            blocked_reasons=blocked_reasons,
        )
        if action is None:
            return None
        try:
            handoff = self._domain_from_action(
                ProjectDirectorSandboxCandidateDiffReviewDispositionHandoffResult,
                action,
            )
        except ValidationError:
            blocked_reasons.append("source_automatic_handoff_domain_invalid")
            return None
        if handoff.handoff_status != "prepared":
            blocked_reasons.append("source_automatic_handoff_domain_invalid")
            return None
        c2_message = self._message_repository.get_by_id(
            handoff.source_consumption_message_id
        )
        c2_action = self._exact_action(
            message=c2_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=source_project_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="sandbox_candidate_diff_review_disposition_consumption",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMED_SOURCE_DETAIL,
            action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_DISPOSITION_CONSUMPTION_ACTION_TYPE,
            schema_version=DISPOSITION_CONSUMPTION_SCHEMA_VERSION,
            expected_requires_confirmation=False,
            blocked_reason="source_automatic_consumption_invalid",
            blocked_reasons=blocked_reasons,
        )
        if c2_action is None:
            return None
        try:
            consumption = self._domain_from_action(
                ProjectDirectorSandboxCandidateDiffReviewDispositionConsumptionResult,
                c2_action,
            )
        except ValidationError:
            blocked_reasons.append("source_automatic_consumption_domain_invalid")
            return None
        if consumption.consumption_status != "consumed":
            blocked_reasons.append("source_automatic_consumption_domain_invalid")
            return None
        binding_fields = (
            (handoff.source_consumption_id, consumption.consumption_id),
            (
                handoff.source_consumption_preflight_message_id,
                consumption.source_consumption_preflight_message_id,
            ),
            (handoff.source_disposition_message_id, consumption.source_disposition_message_id),
            (handoff.source_review_message_id, consumption.source_review_message_id),
            (handoff.source_diff_message_id, consumption.source_diff_message_id),
            (handoff.disposition_id, consumption.disposition_id),
            (handoff.disposition_type, consumption.disposition_type),
            (handoff.review_result_fingerprint, consumption.review_result_fingerprint),
            (
                handoff.revalidated_review_result_fingerprint,
                consumption.revalidated_review_result_fingerprint,
            ),
            (handoff.reviewed_diff_sha256, consumption.reviewed_diff_sha256),
            (
                handoff.persisted_source_diff_sha256,
                consumption.persisted_source_diff_sha256,
            ),
            (handoff.current_diff_sha256, consumption.current_diff_sha256),
            (handoff.reviewed_scope_paths, consumption.reviewed_scope_paths),
            (
                handoff.persisted_source_scope_paths,
                consumption.persisted_source_scope_paths,
            ),
            (handoff.current_scope_paths, consumption.current_scope_paths),
            (handoff.workspace_path, consumption.workspace_path),
            (handoff.workspace_path_within_root, consumption.workspace_path_within_root),
        )
        if any(left != right for left, right in binding_fields):
            blocked_reasons.append("automatic_handoff_consumption_binding_mismatch")
            return None
        expected_transition = {
            ("AUTO_CONTINUE", "automatic_continuation"): "CONTINUE_GUARDRAIL",
            ("AUTO_REWORK", "bounded_automatic_rework"): "BOUNDED_REWORK_GUARDRAIL",
        }.get((handoff.disposition_type, handoff.handoff_kind))
        if expected_transition is None:
            blocked_reasons.append("automatic_transition_mapping_invalid")
            return None
        review_material = self._review_material_from_action(
            c2_action,
            blocked_reasons,
            require_executor=False,
        )
        if review_material is None:
            return None
        source_review_preflight_message_id = self._uuid_from_action(
            c2_action,
            "source_preflight_message_id",
        )
        if source_review_preflight_message_id is None:
            blocked_reasons.append("source_review_binding_material_invalid")
            return None
        return _TransitionEvidence(
            authority="AUTOMATED_DISPOSITION",
            transition_kind=expected_transition,
            source_transition_record_id=handoff.handoff_id,
            source_review_message_id=handoff.source_review_message_id,
            source_review_preflight_message_id=source_review_preflight_message_id,
            source_diff_message_id=handoff.source_diff_message_id,
            review_result_fingerprint=handoff.review_result_fingerprint,
            reviewed_diff_sha256=handoff.reviewed_diff_sha256,
            reviewed_scope_paths=list(handoff.reviewed_scope_paths),
            review_prompt_sha256=review_material[0],
            review_output_schema_version=review_material[1],
            source_review_verdict=review_material[2],
            source_review_risk_level=review_material[3],
            requested_reviewer_executor="",
            source_handoff_message_id=source_message.id,
            handoff_id=handoff.handoff_id,
            source_disposition_consumption_message_id=handoff.source_consumption_message_id,
            disposition_consumption_id=consumption.consumption_id,
            source_disposition_message_id=handoff.source_disposition_message_id,
            disposition_id=handoff.disposition_id,
            disposition_type=handoff.disposition_type,
        )

    def _human_transition_evidence(
        self,
        *,
        source_message: ProjectDirectorMessage,
        session_id: UUID,
        source_task_id: UUID,
        source_project_id: UUID | None,
        validated_at: datetime,
        blocked_reasons: list[str],
    ) -> _TransitionEvidence | None:
        action = self._exact_action(
            message=source_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=source_project_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="sandbox_candidate_diff_review_human_escalation_decision_consumption",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL,
            action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE,
            schema_version=HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION,
            expected_requires_confirmation=False,
            blocked_reason="source_human_consumption_invalid",
            blocked_reasons=blocked_reasons,
        )
        if action is None:
            return None
        try:
            consumption = self._domain_from_action(
                ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult,
                action,
            )
        except ValidationError:
            blocked_reasons.append("source_human_consumption_domain_invalid")
            return None
        if consumption.consumption_status != "consumed":
            blocked_reasons.append("source_human_consumption_domain_invalid")
            return None
        consumption_revalidation = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService.revalidate_persisted_human_escalation_decision_consumption_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_consumption_message_id=source_message.id,
            source_consumption_action=action,
        )
        blocked_reasons.extend(consumption_revalidation.blocked_reasons)
        if (
            action.get("consumption_evidence_fingerprint")
            != consumption_revalidation.consumption_evidence_fingerprint
        ):
            blocked_reasons.append("decision_consumption_evidence_fingerprint_mismatch")
        if consumption.decision_action == "REJECT":
            blocked_reasons.append("terminal_rejection_has_no_protected_transition")
            return None
        expected_transition = {
            "APPROVE_CONTINUE": "CONTINUE_GUARDRAIL",
            "REQUEST_REWORK": "BOUNDED_REWORK_GUARDRAIL",
        }.get(consumption.decision_action)
        if expected_transition is None:
            blocked_reasons.append("human_transition_mapping_invalid")
            return None
        if validated_at >= consumption.decision_expires_at:
            blocked_reasons.append(
                "human_escalation_decision_expired_before_protected_transition"
            )

        decision_message = self._message_repository.get_by_id(
            consumption.source_decision_message_id
        )
        decision_action = self._exact_action(
            message=decision_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=source_project_id,
            role=ProjectDirectorMessageRole.USER,
            intent="sandbox_candidate_diff_review_human_escalation_decision",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_SOURCE_DETAIL,
            action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_ACTION_TYPE,
            schema_version=HUMAN_ESCALATION_DECISION_SCHEMA_VERSION,
            expected_requires_confirmation=False,
            blocked_reason="source_human_decision_invalid",
            blocked_reasons=blocked_reasons,
        )
        if decision_action is None:
            return None
        if decision_action.get("decision_status") != "recorded":
            blocked_reasons.append("source_human_decision_invalid")
            return None
        decision_revalidation = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionService.revalidate_persisted_human_escalation_decision_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_decision_message_id=consumption.source_decision_message_id,
            source_decision_action=decision_action,
        )
        blocked_reasons.extend(decision_revalidation.blocked_reasons)
        decision_fingerprints = (
            decision_action.get("decision_confirmation_fingerprint"),
            decision_revalidation.decision_confirmation_fingerprint,
            consumption.decision_confirmation_fingerprint,
            consumption.revalidated_decision_confirmation_fingerprint,
        )
        if len(set(decision_fingerprints)) != 1:
            blocked_reasons.append("decision_confirmation_fingerprint_mismatch")
        if (
            consumption.decision_id != decision_revalidation.decision_id
            or consumption.source_package_message_id
            != decision_revalidation.source_package_message_id
            or consumption.escalation_package_id
            != decision_revalidation.escalation_package_id
            or consumption.decision_action != decision_revalidation.decision_action
            or consumption.decision_expires_at
            != decision_revalidation.decision_expires_at
        ):
            blocked_reasons.append("human_consumption_decision_binding_mismatch")

        package_message = self._message_repository.get_by_id(
            consumption.source_package_message_id
        )
        package_action = self._exact_action(
            message=package_message,
            session_id=session_id,
            source_task_id=source_task_id,
            source_project_id=source_project_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="sandbox_candidate_diff_review_human_escalation_package",
            source_detail=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_SOURCE_DETAIL,
            action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_PACKAGE_ACTION_TYPE,
            schema_version=HUMAN_ESCALATION_PACKAGE_SCHEMA_VERSION,
            expected_requires_confirmation=True,
            blocked_reason="source_human_package_invalid",
            blocked_reasons=blocked_reasons,
        )
        if package_action is None:
            return None
        try:
            package = self._domain_from_action(
                ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageResult,
                package_action,
            )
        except ValidationError:
            blocked_reasons.append("source_human_package_domain_invalid")
            return None
        if package.package_status != "prepared":
            blocked_reasons.append("source_human_package_domain_invalid")
            return None
        package_revalidation = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationPackageService.revalidate_persisted_human_escalation_package_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_package_message_id=consumption.source_package_message_id,
            source_package_action=package_action,
        )
        blocked_reasons.extend(package_revalidation.blocked_reasons)
        aggregate_fingerprints = (
            package.aggregate_evidence_fingerprint,
            package_revalidation.aggregate_evidence_fingerprint,
            consumption.aggregate_evidence_fingerprint,
        )
        if len(set(aggregate_fingerprints)) != 1:
            blocked_reasons.append("aggregate_evidence_fingerprint_mismatch")
        if (
            package.escalation_package_id != consumption.escalation_package_id
            or package.source_review_message_id is None
            or package.source_diff_message_id is None
        ):
            blocked_reasons.append("human_consumption_package_binding_mismatch")
        review_material = self._review_material_from_action(
            package_action,
            blocked_reasons,
        )
        if blocked_reasons or review_material is None:
            return None
        return _TransitionEvidence(
            authority="HUMAN_ESCALATION_DECISION",
            transition_kind=expected_transition,
            source_transition_record_id=consumption.consumption_id,
            source_review_message_id=package.source_review_message_id,
            source_review_preflight_message_id=package.source_preflight_message_id,
            source_diff_message_id=package.source_diff_message_id,
            review_result_fingerprint=package.review_result_fingerprint,
            reviewed_diff_sha256=package_action["source_diff_sha256"],
            reviewed_scope_paths=list(package_action["review_scope_paths"]),
            review_prompt_sha256=review_material[0],
            review_output_schema_version=review_material[1],
            source_review_verdict=review_material[2],
            source_review_risk_level=review_material[3],
            requested_reviewer_executor=review_material[4],
            source_human_consumption_message_id=source_message.id,
            human_consumption_id=consumption.consumption_id,
            source_decision_message_id=consumption.source_decision_message_id,
            decision_id=consumption.decision_id,
            source_package_message_id=consumption.source_package_message_id,
            escalation_package_id=consumption.escalation_package_id,
            decision_action=consumption.decision_action,
            decision_expires_at=consumption.decision_expires_at,
            aggregate_evidence_fingerprint=package.aggregate_evidence_fingerprint,
            revalidated_aggregate_evidence_fingerprint=(
                package_revalidation.aggregate_evidence_fingerprint
            ),
            decision_confirmation_fingerprint=consumption.decision_confirmation_fingerprint,
            revalidated_decision_confirmation_fingerprint=(
                decision_revalidation.decision_confirmation_fingerprint
            ),
            decision_consumption_evidence_fingerprint=(
                consumption.consumption_evidence_fingerprint
            ),
            revalidated_decision_consumption_evidence_fingerprint=(
                consumption_revalidation.consumption_evidence_fingerprint
            ),
        )

    def _scan_history(
        self,
        *,
        session_id: UUID,
        source_project_id: UUID | None,
        source_transition_message: ProjectDirectorMessage,
        evidence: _TransitionEvidence,
        blocked_reasons: list[str],
    ) -> _FreshnessHistory:
        prior_freshness = False
        decision_consumption_count = 0
        decision_revoked_after_consumption = False
        before_message_id: UUID | None = None
        while True:
            messages, has_more = self._message_repository.list_by_session_id(
                session_id=session_id,
                limit=100,
                before_message_id=before_message_id,
            )
            for message in messages:
                if message.source_detail == P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL:
                    freshness = self._trusted_freshness(
                        message=message,
                        source_project_id=source_project_id,
                    )
                    if freshness is None:
                        blocked_reasons.append(
                            "prior_protected_transition_freshness_record_invalid"
                        )
                    elif (
                        freshness.source_transition_message_id
                        == source_transition_message.id
                        or freshness.source_transition_record_id
                        == evidence.source_transition_record_id
                        or freshness.source_review_message_id
                        == evidence.source_review_message_id
                    ):
                        prior_freshness = True
                if evidence.authority != "HUMAN_ESCALATION_DECISION":
                    continue
                if message.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_SOURCE_DETAIL:
                    consumption = self._trusted_human_consumption(
                        message=message,
                        source_project_id=source_project_id,
                    )
                    if consumption is None:
                        blocked_reasons.append(
                            "prior_human_escalation_decision_consumption_record_invalid"
                        )
                    elif (
                        consumption.source_decision_message_id
                        == evidence.source_decision_message_id
                        or consumption.decision_id == evidence.decision_id
                    ):
                        decision_consumption_count += 1
                elif message.source_detail == P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_SOURCE_DETAIL:
                    revocation = self._trusted_revocation(
                        message=message,
                        source_project_id=source_project_id,
                    )
                    if revocation is None:
                        blocked_reasons.append(
                            "prior_human_escalation_decision_revocation_record_invalid"
                        )
                    elif (
                        (
                            revocation.source_decision_message_id
                            == evidence.source_decision_message_id
                            or revocation.decision_id == evidence.decision_id
                        )
                        and message.sequence_no > source_transition_message.sequence_no
                    ):
                        decision_revoked_after_consumption = True
            if not has_more or not messages:
                break
            before_message_id = messages[0].id
        blocked_reasons[:] = self._dedupe(blocked_reasons)
        return _FreshnessHistory(
            prior_freshness_validation_detected=prior_freshness,
            decision_consumption_count=decision_consumption_count,
            decision_revoked_after_consumption=decision_revoked_after_consumption,
        )

    @classmethod
    def _trusted_freshness(
        cls,
        *,
        message: ProjectDirectorMessage,
        source_project_id: UUID | None,
    ) -> ProjectDirectorProtectedTransitionEvidenceFreshnessResult | None:
        action = cls._trusted_action(
            message=message,
            source_project_id=source_project_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="protected_transition_evidence_freshness",
            action_type=P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE,
            schema_version=PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION,
        )
        if action is None:
            return None
        try:
            result = cls._domain_from_action(
                ProjectDirectorProtectedTransitionEvidenceFreshnessResult,
                action,
            )
        except ValidationError:
            return None
        revalidation = cls.revalidate_persisted_protected_transition_freshness_fingerprint(
            session_id=message.session_id,
            source_task_id=message.related_task_id,
            source_freshness_message_id=message.id,
            source_freshness_action=action,
        )
        if (
            revalidation.blocked_reasons
            or result.freshness_evidence_fingerprint
            != revalidation.freshness_evidence_fingerprint
        ):
            return None
        return result

    @classmethod
    def _trusted_human_consumption(
        cls,
        *,
        message: ProjectDirectorMessage,
        source_project_id: UUID | None,
    ) -> ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult | None:
        action = cls._trusted_action(
            message=message,
            source_project_id=source_project_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            intent="sandbox_candidate_diff_review_human_escalation_decision_consumption",
            action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_CONSUMPTION_ACTION_TYPE,
            schema_version=HUMAN_ESCALATION_DECISION_CONSUMPTION_SCHEMA_VERSION,
        )
        if action is None:
            return None
        try:
            result = cls._domain_from_action(
                ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionResult,
                action,
            )
        except ValidationError:
            return None
        revalidation = ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionConsumptionService.revalidate_persisted_human_escalation_decision_consumption_fingerprint(
            session_id=message.session_id,
            source_task_id=message.related_task_id,
            source_consumption_message_id=message.id,
            source_consumption_action=action,
        )
        if (
            revalidation.blocked_reasons
            or result.consumption_evidence_fingerprint
            != revalidation.consumption_evidence_fingerprint
        ):
            return None
        return result

    @classmethod
    def _trusted_revocation(
        cls,
        *,
        message: ProjectDirectorMessage,
        source_project_id: UUID | None,
    ) -> ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult | None:
        action = cls._trusted_action(
            message=message,
            source_project_id=source_project_id,
            role=ProjectDirectorMessageRole.USER,
            intent="sandbox_candidate_diff_review_human_escalation_decision_revocation",
            action_type=P21_D_SANDBOX_CANDIDATE_DIFF_REVIEW_HUMAN_ESCALATION_DECISION_REVOCATION_ACTION_TYPE,
            schema_version=HUMAN_ESCALATION_DECISION_REVOCATION_SCHEMA_VERSION,
        )
        if action is None:
            return None
        try:
            result = cls._domain_from_action(
                ProjectDirectorSandboxCandidateDiffReviewHumanEscalationDecisionRevocationResult,
                action,
            )
        except ValidationError:
            return None
        return result if result.revocation_status == "revoked" else None

    @staticmethod
    def _review_message_metadata_valid(
        *,
        message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        source_project_id: UUID | None,
    ) -> bool:
        from app.services.project_director_bounded_rework_review_execution_service import (
            P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
        )

        return bool(
            message is not None
            and message.session_id == session_id
            and message.related_project_id == source_project_id
            and message.related_task_id == source_task_id
            and message.role == ProjectDirectorMessageRole.ASSISTANT
            and message.source == ProjectDirectorMessageSource.SYSTEM
            and message.intent
            in (
                "sandbox_candidate_diff_readonly_review_execution",
                P25_BOUNDED_REWORK_REVIEW_OUTCOME_INTENT,
            )
            and message.requires_confirmation is False
            and message.risk_level == ProjectDirectorMessageRiskLevel.HIGH
        )

    @staticmethod
    def _review_binding_matches(
        evidence: _TransitionEvidence,
        revalidation: RevalidatedPersistedReviewResultFingerprint,
    ) -> bool:
        return (
            revalidation.source_diff_message_id == evidence.source_diff_message_id
            and revalidation.source_preflight_message_id
            == evidence.source_review_preflight_message_id
            and revalidation.requested_reviewer_executor in _VALID_REVIEWER_EXECUTORS
            and (
                not evidence.requested_reviewer_executor
                or revalidation.requested_reviewer_executor
                == evidence.requested_reviewer_executor
            )
            and revalidation.source_diff_sha256 == evidence.reviewed_diff_sha256
            and revalidation.review_prompt_sha256 == evidence.review_prompt_sha256
            and (revalidation.review_scope_paths or []) == evidence.reviewed_scope_paths
            and revalidation.review_output_schema_version
            == evidence.review_output_schema_version
            and revalidation.verdict == evidence.source_review_verdict
            and revalidation.risk_level == evidence.source_review_risk_level
        )

    @staticmethod
    def _review_material_from_action(
        action: dict[str, Any],
        blocked_reasons: list[str],
        *,
        require_executor: bool = True,
    ) -> tuple[str, str, str, str, str] | None:
        review_prompt_sha256 = action.get("review_prompt_sha256")
        review_output_schema_version = action.get("review_output_schema_version")
        source_review_verdict = action.get("source_review_verdict")
        source_review_risk_level = action.get("source_review_risk_level")
        requested_reviewer_executor = action.get("requested_reviewer_executor")
        if (
            not ProjectDirectorProtectedTransitionEvidenceFreshnessService._is_sha256(
                review_prompt_sha256
            )
            or review_output_schema_version != REVIEW_OUTPUT_SCHEMA_VERSION
            or source_review_verdict not in _VALID_REVIEW_VERDICTS
            or source_review_risk_level not in _VALID_REVIEW_RISK_LEVELS
            or (
                require_executor
                and requested_reviewer_executor not in _VALID_REVIEWER_EXECUTORS
            )
        ):
            blocked_reasons.append("source_review_binding_material_invalid")
            return None
        return (
            review_prompt_sha256,
            review_output_schema_version,
            source_review_verdict,
            source_review_risk_level,
            requested_reviewer_executor if require_executor else "",
        )

    @staticmethod
    def _exact_action(
        *,
        message: ProjectDirectorMessage | None,
        session_id: UUID,
        source_task_id: UUID,
        source_project_id: UUID | None,
        role: ProjectDirectorMessageRole,
        intent: str,
        source_detail: str,
        action_type: str,
        schema_version: str,
        expected_requires_confirmation: bool,
        blocked_reason: str,
        blocked_reasons: list[str],
    ) -> dict[str, Any] | None:
        if (
            message is None
            or message.session_id != session_id
            or message.related_project_id != source_project_id
            or message.related_task_id != source_task_id
            or message.role != role
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != intent
            or message.source_detail != source_detail
            or message.requires_confirmation is not expected_requires_confirmation
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(message.suggested_actions) != 1
        ):
            blocked_reasons.append(blocked_reason)
            return None
        action = message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type") != action_type
            or action.get("schema_version") != schema_version
            or action.get("session_id") != str(session_id)
            or action.get("source_task_id") != str(source_task_id)
        ):
            blocked_reasons.append(blocked_reason)
            return None
        return action

    @staticmethod
    def _trusted_action(
        *,
        message: ProjectDirectorMessage,
        source_project_id: UUID | None,
        role: ProjectDirectorMessageRole,
        intent: str,
        action_type: str,
        schema_version: str,
    ) -> dict[str, Any] | None:
        if (
            message.related_project_id != source_project_id
            or message.related_task_id is None
            or message.role != role
            or message.source != ProjectDirectorMessageSource.SYSTEM
            or message.intent != intent
            or message.requires_confirmation is not False
            or message.risk_level != ProjectDirectorMessageRiskLevel.HIGH
            or len(message.suggested_actions) != 1
        ):
            return None
        action = message.suggested_actions[0]
        if (
            not isinstance(action, dict)
            or action.get("type") != action_type
            or action.get("schema_version") != schema_version
            or action.get("session_id") != str(message.session_id)
            or action.get("source_task_id") != str(message.related_task_id)
        ):
            return None
        return action

    @staticmethod
    def _domain_from_action(model: type[Any], action: dict[str, Any]) -> Any:
        return model.model_validate(
            {field_name: action.get(field_name) for field_name in model.model_fields}
        )

    @staticmethod
    def _ready_result_values(
        *,
        freshness_validation_id: UUID,
        source_message_id: UUID,
        source_task_id: UUID,
        validated_at: datetime,
        evidence: _TransitionEvidence,
        history: _FreshnessHistory,
        revalidated_review_fingerprint: str,
        persisted_source_diff_sha256: str,
        persisted_source_scope_paths: list[str],
        current_diff_sha256: str,
        current_scope_paths: list[str],
        workspace_path: str,
    ) -> dict[str, Any]:
        human = evidence.authority == "HUMAN_ESCALATION_DECISION"
        return {
            "freshness_status": "ready",
            "freshness_validation_id": freshness_validation_id,
            "source_transition_message_id": source_message_id,
            "source_transition_record_id": evidence.source_transition_record_id,
            "source_task_id": source_task_id,
            "transition_authority": evidence.authority,
            "transition_kind": evidence.transition_kind,
            "validated_at": validated_at,
            "source_handoff_message_id": evidence.source_handoff_message_id,
            "handoff_id": evidence.handoff_id,
            "source_disposition_consumption_message_id": evidence.source_disposition_consumption_message_id,
            "disposition_consumption_id": evidence.disposition_consumption_id,
            "source_disposition_message_id": evidence.source_disposition_message_id,
            "disposition_id": evidence.disposition_id,
            "disposition_type": evidence.disposition_type,
            "source_human_consumption_message_id": evidence.source_human_consumption_message_id,
            "human_consumption_id": evidence.human_consumption_id,
            "source_decision_message_id": evidence.source_decision_message_id,
            "decision_id": evidence.decision_id,
            "source_package_message_id": evidence.source_package_message_id,
            "escalation_package_id": evidence.escalation_package_id,
            "decision_action": evidence.decision_action,
            "decision_expires_at": evidence.decision_expires_at,
            "source_review_message_id": evidence.source_review_message_id,
            "source_diff_message_id": evidence.source_diff_message_id,
            "review_result_fingerprint": evidence.review_result_fingerprint,
            "revalidated_review_result_fingerprint": revalidated_review_fingerprint,
            "reviewed_diff_sha256": evidence.reviewed_diff_sha256,
            "persisted_source_diff_sha256": persisted_source_diff_sha256,
            "current_diff_sha256": current_diff_sha256,
            "reviewed_scope_paths": list(evidence.reviewed_scope_paths),
            "persisted_source_scope_paths": list(persisted_source_scope_paths),
            "current_scope_paths": list(current_scope_paths),
            "workspace_path": workspace_path,
            "workspace_path_within_root": True,
            "aggregate_evidence_fingerprint": evidence.aggregate_evidence_fingerprint,
            "revalidated_aggregate_evidence_fingerprint": evidence.revalidated_aggregate_evidence_fingerprint,
            "decision_confirmation_fingerprint": evidence.decision_confirmation_fingerprint,
            "revalidated_decision_confirmation_fingerprint": evidence.revalidated_decision_confirmation_fingerprint,
            "decision_consumption_evidence_fingerprint": evidence.decision_consumption_evidence_fingerprint,
            "revalidated_decision_consumption_evidence_fingerprint": evidence.revalidated_decision_consumption_evidence_fingerprint,
            "source_transition_validated": True,
            "source_review_validated": True,
            "review_result_fingerprint_revalidated": True,
            "source_diff_revalidated": True,
            "current_workspace_revalidated": True,
            "current_diff_regenerated": True,
            "ordered_scope_revalidated": True,
            "aggregate_evidence_fingerprint_revalidated": human,
            "decision_fingerprint_revalidated": human,
            "decision_consumption_fingerprint_revalidated": human,
            "decision_not_expired_at_freshness_check": human,
            "decision_not_revoked_after_consumption": human,
            "single_decision_consumption_validated": (
                human and history.decision_consumption_count == 1
            ),
            "evidence_fresh": True,
            "replay_check_completed": True,
            "prior_freshness_validation_detected": False,
            "continuation_guardrail_eligible": evidence.transition_kind == "CONTINUE_GUARDRAIL",
            "bounded_rework_guardrail_eligible": evidence.transition_kind == "BOUNDED_REWORK_GUARDRAIL",
            "gate_allows_protected_transition_guardrail": True,
            "gate_allows_write": False,
        }

    @staticmethod
    def _blocked_result(
        *,
        source_message_id: UUID,
        source_task_id: UUID,
        validated_at: datetime | None,
        evidence: _TransitionEvidence | None,
        history: _FreshnessHistory,
        revalidated_review_fingerprint: str,
        persisted_source_diff_sha256: str,
        persisted_source_scope_paths: list[str],
        current_diff_sha256: str,
        current_scope_paths: list[str],
        workspace_path: str,
        workspace_path_within_root: bool,
        source_review_validated: bool,
        review_fingerprint_revalidated: bool,
        source_diff_revalidated: bool,
        current_workspace_revalidated: bool,
        current_diff_regenerated: bool,
        ordered_scope_revalidated: bool,
        replay_check_completed: bool,
        blocked_reasons: list[str],
    ) -> PreparedProjectDirectorProtectedTransitionEvidenceFreshness:
        return PreparedProjectDirectorProtectedTransitionEvidenceFreshness(
            result=ProjectDirectorProtectedTransitionEvidenceFreshnessResult(
                freshness_status="blocked",
                source_transition_message_id=source_message_id,
                source_transition_record_id=(
                    evidence.source_transition_record_id if evidence else None
                ),
                source_task_id=source_task_id,
                transition_authority=evidence.authority if evidence else None,
                transition_kind=evidence.transition_kind if evidence else None,
                validated_at=validated_at,
                source_handoff_message_id=evidence.source_handoff_message_id if evidence else None,
                handoff_id=evidence.handoff_id if evidence else None,
                source_disposition_consumption_message_id=(
                    evidence.source_disposition_consumption_message_id if evidence else None
                ),
                disposition_consumption_id=evidence.disposition_consumption_id if evidence else None,
                source_disposition_message_id=evidence.source_disposition_message_id if evidence else None,
                disposition_id=evidence.disposition_id if evidence else None,
                disposition_type=evidence.disposition_type if evidence else None,
                source_human_consumption_message_id=evidence.source_human_consumption_message_id if evidence else None,
                human_consumption_id=evidence.human_consumption_id if evidence else None,
                source_decision_message_id=evidence.source_decision_message_id if evidence else None,
                decision_id=evidence.decision_id if evidence else None,
                source_package_message_id=evidence.source_package_message_id if evidence else None,
                escalation_package_id=evidence.escalation_package_id if evidence else None,
                decision_action=evidence.decision_action if evidence else None,
                decision_expires_at=evidence.decision_expires_at if evidence else None,
                source_review_message_id=evidence.source_review_message_id if evidence else None,
                source_diff_message_id=evidence.source_diff_message_id if evidence else None,
                review_result_fingerprint=evidence.review_result_fingerprint if evidence else "",
                revalidated_review_result_fingerprint=revalidated_review_fingerprint,
                reviewed_diff_sha256=evidence.reviewed_diff_sha256 if evidence else "",
                persisted_source_diff_sha256=persisted_source_diff_sha256,
                current_diff_sha256=current_diff_sha256,
                reviewed_scope_paths=list(evidence.reviewed_scope_paths) if evidence else [],
                persisted_source_scope_paths=list(persisted_source_scope_paths),
                current_scope_paths=list(current_scope_paths),
                workspace_path=workspace_path,
                workspace_path_within_root=workspace_path_within_root,
                aggregate_evidence_fingerprint=evidence.aggregate_evidence_fingerprint if evidence else "",
                revalidated_aggregate_evidence_fingerprint=evidence.revalidated_aggregate_evidence_fingerprint if evidence else "",
                decision_confirmation_fingerprint=evidence.decision_confirmation_fingerprint if evidence else "",
                revalidated_decision_confirmation_fingerprint=evidence.revalidated_decision_confirmation_fingerprint if evidence else "",
                decision_consumption_evidence_fingerprint=evidence.decision_consumption_evidence_fingerprint if evidence else "",
                revalidated_decision_consumption_evidence_fingerprint=evidence.revalidated_decision_consumption_evidence_fingerprint if evidence else "",
                source_transition_validated=evidence is not None,
                source_review_validated=source_review_validated,
                review_result_fingerprint_revalidated=review_fingerprint_revalidated,
                source_diff_revalidated=source_diff_revalidated,
                current_workspace_revalidated=current_workspace_revalidated,
                current_diff_regenerated=current_diff_regenerated,
                ordered_scope_revalidated=ordered_scope_revalidated,
                aggregate_evidence_fingerprint_revalidated=(
                    evidence is not None
                    and evidence.authority == "HUMAN_ESCALATION_DECISION"
                    and bool(evidence.revalidated_aggregate_evidence_fingerprint)
                ),
                decision_fingerprint_revalidated=(
                    evidence is not None
                    and evidence.authority == "HUMAN_ESCALATION_DECISION"
                    and bool(evidence.revalidated_decision_confirmation_fingerprint)
                ),
                decision_consumption_fingerprint_revalidated=(
                    evidence is not None
                    and evidence.authority == "HUMAN_ESCALATION_DECISION"
                    and bool(evidence.revalidated_decision_consumption_evidence_fingerprint)
                ),
                decision_not_expired_at_freshness_check=False,
                decision_not_revoked_after_consumption=False,
                single_decision_consumption_validated=False,
                replay_check_completed=replay_check_completed,
                prior_freshness_validation_detected=history.prior_freshness_validation_detected,
                blocked_reasons=ProjectDirectorProtectedTransitionEvidenceFreshnessService._dedupe(blocked_reasons),
            ),
            message=None,
        )

    @staticmethod
    def _freshness_evidence_canonical_payload(
        *,
        session_id: UUID,
        result: ProjectDirectorProtectedTransitionEvidenceFreshnessResult,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "schema_version": PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION,
            "session_id": str(session_id),
            "source_task_id": str(result.source_task_id),
            "freshness_validation_id": str(result.freshness_validation_id),
            "source_transition_message_id": str(result.source_transition_message_id),
            "source_transition_record_id": str(result.source_transition_record_id),
            "transition_authority": result.transition_authority,
            "transition_kind": result.transition_kind,
            "source_review_message_id": str(result.source_review_message_id),
            "source_diff_message_id": str(result.source_diff_message_id),
            "review_result_fingerprint": result.review_result_fingerprint,
            "revalidated_review_result_fingerprint": result.revalidated_review_result_fingerprint,
            "reviewed_diff_sha256": result.reviewed_diff_sha256,
            "persisted_source_diff_sha256": result.persisted_source_diff_sha256,
            "current_diff_sha256": result.current_diff_sha256,
            "reviewed_scope_paths": list(result.reviewed_scope_paths),
            "persisted_source_scope_paths": list(result.persisted_source_scope_paths),
            "current_scope_paths": list(result.current_scope_paths),
            "workspace_path": result.workspace_path,
            "validated_at": result.validated_at.isoformat(),
        }
        if result.transition_authority == "HUMAN_ESCALATION_DECISION":
            payload.update(
                {
                    "source_decision_message_id": str(result.source_decision_message_id),
                    "decision_id": str(result.decision_id),
                    "source_package_message_id": str(result.source_package_message_id),
                    "escalation_package_id": str(result.escalation_package_id),
                    "decision_action": result.decision_action,
                    "decision_expires_at": result.decision_expires_at.isoformat(),
                    "aggregate_evidence_fingerprint": result.aggregate_evidence_fingerprint,
                    "decision_confirmation_fingerprint": result.decision_confirmation_fingerprint,
                    "decision_consumption_evidence_fingerprint": result.decision_consumption_evidence_fingerprint,
                }
            )
        return payload

    @staticmethod
    def _canonical_payload_fingerprint(payload: dict[str, Any]) -> str:
        canonical_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    def _freshness_action(
        *,
        session_id: UUID,
        source_task_id: UUID,
        result: ProjectDirectorProtectedTransitionEvidenceFreshnessResult,
    ) -> dict[str, Any]:
        payload = result.model_dump(mode="json")
        payload.update(
            {
                "type": P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE,
                "schema_version": PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION,
                "session_id": str(session_id),
                "source_task_id": str(source_task_id),
            }
        )
        return payload

    @staticmethod
    def _forbidden_actions() -> list[str]:
        return [
            "no_continuation_start",
            "no_rework_start",
            "no_task_creation",
            "no_run_creation",
            "no_worker_dispatch",
            "no_worktree_creation",
            "no_workspace_write",
            "no_main_project_file_write",
            "no_manifest_write",
            "no_diff_file_write",
            "no_patch_apply",
            "no_product_runtime_git_write",
            "no_pr_creation",
            "no_merge",
            "no_ci_trigger",
            "no_legacy_approval_request",
            "no_legacy_approval_decision",
        ]

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
        return (
            isinstance(value, str)
            and len(value) == 64
            and all(character in "0123456789abcdef" for character in value)
        )

    @staticmethod
    def _timezone_aware_datetime(value: Any) -> bool:
        return (
            isinstance(value, datetime)
            and value.tzinfo is not None
            and value.utcoffset() is not None
        )

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
    "P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_ACTION_TYPE",
    "P21_D_PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SOURCE_DETAIL",
    "PROTECTED_TRANSITION_EVIDENCE_FRESHNESS_SCHEMA_VERSION",
    "PreparedProjectDirectorProtectedTransitionEvidenceFreshness",
    "ProjectDirectorProtectedTransitionEvidenceFreshnessService",
    "RevalidatedCurrentProtectedTransitionEvidenceFreshness",
    "RevalidatedPersistedProtectedTransitionFreshnessFingerprint",
)
