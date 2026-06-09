"""P9-RGWP-C preview-only API for the real Git write pilot."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError

from app.services.real_git_write_pilot_preview_service import (
    RealGitWritePilotPreview,
    RealGitWritePilotPreviewRequest,
    RealGitWritePilotPreviewService,
)


router = APIRouter(
    prefix="/real-git-write-pilot",
    tags=["real-git-write-pilot"],
)

_service = RealGitWritePilotPreviewService()


def get_real_git_write_pilot_preview_service() -> RealGitWritePilotPreviewService:
    return _service


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
