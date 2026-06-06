"""Pure P4-F human approval gate evidence contract and builder.

This module is deliberately side-effect free. It does not run Git commands,
call TaskWorker, write AgentMessage rows, expose API schemas, mutate database
tables, query repositories, or perform git add/commit/push/PR operations. It
only evaluates existing P4-C/P4-D evidence plus explicit user confirmation
facts into human approval gate evidence.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel, ensure_utc_datetime, utc_now


DELIVERY_HUMAN_APPROVAL_SOURCE = "delivery_human_approval"

HUMAN_APPROVAL_SCOPE_GIT_ADD_COMMIT_PREVIEW = "git_add_commit_preview"
HUMAN_APPROVAL_ACTION_APPROVE_GIT_ADD_COMMIT_PREVIEW = (
    "approve_git_add_commit_preview"
)

P4F_FORBIDDEN_TRUE_SAFETY_FLAGS: tuple[str, ...] = (
    "runs_git",
    "runs_write_git",
    "git_add_triggered",
    "git_commit_triggered",
    "git_push_triggered",
    "pr_opened",
    "ci_triggered",
    "execution_enabled",
    "operation_applied",
    "gate_allows_write",
)

P4F_REASON_SUMMARIES_CN: dict[str, str] = {
    "agent_session_missing": "会话信息缺失，无法记录用户确认。",
    "operation_dry_run_missing": "提交预览缺失，无法记录用户确认。",
    "operation_dry_run_not_ready": "提交预览未就绪，无法记录用户确认。",
    "delivery_gate_evidence_missing": "交付前检查缺失，无法记录用户确认。",
    "delivery_gate_not_ready": "交付前检查未通过，无法记录用户确认。",
    "user_confirmation_not_allowed": "当前不能进入用户确认。",
    "write_gate_unexpectedly_enabled": "检测到写入授权异常，无法记录用户确认。",
    "unsupported_approval_action": "用户确认动作不受支持。",
    "approval_actor_missing": "缺少确认用户，无法记录用户确认。",
    "approval_scope_missing": "缺少确认范围，无法记录用户确认。",
    "approval_scope_unsupported": "确认范围不受支持，无法记录用户确认。",
    "approval_scope_mismatch": "确认范围与提交预览不一致，无法记录用户确认。",
    "approval_request_id_missing": "缺少确认请求编号，无法记录用户确认。",
    "approval_timestamp_missing": "缺少确认时间，无法记录用户确认。",
    "approval_expiry_missing": "缺少确认过期时间，无法记录用户确认。",
    "approval_expired": "用户确认已过期，无法进入下一阶段检查。",
    "approval_already_applied": "用户确认已被使用，无法重复进入下一阶段检查。",
    "approval_revoked": "用户确认已撤销，无法进入下一阶段检查。",
    "approval_confirmation_missing": "缺少明确确认内容，无法记录用户确认。",
    "changed_files_mismatch": "用户确认的文件列表与证据不一致，无法记录用户确认。",
    "commit_message_mismatch": "用户确认的提交说明与证据不一致，无法记录用户确认。",
    "write_already_triggered": "检测到写操作标记异常，无法记录用户确认。",
}


class HumanApprovalGateScope(StrEnum):
    """Stable confirmation scope values allowed by P4-F."""

    GIT_ADD_COMMIT_PREVIEW = HUMAN_APPROVAL_SCOPE_GIT_ADD_COMMIT_PREVIEW


class HumanApprovalGateAction(StrEnum):
    """Stable confirmation action values allowed by P4-F."""

    APPROVE_GIT_ADD_COMMIT_PREVIEW = (
        HUMAN_APPROVAL_ACTION_APPROVE_GIT_ADD_COMMIT_PREVIEW
    )


class HumanApprovalGateSafetyFlags(DomainModel):
    """P4-F safety flags.

    P4-F may record that a human approved the preview, but it must never allow
    writes or report that Git operations were applied.
    """

    runs_git: bool = False
    runs_write_git: bool = False
    git_add_triggered: bool = False
    git_commit_triggered: bool = False
    git_push_triggered: bool = False
    pr_opened: bool = False
    ci_triggered: bool = False
    execution_enabled: bool = False
    operation_applied: bool = False
    approval_granted: bool = False
    approval_applied: bool = False
    approval_revoked: bool = False
    approval_expired: bool = False
    gate_allows_write: bool = False
    gate_allows_next_guardrail: bool = False

    @model_validator(mode="after")
    def validate_p4f_no_execution_boundary(
        self,
    ) -> "HumanApprovalGateSafetyFlags":
        enabled_forbidden_flags = [
            flag_name
            for flag_name in P4F_FORBIDDEN_TRUE_SAFETY_FLAGS
            if bool(getattr(self, flag_name))
        ]
        if enabled_forbidden_flags:
            raise ValueError(
                "P4-F human approval gate must not execute Git, enable "
                "delivery writes, allow writes, or apply operations: "
                + ", ".join(enabled_forbidden_flags)
            )

        if self.gate_allows_next_guardrail and not self.approval_granted:
            raise ValueError(
                "P4-F gate_allows_next_guardrail requires approval_granted"
            )
        if self.gate_allows_next_guardrail and (
            self.approval_applied or self.approval_revoked or self.approval_expired
        ):
            raise ValueError(
                "P4-F gate_allows_next_guardrail requires an unused, active approval"
            )
        return self


class HumanApprovalRecord(DomainModel):
    """Auditable human confirmation record for the approved preview."""

    approval_id: str = Field(min_length=1, max_length=120)
    approved_by: str = Field(min_length=1, max_length=120)
    approved_by_display_name: str | None = Field(default=None, max_length=200)
    approval_scope: HumanApprovalGateScope = (
        HumanApprovalGateScope.GIT_ADD_COMMIT_PREVIEW
    )
    approval_requested_action: HumanApprovalGateAction = (
        HumanApprovalGateAction.APPROVE_GIT_ADD_COMMIT_PREVIEW
    )
    approval_client_request_id: str = Field(min_length=1, max_length=200)
    approval_created_at: datetime
    approval_expires_at: datetime
    approval_applied: bool = False
    approval_revoked: bool = False
    approval_confirmation_fingerprint: str = Field(min_length=64, max_length=64)

    @field_validator(
        "approval_id",
        "approved_by",
        "approved_by_display_name",
        "approval_client_request_id",
        "approval_confirmation_fingerprint",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("approval_created_at", "approval_expires_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        normalized_value = ensure_utc_datetime(value)
        if normalized_value is None:
            raise ValueError("approval timestamps must be provided")
        return normalized_value

    @model_validator(mode="after")
    def validate_record_contract(self) -> "HumanApprovalRecord":
        if self.approval_expires_at <= self.approval_created_at:
            raise ValueError("approval_expires_at must be later than approval_created_at")
        if self.approval_applied:
            raise ValueError("ready P4-F approval records must not be applied")
        if self.approval_revoked:
            raise ValueError("ready P4-F approval records must not be revoked")
        return self


class DeliveryHumanApprovalResult(DomainModel):
    """P4-F gate evaluation result — no Git write is authorized or executed."""

    ready: bool
    source: str = Field(default=DELIVERY_HUMAN_APPROVAL_SOURCE, min_length=1)
    reason_code: str | None = Field(default=None, max_length=200)
    summary_cn: str = Field(min_length=1, max_length=1_000)

    session_id: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    task_id: str = Field(min_length=1, max_length=120)
    run_id: str = Field(min_length=1, max_length=120)

    approval_required: bool = True
    approval_granted: bool = False
    approval_record: HumanApprovalRecord | None = None

    approval_id: str | None = Field(default=None, max_length=120)
    approved_by: str | None = Field(default=None, max_length=120)
    approved_by_display_name: str | None = Field(default=None, max_length=200)
    approval_scope: HumanApprovalGateScope | None = None
    approval_requested_action: HumanApprovalGateAction | None = None
    approval_client_request_id: str | None = Field(default=None, max_length=200)
    approval_created_at: datetime | None = None
    approval_expires_at: datetime | None = None
    approval_applied: bool = False
    approval_revoked: bool = False
    approval_confirmation_fingerprint: str | None = Field(
        default=None, min_length=64, max_length=64
    )

    operation_dry_run_ready: bool | None = None
    delivery_gate_evidence_ready: bool | None = None
    delivery_gate_allows_user_confirmation: bool | None = None
    delivery_gate_allows_write: bool | None = None
    proposed_operation: str | None = Field(default=None, max_length=120)
    proposed_commit_message: str | None = Field(default=None, max_length=200)
    changed_files_count: int | None = Field(default=None, ge=0)
    changed_files: list[str] = Field(default_factory=list, max_length=500)
    satisfied_conditions: list[str] = Field(default_factory=list, max_length=40)
    blocking_reasons: list[str] = Field(default_factory=list, max_length=40)

    safety_flags: HumanApprovalGateSafetyFlags = Field(
        default_factory=HumanApprovalGateSafetyFlags
    )

    @field_validator(
        "source",
        "reason_code",
        "summary_cn",
        "session_id",
        "project_id",
        "task_id",
        "run_id",
        "approval_id",
        "approved_by",
        "approved_by_display_name",
        "approval_client_request_id",
        "approval_confirmation_fingerprint",
        "proposed_operation",
        "proposed_commit_message",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("approval_created_at", "approval_expires_at")
    @classmethod
    def normalize_optional_datetime(cls, value: datetime | None) -> datetime | None:
        return ensure_utc_datetime(value)

    @field_validator("changed_files", "satisfied_conditions", "blocking_reasons")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        return _normalize_string_list(values)

    @model_validator(mode="after")
    def validate_result_contract(self) -> "DeliveryHumanApprovalResult":
        if self.source != DELIVERY_HUMAN_APPROVAL_SOURCE:
            raise ValueError(f"source must be {DELIVERY_HUMAN_APPROVAL_SOURCE!r}")
        if not self.approval_required:
            raise ValueError("P4-F human approval gate always requires approval")

        if self.ready:
            if self.reason_code is not None:
                raise ValueError("ready human approval evidence must not include reason_code")
            if not self.approval_granted:
                raise ValueError("ready human approval evidence must grant approval")
            if self.approval_record is None:
                raise ValueError("ready human approval evidence must include approval_record")
            if self.blocking_reasons:
                raise ValueError("ready human approval evidence must not include blocking reasons")
            if self.operation_dry_run_ready is not True:
                raise ValueError("ready human approval evidence requires ready operation dry-run")
            if self.delivery_gate_evidence_ready is not True:
                raise ValueError("ready human approval evidence requires ready delivery gate evidence")
            if self.delivery_gate_allows_user_confirmation is not True:
                raise ValueError("ready human approval evidence requires user confirmation gate")
            if self.delivery_gate_allows_write is not False:
                raise ValueError("ready human approval evidence must not allow writes")
            if self.proposed_operation != "git_add_commit":
                raise ValueError("ready human approval evidence requires git_add_commit preview")
            if self.approval_applied:
                raise ValueError("ready human approval evidence must not be applied")
            if self.approval_revoked:
                raise ValueError("ready human approval evidence must not be revoked")
            if not self.safety_flags.approval_granted:
                raise ValueError("ready human approval safety flags must mark approval_granted")
            if not self.safety_flags.gate_allows_next_guardrail:
                raise ValueError(
                    "ready human approval safety flags must allow next guardrail"
                )
        else:
            if self.reason_code is None:
                raise ValueError("blocked human approval evidence must include reason_code")
            if self.approval_granted:
                raise ValueError("blocked human approval evidence must not grant approval")
            if not self.blocking_reasons:
                raise ValueError("blocked human approval evidence must include blocking reasons")
            if self.safety_flags.gate_allows_next_guardrail:
                raise ValueError(
                    "blocked human approval evidence must not allow next guardrail"
                )

        return self


class HumanApprovalGateBuilder:
    """Evaluate P4-F human approval gate evidence from existing values only."""

    @staticmethod
    def evaluate(
        *,
        agent_session: Any,
        operation_dry_run: Any | None,
        delivery_gate_evidence: Any | None,
        approval_id: str | None = None,
        approval_requested_action: str | None = None,
        approval_confirmation_text: str | None = None,
        approval_actor_id: str | None = None,
        approval_actor_display_name: str | None = None,
        approval_client_request_id: str | None = None,
        approval_created_at: datetime | None = None,
        approval_scope: str | None = None,
        approval_expires_at: datetime | None = None,
        approval_applied: bool = False,
        approval_revoked: bool = False,
        delivery_git_write_enabled: bool = False,
        expected_changed_files: list[str] | None = None,
        expected_proposed_commit_message: str | None = None,
        current_time: datetime | None = None,
    ) -> DeliveryHumanApprovalResult:
        session_ids = (
            _session_ids(agent_session)
            if agent_session is not None
            else _missing_session_ids()
        )
        now = ensure_utc_datetime(current_time) or utc_now()
        normalized_created_at = ensure_utc_datetime(approval_created_at)
        normalized_expires_at = ensure_utc_datetime(approval_expires_at)

        operation_ready = bool(_value(operation_dry_run, "ready", False))
        gate_ready = bool(_value(delivery_gate_evidence, "ready", False))
        gate_allows_user_confirmation = _safety_flag_value(
            delivery_gate_evidence, "gate_allows_user_confirmation"
        )
        gate_allows_write = _safety_flag_value(
            delivery_gate_evidence, "gate_allows_write"
        )
        proposed_operation = _enum_or_string_value(
            _value(operation_dry_run, "proposed_operation", None)
        )
        proposed_commit_message = _string_value(
            operation_dry_run, "proposed_commit_message"
        )
        operation_changed_files = _string_list_value(operation_dry_run, "changed_files")
        gate_changed_files = _string_list_value(delivery_gate_evidence, "changed_files")
        changed_files = operation_changed_files or gate_changed_files
        changed_files_count = _int_value(operation_dry_run, "changed_files_count")
        if changed_files_count <= 0:
            changed_files_count = _int_value(
                delivery_gate_evidence, "changed_files_count"
            )
        expected_files = _normalize_string_list(expected_changed_files or [])
        expected_commit_message = _normalize_optional_text(
            expected_proposed_commit_message
        )

        satisfied_conditions: list[str] = []
        blocking_reasons: list[str] = []

        def record(condition_code: str, passed: bool, reason_code: str) -> None:
            if passed:
                satisfied_conditions.append(condition_code)
                return
            blocking_reasons.append(f"{condition_code}:{reason_code}")

        requested_action_value = _normalize_optional_text(approval_requested_action)
        scope_value = _normalize_optional_text(approval_scope)
        actor_id = _normalize_optional_text(approval_actor_id)
        client_request_id = _normalize_optional_text(approval_client_request_id)
        confirmation_text = _normalize_optional_text(approval_confirmation_text)

        record("H1", agent_session is not None, "agent_session_missing")
        record("H2", operation_dry_run is not None, "operation_dry_run_missing")
        record(
            "H3",
            operation_dry_run is not None and operation_ready,
            "operation_dry_run_not_ready",
        )
        record(
            "H4",
            delivery_gate_evidence is not None,
            "delivery_gate_evidence_missing",
        )
        record(
            "H5",
            delivery_gate_evidence is not None and gate_ready,
            "delivery_gate_not_ready",
        )
        record(
            "H6",
            delivery_gate_evidence is not None
            and gate_allows_user_confirmation is True,
            "user_confirmation_not_allowed",
        )
        record(
            "H7",
            delivery_git_write_enabled is False and gate_allows_write is not True,
            "write_gate_unexpectedly_enabled",
        )
        record(
            "H8",
            requested_action_value
            == HUMAN_APPROVAL_ACTION_APPROVE_GIT_ADD_COMMIT_PREVIEW,
            "unsupported_approval_action",
        )
        record("H9", actor_id is not None, "approval_actor_missing")
        record("H10", scope_value is not None, "approval_scope_missing")
        record(
            "H11",
            scope_value == HUMAN_APPROVAL_SCOPE_GIT_ADD_COMMIT_PREVIEW,
            "approval_scope_unsupported",
        )
        record(
            "H12",
            scope_value == HUMAN_APPROVAL_SCOPE_GIT_ADD_COMMIT_PREVIEW
            and requested_action_value
            == HUMAN_APPROVAL_ACTION_APPROVE_GIT_ADD_COMMIT_PREVIEW
            and proposed_operation == "git_add_commit",
            "approval_scope_mismatch",
        )
        record("H13", client_request_id is not None, "approval_request_id_missing")
        record(
            "H14",
            normalized_created_at is not None,
            "approval_timestamp_missing",
        )
        record(
            "H15",
            normalized_expires_at is not None,
            "approval_expiry_missing",
        )
        record(
            "H16",
            normalized_expires_at is not None
            and normalized_created_at is not None
            and normalized_expires_at > normalized_created_at
            and now < normalized_expires_at,
            "approval_expired",
        )
        record("H17", approval_applied is False, "approval_already_applied")
        record("H18", approval_revoked is False, "approval_revoked")
        record(
            "H19",
            _confirmation_is_explicit(confirmation_text),
            "approval_confirmation_missing",
        )
        record(
            "H20",
            bool(expected_files) and expected_files == changed_files,
            "changed_files_mismatch",
        )
        record(
            "H21",
            expected_commit_message is not None
            and expected_commit_message == proposed_commit_message,
            "commit_message_mismatch",
        )
        record(
            "H22",
            operation_dry_run is not None
            and delivery_gate_evidence is not None
            and _operation_and_gate_safety_flags_clear(
                operation_dry_run, delivery_gate_evidence
            ),
            "write_already_triggered",
        )

        ready = not blocking_reasons
        primary_reason_code = (
            None if ready else _reason_code_from_blocking_reason(blocking_reasons[0])
        )

        approved_by_display_name = _normalize_optional_text(
            approval_actor_display_name
        )
        fingerprint = (
            _approval_confirmation_fingerprint(
                confirmation_text=confirmation_text or "",
                changed_files=expected_files,
                proposed_commit_message=expected_commit_message or "",
                approval_scope=scope_value or "",
                approval_expires_at=normalized_expires_at,
            )
            if confirmation_text
            and expected_files
            and expected_commit_message
            and scope_value
            and normalized_expires_at
            else None
        )
        normalized_approval_id = _normalize_optional_text(approval_id)
        if ready and normalized_approval_id is None:
            normalized_approval_id = _generated_approval_id(
                approved_by=actor_id or "",
                approval_client_request_id=client_request_id or "",
                approval_created_at=normalized_created_at,
                approval_scope=scope_value or "",
                changed_files=expected_files,
                proposed_commit_message=expected_commit_message or "",
            )

        if ready:
            approval_record = HumanApprovalRecord(
                approval_id=normalized_approval_id or "",
                approved_by=actor_id or "",
                approved_by_display_name=approved_by_display_name,
                approval_scope=HumanApprovalGateScope.GIT_ADD_COMMIT_PREVIEW,
                approval_requested_action=(
                    HumanApprovalGateAction.APPROVE_GIT_ADD_COMMIT_PREVIEW
                ),
                approval_client_request_id=client_request_id or "",
                approval_created_at=normalized_created_at,  # type: ignore[arg-type]
                approval_expires_at=normalized_expires_at,  # type: ignore[arg-type]
                approval_applied=False,
                approval_revoked=False,
                approval_confirmation_fingerprint=fingerprint or "",
            )
            return DeliveryHumanApprovalResult(
                ready=True,
                reason_code=None,
                summary_cn=(
                    "用户已确认提交预览，可进入下一阶段写入前安全检查。当前仍未写入仓库。"
                ),
                **session_ids,
                approval_required=True,
                approval_granted=True,
                approval_record=approval_record,
                approval_id=approval_record.approval_id,
                approved_by=approval_record.approved_by,
                approved_by_display_name=approval_record.approved_by_display_name,
                approval_scope=approval_record.approval_scope,
                approval_requested_action=approval_record.approval_requested_action,
                approval_client_request_id=approval_record.approval_client_request_id,
                approval_created_at=approval_record.approval_created_at,
                approval_expires_at=approval_record.approval_expires_at,
                approval_applied=approval_record.approval_applied,
                approval_revoked=approval_record.approval_revoked,
                approval_confirmation_fingerprint=(
                    approval_record.approval_confirmation_fingerprint
                ),
                operation_dry_run_ready=True,
                delivery_gate_evidence_ready=True,
                delivery_gate_allows_user_confirmation=True,
                delivery_gate_allows_write=False,
                proposed_operation="git_add_commit",
                proposed_commit_message=proposed_commit_message,
                changed_files_count=changed_files_count,
                changed_files=changed_files,
                satisfied_conditions=satisfied_conditions,
                blocking_reasons=[],
                safety_flags=HumanApprovalGateSafetyFlags(
                    approval_granted=True,
                    approval_applied=False,
                    approval_revoked=False,
                    approval_expired=False,
                    gate_allows_write=False,
                    gate_allows_next_guardrail=True,
                ),
            )

        return DeliveryHumanApprovalResult(
            ready=False,
            reason_code=primary_reason_code,
            summary_cn=P4F_REASON_SUMMARIES_CN.get(
                primary_reason_code or "",
                "尚不能确认提交预览，请先完成交付前检查。当前未写入仓库。",
            ),
            **session_ids,
            approval_required=True,
            approval_granted=False,
            approval_record=None,
            approval_id=normalized_approval_id,
            approved_by=actor_id,
            approved_by_display_name=approved_by_display_name,
            approval_scope=(
                HumanApprovalGateScope.GIT_ADD_COMMIT_PREVIEW
                if scope_value == HUMAN_APPROVAL_SCOPE_GIT_ADD_COMMIT_PREVIEW
                else None
            ),
            approval_requested_action=(
                HumanApprovalGateAction.APPROVE_GIT_ADD_COMMIT_PREVIEW
                if requested_action_value
                == HUMAN_APPROVAL_ACTION_APPROVE_GIT_ADD_COMMIT_PREVIEW
                else None
            ),
            approval_client_request_id=client_request_id,
            approval_created_at=normalized_created_at,
            approval_expires_at=normalized_expires_at,
            approval_applied=approval_applied,
            approval_revoked=approval_revoked,
            approval_confirmation_fingerprint=fingerprint,
            operation_dry_run_ready=(
                None if operation_dry_run is None else operation_ready
            ),
            delivery_gate_evidence_ready=(
                None if delivery_gate_evidence is None else gate_ready
            ),
            delivery_gate_allows_user_confirmation=(
                None
                if delivery_gate_evidence is None
                else gate_allows_user_confirmation
            ),
            delivery_gate_allows_write=(
                None if delivery_gate_evidence is None else gate_allows_write
            ),
            proposed_operation=proposed_operation,
            proposed_commit_message=proposed_commit_message,
            changed_files_count=changed_files_count,
            changed_files=changed_files,
            satisfied_conditions=satisfied_conditions,
            blocking_reasons=blocking_reasons,
            safety_flags=HumanApprovalGateSafetyFlags(
                approval_granted=False,
                approval_applied=approval_applied,
                approval_revoked=approval_revoked,
                approval_expired=primary_reason_code == "approval_expired",
                gate_allows_write=False,
                gate_allows_next_guardrail=False,
            ),
        )


def _session_ids(agent_session: Any) -> dict[str, str]:
    return {
        "session_id": str(_value(agent_session, "id", "")),
        "project_id": str(_value(agent_session, "project_id", "")),
        "task_id": str(_value(agent_session, "task_id", "")),
        "run_id": str(_value(agent_session, "run_id", "")),
    }


def _missing_session_ids() -> dict[str, str]:
    return {
        "session_id": "missing",
        "project_id": "missing",
        "task_id": "missing",
        "run_id": "missing",
    }


def _operation_and_gate_safety_flags_clear(
    operation_dry_run: Any, delivery_gate_evidence: Any
) -> bool:
    operation_flags_clear = not any(
        _safety_flag_value(operation_dry_run, flag_name)
        for flag_name in (
            "runs_git",
            "runs_write_git",
            "git_add_triggered",
            "git_commit_triggered",
            "git_push_triggered",
            "pr_opened",
            "ci_triggered",
            "execution_enabled",
            "operation_applied",
            "approval_granted",
        )
    )
    gate_flags_clear = not any(
        _safety_flag_value(delivery_gate_evidence, flag_name)
        for flag_name in (
            "runs_git",
            "runs_write_git",
            "git_add_triggered",
            "git_commit_triggered",
            "git_push_triggered",
            "pr_opened",
            "ci_triggered",
            "execution_enabled",
            "operation_applied",
            "approval_granted",
            "gate_allows_write",
        )
    )
    return operation_flags_clear and gate_flags_clear


def _safety_flag_value(source: Any, flag_name: str) -> bool:
    safety_flags = _value(source, "safety_flags", None)
    if safety_flags is not None:
        return bool(_value(safety_flags, flag_name, False))
    return bool(_value(source, flag_name, False))


def _approval_confirmation_fingerprint(
    *,
    confirmation_text: str,
    changed_files: list[str],
    proposed_commit_message: str,
    approval_scope: str,
    approval_expires_at: datetime | None,
) -> str:
    expires_at_value = (
        ensure_utc_datetime(approval_expires_at).isoformat()
        if approval_expires_at is not None
        else "missing"
    )
    material = "\n".join(
        [
            _normalize_optional_text(confirmation_text) or "",
            approval_scope,
            expires_at_value,
            proposed_commit_message,
            *changed_files,
        ]
    )
    return sha256(material.encode("utf-8")).hexdigest()


def _generated_approval_id(
    *,
    approved_by: str,
    approval_client_request_id: str,
    approval_created_at: datetime | None,
    approval_scope: str,
    changed_files: list[str],
    proposed_commit_message: str,
) -> str:
    created_at_value = (
        ensure_utc_datetime(approval_created_at).isoformat()
        if approval_created_at is not None
        else "missing"
    )
    material = "\n".join(
        [
            "p4f-human-approval",
            approved_by,
            approval_client_request_id,
            created_at_value,
            approval_scope,
            proposed_commit_message,
            *changed_files,
        ]
    )
    return f"hap_{uuid5(NAMESPACE_URL, material)}"


def _confirmation_is_explicit(confirmation_text: str | None) -> bool:
    if confirmation_text is None:
        return False
    normalized_value = confirmation_text.strip().lower()
    if not normalized_value:
        return False
    explicit_tokens = (
        "confirm_git_add_commit_preview",
        "approve_git_add_commit_preview",
        "确认提交预览",
        "确认 git add commit 预览",
        "确认git add commit预览",
    )
    return any(token in normalized_value for token in explicit_tokens)


def _reason_code_from_blocking_reason(blocking_reason: str) -> str:
    return blocking_reason.split(":", maxsplit=1)[1]


def _int_value(source: Any, name: str) -> int:
    value = _value(source, name, 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _string_list_value(source: Any, name: str) -> list[str]:
    value = _value(source, name, [])
    if not isinstance(value, list):
        return []
    return _normalize_string_list(value)


def _normalize_string_list(values: list[str]) -> list[str]:
    normalized_items: list[str] = []
    seen_items: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        normalized_value = value.strip()
        if not normalized_value or normalized_value in seen_items:
            continue
        normalized_items.append(normalized_value)
        seen_items.add(normalized_value)
    return normalized_items


def _string_value(source: Any, name: str) -> str | None:
    value = _value(source, name, None)
    return _normalize_optional_text(value)


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized_value = str(value).strip()
    return normalized_value or None


def _enum_or_string_value(value: Any) -> str | None:
    if value is None:
        return None
    enum_value = getattr(value, "value", value)
    return _normalize_optional_text(enum_value)


def _value(source: Any, name: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)
