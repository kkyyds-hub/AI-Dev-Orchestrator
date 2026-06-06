"""Pure P4-D delivery gate evidence contract and builder.

This module is deliberately side-effect free. It does not run Git commands,
call TaskWorker, write AgentMessage rows, expose API schemas, mutate database
tables, query audit repositories, or perform git add/commit/push/PR operations.
It only aggregates existing P4-B/P4-C evidence plus caller-supplied audit
evidence values into a delivery gate result.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel


DELIVERY_GATE_EVIDENCE_SOURCE = "delivery_gate_evidence"
DELIVERY_AUDIT_COLLECTED_EVENT_TYPE = "delivery_diff_dry_run_collected"

P4D_FORBIDDEN_TRUE_SAFETY_FLAGS: tuple[str, ...] = (
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

P4D_READY_CONDITIONS: tuple[str, ...] = tuple(f"G{index}" for index in range(1, 22))

P4D_REASON_SUMMARIES_CN: dict[str, str] = {
    "agent_session_missing": "会话信息缺失，无法进行交付前检查。",
    "worktree_unavailable": "当前工作区不可用，无法进行交付前检查。",
    "branch_missing": "当前工作区未绑定分支，无法进行交付前检查。",
    "workspace_not_clean": "工作区状态不一致，无法进行交付前检查。",
    "diff_evidence_not_ready": "代码改动预览未就绪，无法进行交付前检查。",
    "no_changes": "当前没有可提交的代码改动。",
    "diff_write_flag_triggered": "检测到 diff 阶段写操作标志异常，无法进行交付前检查。",
    "operation_dry_run_not_ready": "提交预览未就绪，无法进行交付前检查。",
    "unsupported_operation": "当前操作类型不支持交付。",
    "operation_write_flag_triggered": "检测到操作预览阶段写操作标志异常，无法进行交付前检查。",
    "operation_already_applied": "操作已应用，无法重复进行交付前检查。",
    "approval_already_granted": "审批已授予，无法重新进行交付前检查。",
    "feature_flag_enabled": "真实写入开关已开启，不支持预览模式下的交付前检查。",
    "evidence_mismatch": "代码改动预览与提交预览不一致，无法进行交付前检查。",
    "audit_evidence_missing": "缺少交付审计记录，无法进行交付前检查。",
}


class DeliveryGateNextRequiredAction(StrEnum):
    """Stable next action values emitted by P4-D gate evidence."""

    AWAIT_USER_CONFIRMATION = "await_user_confirmation"
    RESOLVE_BLOCKING_CONDITIONS = "resolve_blocking_conditions"
    NONE = "none"


class DeliveryGateEvidenceSafetyFlags(DomainModel):
    """P4-D safety flags; only user-confirmation gating may become true."""

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
    gate_allows_write: bool = False
    gate_allows_user_confirmation: bool = False

    @model_validator(mode="after")
    def validate_p4d_no_execution_boundary(self) -> "DeliveryGateEvidenceSafetyFlags":
        enabled_forbidden_flags = [
            flag_name
            for flag_name in P4D_FORBIDDEN_TRUE_SAFETY_FLAGS
            if bool(getattr(self, flag_name))
        ]
        if enabled_forbidden_flags:
            raise ValueError(
                "P4-D delivery gate evidence must not execute Git, enable "
                "delivery writes, grant approval, allow writes, or apply "
                "operations: "
                + ", ".join(enabled_forbidden_flags)
            )
        return self


class DeliveryGateEvidenceResult(DomainModel):
    """Aggregated delivery gate evidence — no Git write is executed."""

    ready: bool
    source: str = Field(default=DELIVERY_GATE_EVIDENCE_SOURCE, min_length=1)
    reason_code: str | None = Field(default=None, max_length=200)

    session_id: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    task_id: str = Field(min_length=1, max_length=120)
    run_id: str = Field(min_length=1, max_length=120)

    worktree_path: str | None = Field(default=None, max_length=1_000)
    branch_name: str | None = Field(default=None, max_length=200)

    proposed_operation: str = Field(default="none", min_length=1, max_length=120)
    changed_files_count: int = Field(default=0, ge=0)
    changed_files: list[str] = Field(default_factory=list, max_length=500)

    next_required_action: DeliveryGateNextRequiredAction
    user_confirmation_required: bool = False
    human_approval_required: bool = False

    summary_cn: str = Field(min_length=1, max_length=1_000)
    satisfied_conditions: list[str] = Field(default_factory=list, max_length=21)
    blocking_reasons: list[str] = Field(default_factory=list, max_length=21)

    safety_flags: DeliveryGateEvidenceSafetyFlags = Field(
        default_factory=DeliveryGateEvidenceSafetyFlags
    )

    @field_validator(
        "source",
        "reason_code",
        "session_id",
        "project_id",
        "task_id",
        "run_id",
        "worktree_path",
        "branch_name",
        "proposed_operation",
        "summary_cn",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @field_validator("changed_files", "satisfied_conditions", "blocking_reasons")
    @classmethod
    def normalize_string_lists(cls, values: list[str]) -> list[str]:
        normalized_items: list[str] = []
        seen_items: set[str] = set()
        for value in values:
            normalized_value = value.strip()
            if not normalized_value or normalized_value in seen_items:
                continue
            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)
        return normalized_items

    @model_validator(mode="after")
    def validate_contract(self) -> "DeliveryGateEvidenceResult":
        if self.source != DELIVERY_GATE_EVIDENCE_SOURCE:
            raise ValueError(f"source must be {DELIVERY_GATE_EVIDENCE_SOURCE!r}")
        if self.ready and self.reason_code is not None:
            raise ValueError("ready delivery gate evidence must not include reason_code")
        if not self.ready and self.reason_code is None:
            raise ValueError("blocked delivery gate evidence must include reason_code")
        if self.ready:
            if (
                self.next_required_action
                != DeliveryGateNextRequiredAction.AWAIT_USER_CONFIRMATION
            ):
                raise ValueError(
                    "ready delivery gate evidence must await user confirmation"
                )
            if self.proposed_operation != "git_add_commit":
                raise ValueError(
                    "ready delivery gate evidence must carry git_add_commit preview"
                )
            if not self.user_confirmation_required:
                raise ValueError(
                    "ready delivery gate evidence must require user confirmation"
                )
            if not self.human_approval_required:
                raise ValueError(
                    "ready delivery gate evidence must require human approval"
                )
            if self.blocking_reasons:
                raise ValueError(
                    "ready delivery gate evidence must not include blocking reasons"
                )
            if set(self.satisfied_conditions) != set(P4D_READY_CONDITIONS):
                raise ValueError(
                    "ready delivery gate evidence must satisfy G1-G21 conditions"
                )
            if not self.safety_flags.gate_allows_user_confirmation:
                raise ValueError(
                    "ready delivery gate evidence must allow user confirmation"
                )
        else:
            if (
                self.next_required_action
                != DeliveryGateNextRequiredAction.RESOLVE_BLOCKING_CONDITIONS
            ):
                raise ValueError(
                    "blocked delivery gate evidence must resolve blocking conditions"
                )
            if self.proposed_operation != "none":
                raise ValueError(
                    "blocked delivery gate evidence must not propose operations"
                )
            if self.user_confirmation_required:
                raise ValueError(
                    "blocked delivery gate evidence must not require user confirmation"
                )
            if self.safety_flags.gate_allows_user_confirmation:
                raise ValueError(
                    "blocked delivery gate evidence must not allow user confirmation"
                )
            if not self.blocking_reasons:
                raise ValueError(
                    "blocked delivery gate evidence must include blocking reasons"
                )
        return self


class DeliveryGateEvidenceBuilder:
    """Evaluate P4-D delivery gate evidence from existing values only."""

    @staticmethod
    def evaluate(
        *,
        agent_session: Any,
        diff_evidence: Any | None,
        operation_dry_run: Any | None,
        delivery_audit_event_present: bool | None = None,
        delivery_audit_event_type: str | None = None,
        delivery_audit_event_ready: bool | None = None,
        delivery_git_write_enabled: bool = False,
    ) -> DeliveryGateEvidenceResult:
        session_ids = (
            _session_ids(agent_session)
            if agent_session is not None
            else _missing_session_ids()
        )
        worktree_path = _string_value(agent_session, "workspace_path")
        session_branch_name = _string_value(agent_session, "branch_name")
        branch_name = (
            session_branch_name
            or _string_value(diff_evidence, "branch_name")
            or _string_value(operation_dry_run, "branch_name")
        )

        satisfied_conditions: list[str] = []
        blocking_reasons: list[str] = []

        def record(condition_code: str, passed: bool, reason_code: str) -> None:
            if passed:
                satisfied_conditions.append(condition_code)
                return
            blocking_reasons.append(f"{condition_code}:{reason_code}")

        record("G1", agent_session is not None, "agent_session_missing")
        record("G2", _is_worktree_session(agent_session), "worktree_unavailable")
        record("G3", worktree_path is not None, "worktree_unavailable")
        record("G4", session_branch_name is not None, "branch_missing")
        record(
            "G5",
            _value(agent_session, "workspace_clean", None) is True,
            "workspace_not_clean",
        )

        diff_ready = bool(_value(diff_evidence, "ready", False))
        diff_has_changes = bool(_value(diff_evidence, "has_changes", False))
        diff_changed_files_count = _int_value(diff_evidence, "changed_files_count")
        diff_changed_files = _string_list_value(diff_evidence, "changed_files")

        record("G6", diff_evidence is not None, "diff_evidence_not_ready")
        record("G7", diff_evidence is not None and diff_ready, "diff_evidence_not_ready")
        record("G8", diff_evidence is not None and diff_has_changes, "no_changes")
        record(
            "G9",
            diff_evidence is not None and diff_changed_files_count > 0,
            "no_changes",
        )
        record(
            "G10",
            diff_evidence is not None and _diff_write_flags_clear(diff_evidence),
            "diff_write_flag_triggered",
        )

        operation_ready = bool(_value(operation_dry_run, "ready", False))
        operation_value = _enum_or_string_value(
            _value(operation_dry_run, "proposed_operation", None)
        )
        operation_changed_files_count = _int_value(
            operation_dry_run, "changed_files_count"
        )
        operation_changed_files = _string_list_value(
            operation_dry_run, "changed_files"
        )

        record("G11", operation_dry_run is not None, "operation_dry_run_not_ready")
        record(
            "G12",
            operation_dry_run is not None and operation_ready,
            "operation_dry_run_not_ready",
        )
        record(
            "G13",
            operation_dry_run is not None and operation_value == "git_add_commit",
            "unsupported_operation",
        )
        record(
            "G14",
            operation_dry_run is not None
            and _value(operation_dry_run, "user_confirmation_required", False) is True,
            "operation_dry_run_not_ready",
        )
        record(
            "G15",
            operation_dry_run is not None
            and _value(operation_dry_run, "human_approval_required", False) is True,
            "operation_dry_run_not_ready",
        )
        record(
            "G16",
            operation_dry_run is not None
            and _operation_preview_safety_flags_clear(operation_dry_run),
            "operation_write_flag_triggered",
        )
        record(
            "G17",
            operation_dry_run is not None
            and not _safety_flag_value(operation_dry_run, "operation_applied"),
            "operation_already_applied",
        )
        record(
            "G18",
            operation_dry_run is not None
            and not _safety_flag_value(operation_dry_run, "approval_granted"),
            "approval_already_granted",
        )

        record("G19", delivery_git_write_enabled is False, "feature_flag_enabled")
        record(
            "G20",
            diff_evidence is not None
            and operation_dry_run is not None
            and diff_changed_files_count == operation_changed_files_count
            and diff_changed_files == operation_changed_files,
            "evidence_mismatch",
        )
        record(
            "G21",
            delivery_audit_event_present is True
            and delivery_audit_event_type == DELIVERY_AUDIT_COLLECTED_EVENT_TYPE
            and delivery_audit_event_ready is True,
            "audit_evidence_missing",
        )

        ready = not blocking_reasons
        primary_reason_code = (
            None if ready else _reason_code_from_blocking_reason(blocking_reasons[0])
        )

        if ready:
            return DeliveryGateEvidenceResult(
                ready=True,
                reason_code=None,
                **session_ids,
                worktree_path=worktree_path,
                branch_name=branch_name,
                proposed_operation="git_add_commit",
                changed_files_count=operation_changed_files_count,
                changed_files=operation_changed_files,
                next_required_action=(
                    DeliveryGateNextRequiredAction.AWAIT_USER_CONFIRMATION
                ),
                user_confirmation_required=True,
                human_approval_required=True,
                summary_cn="交付前检查已通过，可以进入用户确认。仍未执行提交或推送。",
                satisfied_conditions=satisfied_conditions,
                blocking_reasons=[],
                safety_flags=DeliveryGateEvidenceSafetyFlags(
                    gate_allows_user_confirmation=True
                ),
            )

        return DeliveryGateEvidenceResult(
            ready=False,
            reason_code=primary_reason_code,
            **session_ids,
            worktree_path=worktree_path,
            branch_name=branch_name,
            proposed_operation="none",
            changed_files_count=0,
            changed_files=[],
            next_required_action=(
                DeliveryGateNextRequiredAction.RESOLVE_BLOCKING_CONDITIONS
            ),
            user_confirmation_required=False,
            human_approval_required=False,
            summary_cn=P4D_REASON_SUMMARIES_CN.get(
                primary_reason_code or "", "交付前检查未通过。"
            ),
            satisfied_conditions=satisfied_conditions,
            blocking_reasons=blocking_reasons,
            safety_flags=DeliveryGateEvidenceSafetyFlags(
                gate_allows_user_confirmation=False
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


def _is_worktree_session(agent_session: Any) -> bool:
    workspace_type = _value(agent_session, "workspace_type", None)
    workspace_type_value = getattr(workspace_type, "value", workspace_type)
    return workspace_type_value == "worktree"


def _diff_write_flags_clear(diff_evidence: Any) -> bool:
    return not any(
        bool(_value(diff_evidence, flag_name, False))
        for flag_name in (
            "runs_write_git",
            "git_add_triggered",
            "git_commit_triggered",
            "git_push_triggered",
            "pr_opened",
            "ci_triggered",
            "execution_enabled",
            "danger_commands_applied",
        )
    )


def _operation_preview_safety_flags_clear(operation_dry_run: Any) -> bool:
    return not any(
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
        )
    )


def _safety_flag_value(source: Any, flag_name: str) -> bool:
    safety_flags = _value(source, "safety_flags", None)
    if safety_flags is not None:
        return bool(_value(safety_flags, flag_name, False))
    return bool(_value(source, flag_name, False))


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
    normalized_items: list[str] = []
    seen_items: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        normalized_value = item.strip()
        if not normalized_value or normalized_value in seen_items:
            continue
        normalized_items.append(normalized_value)
        seen_items.add(normalized_value)
    return normalized_items


def _string_value(source: Any, name: str) -> str | None:
    value = _value(source, name, None)
    if value is None:
        return None
    normalized_value = str(value).strip()
    return normalized_value or None


def _enum_or_string_value(value: Any) -> str | None:
    if value is None:
        return None
    enum_value = getattr(value, "value", value)
    normalized_value = str(enum_value).strip()
    return normalized_value or None


def _value(source: Any, name: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)
