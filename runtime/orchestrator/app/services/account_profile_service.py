"""Local account profile service for the workbench account surface."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Literal

from app.core.config import settings


AccountProfileSource = Literal["saved_config", "env", "default"]


@dataclass(frozen=True, slots=True)
class AccountProfileSummary:
    """Safe account profile returned to the frontend."""

    account_id: str
    display_name: str
    notification_email: str
    login_method: str
    default_role: str
    source: AccountProfileSource


@dataclass(frozen=True, slots=True)
class SavedAccountProfile:
    """Persisted account profile fields."""

    display_name: str
    notification_email: str


class AccountProfileService:
    """Read and persist the single-user local workbench account profile."""

    def __init__(self, *, config_path: Path | None = None) -> None:
        self.config_path = (
            config_path
            if config_path is not None
            else settings.runtime_data_dir / "account" / "profile.json"
        )

    def get_profile(self) -> AccountProfileSummary:
        """Return the current safe account profile."""

        saved = self._load_saved_profile()
        if saved is not None:
            return self._build_summary(
                display_name=saved.display_name,
                notification_email=saved.notification_email,
                source="saved_config",
            )

        env_display_name = self._normalize_optional_str(
            os.getenv("AIDO_ACCOUNT_DISPLAY_NAME"),
        )
        env_email = self._normalize_optional_str(os.getenv("AIDO_ACCOUNT_EMAIL"))
        if env_display_name or env_email:
            return self._build_summary(
                display_name=env_display_name or "本地用户",
                notification_email=env_email or "",
                source="env",
            )

        return self._build_summary(
            display_name="本地用户",
            notification_email="",
            source="default",
        )

    def update_profile(
        self,
        *,
        display_name: str,
        notification_email: str,
    ) -> AccountProfileSummary:
        """Persist the account profile and return the new safe profile."""

        normalized_display_name = self._normalize_required_str(
            display_name,
            field_name="display_name",
            max_length=120,
        )
        normalized_notification_email = self._normalize_optional_str(
            notification_email,
            max_length=240,
        )

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(
                {
                    "display_name": normalized_display_name,
                    "notification_email": normalized_notification_email,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return self.get_profile()

    def _load_saved_profile(self) -> SavedAccountProfile | None:
        if not self.config_path.exists():
            return None

        try:
            payload = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        if not isinstance(payload, dict):
            return None

        display_name = self._normalize_optional_str(payload.get("display_name"))
        if not display_name:
            return None

        notification_email = self._normalize_optional_str(
            payload.get("notification_email"),
        )
        return SavedAccountProfile(
            display_name=display_name,
            notification_email=notification_email or "",
        )

    def _build_summary(
        self,
        *,
        display_name: str,
        notification_email: str,
        source: AccountProfileSource,
    ) -> AccountProfileSummary:
        return AccountProfileSummary(
            account_id="local-workbench-user",
            display_name=display_name,
            notification_email=notification_email,
            login_method="本地账户",
            default_role="项目所有者",
            source=source,
        )

    @staticmethod
    def _normalize_optional_str(
        value: object,
        *,
        max_length: int = 240,
    ) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        return normalized[:max_length]

    def _normalize_required_str(
        self,
        value: object,
        *,
        field_name: str,
        max_length: int,
    ) -> str:
        normalized = self._normalize_optional_str(value, max_length=max_length)
        if not normalized:
            raise ValueError(f"{field_name} is required.")
        return normalized
