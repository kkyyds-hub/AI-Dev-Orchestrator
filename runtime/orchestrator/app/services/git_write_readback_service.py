"""In-memory GitWrite readback service for GitWrite-D.

This service records intent, preview, approval readback, and safe audit
timeline data from explicit caller input only. It does not inspect repository
state, read host configuration, read environment values, launch host processes,
persist rows, call adapters, or perform product runtime Git writes.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from pydantic import Field

from app.domain._base import DomainModel, utc_now
from app.domain.git_write import (
    GitWriteApproval,
    GitWriteApprovalDecision,
    GitWriteAuditEvent,
    GitWriteIntent,
    GitWriteIntentStatus,
    GitWritePreview,
    GitWritePreviewStatus,
    GitWriteSource,
    GitWriteTokenStatus,
    OneShotApprovalToken,
)
from app.services.git_write_adapter import (
    FakeGitWriteAdapter,
    GitWriteAdapterEvidenceRecord,
    GitWriteAdapterRequest,
)
from app.services.git_write_preview_service import (
    GitWriteChangedFileInput,
    GitWritePreviewRequest,
    GitWritePreviewService,
)


class GitWriteReadbackRecord(DomainModel):
    intent: GitWriteIntent
    preview: GitWritePreview
    approval: GitWriteApproval | None = None
    approval_summary: str | None = None
    adapter_evidence: GitWriteAdapterEvidenceRecord | None = None
    audit_events: list[GitWriteAuditEvent] = Field(default_factory=list)
    product_runtime_git_write_executed: bool = False


class GitWriteReadbackNotFoundError(LookupError):
    pass


class GitWriteReadbackConflictError(ValueError):
    pass


class GitWriteReadbackService:
    """Create and read GitWrite API records without side effects."""

    def __init__(self, preview_service: GitWritePreviewService | None = None) -> None:
        self._preview_service = preview_service or GitWritePreviewService()
        self._records: dict[str, GitWriteReadbackRecord] = {}

    def create_intent(
        self,
        *,
        workspace_id: str,
        target_branch: str,
        file_paths: list[str],
        changed_files: list[GitWriteChangedFileInput],
        allowed_branches: list[str],
        feature_flag_enabled: bool,
        intent_id: str | None = None,
        repository_id: str | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        run_id: str | None = None,
        requested_by: str | None = None,
        base_branch: str | None = None,
        commit_message: str | None = None,
        diff_text: str | None = None,
        diff_summary: str | None = None,
        force_push_requested: bool = False,
        destructive_operation_requested: bool = False,
        ci_trigger_requested: bool = False,
    ) -> GitWriteReadbackRecord:
        now = utc_now()
        safe_intent_id = intent_id or f"gitwrite-{uuid4().hex}"
        intent = GitWriteIntent(
            intent_id=safe_intent_id,
            workspace_id=workspace_id,
            repository_id=repository_id,
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            source=GitWriteSource.USER,
            requested_by=requested_by,
            target_branch=target_branch,
            base_branch=base_branch,
            file_paths=file_paths,
            commit_message=commit_message,
            created_at=now,
            updated_at=now,
        )
        preview = self._preview_service.build_preview(
            GitWritePreviewRequest(
                intent=intent,
                changed_files=changed_files,
                allowed_branches=allowed_branches,
                feature_flag_enabled=feature_flag_enabled,
                diff_text=diff_text,
                diff_summary=diff_summary,
                force_push_requested=force_push_requested,
                destructive_operation_requested=destructive_operation_requested,
                ci_trigger_requested=ci_trigger_requested,
                audit_event_planned=True,
                product_runtime_git_write_executed=False,
                requested_at=now,
            )
        )
        intent = intent.model_copy(
            update={
                "status": (
                    GitWriteIntentStatus.PREVIEW_READY
                    if preview.status == GitWritePreviewStatus.READY
                    else GitWriteIntentStatus.BLOCKED
                ),
                "safety_snapshot": preview.safety_snapshot,
                "updated_at": now,
            }
        )
        record = GitWriteReadbackRecord(
            intent=intent,
            preview=preview,
            audit_events=[
                self._audit_event(
                    intent_id=intent.intent_id,
                    event_type="git_write.intent_created",
                    summary="Intent readback recorded.",
                ),
                self._audit_event(
                    intent_id=intent.intent_id,
                    event_type="git_write.preview_generated",
                    summary="Preview readback generated; later gates remain pending.",
                ),
            ],
        )
        self._records[intent.intent_id] = record
        return record

    def get_intent(self, intent_id: str) -> GitWriteReadbackRecord:
        record = self._records.get(intent_id)
        if record is None:
            raise GitWriteReadbackNotFoundError(intent_id)
        return record

    def record_approval(
        self,
        intent_id: str,
        *,
        actor: str,
        approval_note: str | None = None,
    ) -> GitWriteReadbackRecord:
        record = self.get_intent(intent_id)
        if record.preview.status != GitWritePreviewStatus.READY:
            raise GitWriteReadbackConflictError("preview is not ready")
        if record.preview.safety_snapshot.preview_gates_passed() is not True:
            raise GitWriteReadbackConflictError("preview safety gates are not passing")

        now = utc_now()
        approval = GitWriteApproval(
            approval_id=f"approval-{record.intent.intent_id}",
            intent_id=record.intent.intent_id,
            preview_id=record.preview.preview_id,
            decision=GitWriteApprovalDecision.PENDING,
            decided_by=actor,
            decided_at=now,
            approval_note=approval_note,
            one_shot_token=OneShotApprovalToken(
                token_id=f"approval-record-{uuid4().hex}",
                token_hint="approval readback hint",
                intent_id=record.intent.intent_id,
                preview_id=record.preview.preview_id,
                status=GitWriteTokenStatus.PENDING,
                issued_at=now,
                expires_at=now + timedelta(minutes=15),
            ),
            safety_snapshot=record.preview.safety_snapshot,
        )
        approval_summary = (
            "User confirmation record has been generated; no commit or push has run."
        )
        updated_record = record.model_copy(
            update={
                "approval": approval,
                "approval_summary": approval_summary,
                "audit_events": [
                    *record.audit_events,
                    self._audit_event(
                        intent_id=record.intent.intent_id,
                        event_type="git_write.approval_recorded",
                        summary="User confirmation record captured; no write operation has run.",
                    ),
                ],
                "product_runtime_git_write_executed": False,
            }
        )
        self._records[intent_id] = updated_record
        return updated_record

    def get_audit_events(self, intent_id: str) -> list[GitWriteAuditEvent]:
        return self.get_intent(intent_id).audit_events

    def record_fake_adapter_evidence(
        self,
        intent_id: str,
        request: GitWriteAdapterRequest,
        adapter: FakeGitWriteAdapter | None = None,
    ) -> GitWriteReadbackRecord:
        record = self.get_intent(intent_id)
        if request.intent_id != record.intent.intent_id:
            raise GitWriteReadbackConflictError("adapter request intent mismatch")
        if request.preview_id != record.preview.preview_id:
            raise GitWriteReadbackConflictError("adapter request preview mismatch")

        evidence = (adapter or FakeGitWriteAdapter()).build_fake_evidence(request)
        updated_record = record.model_copy(
            update={
                "adapter_evidence": evidence,
                "audit_events": [
                    *record.audit_events,
                    self._audit_event(
                        intent_id=record.intent.intent_id,
                        event_type="git_write.fake_adapter_evidence_recorded",
                        summary=(
                            "Fake adapter evidence readback recorded; no product runtime "
                            "Git write operation has run."
                        ),
                    ),
                ],
                "product_runtime_git_write_executed": False,
            }
        )
        self._records[intent_id] = updated_record
        return updated_record

    def _audit_event(
        self,
        *,
        intent_id: str,
        event_type: str,
        summary: str,
    ) -> GitWriteAuditEvent:
        return GitWriteAuditEvent(
            event_id=f"event-{uuid4().hex}",
            intent_id=intent_id,
            event_type=event_type,
            timestamp=utc_now(),
            safe_summary=summary,
            metadata_count=0,
        )
