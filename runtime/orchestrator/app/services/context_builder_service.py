"""Build a minimal task-scoped execution context package before worker execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.domain.code_context_pack import CodeContextPack, CodeContextPackEntry
from app.domain.project import Project, ProjectStage
from app.domain.project_role import ProjectRoleConfig
from app.domain.run import RunFailureCategory, RunStatus
from app.domain.task import (
    Task,
    TaskHumanStatus,
    TaskPriority,
    TaskRiskLevel,
)
from app.repositories.run_repository import RunRepository
from app.services.project_memory_service import (
    ProjectMemoryItem,
    ProjectMemoryService,
    TaskProjectMemoryContext,
)
from app.services.task_readiness_service import (
    TaskBlockingSignal,
    TaskDependencyReadinessItem,
    TaskReadinessService,
)


_RECENT_RUN_LIMIT = 3
_CONTEXT_SUMMARY_MAX_LENGTH = 1_200
_DEFAULT_CODE_CONTEXT_MAX_TOTAL_BYTES = 12_000
_DEFAULT_CODE_CONTEXT_MAX_BYTES_PER_FILE = 4_000
_CODE_CONTEXT_MATCH_PADDING = 2


@dataclass(slots=True, frozen=True)
class ContextRecentRunItem:
    """A compact excerpt from one previous run of the same task."""

    run_id: UUID
    status: RunStatus
    result_summary: str | None
    verification_summary: str | None
    failure_category: RunFailureCategory | None
    created_at: datetime


@dataclass(slots=True, frozen=True)
class TaskContextPackage:
    """Minimal context package assembled right before execution."""

    task_id: UUID
    task_title: str
    input_summary: str
    acceptance_criteria: list[str]
    priority: TaskPriority
    risk_level: TaskRiskLevel
    human_status: TaskHumanStatus
    paused_reason: str | None
    ready_for_execution: bool
    blocking_signals: list[TaskBlockingSignal]
    blocking_reasons: list[str]
    dependency_items: list[TaskDependencyReadinessItem]
    recent_runs: list[ContextRecentRunItem]
    context_summary: str


@dataclass(slots=True, frozen=True)
class ProjectStageContextRoleItem:
    """One role item included in the project-stage SOP context."""

    role_code: str
    role_name: str
    enabled: bool


@dataclass(slots=True, frozen=True)
class ProjectStageContextTaskItem:
    """One task item included in the project-stage SOP context."""

    task_id: UUID
    title: str
    status: str


@dataclass(slots=True, frozen=True)
class ProjectStageContextPackage:
    """Compact SOP context describing the current project stage."""

    project_id: UUID
    project_name: str
    current_stage: ProjectStage
    template_code: str | None
    template_name: str | None
    stage_title: str | None
    owner_roles: list[ProjectStageContextRoleItem]
    required_inputs: list[str]
    expected_outputs: list[str]
    guard_conditions: list[str]
    stage_tasks: list[ProjectStageContextTaskItem]
    can_advance: bool | None
    blocking_reasons: list[str]
    context_summary: str


@dataclass(slots=True, frozen=True)
class _CodeContextExcerptWindow:
    """One bounded excerpt window selected from a source file."""

    excerpt: str
    included_bytes: int
    line_count: int
    included_line_count: int
    start_line: int
    end_line: int
    truncated: bool


class CodeContextBuildError(ValueError):
    """Raised when Day05 cannot safely assemble one `CodeContextPack`."""


class ContextBuilderService:
    """Assemble a conservative, task-scoped context package for execution."""

    def __init__(
        self,
        *,
        run_repository: RunRepository,
        task_readiness_service: TaskReadinessService,
        project_memory_service: ProjectMemoryService | None = None,
    ) -> None:
        self.run_repository = run_repository
        self.task_readiness_service = task_readiness_service
        self.project_memory_service = project_memory_service

    def build_context_package(
        self,
        *,
        task: Task,
        include_project_memory: bool = False,
        project_memory_limit: int = 3,
    ) -> TaskContextPackage:
        """Build the minimal context package for one task."""

        readiness = self.task_readiness_service.evaluate_task(task=task)
        recent_runs = self._build_recent_run_items(task.id)
        project_memory_context = (
            self.build_task_memory_context(
                task=task,
                limit=project_memory_limit,
            )
            if include_project_memory and project_memory_limit > 0
            else None
        )
        context_summary = self._build_context_summary(
            task=task,
            dependency_items=readiness.dependency_items,
            recent_runs=recent_runs,
            blocking_reasons=readiness.blocking_reasons,
            project_memory_context=project_memory_context,
        )

        return TaskContextPackage(
            task_id=task.id,
            task_title=task.title,
            input_summary=task.input_summary,
            acceptance_criteria=task.acceptance_criteria,
            priority=task.priority,
            risk_level=task.risk_level,
            human_status=task.human_status,
            paused_reason=task.paused_reason,
            ready_for_execution=readiness.ready_for_execution,
            blocking_signals=readiness.blocking_signals,
            blocking_reasons=readiness.blocking_reasons,
            dependency_items=readiness.dependency_items,
            recent_runs=recent_runs,
            context_summary=context_summary,
        )

    def build_task_memory_context(
        self,
        *,
        task: Task,
        limit: int = 3,
    ) -> TaskProjectMemoryContext | None:
        """Recall a small set of Day14 project memories for the provided task."""

        if self.project_memory_service is None or task.project_id is None or limit <= 0:
            return None

        return self.project_memory_service.build_task_memory_context(
            task=task,
            limit=limit,
        )

    def build_project_stage_context(
        self,
        *,
        project: Project,
        template_code: str | None,
        template_name: str | None,
        stage_title: str | None,
        owner_roles: list[ProjectRoleConfig],
        required_inputs: list[str],
        expected_outputs: list[str],
        guard_conditions: list[str],
        stage_tasks: list[Task],
        can_advance: bool | None,
        blocking_reasons: list[str],
    ) -> ProjectStageContextPackage:
        """Build a concise SOP context summary for one project stage."""

        role_items = [
            ProjectStageContextRoleItem(
                role_code=role.role_code.value,
                role_name=role.name,
                enabled=role.enabled,
            )
            for role in owner_roles
        ]
        task_items = [
            ProjectStageContextTaskItem(
                task_id=task.id,
                title=task.title,
                status=task.status.value,
            )
            for task in stage_tasks
        ]
        context_summary = self._build_project_stage_summary(
            project=project,
            template_name=template_name,
            stage_title=stage_title,
            owner_roles=role_items,
            required_inputs=required_inputs,
            expected_outputs=expected_outputs,
            guard_conditions=guard_conditions,
            stage_tasks=task_items,
            can_advance=can_advance,
            blocking_reasons=blocking_reasons,
        )

        return ProjectStageContextPackage(
            project_id=project.id,
            project_name=project.name,
            current_stage=project.stage,
            template_code=template_code,
            template_name=template_name,
            stage_title=stage_title,
            owner_roles=role_items,
            required_inputs=list(required_inputs),
            expected_outputs=list(expected_outputs),
            guard_conditions=list(guard_conditions),
            stage_tasks=task_items,
            can_advance=can_advance,
            blocking_reasons=list(blocking_reasons),
            context_summary=context_summary,
        )

    def _build_recent_run_items(self, task_id: UUID) -> list[ContextRecentRunItem]:
        """Collect the latest few runs for the current task."""

        runs = self.run_repository.list_by_task_id(task_id)[:_RECENT_RUN_LIMIT]
        return [
            ContextRecentRunItem(
                run_id=run.id,
                status=run.status,
                result_summary=run.result_summary,
                verification_summary=run.verification_summary,
                failure_category=run.failure_category,
                created_at=run.created_at,
            )
            for run in runs
        ]

    def _build_context_summary(
        self,
        *,
        task: Task,
        dependency_items: list[TaskDependencyReadinessItem],
        recent_runs: list[ContextRecentRunItem],
        blocking_reasons: list[str],
        project_memory_context: TaskProjectMemoryContext | None = None,
    ) -> str:
        """Compress the structured context into one readable summary."""

        summary_parts = [
            f"Goal: {task.input_summary.strip()}",
            self._build_acceptance_summary(task.acceptance_criteria),
            self._build_dependency_summary(dependency_items),
            self._build_recent_run_summary(recent_runs),
            (
                f"Task posture: priority={task.priority.value}, risk={task.risk_level.value}, "
                f"human={task.human_status.value}."
            ),
        ]

        if blocking_reasons:
            summary_parts.append(
                "Blocking signals: " + " | ".join(reason.strip() for reason in blocking_reasons)
            )
        else:
            summary_parts.append("Blocking signals: none.")

        if project_memory_context is not None and project_memory_context.items:
            summary_parts.append(
                "Project memory: " + self._build_project_memory_summary(project_memory_context.items)
            )

        summary = "\n".join(summary_parts)
        if len(summary) <= _CONTEXT_SUMMARY_MAX_LENGTH:
            return summary

        return summary[: _CONTEXT_SUMMARY_MAX_LENGTH - 3].rstrip() + "..."

    @staticmethod
    def _build_acceptance_summary(acceptance_criteria: list[str]) -> str:
        """Format acceptance criteria into a single compact sentence."""

        if not acceptance_criteria:
            return "Acceptance criteria: not explicitly defined."

        bullet_text = "; ".join(acceptance_criteria[:3])
        if len(acceptance_criteria) > 3:
            bullet_text += f"; and {len(acceptance_criteria) - 3} more"
        return f"Acceptance criteria: {bullet_text}."

    @staticmethod
    def _build_dependency_summary(
        dependency_items: list[TaskDependencyReadinessItem],
    ) -> str:
        """Format dependency state into a compact summary."""

        if not dependency_items:
            return "Dependencies: none."

        summary_parts = [
            f"{dependency.title}({'missing' if dependency.missing else dependency.status.value})"
            for dependency in dependency_items
        ]
        return "Dependencies: " + ", ".join(summary_parts) + "."

    @staticmethod
    def _build_recent_run_summary(recent_runs: list[ContextRecentRunItem]) -> str:
        """Format recent run history into a compact summary."""

        if not recent_runs:
            return "Recent runs: none."

        summary_parts = [
            f"{run.status.value}"
            + (
                f"/{run.failure_category.value}"
                if run.failure_category is not None
                else ""
            )
            for run in recent_runs
        ]
        return "Recent runs: " + " -> ".join(summary_parts) + "."

    @staticmethod
    def _build_project_memory_summary(items: list[ProjectMemoryItem]) -> str:
        """Format recalled project memories into one compact sentence."""

        if not items:
            return "none."

        summary_parts = [
            f"{item.memory_type.value}:{item.summary}"
            for item in items[:3]
        ]
        if len(items) > 3:
            summary_parts.append(f"and {len(items) - 3} more")
        return " | ".join(summary_parts) + "."

    @staticmethod
    def _build_project_stage_summary(
        *,
        project: Project,
        template_name: str | None,
        stage_title: str | None,
        owner_roles: list[ProjectStageContextRoleItem],
        required_inputs: list[str],
        expected_outputs: list[str],
        guard_conditions: list[str],
        stage_tasks: list[ProjectStageContextTaskItem],
        can_advance: bool | None,
        blocking_reasons: list[str],
    ) -> str:
        """Compress the current SOP stage into a readable context summary."""

        role_summary = (
            ", ".join(
                f"{role.role_name}{'' if role.enabled else '(disabled)'}"
                for role in owner_roles
            )
            if owner_roles
            else "none"
        )
        task_summary = (
            ", ".join(f"{task.title}({task.status})" for task in stage_tasks[:4])
            if stage_tasks
            else "none"
        )
        if len(stage_tasks) > 4:
            task_summary += f"; and {len(stage_tasks) - 4} more"

        summary_parts = [
            f"Project: {project.name}",
            f"Template: {template_name or 'not selected'}",
            f"Current stage: {stage_title or project.stage.value}",
            f"Owner roles: {role_summary}.",
            "Required inputs: "
            + ("; ".join(required_inputs) if required_inputs else "not defined.")
            ,
            "Expected outputs: "
            + ("; ".join(expected_outputs) if expected_outputs else "not defined.")
            ,
            "Guard conditions: "
            + ("; ".join(guard_conditions) if guard_conditions else "not defined.")
            ,
            f"Stage tasks: {task_summary}.",
        ]

        if can_advance is None:
            summary_parts.append("Advance readiness: unknown.")
        elif can_advance:
            summary_parts.append("Advance readiness: ready for the next stage.")
        else:
            blocker_text = " | ".join(blocking_reasons[:3]) if blocking_reasons else "blocked"
            summary_parts.append(f"Advance readiness: blocked - {blocker_text}.")

        summary = "\n".join(summary_parts)
        if len(summary) <= _CONTEXT_SUMMARY_MAX_LENGTH:
            return summary

        return summary[: _CONTEXT_SUMMARY_MAX_LENGTH - 3].rstrip() + "..."

    def build_code_context_pack(
        self,
        *,
        repository_root_path: str,
        selected_paths: list[str],
        source_summary: str | None = None,
        focus_terms: list[str] | None = None,
        selection_reasons_by_path: dict[str, list[str]] | None = None,
        max_total_bytes: int = _DEFAULT_CODE_CONTEXT_MAX_TOTAL_BYTES,
        max_bytes_per_file: int = _DEFAULT_CODE_CONTEXT_MAX_BYTES_PER_FILE,
        project_id: UUID | None = None,
    ) -> CodeContextPack:
        """Build one bounded Day05 `CodeContextPack` from selected repository files."""

        if max_total_bytes <= 0:
            raise CodeContextBuildError("max_total_bytes must be greater than zero.")
        if max_bytes_per_file <= 0:
            raise CodeContextBuildError("max_bytes_per_file must be greater than zero.")

        normalized_selected_paths = self._normalize_selected_paths(selected_paths)
        if not normalized_selected_paths:
            raise CodeContextBuildError("selected_paths cannot be empty.")

        try:
            root_path = Path(repository_root_path).resolve(strict=True)
        except FileNotFoundError as exc:
            raise CodeContextBuildError(
                "Repository root_path does not exist during CodeContextPack build."
            ) from exc

        if not root_path.is_dir():
            raise CodeContextBuildError(
                "Repository root_path must point to one directory during CodeContextPack build."
            )

        normalized_focus_terms = self._normalize_focus_terms(focus_terms or [])
        normalized_reason_map = {
            relative_path: [
                reason.strip()
                for reason in reasons
                if isinstance(reason, str) and reason.strip()
            ]
            for relative_path, reasons in (selection_reasons_by_path or {}).items()
            if isinstance(relative_path, str)
        }

        remaining_bytes = max_total_bytes
        entries: list[CodeContextPackEntry] = []
        omitted_paths: list[str] = []

        for relative_path in normalized_selected_paths:
            if remaining_bytes <= 0:
                omitted_paths.append(relative_path)
                continue

            resolved_file_path = self._resolve_selected_file_path(
                root_path=root_path,
                relative_path=relative_path,
            )
            raw_bytes = self._read_code_context_bytes(resolved_file_path)
            text_content = raw_bytes.decode("utf-8", errors="replace")
            excerpt_window = self._build_code_context_excerpt(
                text_content=text_content,
                byte_budget=min(max_bytes_per_file, remaining_bytes),
                focus_terms=normalized_focus_terms,
            )
            if excerpt_window.included_bytes == 0 and raw_bytes:
                omitted_paths.append(relative_path)
                continue

            remaining_bytes -= excerpt_window.included_bytes
            entries.append(
                CodeContextPackEntry(
                    relative_path=relative_path,
                    language=self._infer_code_context_language(resolved_file_path),
                    file_type=self._infer_code_context_file_type(resolved_file_path),
                    byte_size=len(raw_bytes),
                    line_count=excerpt_window.line_count,
                    included_bytes=excerpt_window.included_bytes,
                    included_line_count=excerpt_window.included_line_count,
                    start_line=excerpt_window.start_line,
                    end_line=excerpt_window.end_line,
                    truncated=excerpt_window.truncated,
                    match_reasons=normalized_reason_map.get(relative_path, []),
                    excerpt=excerpt_window.excerpt,
                )
            )

        return CodeContextPack(
            project_id=project_id,
            repository_root_path=str(root_path),
            source_summary=(
                source_summary.strip()
                if source_summary is not None and source_summary.strip()
                else "手动选择文件并生成代码上下文包。"
            ),
            focus_terms=normalized_focus_terms,
            selected_paths=normalized_selected_paths,
            omitted_paths=omitted_paths,
            max_total_bytes=max_total_bytes,
            max_bytes_per_file=max_bytes_per_file,
            included_file_count=len(entries),
            total_included_bytes=sum(entry.included_bytes for entry in entries),
            truncated=bool(
                omitted_paths
                or any(entry.truncated for entry in entries)
            ),
            entries=entries,
        )

    @staticmethod
    def _normalize_selected_paths(selected_paths: list[str]) -> list[str]:
        """Normalize one relative-path selection list while preserving order."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in selected_paths:
            normalized_value = value.replace("\\", "/").strip()
            if normalized_value.startswith("./"):
                normalized_value = normalized_value[2:]
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @staticmethod
    def _normalize_focus_terms(focus_terms: list[str]) -> list[str]:
        """Normalize one focus-term list for excerpt positioning."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for value in focus_terms:
            normalized_value = value.strip().lower()
            if not normalized_value or normalized_value in seen_items:
                continue

            normalized_items.append(normalized_value)
            seen_items.add(normalized_value)

        return normalized_items

    @staticmethod
    def _resolve_selected_file_path(*, root_path: Path, relative_path: str) -> Path:
        """Resolve one selected relative path and keep it inside the repository root."""

        candidate_path = (root_path / relative_path).resolve(strict=True)
        try:
            candidate_path.relative_to(root_path)
        except ValueError as exc:
            raise CodeContextBuildError(
                f"Selected path escapes the repository root: {relative_path}"
            ) from exc

        if not candidate_path.is_file():
            raise CodeContextBuildError(
                f"Selected path is not a file inside the repository: {relative_path}"
            )

        return candidate_path

    @staticmethod
    def _read_code_context_bytes(file_path: Path) -> bytes:
        """Read one selected source file and reject obvious binary payloads."""

        try:
            raw_bytes = file_path.read_bytes()
        except OSError as exc:
            raise CodeContextBuildError(
                f"Unable to read selected file during CodeContextPack build: {file_path}"
            ) from exc

        if b"\x00" in raw_bytes:
            raise CodeContextBuildError(
                f"Selected file is not a text file and cannot enter CodeContextPack: {file_path.name}"
            )

        return raw_bytes

    def _build_code_context_excerpt(
        self,
        *,
        text_content: str,
        byte_budget: int,
        focus_terms: list[str],
    ) -> _CodeContextExcerptWindow:
        """Pick one bounded excerpt window from the selected file content."""

        if byte_budget <= 0:
            return _CodeContextExcerptWindow(
                excerpt="",
                included_bytes=0,
                line_count=0,
                included_line_count=0,
                start_line=0,
                end_line=0,
                truncated=bool(text_content),
            )

        lines = text_content.splitlines()
        if not lines:
            return _CodeContextExcerptWindow(
                excerpt="",
                included_bytes=0,
                line_count=0,
                included_line_count=0,
                start_line=0,
                end_line=0,
                truncated=False,
            )

        start_index = 0
        if focus_terms:
            for index, line in enumerate(lines):
                normalized_line = line.lower()
                if any(term in normalized_line for term in focus_terms):
                    start_index = max(0, index - _CODE_CONTEXT_MATCH_PADDING)
                    break

        included_lines: list[str] = []
        included_bytes = 0
        end_index = start_index - 1
        truncated = start_index > 0

        for index in range(start_index, len(lines)):
            line = lines[index]
            line_fragment = line if not included_lines else f"\n{line}"
            line_fragment_bytes = len(line_fragment.encode("utf-8"))

            if included_lines and included_bytes + line_fragment_bytes > byte_budget:
                truncated = True
                break

            if not included_lines and line_fragment_bytes > byte_budget:
                truncated_line = self._truncate_text_to_byte_budget(
                    line,
                    byte_budget,
                )
                included_lines.append(truncated_line)
                included_bytes = len(truncated_line.encode("utf-8"))
                end_index = index
                truncated = True
                break

            included_lines.append(line)
            included_bytes += line_fragment_bytes
            end_index = index

        if end_index < len(lines) - 1:
            truncated = True

        excerpt = "\n".join(included_lines)
        return _CodeContextExcerptWindow(
            excerpt=excerpt,
            included_bytes=included_bytes,
            line_count=len(lines),
            included_line_count=len(included_lines),
            start_line=start_index + 1 if included_lines else 0,
            end_line=end_index + 1 if included_lines else 0,
            truncated=truncated,
        )

    @staticmethod
    def _truncate_text_to_byte_budget(text: str, byte_budget: int) -> str:
        """Trim one line so it fits inside the requested byte budget."""

        if byte_budget <= 0:
            return ""

        encoded_text = text.encode("utf-8")
        if len(encoded_text) <= byte_budget:
            return text

        truncated_bytes = encoded_text[:byte_budget]
        normalized_text = truncated_bytes.decode("utf-8", errors="ignore").rstrip()

        if not normalized_text:
            return ""

        ellipsis = "..."
        while normalized_text and len((normalized_text + ellipsis).encode("utf-8")) > byte_budget:
            normalized_text = normalized_text[:-1]

        if not normalized_text:
            return ""

        return normalized_text + ellipsis

    @staticmethod
    def _infer_code_context_language(file_path: Path) -> str:
        """Infer a coarse language label for one selected file."""

        normalized_name = file_path.name.lower()
        if normalized_name == "dockerfile":
            return "Docker"
        if normalized_name == "makefile":
            return "Makefile"

        suffix = file_path.suffix.lower()
        if suffix in {".ts", ".tsx"}:
            return "TypeScript"
        if suffix in {".js", ".jsx", ".mjs"}:
            return "JavaScript"
        if suffix == ".py":
            return "Python"
        if suffix == ".md":
            return "Markdown"
        if suffix == ".json":
            return "JSON"
        if suffix in {".yaml", ".yml"}:
            return "YAML"
        if suffix == ".toml":
            return "TOML"
        if suffix == ".sql":
            return "SQL"
        if suffix == ".sh":
            return "Shell"
        if suffix == ".ps1":
            return "PowerShell"

        return "Other"

    @staticmethod
    def _infer_code_context_file_type(file_path: Path) -> str:
        """Infer a stable extension-like file-type label for one selected file."""

        normalized_name = file_path.name.lower()
        if normalized_name == "dockerfile":
            return "dockerfile"
        if normalized_name == "makefile":
            return "makefile"

        normalized_suffix = file_path.suffix.lower().lstrip(".")
        if normalized_suffix:
            return normalized_suffix

        return normalized_name
