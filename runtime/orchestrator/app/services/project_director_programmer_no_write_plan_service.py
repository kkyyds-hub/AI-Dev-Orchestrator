"""Programmer no-write planning service for Project Director P16."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.domain.project_director_message import (
    ProjectDirectorMessage,
    ProjectDirectorMessageRiskLevel,
    ProjectDirectorMessageRole,
    ProjectDirectorMessageSource,
)
from app.domain.project_director_programmer_no_write_plan import (
    ProgrammerNoWritePlanningMode,
    ProjectDirectorProgrammerNoWritePlannedStep,
    ProjectDirectorProgrammerNoWritePlanResult,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_readonly_review_service import (
    P15_READONLY_REVIEW_SOURCE_DETAIL,
)


P16_PROGRAMMER_NO_WRITE_PLAN_SOURCE_DETAIL = "p16_programmer_no_write_plan"


@dataclass(frozen=True, slots=True)
class ConfirmedProgrammerNoWritePlan:
    """Programmer no-write plan result and bound session message."""

    result: ProjectDirectorProgrammerNoWritePlanResult
    message: ProjectDirectorMessage | None


class ProjectDirectorProgrammerNoWritePlanService:
    """Create structured implementation plans without writes or executor starts."""

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

    def confirm_plan(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        requested_programmer_executor: str,
        planning_mode: ProgrammerNoWritePlanningMode = "dry_run",
    ) -> ConfirmedProgrammerNoWritePlan:
        """Record a no-write programmer plan message from P15 review output."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("programmer no-write planning repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        if source_task is None:
            raise ValueError(f"Task {source_task_id} not found")

        source_message = self._message_repository.get_by_id(source_message_id)
        if source_message is None:
            raise ValueError(f"Project Director message {source_message_id} not found")

        result = self.build_plan_from_sources(
            session_id=session_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            requested_programmer_executor=requested_programmer_executor,
            planning_mode=planning_mode,
        )
        if result.blocked_reasons:
            raise ValueError(";".join(result.blocked_reasons))

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已生成 P16 programmer no-write implementation plan。该计划"
                    "不代表代码修改完成，不授权产品运行时 Git 写，不创建 Task/Run，"
                    "不启动 executor；AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="programmer_no_write_plan",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P16_PROGRAMMER_NO_WRITE_PLAN_SOURCE_DETAIL,
                suggested_actions=[
                    self._plan_action(result, source_message_id=source_message_id)
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=[
                    "no_product_runtime_git_write",
                    "no_worktree_write",
                    "no_file_write",
                    "no_executor_start",
                    "no_worker_dispatch",
                    "no_task_creation",
                    "no_run_creation",
                    "no_git_approval_from_plan",
                ],
            )
        )
        self._message_repository.commit()

        result = result.model_copy(update={"plan_message_bound": True})
        return ConfirmedProgrammerNoWritePlan(result=result, message=message)

    def build_plan_from_sources(
        self,
        *,
        session_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        requested_programmer_executor: str = "codex",
        planning_mode: ProgrammerNoWritePlanningMode = "dry_run",
    ) -> ProjectDirectorProgrammerNoWritePlanResult:
        """Build a structured no-write plan from a P15 readonly review message."""

        blocked_reasons: list[str] = []
        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        if source_message is None:
            blocked_reasons.append("source_message_missing")

        if source_message is not None:
            if source_message.session_id != session_id:
                blocked_reasons.append("source_message_not_in_session")
            if source_message.source_detail != P15_READONLY_REVIEW_SOURCE_DETAIL:
                blocked_reasons.append("source_message_is_not_p15_readonly_review")

        if source_task is not None and not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_is_not_p12_safe_dry_run")

        if planning_mode == "controlled_no_write":
            blocked_reasons.append("controlled_no_write_not_enabled_in_api")

        required_evidence_refs = self._required_evidence_refs(
            source_task=source_task,
            source_message=source_message,
        )
        affected_files_preview = self._affected_files_preview(
            source_task=source_task,
            source_message=source_message,
        )
        required_targeted_tests = self._required_targeted_tests(source_task)
        reviewer_feedback_refs = (
            [str(source_message.id)] if source_message is not None else []
        )
        planned_steps = self._planned_steps(
            planning_mode=planning_mode,
            evidence_refs=required_evidence_refs,
            affected_files_preview=affected_files_preview,
            required_targeted_tests=required_targeted_tests,
        )

        return ProjectDirectorProgrammerNoWritePlanResult(
            plan_status="blocked" if blocked_reasons else "planned",
            session_id=session_id,
            source_task_id=source_task.id if source_task is not None else None,
            source_message_id=(
                source_message.id if source_message is not None else None
            ),
            requested_programmer_executor=requested_programmer_executor,  # type: ignore[arg-type]
            planning_mode=planning_mode,
            implementation_summary=(
                "Programmer no-write implementation plan prepared without "
                "executor start or file writes."
            ),
            planned_steps=planned_steps,
            affected_files_preview=affected_files_preview,
            required_evidence_refs=required_evidence_refs,
            required_targeted_tests=required_targeted_tests,
            reviewer_feedback_refs=reviewer_feedback_refs,
            risk_level="low",
            recommended_next_step=(
                "Run fake_plan/safety tests before enabling controlled no-write "
                "programmer execution."
            ),
            blocked_reasons=blocked_reasons,
            risks=self._risk_notes(planning_mode=planning_mode),
            unknowns=[
                "controlled no-write programmer execution is not enabled by this API",
                "this plan is not proof that implementation work is complete",
            ],
        )

    @staticmethod
    def _is_safe_dry_run_task(task: Task) -> bool:
        criteria = set(task.acceptance_criteria)
        return (
            task.source_draft_id is not None
            and task.source_draft_id.startswith("p12-")
            and "SAFE DRY-RUN TASK DISPATCH ONLY" in task.input_summary
            and "safe_dry_run_task=true" in criteria
            and "worker_simulate_required=true" in criteria
            and "product_runtime_git_write_allowed=false" in criteria
            and "native_executor_started=false" in criteria
            and "codex_started=false" in criteria
            and "claude_code_started=false" in criteria
        )

    @classmethod
    def _affected_files_preview(
        cls,
        *,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
    ) -> list[str]:
        candidates: list[str] = []
        if source_message is not None:
            for action in source_message.suggested_actions:
                if not isinstance(action, dict):
                    continue
                candidates.extend(cls._string_list(action.get("affected_files_preview")))
                candidates.extend(cls._string_list(action.get("affected_files")))
                candidates.extend(cls._string_list(action.get("allowed_files")))
                candidates.extend(cls._string_list(action.get("impact_paths")))
                for finding in cls._dict_list(action.get("review_findings")):
                    candidates.extend(
                        cls._string_list(finding.get("affected_files_preview"))
                    )

        if not candidates and source_task is not None:
            candidates.extend(
                item
                for item in source_task.acceptance_criteria
                if "/" in item and not item.endswith("=false")
            )

        return cls._dedupe(candidates, limit=20)

    @classmethod
    def _required_evidence_refs(
        cls,
        *,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
    ) -> list[str]:
        refs: list[str] = []
        if source_message is not None:
            refs.append(str(source_message.id))
            for action in source_message.suggested_actions:
                if not isinstance(action, dict):
                    continue
                refs.extend(cls._string_list(action.get("evidence_refs")))
                for finding in cls._dict_list(action.get("review_findings")):
                    refs.extend(cls._string_list(finding.get("evidence_refs")))
        if source_task is not None:
            refs.append(str(source_task.id))
        return cls._dedupe(refs, limit=20)

    @classmethod
    def _required_targeted_tests(cls, source_task: Task | None) -> list[str]:
        if source_task is None:
            return []
        tests = [
            item
            for item in source_task.acceptance_criteria
            if "test" in item.lower() or "pytest" in item.lower()
        ]
        return cls._dedupe(tests, limit=20)

    @classmethod
    def _planned_steps(
        cls,
        *,
        planning_mode: ProgrammerNoWritePlanningMode,
        evidence_refs: list[str],
        affected_files_preview: list[str],
        required_targeted_tests: list[str],
    ) -> list[ProjectDirectorProgrammerNoWritePlannedStep]:
        tests = list(required_targeted_tests)
        risk_notes = cls._risk_notes(planning_mode=planning_mode)
        if planning_mode == "fake_plan" and not tests:
            tests = [
                "Add targeted tests for P16 programmer no-write planning before enabling controlled execution."
            ]

        first_step = ProjectDirectorProgrammerNoWritePlannedStep(
            step_id="p16-plan-1",
            title="Inspect readonly reviewer feedback",
            summary=(
                "Use the P15 readonly reviewer message as planning evidence and "
                "keep the programmer path no-write."
            ),
            evidence_refs=evidence_refs,
            affected_files_preview=affected_files_preview,
            required_targeted_tests=tests,
            risk_notes=risk_notes,
        )
        if planning_mode != "fake_plan":
            return [first_step]

        return [
            first_step,
            ProjectDirectorProgrammerNoWritePlannedStep(
                step_id="p16-plan-2",
                title="Prepare bounded implementation handoff",
                summary=(
                    "Describe allowed implementation files, targeted checks, and "
                    "reviewer feedback references without changing repository files."
                ),
                evidence_refs=evidence_refs,
                affected_files_preview=affected_files_preview,
                required_targeted_tests=tests,
                risk_notes=risk_notes,
            ),
        ]

    @staticmethod
    def _risk_notes(
        *,
        planning_mode: ProgrammerNoWritePlanningMode,
    ) -> list[str]:
        notes = [
            "no-write programmer plan must not be treated as implementation completion",
            "plan output must not authorize product runtime Git writes",
        ]
        if planning_mode == "controlled_no_write":
            notes.append("controlled_no_write is blocked at the API layer")
        return notes

    @staticmethod
    def _plan_action(
        result: ProjectDirectorProgrammerNoWritePlanResult,
        *,
        source_message_id: UUID,
    ) -> dict[str, Any]:
        return {
            "type": "p16_programmer_no_write_plan_record",
            "source_task_id": (
                str(result.source_task_id)
                if result.source_task_id is not None
                else None
            ),
            "source_message_id": str(source_message_id),
            "requested_programmer_executor": result.requested_programmer_executor,
            "planning_mode": result.planning_mode,
            "plan_status": result.plan_status,
            "programmer_agent": True,
            "controlled_programmer_planning": True,
            "no_write_plan": True,
            "executor_backed_programmer_allowed": True,
            "product_runtime_git_write_allowed": False,
            "worktree_write_allowed": False,
            "file_write_allowed": False,
            "real_code_modified": False,
            "git_write_performed": False,
            "native_executor_started": False,
            "codex_started": False,
            "claude_code_started": False,
            "worker_started": False,
            "task_created": False,
            "run_created": False,
            "plan_message_bound": True,
            "implementation_summary": result.implementation_summary,
            "planned_steps": [
                step.model_dump(mode="json") for step in result.planned_steps
            ],
            "affected_files_preview": list(result.affected_files_preview),
            "required_evidence_refs": list(result.required_evidence_refs),
            "required_targeted_tests": list(result.required_targeted_tests),
            "reviewer_feedback_refs": list(result.reviewer_feedback_refs),
            "risk_level": result.risk_level,
            "recommended_next_step": result.recommended_next_step,
            "ai_project_director_total_loop": "Partial",
            "blocked_reasons": list(result.blocked_reasons),
            "risks": list(result.risks),
            "unknowns": list(result.unknowns),
        }

    @staticmethod
    def _string_list(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
        return []

    @staticmethod
    def _dict_list(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _dedupe(values: list[str], *, limit: int) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for raw_value in values:
            value = raw_value.strip()
            if not value or value in seen:
                continue
            result.append(value)
            seen.add(value)
            if len(result) >= limit:
                break
        return result


__all__ = (
    "ConfirmedProgrammerNoWritePlan",
    "P16_PROGRAMMER_NO_WRITE_PLAN_SOURCE_DETAIL",
    "ProjectDirectorProgrammerNoWritePlanService",
)
