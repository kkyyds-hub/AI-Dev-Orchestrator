"""Workbench account-profile endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.services.account_profile_service import (
    AccountProfileService,
    AccountProfileSummary,
)


class AccountProfileResponse(BaseModel):
    """Safe account profile response for the workbench account modal."""

    account_id: str
    display_name: str
    notification_email: str
    login_method: str
    default_role: str
    source: Literal["saved_config", "env", "default"]

    @classmethod
    def from_summary(cls, summary: AccountProfileSummary) -> "AccountProfileResponse":
        return cls(
            account_id=summary.account_id,
            display_name=summary.display_name,
            notification_email=summary.notification_email,
            login_method=summary.login_method,
            default_role=summary.default_role,
            source=summary.source,
        )


class AccountProfileUpdateRequest(BaseModel):
    """Editable account profile fields."""

    display_name: str = Field(min_length=1, max_length=120)
    notification_email: str = Field(default="", max_length=240)


def get_account_profile_service() -> AccountProfileService:
    """Create one account-profile service dependency."""

    return AccountProfileService()


router = APIRouter(prefix="/account", tags=["account-profile"])


@router.get(
    "/profile",
    response_model=AccountProfileResponse,
    summary="Get the local workbench account profile",
)
def get_account_profile(
    account_profile_service: Annotated[
        AccountProfileService,
        Depends(get_account_profile_service),
    ],
) -> AccountProfileResponse:
    """Return the local product account profile without operational internals."""

    return AccountProfileResponse.from_summary(
        account_profile_service.get_profile(),
    )


@router.put(
    "/profile",
    response_model=AccountProfileResponse,
    summary="Update the local workbench account profile",
)
def update_account_profile(
    request: AccountProfileUpdateRequest,
    account_profile_service: Annotated[
        AccountProfileService,
        Depends(get_account_profile_service),
    ],
) -> AccountProfileResponse:
    """Persist editable account profile fields."""

    try:
        summary = account_profile_service.update_profile(
            display_name=request.display_name,
            notification_email=request.notification_email,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return AccountProfileResponse.from_summary(summary)
