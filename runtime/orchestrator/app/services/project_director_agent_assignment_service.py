"""P10-C dry-run programmer/reviewer agent assignment service."""

from __future__ import annotations

from hashlib import sha1

from app.domain.project_director_agent_assignment import (
    ProjectDirectorAgentAssignment,
    ProjectDirectorAssignedAgent,
)
from app.domain.project_director_evidence_task import (
    ProjectDirectorEvidenceTaskCompositionResult,
)


class ProjectDirectorAgentAssignmentService:
    """Bind programmer and reviewer roles without starting executors."""

    def assign_agents(
        self,
        *,
        task_composition: ProjectDirectorEvidenceTaskCompositionResult,
    ) -> ProjectDirectorAgentAssignment:
        source_task_ids = [
            f"task:{index}:{sha1(task.title.encode('utf-8')).hexdigest()[:8]}"
            for index, task in enumerate(task_composition.composed_tasks, start=1)
        ]
        assignment_id = self._assignment_id(
            source_evidence_pack_id=task_composition.source_evidence_pack_id,
            source_task_ids=source_task_ids,
        )
        blocked_reasons = self._blocked_reasons(task_composition=task_composition)
        common = {
            "assignment_id": assignment_id,
            "source_evidence_pack_id": task_composition.source_evidence_pack_id,
            "source_task_ids": source_task_ids,
            "product_runtime_git_write_allowed": False,
            "frontend_required": False,
            "native_executor_started": False,
            "codex_started": False,
            "claude_code_started": False,
            "risks": [
                "Executor-backed role binding is not product runtime Git write approval.",
                *task_composition.risk_notes,
            ],
            "unknowns": list(task_composition.unknowns),
        }
        if blocked_reasons:
            return ProjectDirectorAgentAssignment(
                assignment_status="blocked",
                blocked_reasons=blocked_reasons,
                **common,
            )

        return ProjectDirectorAgentAssignment(
            assignment_status="assigned",
            programmer_agent=ProjectDirectorAssignedAgent(
                role="programmer",
                agent_kind="executor_backed_implementation_worker",
                executor_backed=True,
                readonly=False,
                write_authorized=False,
                responsibilities=[
                    "Implement only files allowed by the evidence-grounded task.",
                    "Run targeted tests named by the task composer.",
                    "Keep product runtime Git write disabled.",
                ],
            ),
            reviewer_agent=ProjectDirectorAssignedAgent(
                role="reviewer",
                agent_kind="executor_backed_readonly_reviewer",
                executor_backed=True,
                readonly=True,
                write_authorized=False,
                responsibilities=[
                    "Read repository evidence and diffs.",
                    "Review targeted test output and safety boundaries.",
                    "Do not mutate repository state during readonly review.",
                ],
            ),
            programmer_executor_backed=True,
            reviewer_executor_backed=True,
            readonly_review_required=True,
            director_permanent_executor=False,
            reviewer_readonly=True,
            **common,
        )

    def _blocked_reasons(
        self, *, task_composition: ProjectDirectorEvidenceTaskCompositionResult
    ) -> list[str]:
        reasons: list[str] = []
        if task_composition.composition_status != "composed":
            reasons.append("task_composition_must_be_composed")
        if not task_composition.composed_tasks:
            reasons.append("composed_tasks_required")
        if task_composition.product_runtime_git_write_allowed:
            reasons.append("product_runtime_git_write_must_remain_forbidden")
        return reasons

    def _assignment_id(
        self, *, source_evidence_pack_id: str, source_task_ids: list[str]
    ) -> str:
        seed = "|".join([source_evidence_pack_id, *source_task_ids])
        return f"p10-c-{sha1(seed.encode('utf-8')).hexdigest()[:12]}"
