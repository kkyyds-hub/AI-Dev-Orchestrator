"""Day08 execution-preflight risk guard and manual-confirmation service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from uuid import UUID

from app.domain._base import utc_now
from app.domain.change_batch import (
    ChangeBatch,
    ChangeBatchManualConfirmationAction,
    ChangeBatchManualConfirmationDecision,
    ChangeBatchManualConfirmationStatus,
    ChangeBatchPreflight,
    ChangeBatchPreflightStatus,
    ChangeBatchRiskCategory,
    ChangeBatchRiskFinding,
    ChangeBatchRiskSeverity,
)
from app.repositories.change_batch_repository import ChangeBatchRepository
from app.repositories.project_repository import ProjectRepository

_SENSITIVE_DIRECTORY_RULES: tuple[
    tuple[str, ChangeBatchRiskSeverity, str, str],
    ...,
] = (
    (
        ".git",
        ChangeBatchRiskSeverity.CRITICAL,
        "git_metadata",
        "涉及 Git 元数据目录，可能破坏仓库内部状态。",
    ),
    (
        ".github/workflows",
        ChangeBatchRiskSeverity.HIGH,
        "ci_workflow_directory",
        "涉及 CI / 工作流目录，可能直接影响自动化流水线。",
    ),
    (
        "deploy",
        ChangeBatchRiskSeverity.HIGH,
        "deployment_directory",
        "涉及部署目录，发布与回滚成本较高。",
    ),
    (
        "infra",
        ChangeBatchRiskSeverity.HIGH,
        "infrastructure_directory",
        "涉及基础设施目录，配置变更影响范围较大。",
    ),
    (
        "ops",
        ChangeBatchRiskSeverity.HIGH,
        "operations_directory",
        "涉及运维目录，需要显式人工确认。",
    ),
    (
        "scripts",
        ChangeBatchRiskSeverity.HIGH,
        "script_directory",
        "涉及脚本目录，可能改变构建、发布或维护行为。",
    ),
    (
        "runtime/data",
        ChangeBatchRiskSeverity.HIGH,
        "runtime_data_directory",
        "涉及运行时数据目录，容易影响本地状态与缓存。",
    ),
)

_SENSITIVE_FILE_RULES: tuple[
    tuple[str, ChangeBatchRiskSeverity, str, str],
    ...,
] = (
    (
        ".gitignore",
        ChangeBatchRiskSeverity.HIGH,
        "gitignore_file",
        "涉及忽略规则文件，可能改变仓库范围与提交边界。",
    ),
    (
        "package.json",
        ChangeBatchRiskSeverity.HIGH,
        "node_manifest",
        "涉及依赖清单文件，可能改变安装结果与构建入口。",
    ),
    (
        "package-lock.json",
        ChangeBatchRiskSeverity.HIGH,
        "node_lockfile",
        "涉及 Node 锁文件，依赖版本变更需要人工确认。",
    ),
    (
        "pnpm-lock.yaml",
        ChangeBatchRiskSeverity.HIGH,
        "pnpm_lockfile",
        "涉及 pnpm 锁文件，依赖版本变更需要人工确认。",
    ),
    (
        "yarn.lock",
        ChangeBatchRiskSeverity.HIGH,
        "yarn_lockfile",
        "涉及 Yarn 锁文件，依赖版本变更需要人工确认。",
    ),
    (
        "pyproject.toml",
        ChangeBatchRiskSeverity.HIGH,
        "python_project_config",
        "涉及 Python 项目配置文件，可能影响依赖或构建行为。",
    ),
    (
        "poetry.lock",
        ChangeBatchRiskSeverity.HIGH,
        "poetry_lockfile",
        "涉及 Poetry 锁文件，依赖版本变更需要人工确认。",
    ),
    (
        "requirements.txt",
        ChangeBatchRiskSeverity.HIGH,
        "python_requirements",
        "涉及 Python 依赖清单，需要显式人工确认。",
    ),
    (
        "Dockerfile",
        ChangeBatchRiskSeverity.HIGH,
        "dockerfile",
        "涉及镜像构建文件，可能改变运行时与发布链路。",
    ),
    (
        "docker-compose.yml",
        ChangeBatchRiskSeverity.HIGH,
        "docker_compose",
        "涉及容器编排文件，变更影响范围较大。",
    ),
    (
        "runtime/orchestrator/app/core/config.py",
        ChangeBatchRiskSeverity.HIGH,
        "runtime_core_config",
        "涉及运行时核心配置文件，需要显式人工确认。",
    ),
    (
        "runtime/orchestrator/app/core/db.py",
        ChangeBatchRiskSeverity.HIGH,
        "runtime_core_db",
        "涉及数据库与运行时初始化文件，需要显式人工确认。",
    ),
)

_CRITICAL_COMMAND_RULES: tuple[tuple[str, str, str], ...] = (
    (
        "git_reset_hard",
        "包含 `git reset --hard`，会覆写当前工作区与暂存区。",
        "git reset --hard",
    ),
    (
        "git_clean_force",
        "包含强制清理命令，可能直接删除未跟踪文件。",
        "git clean -f",
    ),
    (
        "shell_force_delete",
        "包含强制删除命令，可能造成不可逆文件丢失。",
        "rm -rf",
    ),
    (
        "powershell_force_delete",
        "包含 PowerShell 强制递归删除命令，风险较高。",
        "remove-item -recurse -force",
    ),
    (
        "windows_force_delete",
        "包含 Windows 强制删除命令，风险较高。",
        "del /f /s /q",
    ),
    (
        "windows_force_rmdir",
        "包含 Windows 递归删除目录命令，风险较高。",
        "rmdir /s /q",
    ),
)

_HIGH_COMMAND_RULES: tuple[tuple[str, str, str], ...] = (
    (
        "git_checkout",
        "包含分支或 HEAD 切换命令，可能改变当前工作区状态。",
        "git checkout",
    ),
    (
        "git_switch",
        "包含分支切换命令，可能改变当前工作区状态。",
        "git switch",
    ),
    (
        "git_branch_delete",
        "包含分支删除命令，需要显式人工确认。",
        "git branch -d",
    ),
    (
        "git_stash",
        "包含 stash 命令，会改变当前工作区内容。",
        "git stash",
    ),
    (
        "git_rebase",
        "包含 rebase 命令，历史改写风险较高。",
        "git rebase",
    ),
    (
        "git_cherry_pick",
        "包含 cherry-pick 命令，会改写当前分支历史。",
        "git cherry-pick",
    ),
    (
        "git_commit",
        "包含 commit 命令，属于 V4 当前冻结边界之外的真实 Git 写操作。",
        "git commit",
    ),
    (
        "git_tag",
        "包含 tag 命令，属于高风险 Git 写操作。",
        "git tag",
    ),
    (
        "git_push",
        "包含 push 命令，属于高风险 Git 写操作。",
        "git push",
    ),
    (
        "git_merge",
        "包含 merge 命令，属于高风险 Git 写操作。",
        "git merge",
    ),
    (
        "gh_pr_merge",
        "包含 PR merge 命令，属于高风险放行动作。",
        "gh pr merge",
    ),
)

_MEDIUM_WIDE_CHANGE_FILE_THRESHOLD = 5
_HIGH_WIDE_CHANGE_FILE_THRESHOLD = 8
_MEDIUM_WIDE_CHANGE_DIRECTORY_THRESHOLD = 3
_HIGH_WIDE_CHANGE_DIRECTORY_THRESHOLD = 4


@dataclass(slots=True, frozen=True)
class ChangeBatchPreflightTimelineEntry:
    """One Day08 preflight-related event projected onto the project timeline."""

    change_batch_id: UUID
    project_id: UUID
    change_batch_title: str
    event_kind: str
    summary: str
    occurred_at: datetime
    preflight_status: ChangeBatchPreflightStatus
    manual_confirmation_status: ChangeBatchManualConfirmationStatus
    overall_severity: ChangeBatchRiskSeverity | None


class ChangeRiskGuardError(ValueError):
    """Base error raised by the Day08 preflight guard service."""


class ChangeRiskGuardProjectNotFoundError(ChangeRiskGuardError):
    """Raised when the target project cannot be resolved."""


class ChangeRiskGuardBatchNotFoundError(ChangeRiskGuardError):
    """Raised when the target change batch cannot be resolved."""


class ChangeRiskGuardPreflightMissingError(ChangeRiskGuardError):
    """Raised when manual confirmation is requested before preflight runs."""


class ChangeRiskGuardManualConfirmationError(ChangeRiskGuardError):
    """Raised when a manual-confirmation action is not currently allowed."""


class ChangeRiskGuardService:
    """Evaluate Day08 preflight risk and apply manual-confirmation decisions."""

    def __init__(
        self,
        *,
        change_batch_repository: ChangeBatchRepository,
        project_repository: ProjectRepository,
    ) -> None:
        self.change_batch_repository = change_batch_repository
        self.project_repository = project_repository

    def run_preflight(
        self,
        *,
        change_batch_id: UUID,
        candidate_commands: list[str] | None = None,
    ) -> ChangeBatch:
        """Evaluate one change batch before execution and persist the result."""

        change_batch = self._require_change_batch(change_batch_id)
        evaluated_at = utc_now()
        target_paths = self._collect_target_paths(change_batch)
        inspected_commands = self._collect_commands(
            change_batch=change_batch,
            candidate_commands=candidate_commands or [],
        )
        findings = [
            *self._find_sensitive_paths(target_paths),
            *self._find_wide_change(change_batch=change_batch, target_paths=target_paths),
            *self._find_dangerous_commands(inspected_commands),
        ]
        manual_confirmation_required = any(
            finding.severity in {ChangeBatchRiskSeverity.HIGH, ChangeBatchRiskSeverity.CRITICAL}
            for finding in findings
        )
        summary = self._build_preflight_summary(
            findings=findings,
            manual_confirmation_required=manual_confirmation_required,
        )

        preflight = ChangeBatchPreflight(
            status=(
                ChangeBatchPreflightStatus.BLOCKED_REQUIRES_CONFIRMATION
                if manual_confirmation_required
                else ChangeBatchPreflightStatus.READY_FOR_EXECUTION
            ),
            summary=summary,
            blocked=manual_confirmation_required,
            ready_for_execution=not manual_confirmation_required,
            findings=findings,
            scanned_target_file_count=len(target_paths),
            unique_directory_count=len(
                {
                    str(PurePosixPath(path).parent)
                    for path in target_paths
                    if str(PurePosixPath(path).parent) not in {"", "."}
                }
            ),
            inspected_commands=inspected_commands,
            manual_confirmation_required=manual_confirmation_required,
            manual_confirmation_status=(
                ChangeBatchManualConfirmationStatus.PENDING
                if manual_confirmation_required
                else ChangeBatchManualConfirmationStatus.NOT_REQUIRED
            ),
            requested_at=evaluated_at if manual_confirmation_required else None,
            evaluated_at=evaluated_at,
            decided_at=None,
            decision_history=list(change_batch.preflight.decision_history),
        )

        updated_batch = change_batch.model_copy(
            update={
                "preflight": preflight,
                "updated_at": evaluated_at,
            }
        )
        return self.change_batch_repository.update(updated_batch)

    def apply_manual_confirmation(
        self,
        *,
        change_batch_id: UUID,
        action: ChangeBatchManualConfirmationAction,
        actor_name: str,
        summary: str,
        comment: str | None = None,
        highlighted_risks: list[str] | None = None,
    ) -> ChangeBatch:
        """Apply one explicit Day08 manual-confirmation decision."""

        change_batch = self._require_change_batch(change_batch_id)
        preflight = change_batch.preflight
        if preflight.status == ChangeBatchPreflightStatus.NOT_STARTED:
            raise ChangeRiskGuardPreflightMissingError(
                f"Change batch has not been preflight-checked yet: {change_batch_id}"
            )
        if not preflight.manual_confirmation_required:
            raise ChangeRiskGuardManualConfirmationError(
                "The latest preflight result does not require manual confirmation."
            )
        if preflight.manual_confirmation_status != ChangeBatchManualConfirmationStatus.PENDING:
            raise ChangeRiskGuardManualConfirmationError(
                "The latest preflight result is no longer waiting for manual confirmation."
            )

        decision = ChangeBatchManualConfirmationDecision(
            action=action,
            actor_name=actor_name,
            summary=summary,
            comment=comment,
            highlighted_risks=highlighted_risks or [],
        )

        updated_preflight = preflight.model_copy(
            update={
                "status": (
                    ChangeBatchPreflightStatus.MANUAL_CONFIRMED
                    if action == ChangeBatchManualConfirmationAction.APPROVE
                    else ChangeBatchPreflightStatus.MANUAL_REJECTED
                ),
                "summary": (
                    f"人工确认已放行：{decision.summary}"
                    if action == ChangeBatchManualConfirmationAction.APPROVE
                    else f"人工确认已驳回：{decision.summary}"
                ),
                "blocked": action != ChangeBatchManualConfirmationAction.APPROVE,
                "ready_for_execution": action == ChangeBatchManualConfirmationAction.APPROVE,
                "manual_confirmation_status": (
                    ChangeBatchManualConfirmationStatus.APPROVED
                    if action == ChangeBatchManualConfirmationAction.APPROVE
                    else ChangeBatchManualConfirmationStatus.REJECTED
                ),
                "decided_at": decision.created_at,
                "decision_history": [*preflight.decision_history, decision],
            }
        )

        updated_batch = change_batch.model_copy(
            update={
                "preflight": updated_preflight,
                "updated_at": decision.created_at,
            }
        )
        return self.change_batch_repository.update(updated_batch)

    def list_project_timeline_entries(
        self,
        project_id: UUID,
    ) -> list[ChangeBatchPreflightTimelineEntry]:
        """Return all Day08 preflight and confirmation events for one project."""

        self._ensure_project_exists(project_id)
        timeline_entries: list[ChangeBatchPreflightTimelineEntry] = []
        for change_batch in self.change_batch_repository.list_by_project_id(project_id):
            preflight = change_batch.preflight
            if (
                preflight.status != ChangeBatchPreflightStatus.NOT_STARTED
                and preflight.evaluated_at is not None
                and preflight.summary
            ):
                timeline_entries.append(
                    ChangeBatchPreflightTimelineEntry(
                        change_batch_id=change_batch.id,
                        project_id=change_batch.project_id,
                        change_batch_title=change_batch.title,
                        event_kind="preflight_evaluated",
                        summary=preflight.summary,
                        occurred_at=preflight.evaluated_at,
                        preflight_status=preflight.status,
                        manual_confirmation_status=preflight.manual_confirmation_status,
                        overall_severity=preflight.overall_severity,
                    )
                )

            if (
                preflight.manual_confirmation_status
                == ChangeBatchManualConfirmationStatus.PENDING
                and preflight.requested_at is not None
                and preflight.summary
            ):
                timeline_entries.append(
                    ChangeBatchPreflightTimelineEntry(
                        change_batch_id=change_batch.id,
                        project_id=change_batch.project_id,
                        change_batch_title=change_batch.title,
                        event_kind="manual_confirmation_requested",
                        summary=preflight.summary,
                        occurred_at=preflight.requested_at,
                        preflight_status=preflight.status,
                        manual_confirmation_status=preflight.manual_confirmation_status,
                        overall_severity=preflight.overall_severity,
                    )
                )

            for decision in preflight.decision_history:
                timeline_entries.append(
                    ChangeBatchPreflightTimelineEntry(
                        change_batch_id=change_batch.id,
                        project_id=change_batch.project_id,
                        change_batch_title=change_batch.title,
                        event_kind=(
                            "manual_confirmation_approved"
                            if decision.action
                            == ChangeBatchManualConfirmationAction.APPROVE
                            else "manual_confirmation_rejected"
                        ),
                        summary=decision.summary,
                        occurred_at=decision.created_at,
                        preflight_status=preflight.status,
                        manual_confirmation_status=preflight.manual_confirmation_status,
                        overall_severity=preflight.overall_severity,
                    )
                )

        timeline_entries.sort(
            key=lambda item: (item.occurred_at, item.change_batch_id),
            reverse=True,
        )
        return timeline_entries

    def _ensure_project_exists(self, project_id: UUID) -> None:
        """Validate that the target project exists."""

        if self.project_repository.get_by_id(project_id) is None:
            raise ChangeRiskGuardProjectNotFoundError(f"Project not found: {project_id}")

    def _require_change_batch(self, change_batch_id: UUID) -> ChangeBatch:
        """Return one persisted change batch or raise a Day08-specific error."""

        change_batch = self.change_batch_repository.get_by_id(change_batch_id)
        if change_batch is None:
            raise ChangeRiskGuardBatchNotFoundError(
                f"Change batch not found: {change_batch_id}"
            )

        self._ensure_project_exists(change_batch.project_id)
        return change_batch

    @staticmethod
    def _collect_target_paths(change_batch: ChangeBatch) -> list[str]:
        """Collect all unique target paths carried by the change-batch snapshots."""

        target_paths: list[str] = []
        seen_paths: set[str] = set()
        for snapshot in change_batch.plan_snapshots:
            for target_file in snapshot.target_files:
                normalized_path = target_file.relative_path.strip()
                if not normalized_path or normalized_path in seen_paths:
                    continue
                target_paths.append(normalized_path)
                seen_paths.add(normalized_path)

        return target_paths

    @staticmethod
    def _collect_commands(
        *,
        change_batch: ChangeBatch,
        candidate_commands: list[str],
    ) -> list[str]:
        """Collect deduplicated command text without executing anything."""

        commands: list[str] = []
        seen_commands: set[str] = set()
        combined_commands = [
            *(
                command
                for snapshot in change_batch.plan_snapshots
                for command in snapshot.verification_commands
            ),
            *candidate_commands,
        ]
        for command in combined_commands:
            normalized_command = " ".join(command.strip().split())
            if not normalized_command or normalized_command in seen_commands:
                continue
            commands.append(normalized_command)
            seen_commands.add(normalized_command)

        return commands

    def _find_sensitive_paths(self, target_paths: list[str]) -> list[ChangeBatchRiskFinding]:
        """Return standardized findings for sensitive directories and files."""

        findings: list[ChangeBatchRiskFinding] = []
        for target_path in target_paths:
            normalized_path = target_path.replace("\\", "/").lstrip("./")
            lower_path = normalized_path.lower()

            for prefix, severity, code, summary in _SENSITIVE_DIRECTORY_RULES:
                normalized_prefix = prefix.lower().rstrip("/")
                if lower_path == normalized_prefix or lower_path.startswith(
                    f"{normalized_prefix}/"
                ):
                    findings.append(
                        ChangeBatchRiskFinding(
                            category=ChangeBatchRiskCategory.SENSITIVE_DIRECTORY,
                            severity=severity,
                            code=code,
                            title="涉及敏感目录",
                            summary=summary,
                            affected_paths=[normalized_path],
                        )
                    )

            for candidate, severity, code, summary in _SENSITIVE_FILE_RULES:
                normalized_candidate = candidate.lower()
                basename = PurePosixPath(normalized_path).name.lower()
                if (
                    lower_path == normalized_candidate
                    or basename == normalized_candidate
                    or (
                        normalized_candidate == ".env"
                        and (basename == ".env" or basename.startswith(".env."))
                    )
                ):
                    findings.append(
                        ChangeBatchRiskFinding(
                            category=ChangeBatchRiskCategory.SENSITIVE_FILE,
                            severity=severity,
                            code=code,
                            title="涉及敏感文件",
                            summary=summary,
                            affected_paths=[normalized_path],
                        )
                    )

        return findings

    @staticmethod
    def _find_wide_change(
        *,
        change_batch: ChangeBatch,
        target_paths: list[str],
    ) -> list[ChangeBatchRiskFinding]:
        """Return one Day08 finding when the current batch scope is broad."""

        directory_names = {
            str(PurePosixPath(path).parent)
            for path in target_paths
            if str(PurePosixPath(path).parent) not in {"", "."}
        }
        if (
            len(target_paths) >= _HIGH_WIDE_CHANGE_FILE_THRESHOLD
            or len(directory_names) >= _HIGH_WIDE_CHANGE_DIRECTORY_THRESHOLD
        ):
            severity = ChangeBatchRiskSeverity.HIGH
        elif (
            len(target_paths) >= _MEDIUM_WIDE_CHANGE_FILE_THRESHOLD
            or len(directory_names) >= _MEDIUM_WIDE_CHANGE_DIRECTORY_THRESHOLD
        ):
            severity = ChangeBatchRiskSeverity.MEDIUM
        else:
            return []

        return [
            ChangeBatchRiskFinding(
                category=ChangeBatchRiskCategory.WIDE_CHANGE,
                severity=severity,
                code="wide_change_scope",
                title="涉及大范围变更",
                summary=(
                    f"当前批次覆盖 {len(change_batch.plan_snapshots)} 个任务、"
                    f"{len(target_paths)} 个目标文件、{len(directory_names)} 个目录，"
                    "需要先收敛范围再进入执行。"
                ),
                affected_paths=target_paths[:10],
            )
        ]

    @staticmethod
    def _find_dangerous_commands(commands: list[str]) -> list[ChangeBatchRiskFinding]:
        """Return standardized findings for dangerous command text."""

        findings_by_code: dict[str, dict[str, object]] = {}

        def append_command_finding(
            *,
            severity: ChangeBatchRiskSeverity,
            code: str,
            summary: str,
            command: str,
        ) -> None:
            entry = findings_by_code.setdefault(
                code,
                {
                    "severity": severity,
                    "summary": summary,
                    "commands": [],
                },
            )
            commands_list = entry["commands"]
            if isinstance(commands_list, list) and command not in commands_list:
                commands_list.append(command)

        for command in commands:
            lower_command = command.lower()
            for code, summary, token in _CRITICAL_COMMAND_RULES:
                if token in lower_command:
                    append_command_finding(
                        severity=ChangeBatchRiskSeverity.CRITICAL,
                        code=code,
                        summary=summary,
                        command=command,
                    )
            for code, summary, token in _HIGH_COMMAND_RULES:
                if token in lower_command:
                    append_command_finding(
                        severity=ChangeBatchRiskSeverity.HIGH,
                        code=code,
                        summary=summary,
                        command=command,
                    )

        findings: list[ChangeBatchRiskFinding] = []
        for code, payload in findings_by_code.items():
            severity = payload["severity"]
            summary = payload["summary"]
            related_commands = payload["commands"]
            if not isinstance(severity, ChangeBatchRiskSeverity):
                continue
            if not isinstance(summary, str):
                continue
            if not isinstance(related_commands, list):
                continue

            findings.append(
                ChangeBatchRiskFinding(
                    category=ChangeBatchRiskCategory.DANGEROUS_COMMAND,
                    severity=severity,
                    code=code,
                    title="识别到危险命令",
                    summary=summary,
                    related_commands=list(related_commands),
                )
            )

        return findings

    @staticmethod
    def _build_preflight_summary(
        *,
        findings: list[ChangeBatchRiskFinding],
        manual_confirmation_required: bool,
    ) -> str:
        """Build one short Day08 summary string for the latest preflight result."""

        if not findings:
            return "未识别出危险目录、敏感文件、大范围变更或危险命令，当前批次可进入执行。"

        critical_count = sum(
            1 for finding in findings if finding.severity == ChangeBatchRiskSeverity.CRITICAL
        )
        high_count = sum(
            1 for finding in findings if finding.severity == ChangeBatchRiskSeverity.HIGH
        )
        medium_count = sum(
            1 for finding in findings if finding.severity == ChangeBatchRiskSeverity.MEDIUM
        )
        low_count = sum(
            1 for finding in findings if finding.severity == ChangeBatchRiskSeverity.LOW
        )

        if manual_confirmation_required:
            return (
                f"识别到 {critical_count + high_count} 个高风险项"
                f"（严重 {critical_count} / 高 {high_count} / 中 {medium_count} / 低 {low_count}），"
                "已阻断执行并转入人工确认。"
            )

        return (
            f"识别到 {len(findings)} 条中低风险提醒"
            f"（中 {medium_count} / 低 {low_count}），当前批次可进入执行。"
        )
