"""Delivery lifecycle diff dry-run event schema and pure builders for P4-B3.

This module is deliberately side-effect free.  It does not import repositories,
write AgentMessage rows, run Git commands, call TaskWorker, implement delivery
gates, or perform any Git write operation.  It only normalizes P4-B2 Git diff
dry-run evidence into the AgentMessage content_detail JSON contract.
"""

from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


DELIVERY_EVENT_SCHEMA_VERSION = "1.0"
DELIVERY_EVENT_CONTENT_DETAIL_MAX_LENGTH = 4_000
P4B3_FORBIDDEN_TRUE_SAFETY_FLAGS: tuple[str, ...] = (
    "runs_write_git",
    "git_add_triggered",
    "git_commit_triggered",
    "git_push_triggered",
    "pr_opened",
    "ci_triggered",
    "execution_enabled",
)


class DeliveryEventType(StrEnum):
    """P4-B3 delivery diff dry-run event types."""

    DIFF_DRY_RUN_COLLECTED = "delivery_diff_dry_run_collected"
    DIFF_DRY_RUN_SKIPPED = "delivery_diff_dry_run_skipped"
    DIFF_DRY_RUN_FAILED = "delivery_diff_dry_run_failed"


P4B3_BUILDABLE_DELIVERY_EVENT_TYPES: tuple[DeliveryEventType, ...] = (
    DeliveryEventType.DIFF_DRY_RUN_COLLECTED,
    DeliveryEventType.DIFF_DRY_RUN_SKIPPED,
    DeliveryEventType.DIFF_DRY_RUN_FAILED,
)


class DeliveryEventState(StrEnum):
    """Minimal delivery-axis states used by P4-B3 event content."""

    NONE = "none"
    DIFF_DIRTY = "diff_dirty"
    DIFF_CLEAN = "diff_clean"
    DIFF_SKIPPED = "diff_skipped"
    DIFF_FAILED = "diff_failed"


class DeliveryEventSafetyFlags(DomainModel):
    """Safety switches embedded in every delivery event content_detail."""

    runs_git: bool = False
    runs_write_git: bool = False
    git_add_triggered: bool = False
    git_commit_triggered: bool = False
    git_push_triggered: bool = False
    pr_opened: bool = False
    ci_triggered: bool = False
    execution_enabled: bool = False

    @model_validator(mode="after")
    def validate_p4b3_read_only_boundary(self) -> "DeliveryEventSafetyFlags":
        """Reject every Git write, PR, CI, or execution-enabled flag in P4-B3."""

        enabled_forbidden_flags = [
            flag_name
            for flag_name in P4B3_FORBIDDEN_TRUE_SAFETY_FLAGS
            if bool(getattr(self, flag_name))
        ]
        if enabled_forbidden_flags:
            raise ValueError(
                "P4-B3 delivery diff dry-run events must not enable write or "
                "delivery execution safety flags: "
                + ", ".join(enabled_forbidden_flags)
            )
        return self


