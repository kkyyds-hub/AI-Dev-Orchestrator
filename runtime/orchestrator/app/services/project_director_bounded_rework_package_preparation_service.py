"""Atomic P25 bounded rework instruction-package preparation service."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain._base import utc_now
from app.domain.project_director_bounded_rework_attempt_reservation import (
    BOUNDED_REWORK_ATTEMPT_RESERVATION_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkAttemptReservation,
)
from app.domain.project_director_bounded_rework_contract import (
    BoundedReworkBlockedReason,
    P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
    P25_BOUNDED_REWORK_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkAuthorityEnvelope,
    ProjectDirectorBoundedReworkCorrection,
    ProjectDirectorBoundedReworkFinding,
    path_is_within_scope,
    paths_overlap,
)
from app.domain.project_director_bounded_rework_instruction_package import (
    ProjectDirectorBoundedReworkInstructionPackage,
)
from app.domain.project_director_bounded_rework_invocation_claim import (
    BOUNDED_REWORK_INVOCATION_CLAIM_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkInvocationClaim,
)
from app.domain.project_director_bounded_rework_invocation_outcome import (
    BOUNDED_REWORK_INVOCATION_OUTCOME_SCHEMA_VERSION,
    ProjectDirectorBoundedReworkInvocationOutcome,
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
from app.services.project_director_bounded_rework_evidence_resolver import (
    ProjectDirectorBoundedReworkEvidenceResolver,
    ProjectDirectorBoundedReworkEvidenceSnapshot,
)
from app.services.project_director_protected_transition_dispatch_consumption_service import (
    ProjectDirectorProtectedTransitionDispatchConsumptionService,
)
from app.services.project_director_protected_transition_dispatch_intent_service import (
    ProjectDirectorProtectedTransitionDispatchIntentService,
)
from app.services.project_director_sandbox_candidate_diff_review_disposition_service import (
    ProjectDirectorSandboxCandidateDiffReviewDispositionService,
)


P25_BOUNDED_REWORK_PACKAGE_SOURCE_DETAIL = (
    "p25_bounded_rework_instruction_package_prepared"
)
P25_BOUNDED_REWORK_PACKAGE_ACTION_TYPE = (
    "p25_bounded_rework_instruction_package_record"
)
P25_BOUNDED_REWORK_PACKAGE_INTENT = "bounded_rework_instruction_package"

_PAGE_SIZE = 200
_P25_SCHEMA_PREFIX = "p25-b"
_PACKAGE_SCHEMA_VERSION = P25_BOUNDED_REWORK_SCHEMA_VERSION
_FORMAL_FALSE_BOUNDARIES = (
    "product_runtime_git_write_allowed=false",
    "main_project_write_allowed=false",
    "automatic_pr_allowed=false",
    "automatic_merge_allowed=false",
    "git_add_allowed=false",
    "git_commit_allowed=false",
    "git_push_allowed=false",
    "branch_operation_allowed=false",
    "ci_trigger_allowed=false",
)

PreparationStatus = Literal["package_prepared", "package_replayed", "blocked"]


@dataclass(frozen=True, slots=True)
class PreparedProjectDirectorBoundedReworkInstructionPackage:
    status: PreparationStatus
    package: ProjectDirectorBoundedReworkInstructionPackage
    message: ProjectDirectorMessage | None
    blocked_reasons: tuple[BoundedReworkBlockedReason, ...]


@dataclass(frozen=True, slots=True)
class _AuthorityContext:
    authority: ProjectDirectorBoundedReworkAuthorityEnvelope
    source_freshness_message_id: UUID
    source_diff_message_id: UUID
    rework_attempt_index: int
    rework_attempt_limit: int


@dataclass(frozen=True, slots=True)
class _History:
    packages: tuple[
        tuple[ProjectDirectorMessage, ProjectDirectorBoundedReworkInstructionPackage],
        ...,
    ]
    reservations: tuple[ProjectDirectorBoundedReworkAttemptReservation, ...]
    claims: tuple[ProjectDirectorBoundedReworkInvocationClaim, ...]
    outcomes: tuple[ProjectDirectorBoundedReworkInvocationOutcome, ...]


@dataclass(frozen=True, slots=True)
class _AttemptLineage:
    rework_attempt_index: int
    previous_attempt_id: UUID | None = None
    previous_outcome_id: UUID | None = None
    previous_rework_attempt_index: int | None = None
    previous_candidate_diff_sha256: str | None = None
    previous_review_semantic_fingerprint: str | None = None


class _Blocked(RuntimeError):
    def __init__(self, reason: BoundedReworkBlockedReason) -> None:
        self.reason = reason
        super().__init__(reason)


class ProjectDirectorBoundedReworkPackagePreparationService:
    """Prepare or replay one P25 package without reserving or executing work."""

    def __init__(
        self,
        *,
        message_repository: ProjectDirectorMessageRepository,
        dispatch_consumption_service: (
            ProjectDirectorProtectedTransitionDispatchConsumptionService
        ),
        dispatch_intent_service: ProjectDirectorProtectedTransitionDispatchIntentService,
        evidence_resolver: ProjectDirectorBoundedReworkEvidenceResolver,
    ) -> None:
        self._message_repository = message_repository
        self._dispatch_consumption_service = dispatch_consumption_service
        self._dispatch_intent_service = dispatch_intent_service
        self._evidence_resolver = evidence_resolver
        self._require_shared_message_repository()

    def prepare_bounded_rework_instruction_package(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_p23_dispatch_consumption_message_id: UUID,
    ) -> PreparedProjectDirectorBoundedReworkInstructionPackage:
        """Prepare from three locators; all semantic authority is reconstructed."""

        try:
            initial_authority = self._revalidate_authority(
                session_id=session_id,
                source_task_id=source_task_id,
                source_consumption_message_id=(
                    source_p23_dispatch_consumption_message_id
                ),
            )
            initial_evidence_resolution = (
                self._evidence_resolver.resolve_bounded_rework_evidence_snapshot(
                    session_id=session_id,
                    project_id=initial_authority.authority.project_id,
                    source_task_id=source_task_id,
                    source_run_id=initial_authority.authority.source_run_id,
                    source_review_message_id=(
                        initial_authority.authority.source_review_message_id
                    ),
                    source_review_fingerprint=(
                        initial_authority.authority.source_review_fingerprint
                    ),
                    source_review_semantic_fingerprint=(
                        initial_authority.authority.source_review_semantic_fingerprint
                    ),
                    source_freshness_message_id=(
                        initial_authority.source_freshness_message_id
                    ),
                    source_diff_message_id=initial_authority.source_diff_message_id,
                )
            )
            initial_evidence = initial_evidence_resolution.snapshot
            if (
                initial_evidence is None
                or initial_evidence_resolution.blocked_reasons
            ):
                raise _Blocked(
                    self._map_evidence_reason(
                        initial_evidence_resolution.blocked_reasons
                    )
                )

            with self._message_repository.sqlite_immediate_transaction():
                history = self._load_history(session_id)
                authority = self._revalidate_authority(
                    session_id=session_id,
                    source_task_id=source_task_id,
                    source_consumption_message_id=(
                        source_p23_dispatch_consumption_message_id
                    ),
                )
                if authority != initial_authority:
                    raise _Blocked("authority_invalid")
                evidence_resolution = (
                    self._evidence_resolver.revalidate_bounded_rework_evidence_snapshot(
                        initial_evidence
                    )
                )
                evidence = evidence_resolution.snapshot
                if evidence is None or evidence_resolution.blocked_reasons:
                    raise _Blocked(
                        self._map_evidence_reason(evidence_resolution.blocked_reasons)
                    )
                return self._prepare_or_replay(
                    history=history,
                    authority_context=authority,
                    evidence=evidence,
                )
        except _Blocked as exc:
            return self._blocked_result(exc.reason)
        except SQLAlchemyError:
            return self._blocked_result("persistence_failed")
        except (OSError, RuntimeError, TypeError, ValueError, ValidationError):
            return self._blocked_result("history_invalid")

    def _revalidate_authority(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_consumption_message_id: UUID,
    ) -> _AuthorityContext:
        consumption_revalidation = self._dispatch_consumption_service.revalidate_persisted_protected_transition_dispatch_consumption(
            session_id=session_id,
            source_task_id=source_task_id,
            source_consumption_message_id=source_consumption_message_id,
        )
        consumption = consumption_revalidation.result
        consumption_message = consumption_revalidation.message
        run = consumption_revalidation.run
        if (
            consumption is not None
            and consumption.product_runtime_git_write_allowed is not False
        ):
            raise _Blocked("git_boundary_violation")
        if (
            consumption_revalidation.blocked_reasons
            or consumption is None
            or consumption_message is None
            or run is None
            or consumption_message.id != source_consumption_message_id
            or consumption.consumption_id != source_consumption_message_id
            or consumption.consumption_status != "reserved_for_worker_start"
            or consumption.dispatch_intent_consumed is not True
            or consumption.disposition_type != "AUTO_REWORK"
            or consumption.dispatch_kind != "auto_rework"
            or consumption.target_task_strategy != "source_task_rework"
            or consumption.target_task_id != source_task_id
            or consumption.source_task_id != source_task_id
            or consumption.project_id is None
            or consumption.run_id != run.id
            or consumption.product_runtime_git_write_allowed is not False
            or consumption.source_intent_message_id is None
            or consumption.source_dispatch_intent_id is None
            or consumption.source_p22_summary_message_id is None
            or consumption.source_review_message_id is None
            or consumption.source_freshness_message_id is None
        ):
            raise _Blocked("authority_invalid")

        intent_revalidation = self._dispatch_intent_service.revalidate_persisted_protected_transition_dispatch_intent(
            session_id=session_id,
            source_task_id=source_task_id,
            source_intent_message_id=consumption.source_intent_message_id,
        )
        intent = intent_revalidation.result
        intent_message = intent_revalidation.message
        if (
            intent is not None
            and intent.product_runtime_git_write_allowed is not False
        ):
            raise _Blocked("git_boundary_violation")
        if (
            intent_revalidation.blocked_reasons
            or intent is None
            or intent_message is None
            or intent.intent_status != "prepared"
            or intent.dispatch_intent_id != intent_message.id
            or intent.dispatch_intent_id != consumption.source_dispatch_intent_id
            or intent.dispatch_intent_fingerprint
            != consumption.source_dispatch_intent_fingerprint
            or intent.source_p22_summary_message_id
            != consumption.source_p22_summary_message_id
            or intent.source_review_message_id != consumption.source_review_message_id
            or intent.source_freshness_message_id
            != consumption.source_freshness_message_id
            or intent.disposition_type != "AUTO_REWORK"
            or intent.dispatch_kind != "auto_rework"
            or intent.target_task_strategy != "source_task_rework"
            or intent.target_task_id != source_task_id
            or intent.transition_kind != "BOUNDED_REWORK_GUARDRAIL"
            or intent.transition_authority != "AUTOMATED_DISPOSITION"
            or intent.review_result_fingerprint
            != consumption.review_result_fingerprint
            or intent.review_semantic_fingerprint
            != consumption.review_semantic_fingerprint
            or intent.source_diff_sha256 != consumption.source_diff_sha256
            or intent.review_scope_paths != consumption.review_scope_paths
            or intent.rework_attempt_index != consumption.rework_attempt_index
            or intent.rework_attempt_limit != consumption.rework_attempt_limit
            or intent.product_runtime_git_write_allowed is not False
            or intent.source_disposition_message_id is None
        ):
            raise _Blocked("authority_invalid")
        if (
            intent.rework_attempt_limit != P25_BOUNDED_REWORK_ATTEMPT_LIMIT
            or intent.rework_attempt_index >= P25_BOUNDED_REWORK_ATTEMPT_LIMIT
        ):
            raise _Blocked("attempt_limit_exhausted")

        review_message = self._message_repository.get_by_id(
            intent.source_review_message_id
        )
        review_revalidation = ProjectDirectorSandboxCandidateDiffReviewDispositionService.revalidate_persisted_review_result_fingerprint(
            session_id=session_id,
            source_task_id=source_task_id,
            source_review_message_id=intent.source_review_message_id,
            source_review_message=review_message,
        )
        if (
            review_revalidation.blocked_reasons
            or review_revalidation.source_diff_message_id is None
            or review_revalidation.review_result_fingerprint
            != intent.review_result_fingerprint
            or review_revalidation.source_diff_sha256 != intent.source_diff_sha256
            or tuple(review_revalidation.review_scope_paths or ())
            != tuple(intent.review_scope_paths)
            or review_revalidation.verdict != "changes_required"
        ):
            raise _Blocked("authority_invalid")

        try:
            authority = ProjectDirectorBoundedReworkAuthorityEnvelope(
                session_id=session_id,
                project_id=consumption.project_id,
                source_task_id=source_task_id,
                target_task_id=source_task_id,
                source_run_id=run.id,
                source_review_message_id=intent.source_review_message_id,
                source_review_fingerprint=intent.review_result_fingerprint,
                source_review_semantic_fingerprint=(
                    intent.review_semantic_fingerprint
                ),
                source_disposition_message_id=(
                    intent.source_disposition_message_id
                ),
                source_p22_summary_message_id=(
                    intent.source_p22_summary_message_id
                ),
                source_p23_dispatch_intent_id=intent.dispatch_intent_id,
                source_p23_dispatch_intent_fingerprint=(
                    intent.dispatch_intent_fingerprint
                ),
                source_p23_dispatch_consumption_id=consumption.consumption_id,
                source_p23_dispatch_consumption_fingerprint=(
                    consumption.consumption_fingerprint
                ),
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("authority_invalid") from exc
        return _AuthorityContext(
            authority=authority,
            source_freshness_message_id=intent.source_freshness_message_id,
            source_diff_message_id=review_revalidation.source_diff_message_id,
            rework_attempt_index=intent.rework_attempt_index,
            rework_attempt_limit=intent.rework_attempt_limit,
        )

    def _prepare_or_replay(
        self,
        *,
        history: _History,
        authority_context: _AuthorityContext,
        evidence: ProjectDirectorBoundedReworkEvidenceSnapshot,
    ) -> PreparedProjectDirectorBoundedReworkInstructionPackage:
        authority = authority_context.authority
        if (
            evidence.session_id != authority.session_id
            or evidence.project_id != authority.project_id
            or evidence.source_task_id != authority.source_task_id
            or evidence.source_run_id != authority.source_run_id
            or evidence.source_review_message_id
            != authority.source_review_message_id
            or evidence.source_review_fingerprint
            != authority.source_review_fingerprint
            or evidence.source_review_semantic_fingerprint
            != authority.source_review_semantic_fingerprint
            or evidence.source_candidate_diff_message_id
            != authority_context.source_diff_message_id
        ):
            raise _Blocked("authority_invalid")

        allowed_scope = self._intersect_scope_sources(
            evidence.task_plan_allowed_paths,
            evidence.repository_allowed_paths,
            evidence.workspace_manifest_allowed_paths,
            evidence.review_scope_paths,
        )
        forbidden_scope = evidence.trusted_forbidden_paths
        if any(
            paths_overlap(allowed, forbidden)
            for allowed in allowed_scope
            for forbidden in forbidden_scope
        ):
            raise _Blocked("scope_invalid")
        findings, corrections = self._findings_and_corrections(
            evidence=evidence,
            allowed_scope=allowed_scope,
        )
        lineage = self._attempt_lineage(
            history=history,
            authority_context=authority_context,
            evidence=evidence,
        )
        package = self._build_package(
            package_id=uuid4(),
            created_at=utc_now(),
            authority=authority,
            evidence=evidence,
            allowed_scope=allowed_scope,
            forbidden_scope=forbidden_scope,
            findings=findings,
            corrections=corrections,
            lineage=lineage,
        )

        replay_matches = [
            item
            for item in history.packages
            if item[1].package_replay_key == package.package_replay_key
        ]
        if replay_matches:
            if len(replay_matches) != 1:
                raise _Blocked("history_invalid")
            message, existing = replay_matches[0]
            if self._semantic_package_payload(existing) != self._semantic_package_payload(
                package
            ):
                raise _Blocked("instruction_package_conflict")
            return PreparedProjectDirectorBoundedReworkInstructionPackage(
                status="package_replayed",
                package=existing,
                message=message,
                blocked_reasons=(),
            )

        authority_packages = [
            item
            for item in history.packages
            if item[1].authority is not None
            and item[1].authority.source_p23_dispatch_consumption_id
            == authority.source_p23_dispatch_consumption_id
        ]
        if authority_packages:
            raise _Blocked("authority_replayed")

        sequence_no = self._message_repository.get_next_sequence_no(
            session_id=authority.session_id
        )
        try:
            message = self._build_package_message(package, sequence_no)
            self._message_repository.create(message)
        except (TypeError, ValueError, ValidationError, SQLAlchemyError) as exc:
            raise _Blocked("persistence_failed") from exc
        return PreparedProjectDirectorBoundedReworkInstructionPackage(
            status="package_prepared",
            package=package,
            message=message,
            blocked_reasons=(),
        )

    @staticmethod
    def _intersect_scope_sources(
        *sources: tuple[str, ...],
    ) -> tuple[str, ...]:
        if not sources or any(not source for source in sources):
            raise _Blocked("scope_invalid")
        current = set(sources[0])
        for source in sources[1:]:
            next_scope: set[str] = set()
            for left in current:
                for right in source:
                    if path_is_within_scope(left, right):
                        next_scope.add(left)
                    elif path_is_within_scope(right, left):
                        next_scope.add(right)
            current = next_scope
            if not current:
                raise _Blocked("scope_invalid")
        ordered = sorted(current, key=lambda value: (len(PurePathParts(value)), value))
        minimal: list[str] = []
        for value in ordered:
            if not any(path_is_within_scope(value, existing) for existing in minimal):
                minimal.append(value)
        if not minimal:
            raise _Blocked("scope_invalid")
        return tuple(sorted(minimal))

    @staticmethod
    def _findings_and_corrections(
        *,
        evidence: ProjectDirectorBoundedReworkEvidenceSnapshot,
        allowed_scope: tuple[str, ...],
    ) -> tuple[
        tuple[ProjectDirectorBoundedReworkFinding, ...],
        tuple[ProjectDirectorBoundedReworkCorrection, ...],
    ]:
        blocking = tuple(
            item
            for item in evidence.review_output.findings
            if item.severity in {"medium", "high"}
        )
        if not blocking:
            raise _Blocked("review_findings_invalid")
        finding_ids = tuple(item.finding_id for item in blocking)
        if len(finding_ids) != len(set(finding_ids)):
            raise _Blocked("review_findings_invalid")
        findings: list[ProjectDirectorBoundedReworkFinding] = []
        corrections: list[ProjectDirectorBoundedReworkCorrection] = []
        correction_ids: set[str] = set()
        for item in blocking:
            evidence_paths = tuple(sorted(set(item.evidence_paths)))
            if (
                not evidence_paths
                or any(
                    not any(
                        path_is_within_scope(path, allowed)
                        for allowed in allowed_scope
                    )
                    for path in evidence_paths
                )
            ):
                raise _Blocked("review_findings_invalid")
            try:
                finding = ProjectDirectorBoundedReworkFinding(
                    finding_id=item.finding_id,
                    severity=item.severity,
                    title=item.title,
                    summary=item.summary,
                    evidence_paths=evidence_paths,
                    recommended_action=item.recommended_action,
                )
            except (TypeError, ValueError, ValidationError) as exc:
                raise _Blocked("review_findings_invalid") from exc
            correction_id = "correction-" + hashlib.sha256(
                item.finding_id.encode("utf-8")
            ).hexdigest()[:24]
            if correction_id in correction_ids:
                raise _Blocked("review_findings_invalid")
            correction_ids.add(correction_id)
            findings.append(finding)
            corrections.append(
                ProjectDirectorBoundedReworkCorrection(
                    correction_id=correction_id,
                    source_finding_id=item.finding_id,
                    instruction=item.recommended_action,
                )
            )
        return tuple(findings), tuple(corrections)

    @staticmethod
    def _attempt_lineage(
        *,
        history: _History,
        authority_context: _AuthorityContext,
        evidence: ProjectDirectorBoundedReworkEvidenceSnapshot,
    ) -> _AttemptLineage:
        index = authority_context.rework_attempt_index
        authority = authority_context.authority
        task_packages = [
            package
            for _, package in history.packages
            if package.package_status == "prepared"
            and package.authority is not None
            and package.authority.project_id == authority.project_id
            and package.authority.source_task_id == authority.source_task_id
            and package.authority.source_p23_dispatch_consumption_id
            != authority.source_p23_dispatch_consumption_id
        ]
        attempt_indexes = [
            package.rework_attempt_index for package in task_packages
        ]
        if any(value is None for value in attempt_indexes):
            raise _Blocked("history_invalid")
        if len(attempt_indexes) != len(set(attempt_indexes)):
            raise _Blocked("history_invalid")
        if index == 0:
            if task_packages:
                raise _Blocked("authority_replayed")
            return _AttemptLineage(rework_attempt_index=0)

        expected_previous_indexes = set(range(index))
        if set(attempt_indexes) != expected_previous_indexes:
            raise _Blocked("history_invalid")
        previous_packages = [
            package
            for package in task_packages
            if package.rework_attempt_index == index - 1
        ]
        if len(previous_packages) != 1:
            raise _Blocked("history_invalid")
        previous_package = previous_packages[0]
        reservations = [
            item
            for item in history.reservations
            if item.package_id == previous_package.package_id
        ]
        if len(reservations) != 1:
            raise _Blocked("history_invalid")
        reservation = reservations[0]
        claims = [
            item
            for item in history.claims
            if item.reservation_id == reservation.reservation_id
        ]
        if len(claims) != 1:
            raise _Blocked("claim_without_outcome")
        claim = claims[0]
        outcomes = [
            item for item in history.outcomes if item.claim_id == claim.claim_id
        ]
        if len(outcomes) != 1:
            raise _Blocked("claim_without_outcome")
        outcome = outcomes[0]
        if outcome.human_escalation_required:
            raise _Blocked("human_escalation_required")
        if outcome.git_activity_detected:
            raise _Blocked("git_boundary_violation")
        if (
            reservation.rework_attempt_index != index - 1
            or claim.rework_attempt_index != index - 1
            or outcome.rework_attempt_index != index - 1
            or claim.package_id != previous_package.package_id
            or outcome.package_id != previous_package.package_id
            or outcome.reservation_id != reservation.reservation_id
            or outcome.outcome_status != "returned"
            or not outcome.executor_result_valid
            or not outcome.candidate_files_changed
            or outcome.recovery_required
        ):
            raise _Blocked("history_invalid")
        if (
            previous_package.source_candidate_diff_sha256
            == evidence.source_candidate_diff_sha256
            or previous_package.authority is None
            or previous_package.authority.source_review_semantic_fingerprint
            == authority.source_review_semantic_fingerprint
        ):
            raise _Blocked("non_convergence")
        return _AttemptLineage(
            rework_attempt_index=index,
            previous_attempt_id=reservation.reservation_id,
            previous_outcome_id=outcome.outcome_id,
            previous_rework_attempt_index=index - 1,
            previous_candidate_diff_sha256=(
                previous_package.source_candidate_diff_sha256
            ),
            previous_review_semantic_fingerprint=(
                previous_package.authority.source_review_semantic_fingerprint
            ),
        )

    @staticmethod
    def _build_package(
        *,
        package_id: UUID,
        created_at: datetime,
        authority: ProjectDirectorBoundedReworkAuthorityEnvelope,
        evidence: ProjectDirectorBoundedReworkEvidenceSnapshot,
        allowed_scope: tuple[str, ...],
        forbidden_scope: tuple[str, ...],
        findings: tuple[ProjectDirectorBoundedReworkFinding, ...],
        corrections: tuple[ProjectDirectorBoundedReworkCorrection, ...],
        lineage: _AttemptLineage,
    ) -> ProjectDirectorBoundedReworkInstructionPackage:
        replay_key = ProjectDirectorBoundedReworkInstructionPackage.compute_package_replay_key(
            authority=authority,
            source_candidate_diff_sha256=evidence.source_candidate_diff_sha256,
            repository_binding_fingerprint=evidence.repository_binding_fingerprint,
            workspace_binding_fingerprint=evidence.workspace_binding_fingerprint,
            base_commit_sha=evidence.base_commit_sha,
            rework_attempt_index=lineage.rework_attempt_index,
        )
        payload: dict[str, Any] = {
            "package_id": package_id,
            "package_status": "prepared",
            "package_replay_key": replay_key,
            "created_at": created_at,
            "authority": authority,
            "review_verdict": "changes_required",
            "review_risk_level": evidence.review_output.risk_level,
            "review_summary": evidence.review_output.summary,
            "blocking_findings": findings,
            "required_corrections": corrections,
            "recommended_next_step_context": (
                evidence.review_output.recommended_next_step
            ),
            "confirmed_acceptance_criteria": (
                evidence.confirmed_acceptance_criteria
            ),
            "verification_requirements": evidence.verification_requirements,
            "allowed_scope_paths": allowed_scope,
            "forbidden_scope_paths": forbidden_scope,
            "repository_binding": evidence.repository_binding,
            "workspace_binding": evidence.workspace_binding,
            "base_commit_sha": evidence.base_commit_sha,
            "base_snapshot_fingerprint": evidence.base_snapshot_fingerprint,
            "source_candidate_diff_message_id": (
                evidence.source_candidate_diff_message_id
            ),
            "source_candidate_diff_sha256": evidence.source_candidate_diff_sha256,
            "source_candidate_diff_fingerprint": (
                evidence.source_candidate_diff_fingerprint
            ),
            "selected_model": evidence.selected_model,
            "selected_skills": evidence.selected_skills,
            "selected_role": evidence.selected_role,
            "rework_attempt_index": lineage.rework_attempt_index,
            "rework_attempt_limit": P25_BOUNDED_REWORK_ATTEMPT_LIMIT,
            "previous_attempt_id": lineage.previous_attempt_id,
            "previous_outcome_id": lineage.previous_outcome_id,
            "previous_rework_attempt_index": (
                lineage.previous_rework_attempt_index
            ),
            "previous_candidate_diff_sha256": (
                lineage.previous_candidate_diff_sha256
            ),
            "previous_review_semantic_fingerprint": (
                lineage.previous_review_semantic_fingerprint
            ),
            "non_convergence_evidence": (),
            "blocked_reasons": (),
            "blocked_summary": None,
            "product_runtime_git_write_allowed": False,
            "main_project_write_allowed": False,
            "automatic_pr_allowed": False,
            "automatic_merge_allowed": False,
            "git_add_allowed": False,
            "git_commit_allowed": False,
            "git_push_allowed": False,
            "branch_operation_allowed": False,
            "ci_trigger_allowed": False,
        }
        try:
            draft = ProjectDirectorBoundedReworkInstructionPackage.model_construct(
                **payload,
                package_fingerprint="0" * 64,
            )
            return ProjectDirectorBoundedReworkInstructionPackage(
                **payload,
                package_fingerprint=draft.compute_fingerprint(),
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise _Blocked("authority_invalid") from exc

    def _load_history(self, session_id: UUID) -> _History:
        packages: list[
            tuple[ProjectDirectorMessage, ProjectDirectorBoundedReworkInstructionPackage]
        ] = []
        reservations: list[ProjectDirectorBoundedReworkAttemptReservation] = []
        claims: list[ProjectDirectorBoundedReworkInvocationClaim] = []
        outcomes: list[ProjectDirectorBoundedReworkInvocationOutcome] = []
        for message in self._iter_session_messages(session_id):
            action = self._p25_action(message)
            if action is None:
                continue
            schema_version = action.get("schema_version")
            payload = dict(action)
            payload.pop("type", None)
            try:
                if schema_version == _PACKAGE_SCHEMA_VERSION:
                    package = ProjectDirectorBoundedReworkInstructionPackage.model_validate(
                        payload
                    )
                    self._validate_package_message(message, package)
                    packages.append((message, package))
                elif schema_version == BOUNDED_REWORK_ATTEMPT_RESERVATION_SCHEMA_VERSION:
                    item = ProjectDirectorBoundedReworkAttemptReservation.model_validate(
                        payload
                    )
                    self._validate_generic_p25_message(
                        message,
                        item.reservation_id,
                        item.created_at,
                        item.exact_task_id,
                        item.authority.project_id,
                    )
                    reservations.append(item)
                elif schema_version == BOUNDED_REWORK_INVOCATION_CLAIM_SCHEMA_VERSION:
                    item = ProjectDirectorBoundedReworkInvocationClaim.model_validate(
                        payload
                    )
                    self._validate_generic_p25_message(
                        message,
                        item.claim_id,
                        item.created_at,
                        item.exact_task_id,
                        item.authority.project_id,
                    )
                    claims.append(item)
                elif schema_version == BOUNDED_REWORK_INVOCATION_OUTCOME_SCHEMA_VERSION:
                    item = ProjectDirectorBoundedReworkInvocationOutcome.model_validate(
                        payload
                    )
                    self._validate_generic_p25_message(
                        message,
                        item.outcome_id,
                        item.created_at,
                        item.exact_task_id,
                        item.authority.project_id,
                    )
                    outcomes.append(item)
                else:
                    raise _Blocked("history_invalid")
            except _Blocked:
                raise
            except (TypeError, ValueError, ValidationError) as exc:
                raise _Blocked("history_invalid") from exc
        history = _History(
            packages=tuple(packages),
            reservations=tuple(reservations),
            claims=tuple(claims),
            outcomes=tuple(outcomes),
        )
        self._validate_history(history)
        return history

    def _iter_session_messages(
        self,
        session_id: UUID,
    ) -> list[ProjectDirectorMessage]:
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
    def _p25_action(message: ProjectDirectorMessage) -> dict[str, Any] | None:
        markers = (
            message.intent == P25_BOUNDED_REWORK_PACKAGE_INTENT,
            message.source_detail == P25_BOUNDED_REWORK_PACKAGE_SOURCE_DETAIL,
            any(
                isinstance(action, dict)
                and (
                    str(action.get("schema_version", "")).startswith(
                        _P25_SCHEMA_PREFIX
                    )
                    or action.get("type") == P25_BOUNDED_REWORK_PACKAGE_ACTION_TYPE
                )
                for action in message.suggested_actions
            ),
        )
        if not any(markers):
            return None
        for action in message.suggested_actions:
            if not isinstance(action, dict):
                continue
            for field_name in (
                "product_runtime_git_write_allowed",
                "main_project_write_allowed",
                "automatic_pr_allowed",
                "automatic_merge_allowed",
                "git_add_allowed",
                "git_commit_allowed",
                "git_push_allowed",
                "branch_operation_allowed",
                "pull_request_allowed",
                "merge_allowed",
                "ci_trigger_allowed",
            ):
                if action.get(field_name) is True:
                    raise _Blocked("git_boundary_violation")
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
        return message.suggested_actions[0]

    @staticmethod
    def _validate_package_message(
        message: ProjectDirectorMessage,
        package: ProjectDirectorBoundedReworkInstructionPackage,
    ) -> None:
        if (
            package.package_status != "prepared"
            or package.authority is None
            or message.id != package.package_id
            or message.session_id != package.authority.session_id
            or message.related_project_id != package.authority.project_id
            or message.related_task_id != package.authority.source_task_id
            or message.intent != P25_BOUNDED_REWORK_PACKAGE_INTENT
            or message.source_detail != P25_BOUNDED_REWORK_PACKAGE_SOURCE_DETAIL
            or message.content
            != f"P25 bounded rework instruction package: {package.package_id}"
            or message.created_at != package.created_at
            or message.suggested_actions[0].get("type")
            != P25_BOUNDED_REWORK_PACKAGE_ACTION_TYPE
            or tuple(message.forbidden_actions_detected)
            != _FORMAL_FALSE_BOUNDARIES
        ):
            raise _Blocked("history_invalid")

    @staticmethod
    def _validate_generic_p25_message(
        message: ProjectDirectorMessage,
        record_id: UUID,
        created_at: datetime,
        source_task_id: UUID,
        project_id: UUID,
    ) -> None:
        if (
            message.id != record_id
            or message.related_task_id != source_task_id
            or message.related_project_id != project_id
            or message.created_at != created_at
        ):
            raise _Blocked("history_invalid")

    @staticmethod
    def _validate_history(history: _History) -> None:
        packages = [item[1] for item in history.packages]
        collections = (
            [item.package_id for item in packages],
            [item.package_replay_key for item in packages],
            [item.reservation_id for item in history.reservations],
            [item.reservation_replay_key for item in history.reservations],
            [item.claim_id for item in history.claims],
            [item.claim_replay_key for item in history.claims],
            [item.outcome_id for item in history.outcomes],
            [item.outcome_replay_key for item in history.outcomes],
        )
        if any(len(values) != len(set(values)) for values in collections):
            raise _Blocked("history_invalid")
        consumption_ids = [
            item.authority.source_p23_dispatch_consumption_id
            for item in packages
            if item.authority is not None
        ]
        if len(consumption_ids) != len(set(consumption_ids)):
            raise _Blocked("authority_replayed")
        reservation_ids = {item.reservation_id for item in history.reservations}
        claim_ids = {item.claim_id for item in history.claims}
        package_ids = {item.package_id for item in packages}
        if any(item.package_id not in package_ids for item in history.reservations):
            raise _Blocked("history_invalid")
        if any(item.reservation_id not in reservation_ids for item in history.claims):
            raise _Blocked("history_invalid")
        if any(item.claim_id not in claim_ids for item in history.outcomes):
            raise _Blocked("history_invalid")
        for claim in history.claims:
            matches = [item for item in history.outcomes if item.claim_id == claim.claim_id]
            if not matches:
                raise _Blocked("claim_without_outcome")
            if len(matches) != 1:
                raise _Blocked("history_invalid")

    @staticmethod
    def _semantic_package_payload(
        package: ProjectDirectorBoundedReworkInstructionPackage,
    ) -> dict[str, Any]:
        return package.model_dump(
            mode="python",
            exclude={"package_id", "created_at", "package_fingerprint"},
        )

    @staticmethod
    def _build_package_message(
        package: ProjectDirectorBoundedReworkInstructionPackage,
        sequence_no: int,
    ) -> ProjectDirectorMessage:
        assert package.authority is not None
        return ProjectDirectorMessage(
            id=package.package_id,
            session_id=package.authority.session_id,
            role=ProjectDirectorMessageRole.ASSISTANT,
            content=f"P25 bounded rework instruction package: {package.package_id}",
            sequence_no=sequence_no,
            intent=P25_BOUNDED_REWORK_PACKAGE_INTENT,
            related_project_id=package.authority.project_id,
            related_task_id=package.authority.source_task_id,
            source=ProjectDirectorMessageSource.SYSTEM,
            source_detail=P25_BOUNDED_REWORK_PACKAGE_SOURCE_DETAIL,
            suggested_actions=[
                {
                    "type": P25_BOUNDED_REWORK_PACKAGE_ACTION_TYPE,
                    **package.model_dump(mode="json"),
                }
            ],
            requires_confirmation=False,
            risk_level=ProjectDirectorMessageRiskLevel.HIGH,
            forbidden_actions_detected=list(_FORMAL_FALSE_BOUNDARIES),
            token_count=None,
            estimated_cost=None,
            created_at=package.created_at,
        )

    @staticmethod
    def _map_evidence_reason(reasons: tuple[str, ...]) -> BoundedReworkBlockedReason:
        if not reasons:
            return "authority_invalid"
        reason = reasons[0]
        mapping: dict[str, BoundedReworkBlockedReason] = {
            "authority_invalid": "authority_invalid",
            "history_invalid": "history_invalid",
            "scope_invalid": "scope_invalid",
            "workspace_invalid": "workspace_invalid",
            "base_commit_mismatch": "base_commit_mismatch",
            "source_diff_mismatch": "source_diff_mismatch",
            "review_findings_invalid": "review_findings_invalid",
        }
        return mapping.get(reason, "authority_invalid")

    @staticmethod
    def _blocked_result(
        reason: BoundedReworkBlockedReason,
    ) -> PreparedProjectDirectorBoundedReworkInstructionPackage:
        package_id = uuid4()
        created_at = utc_now()
        payload: dict[str, Any] = {
            "package_id": package_id,
            "package_status": "blocked",
            "created_at": created_at,
            "blocked_reasons": (reason,),
            "blocked_summary": (
                "Bounded rework instruction package preparation was blocked."
            ),
            "product_runtime_git_write_allowed": False,
            "main_project_write_allowed": False,
            "automatic_pr_allowed": False,
            "automatic_merge_allowed": False,
            "git_add_allowed": False,
            "git_commit_allowed": False,
            "git_push_allowed": False,
            "branch_operation_allowed": False,
            "ci_trigger_allowed": False,
        }
        draft = ProjectDirectorBoundedReworkInstructionPackage.model_construct(
            **payload,
            package_fingerprint="0" * 64,
        )
        package = ProjectDirectorBoundedReworkInstructionPackage(
            **payload,
            package_fingerprint=draft.compute_fingerprint(),
        )
        return PreparedProjectDirectorBoundedReworkInstructionPackage(
            status="blocked",
            package=package,
            message=None,
            blocked_reasons=(reason,),
        )

    def _require_shared_message_repository(self) -> None:
        if (
            self._dispatch_consumption_service._message_repository
            is not self._message_repository
            or self._dispatch_intent_service._message_repository
            is not self._message_repository
            or self._evidence_resolver._message_repository
            is not self._message_repository
        ):
            raise ValueError("P25-C dependencies must share one message repository")


def PurePathParts(value: str) -> tuple[str, ...]:
    """Return POSIX parts without exposing pathlib objects in sort keys."""

    return tuple(part for part in value.split("/") if part)


__all__ = (
    "P25_BOUNDED_REWORK_PACKAGE_ACTION_TYPE",
    "P25_BOUNDED_REWORK_PACKAGE_INTENT",
    "P25_BOUNDED_REWORK_PACKAGE_SOURCE_DETAIL",
    "PreparedProjectDirectorBoundedReworkInstructionPackage",
    "ProjectDirectorBoundedReworkPackagePreparationService",
)
