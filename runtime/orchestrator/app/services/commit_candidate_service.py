"""Business services for V4 Day13 commit-candidate draft generation."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.domain._base import utc_now
from app.domain.change_batch import ChangeBatch, ChangeBatchPreflightStatus
from app.domain.change_evidence import ChangeEvidencePackage
from app.domain.commit_candidate import (
    CommitCandidate,
    CommitCandidateLinkedDeliverable,
    CommitCandidateStatus,
    CommitCandidateVerificationSummary,
    CommitCandidateVersion,
)
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.commit_candidate_repository import CommitCandidateRepository
from app.repositories.project_repository import ProjectRepository
from app.services.diff_summary_service import (
    DiffSummaryChangeBatchNotFoundError,
    DiffSummaryProjectNotFoundError,
    DiffSummaryService,
    DiffSummaryWorkspaceNotFoundError,
)


class CommitCandidateError(ValueError):
    """Base error raised by the Day13 commit-candidate service."""


class CommitCandidateProjectNotFoundError(CommitCandidateError):
    """Raised when the target project cannot be resolved."""


class CommitCandidateBatchNotFoundError(CommitCandidateError):
    """Raised when the target change batch cannot be resolved."""


class CommitCandidateNotFoundError(CommitCandidateError):
    """Raised when no commit candidate can be found for the selected scope."""


class CommitCandidatePreflightNotReadyError(CommitCandidateError):
    """Raised when Day08 preflight has not reached a ready state."""


class CommitCandidateVerificationNotPassedError(CommitCandidateError):
    """Raised when verification evidence is missing or contains failures."""


class CommitCandidateEvidenceUnavailableError(CommitCandidateError):
    """Raised when the Day11 evidence package cannot be generated."""


class CommitCandidateService:
    """Generate and query Day13 commit-candidate draft revisions."""

    def __init__(
        self,
        *,
        commit_candidate_repository: CommitCandidateRepository,
        change_batch_repository: ChangeBatchRepository,
        project_repository: ProjectRepository,
        diff_summary_service: DiffSummaryService,
    ) -> None:
        self.commit_candidate_repository = commit_candidate_repository
        self.change_batch_repository = change_batch_repository
        self.project_repository = project_repository
        self.diff_summary_service = diff_summary_service

    def list_project_commit_candidates(self, project_id: UUID) -> list[CommitCandidate]:
        """Return project-scoped commit candidates ordered by latest activity."""

        self._ensure_project_exists(project_id)
        return self.commit_candidate_repository.list_by_project_id(project_id)

    def get_commit_candidate(self, candidate_id: UUID) -> CommitCandidate:
        """Return one commit candidate by ID."""

        candidate = self.commit_candidate_repository.get_by_id(candidate_id)
        if candidate is None:
            raise CommitCandidateNotFoundError(f"Commit candidate not found: {candidate_id}")

        return candidate

    def get_change_batch_commit_candidate(self, change_batch_id: UUID) -> CommitCandidate:
        """Return the commit candidate currently bound to one change batch."""

        self._require_change_batch(change_batch_id)
        candidate = self.commit_candidate_repository.get_by_change_batch_id(change_batch_id)
        if candidate is None:
            raise CommitCandidateNotFoundError(
                f"Commit candidate not found for change batch: {change_batch_id}"
            )

        return candidate

    def generate_commit_candidate(
        self,
        *,
        change_batch_id: UUID,
        message_title: str | None = None,
        message_body: str | None = None,
        impact_scope: list[str] | None = None,
        related_files: list[str] | None = None,
        revision_note: str | None = None,
    ) -> CommitCandidate:
        """Generate one new commit-candidate revision from preflighted evidence."""

        change_batch = self._require_change_batch(change_batch_id)
        self._ensure_preflight_ready(change_batch)
        evidence_package = self._build_evidence_package(change_batch)
        verification_summary = self._build_verification_summary(evidence_package)

        persisted_candidate = self.commit_candidate_repository.get_by_change_batch_id(
            change_batch_id
        )
        candidate_id = persisted_candidate.id if persisted_candidate else uuid4()
        next_version_number = (
            persisted_candidate.current_version_number + 1 if persisted_candidate else 1
        )
        timestamp = utc_now()

        resolved_impact_scope = self._normalize_string_list(impact_scope)
        if not resolved_impact_scope:
            resolved_impact_scope = self._build_default_impact_scope(
                change_batch=change_batch,
                evidence_package=evidence_package,
            )

        resolved_related_files = self._normalize_string_list(related_files)
        if not resolved_related_files:
            resolved_related_files = self._build_default_related_files(
                change_batch=change_batch,
                evidence_package=evidence_package,
            )

        default_message_body = self._build_default_message_body(
            change_batch=change_batch,
            evidence_package=evidence_package,
            verification_summary=verification_summary,
        )
        revision = CommitCandidateVersion(
            commit_candidate_id=candidate_id,
            version_number=next_version_number,
            message_title=(
                (message_title or "").strip()
                or self._build_default_message_title(
                    change_batch=change_batch,
                    evidence_package=evidence_package,
                )
            ),
            message_body=(message_body or "").strip() or default_message_body,
            impact_scope=resolved_impact_scope,
            related_files=resolved_related_files,
            verification_summary=verification_summary,
            related_deliverables=self._build_linked_deliverables(evidence_package),
            evidence_package_key=evidence_package.package_key,
            evidence_summary=evidence_package.summary,
            revision_note=(revision_note or "").strip() or None,
            created_at=timestamp,
        )

        if persisted_candidate is None:
            candidate = CommitCandidate(
                id=candidate_id,
                project_id=change_batch.project_id,
                change_batch_id=change_batch.id,
                change_batch_title=change_batch.title,
                status=CommitCandidateStatus.DRAFT,
                current_version_number=revision.version_number,
                versions=[revision],
                created_at=timestamp,
                updated_at=timestamp,
            )
            return self.commit_candidate_repository.create(candidate)

        candidate = persisted_candidate.model_copy(
            update={
                "change_batch_title": change_batch.title,
                "status": CommitCandidateStatus.DRAFT,
                "versions": [*persisted_candidate.versions, revision],
                "updated_at": timestamp,
            }
        )
        return self.commit_candidate_repository.update(candidate)

    def _ensure_project_exists(self, project_id: UUID) -> None:
        """Ensure the target project exists before Day13 operations."""

        if self.project_repository.get_by_id(project_id) is None:
            raise CommitCandidateProjectNotFoundError(f"Project not found: {project_id}")

    def _require_change_batch(self, change_batch_id: UUID) -> ChangeBatch:
        """Return one persisted change batch or raise a Day13-specific error."""

        change_batch = self.change_batch_repository.get_by_id(change_batch_id)
        if change_batch is None:
            raise CommitCandidateBatchNotFoundError(
                f"Change batch not found: {change_batch_id}"
            )

        self._ensure_project_exists(change_batch.project_id)
        return change_batch

    @staticmethod
    def _ensure_preflight_ready(change_batch: ChangeBatch) -> None:
        """Require that the Day08 preflight result is already ready for execution."""

        ready_statuses = {
            ChangeBatchPreflightStatus.READY_FOR_EXECUTION,
            ChangeBatchPreflightStatus.MANUAL_CONFIRMED,
        }
        preflight = change_batch.preflight
        if preflight.status not in ready_statuses or not preflight.ready_for_execution:
            raise CommitCandidatePreflightNotReadyError(
                "Change batch preflight is not ready; Day13 requires a preflight-ready batch."
            )

    def _build_evidence_package(self, change_batch: ChangeBatch) -> ChangeEvidencePackage:
        """Build and validate one Day11 evidence package for this change batch."""

        try:
            evidence_package = self.diff_summary_service.get_project_change_evidence(
                change_batch.project_id,
                change_batch_id=change_batch.id,
            )
        except (
            DiffSummaryProjectNotFoundError,
            DiffSummaryWorkspaceNotFoundError,
            DiffSummaryChangeBatchNotFoundError,
        ) as exc:
            raise CommitCandidateEvidenceUnavailableError(str(exc)) from exc

        if evidence_package.selected_change_batch_id != change_batch.id:
            raise CommitCandidateEvidenceUnavailableError(
                "Evidence package does not match the selected change batch."
            )

        return evidence_package

    @staticmethod
    def _build_verification_summary(
        evidence_package: ChangeEvidencePackage,
    ) -> CommitCandidateVerificationSummary:
        """Convert Day11 verification evidence into Day13 commit-candidate summary."""

        verification = evidence_package.verification_summary
        if verification.total_runs <= 0 or verification.passed_runs <= 0:
            raise CommitCandidateVerificationNotPassedError(
                "Verification evidence is missing; Day13 requires at least one passed run."
            )
        if verification.failed_runs > 0:
            raise CommitCandidateVerificationNotPassedError(
                "Verification contains failed runs; Day13 only accepts passed verification sets."
            )

        highlights = [
            f"{item.status.value.upper()} · {item.change_plan_title} · {item.output_summary}"
            for item in verification.runs[:8]
        ]
        return CommitCandidateVerificationSummary(
            total_runs=verification.total_runs,
            passed_runs=verification.passed_runs,
            failed_runs=verification.failed_runs,
            skipped_runs=verification.skipped_runs,
            latest_finished_at=verification.latest_finished_at,
            highlights=highlights,
        )

    @staticmethod
    def _build_default_message_title(
        *,
        change_batch: ChangeBatch,
        evidence_package: ChangeEvidencePackage,
    ) -> str:
        """Build a short review-only commit message subject."""

        title = (
            f"chore: {change_batch.title}（{evidence_package.diff_summary.metrics.changed_file_count} 文件）"
        )
        return title[:200].rstrip()

    @staticmethod
    def _build_default_message_body(
        *,
        change_batch: ChangeBatch,
        evidence_package: ChangeEvidencePackage,
        verification_summary: CommitCandidateVerificationSummary,
    ) -> str:
        """Build one default review-only commit message body."""

        lines = [
            evidence_package.summary,
            "",
            f"- 变更批次：{change_batch.title}",
            f"- 证据包：{evidence_package.package_key}",
            f"- 差异文件：{evidence_package.diff_summary.metrics.changed_file_count}",
            (
                f"- 验证结果：{verification_summary.passed_runs}/{verification_summary.total_runs}"
                " 通过（本草案阶段不执行真实 Git 提交）"
            ),
            "",
            "说明：该草案仅用于审批审阅，不执行 git commit / push / PR / merge。",
        ]
        return "\n".join(lines).strip()

    @staticmethod
    def _build_default_impact_scope(
        *,
        change_batch: ChangeBatch,
        evidence_package: ChangeEvidencePackage,
    ) -> list[str]:
        """Build one impact-scope list from plans and diff evidence."""

        impact_scope: list[str] = []
        for item in evidence_package.plan_items:
            impact_scope.append(
                f"任务《{item.task_title}》对应计划《{item.change_plan_title}》"
            )

        impact_scope.append(
            (
                "差异统计："
                f"{evidence_package.diff_summary.metrics.changed_file_count} 文件，"
                f"+{evidence_package.diff_summary.metrics.total_added_line_count} / "
                f"-{evidence_package.diff_summary.metrics.total_deleted_line_count}"
            )
        )
        impact_scope.append(f"批次摘要：{change_batch.summary}")

        return CommitCandidateService._normalize_string_list(impact_scope)[:40]

    @staticmethod
    def _build_default_related_files(
        *,
        change_batch: ChangeBatch,
        evidence_package: ChangeEvidencePackage,
    ) -> list[str]:
        """Build one related-file list by preferring Day11 key files."""

        related_files: list[str] = []
        for row in evidence_package.diff_summary.key_files:
            related_files.append(row.relative_path)
        for row in evidence_package.diff_summary.files:
            related_files.append(row.relative_path)

        if not related_files:
            for snapshot in change_batch.plan_snapshots:
                for target_file in snapshot.target_files:
                    related_files.append(target_file.relative_path)

        return CommitCandidateService._normalize_string_list(related_files)[:120]

    @staticmethod
    def _build_linked_deliverables(
        evidence_package: ChangeEvidencePackage,
    ) -> list[CommitCandidateLinkedDeliverable]:
        """Project deliverable references from Day11 evidence into Day13 draft snapshots."""

        return [
            CommitCandidateLinkedDeliverable(
                deliverable_id=item.deliverable_id,
                title=item.title,
                type=item.type,
                stage=item.stage,
                current_version_number=item.current_version_number,
                latest_version_summary=item.latest_version_summary,
            )
            for item in evidence_package.deliverables[:20]
        ]

    @staticmethod
    def _normalize_string_list(values: list[str] | None) -> list[str]:
        """Trim, deduplicate and drop blank items from optional list inputs."""

        if not values:
            return []

        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items
