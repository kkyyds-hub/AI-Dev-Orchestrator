"""P9-E fake-only runtime readback and launch request API."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, field_validator

from app.domain.executor_runtime import (
    ExecutorRuntimeProcessSnapshot,
    ExecutorRuntimeSession,
    ExecutorRuntimeUsageSnapshot,
    ExecutorRuntimeWorkspaceBinding,
    RuntimeEvent,
    RuntimeEventPayload,
    RuntimeEventStreamSnapshot,
)
from app.domain.executor_runtime_safety import (
    ExecutorLaunchRequest,
    RuntimeBudgetGateInput,
    RuntimeConcurrencyGateInput,
    RuntimeFeatureFlagPolicy,
    RuntimeLaunchRequestStatus,
    RuntimeSafetyEvaluationInput,
    RuntimeSafetyGateCheck,
    RuntimeSafetyGateSnapshot,
    RuntimeWorkspaceGateInput,
)
from app.external_executors.actual_readback import (
    RealExecutorLaunchReadbackBuilder,
    RealExecutorLaunchReadbackRequest,
    RealExecutorLaunchReadbackResponse,
)
from app.services.controlled_runtime_service import ControlledRuntimeService


class RuntimeProcessResponse(BaseModel):
    process_id: int | None
    exit_code: int | None
    started_at: datetime | None
    finished_at: datetime | None
    last_activity_at: datetime | None
    heartbeat_at: datetime | None

    @classmethod
    def from_domain(
        cls,
        process: ExecutorRuntimeProcessSnapshot,
    ) -> "RuntimeProcessResponse":
        return cls(
            process_id=process.process_id,
            exit_code=process.exit_code,
            started_at=process.started_at,
            finished_at=process.finished_at,
            last_activity_at=process.last_activity_at,
            heartbeat_at=process.heartbeat_at,
        )


class RuntimeUsageResponse(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: Decimal | None
    cost_currency: str | None

    @classmethod
    def from_domain(cls, usage: ExecutorRuntimeUsageSnapshot) -> "RuntimeUsageResponse":
        return cls(
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost=usage.estimated_cost,
            cost_currency=usage.cost_currency,
        )


class RuntimeWorkspaceResponse(BaseModel):
    workspace_id: str | None
    workspace_path_hint: str | None
    repository_id: str | None
    branch_name: str | None
    worktree_id: str | None
    workspace_bound: bool

    @classmethod
    def from_domain(
        cls,
        workspace: ExecutorRuntimeWorkspaceBinding,
    ) -> "RuntimeWorkspaceResponse":
        return cls(
            workspace_id=workspace.workspace_id,
            workspace_path_hint=workspace.workspace_path_hint,
            repository_id=workspace.repository_id,
            branch_name=workspace.branch_name,
            worktree_id=workspace.worktree_id,
            workspace_bound=workspace.workspace_bound,
        )


class RuntimeSessionResponse(BaseModel):
    session_id: str
    executor_id: str
    launch_preview_id: str | None
    project_id: str | None
    task_id: str | None
    run_id: str | None
    state: str
    source: str
    workspace: RuntimeWorkspaceResponse
    process: RuntimeProcessResponse
    usage: RuntimeUsageResponse
    exit_reason: str | None
    result_summary: str | None
    error_summary: str | None
    blocking_reasons: list[str]
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_domain(cls, session: ExecutorRuntimeSession) -> "RuntimeSessionResponse":
        return cls(
            session_id=session.session_id,
            executor_id=session.executor_id,
            launch_preview_id=session.launch_preview_id,
            project_id=session.project_id,
            task_id=session.task_id,
            run_id=session.run_id,
            state=session.state.value,
            source=session.source.value,
            workspace=RuntimeWorkspaceResponse.from_domain(session.workspace),
            process=RuntimeProcessResponse.from_domain(session.process),
            usage=RuntimeUsageResponse.from_domain(session.usage),
            exit_reason=session.exit_reason.value if session.exit_reason is not None else None,
            result_summary=session.result_summary,
            error_summary=session.error_summary,
            blocking_reasons=session.blocking_reasons,
            created_by=session.created_by,
            created_at=session.created_at,
            updated_at=session.updated_at,
            started_at=session.started_at,
            finished_at=session.finished_at,
        )


class RuntimeEventPayloadResponse(BaseModel):
    message: str | None
    reason_code: str | None
    state: str | None
    metadata_count: int

    @classmethod
    def from_domain(cls, payload: RuntimeEventPayload) -> "RuntimeEventPayloadResponse":
        return cls(
            message=payload.message,
            reason_code=payload.reason_code,
            state=payload.state.value if payload.state is not None else None,
            metadata_count=payload.metadata_count,
        )


class RuntimeEventResponse(BaseModel):
    event_id: str
    session_id: str
    event_type: str
    timestamp: datetime
    payload: RuntimeEventPayloadResponse
    append_only: bool

    @classmethod
    def from_domain(cls, event: RuntimeEvent) -> "RuntimeEventResponse":
        return cls(
            event_id=event.event_id,
            session_id=event.session_id,
            event_type=event.event_type.value,
            timestamp=event.timestamp,
            payload=RuntimeEventPayloadResponse.from_domain(event.payload),
            append_only=event.append_only,
        )


class RuntimeEventStreamResponse(BaseModel):
    session_id: str
    events: list[RuntimeEventResponse]
    total: int

    @classmethod
    def from_domain(
        cls,
        stream: RuntimeEventStreamSnapshot,
    ) -> "RuntimeEventStreamResponse":
        return cls(
            session_id=stream.session_id,
            events=[RuntimeEventResponse.from_domain(event) for event in stream.events],
            total=stream.total or 0,
        )


class RuntimeSafetyGateCheckResponse(BaseModel):
    gate_name: str
    status: str
    passed: bool
    block_reason: str | None
    safe_summary: str | None
    checked_at: datetime | None

    @classmethod
    def from_domain(
        cls,
        check: RuntimeSafetyGateCheck,
    ) -> "RuntimeSafetyGateCheckResponse":
        return cls(
            gate_name=check.gate_name.value,
            status=check.status.value,
            passed=check.passed,
            block_reason=check.block_reason.value if check.block_reason is not None else None,
            safe_summary=check.safe_summary,
            checked_at=check.checked_at,
        )


class RuntimeSafetyGateSnapshotResponse(BaseModel):
    gate_checks: list[RuntimeSafetyGateCheckResponse]
    all_passed: bool
    blocking_reasons: list[str]
    evaluated_at: datetime

    @classmethod
    def from_domain(
        cls,
        snapshot: RuntimeSafetyGateSnapshot,
    ) -> "RuntimeSafetyGateSnapshotResponse":
        return cls(
            gate_checks=[
                RuntimeSafetyGateCheckResponse.from_domain(check)
                for check in snapshot.gate_checks
            ],
            all_passed=snapshot.all_passed,
            blocking_reasons=[reason.value for reason in snapshot.blocking_reasons],
            evaluated_at=snapshot.evaluated_at,
        )


class RuntimeLaunchRequestResponse(BaseModel):
    request_id: str
    executor_id: str
    launch_preview_id: str
    project_id: str | None
    task_id: str | None
    run_id: str | None
    requested_by: str | None
    status: str
    safety_snapshot: RuntimeSafetyGateSnapshotResponse
    human_confirmation_required: bool
    created_at: datetime
    expires_at: datetime | None
    approved_at: datetime | None
    consumed_at: datetime | None
    blocked_reasons: list[str]

    @classmethod
    def from_domain(
        cls,
        request: ExecutorLaunchRequest,
    ) -> "RuntimeLaunchRequestResponse":
        return cls(
            request_id=request.request_id,
            executor_id=request.executor_id,
            launch_preview_id=request.launch_preview_id,
            project_id=request.project_id,
            task_id=request.task_id,
            run_id=request.run_id,
            requested_by=request.requested_by,
            status=request.status.value,
            safety_snapshot=RuntimeSafetyGateSnapshotResponse.from_domain(
                request.safety_snapshot,
            ),
            human_confirmation_required=request.human_confirmation_required,
            created_at=request.created_at,
            expires_at=request.expires_at,
            approved_at=request.approved_at,
            consumed_at=request.consumed_at,
            blocked_reasons=[reason.value for reason in request.blocked_reasons],
        )


class CreateLaunchRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executor_id: str
    launch_preview_id: str
    project_id: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    requested_by: str | None = None
    human_confirmed: bool = False
    executor_ready: bool = False
    launch_preview_ready: bool = False
    workspace_bound: bool = False
    workspace_path_hint: str | None = None
    estimated_cost: Decimal | None = None
    session_budget_limit: Decimal | None = None
    daily_budget_remaining: Decimal | None = None
    active_session_count: int = 0
    max_concurrent_sessions: int = 1
    timeout_configured: bool = False
    cancellation_supported: bool = False
    audit_event_ready: bool = False
    executor_runtime_enabled: bool = False

    @field_validator(
        "executor_id",
        "launch_preview_id",
        "project_id",
        "task_id",
        "run_id",
        "requested_by",
        "workspace_path_hint",
        mode="before",
    )
    @classmethod
    def trim_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    def to_safety_input(self) -> RuntimeSafetyEvaluationInput:
        return RuntimeSafetyEvaluationInput(
            feature_flags=RuntimeFeatureFlagPolicy(
                executor_runtime_enabled=self.executor_runtime_enabled,
            ),
            executor_ready=self.executor_ready,
            launch_preview_ready=self.launch_preview_ready,
            workspace=RuntimeWorkspaceGateInput(
                workspace_bound=self.workspace_bound,
                workspace_path_hint=self.workspace_path_hint,
            ),
            budget=RuntimeBudgetGateInput(
                estimated_cost=self.estimated_cost,
                session_budget_limit=self.session_budget_limit,
                daily_budget_remaining=self.daily_budget_remaining,
            ),
            concurrency=RuntimeConcurrencyGateInput(
                active_session_count=self.active_session_count,
                max_concurrent_sessions=self.max_concurrent_sessions,
            ),
            human_confirmed=self.human_confirmed,
            timeout_configured=self.timeout_configured,
            cancellation_supported=self.cancellation_supported,
            audit_event_ready=self.audit_event_ready,
        )


class ConfirmLaunchRequestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_by: str = ""
    confirmation_text: str | None = None

    @field_validator("approved_by", "confirmation_text", mode="before")
    @classmethod
    def trim_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class CancelRuntimeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class InMemoryLaunchRequestRegistry:
    def __init__(self) -> None:
        self._requests: dict[str, ExecutorLaunchRequest] = {}
        self._session_ids: list[str] = []

    def create(self, request: ExecutorLaunchRequest) -> ExecutorLaunchRequest:
        stored = request.model_copy(deep=True)
        self._requests[stored.request_id] = stored
        return stored.model_copy(deep=True)

    def get(self, request_id: str) -> ExecutorLaunchRequest | None:
        request = self._requests.get(request_id.strip())
        if request is None:
            return None
        return request.model_copy(deep=True)

    def approve(self, request_id: str) -> ExecutorLaunchRequest | None:
        request = self.get(request_id)
        if request is None:
            return None

        approved = request.model_copy(
            update={
                "status": RuntimeLaunchRequestStatus.APPROVED,
                "approved_at": _utc_now(),
            },
            deep=True,
        )
        self._requests[approved.request_id] = approved.model_copy(deep=True)
        return approved

    def record_session(self, session_id: str) -> None:
        if session_id not in self._session_ids:
            self._session_ids.append(session_id)

    def session_ids(self) -> list[str]:
        return list(self._session_ids)


_runtime_service = ControlledRuntimeService()
_launch_request_registry = InMemoryLaunchRequestRegistry()
_real_executor_launch_readback_builder = RealExecutorLaunchReadbackBuilder()


def get_controlled_runtime_service() -> ControlledRuntimeService:
    return _runtime_service


def get_launch_request_registry() -> InMemoryLaunchRequestRegistry:
    return _launch_request_registry


def get_real_executor_launch_readback_builder() -> RealExecutorLaunchReadbackBuilder:
    return _real_executor_launch_readback_builder


router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.post(
    "/real-executor/launch-readback",
    response_model=RealExecutorLaunchReadbackResponse,
    summary="Read back real executor launch safety preview",
)
def build_real_executor_launch_readback(
    request_input: RealExecutorLaunchReadbackRequest,
    builder: Annotated[
        RealExecutorLaunchReadbackBuilder,
        Depends(get_real_executor_launch_readback_builder),
    ],
) -> RealExecutorLaunchReadbackResponse:
    return builder.build(request_input)


@router.get(
    "/sessions",
    response_model=list[RuntimeSessionResponse],
    summary="List fake runtime sessions",
)
def list_runtime_sessions(
    service: Annotated[
        ControlledRuntimeService,
        Depends(get_controlled_runtime_service),
    ],
    registry: Annotated[
        InMemoryLaunchRequestRegistry,
        Depends(get_launch_request_registry),
    ],
) -> list[RuntimeSessionResponse]:
    sessions: list[RuntimeSessionResponse] = []
    for session_id in registry.session_ids():
        session = service.get_session(session_id)
        if session is not None:
            sessions.append(RuntimeSessionResponse.from_domain(session))
    return sessions


@router.get(
    "/sessions/{session_id}",
    response_model=RuntimeSessionResponse,
    summary="Get one fake runtime session",
)
def get_runtime_session(
    session_id: str,
    service: Annotated[
        ControlledRuntimeService,
        Depends(get_controlled_runtime_service),
    ],
) -> RuntimeSessionResponse:
    session = service.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Runtime session not found",
        )
    return RuntimeSessionResponse.from_domain(session)


@router.get(
    "/sessions/{session_id}/events",
    response_model=RuntimeEventStreamResponse,
    summary="Get one fake runtime session event stream",
)
def get_runtime_session_events(
    session_id: str,
    service: Annotated[
        ControlledRuntimeService,
        Depends(get_controlled_runtime_service),
    ],
) -> RuntimeEventStreamResponse:
    if service.get_session(session_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Runtime session not found",
        )
    return RuntimeEventStreamResponse.from_domain(service.events_for_session(session_id))


@router.post(
    "/launch-requests",
    response_model=RuntimeLaunchRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a fake-only runtime launch request",
)
def create_launch_request(
    request_input: CreateLaunchRequestInput,
    registry: Annotated[
        InMemoryLaunchRequestRegistry,
        Depends(get_launch_request_registry),
    ],
) -> RuntimeLaunchRequestResponse:
    safety_snapshot = request_input.to_safety_input().evaluate()
    request = ExecutorLaunchRequest(
        request_id=_new_id("runtime-launch-request"),
        executor_id=request_input.executor_id,
        launch_preview_id=request_input.launch_preview_id,
        project_id=request_input.project_id,
        task_id=request_input.task_id,
        run_id=request_input.run_id,
        requested_by=request_input.requested_by,
        status=(
            RuntimeLaunchRequestStatus.AWAITING_CONFIRMATION
            if safety_snapshot.all_passed
            else RuntimeLaunchRequestStatus.BLOCKED
        ),
        safety_snapshot=safety_snapshot,
        human_confirmation_required=True,
        created_at=_utc_now(),
    )
    return RuntimeLaunchRequestResponse.from_domain(registry.create(request))


@router.get(
    "/launch-requests/{request_id}",
    response_model=RuntimeLaunchRequestResponse,
    summary="Get one fake-only runtime launch request",
)
def get_launch_request(
    request_id: str,
    registry: Annotated[
        InMemoryLaunchRequestRegistry,
        Depends(get_launch_request_registry),
    ],
) -> RuntimeLaunchRequestResponse:
    request = registry.get(request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Runtime launch request not found",
        )
    return RuntimeLaunchRequestResponse.from_domain(request)


@router.post(
    "/launch-requests/{request_id}/confirm",
    response_model=RuntimeSessionResponse,
    summary="Confirm a fake-only runtime launch request",
)
def confirm_launch_request(
    request_id: str,
    confirmation: ConfirmLaunchRequestInput,
    service: Annotated[
        ControlledRuntimeService,
        Depends(get_controlled_runtime_service),
    ],
    registry: Annotated[
        InMemoryLaunchRequestRegistry,
        Depends(get_launch_request_registry),
    ],
) -> RuntimeSessionResponse:
    request = registry.get(request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Runtime launch request not found",
        )
    if not confirmation.approved_by:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Launch confirmation is required",
        )
    if not request.safety_snapshot.all_passed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime safety gates failed",
        )

    approved = registry.approve(request.request_id)
    if approved is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Runtime launch request not found",
        )

    session = service.launch(approved)
    registry.record_session(session.session_id)
    return RuntimeSessionResponse.from_domain(session)


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=RuntimeSessionResponse,
    summary="Cancel one fake runtime session",
)
def cancel_runtime_session(
    session_id: str,
    service: Annotated[
        ControlledRuntimeService,
        Depends(get_controlled_runtime_service),
    ],
    _: CancelRuntimeInput | None = None,
) -> RuntimeSessionResponse:
    session = service.cancel(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Runtime session not found",
        )
    return RuntimeSessionResponse.from_domain(session)


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)
