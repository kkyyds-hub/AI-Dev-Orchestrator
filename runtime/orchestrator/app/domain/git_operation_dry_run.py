"""Pure P4-C Git operation dry-run contract and builder.

This module is deliberately side-effect free.  It does not run Git commands,
call TaskWorker, write AgentMessage rows, expose API schemas, mutate database
tables, or perform git add/commit/push/PR operations.  It only converts existing
P4-B diff evidence into a proposal describing what would be prepared after a
future explicit user confirmation.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from app.domain._base import DomainModel


GIT_OPERATION_DRY_RUN_SOURCE = "git_operation_dry_run"

P4C_FORBIDDEN_TRUE_SAFETY_FLAGS: tuple[str, ...] = (
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


class GitOperationDryRunOperation(StrEnum):
    """Stable operation proposal kinds for P4-C."""

    GIT_ADD_COMMIT = "git_add_commit"
    GIT_PUSH_PR = "git_push_pr"
    NONE = "none"


class GitOperationDryRunSafetyFlags(DomainModel):
    """P4-C safety flags; every flag must stay false."""

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

    @model_validator(mode="after")
    def validate_p4c_no_execution_boundary(self) -> "GitOperationDryRunSafetyFlags":
        enabled_forbidden_flags = [
            flag_name
            for flag_name in P4C_FORBIDDEN_TRUE_SAFETY_FLAGS
            if bool(getattr(self, flag_name))
        ]
        if enabled_forbidden_flags:
            raise ValueError(
                "P4-C git operation dry-run must not execute Git, enable "
                "delivery writes, grant approval, or apply operations: "
                + ", ".join(enabled_forbidden_flags)
            )
        return self


class GitOperationDryRunResult(DomainModel):
    """Preview of planned Git operations — no Git commands are executed."""

    ready: bool
    source: str = Field(default=GIT_OPERATION_DRY_RUN_SOURCE, min_length=1)
    reason_code: str | None = Field(default=None, max_length=200)

    session_id: str = Field(min_length=1, max_length=120)
    project_id: str = Field(min_length=1, max_length=120)
    task_id: str = Field(min_length=1, max_length=120)
    run_id: str = Field(min_length=1, max_length=120)

    worktree_path: str | None = Field(default=None, max_length=1_000)
    branch_name: str | None = Field(default=None, max_length=200)

    changed_files_count: int = Field(default=0, ge=0)
    changed_files: list[str] = Field(default_factory=list, max_length=500)
    added_files: list[str] = Field(default_factory=list, max_length=500)
    modified_files: list[str] = Field(default_factory=list, max_length=500)
    deleted_files: list[str] = Field(default_factory=list, max_length=500)
    renamed_files: list[str] = Field(default_factory=list, max_length=500)

    proposed_operation: GitOperationDryRunOperation = GitOperationDryRunOperation.NONE
    proposed_steps: list[str] = Field(default_factory=list, max_length=10)
    proposed_commit_message: str | None = Field(default=None, max_length=200)
    proposed_pr_title: str | None = Field(default=None, max_length=200)
    proposed_pr_body: str | None = Field(default=None, max_length=2_000)

    user_confirmation_required: bool = True
    human_approval_required: bool = True
    feature_flag_required: bool = True

    summary_cn: str = Field(min_length=1, max_length=1_000)
    safety_flags: GitOperationDryRunSafetyFlags = Field(
        default_factory=GitOperationDryRunSafetyFlags
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
        "proposed_commit_message",
        "proposed_pr_title",
        "proposed_pr_body",
        "summary_cn",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None

    @field_validator(
        "changed_files",
        "added_files",
        "modified_files",
        "deleted_files",
        "renamed_files",
        "proposed_steps",
    )
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
    def validate_contract(self) -> "GitOperationDryRunResult":
        if self.source != GIT_OPERATION_DRY_RUN_SOURCE:
            raise ValueError(f"source must be {GIT_OPERATION_DRY_RUN_SOURCE!r}")
        if self.ready and self.reason_code is not None:
            raise ValueError("ready operation dry-run must not include reason_code")
        if not self.ready and self.reason_code is None:
            raise ValueError("blocked operation dry-run must include reason_code")
        if self.ready and self.proposed_operation == GitOperationDryRunOperation.NONE:
            raise ValueError("ready operation dry-run must include a proposed operation")
        if not self.ready and self.proposed_operation != GitOperationDryRunOperation.NONE:
            raise ValueError("blocked operation dry-run must not propose operations")
        if not self.ready and self.proposed_steps:
            raise ValueError("blocked operation dry-run must not include proposed steps")
        if not self.user_confirmation_required:
            raise ValueError("P4-C operation dry-run always requires user confirmation")
        if not self.human_approval_required:
            raise ValueError("P4-C operation dry-run always requires human approval")
        if not self.feature_flag_required:
            raise ValueError("P4-C operation dry-run always requires a feature flag")
        return self


class GitOperationDryRunBuilder:
    """Build P4-C operation proposals from existing diff evidence only."""

    @staticmethod
    def build_from_diff_evidence(
        *,
        agent_session: Any,
        diff_evidence: Any | None,
        delivery_operation_dry_run_enabled: bool = True,
        delivery_git_write_enabled: bool = False,
        human_approval_status: str | None = None,
    ) -> GitOperationDryRunResult:
        session_ids = _session_ids(agent_session)
        worktree_path = _string_value(agent_session, "workspace_path")
        branch_name = _string_value(agent_session, "branch_name") or _string_value(
            diff_evidence, "branch_name"
        )

        if not _is_worktree_session(agent_session) or not worktree_path:
            return _blocked_result(
                **session_ids,
                reason_code="worktree_unavailable",
                summary_cn="当前工作区不可用，无法生成提交预览。",
                worktree_path=worktree_path,
                branch_name=branch_name,
            )

        if not delivery_operation_dry_run_enabled:
            return _blocked_result(
                **session_ids,
                reason_code="feature_flag_disabled",
                summary_cn="提交功能尚未开启。",
                worktree_path=worktree_path,
                branch_name=branch_name,
            )

        if delivery_git_write_enabled:
            return _blocked_result(
                **session_ids,
                reason_code="write_already_triggered",
                summary_cn="检测到写操作已触发，无法再次生成提交预览。",
                worktree_path=worktree_path,
                branch_name=branch_name,
            )

        if human_approval_status not in (None, "none", "pending"):
            return _blocked_result(
                **session_ids,
                reason_code="write_already_triggered",
                summary_cn="检测到写操作已触发，无法再次生成提交预览。",
                worktree_path=worktree_path,
                branch_name=branch_name,
            )

        if diff_evidence is None or not bool(_value(diff_evidence, "ready", False)):
            return _blocked_result(
                **session_ids,
                reason_code="diff_evidence_not_ready",
                summary_cn="代码改动预览未就绪，无法生成提交预览。",
                worktree_path=worktree_path,
                branch_name=branch_name,
            )

        if _has_any_write_flag(diff_evidence):
            return _blocked_result(
                **session_ids,
                reason_code="write_already_triggered",
                summary_cn="检测到写操作已触发，无法再次生成提交预览。",
                worktree_path=worktree_path,
                branch_name=branch_name,
            )

        changed_files = _string_list_value(diff_evidence, "changed_files")
        changed_files_count = int(_value(diff_evidence, "changed_files_count", 0) or 0)
        has_changes = bool(_value(diff_evidence, "has_changes", False))
        if not has_changes or changed_files_count <= 0 or not changed_files:
            return _blocked_result(
                **session_ids,
                reason_code="no_changes",
                summary_cn="当前没有可提交的代码改动。",
                worktree_path=worktree_path,
                branch_name=branch_name,
            )

        proposed_commit_message = _build_commit_message(changed_files_count)
        proposed_steps = [
            "加入待提交区（git add）",
            f"生成本地提交（git commit）：{proposed_commit_message}",
        ]
        summary_cn = (
            f"已生成提交预览：检测到 {changed_files_count} 个文件变更。"
            f"如果确认，将把这些文件提交到分支 {branch_name or '当前分支'}。"
        )

        return GitOperationDryRunResult(
            ready=True,
            reason_code=None,
            **session_ids,
            worktree_path=worktree_path,
            branch_name=branch_name,
            changed_files_count=changed_files_count,
            changed_files=changed_files,
            added_files=_string_list_value(diff_evidence, "added_files"),
            modified_files=_string_list_value(diff_evidence, "modified_files"),
            deleted_files=_string_list_value(diff_evidence, "deleted_files"),
            renamed_files=_string_list_value(diff_evidence, "renamed_files"),
            proposed_operation=GitOperationDryRunOperation.GIT_ADD_COMMIT,
            proposed_steps=proposed_steps,
            proposed_commit_message=proposed_commit_message,
            proposed_pr_title=None,
            proposed_pr_body=None,
            summary_cn=summary_cn,
        )


def _blocked_result(
    *,
    session_id: str,
    project_id: str,
    task_id: str,
    run_id: str,
    reason_code: str,
    summary_cn: str,
    worktree_path: str | None = None,
    branch_name: str | None = None,
) -> GitOperationDryRunResult:
    return GitOperationDryRunResult(
        ready=False,
        reason_code=reason_code,
        session_id=session_id,
        project_id=project_id,
        task_id=task_id,
        run_id=run_id,
        worktree_path=worktree_path,
        branch_name=branch_name,
        changed_files_count=0,
        proposed_operation=GitOperationDryRunOperation.NONE,
        proposed_steps=[],
        summary_cn=summary_cn,
    )


def _session_ids(agent_session: Any) -> dict[str, str]:
    return {
        "session_id": str(_value(agent_session, "id", "")),
        "project_id": str(_value(agent_session, "project_id", "")),
        "task_id": str(_value(agent_session, "task_id", "")),
        "run_id": str(_value(agent_session, "run_id", "")),
    }


def _is_worktree_session(agent_session: Any) -> bool:
    workspace_type = _value(agent_session, "workspace_type", None)
    workspace_type_value = getattr(workspace_type, "value", workspace_type)
    return workspace_type_value == "worktree"


def _has_any_write_flag(diff_evidence: Any) -> bool:
    return any(
        bool(_value(diff_evidence, flag_name, False))
        for flag_name in (
            "runs_write_git",
            "git_add_triggered",
            "git_commit_triggered",
            "git_push_triggered",
            "pr_opened",
            "ci_triggered",
            "execution_enabled",
        )
    )


def _build_commit_message(changed_files_count: int) -> str:
    return f"chore: update {changed_files_count} files from agent work"


def _string_list_value(source: Any, name: str) -> list[str]:
    value = _value(source, name, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _string_value(source: Any, name: str) -> str | None:
    value = _value(source, name, None)
    if value is None:
        return None
    normalized_value = str(value).strip()
    return normalized_value or None


def _value(source: Any, name: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)
