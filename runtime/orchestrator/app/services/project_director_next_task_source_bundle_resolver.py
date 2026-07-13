"""Strictly readonly P24-D1 next-Task source authority resolver."""

from __future__ import annotations

import json
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db_tables import (
    ProjectDirectorAgentTeamConfigTable,
    ProjectDirectorPlanVersionTable,
    ProjectDirectorRepositoryBindingConfigTable,
    ProjectDirectorSkillBindingConfigTable,
    ProjectDirectorVerificationConfigTable,
    RepositoryWorkspaceTable,
    TaskTable,
)
from app.domain._base import ensure_utc_datetime
from app.domain.project_director_agent_team_config import (
    AgentTeamConfigStatus,
    ProjectDirectorAgentTeamMemberConfig,
)
from app.domain.project_director_next_task_source_bundle import (
    NEXT_TASK_SOURCE_BUNDLE_SCHEMA_VERSION,
    NextTaskSourceBundleBlockedReason,
    ProjectDirectorAgentTeamConfigSnapshot,
    ProjectDirectorAgentTeamMemberSnapshot,
    ProjectDirectorDeliverableBoundarySnapshot,
    ProjectDirectorNextTaskSourceBundle,
    ProjectDirectorNextTaskSourceBundleResolution,
    ProjectDirectorPlanScopeSnapshot,
    ProjectDirectorRepositoryBindingConfigSnapshot,
    ProjectDirectorRepositoryBindingSnapshot,
    ProjectDirectorRepositoryWorkspaceSnapshot,
    ProjectDirectorSkillBindingConfigSnapshot,
    ProjectDirectorSkillBindingSnapshot,
    ProjectDirectorVerificationConfigSnapshot,
    ProjectDirectorVerificationMechanismSnapshot,
)
from app.domain.project_director_plan_version import (
    DeliverableBoundary,
    PlanVersionStatus,
    ProjectScopeSummary,
    ProposedTask,
)
from app.domain.project_director_repository_binding_config import (
    ProjectDirectorRepositoryBindingConfigItem,
    RepositoryBindingConfigStatus,
)
from app.domain.project_director_skill_binding_config import (
    ProjectDirectorSkillBindingConfigItem,
    SkillBindingConfigStatus,
)
from app.domain.project_director_verification_config import (
    ProjectDirectorVerificationConfigItem,
    VerificationConfigStatus,
)
from app.domain.repository_workspace import RepositoryAccessMode
from app.domain.task import Task, TaskPriority
from app.repositories.task_repository import TaskRepository
from app.services.project_director_confirmed_plan_queue_resolver import (
    ProjectDirectorConfirmedPlanQueueResolver,
)


_PRIORITY_MAP: dict[str, TaskPriority] = {
    "high": TaskPriority.HIGH,
    "urgent": TaskPriority.URGENT,
    "low": TaskPriority.LOW,
}

_FORBIDDEN_ACTIONS = (
    "no_task_router_or_global_pending_queue",
    "no_exact_dispatch_or_readiness_evaluation",
    "no_budget_guard_or_strategy_engine_evaluation",
    "no_instruction_package_or_continuation_creation",
    "no_task_run_agentsession_reservation_claim_or_outcome_creation",
    "no_verification_command_execution",
    "no_worker_provider_reviewer_or_runtime_call",
    "no_workspace_file_read_scan_or_write",
    "no_product_runtime_git_add_commit_push_pr_merge_or_branch_destruction",
    "no_plan_config_or_repository_workspace_mutation",
)

_ModelT = TypeVar("_ModelT")


class _Blocked(Exception):
    def __init__(self, *reasons: NextTaskSourceBundleBlockedReason) -> None:
        self.reasons = tuple(dict.fromkeys(reasons))
        super().__init__(self.reasons[0] if self.reasons else "source bundle blocked")


