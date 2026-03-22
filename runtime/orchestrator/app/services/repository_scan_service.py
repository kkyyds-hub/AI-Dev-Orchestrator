"""Repository workspace scan helpers for V4 Day02."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.domain._base import utc_now
from app.domain.repository_snapshot import (
    RepositoryLanguageStat,
    RepositorySnapshot,
    RepositorySnapshotStatus,
    RepositoryTreeNode,
    RepositoryTreeNodeKind,
)
from app.repositories.project_repository import ProjectRepository
from app.repositories.repository_snapshot_repository import (
    RepositorySnapshotRepository,
)
from app.repositories.repository_workspace_repository import (
    RepositoryWorkspaceRepository,
)
from app.services.repository_workspace_service import (
    DEFAULT_REPOSITORY_IGNORE_RULE_SUMMARY,
)


DEFAULT_REPOSITORY_SCAN_IGNORED_DIRECTORIES = DEFAULT_REPOSITORY_IGNORE_RULE_SUMMARY
MAX_TREE_DEPTH = 3
MAX_TREE_ENTRIES_PER_DIRECTORY = 20

_LANGUAGE_BY_NAME = {
    "dockerfile": "Docker",
    "makefile": "Makefile",
}
_LANGUAGE_BY_SUFFIX = {
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".cs": "C#",
    ".css": "CSS",
    ".go": "Go",
    ".html": "HTML",
    ".java": "Java",
    ".js": "JavaScript",
    ".json": "JSON",
    ".jsx": "JavaScript",
    ".kt": "Kotlin",
    ".md": "Markdown",
    ".mjs": "JavaScript",
    ".php": "PHP",
    ".ps1": "PowerShell",
    ".py": "Python",
    ".rb": "Ruby",
    ".rs": "Rust",
    ".sh": "Shell",
    ".sql": "SQL",
    ".toml": "TOML",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".txt": "Text",
    ".xml": "XML",
    ".yaml": "YAML",
    ".yml": "YAML",
}


class RepositoryScanError(ValueError):
    """Base error raised by the repository-scan service."""


class RepositoryScanProjectNotFoundError(RepositoryScanError):
    """Raised when one project is missing during Day02 scan actions."""


class RepositoryScanWorkspaceNotFoundError(RepositoryScanError):
    """Raised when one project has no bound repository workspace."""


@dataclass(slots=True)
class _DirectoryScanResult:
    """In-memory aggregate returned while walking one directory subtree."""

    child_nodes: list[RepositoryTreeNode]
    directory_count: int
    file_count: int
    language_counter: Counter[str]
    truncated: bool = False


class RepositoryScanService:
    """Build and persist one minimal repository snapshot for a project."""

    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        repository_workspace_repository: RepositoryWorkspaceRepository,
        repository_snapshot_repository: RepositorySnapshotRepository,
    ) -> None:
        self.project_repository = project_repository
        self.repository_workspace_repository = repository_workspace_repository
        self.repository_snapshot_repository = repository_snapshot_repository

    def scan_project_repository(self, project_id: UUID) -> RepositorySnapshot:
        """Refresh one project's latest repository snapshot."""

        if not self.project_repository.exists(project_id):
            raise RepositoryScanProjectNotFoundError(f"Project not found: {project_id}")

        workspace = self.repository_workspace_repository.get_by_project_id(project_id)
        if workspace is None:
            raise RepositoryScanWorkspaceNotFoundError(
                f"Repository workspace not found for project: {project_id}"
            )

        existing_snapshot = self.repository_snapshot_repository.get_by_project_id(project_id)
        now = utc_now()
        ignored_directory_names = self._build_ignored_directory_names(
            workspace.ignore_rule_summary
        )

        try:
            scan_result = self._scan_workspace(
                Path(workspace.root_path),
                ignored_directory_names=ignored_directory_names,
            )
            snapshot_payload = dict(
                project_id=project_id,
                repository_workspace_id=workspace.id,
                repository_root_path=workspace.root_path,
                status=RepositorySnapshotStatus.SUCCESS,
                directory_count=scan_result.directory_count,
                file_count=scan_result.file_count,
                ignored_directory_names=ignored_directory_names,
                language_breakdown=self._build_language_breakdown(
                    scan_result.language_counter
                ),
                tree=scan_result.child_nodes,
                scan_error=None,
                scanned_at=now,
                created_at=existing_snapshot.created_at if existing_snapshot is not None else now,
                updated_at=now,
            )
        except Exception as exc:  # pragma: no cover - guarded by smoke flow instead
            snapshot_payload = dict(
                project_id=project_id,
                repository_workspace_id=workspace.id,
                repository_root_path=workspace.root_path,
                status=RepositorySnapshotStatus.FAILED,
                directory_count=0,
                file_count=0,
                ignored_directory_names=ignored_directory_names,
                language_breakdown=[],
                tree=[],
                scan_error=str(exc),
                scanned_at=now,
                created_at=existing_snapshot.created_at if existing_snapshot is not None else now,
                updated_at=now,
            )

        if existing_snapshot is not None:
            snapshot_payload["id"] = existing_snapshot.id

        snapshot = RepositorySnapshot(**snapshot_payload)
        return self.repository_snapshot_repository.upsert(snapshot)

    def get_latest_project_snapshot(self, project_id: UUID) -> RepositorySnapshot | None:
        """Return one project's latest repository snapshot, if present."""

        if not self.project_repository.exists(project_id):
            raise RepositoryScanProjectNotFoundError(f"Project not found: {project_id}")

        workspace = self.repository_workspace_repository.get_by_project_id(project_id)
        snapshot = self.repository_snapshot_repository.get_by_project_id(project_id)
        if workspace is None or snapshot is None:
            return None
        if snapshot.repository_root_path != workspace.root_path:
            return None

        return snapshot

    @staticmethod
    def _build_ignored_directory_names(ignore_rule_summary: list[str]) -> list[str]:
        """Merge the Day01 baseline ignore names with repository-specific entries."""

        normalized_items: list[str] = []
        seen_items: set[str] = set()

        for item in (
            *DEFAULT_REPOSITORY_SCAN_IGNORED_DIRECTORIES,
            *ignore_rule_summary,
        ):
            normalized_item = item.strip()
            if not normalized_item or normalized_item in seen_items:
                continue

            normalized_items.append(normalized_item)
            seen_items.add(normalized_item)

        return normalized_items

    def _scan_workspace(
        self,
        root_path: Path,
        *,
        ignored_directory_names: list[str],
    ) -> _DirectoryScanResult:
        """Walk one repository tree and return a structured Day02 summary."""

        if not root_path.exists():
            raise FileNotFoundError("Repository root_path does not exist during scan.")
        if not root_path.is_dir():
            raise NotADirectoryError(
                "Repository root_path must point to one local directory during scan."
            )

        return self._scan_directory(
            root_path,
            root_path=root_path,
            ignored_directory_names=set(ignored_directory_names),
            depth=0,
        )

    def _scan_directory(
        self,
        directory_path: Path,
        *,
        root_path: Path,
        ignored_directory_names: set[str],
        depth: int,
    ) -> _DirectoryScanResult:
        """Recursively walk one directory while storing only a bounded tree summary."""

        try:
            entries = list(directory_path.iterdir())
        except OSError as exc:
            raise OSError(
                f"Unable to read directory during repository scan: {directory_path}"
            ) from exc

        entries.sort(
            key=lambda entry: (
                1 if self._is_traversable_directory(entry) else 2,
                entry.name.lower(),
            )
        )

        child_nodes: list[RepositoryTreeNode] = []
        directory_count = 0
        file_count = 0
        language_counter: Counter[str] = Counter()
        truncated = False

        for entry in entries:
            entry_is_directory = self._is_traversable_directory(entry)
            if entry_is_directory and entry.name in ignored_directory_names:
                continue

            relative_path = entry.relative_to(root_path).as_posix()

            if entry_is_directory:
                nested_result = self._scan_directory(
                    entry,
                    root_path=root_path,
                    ignored_directory_names=ignored_directory_names,
                    depth=depth + 1,
                )
                directory_count += 1 + nested_result.directory_count
                file_count += nested_result.file_count
                language_counter.update(nested_result.language_counter)

                hidden_descendants = (
                    depth + 1 >= MAX_TREE_DEPTH
                    and (nested_result.directory_count > 0 or nested_result.file_count > 0)
                )
                node = RepositoryTreeNode(
                    name=entry.name,
                    relative_path=relative_path,
                    kind=RepositoryTreeNodeKind.DIRECTORY,
                    directory_count=nested_result.directory_count,
                    file_count=nested_result.file_count,
                    children=nested_result.child_nodes,
                    truncated=nested_result.truncated or hidden_descendants,
                )
            else:
                file_count += 1
                language_counter[self._infer_language(entry)] += 1
                node = RepositoryTreeNode(
                    name=entry.name,
                    relative_path=relative_path,
                    kind=RepositoryTreeNodeKind.FILE,
                    directory_count=0,
                    file_count=1,
                    children=[],
                    truncated=False,
                )

            if depth < MAX_TREE_DEPTH and len(child_nodes) < MAX_TREE_ENTRIES_PER_DIRECTORY:
                child_nodes.append(node)
            else:
                truncated = True

        return _DirectoryScanResult(
            child_nodes=child_nodes,
            directory_count=directory_count,
            file_count=file_count,
            language_counter=language_counter,
            truncated=truncated,
        )

    @staticmethod
    def _is_traversable_directory(path: Path) -> bool:
        """Return whether one entry should be traversed as a directory node."""

        try:
            return path.is_dir() and not path.is_symlink()
        except OSError as exc:
            raise OSError(
                f"Unable to inspect directory entry during repository scan: {path}"
            ) from exc

    @staticmethod
    def _build_language_breakdown(
        language_counter: Counter[str],
    ) -> list[RepositoryLanguageStat]:
        """Convert one language counter into a stable response payload."""

        return [
            RepositoryLanguageStat(language=language, file_count=file_count)
            for language, file_count in sorted(
                language_counter.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

    @staticmethod
    def _infer_language(path: Path) -> str:
        """Resolve one file name into a coarse language bucket."""

        normalized_name = path.name.strip().lower()
        if normalized_name in _LANGUAGE_BY_NAME:
            return _LANGUAGE_BY_NAME[normalized_name]

        return _LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "Other")
