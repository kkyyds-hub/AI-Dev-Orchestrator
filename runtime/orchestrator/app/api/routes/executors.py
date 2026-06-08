"""Read-only executor readiness endpoints for P8."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.domain.executor_config import (
    ExecutorBinaryDiscoveryStrategy,
    ExecutorConfigSource,
    ExecutorLaunchPreview,
    ExecutorLaunchSafetyFlags,
    ExecutorLoginStatus,
    ExecutorPermissionModel,
    ExecutorProvider,
    ExecutorStatus,
)
from app.domain.executor_config import (
    ExecutorCapability,
    ExecutorConfigDiscovery,
    ExecutorProfile,
)
from app.services.executor_config_discovery_service import (
    ExecutorConfigDiscoveryService,
)
from app.services.executor_launch_preview_service import (
    ExecutorLaunchPreviewRequest,
    ExecutorLaunchPreviewService,
)


class ExecutorCapabilityResponse(BaseModel):
    code_fix: bool
    test_fix: bool
    backend_domain: bool
    api_implementation: bool
    frontend_implementation: bool
    documentation: bool
    ledger_evidence: bool
    route_planning: bool
    design_explanation: bool
    git_read_only: bool
    git_write: bool
    shell_execution: bool
    file_system_write: bool
    requires_network: bool
    requires_auth_token: bool
    max_context_tokens: int | None

    @classmethod
    def from_domain(cls, capability: ExecutorCapability) -> "ExecutorCapabilityResponse":
        return cls(
            code_fix=capability.code_fix,
            test_fix=capability.test_fix,
            backend_domain=capability.backend_domain,
            api_implementation=capability.api_implementation,
            frontend_implementation=capability.frontend_implementation,
            documentation=capability.documentation,
            ledger_evidence=capability.ledger_evidence,
            route_planning=capability.route_planning,
            design_explanation=capability.design_explanation,
            git_read_only=capability.git_read_only,
            git_write=False,
            shell_execution=capability.shell_execution,
            file_system_write=capability.file_system_write,
            requires_network=capability.requires_network,
            requires_auth_token=capability.requires_auth_token,
            max_context_tokens=capability.max_context_tokens,
        )


class ExecutorConfigDiscoveryResponse(BaseModel):
    source: ExecutorConfigSource
    cli_installed: bool
    binary_path_hint: str | None
    cli_version: str | None
    login_status: ExecutorLoginStatus
    default_model: str | None
    permission_mode: ExecutorPermissionModel | None
    native_config_valid: bool
    env_var_count: int
    token_configured: bool
    last_checked_at: datetime | None
    discovery_error: str | None

    @classmethod
    def from_domain(
        cls,
        discovery: ExecutorConfigDiscovery,
    ) -> "ExecutorConfigDiscoveryResponse":
        return cls(
            source=discovery.source,
            cli_installed=discovery.cli_installed,
            binary_path_hint=discovery.binary_path_hint,
            cli_version=discovery.cli_version,
            login_status=discovery.login_status,
            default_model=discovery.default_model,
            permission_mode=discovery.permission_mode,
            native_config_valid=discovery.native_config_valid,
            env_var_count=discovery.env_var_count,
            token_configured=discovery.token_configured,
            last_checked_at=discovery.last_checked_at,
            discovery_error=discovery.discovery_error,
        )


class ExecutorProfileResponse(BaseModel):
    executor_id: str
    display_name: str
    description: str | None
    provider: ExecutorProvider
    binary_name: str | None
    binary_discovery_strategy: ExecutorBinaryDiscoveryStrategy
    capabilities: ExecutorCapabilityResponse
    config_discovery: ExecutorConfigDiscoveryResponse
    permission_model: ExecutorPermissionModel
    status: ExecutorStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, profile: ExecutorProfile) -> "ExecutorProfileResponse":
        return cls(
            executor_id=profile.executor_id,
            display_name=profile.display_name,
            description=profile.description,
            provider=profile.provider,
            binary_name=profile.binary_name,
            binary_discovery_strategy=profile.binary_discovery_strategy,
            capabilities=ExecutorCapabilityResponse.from_domain(profile.capabilities),
            config_discovery=ExecutorConfigDiscoveryResponse.from_domain(
                profile.config_discovery,
            ),
            permission_model=profile.permission_model,
            status=profile.status,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )




class ExecutorLaunchPreviewRequestBody(BaseModel):
    operation_intent: str | None = None
    project_id: str | None = None
    task_id: str | None = None
    model_name: str | None = None
    workspace_bound: bool = False
    launch_cwd_hint: str | None = None
    require_human_confirmation: bool = True

    def to_domain(self) -> ExecutorLaunchPreviewRequest:
        return ExecutorLaunchPreviewRequest(
            operation_intent=self.operation_intent,
            project_id=self.project_id,
            task_id=self.task_id,
            model_name=self.model_name,
            workspace_bound=self.workspace_bound,
            launch_cwd_hint=self.launch_cwd_hint,
            require_human_confirmation=self.require_human_confirmation,
        )


class ExecutorLaunchSafetyFlagsResponse(BaseModel):
    no_secret_exposure: bool
    launch_preview_only: bool
    no_external_process_launch: bool
    no_product_runtime_git_write: bool
    requires_human_confirmation_before_p9: bool

    @classmethod
    def from_domain(
        cls,
        safety_flags: ExecutorLaunchSafetyFlags,
    ) -> "ExecutorLaunchSafetyFlagsResponse":
        return cls(
            no_secret_exposure=safety_flags.no_secret_exposure,
            launch_preview_only=safety_flags.launch_preview_only,
            no_external_process_launch=safety_flags.no_external_process_launch,
            no_product_runtime_git_write=safety_flags.no_product_runtime_git_write,
            requires_human_confirmation_before_p9=(
                safety_flags.requires_human_confirmation_before_p9
            ),
        )


class ExecutorLaunchPreviewResponse(BaseModel):
    ready: bool
    reason_code: str | None
    executor_id: str
    launch_command_preview: str
    launch_cwd_hint: str | None
    workspace_bound: bool
    env_var_count: int
    token_configured: bool
    permission_mode: ExecutorPermissionModel | None
    model_name: str | None
    estimated_cost_warning: str | None
    blocking_reasons: list[str]
    safety_flags: ExecutorLaunchSafetyFlagsResponse
    contract_kind: str

    @classmethod
    def from_domain(cls, preview: ExecutorLaunchPreview) -> "ExecutorLaunchPreviewResponse":
        return cls(
            ready=preview.ready,
            reason_code=preview.reason_code,
            executor_id=preview.executor_id,
            launch_command_preview=preview.launch_command_preview,
            launch_cwd_hint=preview.launch_cwd_hint,
            workspace_bound=preview.workspace_bound,
            env_var_count=preview.env_var_count,
            token_configured=preview.token_configured,
            permission_mode=preview.permission_mode,
            model_name=preview.model_name,
            estimated_cost_warning=preview.estimated_cost_warning,
            blocking_reasons=preview.blocking_reasons,
            safety_flags=ExecutorLaunchSafetyFlagsResponse.from_domain(
                preview.safety_flags,
            ),
            contract_kind=preview.contract_kind,
        )


class ExecutorRegistryResponse(BaseModel):
    profiles: list[ExecutorProfileResponse]
    total: int
    available_count: int

    @classmethod
    def from_profiles(
        cls,
        profiles: list[ExecutorProfile],
    ) -> "ExecutorRegistryResponse":
        return cls(
            profiles=[ExecutorProfileResponse.from_domain(profile) for profile in profiles],
            total=len(profiles),
            available_count=sum(
                1 for profile in profiles if profile.status == ExecutorStatus.AVAILABLE
            ),
        )


class ExecutorReadinessResponse(BaseModel):
    executor_id: str
    ready: bool
    status: ExecutorStatus
    blocking_reasons: list[str]
    safe_summary: str
    config_discovery: ExecutorConfigDiscoveryResponse
    capabilities: ExecutorCapabilityResponse

    @classmethod
    def from_profile(cls, profile: ExecutorProfile) -> "ExecutorReadinessResponse":
        ready = profile.status == ExecutorStatus.AVAILABLE
        return cls(
            executor_id=profile.executor_id,
            ready=ready,
            status=profile.status,
            blocking_reasons=build_blocking_reasons(profile.status),
            safe_summary=build_safe_summary(profile.status),
            config_discovery=ExecutorConfigDiscoveryResponse.from_domain(
                profile.config_discovery,
            ),
            capabilities=ExecutorCapabilityResponse.from_domain(profile.capabilities),
        )


def get_executor_config_discovery_service() -> ExecutorConfigDiscoveryService:
    """Create the read-only executor discovery service dependency."""

    return ExecutorConfigDiscoveryService()




def get_executor_launch_preview_service(
    discovery_service: Annotated[
        ExecutorConfigDiscoveryService,
        Depends(get_executor_config_discovery_service),
    ],
) -> ExecutorLaunchPreviewService:
    """Create the preview-only executor launch service dependency."""

    return ExecutorLaunchPreviewService(discovery_service=discovery_service)


router = APIRouter(prefix="/executors", tags=["executors"])


@router.get(
    "",
    response_model=ExecutorRegistryResponse,
    summary="List executor readiness metadata",
)
def list_executors(
    service: Annotated[
        ExecutorConfigDiscoveryService,
        Depends(get_executor_config_discovery_service),
    ],
) -> ExecutorRegistryResponse:
    snapshot = service.get_registry_snapshot()
    return ExecutorRegistryResponse.from_profiles(snapshot.profiles)


@router.get(
    "/available",
    response_model=ExecutorRegistryResponse,
    summary="List available executor readiness metadata",
)
def list_available_executors(
    service: Annotated[
        ExecutorConfigDiscoveryService,
        Depends(get_executor_config_discovery_service),
    ],
) -> ExecutorRegistryResponse:
    return ExecutorRegistryResponse.from_profiles(service.available_profiles())


@router.get(
    "/{executor_id}",
    response_model=ExecutorProfileResponse,
    summary="Get one executor readiness profile",
)
def get_executor_profile(
    executor_id: str,
    service: Annotated[
        ExecutorConfigDiscoveryService,
        Depends(get_executor_config_discovery_service),
    ],
) -> ExecutorProfileResponse:
    profile = service.get_profile(executor_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Executor profile not found",
        )
    return ExecutorProfileResponse.from_domain(profile)


@router.get(
    "/{executor_id}/readiness",
    response_model=ExecutorReadinessResponse,
    summary="Get one executor readiness summary",
)
def get_executor_readiness(
    executor_id: str,
    service: Annotated[
        ExecutorConfigDiscoveryService,
        Depends(get_executor_config_discovery_service),
    ],
) -> ExecutorReadinessResponse:
    profile = service.get_profile(executor_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Executor profile not found",
        )
    return ExecutorReadinessResponse.from_profile(profile)


@router.post(
    "/{executor_id}/launch-preview",
    response_model=ExecutorLaunchPreviewResponse,
    summary="Build a preview-only executor launch contract",
)
def build_executor_launch_preview(
    executor_id: str,
    service: Annotated[
        ExecutorLaunchPreviewService,
        Depends(get_executor_launch_preview_service),
    ],
    request: ExecutorLaunchPreviewRequestBody | None = None,
) -> ExecutorLaunchPreviewResponse:
    preview = service.build_preview(
        executor_id,
        request.to_domain() if request is not None else None,
    )
    if preview is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Executor profile not found",
        )
    return ExecutorLaunchPreviewResponse.from_domain(preview)


def build_blocking_reasons(status_value: ExecutorStatus) -> list[str]:
    if status_value == ExecutorStatus.AVAILABLE:
        return []
    if status_value == ExecutorStatus.NOT_INSTALLED:
        return ["executor_not_installed"]
    if status_value == ExecutorStatus.NOT_CONFIGURED:
        return ["executor_not_configured"]
    if status_value == ExecutorStatus.DISABLED:
        return ["executor_disabled"]
    return ["executor_status_unknown"]


def build_safe_summary(status_value: ExecutorStatus) -> str:
    if status_value == ExecutorStatus.AVAILABLE:
        return "Executor readiness metadata is available for later human-confirmed steps."
    if status_value == ExecutorStatus.NOT_INSTALLED:
        return "Executor is not marked as installed by the safe metadata source."
    if status_value == ExecutorStatus.NOT_CONFIGURED:
        return "Executor is not marked as configured by the safe metadata source."
    if status_value == ExecutorStatus.DISABLED:
        return "Executor is disabled in the safe metadata source."
    return "Executor readiness is unknown from the safe metadata source."