class ProjectDirectorNextTaskSourceBundleResolver:
    """Restore immutable static authority for P24-C's exact next Task."""

    def __init__(
        self,
        *,
        session: Session,
        confirmed_plan_queue_resolver: ProjectDirectorConfirmedPlanQueueResolver,
    ) -> None:
        self._session = session
        self._confirmed_plan_queue_resolver = confirmed_plan_queue_resolver
        self._task_repository: TaskRepository = (
            confirmed_plan_queue_resolver._task_repository
        )
        self._require_shared_session()

    def resolve_next_task_source_bundle(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        source_completion_evidence_id: UUID,
        source_task_id: UUID,
        source_run_id: UUID,
    ) -> ProjectDirectorNextTaskSourceBundleResolution:
        """Resolve only persisted static facts for the immediate queue successor."""

        queue_snapshot = None
        try:
            with self._session.no_autoflush:
                queue_resolution = (
                    self._confirmed_plan_queue_resolver.resolve_exact_next_task(
                        session_id=session_id,
                        project_id=project_id,
                        source_completion_evidence_id=(
                            source_completion_evidence_id
                        ),
                        source_task_id=source_task_id,
                        source_run_id=source_run_id,
                    )
                )
                if (
                    queue_resolution.status == "blocked"
                    or queue_resolution.snapshot is None
                ):
                    raise _Blocked("next_task_queue_invalid")
                queue_snapshot = queue_resolution.snapshot
                if queue_resolution.status == "plan_queue_exhausted":
                    return ProjectDirectorNextTaskSourceBundleResolution(
                        status="plan_queue_exhausted",
                        queue_snapshot=queue_snapshot,
                        source_bundle=None,
                        blocked_reasons=(),
                    )
                if (
                    queue_resolution.status != "next_task_resolved"
                    or queue_snapshot.queue_exhausted
                    or queue_snapshot.next_task_id is None
                    or queue_snapshot.next_task_index is None
                    or queue_snapshot.session_id != session_id
                    or queue_snapshot.project_id != project_id
                    or queue_snapshot.source_completion_evidence_id
                    != source_completion_evidence_id
                    or queue_snapshot.source_task_id != source_task_id
                ):
                    raise _Blocked("next_task_queue_invalid")

                plan_sources = self._load_strict_plan_sources(
                    plan_version_id=queue_snapshot.plan_version_id,
                    session_id=session_id,
                    project_id=project_id,
                    plan_version_no=queue_snapshot.plan_version_no,
                    task_count=queue_snapshot.task_count,
                    next_task_index=queue_snapshot.next_task_index,
                )
                proposed_task = plan_sources[0][queue_snapshot.next_task_index]
                next_task = self._load_and_validate_next_task(
                    task_id=queue_snapshot.next_task_id,
                    project_id=project_id,
                    locator=(
                        f"pdv:{queue_snapshot.plan_version_id}:"
                        f"{queue_snapshot.plan_version_no}"
                    ),
                    proposed_task=proposed_task,
                )
                owner_role_code = next_task.owner_role_code
                if owner_role_code is None:
                    raise _Blocked("next_task_owner_role_unconfirmed")
                locator = (
                    f"pdv:{queue_snapshot.plan_version_id}:"
                    f"{queue_snapshot.plan_version_no}"
                )

                agent_config, owner_member = self._load_agent_team_config(
                    plan_version_id=queue_snapshot.plan_version_id,
                    project_id=project_id,
                    locator=locator,
                    owner_role_code=owner_role_code.value,
                )
                skill_config, all_skills, owner_skills = (
                    self._load_skill_binding_config(
                        plan_version_id=queue_snapshot.plan_version_id,
                        project_id=project_id,
                        locator=locator,
                        owner_role_code=owner_role_code.value,
                    )
                )
                repository_config, repository_bindings = (
                    self._load_repository_binding_config(
                        plan_version_id=queue_snapshot.plan_version_id,
                        project_id=project_id,
                        locator=locator,
                    )
                )
                (
                    verification_config,
                    all_verifications,
                    owner_verifications,
                    human_verifications,
                ) = self._load_verification_config(
                    plan_version_id=queue_snapshot.plan_version_id,
                    project_id=project_id,
                    locator=locator,
                    owner_role_code=owner_role_code.value,
                )
                workspace = self._load_repository_workspace(project_id)

                proposed_tasks, acceptance, risks, scope, boundaries = plan_sources
                payload: dict[str, Any] = {
                    "schema_version": NEXT_TASK_SOURCE_BUNDLE_SCHEMA_VERSION,
                    "source_completion_evidence_id": (
                        queue_snapshot.source_completion_evidence_id
                    ),
                    "source_completion_evidence_fingerprint": (
                        queue_snapshot.source_completion_evidence_fingerprint
                    ),
                    "queue_fingerprint": queue_snapshot.queue_fingerprint,
                    "session_id": queue_snapshot.session_id,
                    "project_id": queue_snapshot.project_id,
                    "plan_version_id": queue_snapshot.plan_version_id,
                    "plan_version_no": queue_snapshot.plan_version_no,
                    "task_creation_record_id": (
                        queue_snapshot.task_creation_record_id
                    ),
                    "source_task_id": source_task_id,
                    "source_run_id": source_run_id,
                    "source_task_index": queue_snapshot.source_task_index,
                    "next_task_id": queue_snapshot.next_task_id,
                    "next_task_index": queue_snapshot.next_task_index,
                    "task_count": queue_snapshot.task_count,
                    "next_task_title": next_task.title,
                    "next_task_input_summary": next_task.input_summary,
                    "next_task_owner_role_code": owner_role_code,
                    "next_task_priority": next_task.priority,
                    "next_task_risk_level": next_task.risk_level,
                    "next_task_dependency_ids": tuple(
                        next_task.depends_on_task_ids
                    ),
                    "proposed_task_title": proposed_task.title,
                    "proposed_task_description": proposed_task.description,
                    "proposed_task_role_code": proposed_task.suggested_role_code,
                    "proposed_task_priority_hint": proposed_task.priority_hint,
                    "project_scope": scope,
                    "plan_acceptance_criteria": acceptance,
                    "plan_risks": risks,
                    "deliverable_boundaries": boundaries,
                    "agent_team_config": agent_config,
                    "confirmed_owner_member": owner_member,
                    "skill_binding_config": skill_config,
                    "all_confirmed_skill_bindings": all_skills,
                    "owner_confirmed_skill_bindings": owner_skills,
                    "repository_binding_config": repository_config,
                    "confirmed_repository_bindings": repository_bindings,
                    "verification_config": verification_config,
                    "all_verification_mechanisms": all_verifications,
                    "owner_role_verification_mechanisms": owner_verifications,
                    "human_confirmation_mechanisms": human_verifications,
                    "repository_workspace": workspace,
                    "product_runtime_git_write_allowed": False,
                    "forbidden_actions": _FORBIDDEN_ACTIONS,
                }
                fingerprint = (
                    ProjectDirectorNextTaskSourceBundle.fingerprint_payload(payload)
                )
                try:
                    bundle = ProjectDirectorNextTaskSourceBundle(
                        **payload,
                        source_bundle_fingerprint=fingerprint,
                    )
                except (TypeError, ValueError, ValidationError) as exc:
                    raise _Blocked("next_task_source_bundle_invalid") from exc
                return ProjectDirectorNextTaskSourceBundleResolution(
                    status="source_bundle_resolved",
                    queue_snapshot=queue_snapshot,
                    source_bundle=bundle,
                    blocked_reasons=(),
                )
        except _Blocked as exc:
            return ProjectDirectorNextTaskSourceBundleResolution.blocked(
                *exc.reasons,
                queue_snapshot=queue_snapshot,
            )

    def _load_strict_plan_sources(
        self,
        *,
        plan_version_id: UUID,
        session_id: UUID,
        project_id: UUID,
        plan_version_no: int,
        task_count: int,
        next_task_index: int,
    ) -> tuple[
        tuple[ProposedTask, ...],
        tuple[str, ...],
        tuple[str, ...],
        ProjectDirectorPlanScopeSnapshot,
        tuple[ProjectDirectorDeliverableBoundarySnapshot, ...],
    ]:
        try:
            row = self._session.get(ProjectDirectorPlanVersionTable, plan_version_id)
        except SQLAlchemyError as exc:
            raise _Blocked("next_task_plan_source_invalid") from exc
        if row is None:
            raise _Blocked("next_task_plan_source_invalid")
        if (
            row.id != plan_version_id
            or row.session_id != session_id
            or row.project_id != project_id
            or row.version_no != plan_version_no
            or row.status != PlanVersionStatus.CONFIRMED
            or row.confirmed_at is None
        ):
            raise _Blocked("next_task_plan_source_conflict")
        try:
            proposed_tasks = tuple(
                self._parse_model_list(row.proposed_tasks_json, ProposedTask)
            )
            acceptance = tuple(
                self._parse_string_list(row.acceptance_criteria_json)
            )
            risks = tuple(self._parse_string_list(row.risks_json))
            raw_scope = self._parse_model_dict(
                row.project_scope_json,
                ProjectScopeSummary,
            )
            raw_boundaries = self._parse_model_list(
                row.deliverable_boundaries_json,
                DeliverableBoundary,
            )
        except (TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            raise _Blocked("next_task_plan_source_invalid") from exc
        if (
            len(proposed_tasks) != task_count
            or next_task_index >= len(proposed_tasks)
            or not self._scope_has_content(raw_scope)
        ):
            raise _Blocked("next_task_plan_source_conflict")
        scope = ProjectDirectorPlanScopeSnapshot(
            in_scope=tuple(raw_scope.in_scope),
            out_of_scope=tuple(raw_scope.out_of_scope),
            assumptions=tuple(raw_scope.assumptions),
        )
        boundaries = tuple(
            ProjectDirectorDeliverableBoundarySnapshot(
                name=item.name,
                description=item.description,
                owner_role_code=item.owner_role_code,
                required_contents=tuple(item.required_contents),
                done_definition=item.done_definition,
                acceptance_signal=item.acceptance_signal,
            )
            for item in raw_boundaries
        )
        return proposed_tasks, acceptance, risks, scope, boundaries

    def _load_and_validate_next_task(
        self,
        *,
        task_id: UUID,
        project_id: UUID,
        locator: str,
        proposed_task: ProposedTask,
    ) -> Task:
        try:
            task = self._task_repository.get_by_id(task_id)
            row = self._session.get(TaskTable, task_id)
        except (TypeError, ValueError, ValidationError, SQLAlchemyError) as exc:
            raise _Blocked("next_task_plan_task_mismatch") from exc
        expected_summary = (
            proposed_task.description.strip()
            if proposed_task.description and proposed_task.description.strip()
            else f"由计划版本生成的任务: {proposed_task.title}"
        )
        expected_priority = _PRIORITY_MAP.get(
            proposed_task.priority_hint.lower(),
            TaskPriority.NORMAL,
        )
        if (
            task is None
            or row is None
            or task.id != task_id
            or task.project_id != project_id
            or task.title != proposed_task.title
            or task.input_summary != expected_summary
            or task.owner_role_code != proposed_task.suggested_role_code
            or task.priority != expected_priority
            or task.source_draft_id != locator
            or row.source_draft_id != locator
        ):
            raise _Blocked("next_task_plan_task_mismatch")
        return task

    def _load_agent_team_config(
        self,
        *,
        plan_version_id: UUID,
        project_id: UUID,
        locator: str,
        owner_role_code: str,
    ) -> tuple[
        ProjectDirectorAgentTeamConfigSnapshot,
        ProjectDirectorAgentTeamMemberSnapshot,
    ]:
        row = self._load_exact_config_row(
            table=ProjectDirectorAgentTeamConfigTable,
            plan_version_id=plan_version_id,
            missing="next_task_agent_team_config_missing",
            conflict="next_task_agent_team_config_conflict",
            invalid="next_task_agent_team_config_invalid",
        )
        self._validate_config_authority(
            row=row,
            project_id=project_id,
            plan_version_id=plan_version_id,
            locator=locator,
            confirmed_status=AgentTeamConfigStatus.CONFIRMED,
            conflict="next_task_agent_team_config_conflict",
            invalid="next_task_agent_team_config_invalid",
            not_confirmed="next_task_agent_team_config_not_confirmed",
        )
        try:
            raw_members = self._parse_model_list(
                row.agent_team_json,
                ProjectDirectorAgentTeamMemberConfig,
            )
            warnings = tuple(self._parse_string_list(row.warnings_json))
            members = tuple(
                ProjectDirectorAgentTeamMemberSnapshot(
                    role_code=item.role_code,
                    role_name=item.role_name,
                    responsibility=item.responsibility,
                    collaboration_notes=tuple(item.collaboration_notes),
                    review_status=item.review_status,
                )
                for item in raw_members
            )
        except (TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            raise _Blocked("next_task_agent_team_config_invalid") from exc
        owners = tuple(item for item in members if item.role_code == owner_role_code)
        if (
            not members
            or len(owners) != 1
            or any(not item.responsibility.strip() for item in members)
        ):
            raise _Blocked("next_task_owner_role_unconfirmed")
        created_at, updated_at, confirmed_at = self._config_times(
            row,
            "next_task_agent_team_config_invalid",
        )
        config = ProjectDirectorAgentTeamConfigSnapshot(
            id=row.id,
            project_id=row.project_id,
            plan_version_id=row.plan_version_id,
            source_draft_id=row.source_draft_id,
            status="confirmed",
            agent_team=members,
            warnings=warnings,
            review_note=row.review_note or "",
            created_at=created_at,
            updated_at=updated_at,
            confirmed_at=confirmed_at,
            rejected_at=None,
        )
        return config, owners[0]

    def _load_skill_binding_config(
        self,
        *,
        plan_version_id: UUID,
        project_id: UUID,
        locator: str,
        owner_role_code: str,
    ) -> tuple[
        ProjectDirectorSkillBindingConfigSnapshot,
        tuple[ProjectDirectorSkillBindingSnapshot, ...],
        tuple[ProjectDirectorSkillBindingSnapshot, ...],
    ]:
        row = self._load_exact_config_row(
            table=ProjectDirectorSkillBindingConfigTable,
            plan_version_id=plan_version_id,
            missing="next_task_skill_config_missing",
            conflict="next_task_skill_config_conflict",
            invalid="next_task_skill_config_invalid",
        )
        self._validate_config_authority(
            row=row,
            project_id=project_id,
            plan_version_id=plan_version_id,
            locator=locator,
            confirmed_status=SkillBindingConfigStatus.CONFIRMED,
            conflict="next_task_skill_config_conflict",
            invalid="next_task_skill_config_invalid",
            not_confirmed="next_task_skill_config_not_confirmed",
        )
        try:
            raw_items = self._parse_model_list(
                row.skill_bindings_json,
                ProjectDirectorSkillBindingConfigItem,
            )
            warnings = tuple(self._parse_string_list(row.warnings_json))
            items = tuple(
                ProjectDirectorSkillBindingSnapshot(
                    skill_code=item.skill_code,
                    skill_name=item.skill_name,
                    owner_role_code=item.owner_role_code,
                    usage=item.usage,
                    activation_stage=item.activation_stage,
                    binding_mode=item.binding_mode,
                    reason=item.reason,
                    review_status=item.review_status,
                )
                for item in raw_items
            )
        except (TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            raise _Blocked("next_task_skill_config_invalid") from exc
        owner_items = tuple(
            item
            for item in items
            if item.owner_role_code == owner_role_code and item.skill_code.strip()
        )
        executable_keys = [
            (item.owner_role_code, item.skill_code.strip())
            for item in items
            if item.skill_code.strip()
        ]
        if len(executable_keys) != len(set(executable_keys)):
            raise _Blocked("next_task_skill_config_invalid")
        created_at, updated_at, confirmed_at = self._config_times(
            row,
            "next_task_skill_config_invalid",
        )
        config = ProjectDirectorSkillBindingConfigSnapshot(
            id=row.id,
            project_id=row.project_id,
            plan_version_id=row.plan_version_id,
            source_draft_id=row.source_draft_id,
            status="confirmed",
            skill_bindings=items,
            warnings=warnings,
            review_note=row.review_note or "",
            created_at=created_at,
            updated_at=updated_at,
            confirmed_at=confirmed_at,
            rejected_at=None,
        )
        return config, items, owner_items

    def _load_repository_binding_config(
        self,
        *,
        plan_version_id: UUID,
        project_id: UUID,
        locator: str,
    ) -> tuple[
        ProjectDirectorRepositoryBindingConfigSnapshot,
        tuple[ProjectDirectorRepositoryBindingSnapshot, ...],
    ]:
        row = self._load_exact_config_row(
            table=ProjectDirectorRepositoryBindingConfigTable,
            plan_version_id=plan_version_id,
            missing="next_task_repository_config_missing",
            conflict="next_task_repository_config_conflict",
            invalid="next_task_repository_config_invalid",
        )
        self._validate_config_authority(
            row=row,
            project_id=project_id,
            plan_version_id=plan_version_id,
            locator=locator,
            confirmed_status=RepositoryBindingConfigStatus.CONFIRMED,
            conflict="next_task_repository_config_conflict",
            invalid="next_task_repository_config_invalid",
            not_confirmed="next_task_repository_config_not_confirmed",
        )
        try:
            raw_items = self._parse_model_list(
                row.repository_bindings_json,
                ProjectDirectorRepositoryBindingConfigItem,
                nested_string_lists=("focus_paths",),
            )
            warnings = tuple(self._parse_string_list(row.warnings_json))
            items = tuple(
                ProjectDirectorRepositoryBindingSnapshot(
                    binding_type=item.binding_type,
                    binding_mode=item.binding_mode,
                    target=item.target,
                    branch=item.branch,
                    focus_paths=tuple(item.focus_paths),
                    usage=item.usage,
                    safety_note=item.safety_note,
                    review_status=item.review_status,
                )
                for item in raw_items
            )
        except (TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            raise _Blocked("next_task_repository_config_invalid") from exc
        if (
            not items
            or any(not item.target.strip() for item in items)
            or len(items) != len(set(items))
        ):
            raise _Blocked("next_task_repository_config_invalid")
        created_at, updated_at, confirmed_at = self._config_times(
            row,
            "next_task_repository_config_invalid",
        )
        config = ProjectDirectorRepositoryBindingConfigSnapshot(
            id=row.id,
            project_id=row.project_id,
            plan_version_id=row.plan_version_id,
            source_draft_id=row.source_draft_id,
            status="confirmed",
            repository_bindings=items,
            warnings=warnings,
            review_note=row.review_note or "",
            created_at=created_at,
            updated_at=updated_at,
            confirmed_at=confirmed_at,
            rejected_at=None,
        )
        return config, items

    def _load_verification_config(
        self,
        *,
        plan_version_id: UUID,
        project_id: UUID,
        locator: str,
        owner_role_code: str,
    ) -> tuple[
        ProjectDirectorVerificationConfigSnapshot,
        tuple[ProjectDirectorVerificationMechanismSnapshot, ...],
        tuple[ProjectDirectorVerificationMechanismSnapshot, ...],
        tuple[ProjectDirectorVerificationMechanismSnapshot, ...],
    ]:
        row = self._load_exact_config_row(
            table=ProjectDirectorVerificationConfigTable,
            plan_version_id=plan_version_id,
            missing="next_task_verification_config_missing",
            conflict="next_task_verification_config_conflict",
            invalid="next_task_verification_config_invalid",
        )
        self._validate_config_authority(
            row=row,
            project_id=project_id,
            plan_version_id=plan_version_id,
            locator=locator,
            confirmed_status=VerificationConfigStatus.CONFIRMED,
            conflict="next_task_verification_config_conflict",
            invalid="next_task_verification_config_invalid",
            not_confirmed="next_task_verification_config_not_confirmed",
        )
        try:
            raw_items = self._parse_model_list(
                row.verification_mechanisms_json,
                ProjectDirectorVerificationConfigItem,
            )
            warnings = tuple(self._parse_string_list(row.warnings_json))
            items = tuple(
                ProjectDirectorVerificationMechanismSnapshot(
                    name=item.name,
                    command_or_method=item.command_or_method,
                    purpose=item.purpose,
                    evidence_required=item.evidence_required,
                    owner_role_code=item.owner_role_code,
                    risk_level=item.risk_level,
                    requires_user_confirmation=item.requires_user_confirmation,
                    review_status=item.review_status,
                )
                for item in raw_items
            )
        except (TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
            raise _Blocked("next_task_verification_config_invalid") from exc
        required_text = (
            "name",
            "command_or_method",
            "evidence_required",
            "owner_role_code",
            "risk_level",
        )
        if (
            not items
            or any(
                not getattr(item, field).strip()
                for item in items
                for field in required_text
            )
            or len(items) != len(set(items))
        ):
            raise _Blocked("next_task_verification_config_invalid")
        owner_items = tuple(
            item for item in items if item.owner_role_code == owner_role_code
        )
        human_items = tuple(
            item
            for item in items
            if item.requires_user_confirmation or item.risk_level == "high"
        )
        created_at, updated_at, confirmed_at = self._config_times(
            row,
            "next_task_verification_config_invalid",
        )
        config = ProjectDirectorVerificationConfigSnapshot(
            id=row.id,
            project_id=row.project_id,
            plan_version_id=row.plan_version_id,
            source_draft_id=row.source_draft_id,
            status="confirmed",
            verification_mechanisms=items,
            warnings=warnings,
            review_note=row.review_note or "",
            created_at=created_at,
            updated_at=updated_at,
            confirmed_at=confirmed_at,
            rejected_at=None,
        )
        return config, items, owner_items, human_items

    def _load_repository_workspace(
        self,
        project_id: UUID,
    ) -> ProjectDirectorRepositoryWorkspaceSnapshot:
        try:
            rows = self._session.execute(
                select(RepositoryWorkspaceTable).where(
                    RepositoryWorkspaceTable.project_id == project_id
                )
            ).scalars().all()
        except SQLAlchemyError as exc:
            raise _Blocked("next_task_workspace_invalid") from exc
        if not rows:
            raise _Blocked("next_task_workspace_missing")
        if len(rows) != 1:
            raise _Blocked("next_task_workspace_conflict")
        row = rows[0]
        try:
            ignore_rules = tuple(
                self._parse_string_list(row.ignore_rule_summary_json)
            )
            created_at = self._strict_utc_datetime(row.created_at)
            updated_at = self._strict_utc_datetime(row.updated_at)
            root_path = row.root_path.strip()
            allowed_root = row.allowed_workspace_root.strip()
            normalized_root = Path(os.path.normpath(root_path))
            normalized_allowed_root = Path(os.path.normpath(allowed_root))
            if (
                row.project_id != project_id
                or row.access_mode != RepositoryAccessMode.READ_ONLY
                or not root_path
                or not allowed_root
                or not normalized_root.is_absolute()
                or not normalized_allowed_root.is_absolute()
                or not (row.display_name or "").strip()
                or not (row.default_base_branch or "").strip()
                or updated_at < created_at
            ):
                raise ValueError("repository workspace is invalid")
            normalized_root.relative_to(normalized_allowed_root)
            return ProjectDirectorRepositoryWorkspaceSnapshot(
                id=row.id,
                project_id=row.project_id,
                root_path=str(normalized_root),
                display_name=row.display_name.strip(),
                access_mode=row.access_mode,
                default_base_branch=row.default_base_branch.strip(),
                ignore_rule_summary=ignore_rules,
                allowed_workspace_root=str(normalized_allowed_root),
                created_at=created_at,
                updated_at=updated_at,
            )
        except (
            TypeError,
            ValueError,
            ValidationError,
            json.JSONDecodeError,
        ) as exc:
            raise _Blocked("next_task_workspace_invalid") from exc

    def _load_exact_config_row(
        self,
        *,
        table: Any,
        plan_version_id: UUID,
        missing: NextTaskSourceBundleBlockedReason,
        conflict: NextTaskSourceBundleBlockedReason,
        invalid: NextTaskSourceBundleBlockedReason,
    ) -> Any:
        try:
            rows = self._session.execute(
                select(table).where(table.plan_version_id == plan_version_id)
            ).scalars().all()
        except SQLAlchemyError as exc:
            raise _Blocked(invalid) from exc
        if not rows:
            raise _Blocked(missing)
        if len(rows) != 1:
            raise _Blocked(conflict)
        return rows[0]

    def _validate_config_authority(
        self,
        *,
        row: Any,
        project_id: UUID,
        plan_version_id: UUID,
        locator: str,
        confirmed_status: Enum,
        conflict: NextTaskSourceBundleBlockedReason,
        invalid: NextTaskSourceBundleBlockedReason,
        not_confirmed: NextTaskSourceBundleBlockedReason,
    ) -> None:
        if (
            row.project_id != project_id
            or row.plan_version_id != plan_version_id
            or row.source_draft_id != locator
        ):
            raise _Blocked(conflict)
        if (
            row.status != confirmed_status
            or row.confirmed_at is None
            or row.rejected_at is not None
        ):
            raise _Blocked(not_confirmed)
        self._config_times(row, invalid)

    def _config_times(
        self,
        row: Any,
        invalid: NextTaskSourceBundleBlockedReason,
    ) -> tuple[datetime, datetime, datetime]:
        try:
            created_at = self._strict_utc_datetime(row.created_at)
            updated_at = self._strict_utc_datetime(row.updated_at)
            confirmed_at = self._strict_utc_datetime(row.confirmed_at)
        except (TypeError, ValueError) as exc:
            raise _Blocked(invalid) from exc
        if updated_at < created_at:
            raise _Blocked(invalid)
        return created_at, updated_at, confirmed_at

    @staticmethod
    def _strict_utc_datetime(value: Any) -> datetime:
        if not isinstance(value, datetime):
            raise TypeError("persisted timestamp must be a datetime")
        normalized = ensure_utc_datetime(value)
        if normalized is None:
            raise ValueError("persisted timestamp is required")
        return normalized

    @staticmethod
    def _parse_json(raw_value: Any) -> Any:
        if not isinstance(raw_value, str):
            raise TypeError("persisted JSON must be text")
        return json.loads(raw_value)

    @classmethod
    def _parse_string_list(cls, raw_value: Any) -> list[str]:
        decoded = cls._parse_json(raw_value)
        if not isinstance(decoded, list) or any(
            not isinstance(item, str) for item in decoded
        ):
            raise TypeError("persisted JSON must be a string array")
        return decoded

    @classmethod
    def _parse_model_list(
        cls,
        raw_value: Any,
        model_type: type[_ModelT],
        *,
        nested_string_lists: tuple[str, ...] = (),
    ) -> list[_ModelT]:
        decoded = cls._parse_json(raw_value)
        if not isinstance(decoded, list):
            raise TypeError("persisted JSON must be an object array")
        result: list[_ModelT] = []
        for item in decoded:
            if not isinstance(item, dict):
                raise TypeError("persisted model array item must be an object")
            for field in nested_string_lists:
                nested = item.get(field)
                if not isinstance(nested, list) or any(
                    not isinstance(value, str) for value in nested
                ):
                    raise TypeError(f"{field} must be a string array")
            result.append(model_type(**item))
        return result

    @classmethod
    def _parse_model_dict(
        cls,
        raw_value: Any,
        model_type: type[_ModelT],
    ) -> _ModelT:
        decoded = cls._parse_json(raw_value)
        if not isinstance(decoded, dict):
            raise TypeError("persisted JSON must be an object")
        return model_type(**decoded)

    @staticmethod
    def _scope_has_content(scope: ProjectScopeSummary) -> bool:
        return any(
            item.strip()
            for collection in (
                scope.in_scope,
                scope.out_of_scope,
                scope.assumptions,
            )
            for item in collection
        )

    def _require_shared_session(self) -> None:
        queue_resolver = self._confirmed_plan_queue_resolver
        sessions = (
            self._session,
            self._task_repository.session,
            queue_resolver._task_repository.session,
            queue_resolver._completion_evidence_service._message_repository._session,
        )
        if any(item is not self._session for item in sessions):
            raise ValueError("P24-D1 dependencies must share one SQLAlchemy session")


__all__ = ("ProjectDirectorNextTaskSourceBundleResolver",)
