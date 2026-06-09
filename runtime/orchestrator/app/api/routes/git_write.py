"""GitWrite-D readback API.

The endpoints in this module expose intent, preview, approval readback, and
safe audit timeline data. They do not inspect repository state, read
environment values, call adapters, or perform product runtime Git writes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.domain.git_write import (
    GitWriteApproval,
    GitWriteAuditEvent,
    GitWriteIntent,
    GitWritePreview,
    GitWriteSafetyGateCheck,
    GitWriteSafetyGateSnapshot,
    GitWriteTokenStatus,
    OneShotApprovalToken,
)
from app.services.git_write_preview_service import GitWriteChangedFileInput
from app.services.git_write_adapter import GitWriteAdapterEvidenceRecord
from app.services.git_write_readback_service import (
    GitWriteReadbackConflictError,
    GitWriteReadbackNotFoundError,
    GitWriteReadbackRecord,
    GitWriteReadbackService,
)


router = APIRouter(prefix="/git-write", tags=["git-write"])

_service = GitWriteReadbackService()


class GitWriteCreateIntentRequest(BaseModel):
    intent_id: str | None = Field(default=None, max_length=120)
    workspace_id: str = Field(min_length=1, max_length=120)
    repository_id: str | None = Field(default=None, max_length=120)
    project_id: str | None = Field(default=None, max_length=120)
    task_id: str | None = Field(default=None, max_length=120)
    run_id: str | None = Field(default=None, max_length=120)
    requested_by: str | None = Field(default=None, max_length=120)
    target_branch: str
    base_branch: str | None = None
    file_paths: list[str] = Field(min_length=1)
    changed_files: list[GitWriteChangedFileInput] = Field(min_length=1)
    allowed_branches: list[str] = Field(default_factory=list)
    feature_flag_enabled: bool = False
    diff_text: str | None = Field(default=None, max_length=50_000)
    diff_summary: str | None = Field(default=None, max_length=2_000)
    commit_message: str | None = Field(default=None, max_length=500)
    force_push_requested: bool = False
    destructive_operation_requested: bool = False
    ci_trigger_requested: bool = False

    @field_validator(
        "intent_id",
        "repository_id",
        "project_id",
        "task_id",
        "run_id",
        "requested_by",
        "base_branch",
        "diff_text",
        "diff_summary",
        "commit_message",
        mode="before",
    )
    @classmethod
    def trim_optional_string(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class GitWriteApprovalRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    approval_note: str | None = Field(default=None, max_length=1_000)

    @field_validator("actor", mode="before")
    @classmethod
    def trim_actor(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("approval_note", mode="before")
    @classmethod
    def trim_approval_note(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class GitWriteSafetyGateCheckResponse(BaseModel):
    gate_name: str
    status: str
    passed: bool
    block_reason: str | None
    safe_summary: str | None
    checked_at: datetime | None

    @classmethod
    def from_domain(
        cls,
        check: GitWriteSafetyGateCheck,
    ) -> "GitWriteSafetyGateCheckResponse":
        return cls(
            gate_name=check.gate_name.value,
            status=check.status.value,
            passed=check.passed,
            block_reason=(
                check.block_reason.value if check.block_reason is not None else None
            ),
            safe_summary=check.safe_summary,
            checked_at=check.checked_at,
        )


class GitWriteSafetySnapshotResponse(BaseModel):
    gate_checks: list[GitWriteSafetyGateCheckResponse]
    all_passed: bool
    preview_gates_passed: bool
    blocking_reasons: list[str]
    evaluated_at: datetime

    @classmethod
    def from_domain(
        cls,
        snapshot: GitWriteSafetyGateSnapshot,
    ) -> "GitWriteSafetySnapshotResponse":
        return cls(
            gate_checks=[
                GitWriteSafetyGateCheckResponse.from_domain(check)
                for check in snapshot.gate_checks
            ],
            all_passed=snapshot.all_passed,
            preview_gates_passed=snapshot.preview_gates_passed(),
            blocking_reasons=[reason.value for reason in snapshot.blocking_reasons],
            evaluated_at=snapshot.evaluated_at,
        )


class GitWriteIntentResponse(BaseModel):
    intent_id: str
    workspace_id: str
    repository_id: str | None
    project_id: str | None
    task_id: str | None
    run_id: str | None
    requested_by: str | None
    target_branch: str
    base_branch: str | None
    file_paths: list[str]
    commit_message: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, intent: GitWriteIntent) -> "GitWriteIntentResponse":
        return cls(
            intent_id=intent.intent_id,
            workspace_id=intent.workspace_id,
            repository_id=intent.repository_id,
            project_id=intent.project_id,
            task_id=intent.task_id,
            run_id=intent.run_id,
            requested_by=intent.requested_by,
            target_branch=intent.target_branch,
            base_branch=intent.base_branch,
            file_paths=intent.file_paths,
            commit_message=intent.commit_message,
            status=intent.status.value,
            created_at=intent.created_at,
            updated_at=intent.updated_at,
        )


class GitWritePreviewFileResponse(BaseModel):
    path: str
    change_type: str
    additions: int
    deletions: int
    reviewed: bool
    contains_secret: bool
    safe_summary: str | None


class GitWriteRollbackPlanResponse(BaseModel):
    plan_id: str
    summary: str
    restore_branch_hint: str | None
    restore_commit_hint: str | None
    generated_at: datetime


class GitWritePreviewResponse(BaseModel):
    preview_id: str
    intent_id: str
    status: str
    target_branch: str
    files: list[GitWritePreviewFileResponse]
    diff_summary: str | None
    commit_message_preview: str | None
    rollback_plan: GitWriteRollbackPlanResponse | None
    safety_snapshot: GitWriteSafetySnapshotResponse
    created_at: datetime

    @classmethod
    def from_domain(cls, preview: GitWritePreview) -> "GitWritePreviewResponse":
        return cls(
            preview_id=preview.preview_id,
            intent_id=preview.intent_id,
            status=preview.status.value,
            target_branch=preview.target_branch,
            files=[
                GitWritePreviewFileResponse(
                    path=file.path,
                    change_type=file.change_type,
                    additions=file.additions,
                    deletions=file.deletions,
                    reviewed=file.reviewed,
                    contains_secret=file.contains_secret,
                    safe_summary=file.safe_summary,
                )
                for file in preview.files
            ],
            diff_summary=preview.diff_summary,
            commit_message_preview=preview.commit_message_preview,
            rollback_plan=(
                GitWriteRollbackPlanResponse(
                    plan_id=preview.rollback_plan.plan_id,
                    summary=preview.rollback_plan.summary,
                    restore_branch_hint=preview.rollback_plan.restore_branch_hint,
                    restore_commit_hint=preview.rollback_plan.restore_commit_hint,
                    generated_at=preview.rollback_plan.generated_at,
                )
                if preview.rollback_plan is not None
                else None
            ),
            safety_snapshot=GitWriteSafetySnapshotResponse.from_domain(
                preview.safety_snapshot,
            ),
            created_at=preview.created_at,
        )


class OneShotApprovalTokenResponse(BaseModel):
    token_id: str
    token_hint: str
    status: GitWriteTokenStatus
    expires_at: datetime

    @classmethod
    def from_domain(
        cls,
        token: OneShotApprovalToken,
    ) -> "OneShotApprovalTokenResponse":
        return cls(
            token_id=token.token_id,
            token_hint=token.token_hint,
            status=token.status,
            expires_at=token.expires_at,
        )


class GitWriteApprovalResponse(BaseModel):
    approval_id: str
    intent_id: str
    preview_id: str
    decision: str
    decided_by: str | None
    decided_at: datetime | None
    approval_note: str | None
    one_shot_token: OneShotApprovalTokenResponse | None

    @classmethod
    def from_domain(
        cls,
        approval: GitWriteApproval | None,
    ) -> "GitWriteApprovalResponse | None":
        if approval is None:
            return None
        return cls(
            approval_id=approval.approval_id,
            intent_id=approval.intent_id,
            preview_id=approval.preview_id,
            decision=approval.decision.value,
            decided_by=approval.decided_by,
            decided_at=approval.decided_at,
            approval_note=approval.approval_note,
            one_shot_token=(
                OneShotApprovalTokenResponse.from_domain(approval.one_shot_token)
                if approval.one_shot_token is not None
                else None
            ),
        )


class GitWriteAuditEventResponse(BaseModel):
    event_id: str
    intent_id: str
    event_type: str
    timestamp: datetime
    safe_summary: str | None
    append_only: bool
    metadata_count: int

    @classmethod
    def from_domain(cls, event: GitWriteAuditEvent) -> "GitWriteAuditEventResponse":
        return cls(
            event_id=event.event_id,
            intent_id=event.intent_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            safe_summary=event.safe_summary,
            append_only=event.append_only,
            metadata_count=event.metadata_count,
        )


class GitWriteAdapterEvidenceResponse(BaseModel):
    evidence_id: str
    intent_id: str
    preview_id: str
    adapter_mode: str
    status: str
    fake_evidence_ready: bool
    fake_execution_recorded: bool
    product_runtime_git_write_executed: bool
    operation_plan_id: str
    rollback_plan_id: str
    safe_summary: str
    blocking_reason: str | None
    audit_event_summaries: list[str]
    created_at: datetime

    @classmethod
    def from_domain(
        cls,
        evidence: GitWriteAdapterEvidenceRecord | None,
    ) -> "GitWriteAdapterEvidenceResponse | None":
        if evidence is None:
            return None
        return cls(
            evidence_id=evidence.evidence_id,
            intent_id=evidence.intent_id,
            preview_id=evidence.preview_id,
            adapter_mode=evidence.adapter_mode.value,
            status=evidence.status.value,
            fake_evidence_ready=evidence.fake_evidence_ready,
            fake_execution_recorded=evidence.fake_execution_recorded,
            product_runtime_git_write_executed=evidence.product_runtime_git_write_executed,
            operation_plan_id=evidence.operation_plan_id,
            rollback_plan_id=evidence.rollback_plan_id,
            safe_summary=evidence.safe_summary,
            blocking_reason=(
                evidence.blocking_reason.value
                if evidence.blocking_reason is not None
                else None
            ),
            audit_event_summaries=evidence.audit_event_summaries,
            created_at=evidence.created_at,
        )


class GitWriteReadbackResponse(BaseModel):
    intent: GitWriteIntentResponse
    preview: GitWritePreviewResponse
    safety_snapshot: GitWriteSafetySnapshotResponse
    rollback_plan: GitWriteRollbackPlanResponse | None
    approval: GitWriteApprovalResponse | None
    approval_summary: str | None
    adapter_evidence: GitWriteAdapterEvidenceResponse | None
    audit_timeline: list[GitWriteAuditEventResponse]
    product_runtime_git_write_executed: bool

    @classmethod
    def from_record(cls, record: GitWriteReadbackRecord) -> "GitWriteReadbackResponse":
        preview = GitWritePreviewResponse.from_domain(record.preview)
        return cls(
            intent=GitWriteIntentResponse.from_domain(record.intent),
            preview=preview,
            safety_snapshot=preview.safety_snapshot,
            rollback_plan=preview.rollback_plan,
            approval=GitWriteApprovalResponse.from_domain(record.approval),
            approval_summary=record.approval_summary,
            adapter_evidence=GitWriteAdapterEvidenceResponse.from_domain(
                record.adapter_evidence,
            ),
            audit_timeline=[
                GitWriteAuditEventResponse.from_domain(event)
                for event in record.audit_events
            ],
            product_runtime_git_write_executed=record.product_runtime_git_write_executed,
        )


def get_git_write_readback_service() -> GitWriteReadbackService:
    return _service


@router.post(
    "/intents",
    response_model=GitWriteReadbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_git_write_intent(
    request: GitWriteCreateIntentRequest,
    service: Annotated[
        GitWriteReadbackService,
        Depends(get_git_write_readback_service),
    ],
) -> GitWriteReadbackResponse:
    record = service.create_intent(
        intent_id=request.intent_id,
        workspace_id=request.workspace_id,
        repository_id=request.repository_id,
        project_id=request.project_id,
        task_id=request.task_id,
        run_id=request.run_id,
        requested_by=request.requested_by,
        target_branch=request.target_branch,
        base_branch=request.base_branch,
        file_paths=request.file_paths,
        changed_files=request.changed_files,
        allowed_branches=request.allowed_branches,
        feature_flag_enabled=request.feature_flag_enabled,
        diff_text=request.diff_text,
        diff_summary=request.diff_summary,
        commit_message=request.commit_message,
        force_push_requested=request.force_push_requested,
        destructive_operation_requested=request.destructive_operation_requested,
        ci_trigger_requested=request.ci_trigger_requested,
    )
    return GitWriteReadbackResponse.from_record(record)


@router.get(
    "/intents/{intent_id}",
    response_model=GitWriteReadbackResponse,
)
def get_git_write_intent(
    intent_id: str,
    service: Annotated[
        GitWriteReadbackService,
        Depends(get_git_write_readback_service),
    ],
) -> GitWriteReadbackResponse:
    try:
        return GitWriteReadbackResponse.from_record(service.get_intent(intent_id))
    except GitWriteReadbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail="GitWrite intent not found") from exc


@router.post(
    "/intents/{intent_id}/approve",
    response_model=GitWriteReadbackResponse,
)
def record_git_write_approval(
    intent_id: str,
    request: GitWriteApprovalRequest,
    service: Annotated[
        GitWriteReadbackService,
        Depends(get_git_write_readback_service),
    ],
) -> GitWriteReadbackResponse:
    try:
        record = service.record_approval(
            intent_id,
            actor=request.actor,
            approval_note=request.approval_note,
        )
    except GitWriteReadbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail="GitWrite intent not found") from exc
    except GitWriteReadbackConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return GitWriteReadbackResponse.from_record(record)


@router.get(
    "/intents/{intent_id}/audit",
    response_model=list[GitWriteAuditEventResponse],
)
def get_git_write_audit(
    intent_id: str,
    service: Annotated[
        GitWriteReadbackService,
        Depends(get_git_write_readback_service),
    ],
) -> list[GitWriteAuditEventResponse]:
    try:
        return [
            GitWriteAuditEventResponse.from_domain(event)
            for event in service.get_audit_events(intent_id)
        ]
    except GitWriteReadbackNotFoundError as exc:
        raise HTTPException(status_code=404, detail="GitWrite intent not found") from exc
