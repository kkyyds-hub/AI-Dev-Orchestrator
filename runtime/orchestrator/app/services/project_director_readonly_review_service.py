"""Readonly Project Director reviewer deep-review service."""

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
from app.domain.project_director_readonly_review import (
    ProjectDirectorReadonlyReviewFinding,
    ProjectDirectorReadonlyReviewPlan,
    ProjectDirectorReadonlyReviewResult,
    ReviewMode,
)
from app.domain.task import Task
from app.repositories.project_director_message_repository import (
    ProjectDirectorMessageRepository,
)
from app.repositories.project_director_session_repository import (
    ProjectDirectorSessionRepository,
)
from app.repositories.task_repository import TaskRepository
from app.services.project_director_controlled_executor_dispatch_service import (
    P14_LIFECYCLE_RESULT_SOURCE_DETAIL,
)


P15_READONLY_REVIEW_SOURCE_DETAIL = "p15_readonly_reviewer_review"


@dataclass(frozen=True, slots=True)
class ConfirmedReadonlyReview:
    """Readonly review result and bound session message."""

    result: ProjectDirectorReadonlyReviewResult
    message: ProjectDirectorMessage | None


class ProjectDirectorReadonlyReviewService:
    """Plan and record readonly reviewer requests from P14 lifecycle evidence."""

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

    def build_plan_from_sources(
        self,
        *,
        session_id: UUID,
        source_task: Task | None,
        source_message: ProjectDirectorMessage | None,
        user_confirmed: bool,
        requested_reviewer_executor: str = "codex",
        review_mode: ReviewMode = "dry_run",
    ) -> ProjectDirectorReadonlyReviewPlan:
        """Build a no-execution readonly review plan from P14 evidence."""

        blocked_reasons: list[str] = []
        if not user_confirmed:
            blocked_reasons.append("user_confirmation_required")
        if source_task is None:
            blocked_reasons.append("source_task_missing")
        if source_message is None:
            blocked_reasons.append("p14_lifecycle_message_missing")

        if source_message is not None:
            if source_message.session_id != session_id:
                blocked_reasons.append("source_message_not_in_session")
            if source_message.source_detail != P14_LIFECYCLE_RESULT_SOURCE_DETAIL:
                blocked_reasons.append("source_message_is_not_p14_lifecycle_result")

        if source_task is not None and source_message is not None:
            if source_message.related_task_id != source_task.id and not (
                self._p14_action_value(source_message, "source_task_id")
                == str(source_task.id)
            ):
                blocked_reasons.append("source_task_not_bound_to_p14_lifecycle")
            if not self._is_safe_dry_run_task(source_task):
                blocked_reasons.append("source_task_is_not_safe_dry_run")

        if review_mode == "controlled_review":
            blocked_reasons.append("controlled_review_not_enabled_in_api")

        return ProjectDirectorReadonlyReviewPlan(
            session_id=session_id,
            source_task_id=source_task.id if source_task is not None else None,
            source_message_id=(
                source_message.id if source_message is not None else None
            ),
            p14_lifecycle_message_id=(
                source_message.id if source_message is not None else None
            ),
            user_confirmed=user_confirmed,
            requested_reviewer_executor=requested_reviewer_executor,  # type: ignore[arg-type]
            review_mode=review_mode,
            review_status="blocked" if blocked_reasons else "planned",
            review_summary=(
                "Readonly reviewer review request planned without starting an executor."
            ),
            recommended_next_step=(
                "Use dry_run or fake_review evidence before considering controlled review."
            ),
            blocked_reasons=blocked_reasons,
            risks=[
                "readonly reviewer result is not code modification completion",
                "readonly reviewer result is not product runtime Git write authorization",
                "controlled_review requires explicit safety flags outside the API",
            ],
            unknowns=[
                "real reviewer subprocess evidence is optional and not proven by dry_run",
            ],
        )

    def confirm_review(
        self,
        *,
        session_id: UUID,
        source_task_id: UUID,
        source_message_id: UUID,
        user_confirmed: bool,
        requested_reviewer_executor: str,
        review_mode: ReviewMode = "dry_run",
    ) -> ConfirmedReadonlyReview:
        """Record a planned or fake readonly review message."""

        if (
            self._session_repository is None
            or self._message_repository is None
            or self._task_repository is None
        ):
            raise ValueError("readonly review repositories are required")

        session_obj = self._session_repository.get_by_id(session_id)
        if session_obj is None:
            raise ValueError(f"Project Director session {session_id} not found")

        source_task = self._task_repository.get_by_id(source_task_id)
        if source_task is None:
            raise ValueError(f"Task {source_task_id} not found")

        source_message = self._message_repository.get_by_id(source_message_id)
        if source_message is None:
            raise ValueError(f"Project Director message {source_message_id} not found")

        plan = self.build_plan_from_sources(
            session_id=session_id,
            source_task=source_task,
            source_message=source_message,
            user_confirmed=user_confirmed,
            requested_reviewer_executor=requested_reviewer_executor,
            review_mode=review_mode,
        )
        if plan.blocked_reasons:
            raise ValueError(";".join(plan.blocked_reasons))

        result = self._result_from_plan(plan, message_bound=False)
        if review_mode == "fake_review":
            result = result.model_copy(
                update={
                    "review_status": "reviewed",
                    "review_summary": (
                        "Fake readonly reviewer found no write authorization and "
                        "confirmed P14 lifecycle evidence is reviewable."
                    ),
                    "review_findings": [
                        ProjectDirectorReadonlyReviewFinding(
                            finding_id="p15-fake-review-boundary",
                            severity="low",
                            title="Readonly boundary preserved",
                            summary=(
                                "P15 fake reviewer found product Git, worktree, "
                                "and file write flags remain false."
                            ),
                            evidence_refs=[
                                str(source_message.id),
                                str(source_task.id),
                            ],
                            recommended_action=(
                                "Keep AI Project Director total loop Partial."
                            ),
                        )
                    ],
                    "recommended_next_step": (
                        "Harden controlled reviewer output parsing before any "
                        "programmer no-write execution path."
                    ),
                }
            )

        message = self._message_repository.create(
            ProjectDirectorMessage(
                session_id=session_id,
                role=ProjectDirectorMessageRole.ASSISTANT,
                content=(
                    "已记录 P15 readonly reviewer review。该审查只读，不代表代码"
                    "修改完成，不授权 Git 写，也不代表合并或审批通过；"
                    "AI Project Director 总闭环仍为 Partial。"
                ),
                sequence_no=self._message_repository.get_next_sequence_no(
                    session_id=session_id
                ),
                intent="readonly_reviewer_review",
                related_project_id=session_obj.project_id,
                related_task_id=source_task_id,
                source=ProjectDirectorMessageSource.SYSTEM,
                source_detail=P15_READONLY_REVIEW_SOURCE_DETAIL,
                suggested_actions=[
                    self._review_action(result, source_message_id=source_message_id)
                ],
                requires_confirmation=False,
                risk_level=ProjectDirectorMessageRiskLevel.LOW,
                forbidden_actions_detected=[
                    "no_product_runtime_git_write",
                    "no_worktree_write",
                    "no_file_write",
                    "no_real_code_modification_as_pass_condition",
                    "no_git_approval_from_review_result",
                ],
            )
        )
        self._message_repository.commit()

        result = result.model_copy(update={"review_result_message_bound": True})
        return ConfirmedReadonlyReview(result=result, message=message)

    @staticmethod
    def _p14_action_value(
        source_message: ProjectDirectorMessage,
        key: str,
    ) -> Any | None:
        for action in source_message.suggested_actions:
            if not isinstance(action, dict):
                continue
            if action.get("type") != "p14_controlled_subprocess_lifecycle_result_record":
                continue
            return action.get(key)
        return None

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
    def _result_from_plan(
        plan: ProjectDirectorReadonlyReviewPlan,
        *,
        message_bound: bool,
    ) -> ProjectDirectorReadonlyReviewResult:
        data: dict[str, Any] = plan.model_dump()
        data.pop("user_confirmed", None)
        data["review_result_message_bound"] = message_bound
        return ProjectDirectorReadonlyReviewResult(**data)

    @staticmethod
    def _review_action(
        result: ProjectDirectorReadonlyReviewResult,
        *,
        source_message_id: UUID,
    ) -> dict[str, Any]:
        return {
            "type": "p15_readonly_reviewer_review_record",
            "source_task_id": (
                str(result.source_task_id)
                if result.source_task_id is not None
                else None
            ),
            "source_message_id": str(source_message_id),
            "p14_lifecycle_message_id": (
                str(result.p14_lifecycle_message_id)
                if result.p14_lifecycle_message_id is not None
                else None
            ),
            "requested_reviewer_executor": result.requested_reviewer_executor,
            "review_mode": result.review_mode,
            "review_status": result.review_status,
            "readonly_review": True,
            "reviewer_agent": True,
            "executor_backed_review_allowed": True,
            "product_runtime_git_write_allowed": False,
            "worktree_write_allowed": False,
            "file_write_allowed": False,
            "real_code_modified": False,
            "git_write_performed": False,
            "native_executor_started": False,
            "codex_started": False,
            "claude_code_started": False,
            "review_result_message_bound": True,
            "review_findings_count": len(result.review_findings),
            "risk_level": result.risk_level,
            "recommended_next_step": result.recommended_next_step,
            "ai_project_director_total_loop": "Partial",
            "blocked_reasons": list(result.blocked_reasons),
        }


__all__ = (
    "ConfirmedReadonlyReview",
    "P15_READONLY_REVIEW_SOURCE_DETAIL",
    "ProjectDirectorReadonlyReviewService",
)
