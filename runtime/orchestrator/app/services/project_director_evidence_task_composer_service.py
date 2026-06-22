"""Compose P10-B task drafts from readonly Project Director evidence."""

from __future__ import annotations

from app.domain.project_director_evidence_pack import ProjectDirectorRepoEvidencePack
from app.domain.project_director_evidence_task import (
    ProjectDirectorEvidenceTask,
    ProjectDirectorEvidenceTaskCompositionResult,
)


class ProjectDirectorEvidenceTaskComposerService:
    """Create bounded task drafts from a P10-A evidence pack."""

    _ALLOWED_FILES = [
        "runtime/orchestrator/app/domain/project_director_evidence_pack.py",
        "runtime/orchestrator/app/domain/project_director_evidence_task.py",
        "runtime/orchestrator/app/services/project_director_repo_evidence_service.py",
        "runtime/orchestrator/app/services/project_director_evidence_task_composer_service.py",
        "runtime/orchestrator/tests/test_project_director_repo_evidence_pack.py",
        "runtime/orchestrator/tests/test_project_director_evidence_task_composer.py",
    ]
    _TARGETED_TESTS = [
        "runtime/orchestrator/tests/test_project_director_repo_evidence_pack.py",
        "runtime/orchestrator/tests/test_project_director_evidence_task_composer.py",
    ]

    def compose_tasks(
        self,
        *,
        evidence_pack: ProjectDirectorRepoEvidencePack,
        user_goal: str,
    ) -> ProjectDirectorEvidenceTaskCompositionResult:
        blocked_reasons = self._blocked_reasons(evidence_pack=evidence_pack)
        common = self._common_payload(evidence_pack=evidence_pack)
        if blocked_reasons:
            return ProjectDirectorEvidenceTaskCompositionResult(
                source_evidence_pack_id=evidence_pack.evidence_pack_id,
                composition_status="blocked",
                blocked_reasons=blocked_reasons,
                **common,
            )

        evidence_ref_ids = [ref.ref_id for ref in evidence_pack.evidence_refs]
        required_reading = evidence_pack.related_files[:8]
        tasks = [
            ProjectDirectorEvidenceTask(
                source_evidence_pack_id=evidence_pack.evidence_pack_id,
                title="P10-B evidence-grounded task composer",
                objective=(
                    "Compose bounded Project Director task drafts from the P10-A "
                    "readonly evidence pack before any agent assignment."
                ),
                evidence_refs=evidence_ref_ids,
                allowed_files=list(self._ALLOWED_FILES),
                forbidden_files=list(evidence_pack.forbidden_paths),
                required_reading=required_reading,
                targeted_tests=list(self._TARGETED_TESTS),
                risk_notes=list(evidence_pack.risks),
                unknowns=list(evidence_pack.unknowns),
            ),
            ProjectDirectorEvidenceTask(
                source_evidence_pack_id=evidence_pack.evidence_pack_id,
                title="P10-C evidence-based programmer and reviewer assignment",
                objective=(
                    "Bind programmer and reviewer agent roles to evidence-grounded "
                    "tasks without starting real executors or granting product "
                    "runtime Git write access."
                ),
                evidence_refs=evidence_ref_ids,
                allowed_files=[
                    "runtime/orchestrator/app/domain/project_director_agent_assignment.py",
                    "runtime/orchestrator/app/services/project_director_agent_assignment_service.py",
                    "runtime/orchestrator/tests/test_project_director_agent_assignment.py",
                ],
                forbidden_files=list(evidence_pack.forbidden_paths),
                required_reading=required_reading,
                targeted_tests=[
                    "runtime/orchestrator/tests/test_project_director_agent_assignment.py"
                ],
                risk_notes=[
                    "Agent binding must stay separate from product runtime Git write authorization.",
                    *evidence_pack.risks,
                ],
                unknowns=list(evidence_pack.unknowns),
            ),
        ]

        return ProjectDirectorEvidenceTaskCompositionResult(
            source_evidence_pack_id=evidence_pack.evidence_pack_id,
            composition_status="composed",
            composed_tasks=tasks,
            **common,
        )

    def _blocked_reasons(
        self, *, evidence_pack: ProjectDirectorRepoEvidencePack
    ) -> list[str]:
        reasons: list[str] = []
        if not evidence_pack.evidence_refs:
            reasons.append("evidence_refs_required")
        if not evidence_pack.related_files:
            reasons.append("related_files_required")
        if evidence_pack.product_runtime_git_write_allowed:
            reasons.append("product_runtime_git_write_must_remain_forbidden")
        if evidence_pack.frontend_required:
            reasons.append("frontend_must_not_be_required")
        return reasons

    def _common_payload(
        self, *, evidence_pack: ProjectDirectorRepoEvidencePack
    ) -> dict[str, object]:
        return {
            "allowed_files": list(self._ALLOWED_FILES),
            "forbidden_files": list(evidence_pack.forbidden_paths),
            "required_reading": evidence_pack.related_files[:8],
            "targeted_tests": list(self._TARGETED_TESTS),
            "risk_notes": list(evidence_pack.risks),
            "unknowns": list(evidence_pack.unknowns),
            "user_confirmation_required": True,
            "product_runtime_git_write_allowed": False,
        }