class DeliveryEventSchema(DomainModel):
    """Structured JSON contract for one P4-B3 delivery diff dry-run event."""

    schema_version: str = DELIVERY_EVENT_SCHEMA_VERSION
    event_id: UUID = Field(default_factory=uuid4)
    event_type: DeliveryEventType
    session_id: UUID
    project_id: UUID
    task_id: UUID
    run_id: UUID
    previous_delivery_state: DeliveryEventState
    next_delivery_state: DeliveryEventState
    reason_code: str | None = Field(default=None, max_length=200)
    summary_cn: str = Field(min_length=1, max_length=2_000)
    technical_detail: str | None = Field(default=None, max_length=2_000)
    safety_flags: DeliveryEventSafetyFlags = Field(
        default_factory=DeliveryEventSafetyFlags
    )
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator(
        "reason_code",
        "summary_cn",
        "technical_detail",
        "created_by",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        """Trim text fields and collapse optional blank values."""

        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            return None
        return normalized_value

    @model_validator(mode="after")
    def validate_contract(self) -> "DeliveryEventSchema":
        """Keep schema version stable and timestamps UTC-aware."""

        if self.schema_version != DELIVERY_EVENT_SCHEMA_VERSION:
            raise ValueError(
                f"schema_version must be {DELIVERY_EVENT_SCHEMA_VERSION!r}"
            )
        object.__setattr__(self, "created_at", ensure_utc_datetime(self.created_at))
        return self

    def to_content_detail_json(self) -> str:
        """Serialize for AgentMessage.content_detail without exceeding 4000 chars."""

        payload = self.to_content_detail_dict()
        content = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        if len(content) <= DELIVERY_EVENT_CONTENT_DETAIL_MAX_LENGTH:
            return content

        compact_payload = dict(payload)
        compact_payload["technical_detail"] = _truncate_nullable_text(
            compact_payload.get("technical_detail"),
            max_length=500,
        )
        compact_payload["evidence"] = _compact_json_value(
            compact_payload.get("evidence", {}),
            max_length=1_200,
        )
        content = json.dumps(compact_payload, ensure_ascii=False, sort_keys=True)
        if len(content) <= DELIVERY_EVENT_CONTENT_DETAIL_MAX_LENGTH:
            return content

        minimal_payload = {
            "schema_version": payload["schema_version"],
            "event_id": payload["event_id"],
            "event_type": payload["event_type"],
            "session_id": payload["session_id"],
            "project_id": payload["project_id"],
            "task_id": payload["task_id"],
            "run_id": payload["run_id"],
            "previous_delivery_state": payload["previous_delivery_state"],
            "next_delivery_state": payload["next_delivery_state"],
            "reason_code": payload["reason_code"],
            "summary_cn": _truncate_nullable_text(payload["summary_cn"], max_length=500),
            "technical_detail": _truncate_nullable_text(
                payload.get("technical_detail"),
                max_length=200,
            ),
            "safety_flags": payload["safety_flags"],
            "evidence": {
                "truncated": True,
                "original_json_length": len(
                    json.dumps(payload, ensure_ascii=False, sort_keys=True)
                ),
            },
            "created_by": payload["created_by"],
        }
        content = json.dumps(minimal_payload, ensure_ascii=False, sort_keys=True)
        if len(content) <= DELIVERY_EVENT_CONTENT_DETAIL_MAX_LENGTH:
            return content

        minimal_payload["summary_cn"] = "交付事件详情过长，已保留核心审计字段。"
        minimal_payload["technical_detail"] = None
        minimal_payload["evidence"] = {"truncated": True}
        return json.dumps(minimal_payload, ensure_ascii=False, sort_keys=True)

    def to_content_detail_dict(self) -> dict[str, Any]:
        """Return the JSON-compatible P4-B3 content_detail payload."""

        return self.model_dump(mode="json", exclude={"created_at"})


class DeliveryEventBuilder:
    """Factory for standardized P4-B3 delivery diff dry-run event payloads."""

    @staticmethod
    def from_diff_dry_run_result(
        *,
        session_id: UUID,
        project_id: UUID,
        task_id: UUID,
        run_id: UUID,
        result: Any | None,
        skipped_reason_code: str | None = None,
        workspace_path: str | None = None,
        created_by: str = "TaskWorker.run_once",
        event_id: UUID | None = None,
    ) -> DeliveryEventSchema:
        """Build a collected/skipped/failed event from diff dry-run evidence."""

        if result is None:
            event_type = DeliveryEventType.DIFF_DRY_RUN_SKIPPED
            reason_code = skipped_reason_code or "worktree_path_unavailable"
            next_state = DeliveryEventState.DIFF_SKIPPED
            summary_cn = "代码改动预览已跳过：当前没有可检查的工作区。"
            technical_detail = "Git diff dry-run was skipped before running Git."
            safety_flags = DeliveryEventSafetyFlags(runs_git=False)
            evidence = {
                "source": "agent_session_worktree_diff",
                "worktree_path": workspace_path,
                "has_changes": None,
                "changed_files_count": None,
            }
        elif bool(_value(result, "ready", False)):
            event_type = DeliveryEventType.DIFF_DRY_RUN_COLLECTED
            reason_code = _value(result, "reason_code", None)
            has_changes = bool(_value(result, "has_changes", False))
            changed_files_count = int(_value(result, "changed_files_count", 0) or 0)
            next_state = (
                DeliveryEventState.DIFF_DIRTY
                if has_changes
                else DeliveryEventState.DIFF_CLEAN
            )
            if has_changes:
                summary_cn = (
                    "已完成代码改动预览：检测到 "
                    f"{changed_files_count} 个文件变更。注意：改动只是预览结果，"
                    "尚未被提交或推送。"
                )
            else:
                summary_cn = "本次执行未产生代码改动。"
            technical_detail = "Git diff dry-run completed using read-only Git commands."
            safety_flags = _safety_flags_from_result(result)
            evidence = _evidence_from_result(result)
        else:
            event_type = DeliveryEventType.DIFF_DRY_RUN_FAILED
            reason_code = _value(result, "reason_code", None) or "git_diff_dry_run_failed"
            next_state = DeliveryEventState.DIFF_FAILED
            runs_git = bool(_value(result, "runs_git", False))
            if runs_git:
                summary_cn = "代码改动预览失败：Git 只读检查未完成。"
                technical_detail = (
                    "Git diff dry-run failed during a read-only Git command."
                )
            else:
                summary_cn = "代码改动预览失败：当前工作区不可用，未运行 Git 检查。"
                technical_detail = "Git diff dry-run failed before running Git."
            safety_flags = _safety_flags_from_result(result)
            evidence = _evidence_from_result(result)

        return DeliveryEventSchema(
            event_id=event_id or uuid4(),
            event_type=event_type,
            session_id=session_id,
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            previous_delivery_state=DeliveryEventState.NONE,
            next_delivery_state=next_state,
            reason_code=reason_code,
            summary_cn=summary_cn,
            technical_detail=technical_detail,
            safety_flags=safety_flags,
            evidence=evidence,
            created_by=created_by,
        )

    @staticmethod
    def build(
        *,
        session_id: UUID,
        project_id: UUID,
        task_id: UUID,
        run_id: UUID,
        event_type: DeliveryEventType | str,
        reason_code: str | None = None,
        summary_cn: str | None = None,
        technical_detail: str | None = None,
        safety_flags: DeliveryEventSafetyFlags | None = None,
        evidence: dict[str, Any] | None = None,
        created_by: str = "TaskWorker.run_once",
    ) -> DeliveryEventSchema:
        """Build a P4-B3 delivery event while rejecting future event types."""

        try:
            normalized_event_type = DeliveryEventType(event_type)
        except ValueError as exc:
            raise ValueError(f"Unknown delivery event type: {event_type}") from exc
        if normalized_event_type not in P4B3_BUILDABLE_DELIVERY_EVENT_TYPES:
            raise ValueError(f"Not started delivery event type: {event_type}")

        next_state = {
            DeliveryEventType.DIFF_DRY_RUN_COLLECTED: DeliveryEventState.DIFF_DIRTY,
            DeliveryEventType.DIFF_DRY_RUN_SKIPPED: DeliveryEventState.DIFF_SKIPPED,
            DeliveryEventType.DIFF_DRY_RUN_FAILED: DeliveryEventState.DIFF_FAILED,
        }[normalized_event_type]
        return DeliveryEventSchema(
            event_type=normalized_event_type,
            session_id=session_id,
            project_id=project_id,
            task_id=task_id,
            run_id=run_id,
            previous_delivery_state=DeliveryEventState.NONE,
            next_delivery_state=next_state,
            reason_code=reason_code,
            summary_cn=summary_cn or _default_summary_for_event(normalized_event_type),
            technical_detail=technical_detail,
            safety_flags=safety_flags or DeliveryEventSafetyFlags(),
            evidence=evidence or {},
            created_by=created_by,
        )


def _safety_flags_from_result(result: Any) -> DeliveryEventSafetyFlags:
    """Map GitDiffDryRunResult safety fields without enabling write flags."""

    return DeliveryEventSafetyFlags(
        runs_git=bool(_value(result, "runs_git", False)),
        runs_write_git=False,
        git_add_triggered=False,
        git_commit_triggered=False,
        git_push_triggered=False,
        pr_opened=False,
        ci_triggered=False,
        execution_enabled=False,
    )


def _evidence_from_result(result: Any) -> dict[str, Any]:
    return {
        "source": _value(result, "source", None),
        "reason_code": _value(result, "reason_code", None),
        "worktree_path": _value(result, "worktree_path", None),
        "has_changes": _value(result, "has_changes", None),
        "changed_files_count": _value(result, "changed_files_count", None),
        "changed_files": list(_value(result, "changed_files", []) or []),
        "added_files": list(_value(result, "added_files", []) or []),
        "modified_files": list(_value(result, "modified_files", []) or []),
        "deleted_files": list(_value(result, "deleted_files", []) or []),
        "renamed_files": list(_value(result, "renamed_files", []) or []),
        "status_summary_cn": _value(result, "status_summary_cn", None),
        "branch_name": _value(result, "branch_name", None),
        "compare_branch": _value(result, "compare_branch", None),
        "command": _value(result, "command", None),
        "peek_command": _value(result, "peek_command", None),
        "danger_commands_applied": _value(result, "danger_commands_applied", None),
    }


def _value(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _default_summary_for_event(event_type: DeliveryEventType) -> str:
    if event_type == DeliveryEventType.DIFF_DRY_RUN_COLLECTED:
        return (
            "已完成代码改动预览。注意：改动只是预览结果，尚未被提交或推送。"
        )
    if event_type == DeliveryEventType.DIFF_DRY_RUN_SKIPPED:
        return "代码改动预览已跳过：当前没有可检查的工作区。"
    return "代码改动预览失败：无法读取工作区改动。"


def _truncate_nullable_text(value: object, *, max_length: int) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def _compact_json_value(value: object, *, max_length: int) -> object:
    content = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if len(content) <= max_length:
        return value
    return {
        "truncated": True,
        "preview": content[: max_length - 3] + "...",
        "original_json_length": len(content),
    }
