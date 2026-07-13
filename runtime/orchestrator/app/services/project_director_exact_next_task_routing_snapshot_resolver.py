"""Readonly P24-D2A1 exact next-Task routing snapshot resolution."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.domain.project_director_exact_next_task_routing_snapshot import (
    EXACT_NEXT_TASK_ROUTING_SCHEMA_VERSION,
    NEXT_TASK_SOURCE_AUTHORITY_LINEAGE_SCHEMA_VERSION,
    ExactNextTaskRoutingBlockedReason,
    ProjectDirectorExactNextTaskRoutingResolution,
    ProjectDirectorExactNextTaskRoutingSnapshot,
    ProjectDirectorNextTaskSourceAuthorityLineageSnapshot,
    ProjectDirectorRoutingScoreItemSnapshot,
    ProjectDirectorStrategyDecisionSnapshot,
    ProjectDirectorStrategyReasonSnapshot,
)
from app.domain.project_director_next_task_source_bundle import (
    ProjectDirectorNextTaskSourceBundle,
)
from app.domain.project_director_source_task_completion_evidence import (
    SOURCE_TASK_COMPLETION_EVIDENCE_SCHEMA_VERSION,
    ProjectDirectorSourceTaskCompletionEvidence,
)
from app.domain.run import RunBudgetStrategyAction
from app.domain.task import Task, TaskHumanStatus, TaskRiskLevel, TaskStatus
from app.repositories.task_repository import TaskRepository
from app.services.project_director_next_task_source_bundle_resolver import (
    ProjectDirectorNextTaskSourceBundleResolver,
)
from app.services.project_director_source_task_completion_evidence_service import (
    ProjectDirectorSourceTaskCompletionEvidenceService,
)
from app.services.task_router_service import TaskRouterService, TaskRoutingCandidate


_FORBIDDEN_ACTIONS = (
    "product_runtime_git_write",
    "global_pending_task_scan",
    "next_task_skip",
    "task_claim",
    "run_creation",
    "worker_invocation",
    "workspace_write",
    "verification_command_execution",
)
_DEPENDENCY_CODES = {"dependency_missing", "dependency_incomplete"}
_STATE_CODES = {"task_not_pending", "task_paused", "pause_note_present"}
_HUMAN_CODES = {
    "task_waiting_human",
    "human_review_requested",
    "human_review_in_progress",
}


class ProjectDirectorExactNextTaskRoutingSnapshotResolver:
    """Freeze one exact Router decision without mutating runtime state."""

    def __init__(
        self,
        *,
        source_bundle_resolver: ProjectDirectorNextTaskSourceBundleResolver,
        completion_evidence_service: (
            ProjectDirectorSourceTaskCompletionEvidenceService
        ),
        task_repository: TaskRepository,
        task_router_service: TaskRouterService,
    ) -> None:
        self._source_bundle_resolver = source_bundle_resolver
        self._completion_evidence_service = completion_evidence_service
        self._task_repository = task_repository
        self._task_router_service = task_router_service
        self._session = source_bundle_resolver._session
        self._require_shared_session()

    def resolve_exact_next_task_routing_snapshot(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> ProjectDirectorExactNextTaskRoutingResolution:
        """Resolve current readonly routing facts for D1's exact next Task."""

        self._require_shared_session()
        with self._session.no_autoflush:
            try:
                source_resolution = (
                    self._source_bundle_resolver.resolve_next_task_source_bundle(
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
                return ProjectDirectorExactNextTaskRoutingResolution.blocked(
                    "next_task_source_bundle_invalid"
                )

            if source_resolution.status == "plan_queue_exhausted":
                if (
                    source_resolution.source_bundle is not None
                    or source_resolution.blocked_reasons
                ):
                    return ProjectDirectorExactNextTaskRoutingResolution.blocked(
                        "next_task_source_bundle_invalid"
                    )
                return ProjectDirectorExactNextTaskRoutingResolution(
                    status="plan_queue_exhausted",
                    source_bundle=None,
                    authority_lineage=None,
                    routing_snapshot=None,
                    blocked_reasons=(),
                    routing_blocker_codes=(),
                )
            if (
                source_resolution.status != "source_bundle_resolved"
                or source_resolution.source_bundle is None
                or source_resolution.blocked_reasons
            ):
                return ProjectDirectorExactNextTaskRoutingResolution.blocked(
                    "next_task_source_bundle_invalid"
                )
            source_bundle = source_resolution.source_bundle

            evidence = self._revalidate_completion_evidence(
                source_bundle=source_bundle,
                session_id=session_id,
                project_id=project_id,
                source_completion_evidence_id=source_completion_evidence_id,
                source_task_id=source_task_id,
                source_run_id=source_run_id,
            )
            if isinstance(evidence, ProjectDirectorExactNextTaskRoutingResolution):
                return evidence

            try:
                authority_lineage = self._build_authority_lineage(evidence)
            except (TypeError, ValueError, ValidationError):
                return ProjectDirectorExactNextTaskRoutingResolution.blocked(
                    "next_task_completion_evidence_invalid",
                    source_bundle=source_bundle,
                )

            try:
                exact_task = self._task_repository.get_by_id(
                    source_bundle.next_task_id
                )
            except (TypeError, ValueError, SQLAlchemyError):
                return self._blocked(
                    "next_task_routing_authority_unavailable",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )
            if exact_task is None:
                return self._blocked(
                    "next_task_missing",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )
            if not self._task_matches_source_bundle(exact_task, source_bundle):
                return self._blocked(
                    "next_task_identity_conflict",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )
            if exact_task.human_status in {
                TaskHumanStatus.REQUESTED,
                TaskHumanStatus.IN_PROGRESS,
            }:
                return self._blocked(
                    "next_task_human_intervention_required",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )
            if exact_task.status != TaskStatus.PENDING or exact_task.paused_reason:
                return self._blocked(
                    "next_task_state_conflict",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )

            try:
                candidate = (
                    self._task_router_service.evaluate_exact_task_for_dispatch(
                        task=exact_task
                    )
                )
            except (TypeError, ValueError, ValidationError, SQLAlchemyError):
                return self._blocked(
                    "next_task_routing_authority_unavailable",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )

            if not self._candidate_identity_matches(
                candidate,
                exact_task=exact_task,
                source_bundle=source_bundle,
                project_id=project_id,
            ):
                return self._blocked(
                    "next_task_routing_identity_conflict",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )

            structured_codes = self._collect_structured_codes(candidate)
            if (
                not candidate.ready
                or not candidate.readiness.ready_for_execution
                or candidate.readiness.blocking_signals
            ):
                reason = self._classify_router_block(
                    candidate=candidate,
                    structured_codes=structured_codes,
                )
                return self._blocked(
                    reason,
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                    routing_blocker_codes=structured_codes,
                )
            if candidate.budget_action == RunBudgetStrategyAction.BLOCK:
                return self._blocked(
                    "next_task_budget_blocked",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                    routing_blocker_codes=structured_codes,
                )
            if (
                not candidate.strategy_code
                or not candidate.strategy_code.strip()
                or not candidate.strategy_summary
                or not candidate.strategy_summary.strip()
                or candidate.strategy_decision is None
                or candidate.routing_score is None
            ):
                return self._blocked(
                    "next_task_strategy_invalid",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )
            if (
                not candidate.model_name
                or not candidate.model_name.strip()
                or not candidate.model_tier
                or not candidate.model_tier.strip()
            ):
                return self._blocked(
                    "next_task_model_unresolved",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )
            if (
                not candidate.dispatch_status
                or not candidate.dispatch_status.strip()
            ):
                return self._blocked(
                    "next_task_dispatch_status_invalid",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )
            if (
                candidate.owner_role_code is None
                or candidate.owner_role_code != exact_task.owner_role_code
                or candidate.owner_role_code
                != source_bundle.next_task_owner_role_code
            ):
                return self._blocked(
                    "next_task_owner_role_conflict",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )

            skill_reason = self._validate_selected_skills(
                candidate=candidate,
                source_bundle=source_bundle,
            )
            if skill_reason is not None:
                return self._blocked(
                    skill_reason,
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )
            if (
                exact_task.risk_level == TaskRiskLevel.HIGH
                or source_bundle.human_confirmation_mechanisms
            ):
                return self._blocked(
                    "next_task_human_confirmation_required",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )

            try:
                routing_snapshot = self._build_routing_snapshot(
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                    exact_task=exact_task,
                    candidate=candidate,
                )
            except (TypeError, ValueError, ValidationError):
                return self._blocked(
                    "next_task_strategy_invalid",
                    source_bundle=source_bundle,
                    authority_lineage=authority_lineage,
                )
            return ProjectDirectorExactNextTaskRoutingResolution(
                status="routing_snapshot_resolved",
                source_bundle=source_bundle,
                authority_lineage=authority_lineage,
                routing_snapshot=routing_snapshot,
                blocked_reasons=(),
                routing_blocker_codes=(),
            )

    def _revalidate_completion_evidence(
        self,
        *,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> (
        ProjectDirectorSourceTaskCompletionEvidence
        | ProjectDirectorExactNextTaskRoutingResolution
    ):
        try:
            resolution = self._completion_evidence_service.revalidate_persisted_source_task_completion_evidence(
                source_completion_evidence_id=source_completion_evidence_id,
                source_task_id=source_task_id,
                source_run_id=source_run_id,
            )
        except (TypeError, ValueError, ValidationError, SQLAlchemyError):
            return self._blocked(
                "next_task_completion_evidence_invalid",
                source_bundle=source_bundle,
            )
        if (
            resolution.status != "evidence_revalidated"
            or resolution.evidence is None
            or resolution.blocked_reasons
            or resolution.evidence.schema_version
            != SOURCE_TASK_COMPLETION_EVIDENCE_SCHEMA_VERSION
            or resolution.evidence.product_runtime_git_write_allowed is not False
        ):
            return self._blocked(
                "next_task_completion_evidence_invalid",
                source_bundle=source_bundle,
            )
        evidence = resolution.evidence
        if (
            evidence.source_completion_evidence_id
            != source_completion_evidence_id
            or evidence.source_completion_evidence_id
            != source_bundle.source_completion_evidence_id
            or evidence.session_id != session_id
            or evidence.session_id != source_bundle.session_id
            or evidence.project_id != project_id
            or evidence.project_id != source_bundle.project_id
            or evidence.plan_version_id != source_bundle.plan_version_id
            or evidence.plan_version_no != source_bundle.plan_version_no
            or evidence.task_creation_record_id
            != source_bundle.task_creation_record_id
            or evidence.source_task_id != source_task_id
            or evidence.source_task_id != source_bundle.source_task_id
            or evidence.source_success_run_id != source_run_id
            or evidence.source_success_run_id != source_bundle.source_run_id
            or evidence.source_completion_evidence_fingerprint
            != source_bundle.source_completion_evidence_fingerprint
        ):
            return self._blocked(
                "next_task_completion_evidence_conflict",
                source_bundle=source_bundle,
            )
        return evidence

    @staticmethod
    def _build_authority_lineage(
        evidence: ProjectDirectorSourceTaskCompletionEvidence,
    ) -> ProjectDirectorNextTaskSourceAuthorityLineageSnapshot:
        payload = {
            "schema_version": NEXT_TASK_SOURCE_AUTHORITY_LINEAGE_SCHEMA_VERSION,
            "source_completion_evidence_id": (
                evidence.source_completion_evidence_id
            ),
            "source_completion_evidence_fingerprint": (
                evidence.source_completion_evidence_fingerprint
            ),
            "source_execution_authority_kind": (
                evidence.source_execution_authority_kind
            ),
            "source_execution_authority_id": (
                evidence.source_execution_authority_id
            ),
            "source_execution_authority_fingerprint": (
                evidence.source_execution_authority_fingerprint
            ),
            "source_reservation_id": evidence.source_reservation_id,
            "source_claim_id": evidence.source_claim_id,
            "source_outcome_id": evidence.source_outcome_id,
            "source_outcome_schema_version": evidence.source_outcome_schema_version,
            "source_outcome_fingerprint": evidence.source_outcome_fingerprint,
            "source_review_id": evidence.source_review_id,
            "source_review_outcome": evidence.source_review_outcome,
            "source_transition_evidence_ids": tuple(
                evidence.source_transition_evidence_ids
            ),
            "completion_policy_id": evidence.completion_policy_id,
            "completion_policy_version": evidence.completion_policy_version,
            "completion_policy_fingerprint": evidence.completion_policy_fingerprint,
            "completion_review_requirement": evidence.review_requirement,
            "completion_review_satisfaction_status": (
                evidence.review_satisfaction_status
            ),
            "completion_review_evidence_kind": evidence.review_evidence_kind,
            "completion_review_evidence_ids": tuple(evidence.review_evidence_ids),
            "source_completion_review_id": evidence.source_completion_review_id,
            "source_completion_review_result_fingerprint": (
                evidence.source_completion_review_result_fingerprint
            ),
            "source_completion_review_verdict": (
                evidence.source_completion_review_verdict
            ),
            "source_completion_review_disposition_id": (
                evidence.source_completion_review_disposition_id
            ),
            "source_completion_review_disposition_type": (
                evidence.source_completion_review_disposition_type
            ),
            "source_completion_review_diff_id": (
                evidence.source_completion_review_diff_id
            ),
            "source_completion_review_diff_sha256": (
                evidence.source_completion_review_diff_sha256
            ),
            "product_runtime_git_write_allowed": False,
        }
        fingerprint = ProjectDirectorNextTaskSourceAuthorityLineageSnapshot.fingerprint_payload(
            payload
        )
        return ProjectDirectorNextTaskSourceAuthorityLineageSnapshot(
            **payload,
            authority_lineage_fingerprint=fingerprint,
        )

    @staticmethod
    def _task_matches_source_bundle(
        task: Task,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
    ) -> bool:
        expected_locator = (
            f"pdv:{source_bundle.plan_version_id}:{source_bundle.plan_version_no}"
        )
        return (
            task.id == source_bundle.next_task_id
            and task.project_id == source_bundle.project_id
            and task.title == source_bundle.next_task_title
            and task.input_summary == source_bundle.next_task_input_summary
            and task.owner_role_code == source_bundle.next_task_owner_role_code
            and task.priority == source_bundle.next_task_priority
            and task.risk_level == source_bundle.next_task_risk_level
            and tuple(task.depends_on_task_ids)
            == source_bundle.next_task_dependency_ids
            and task.source_draft_id == expected_locator
        )

    @staticmethod
    def _candidate_identity_matches(
        candidate: TaskRoutingCandidate,
        *,
        exact_task: Task,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
        project_id: UUID,
    ) -> bool:
        return (
            candidate.task.id == source_bundle.next_task_id
            and candidate.task.project_id == project_id
            and candidate.task.source_draft_id == exact_task.source_draft_id
            and candidate.task.owner_role_code == exact_task.owner_role_code
            and candidate.readiness.task_id == exact_task.id
        )

    @classmethod
    def _collect_structured_codes(
        cls,
        candidate: TaskRoutingCandidate,
    ) -> tuple[str, ...]:
        codes = [
            *(signal.code for signal in candidate.readiness.blocking_signals),
            *(item.code for item in candidate.routing_score_breakdown),
            *(item.code for item in candidate.strategy_reasons),
            *(
                candidate.strategy_decision.rule_codes
                if candidate.strategy_decision is not None
                else ()
            ),
        ]
        normalized = (
            cls._code_value(code)
            for code in codes
        )
        return tuple(dict.fromkeys(code for code in normalized if code))

    @staticmethod
    def _code_value(code: object) -> str:
        if isinstance(code, Enum):
            value = code.value
        else:
            value = code
        return value.strip() if isinstance(value, str) else ""

    @classmethod
    def _classify_router_block(
        cls,
        *,
        candidate: TaskRoutingCandidate,
        structured_codes: tuple[str, ...],
    ) -> ExactNextTaskRoutingBlockedReason:
        code_set = set(structured_codes)
        if any(cls._is_readonly_authority_code(code) for code in code_set):
            return "next_task_routing_authority_unavailable"
        if code_set & _DEPENDENCY_CODES:
            return "next_task_dependency_blocked"
        if code_set & _STATE_CODES:
            return "next_task_state_conflict"
        if code_set & _HUMAN_CODES:
            return "next_task_human_intervention_required"
        if candidate.budget_action == RunBudgetStrategyAction.BLOCK:
            return "next_task_budget_blocked"
        return "next_task_not_ready"

    @staticmethod
    def _is_readonly_authority_code(code: str) -> bool:
        return (
            code in {
                "readonly_router_session_mismatch",
                "readonly_strategy_session_mismatch",
            }
            or code.startswith("readonly_role_")
            or code.startswith("readonly_skill_")
        )

    @staticmethod
    def _validate_selected_skills(
        *,
        candidate: TaskRoutingCandidate,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
    ) -> ExactNextTaskRoutingBlockedReason | None:
        codes = candidate.selected_skill_codes
        names = candidate.selected_skill_names
        if not codes:
            return "next_task_selected_skills_missing"
        if (
            len(codes) != len(names)
            or len(codes) != len(set(codes))
            or len(names) != len(set(names))
        ):
            return "next_task_selected_skill_unconfirmed"
        confirmed_skills = {
            binding.skill_code: binding.skill_name
            for binding in source_bundle.owner_confirmed_skill_bindings
        }
        if any(
            confirmed_skills.get(code) != name
            for code, name in zip(codes, names, strict=True)
        ):
            return "next_task_selected_skill_unconfirmed"
        return None

    @staticmethod
    def _build_routing_snapshot(
        *,
        source_bundle: ProjectDirectorNextTaskSourceBundle,
        authority_lineage: ProjectDirectorNextTaskSourceAuthorityLineageSnapshot,
        exact_task: Task,
        candidate: TaskRoutingCandidate,
    ) -> ProjectDirectorExactNextTaskRoutingSnapshot:
        score_items = tuple(
            ProjectDirectorRoutingScoreItemSnapshot(
                code=item.code,
                label=item.label,
                score=item.score,
                detail=item.detail,
            )
            for item in candidate.routing_score_breakdown
        )
        strategy_reasons = tuple(
            ProjectDirectorStrategyReasonSnapshot(
                code=item.code,
                label=item.label,
                detail=item.detail,
                score=item.score,
            )
            for item in candidate.strategy_reasons
        )
        decision = candidate.strategy_decision
        decision_reasons = tuple(
            ProjectDirectorStrategyReasonSnapshot(
                code=item.code,
                label=item.label,
                detail=item.detail,
                score=item.score,
            )
            for item in decision.reasons
        )
        decision_snapshot = ProjectDirectorStrategyDecisionSnapshot(
            version=decision.version,
            project_stage=decision.project_stage,
            owner_role_code=decision.owner_role_code,
            model_tier=decision.model_tier,
            model_name=decision.model_name,
            selected_skill_codes=tuple(decision.selected_skill_codes),
            selected_skill_names=tuple(decision.selected_skill_names),
            budget_pressure_level=decision.budget_pressure_level,
            budget_action=decision.budget_action,
            strategy_code=decision.strategy_code,
            summary=decision.summary,
            role_model_policy_source=decision.role_model_policy_source,
            role_model_policy_desired_tier=(
                decision.role_model_policy_desired_tier
            ),
            role_model_policy_adjusted_tier=(
                decision.role_model_policy_adjusted_tier
            ),
            role_model_policy_final_tier=decision.role_model_policy_final_tier,
            role_model_policy_stage_override_applied=(
                decision.role_model_policy_stage_override_applied
            ),
            rule_codes=tuple(decision.rule_codes),
            reasons=decision_reasons,
        )
        payload = {
            "schema_version": EXACT_NEXT_TASK_ROUTING_SCHEMA_VERSION,
            "source_bundle_fingerprint": source_bundle.source_bundle_fingerprint,
            "authority_lineage_fingerprint": (
                authority_lineage.authority_lineage_fingerprint
            ),
            "session_id": source_bundle.session_id,
            "project_id": source_bundle.project_id,
            "plan_version_id": source_bundle.plan_version_id,
            "task_creation_record_id": source_bundle.task_creation_record_id,
            "source_task_id": source_bundle.source_task_id,
            "source_run_id": source_bundle.source_run_id,
            "source_completion_evidence_id": (
                source_bundle.source_completion_evidence_id
            ),
            "next_task_id": source_bundle.next_task_id,
            "next_task_index": source_bundle.next_task_index,
            "task_count": source_bundle.task_count,
            "task_status": exact_task.status,
            "task_human_status": exact_task.human_status,
            "task_paused_reason_absent": True,
            "task_owner_role_code": exact_task.owner_role_code,
            "task_priority": exact_task.priority,
            "task_risk_level": exact_task.risk_level,
            "task_dependency_ids": tuple(exact_task.depends_on_task_ids),
            "ready": True,
            "readiness_ready": True,
            "readiness_blocking_codes": (),
            "routing_score": candidate.routing_score,
            "routing_score_breakdown": score_items,
            "route_reason": candidate.route_reason,
            "execution_attempts": candidate.execution_attempts,
            "recent_failure_count": candidate.recent_failure_count,
            "budget_pressure_level": candidate.budget_pressure_level,
            "budget_action": candidate.budget_action,
            "budget_strategy_code": candidate.budget_strategy_code,
            "budget_score_adjustment": candidate.budget_score_adjustment,
            "project_stage": candidate.project_stage,
            "owner_role_code": candidate.owner_role_code,
            "upstream_role_code": candidate.upstream_role_code,
            "downstream_role_code": candidate.downstream_role_code,
            "dispatch_status": candidate.dispatch_status,
            "handoff_reason": candidate.handoff_reason,
            "matched_terms": candidate.matched_terms,
            "model_name": candidate.model_name,
            "model_tier": candidate.model_tier,
            "selected_skill_codes": candidate.selected_skill_codes,
            "selected_skill_names": candidate.selected_skill_names,
            "strategy_code": candidate.strategy_code,
            "strategy_summary": candidate.strategy_summary,
            "strategy_reasons": strategy_reasons,
            "strategy_decision": decision_snapshot,
            "human_confirmation_required": False,
            "human_confirmation_evidence_id": None,
            "product_runtime_git_write_allowed": False,
            "forbidden_actions": _FORBIDDEN_ACTIONS,
        }
        fingerprint = ProjectDirectorExactNextTaskRoutingSnapshot.fingerprint_payload(
            payload
        )
        return ProjectDirectorExactNextTaskRoutingSnapshot(
            **payload,
            routing_snapshot_fingerprint=fingerprint,
        )

    def _require_shared_session(self) -> None:
        sessions = (
            self._source_bundle_resolver._session,
            self._completion_evidence_service._message_repository._session,
            self._task_repository.session,
            self._task_router_service.task_repository.session,
        )
        if any(session is not self._session for session in sessions):
            raise ValueError(
                "P24-D2A1 dependencies must share one SQLAlchemy session"
            )

    @staticmethod
    def _blocked(
        reason: ExactNextTaskRoutingBlockedReason,
        *,
        source_bundle: ProjectDirectorNextTaskSourceBundle | None = None,
        authority_lineage: (
            ProjectDirectorNextTaskSourceAuthorityLineageSnapshot | None
        ) = None,
        routing_blocker_codes: tuple[str, ...] = (),
    ) -> ProjectDirectorExactNextTaskRoutingResolution:
        return ProjectDirectorExactNextTaskRoutingResolution.blocked(
            reason,
            source_bundle=source_bundle,
            authority_lineage=authority_lineage,
            routing_blocker_codes=routing_blocker_codes,
        )


__all__ = ("ProjectDirectorExactNextTaskRoutingSnapshotResolver",)
