"""P9-RGWP readback APIs for the real Git write pilot."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.services.real_git_write_pilot_approval_service import (
    RealGitWritePilotApprovalReadback,
    RealGitWritePilotApprovalReadbackRequest,
    RealGitWritePilotApprovalReadbackService,
)
from app.services.real_git_write_pilot_dry_run_plan_service import (
    RealGitWritePilotDryRunPlan,
    RealGitWritePilotDryRunPlanRequest,
    RealGitWritePilotDryRunPlanService,
)
from app.services.real_git_write_pilot_preview_service import (
    RealGitWritePilotPreview,
    RealGitWritePilotPreviewRequest,
    RealGitWritePilotPreviewService,
)
from app.services.real_git_write_pilot_readiness_service import (
    RealGitWritePilotReadinessReadback,
    RealGitWritePilotReadinessRequest,
    RealGitWritePilotReadinessService,
)
from app.services.real_git_write_pilot_token_readback_service import (
    RealGitWritePilotTokenReadback,
    RealGitWritePilotTokenReadbackRequest,
    RealGitWritePilotTokenReadbackService,
)


router = APIRouter(
    prefix="/real-git-write-pilot",
    tags=["real-git-write-pilot"],
)

_service = RealGitWritePilotPreviewService()
_readiness_service = RealGitWritePilotReadinessService()
_dry_run_plan_service = RealGitWritePilotDryRunPlanService()
_approval_readback_service = RealGitWritePilotApprovalReadbackService()
_token_readback_service = RealGitWritePilotTokenReadbackService()


def get_real_git_write_pilot_preview_service() -> RealGitWritePilotPreviewService:
    return _service


def get_real_git_write_pilot_readiness_service() -> RealGitWritePilotReadinessService:
    return _readiness_service


def get_real_git_write_pilot_dry_run_plan_service() -> RealGitWritePilotDryRunPlanService:
    return _dry_run_plan_service


def get_real_git_write_pilot_approval_readback_service() -> (
    RealGitWritePilotApprovalReadbackService
):
    return _approval_readback_service


def get_real_git_write_pilot_token_readback_service() -> (
    RealGitWritePilotTokenReadbackService
):
    return _token_readback_service


@router.post(
    "/preview",
    response_model=RealGitWritePilotPreview,
    status_code=status.HTTP_200_OK,
)
def build_real_git_write_pilot_preview(
    request: RealGitWritePilotPreviewRequest,
    service: Annotated[
        RealGitWritePilotPreviewService,
        Depends(get_real_git_write_pilot_preview_service),
    ],
) -> RealGitWritePilotPreview:
    try:
        return service.build_preview(request)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="real Git write pilot preview validation failed",
        ) from exc


@router.post(
    "/readiness",
    response_model=RealGitWritePilotReadinessReadback,
    status_code=status.HTTP_200_OK,
)
def build_real_git_write_pilot_readiness(
    request: RealGitWritePilotReadinessRequest,
    service: Annotated[
        RealGitWritePilotReadinessService,
        Depends(get_real_git_write_pilot_readiness_service),
    ],
) -> RealGitWritePilotReadinessReadback:
    try:
        return service.build_readiness(request)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="real Git write pilot readiness validation failed",
        ) from exc


@router.post(
    "/dry-run-plan",
    response_model=RealGitWritePilotDryRunPlan,
    status_code=status.HTTP_200_OK,
)
def build_real_git_write_pilot_dry_run_plan(
    request: RealGitWritePilotDryRunPlanRequest,
    service: Annotated[
        RealGitWritePilotDryRunPlanService,
        Depends(get_real_git_write_pilot_dry_run_plan_service),
    ],
) -> RealGitWritePilotDryRunPlan:
    try:
        return service.build_plan(request)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="real Git write pilot dry-run plan validation failed",
        ) from exc


@router.post(
    "/approval-readback",
    response_model=RealGitWritePilotApprovalReadback,
    status_code=status.HTTP_200_OK,
)
def build_real_git_write_pilot_approval_readback(
    request: RealGitWritePilotApprovalReadbackRequest,
    service: Annotated[
        RealGitWritePilotApprovalReadbackService,
        Depends(get_real_git_write_pilot_approval_readback_service),
    ],
) -> RealGitWritePilotApprovalReadback:
    try:
        return service.build_readback(request)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="real Git write pilot approval readback validation failed",
        ) from exc


@router.post(
    "/token-readback",
    response_model=RealGitWritePilotTokenReadback,
    status_code=status.HTTP_200_OK,
)
def build_real_git_write_pilot_token_readback(
    request: RealGitWritePilotTokenReadbackRequest,
    service: Annotated[
        RealGitWritePilotTokenReadbackService,
        Depends(get_real_git_write_pilot_token_readback_service),
    ],
) -> RealGitWritePilotTokenReadback:
    try:
        return service.build_readback(request)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="real Git write pilot token readback validation failed",
        ) from exc
