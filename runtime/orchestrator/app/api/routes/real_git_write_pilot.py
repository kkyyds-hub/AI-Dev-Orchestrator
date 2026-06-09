"""P9-RGWP preview and readiness readback APIs for the real Git write pilot."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

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


router = APIRouter(
    prefix="/real-git-write-pilot",
    tags=["real-git-write-pilot"],
)

_service = RealGitWritePilotPreviewService()
_readiness_service = RealGitWritePilotReadinessService()


def get_real_git_write_pilot_preview_service() -> RealGitWritePilotPreviewService:
    return _service


def get_real_git_write_pilot_readiness_service() -> RealGitWritePilotReadinessService:
    return _readiness_service


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
