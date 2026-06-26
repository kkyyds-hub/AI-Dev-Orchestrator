"""Programmer no-write execution service for Project Director P17."""

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
from app.domain.project_director_patch_preview_safety import (
    ProjectDirectorPatchPreviewSafetyResult,
    sanitize_patch_preview,
)
from app.domain.project_director_programmer_no_write_execution import (
    ProgrammerNoWriteExecutionMode,
    ProjectDirectorProgrammerNoWriteExecutionResult,
    ProjectDirectorProgrammerNoWriteExecutionStep,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_programmer_no_write_plan_service import (
    P16_PROGRAMMER_NO_WRITE_PLAN_SOURCE_DETAIL,
)


P17_PROGRAMMER_NO_WRITE_EXECUTION_SOURCE_DETAIL = (
    "p17_programmer_no_write_execution"
)


@dataclass(frozen=True, slots=True)
class ConfirmedProgrammerNoWriteExecution:
    """Programmer no-write execution result and bound session message."""

    result: ProjectDirectorProgrammerNoWriteExecutionResult
    message: ProjectDirectorMessage | None


class ProjectDirectorProgrammerNoWriteExecutionService:
    """Create structured no-write execution results without applying patches."""

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

    def confirm_execution(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        requested_programmer_executor: str,
        execution_mode: ProgrammerNoWriteExecutionMode = "dry_run",
    ) -> ConfirmedProgrammerNoWriteExecution:
        """Record a no-write execution result message from P16 plan output."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("programmer no-write execution repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        if source_task is None:
            raise ValueError(f"Task {source_task_id} not found")

        source_message = self._message_repository.get_by_id(source_message_id)
        if source_message is None:
            raise ValueError(f"Project Director message {source_message_id} not found")

        result = self.build_execution_from_sources(
            session_id=session_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            requested_programmer_executor=requested_programmer_executor,
            execution_mode=execution_mode,
        )
        if result.blocked_reasons:
            raise ValueError(";".join(result.blocked_reasons))

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已生成 P17 programmer no-write execution result。该结果"
                    "不代表代码修改完成，不授权产品运行时 Git 写，不创建 Task/Run，"
                    "不启动 executor，不应用 patch；AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="programmer_no_write_execution",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P17_PROGRAMMER_NO_WRITE_EXECUTION_SOURCE_DETAIL,
                suggested_actions=[
                    self._execution_action(
                        result,
                        source_message_id=source_message_id,
                    )
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=[
                    "no_product_runtime_git_write",
                    "no_worktree_write",
                    "no_file_write",
                    "no_patch_apply",
                    "no_executor_start",
                    "no_worker_dispatch",
                    "no_task_creation",
                    "no_run_creation",
                    "no_git_approval_from_execution",
                ],
            )
        )
        self._message_repository.commit()

        result = result.model_copy(update={"execution_message_bound": True})
        return ConfirmedProgrammerNoWriteExecution(result=result, message=message)

    def build_execution_from_sources(
        self,
        *,
        session_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        requested_programmer_executor: str = "codex",
        execution_mode: ProgrammerNoWriteExecutionMode = "dry_run",
    ) -> ProjectDirectorProgrammerNoWriteExecutionResult:
        """Build a structured no-write execution result from a P16 plan message."""

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
            if source_message.source_detail != P16_PROGRAMMER_NO_WRITE_PLAN_SOURCE_DETAIL:
                blocked_reasons.append(
                    "source_message_is_not_p16_programmer_no_write_plan"
                )

        if source_task is not None and not self._is_safe_dry_run_task(source_task):
            blocked_reasons.append("source_task_is_not_p12_safe_dry_run")

        if source_task is not None and source_message is not None:
            if not self._source_message_binds_task(source_message, source_task):
                blocked_reasons.append("source_task_not_bound_to_p16_plan")

        if execution_mode == "controlled_no_write":
            blocked_reasons.append("controlled_no_write_not_enabled_in_api")

        files_considered = self._files_considered(source_message)
        tests_to_run = self._tests_to_run(source_message)
        if execution_mode == "fake_execution" and not tests_to_run:
            tests_to_run = [
                "Add targeted tests for P17 programmer no-write execution before enabling controlled file writes."
            ]
        patch_preview_safety = self._patch_preview_safety_result(
            files_considered,
            execution_mode=execution_mode,
        )
        patch_preview = patch_preview_safety.sanitized_preview
        for reason in patch_preview_safety.blocked_reasons:
            if reason not in blocked_reasons:
                blocked_reasons.append(reason)
        source_plan_refs = (
            [str(source_message.id)] if source_message is not None else []
        )
        risk_notes = self._risk_notes(execution_mode=execution_mode)
        if patch_preview_safety.applyable_diff_detected:
            risk_notes = [
                *risk_notes,
                "patch preview sanitizer removed applyable diff markers",
            ]
        execution_steps = self._execution_steps(
            source_message=source_message,
            execution_mode=execution_mode,
            files_considered=files_considered,
            patch_preview=patch_preview,
            tests_to_run=tests_to_run,
            risk_notes=risk_notes,
        )
        risks = [
            "no-write execution result must not be treated as code completion",
            "execution output must not authorize product runtime Git writes",
            "patch preview is not an applyable patch",
        ]
        unknowns = [
            "controlled no-write programmer execution is not enabled by this API",
            "real file changes and reviewer review of a real diff remain out of scope",
        ]
        if patch_preview_safety.applyable_diff_detected:
            risks.append("patch preview sanitizer removed applyable diff markers")
            unknowns.append("unsafe raw patch preview was not returned")

        return ProjectDirectorProgrammerNoWriteExecutionResult(
            execution_status=(
                "executed"
                if execution_mode == "fake_execution" and not blocked_reasons
                else "blocked"
                if blocked_reasons
                else "planned"
            ),
            session_id=session_id,
            source_task_id=source_task.id if source_task is not None else None,
            source_message_id=(
                source_message.id if source_message is not None else None
            ),
            requested_programmer_executor=requested_programmer_executor,  # type: ignore[arg-type]
            execution_mode=execution_mode,
            execution_summary=(
                "Programmer no-write execution prepared without executor start, "
                "file writes, patch application, or Git writes."
            ),
            execution_steps=execution_steps,
            patch_preview=patch_preview,
            files_considered=files_considered,
            tests_to_run=tests_to_run,
            implementation_notes=[
                "No repository file was modified by this execution result.",
                "No patch was applied and no product runtime Git write was authorized.",
            ],
            handoff_notes=[
                "Use this result as a bounded handoff for later controlled execution hardening.",
                "Keep AI Project Director total loop Partial until final UAT.",
            ],
            risk_notes=risk_notes,
            risk_level="low",
            recommended_next_step=(
                "Run fake_execution/safety tests before enabling controlled "
                "no-write programmer execution."
            ),
            source_plan_refs=source_plan_refs,
            blocked_reasons=blocked_reasons,
            risks=risks,
            unknowns=unknowns,
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

    @staticmethod
    def _source_message_binds_task(
        source_message: ProjectDirectorMessage,
        source_task: Task,
    ) -> bool:
        if source_message.related_task_id == source_task.id:
            return True

        for action in source_message.suggested_actions:
            if not isinstance(action, dict):
                continue
            if action.get("type") != "p16_programmer_no_write_plan_record":
                continue
            if action.get("source_task_id") == str(source_task.id):
                return True

        return False

    @classmethod
    def _p16_plan_actions(
        cls,
        source_message: ProjectDirectorMessage | None,
    ) -> list[dict[str, Any]]:
        if source_message is None:
            return []
        return [
            action
            for action in source_message.suggested_actions
            if isinstance(action, dict)
            and action.get("type") == "p16_programmer_no_write_plan_record"
        ]

    @classmethod
    def _files_considered(
        cls,
        source_message: ProjectDirectorMessage | None,
    ) -> list[str]:
        files: list[str] = []
        for action in cls._p16_plan_actions(source_message):
            files.extend(cls._string_list(action.get("affected_files_preview")))
            for step in cls._dict_list(action.get("planned_steps")):
                files.extend(cls._string_list(step.get("affected_files_preview")))
        return cls._dedupe(files, limit=20)

    @classmethod
    def _tests_to_run(
        cls,
        source_message: ProjectDirectorMessage | None,
    ) -> list[str]:
        tests: list[str] = []
        for action in cls._p16_plan_actions(source_message):
            tests.extend(cls._string_list(action.get("required_targeted_tests")))
            for step in cls._dict_list(action.get("planned_steps")):
                tests.extend(cls._string_list(step.get("required_targeted_tests")))
        return cls._dedupe(tests, limit=20)

    @classmethod
    def _source_plan_steps(
        cls,
        source_message: ProjectDirectorMessage | None,
    ) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        for action in cls._p16_plan_actions(source_message):
            steps.extend(cls._dict_list(action.get("planned_steps")))
        return steps[:10]

    @classmethod
    def _execution_steps(
        cls,
        *,
        source_message: ProjectDirectorMessage | None,
        execution_mode: ProgrammerNoWriteExecutionMode,
        files_considered: list[str],
        patch_preview: list[str],
        tests_to_run: list[str],
        risk_notes: list[str],
    ) -> list[ProjectDirectorProgrammerNoWriteExecutionStep]:
        steps: list[ProjectDirectorProgrammerNoWriteExecutionStep] = []
        source_steps = cls._source_plan_steps(source_message)
        for index, source_step in enumerate(source_steps, start=1):
            source_step_id = str(source_step.get("step_id") or f"p16-plan-{index}")
            step_files = cls._dedupe(
                cls._string_list(source_step.get("affected_files_preview"))
                or files_considered,
                limit=20,
            )
            step_tests = cls._dedupe(
                cls._string_list(source_step.get("required_targeted_tests"))
                or tests_to_run,
                limit=20,
            )
            steps.append(
                ProjectDirectorProgrammerNoWriteExecutionStep(
                    step_id=f"p17-execution-{index}",
                    title=f"No-write execution for {source_step_id}",
                    summary=(
                        "Translate the P16 plan step into a no-write execution "
                        "handoff without patch application."
                    ),
                    source_plan_step_ids=[source_step_id],
                    files_considered=step_files,
                    patch_preview=cls._patch_preview(
                        step_files,
                        execution_mode=execution_mode,
                    )
                    or patch_preview,
                    tests_to_run=step_tests,
                    risk_notes=risk_notes,
                )
            )

        if not steps:
            steps.append(
                ProjectDirectorProgrammerNoWriteExecutionStep(
                    step_id="p17-execution-1",
                    title="Prepare no-write execution handoff",
                    summary=(
                        "Prepare a bounded execution result from the P16 plan "
                        "without modifying repository files."
                    ),
                    source_plan_step_ids=[],
                    files_considered=files_considered,
                    patch_preview=patch_preview,
                    tests_to_run=tests_to_run,
                    risk_notes=risk_notes,
                )
            )

        if execution_mode == "fake_execution" and len(steps) < 2:
            steps.append(
                ProjectDirectorProgrammerNoWriteExecutionStep(
                    step_id="p17-execution-2",
                    title="Record fake execution boundary",
                    summary=(
                        "Record deterministic fake execution output while keeping "
                        "file writes, patch application, and Git writes disabled."
                    ),
                    source_plan_step_ids=[],
                    files_considered=files_considered,
                    patch_preview=patch_preview
                    or ["PREVIEW ONLY: no repository file was modified."],
                    tests_to_run=tests_to_run,
                    risk_notes=risk_notes,
                )
            )

        return steps

    @classmethod
    def _patch_preview(
        cls,
        files_considered: list[str],
        *,
        execution_mode: ProgrammerNoWriteExecutionMode,
    ) -> list[str]:
        return cls._patch_preview_safety_result(
            files_considered,
            execution_mode=execution_mode,
        ).sanitized_preview

    @classmethod
    def _patch_preview_safety_result(
        cls,
        files_considered: list[str],
        *,
        execution_mode: ProgrammerNoWriteExecutionMode,
    ) -> ProjectDirectorPatchPreviewSafetyResult:
        return sanitize_patch_preview(
            cls._patch_preview_candidates(
                files_considered,
                execution_mode=execution_mode,
            )
        )

    @staticmethod
    def _patch_preview_candidates(
        files_considered: list[str],
        *,
        execution_mode: ProgrammerNoWriteExecutionMode,
    ) -> list[str]:
        if files_considered:
            return [
                f"PREVIEW ONLY: consider {path}; no repository file was modified."
                for path in files_considered[:20]
            ]
        if execution_mode == "fake_execution":
            return ["PREVIEW ONLY: no repository file was modified."]
        return []

    @staticmethod
    def _risk_notes(
        *,
        execution_mode: ProgrammerNoWriteExecutionMode,
    ) -> list[str]:
        notes = [
            "no-write execution must not be treated as implementation completion",
            "patch preview must not be treated as an applyable patch",
            "execution output must not authorize product runtime Git writes",
        ]
        if execution_mode == "controlled_no_write":
            notes.append("controlled_no_write is blocked at the API layer")
        return notes

    @staticmethod
    def _execution_action(
        result: ProjectDirectorProgrammerNoWriteExecutionResult,
        *,
        source_message_id: UUID,
    ) -> dict[str, Any]:
        return {
            "type": "p17_programmer_no_write_execution_record",
            "source_task_id": (
                str(result.source_task_id)
                if result.source_task_id is not None
                else None
            ),
            "source_message_id": str(source_message_id),
            "requested_programmer_executor": result.requested_programmer_executor,
            "execution_mode": result.execution_mode,
            "execution_status": result.execution_status,
            "programmer_agent": True,
            "controlled_programmer_execution": True,
            "no_write_execution": True,
            "executor_backed_programmer_allowed": True,
            "product_runtime_git_write_allowed": False,
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
            "execution_message_bound": True,
            "execution_summary": result.execution_summary,
            "execution_steps": [
                step.model_dump(mode="json") for step in result.execution_steps
            ],
            "patch_preview": list(result.patch_preview),
            "files_considered": list(result.files_considered),
            "tests_to_run": list(result.tests_to_run),
            "implementation_notes": list(result.implementation_notes),
            "handoff_notes": list(result.handoff_notes),
            "risk_notes": list(result.risk_notes),
            "risk_level": result.risk_level,
            "recommended_next_step": result.recommended_next_step,
            "source_plan_refs": list(result.source_plan_refs),
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
    "ConfirmedProgrammerNoWriteExecution",
    "P17_PROGRAMMER_NO_WRITE_EXECUTION_SOURCE_DETAIL",
    "ProjectDirectorProgrammerNoWriteExecutionService",
)
